from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.base import utcnow
from persistence.models import DuplicateGroup, StatementBatch, Transaction


def detect_batch_overlap(session: Session, *, account_id: str | None, fingerprint: str, start_date, end_date) -> str:
    if not account_id:
        return "unknown_account"

    exact = session.scalars(
        select(StatementBatch).where(
            StatementBatch.account_id == account_id,
            StatementBatch.batch_fingerprint == fingerprint,
        )
    ).first()
    if exact:
        return "exact_same_batch"

    if not start_date or not end_date:
        return "new"

    overlaps = session.scalars(
        select(StatementBatch).where(
            StatementBatch.account_id == account_id,
            StatementBatch.statement_start_date <= end_date,
            StatementBatch.statement_end_date >= start_date,
        )
    ).all()
    if overlaps:
        return "overlapping_range"
    return "new"


def _ensure_group(session: Session, duplicate_type: str, confidence: float, reason: str, existing_group_id: str | None = None) -> str:
    if existing_group_id:
        return existing_group_id
    row = DuplicateGroup(
        duplicate_type=duplicate_type,
        confidence_score=Decimal(str(confidence)).quantize(Decimal("0.0001")),
        reason=reason,
        created_at=utcnow(),
        resolution_status="pending",
    )
    session.add(row)
    session.flush()
    return row.id


def classify_transaction_duplicate(session: Session, payload: dict[str, Any]) -> tuple[str, str | None, float, str]:
    """Classify a new transaction against stored history for the same account."""
    account_id = payload.get("account_id")
    parser_run_id = payload.get("parser_run_id")
    tx_dt = payload.get("transaction_datetime")
    amount = payload.get("amount")
    fingerprint = payload.get("transaction_fingerprint")
    direction = payload.get("direction")
    reference = str(payload.get("reference_no") or "").strip()
    description = str(payload.get("description_normalized") or "").strip()
    balance = payload.get("balance_after")

    if not account_id or amount is None:
        return "unique", None, 0.0, "insufficient_fields"

    exact = session.scalars(
        select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.transaction_fingerprint == fingerprint,
            Transaction.parser_run_id != parser_run_id,
        )
    ).first()
    if exact:
        group_id = _ensure_group(session, "exact_duplicate", 1.0, "matching transaction fingerprint", exact.duplicate_group_id)
        return "exact_duplicate", group_id, 1.0, f"same fingerprint as transaction {exact.id}"

    if tx_dt is None:
        return "unique", None, 0.0, "no transaction datetime"

    candidates = session.scalars(
        select(Transaction).where(
            Transaction.account_id == account_id,
            Transaction.amount == amount,
            Transaction.parser_run_id != parser_run_id,
            Transaction.transaction_datetime >= tx_dt - timedelta(days=1),
            Transaction.transaction_datetime <= tx_dt + timedelta(days=1),
        )
    ).all()

    best_status = "unique"
    best_conf = 0.0
    best_reason = "no similar transaction"
    best_group = None
    for candidate in candidates:
        same_direction = candidate.direction == direction
        same_reference = str(candidate.reference_no or "").strip() == reference and bool(reference)
        same_description = str(candidate.description_normalized or "").strip() == description and bool(description)
        same_balance = balance is not None and candidate.balance_after == balance
        minute_gap = abs((candidate.transaction_datetime - tx_dt).total_seconds()) / 60.0

        features = sum(
            [
                1 if same_direction else 0,
                1 if same_reference else 0,
                1 if same_description else 0,
                1 if same_balance else 0,
                1 if minute_gap <= 5 else 0,
                1 if candidate.counterparty_account_normalized == payload.get("counterparty_account_normalized") else 0,
                1 if candidate.transaction_type == payload.get("transaction_type") else 0,
            ]
        )

        if same_direction and features >= 5 and minute_gap <= 5:
            best_status = "probable_duplicate"
            best_conf = 0.85
            best_reason = f"same amount/direction within 5 minutes of {candidate.id}"
            best_group = _ensure_group(session, best_status, best_conf, best_reason, candidate.duplicate_group_id)
            break

        if same_direction and (same_reference or same_description):
            best_status = "overlap_duplicate"
            best_conf = max(best_conf, 0.75)
            best_reason = f"overlapping transaction signature with {candidate.id}"
            best_group = _ensure_group(session, best_status, best_conf, best_reason, candidate.duplicate_group_id)
            continue

        if same_direction and minute_gap <= 1440:
            best_status = "similar_conflict"
            best_conf = max(best_conf, 0.60)
            best_reason = f"same amount/date family but conflicting details vs {candidate.id}"
            best_group = _ensure_group(session, best_status, best_conf, best_reason, candidate.duplicate_group_id)

    return best_status, best_group, best_conf, best_reason
