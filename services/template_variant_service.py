from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.base import utcnow
from persistence.models import BankTemplateVariant

TRUST_STATES = {"candidate", "verified", "trusted"}
TRUST_ORDER = {"candidate": 0, "verified": 1, "trusted": 2}
AUTO_PASS_MODE = "observe_only"
AUTO_PASS_MIN_CONFIRMATIONS = 3
AUTO_PASS_MIN_REVIEWERS = 2
AUTO_PASS_MAX_CORRECTION_RATE = 0.10
AUTO_PASS_MIN_VALID_ROWS = 1
AUTO_PASS_MIN_BANK_CONFIDENCE = 0.90
AUTO_PASS_MIN_MATCH_SCORE = 0.99
AUTO_PASS_ALLOWED_MATCH_TYPES = {"ordered_signature"}


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


def _int_metric(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_metric(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _valid_transaction_rows(variant: dict[str, Any]) -> int:
    dry_run = variant.get("dry_run_summary") or {}
    if not isinstance(dry_run, dict):
        return 0
    return _int_metric(dry_run.get("valid_transaction_rows"))


def build_auto_pass_gate(
    variant: dict[str, Any],
    *,
    source_type: str | None = None,
    bank_confidence: float | None = None,
    bank_ambiguous: bool | None = None,
    mapping_valid: bool | None = None,
    match_type: str | None = None,
    match_score: float | None = None,
) -> dict[str, Any]:
    """Evaluate Phase 5 auto-pass readiness without enabling auto-pass."""
    clean_source = normalize_source_type(source_type or variant.get("source_type") or "excel")
    trust_state = str(variant.get("trust_state") or "").strip().lower()
    confirmation_count = _int_metric(variant.get("confirmation_count"))
    correction_count = _int_metric(variant.get("correction_count"))
    reviewer_count = _int_metric(variant.get("reviewer_count"))
    valid_rows = _valid_transaction_rows(variant)
    correction_rate = correction_count / confirmation_count if confirmation_count else 0.0
    if "correction_rate" in variant:
        correction_rate = _float_metric(variant.get("correction_rate"))
    clean_match_type = str(match_type or variant.get("match_type") or "").strip()
    clean_match_score = _float_metric(match_score if match_score is not None else variant.get("match_score"))

    blocked_reasons: list[str] = []
    if clean_source != "excel":
        blocked_reasons.append("source_not_excel")
    if trust_state != "trusted":
        blocked_reasons.append("not_trusted")
    if confirmation_count < AUTO_PASS_MIN_CONFIRMATIONS:
        blocked_reasons.append("insufficient_confirmations")
    if reviewer_count < AUTO_PASS_MIN_REVIEWERS:
        blocked_reasons.append("insufficient_reviewers")
    if correction_rate > AUTO_PASS_MAX_CORRECTION_RATE:
        blocked_reasons.append("correction_rate_high")
    if valid_rows < AUTO_PASS_MIN_VALID_ROWS:
        blocked_reasons.append("no_valid_preview_rows")
    if bank_confidence is not None and _float_metric(bank_confidence) < AUTO_PASS_MIN_BANK_CONFIDENCE:
        blocked_reasons.append("bank_confidence_low")
    if bank_ambiguous is True:
        blocked_reasons.append("bank_ambiguous")
    if mapping_valid is False:
        blocked_reasons.append("mapping_invalid")
    if clean_match_type and clean_match_type not in AUTO_PASS_ALLOWED_MATCH_TYPES:
        blocked_reasons.append("match_not_exact")
    if match_score is not None and clean_match_score < AUTO_PASS_MIN_MATCH_SCORE:
        blocked_reasons.append("match_score_low")

    rollback_reasons: list[str] = []
    if trust_state == "trusted":
        if confirmation_count < AUTO_PASS_MIN_CONFIRMATIONS:
            rollback_reasons.append("trusted_without_enough_confirmations")
        if reviewer_count < AUTO_PASS_MIN_REVIEWERS:
            rollback_reasons.append("trusted_without_enough_reviewers")
        if correction_rate > AUTO_PASS_MAX_CORRECTION_RATE:
            rollback_reasons.append("trusted_correction_rate_high")
        if valid_rows < AUTO_PASS_MIN_VALID_ROWS:
            rollback_reasons.append("trusted_without_valid_preview_rows")

    would_auto_pass = not blocked_reasons
    rollback_recommended = bool(rollback_reasons)
    status = "blocked"
    if rollback_recommended:
        status = "rollback_review"
    elif would_auto_pass:
        status = "ready_observe_only"

    return {
        "mode": AUTO_PASS_MODE,
        "status": status,
        "would_auto_pass": would_auto_pass,
        "auto_pass_eligible": False,
        "blocked_reasons": blocked_reasons,
        "rollback_recommended": rollback_recommended,
        "rollback_reasons": rollback_reasons,
        "thresholds": {
            "min_confirmations": AUTO_PASS_MIN_CONFIRMATIONS,
            "min_reviewers": AUTO_PASS_MIN_REVIEWERS,
            "max_correction_rate": AUTO_PASS_MAX_CORRECTION_RATE,
            "min_valid_transaction_rows": AUTO_PASS_MIN_VALID_ROWS,
            "min_bank_confidence": AUTO_PASS_MIN_BANK_CONFIDENCE,
            "min_match_score": AUTO_PASS_MIN_MATCH_SCORE,
            "allowed_match_types": sorted(AUTO_PASS_ALLOWED_MATCH_TYPES),
        },
        "metrics": {
            "source_type": clean_source,
            "trust_state": trust_state,
            "confirmation_count": confirmation_count,
            "reviewer_count": reviewer_count,
            "correction_count": correction_count,
            "correction_rate": round(correction_rate, 4),
            "valid_transaction_rows": valid_rows,
            "bank_confidence": round(_float_metric(bank_confidence), 4) if bank_confidence is not None else None,
            "bank_ambiguous": bank_ambiguous,
            "mapping_valid": mapping_valid,
            "match_type": clean_match_type,
            "match_score": round(clean_match_score, 4) if match_score is not None else None,
        },
    }


def summarize_auto_pass_gates(variants: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "mode": AUTO_PASS_MODE,
        "total": 0,
        "would_auto_pass": 0,
        "auto_pass_eligible": 0,
        "ready_observe_only": 0,
        "blocked": 0,
        "rollback_review": 0,
        "by_trust_state": {state: 0 for state in sorted(TRUST_STATES, key=lambda item: TRUST_ORDER[item])},
        "by_gate_status": {
            "ready_observe_only": 0,
            "blocked": 0,
            "rollback_review": 0,
        },
        "by_bank": {},
        "top_blocked_reasons": [],
        "top_rollback_reasons": [],
    }
    blocked_reason_counts: dict[str, int] = {}
    rollback_reason_counts: dict[str, int] = {}

    for variant in variants or []:
        gate = variant.get("auto_pass_gate") if isinstance(variant.get("auto_pass_gate"), dict) else build_auto_pass_gate(variant)
        status = str(gate.get("status") or "blocked")
        if status not in summary["by_gate_status"]:
            status = "blocked"
        bank_key = str(variant.get("bank_key") or "unknown").strip().lower() or "unknown"
        trust_state = str(variant.get("trust_state") or "unknown").strip().lower() or "unknown"

        summary["total"] += 1
        summary[status] += 1
        summary["by_gate_status"][status] += 1
        summary["by_trust_state"][trust_state] = int(summary["by_trust_state"].get(trust_state, 0)) + 1
        if bool(gate.get("would_auto_pass")):
            summary["would_auto_pass"] += 1
        if bool(gate.get("auto_pass_eligible")):
            summary["auto_pass_eligible"] += 1

        bank_summary = summary["by_bank"].setdefault(bank_key, {
            "total": 0,
            "ready_observe_only": 0,
            "blocked": 0,
            "rollback_review": 0,
            "would_auto_pass": 0,
            "auto_pass_eligible": 0,
            "by_trust_state": {},
        })
        bank_summary["total"] += 1
        bank_summary[status] += 1
        if bool(gate.get("would_auto_pass")):
            bank_summary["would_auto_pass"] += 1
        if bool(gate.get("auto_pass_eligible")):
            bank_summary["auto_pass_eligible"] += 1
        bank_summary["by_trust_state"][trust_state] = int(bank_summary["by_trust_state"].get(trust_state, 0)) + 1

        for reason in gate.get("blocked_reasons") or []:
            reason_text = str(reason or "").strip()
            if reason_text:
                blocked_reason_counts[reason_text] = blocked_reason_counts.get(reason_text, 0) + 1
        for reason in gate.get("rollback_reasons") or []:
            reason_text = str(reason or "").strip()
            if reason_text:
                rollback_reason_counts[reason_text] = rollback_reason_counts.get(reason_text, 0) + 1

    summary["top_blocked_reasons"] = _ranked_reason_counts(blocked_reason_counts)
    summary["top_rollback_reasons"] = _ranked_reason_counts(rollback_reason_counts)
    return summary


def _ranked_reason_counts(counts: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


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


def find_matching_template_variant(
    session: Session,
    *,
    columns: list[Any],
    bank_key: str,
    source_type: str = "excel",
    sheet_name: str = "",
    header_row: int | None = None,
    include_candidate: bool = True,
    allowed_trust_states: set[str] | list[str] | tuple[str, ...] | None = None,
    bank_confidence: float | None = None,
    bank_ambiguous: bool | None = None,
    mapping_valid: bool | None = None,
) -> dict | None:
    clean_bank = str(bank_key or "").strip().lower()
    if not clean_bank or clean_bank in {"unknown", "generic"}:
        return None

    clean_source = normalize_source_type(source_type)
    ordered_sig = ordered_signature(columns)
    set_sig = set_signature(columns)
    if allowed_trust_states is None:
        allowed_states = {"verified", "trusted"}
        if include_candidate:
            allowed_states.add("candidate")
    else:
        allowed_states = {str(state or "").strip().lower() for state in allowed_trust_states}
        allowed_states = {state for state in allowed_states if state in TRUST_STATES}
        if not allowed_states:
            return None

    rows = session.scalars(
        select(BankTemplateVariant).where(
            BankTemplateVariant.bank_key == clean_bank,
            BankTemplateVariant.source_type == clean_source,
            BankTemplateVariant.trust_state.in_(sorted(allowed_states)),
            BankTemplateVariant.set_signature == set_sig,
        )
    ).all()
    if not rows:
        return None

    clean_sheet = str(sheet_name or "").strip()
    clean_header = int(header_row or 0) if header_row is not None else None
    ranked: list[tuple[tuple, BankTemplateVariant, str, float]] = []
    for row in rows:
        ordered_match = row.ordered_signature == ordered_sig
        if not ordered_match and row.trust_state == "candidate":
            continue
        match_type = "ordered_signature" if ordered_match else "set_signature"
        match_score = 1.0 if ordered_match else 0.92
        same_sheet = bool(clean_sheet and row.sheet_name == clean_sheet)
        same_header = clean_header is not None and int(row.header_row or 0) == clean_header
        rank = (
            1 if ordered_match else 0,
            TRUST_ORDER.get(row.trust_state, 0),
            1 if same_sheet else 0,
            1 if same_header else 0,
            int(row.confirmation_count or 0),
            int(row.usage_count or 0),
            str(row.updated_at or ""),
            str(row.id or ""),
        )
        ranked.append((rank, row, match_type, match_score))

    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    _, row, match_type, match_score = ranked[0]
    variant = variant_to_dict(row)
    gate = build_auto_pass_gate(
        variant,
        source_type=clean_source,
        bank_confidence=bank_confidence,
        bank_ambiguous=bank_ambiguous,
        mapping_valid=mapping_valid,
        match_type=match_type,
        match_score=match_score,
    )
    return {
        **variant,
        "match_type": match_type,
        "match_score": match_score,
        "auto_pass_gate": gate,
        "auto_pass_eligible": gate["auto_pass_eligible"],
        "suggestion_only": True,
    }


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
    result = {
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
    result["auto_pass_gate"] = build_auto_pass_gate(result)
    result["auto_pass_eligible"] = False
    return result
