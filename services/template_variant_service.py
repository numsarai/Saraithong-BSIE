from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.base import utcnow
from persistence.models import BankTemplateVariant

TRUST_STATES = {"candidate", "verified", "trusted"}
TRUST_ORDER = {"candidate": 0, "verified": 1, "trusted": 2}


def normalize_source_type(value: str | None) -> str:
    text = str(value or "excel").strip().lower()
    return text or "excel"


def clean_columns(columns: list[Any] | None) -> list[str]:
    result: list[str] = []
    for column in columns or []:
        text = str(column or "").strip()
        if text:
            result.append(text)
    return result


def clean_mapping(mapping: dict[str, Any] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    if not isinstance(mapping, dict):
        return result
    for field, column in mapping.items():
        field_text = str(field or "").strip()
        column_text = str(column or "").strip()
        if field_text and column_text:
            result[field_text] = column_text
    return result


def ordered_signature(columns: list[Any] | None) -> str:
    normalized = [str(column or "").strip().lower() for column in columns or [] if str(column or "").strip()]
    return _hash("|".join(normalized))


def set_signature(columns: list[Any] | None) -> str:
    normalized = sorted({str(column or "").strip().lower() for column in columns or [] if str(column or "").strip()})
    return _hash("|".join(normalized))


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _reviewers(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item or "").strip() for item in value if str(item or "").strip()]


def _next_trust_state(
    current_state: str,
    *,
    confirmation_count: int,
    correction_count: int,
    reviewer_count: int,
    valid_transaction_rows: int,
) -> str:
    current = current_state if current_state in TRUST_STATES else "candidate"
    if current == "trusted":
        return current
    if valid_transaction_rows <= 0:
        return current

    correction_rate = correction_count / confirmation_count if confirmation_count else 0.0
    if confirmation_count >= 3 and reviewer_count >= 2 and correction_rate <= 0.25:
        return "trusted"
    if confirmation_count >= 2 and correction_rate <= 0.5:
        return "verified"
    return current


def upsert_template_variant(
    session: Session,
    *,
    bank_key: str,
    columns: list[Any],
    mapping: dict[str, Any],
    source_type: str = "excel",
    sheet_name: str = "",
    header_row: int = 0,
    layout_type: str = "",
    reviewer: str = "analyst",
    feedback_status: str = "accepted",
    dry_run_summary: dict[str, Any] | None = None,
) -> dict:
    clean_bank = str(bank_key or "UNKNOWN").strip().lower() or "unknown"
    clean_source = normalize_source_type(source_type)
    clean_sheet = str(sheet_name or "").strip()
    clean_header = int(header_row or 0)
    clean_cols = clean_columns(columns)
    clean_map = clean_mapping(mapping)
    ordered_sig = ordered_signature(clean_cols)
    set_sig = set_signature(clean_cols)
    now = utcnow()

    existing = session.scalars(
        select(BankTemplateVariant).where(
            BankTemplateVariant.bank_key == clean_bank,
            BankTemplateVariant.source_type == clean_source,
            BankTemplateVariant.ordered_signature == ordered_sig,
            BankTemplateVariant.sheet_name == clean_sheet,
            BankTemplateVariant.header_row == clean_header,
        )
    ).first()

    created = existing is None
    row = existing or BankTemplateVariant(
        bank_key=clean_bank,
        source_type=clean_source,
        sheet_name=clean_sheet,
        header_row=clean_header,
        ordered_signature=ordered_sig,
        set_signature=set_sig,
        layout_type=str(layout_type or ""),
        column_order_json=clean_cols,
        confirmed_mapping_json=clean_map,
        trust_state="candidate",
        usage_count=0,
        confirmation_count=0,
        correction_count=0,
        confirmed_by_json=[],
        created_at=now,
    )

    reviewers = _reviewers(row.confirmed_by_json)
    clean_reviewer = str(reviewer or "analyst").strip() or "analyst"
    if clean_reviewer not in reviewers:
        reviewers.append(clean_reviewer)

    row.confirmed_mapping_json = clean_map
    row.column_order_json = clean_cols
    row.set_signature = set_sig
    row.layout_type = str(layout_type or row.layout_type or "")
    row.usage_count = int(row.usage_count or 0) + 1
    row.confirmation_count = int(row.confirmation_count or 0) + 1
    if feedback_status == "corrected":
        row.correction_count = int(row.correction_count or 0) + 1
    row.confirmed_by_json = reviewers
    row.dry_run_summary_json = dry_run_summary or {}
    row.updated_at = now
    row.last_confirmed_at = now
    row.trust_state = _next_trust_state(
        row.trust_state,
        confirmation_count=int(row.confirmation_count or 0),
        correction_count=int(row.correction_count or 0),
        reviewer_count=len(reviewers),
        valid_transaction_rows=int((dry_run_summary or {}).get("valid_transaction_rows") or 0),
    )

    session.add(row)
    session.flush()
    return {
        **variant_to_dict(row),
        "created": created,
        "action": "created" if created else "updated",
    }


def list_template_variants(
    session: Session,
    *,
    bank_key: str = "",
    trust_state: str = "",
    limit: int = 100,
) -> list[dict]:
    statement = select(BankTemplateVariant)
    clean_bank = str(bank_key or "").strip().lower()
    clean_trust = str(trust_state or "").strip().lower()
    if clean_bank:
        statement = statement.where(BankTemplateVariant.bank_key == clean_bank)
    if clean_trust:
        statement = statement.where(BankTemplateVariant.trust_state == clean_trust)
    statement = statement.order_by(BankTemplateVariant.updated_at.desc()).limit(max(1, min(int(limit or 100), 500)))
    return [variant_to_dict(row) for row in session.scalars(statement).all()]


def promote_template_variant(
    session: Session,
    *,
    variant_id: str,
    target_state: str,
    reviewer: str,
    note: str = "",
) -> dict:
    clean_state = str(target_state or "").strip().lower()
    if clean_state not in TRUST_STATES:
        raise ValueError(f"Invalid trust state: {target_state}")
    clean_reviewer = str(reviewer or "").strip()
    if not clean_reviewer or clean_reviewer.lower() in {"analyst", "unknown"}:
        raise PermissionError("Template variant promotion requires a named reviewer")

    row = session.get(BankTemplateVariant, variant_id)
    if not row:
        raise LookupError("Template variant not found")
    current_rank = TRUST_ORDER.get(row.trust_state, 0)
    target_rank = TRUST_ORDER[clean_state]
    if target_rank < current_rank:
        raise ValueError("Template variant trust state cannot be demoted by this endpoint")

    row.trust_state = clean_state
    row.promoted_at = utcnow()
    row.promoted_by = clean_reviewer
    row.updated_at = row.promoted_at
    row.notes = note or row.notes
    session.add(row)
    session.flush()
    return variant_to_dict(row)


def variant_to_dict(row: BankTemplateVariant) -> dict:
    reviewers = _reviewers(row.confirmed_by_json)
    confirmation_count = int(row.confirmation_count or 0)
    correction_count = int(row.correction_count or 0)
    correction_rate = correction_count / confirmation_count if confirmation_count else 0.0
    return {
        "variant_id": row.id,
        "bank_key": row.bank_key,
        "source_type": row.source_type,
        "sheet_name": row.sheet_name,
        "header_row": row.header_row,
        "ordered_signature": row.ordered_signature,
        "set_signature": row.set_signature,
        "layout_type": row.layout_type,
        "columns": row.column_order_json or [],
        "confirmed_mapping": row.confirmed_mapping_json or {},
        "trust_state": row.trust_state,
        "usage_count": int(row.usage_count or 0),
        "confirmation_count": confirmation_count,
        "correction_count": correction_count,
        "correction_rate": round(correction_rate, 4),
        "reviewer_count": len(reviewers),
        "confirmed_by": reviewers,
        "dry_run_summary": row.dry_run_summary_json or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "last_confirmed_at": row.last_confirmed_at.isoformat() if row.last_confirmed_at else None,
        "promoted_at": row.promoted_at.isoformat() if row.promoted_at else None,
        "promoted_by": row.promoted_by or "",
        "notes": row.notes or "",
    }
