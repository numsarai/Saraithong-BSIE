"""
routers/results.py
------------------
Result retrieval and file search endpoints.
"""

import json
import logging

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select

from paths import OUTPUT_DIR
from persistence.base import get_db_session
from persistence.models import Account, ParserRun, StatementBatch, Transaction
from services.search_service import (
    get_file_detail,
    list_files,
    serialize_transaction,
)

logger = logging.getLogger("bsie.api")

router = APIRouter(prefix="/api", tags=["results"])


@router.get("/results/{account}")
async def api_results(account: str, page: int = 1, page_size: int = 100, parser_run_id: str = ""):
    """Return paginated transaction results for an account."""
    safe = "".join(c for c in account if c.isdigit())
    processed_dir = OUTPUT_DIR / safe / "processed"
    meta = {}
    rows = []
    total = 0

    with get_db_session() as session:
        account_row = session.scalars(
            select(Account).where(Account.normalized_account_number == safe).order_by(Account.last_seen_at.desc())
        ).first()
        if account_row:
            tx_query = select(Transaction).where(Transaction.account_id == account_row.id)
            if parser_run_id:
                tx_query = tx_query.where(Transaction.parser_run_id == parser_run_id)
            all_rows = session.scalars(
                tx_query.order_by(Transaction.transaction_datetime.desc())
            ).all()
            total = len(all_rows)
            start = (page - 1) * page_size
            end = start + page_size
            rows = [serialize_transaction(row) for row in all_rows[start:end]]
            latest_run = session.get(ParserRun, parser_run_id) if parser_run_id else session.scalars(
                select(ParserRun).join(StatementBatch, StatementBatch.parser_run_id == ParserRun.id).where(
                    StatementBatch.account_id == account_row.id
                ).order_by(ParserRun.started_at.desc())
            ).first()
            if latest_run:
                meta = latest_run.summary_json or {}

    txn_path = processed_dir / "transactions.csv"
    if not rows and txn_path.exists():
        df = pd.read_csv(txn_path, dtype=str, encoding="utf-8-sig")
        df = df.fillna("")
        total = len(df)
        start = (page - 1) * page_size
        end = start + page_size
        rows = df.iloc[start:end].to_dict(orient="records")

    meta_path = OUTPUT_DIR / safe / "meta.json"
    if not meta and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not rows and not txn_path.exists():
        raise HTTPException(404, f"No results for account {safe}")

    entities = []
    entities_path = processed_dir / "entities.csv"
    if entities_path.exists():
        entities_df = pd.read_csv(entities_path, dtype=str, encoding="utf-8-sig").fillna("")
        entities = entities_df.to_dict(orient="records")

    links = []
    links_path = processed_dir / "links.csv"
    if links_path.exists():
        links_df = pd.read_csv(links_path, dtype=str, encoding="utf-8-sig").fillna("")
        links = links_df.to_dict(orient="records")

    return JSONResponse({
        "account":    safe,
        "meta":       meta,
        "total":      total,
        "page":       page,
        "page_size":  page_size,
        "items":      rows,
        "rows":       rows,
        "entities":   entities,
        "links":      links,
    })


@router.get("/results/{account}/timeline")
async def api_results_timeline(account: str, parser_run_id: str = ""):
    """Return lightweight date+amount+direction data for ALL transactions — for timeline charts."""
    safe = "".join(c for c in account if c.isdigit())

    with get_db_session() as session:
        account_row = session.scalars(
            select(Account).where(Account.normalized_account_number == safe).order_by(Account.last_seen_at.desc())
        ).first()
        if account_row:
            tx_query = select(
                Transaction.transaction_datetime,
                Transaction.posted_date,
                Transaction.amount,
                Transaction.direction,
                Transaction.transaction_type,
                Transaction.counterparty_account_normalized,
                Transaction.counterparty_name_normalized,
            ).where(Transaction.account_id == account_row.id)
            if parser_run_id:
                tx_query = tx_query.where(Transaction.parser_run_id == parser_run_id)
            tx_query = tx_query.order_by(Transaction.transaction_datetime.asc())
            result = session.execute(tx_query).all()
            items = [
                {
                    "date": str(row.posted_date or "")[:10] if row.posted_date else str(row.transaction_datetime or "")[:10],
                    "amount": float(row.amount or 0),
                    "direction": str(row.direction or ""),
                    "transaction_type": str(row.transaction_type or ""),
                    "counterparty_account": str(row.counterparty_account_normalized or ""),
                    "counterparty_name": str(row.counterparty_name_normalized or ""),
                }
                for row in result
            ]
            return JSONResponse({"account": safe, "items": items, "total": len(items)})

    # Fallback to CSV
    txn_path = OUTPUT_DIR / safe / "processed" / "transactions.csv"
    if txn_path.exists():
        df = pd.read_csv(txn_path, dtype=str, encoding="utf-8-sig", usecols=lambda c: c in {
            "date", "amount", "direction", "transaction_type", "counterparty_account", "counterparty_name",
        }).fillna("")
        items = df.to_dict(orient="records")
        return JSONResponse({"account": safe, "items": items, "total": len(items)})

    return JSONResponse({"account": safe, "items": [], "total": 0})


@router.get("/files")
async def api_files(limit: int = 100, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_files(session, limit=limit, offset=offset)})


@router.get("/files/{file_id}")
async def api_file_detail(file_id: str):
    with get_db_session() as session:
        payload = get_file_detail(session, file_id)
    if not payload:
        raise HTTPException(404, "File not found")
    return JSONResponse(payload)
