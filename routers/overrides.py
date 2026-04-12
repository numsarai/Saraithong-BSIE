"""
routers/overrides.py
--------------------
Override-management API routes extracted from app.py.
"""

import logging

import pandas as pd
from services.auth_service import require_auth
from fastapi import Depends, APIRouter, HTTPException
from fastapi.responses import JSONResponse

from core.override_manager import (
    add_override,
    apply_overrides_to_df,
    get_all_overrides,
    remove_override,
)
from paths import OUTPUT_DIR
from persistence.base import get_db_session
from persistence.schemas import OverrideRequest
from services.audit_service import log_audit

logger = logging.getLogger("bsie.api")

router = APIRouter(prefix="/api", tags=["overrides"], dependencies=[Depends(require_auth)])


@router.post("/override")
async def api_add_override(body: OverrideRequest):
    """Add or update a manual relationship override."""
    tid = body.transaction_id.strip()
    # Accept both API-native and frontend-react payload keys for compatibility.
    frm = (body.from_account or body.override_from_account or "").strip()
    to = (body.to_account or body.override_to_account or "").strip()
    reason = body.reason or body.override_reason or ""
    by = body.override_by or "analyst"
    account_number = (body.account_number or body.account or "").strip()

    if not tid or not frm or not to:
        raise HTTPException(400, "transaction_id, from_account, and to_account are required")

    record = add_override(tid, frm, to, reason, by, account_number=account_number)

    with get_db_session() as session:
        log_audit(
            session,
            object_type="override",
            object_id=f"{account_number or 'global'}::{tid}",
            action_type="upsert_override",
            field_name="override_flow",
            old_value=None,
            new_value=record,
            changed_by=by,
            reason=reason,
        )
        session.commit()

    # Re-apply overrides to persisted CSV if it exists
    _reapply_overrides_to_csv(tid, account_number=account_number)

    return JSONResponse({"status": "ok", "override": record})


@router.delete("/override/{transaction_id}")
async def api_remove_override(transaction_id: str, account_number: str = "", operator: str = "analyst"):
    removed = remove_override(transaction_id, account_number=account_number)
    if not removed:
        raise HTTPException(404, "Override not found")
    changed_by = str(operator or "analyst").strip() or "analyst"
    with get_db_session() as session:
        log_audit(
            session,
            object_type="override",
            object_id=f"{account_number or 'global'}::{transaction_id}",
            action_type="delete_override",
            changed_by=changed_by,
            reason="override removed",
        )
        session.commit()
    return JSONResponse({"status": "removed"})


@router.get("/overrides")
async def api_list_overrides():
    return JSONResponse({"overrides": get_all_overrides()})


def _reapply_overrides_to_csv(changed_txn_id: str, account_number: str = "") -> None:
    """Re-run override application on all account CSVs that contain the transaction."""
    for acct_dir in OUTPUT_DIR.iterdir():
        if not acct_dir.is_dir():
            continue
        if account_number and acct_dir.name != "".join(c for c in account_number if c.isdigit()):
            continue
        txn_csv = acct_dir / "processed" / "transactions.csv"
        if not txn_csv.exists():
            continue
        try:
            df = pd.read_csv(txn_csv, dtype=str, encoding="utf-8-sig").fillna("")
            if changed_txn_id not in df.get("transaction_id", pd.Series()).values:
                continue
            df = apply_overrides_to_df(df, account_number=acct_dir.name)
            df.to_csv(txn_csv, index=False, encoding="utf-8-sig")
        except Exception as e:
            logger.warning(f"Could not reapply overrides to {txn_csv}: {e}")
