"""
routers/review.py
-----------------
Review-related API routes extracted from app.py.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from persistence.base import get_db_session
from persistence.models import Transaction
from services.audit_service import log_audit
from persistence.schemas import (
    AccountCorrectionRequest,
    ReviewRequest,
    TransactionCorrectionRequest,
)
from services.review_service import (
    get_account_review_payload,
    review_duplicate_group,
    review_match,
    update_account_fields,
    update_transaction_fields,
)
from services.search_service import (
    list_duplicate_groups,
    list_matches,
)

router = APIRouter(prefix="/api", tags=["review"])


@router.get("/duplicates")
async def api_duplicates(limit: int = 100, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_duplicate_groups(session, limit=limit, offset=offset)})


@router.post("/duplicates/{group_id}/review")
async def api_review_duplicate(group_id: str, body: ReviewRequest):
    with get_db_session() as session:
        group = review_duplicate_group(
            session,
            group_id=group_id,
            decision_value=body.decision_value,
            reviewer=body.reviewer,
            reviewer_note=body.reviewer_note,
        )
        if not group:
            raise HTTPException(404, "Duplicate group not found")
        session.commit()
        return JSONResponse({"status": "ok", "group_id": group.id, "resolution_status": group.resolution_status})


@router.get("/matches")
async def api_matches(status: str = "", limit: int = 100, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_matches(session, status=status, limit=limit, offset=offset)})


@router.post("/matches/{match_id}/review")
async def api_review_match(match_id: str, body: ReviewRequest):
    with get_db_session() as session:
        match = review_match(
            session,
            match_id=match_id,
            decision_value=body.decision_value,
            reviewer=body.reviewer,
            reviewer_note=body.reviewer_note,
        )
        if not match:
            raise HTTPException(404, "Match not found")
        session.commit()
        return JSONResponse({"status": "ok", "match_id": match.id, "match_status": match.status})


@router.post("/transactions/{transaction_id}/review")
async def api_review_transaction(transaction_id: str, body: TransactionCorrectionRequest):
    with get_db_session() as session:
        transaction = update_transaction_fields(
            session,
            transaction_id=transaction_id,
            changes=body.changes,
            reviewer=body.reviewer,
            reason=body.reason,
        )
        if not transaction:
            raise HTTPException(404, "Transaction not found")
        session.commit()
        return JSONResponse({"status": "ok", "transaction_id": transaction.id, "review_status": transaction.review_status})


@router.post("/transactions/{transaction_id}/annotate")
async def api_annotate_transaction(transaction_id: str, request: Request):
    """Add or update an analyst note on a transaction."""
    payload = await request.json()
    note = str(payload.get("note", ""))
    reviewer = str(payload.get("reviewer", "analyst"))

    with get_db_session() as session:
        txn = session.get(Transaction, transaction_id)
        if not txn:
            raise HTTPException(404, "Transaction not found")
        old_note = txn.analyst_note or ""
        txn.analyst_note = note
        session.add(txn)
        log_audit(
            session,
            object_type="transaction",
            object_id=transaction_id,
            action_type="annotate",
            field_name="analyst_note",
            old_value=old_note,
            new_value=note,
            changed_by=reviewer,
            reason="Analyst annotation",
        )
        session.commit()
        return JSONResponse({"status": "ok", "transaction_id": txn.id, "analyst_note": note})


@router.get("/accounts/{account_id}/review")
async def api_account_review_payload(account_id: str):
    with get_db_session() as session:
        payload = get_account_review_payload(session, account_id)
    if not payload:
        raise HTTPException(404, "Account not found")
    return JSONResponse(payload)


@router.post("/accounts/{account_id}/review")
async def api_review_account(account_id: str, body: AccountCorrectionRequest):
    with get_db_session() as session:
        account_row = update_account_fields(
            session,
            account_id=account_id,
            changes=body.changes,
            reviewer=body.reviewer,
            reason=body.reason,
        )
        if not account_row:
            raise HTTPException(404, "Account not found")
        session.commit()
        return JSONResponse({"status": "ok", "account_id": account_row.id})
