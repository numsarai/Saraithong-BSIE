"""
alert_service.py
----------------
Manages suspicious transaction alerts — creation from graph findings,
configuration, listing, and analyst review.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from persistence.base import utcnow
from persistence.models import AdminSetting, Alert, Transaction
from services.audit_service import log_audit

logger = logging.getLogger(__name__)

ALERT_CONFIG_KEY = "alert_rules_config"

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

DEFAULT_ALERT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "min_severity": "medium",
    "min_confidence": 0.5,
    "auto_flag_review": True,
    "rules": {
        "repeated_transfers": True,
        "fan_in_accounts": True,
        "fan_out_accounts": True,
        "circular_paths": True,
        "pass_through_behavior": True,
        "high_degree_hubs": True,
        "repeated_counterparties": True,
    },
}


def get_alert_config(session: Session) -> dict[str, Any]:
    """Load alert rules configuration from AdminSetting."""
    row = session.get(AdminSetting, ALERT_CONFIG_KEY)
    if row and row.value_json:
        return {**DEFAULT_ALERT_CONFIG, **row.value_json}
    return dict(DEFAULT_ALERT_CONFIG)


def update_alert_config(session: Session, config: dict[str, Any], updated_by: str = "analyst") -> dict[str, Any]:
    """Save alert rules configuration."""
    row = session.get(AdminSetting, ALERT_CONFIG_KEY)
    merged = {**DEFAULT_ALERT_CONFIG, **config}
    if row:
        row.value_json = merged
        row.updated_at = utcnow()
        row.updated_by = updated_by
    else:
        row = AdminSetting(
            key=ALERT_CONFIG_KEY,
            value_json=merged,
            updated_at=utcnow(),
            updated_by=updated_by,
        )
        session.add(row)
    session.commit()
    return merged


def _severity_passes(severity: str, min_severity: str) -> bool:
    """Check if a severity level meets the minimum threshold."""
    return SEVERITY_ORDER.get(severity, 99) <= SEVERITY_ORDER.get(min_severity, 2)


def process_findings(
    session: Session,
    findings: list[dict[str, Any]],
    *,
    account_id: str | None = None,
    parser_run_id: str | None = None,
) -> list[Alert]:
    """Convert graph analysis findings into persistent Alert records."""
    config = get_alert_config(session)
    if not config.get("enabled"):
        return []

    min_severity = str(config.get("min_severity", "medium"))
    min_confidence = float(config.get("min_confidence", 0.5))
    enabled_rules = config.get("rules", {})
    auto_flag = bool(config.get("auto_flag_review", True))

    created: list[Alert] = []

    for finding in findings:
        rule_type = str(finding.get("rule_type", ""))
        severity = str(finding.get("severity", "low"))
        confidence = float(finding.get("confidence_score", 0) or 0)
        finding_id = str(finding.get("finding_id", ""))

        # Check if rule is enabled
        if not enabled_rules.get(rule_type, True):
            continue
        # Check severity threshold
        if not _severity_passes(severity, min_severity):
            continue
        # Check confidence threshold
        if confidence < min_confidence:
            continue

        # Check for duplicate finding
        existing = session.scalars(
            select(Alert).where(Alert.finding_id == finding_id)
        ).first()
        if existing:
            continue

        # Extract linked transaction IDs
        txn_ids = []
        raw_ids = finding.get("source_transaction_ids") or finding.get("transaction_ids") or ""
        if isinstance(raw_ids, str):
            txn_ids = [t.strip() for t in raw_ids.split("|") if t.strip()]
        elif isinstance(raw_ids, list):
            txn_ids = [str(t) for t in raw_ids]

        summary = str(finding.get("summary", "") or finding.get("description", "") or f"{rule_type}: {severity}")

        evidence = {
            k: v for k, v in finding.items()
            if k in ("reason_codes", "subject_node_ids", "thresholds", "edge_ids", "node_ids")
        }

        # Create alert for the finding (account-level)
        alert = Alert(
            transaction_id=None,
            account_id=account_id,
            parser_run_id=parser_run_id,
            rule_type=rule_type,
            severity=severity,
            confidence=Decimal(str(confidence)).quantize(Decimal("0.0001")),
            finding_id=finding_id,
            summary=summary,
            evidence_json=evidence,
            status="new",
            created_at=utcnow(),
        )
        session.add(alert)
        created.append(alert)

        # Auto-flag linked transactions for review
        if auto_flag and txn_ids:
            session.execute(
                Transaction.__table__.update()
                .where(Transaction.id.in_(txn_ids))
                .values(review_status="needs_review")
            )

    if created:
        session.flush()
        logger.info("Generated %d alerts from %d findings", len(created), len(findings))

    return created


def list_alerts(
    session: Session,
    *,
    status: str = "",
    severity: str = "",
    rule_type: str = "",
    account_id: str = "",
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List alerts with optional filters."""
    q = select(Alert).order_by(Alert.created_at.desc())
    if status:
        q = q.where(Alert.status == status)
    if severity:
        q = q.where(Alert.severity == severity)
    if rule_type:
        q = q.where(Alert.rule_type == rule_type)
    if account_id:
        q = q.where(Alert.account_id == account_id)
    q = q.offset(offset).limit(limit)

    rows = session.scalars(q).all()
    return [_serialize_alert(a) for a in rows]


def get_alert_summary(session: Session) -> dict[str, Any]:
    """Get summary counts by severity and status."""
    all_alerts = session.scalars(select(Alert)).all()

    by_severity: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for a in all_alerts:
        by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
        by_status[a.status] = by_status.get(a.status, 0) + 1

    return {
        "total": len(all_alerts),
        "by_severity": by_severity,
        "by_status": by_status,
        "new_count": by_status.get("new", 0),
        "critical_count": by_severity.get("critical", 0),
        "high_count": by_severity.get("high", 0),
    }


def review_alert(
    session: Session,
    alert_id: str,
    *,
    status: str,
    reviewer: str = "analyst",
    note: str = "",
) -> dict[str, Any] | None:
    """Acknowledge or resolve an alert."""
    alert = session.get(Alert, alert_id)
    if not alert:
        return None

    old_status = alert.status
    alert.status = status
    alert.reviewed_by = reviewer
    alert.reviewed_at = utcnow()
    alert.review_note = note or alert.review_note
    session.add(alert)

    log_audit(
        session,
        object_type="alert",
        object_id=alert_id,
        action_type="alert_reviewed",
        field_name="status",
        old_value=old_status,
        new_value=status,
        changed_by=reviewer,
        reason=note,
    )

    session.commit()
    return _serialize_alert(alert)


def _serialize_alert(alert: Alert) -> dict[str, Any]:
    return {
        "id": alert.id,
        "transaction_id": alert.transaction_id,
        "account_id": alert.account_id,
        "parser_run_id": alert.parser_run_id,
        "rule_type": alert.rule_type,
        "severity": alert.severity,
        "confidence": float(alert.confidence),
        "finding_id": alert.finding_id,
        "summary": alert.summary,
        "evidence_json": alert.evidence_json,
        "status": alert.status,
        "reviewed_by": alert.reviewed_by,
        "reviewed_at": str(alert.reviewed_at) if alert.reviewed_at else None,
        "review_note": alert.review_note,
        "created_at": str(alert.created_at),
    }
