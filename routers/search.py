"""
routers/search.py
-----------------
Search-related API routes: accounts, transactions, and account details.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from persistence.base import get_db_session
from persistence.models import Transaction
from services.account_resolution_service import best_known_account_holder_name, normalize_account_number
from services.search_service import (
    get_account_detail,
    list_accounts,
    search_transactions,
    serialize_transaction,
)

logger = logging.getLogger("bsie.api")

router = APIRouter(prefix="/api", tags=["search"])


# CRITICAL: /accounts/remembered-name MUST be registered BEFORE
# /accounts/{account_id} to avoid the path parameter capturing "remembered-name".

@router.get("/accounts")
async def api_accounts(q: str = "", limit: int = 100, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_accounts(session, q=q, limit=limit, offset=offset)})


@router.get("/accounts/remembered-name")
async def api_account_remembered_name(bank_key: str = "", account: str = ""):
    resolved_bank = str(bank_key or "").strip()
    raw_account = str(account or "").strip()
    normalized_account = normalize_account_number(raw_account) or ""
    remembered_name = ""

    if normalized_account:
        with get_db_session() as session:
            remembered_name = best_known_account_holder_name(
                session,
                bank_name=resolved_bank,
                raw_account_number=raw_account,
            ) or ""

    return JSONResponse({
        "bank_key": resolved_bank,
        "account": raw_account,
        "normalized_account_number": normalized_account,
        "remembered_name": remembered_name,
        "matched": bool(remembered_name),
    })


@router.get("/accounts/{account_id}")
async def api_account_detail(account_id: str):
    with get_db_session() as session:
        payload = get_account_detail(session, account_id)
    if not payload:
        raise HTTPException(404, "Account not found")
    return JSONResponse(payload)


@router.get("/transactions/search")
async def api_search_transactions(
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    limit: int = 100,
    offset: int = 0,
):
    with get_db_session() as session:
        rows = search_transactions(
            session,
            q=q,
            account=account,
            counterparty=counterparty,
            amount_min=amount_min,
            amount_max=amount_max,
            date_from=date_from,
            date_to=date_to,
            bank=bank,
            reference_no=reference_no,
            transaction_type=transaction_type,
            duplicate_status=duplicate_status,
            review_status=review_status,
            match_status=match_status,
            file_id=file_id,
            parser_run_id=parser_run_id,
            limit=limit,
            offset=offset,
        )
    return JSONResponse({"items": rows})


@router.get("/transactions/timeline-aggregate")
async def api_timeline_aggregate(
    account: str = "",
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    file_id: str = "",
    parser_run_id: str = "",
):
    """Return daily aggregated timeline data for charting — no heavy transaction details."""
    from datetime import date, datetime, time
    from sqlalchemy import func, case, select as sa_select
    from persistence.models import Account

    with get_db_session() as session:
        q = sa_select(
            func.date(Transaction.transaction_datetime).label("day"),
            func.sum(case((Transaction.direction == "IN", func.abs(Transaction.amount)), else_=0)).label("in_total"),
            func.sum(case((Transaction.direction == "OUT", func.abs(Transaction.amount)), else_=0)).label("out_total"),
            func.sum(case((Transaction.direction == "IN", 1), else_=0)).label("in_count"),
            func.sum(case((Transaction.direction == "OUT", 1), else_=0)).label("out_count"),
        ).where(Transaction.transaction_datetime.isnot(None))

        if account:
            norm = normalize_account_number(account)
            acct_row = session.scalars(
                sa_select(Account).where(Account.normalized_account_number == norm)
            ).first()
            if acct_row:
                q = q.where(Transaction.account_id == acct_row.id)
        if date_from:
            try:
                q = q.where(Transaction.transaction_datetime >= datetime.combine(date.fromisoformat(date_from), time.min))
            except ValueError:
                pass
        if date_to:
            try:
                q = q.where(Transaction.transaction_datetime <= datetime.combine(date.fromisoformat(date_to), time.max))
            except ValueError:
                pass
        if file_id:
            q = q.where(Transaction.file_id == file_id)
        if parser_run_id:
            q = q.where(Transaction.parser_run_id == parser_run_id)

        q = q.group_by(func.date(Transaction.transaction_datetime)).order_by(func.date(Transaction.transaction_datetime).asc())
        result = session.execute(q).all()

        items = [
            {
                "date": str(row.day),
                "in_total": float(row.in_total or 0),
                "out_total": float(row.out_total or 0),
                "in_count": int(row.in_count or 0),
                "out_count": int(row.out_count or 0),
            }
            for row in result
        ]

    return JSONResponse({"items": items, "total": len(items)})


@router.get("/transactions/{transaction_id}")
async def api_transaction_detail(transaction_id: str):
    with get_db_session() as session:
        row = session.get(Transaction, transaction_id)
        if not row:
            raise HTTPException(404, "Transaction not found")
        return JSONResponse(serialize_transaction(row))
