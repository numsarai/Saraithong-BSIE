from __future__ import annotations

from sqlalchemy.orm import Session

from persistence.base import utcnow
from persistence.models import Account, DuplicateGroup, Transaction, TransactionMatch
from services.account_resolution_service import find_merge_candidates, resolve_account
from services.audit_service import log_audit, record_learning_feedback, record_review_decision


ACCOUNT_IDENTITY_FIELDS = {
    "bank_name",
    "bank_code",
    "raw_account_number",
    "normalized_account_number",
    "display_account_number",
    "account_holder_name",
}

TRANSACTION_COUNTERPARTY_FIELDS = {
    "counterparty_account_normalized",
    "counterparty_name_normalized",
}


def review_duplicate_group(
    session: Session,
    *,
    group_id: str,
    decision_value: str,
    reviewer: str,
    reviewer_note: str = "",
) -> DuplicateGroup | None:
    group = session.get(DuplicateGroup, group_id)
    if not group:
        return None
    old_status = group.resolution_status
    group.resolution_status = decision_value
    group.resolved_at = utcnow()
    session.add(group)
    record_review_decision(
        session,
        object_type="duplicate_group",
        object_id=group_id,
        decision_type="resolution",
        decision_value=decision_value,
        reviewer=reviewer,
        reviewer_note=reviewer_note,
    )
    log_audit(
        session,
        object_type="duplicate_group",
        object_id=group_id,
        action_type="review_duplicate_group",
        field_name="resolution_status",
        old_value=old_status,
        new_value=decision_value,
        changed_by=reviewer,
        reason=reviewer_note,
    )
    return group


def review_match(
    session: Session,
    *,
    match_id: str,
    decision_value: str,
    reviewer: str,
    reviewer_note: str = "",
) -> TransactionMatch | None:
    match = session.get(TransactionMatch, match_id)
    if not match:
        return None
    old_status = match.status
    match.status = decision_value
    match.reviewed_at = utcnow()
    match.is_manual_confirmed = decision_value == "confirmed"
    session.add(match)
    record_review_decision(
        session,
        object_type="transaction_match",
        object_id=match_id,
        decision_type="status",
        decision_value=decision_value,
        reviewer=reviewer,
        reviewer_note=reviewer_note,
    )
    log_audit(
        session,
        object_type="transaction_match",
        object_id=match_id,
        action_type="review_match",
        field_name="status",
        old_value=old_status,
        new_value=decision_value,
        changed_by=reviewer,
        reason=reviewer_note,
    )
    return match


def update_transaction_fields(
    session: Session,
    *,
    transaction_id: str,
    changes: dict,
    reviewer: str,
    reason: str = "",
) -> Transaction | None:
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        return None

    changed_fields: dict[str, dict[str, object]] = {}
    for field, new_value in changes.items():
        if not hasattr(transaction, field):
            continue
        old_value = getattr(transaction, field)
        if old_value == new_value:
            continue
        setattr(transaction, field, new_value)
        changed_fields[field] = {"old": old_value, "new": new_value}
        log_audit(
            session,
            object_type="transaction",
            object_id=transaction_id,
            action_type="field_update",
            field_name=field,
            old_value=old_value,
            new_value=new_value,
            changed_by=reviewer,
            reason=reason,
        )

    transaction.review_status = "reviewed"
    session.add(transaction)
    if TRANSACTION_COUNTERPARTY_FIELDS.intersection(changed_fields):
        learned_counterparty = None
        if transaction.counterparty_account_normalized:
            learned_counterparty = resolve_account(
                session,
                bank_name="UNKNOWN",
                raw_account_number=transaction.counterparty_account_normalized,
                account_holder_name=transaction.counterparty_name_normalized or transaction.counterparty_name_raw or "",
                account_type="COUNTERPARTY_ACCOUNT",
                confidence_score=0.8,
                notes="learned_from_review:transaction_counterparty",
            )
        record_learning_feedback(
            session,
            learning_domain="counterparty_identity",
            action_type="transaction_review_counterparty",
            source_object_type="transaction",
            source_object_id=transaction_id,
            feedback_status="corrected",
            changed_by=reviewer,
            old_value={key: value["old"] for key, value in changed_fields.items() if key in TRANSACTION_COUNTERPARTY_FIELDS},
            new_value={key: value["new"] for key, value in changed_fields.items() if key in TRANSACTION_COUNTERPARTY_FIELDS},
            reason=reason,
            extra_context={
                "fields": sorted(TRANSACTION_COUNTERPARTY_FIELDS.intersection(changed_fields)),
                "learned_account_id": learned_counterparty.id if learned_counterparty else None,
                "learned_bank_code": learned_counterparty.bank_code if learned_counterparty else None,
                "learned_bank_name": learned_counterparty.bank_name if learned_counterparty else None,
                "bank_resolution_strategy": (
                    "reused_known_bank"
                    if learned_counterparty and str(learned_counterparty.bank_code or "").strip() not in {"", "unknown"}
                    else "unknown_fallback"
                ),
            },
        )
    record_review_decision(
        session,
        object_type="transaction",
        object_id=transaction_id,
        decision_type="correction",
        decision_value="applied",
        reviewer=reviewer,
        reviewer_note=reason,
    )
    return transaction


def update_account_fields(
    session: Session,
    *,
    account_id: str,
    changes: dict,
    reviewer: str,
    reason: str = "",
) -> Account | None:
    account = session.get(Account, account_id)
    if not account:
        return None

    changed_fields: dict[str, dict[str, object]] = {}
    for field, new_value in changes.items():
        if not hasattr(account, field):
            continue
        old_value = getattr(account, field)
        if old_value == new_value:
            continue
        setattr(account, field, new_value)
        changed_fields[field] = {"old": old_value, "new": new_value}
        log_audit(
            session,
            object_type="account",
            object_id=account_id,
            action_type="field_update",
            field_name=field,
            old_value=old_value,
            new_value=new_value,
            changed_by=reviewer,
            reason=reason,
        )

    session.add(account)
    if ACCOUNT_IDENTITY_FIELDS.intersection(changed_fields):
        record_learning_feedback(
            session,
            learning_domain="account_identity",
            action_type="account_review_identity",
            source_object_type="account",
            source_object_id=account_id,
            feedback_status="corrected",
            changed_by=reviewer,
            old_value={key: value["old"] for key, value in changed_fields.items() if key in ACCOUNT_IDENTITY_FIELDS},
            new_value={key: value["new"] for key, value in changed_fields.items() if key in ACCOUNT_IDENTITY_FIELDS},
            reason=reason,
            extra_context={
                "fields": sorted(ACCOUNT_IDENTITY_FIELDS.intersection(changed_fields)),
                "remembered_name_enabled": bool(account.normalized_account_number and account.account_holder_name),
            },
        )
    record_review_decision(
        session,
        object_type="account",
        object_id=account_id,
        decision_type="correction",
        decision_value="applied",
        reviewer=reviewer,
        reviewer_note=reason,
    )
    return account


def get_account_review_payload(session: Session, account_id: str) -> dict | None:
    account = session.get(Account, account_id)
    if not account:
        return None
    return {
        "account_id": account.id,
        "bank_name": account.bank_name,
        "normalized_account_number": account.normalized_account_number,
        "account_holder_name": account.account_holder_name,
        "status": account.status,
        "merge_candidates": find_merge_candidates(session, account_id),
    }
