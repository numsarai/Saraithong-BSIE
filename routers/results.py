"""
routers/results.py
------------------
Result retrieval and file search endpoints.
"""

import json
import logging

import pandas as pd
from services.auth_service import require_auth
from fastapi import Depends, APIRouter, HTTPException
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

router = APIRouter(prefix="/api", tags=["results"], dependencies=[Depends(require_auth)])


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

    # Always merge meta.json (financial stats) into meta from DB (parsing info).
    # meta.json is the authoritative source for total_in/out, category_counts, etc.
    meta_path = OUTPUT_DIR / safe / "meta.json"
    if meta_path.exists():
        file_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        # Preserve parser-run-specific fields when reviewing a historical run.
        # The account-level meta.json still fills in export stats such as total_in/out.
        meta = {**file_meta, **meta} if parser_run_id else {**meta, **file_meta}
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
                    "date": row.posted_date.isoformat() if row.posted_date else (
                        row.transaction_datetime.isoformat()[:10] if row.transaction_datetime else ""
                    ),
                    "transaction_datetime": row.transaction_datetime.isoformat() if row.transaction_datetime else "",
                    "posted_date": row.posted_date.isoformat() if row.posted_date else "",
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
            "date",
            "time",
            "transaction_datetime",
            "posted_date",
            "amount",
            "direction",
            "transaction_type",
            "counterparty_account",
            "counterparty_name",
        }).fillna("")
        items = []
        for row in df.to_dict(orient="records"):
            date_value = str(row.get("date", "") or "").strip()[:10]
            time_value = str(row.get("time", "") or "").strip()
            transaction_datetime = str(row.get("transaction_datetime", "") or "").strip()
            if not transaction_datetime:
                transaction_datetime = f"{date_value}T{time_value}" if date_value and time_value else date_value
            posted_date = str(row.get("posted_date", "") or "").strip()[:10] or date_value
            items.append({
                "date": date_value,
                "transaction_datetime": transaction_datetime,
                "posted_date": posted_date,
                "amount": row.get("amount", ""),
                "direction": row.get("direction", ""),
                "transaction_type": row.get("transaction_type", ""),
                "counterparty_account": row.get("counterparty_account", ""),
                "counterparty_name": row.get("counterparty_name", ""),
            })
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
