"""
override_manager.py
-------------------
Manages manual relationship overrides for transactions.
Overrides are stored in the SQLite DB (override table).

Override record:
{
  "transaction_id"       : str,
  "override_from_account": str,
  "override_to_account"  : str,
  "override_reason"      : str,
  "override_by"          : str,
  "override_timestamp"   : ISO str
}
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────

def _make_override_key(transaction_id: str, account_number: str = "") -> str:
    transaction_id = str(transaction_id or "").strip()
    account_number = str(account_number or "").strip()
    if account_number:
        return f"{account_number}::{transaction_id}"
    return transaction_id


def _split_override_key(key: str) -> tuple[str, str]:
    text = str(key or "").strip()
    if "::" in text:
        account_number, transaction_id = text.split("::", 1)
        return account_number.strip(), transaction_id.strip()
    return "", text

def add_override(
    transaction_id: str,
    from_account: str,
    to_account: str,
    reason: str = "",
    override_by: str = "analyst",
    account_number: str = "",
) -> Dict:
    """
    Add or update a manual relationship override.
    If an override for the same transaction_id already exists, it is replaced.

    Returns the saved override record.
    """
    from database import get_session, Override
    from sqlmodel import select

    now = datetime.now(timezone.utc)
    override_key = _make_override_key(transaction_id, account_number)

    with get_session() as session:
        statement = select(Override).where(Override.transaction_id == override_key)
        existing = session.exec(statement).first()

        if existing:
            existing.override_from_account = from_account
            existing.override_to_account = to_account
            existing.override_reason = reason
            existing.override_by = override_by
            existing.override_timestamp = now
            session.add(existing)
            session.commit()
            session.refresh(existing)
            result = existing.to_dict()
            logger.info(f"Updated override for {override_key}")
            result["account_number"] = account_number
            result["transaction_id"] = transaction_id
            return result

        row = Override(
            transaction_id=override_key,
            override_from_account=from_account,
            override_to_account=to_account,
            override_reason=reason,
            override_by=override_by,
            override_timestamp=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        result = row.to_dict()
        logger.info(f"Added override for {override_key}")
        result["account_number"] = account_number
        result["transaction_id"] = transaction_id
        return result


def remove_override(transaction_id: str, account_number: str = "") -> bool:
    """Remove an override by transaction_id. Returns True if removed."""
    from database import get_session, Override
    from sqlmodel import select

    override_key = _make_override_key(transaction_id, account_number)
    with get_session() as session:
        statement = select(Override).where(Override.transaction_id == override_key)
        existing = session.exec(statement).first()
        if existing:
            session.delete(existing)
            session.commit()
            logger.info(f"Removed override for {override_key}")
            return True
    return False


def get_all_overrides() -> List[Dict]:
    """Return all stored overrides."""
    from database import get_session, Override
    from sqlmodel import select

    with get_session() as session:
        all_overrides = session.exec(select(Override)).all()
        rows: list[Dict] = []
        for override in all_overrides:
            payload = override.to_dict()
            account_number, transaction_id = _split_override_key(payload["transaction_id"])
            payload["account_number"] = account_number
            payload["transaction_id"] = transaction_id
            rows.append(payload)
        return rows


def get_override(transaction_id: str, account_number: str = "") -> Optional[Dict]:
    """Return override for a specific transaction_id or None."""
    from database import get_session, Override
    from sqlmodel import select

    override_key = _make_override_key(transaction_id, account_number)
    with get_session() as session:
        statement = select(Override).where(Override.transaction_id == override_key)
        row = session.exec(statement).first()
        if row:
            payload = row.to_dict()
            payload["account_number"] = account_number
            payload["transaction_id"] = transaction_id
            return payload
    return None


def apply_overrides_to_df(df: pd.DataFrame, account_number: str = "") -> pd.DataFrame:
    """
    Apply all stored overrides to a transaction DataFrame.

    Adds / updates columns:
        is_overridden         : bool
        override_from_account : str
        override_to_account   : str
        override_reason       : str
        override_by           : str
        override_timestamp    : str

    For overridden rows:
        from_account = override_from_account
        to_account   = override_to_account
        confidence   = 1.0
    """
    overrides = get_all_overrides()
    if not overrides:
        # Ensure override columns exist even with no overrides
        df = df.copy()
        for col in ["is_overridden", "override_from_account", "override_to_account",
                    "override_reason", "override_by", "override_timestamp"]:
            if col not in df.columns:
                df[col] = "" if col != "is_overridden" else False
        return df

    override_map: Dict[str, Dict] = {}
    for override in overrides:
        scoped_account = str(override.get("account_number") or "").strip()
        if account_number:
            if scoped_account != account_number:
                continue
        elif scoped_account:
            continue
        override_map[str(override["transaction_id"])] = override
    df = df.copy()

    # Initialise override columns
    df["is_overridden"]         = False
    df["override_from_account"] = ""
    df["override_to_account"]   = ""
    df["override_reason"]       = ""
    df["override_by"]           = ""
    df["override_timestamp"]    = ""

    applied = 0
    for idx, row in df.iterrows():
        tid = str(row.get("transaction_id", ""))
        if tid in override_map:
            ov = override_map[tid]
            df.at[idx, "is_overridden"]         = True
            df.at[idx, "override_from_account"] = ov["override_from_account"]
            df.at[idx, "override_to_account"]   = ov["override_to_account"]
            df.at[idx, "override_reason"]       = ov.get("override_reason", "")
            df.at[idx, "override_by"]           = ov.get("override_by", "")
            df.at[idx, "override_timestamp"]    = ov.get("override_timestamp", "")
            # Apply to link columns
            df.at[idx, "from_account"]          = ov["override_from_account"]
            df.at[idx, "to_account"]            = ov["override_to_account"]
            df.at[idx, "confidence"]            = 1.0
            applied += 1

    if applied:
        logger.info(f"Applied {applied} manual overrides to DataFrame")
    return df
