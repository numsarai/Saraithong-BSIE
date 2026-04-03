from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from persistence.base import utcnow
from persistence.models import AuditLog, ReviewDecision


def log_audit(
    session: Session,
    *,
    object_type: str,
    object_id: str,
    action_type: str,
    changed_by: str,
    field_name: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
    reason: str = "",
    extra_context: dict | None = None,
) -> AuditLog:
    row = AuditLog(
        object_type=object_type,
        object_id=object_id,
        action_type=action_type,
        field_name=field_name,
        old_value_json=old_value,
        new_value_json=new_value,
        changed_by=changed_by or "analyst",
        changed_at=utcnow(),
        reason=reason or None,
        extra_context_json=extra_context,
    )
    session.add(row)
    session.flush()
    return row


def record_review_decision(
    session: Session,
    *,
    object_type: str,
    object_id: str,
    decision_type: str,
    decision_value: str,
    reviewer: str,
    reviewer_note: str = "",
) -> ReviewDecision:
    row = ReviewDecision(
        object_type=object_type,
        object_id=object_id,
        decision_type=decision_type,
        decision_value=decision_value,
        reviewer=reviewer or "analyst",
        reviewer_note=reviewer_note or None,
        created_at=utcnow(),
    )
    session.add(row)
    session.flush()
    return row
