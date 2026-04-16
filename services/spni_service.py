"""
spni_service.py
---------------
Service layer for SPNI integration endpoints.

Provides query and serialization functions for exporting BSIE data
(accounts, transactions, entities) in a format ready for SPNI's
BSIEAdapter to consume.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, distinct
from sqlalchemy.orm import Session

from persistence.base import utcnow
from persistence.models import (
    Account,
    AccountEntityLink,
    Entity,
    FileRecord,
    ParserRun,
    StatementBatch,
    Transaction,
)

logger = logging.getLogger(__name__)

APP_VERSION = "4.0.0"


# ── Serialization helpers ───────────────────────────────────────────────


def _iso(val: datetime | date | None) -> str | None:
    return val.isoformat() if val else None


def _serialize_account(acct: Account) -> dict[str, Any]:
    return {
        "id": acct.id,
        "normalized_account_number": acct.normalized_account_number or "",
        "bank_code": acct.bank_code or "",
        "bank_name": acct.bank_name or "",
        "account_holder_name": acct.account_holder_name or "",
        "account_type": acct.account_type or "",
        "confidence_score": float(acct.confidence_score or 0),
        "first_seen_at": _iso(acct.first_seen_at),
        "last_seen_at": _iso(acct.last_seen_at),
    }


def _serialize_transaction(
    tx: Transaction,
    subject_account_number: str,
) -> dict[str, Any]:
    """Serialize a transaction with from/to account derivation.

    Direction logic (same as export_service):
    - IN:  from=counterparty, to=subject
    - OUT: from=subject, to=counterparty
    """
    counterparty = tx.counterparty_account_normalized or ""
    if tx.direction == "IN":
        from_acct = counterparty
        to_acct = subject_account_number
    else:
        from_acct = subject_account_number
        to_acct = counterparty

    return {
        "id": tx.id,
        "account_id": tx.account_id or "",
        "from_account": from_acct,
        "to_account": to_acct,
        "amount": float(tx.amount or 0),
        "direction": tx.direction,
        "transaction_datetime": _iso(tx.transaction_datetime),
        "posted_date": _iso(tx.posted_date),
        "description": tx.description_raw or tx.description_normalized or "",
        "reference_no": tx.reference_no or "",
        "transaction_type": tx.transaction_type or "",
        "counterparty_name": tx.counterparty_name_raw or tx.counterparty_name_normalized or "",
        "parse_confidence": float(tx.parse_confidence or 0),
    }


def _serialize_entity(ent: Entity) -> dict[str, Any]:
    return {
        "id": ent.id,
        "entity_type": ent.entity_type,
        "full_name": ent.full_name or "",
        "normalized_name": ent.normalized_name or "",
        "aliases": ent.alias_json or [],
        "identifier_value": ent.identifier_value or "",
    }


# ── Service functions ───────────────────────────────────────────────────


def list_completed_runs(
    session: Session,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """List completed parser runs with metadata for SPNI's run selector."""

    # Total count (completed runs only)
    total = session.scalar(
        select(func.count(ParserRun.id)).where(ParserRun.status == "done")
    ) or 0

    # Runs with file info (completed only)
    stmt = (
        select(ParserRun, FileRecord.original_filename)
        .join(FileRecord, ParserRun.file_id == FileRecord.id)
        .where(ParserRun.status == "done")
        .order_by(ParserRun.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = session.execute(stmt).all()

    # ── Batch counts to avoid N+1 ──────────────────────────────────────
    run_ids = [run.id for run, _ in rows]

    txn_counts: dict[str, int] = {}
    acct_counts: dict[str, int] = {}
    if run_ids:
        txn_counts = dict(
            session.execute(
                select(Transaction.parser_run_id, func.count(Transaction.id))
                .where(Transaction.parser_run_id.in_(run_ids))
                .group_by(Transaction.parser_run_id)
            ).all()
        )
        acct_counts = dict(
            session.execute(
                select(
                    StatementBatch.parser_run_id,
                    func.count(distinct(StatementBatch.account_id)),
                )
                .where(
                    StatementBatch.parser_run_id.in_(run_ids),
                    StatementBatch.account_id.isnot(None),
                )
                .group_by(StatementBatch.parser_run_id)
            ).all()
        )

    items: list[dict[str, Any]] = []
    for run, file_name in rows:
        items.append({
            "id": run.id,
            "file_name": file_name or "",
            "bank": run.bank_detected or "",
            "status": run.status,
            "account_count": acct_counts.get(run.id, 0),
            "transaction_count": txn_counts.get(run.id, 0),
            "started_at": _iso(run.started_at),
            "processed_at": _iso(run.finished_at),
        })

    return {"items": items, "total": total}


def get_run_preview(
    session: Session,
    run_id: str,
) -> dict[str, Any] | None:
    """Preview data available in a parser run before import."""

    # Fetch run with file info in one query (avoid lazy load)
    row = session.execute(
        select(ParserRun, FileRecord.original_filename)
        .join(FileRecord, ParserRun.file_id == FileRecord.id)
        .where(ParserRun.id == run_id)
    ).first()
    if not row:
        return None

    run, file_name = row

    # Transaction count
    txn_count = session.scalar(
        select(func.count(Transaction.id)).where(
            Transaction.parser_run_id == run_id
        )
    ) or 0

    # Accounts in this run (via StatementBatch)
    acct_ids = session.scalars(
        select(distinct(StatementBatch.account_id)).where(
            StatementBatch.parser_run_id == run_id,
            StatementBatch.account_id.isnot(None),
        )
    ).all()

    # ── Batch account info + per-account txn counts (avoid N+1) ────────
    acct_map: dict[str, Account] = {}
    per_acct_txn_counts: dict[str, int] = {}
    if acct_ids:
        acct_rows = session.scalars(
            select(Account).where(Account.id.in_(acct_ids))
        ).all()
        acct_map = {a.id: a for a in acct_rows}

        per_acct_txn_counts = dict(
            session.execute(
                select(Transaction.account_id, func.count(Transaction.id))
                .where(
                    Transaction.parser_run_id == run_id,
                    Transaction.account_id.in_(acct_ids),
                )
                .group_by(Transaction.account_id)
            ).all()
        )

    accounts_summary: list[dict[str, Any]] = []
    for acct_id in acct_ids:
        acct = acct_map.get(acct_id)
        if not acct:
            continue
        accounts_summary.append({
            "id": acct.id,
            "name": acct.account_holder_name or "",
            "number": acct.normalized_account_number or "",
            "bank": acct.bank_name or "",
            "transaction_count": per_acct_txn_counts.get(acct_id, 0),
        })

    # Entity count linked to these accounts
    entity_count = 0
    if acct_ids:
        entity_count = session.scalar(
            select(func.count(distinct(AccountEntityLink.entity_id))).where(
                AccountEntityLink.account_id.in_(acct_ids)
            )
        ) or 0

    # Date range (single query)
    date_row = session.execute(
        select(
            func.min(Transaction.transaction_datetime),
            func.max(Transaction.transaction_datetime),
        ).where(Transaction.parser_run_id == run_id)
    ).one()
    range_from, range_to = date_row

    return {
        "run_id": run_id,
        "file_name": file_name or "",
        "bank": run.bank_detected or "",
        "status": run.status,
        "account_count": len(acct_ids),
        "transaction_count": txn_count,
        "entity_count": entity_count,
        "date_range": {
            "from": _iso(range_from),
            "to": _iso(range_to),
        },
        "accounts": accounts_summary,
    }


def export_data(
    session: Session,
    *,
    run_id: str,
    account_filter: list[str] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    limit: int = 5000,
    offset: int = 0,
) -> dict[str, Any]:
    """Export accounts, transactions, and entities for SPNI consumption.

    ``run_id`` is required — scopes all queries to a single parser run.
    """

    # ── Build filtered transaction query ────────────────────────────────
    base = select(Transaction).where(Transaction.parser_run_id == run_id)

    if account_filter:
        # Resolve account numbers to IDs
        acct_id_rows = session.scalars(
            select(Account.id).where(
                Account.normalized_account_number.in_(account_filter)
            )
        ).all()
        if acct_id_rows:
            base = base.where(Transaction.account_id.in_(acct_id_rows))
        else:
            return _empty_export(run_id)

    if date_from is not None:
        base = base.where(Transaction.transaction_datetime >= date_from)
    if date_to is not None:
        base = base.where(Transaction.transaction_datetime <= date_to)
    if amount_min is not None:
        base = base.where(Transaction.amount >= Decimal(str(amount_min)))
    if amount_max is not None:
        base = base.where(Transaction.amount <= Decimal(str(amount_max)))

    filtered_transactions = base.subquery()

    # ── Total count (before pagination) ─────────────────────────────────
    count_stmt = select(func.count()).select_from(filtered_transactions)
    total_transactions = session.scalar(count_stmt) or 0

    # ── Collect all account IDs for the filtered export set ─────────────
    acct_ids = session.scalars(
        select(distinct(filtered_transactions.c.account_id)).where(
            filtered_transactions.c.account_id.isnot(None)
        )
    ).all()
    acct_id_set: set[str] = set(acct_ids)

    # ── Fetch accounts for the full filtered export set ─────────────────
    acct_map: dict[str, Account] = {}
    if acct_id_set:
        acct_rows = session.scalars(
            select(Account).where(Account.id.in_(acct_id_set))
        ).all()
        acct_map = {a.id: a for a in acct_rows}

    acct_number_map: dict[str, str] = {
        a.id: (a.normalized_account_number or "")
        for a in acct_map.values()
    }

    # ── Fetch entities linked to the full filtered export set ───────────
    entities: list[dict[str, Any]] = []
    if acct_id_set:
        entity_stmt = (
            select(Entity)
            .join(AccountEntityLink, AccountEntityLink.entity_id == Entity.id)
            .where(AccountEntityLink.account_id.in_(acct_id_set))
            .distinct()
        )
        entity_rows = session.scalars(entity_stmt).all()
        entities = [_serialize_entity(e) for e in entity_rows]

    # ── Fetch paginated transactions ────────────────────────────────────
    txn_stmt = base.order_by(Transaction.transaction_datetime).limit(limit).offset(offset)
    txn_rows = session.scalars(txn_stmt).all()

    # ── Serialize ───────────────────────────────────────────────────────
    serialized_accounts = [_serialize_account(a) for a in acct_map.values()]
    serialized_txns = [
        _serialize_transaction(
            tx,
            acct_number_map.get(tx.account_id or "", ""),
        )
        for tx in txn_rows
    ]

    return {
        "meta": {
            "exported_at": utcnow().isoformat(),
            "source": "bsie",
            "version": APP_VERSION,
            "run_id": run_id,
            "total_accounts": len(serialized_accounts),
            "total_transactions": total_transactions,
            "total_entities": len(entities),
            "limit": limit,
            "offset": offset,
        },
        "accounts": serialized_accounts,
        "transactions": serialized_txns,
        "entities": entities,
    }


def _empty_export(run_id: str) -> dict[str, Any]:
    """Return an empty export response."""
    return {
        "meta": {
            "exported_at": utcnow().isoformat(),
            "source": "bsie",
            "version": APP_VERSION,
            "run_id": run_id,
            "total_accounts": 0,
            "total_transactions": 0,
            "total_entities": 0,
            "limit": 0,
            "offset": 0,
        },
        "accounts": [],
        "transactions": [],
        "entities": [],
    }
