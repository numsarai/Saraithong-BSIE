"""Tests for services/alert_service.py."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

from persistence.base import Base, utcnow
from persistence.models import Account, AdminSetting, Alert, AuditLog, Transaction
from services.alert_service import (
    DEFAULT_ALERT_CONFIG,
    _severity_passes,
    get_alert_config,
    process_findings,
    review_alert,
    update_alert_config,
)


def _make_engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'alert-service.sqlite'}", future=True)
    Base.metadata.create_all(engine)
    SQLModel.metadata.create_all(engine)
    return engine


# ── _severity_passes ─────────────────────────────────────────────────


def test_severity_passes_critical_meets_any_threshold():
    assert _severity_passes("critical", "low") is True
    assert _severity_passes("critical", "medium") is True
    assert _severity_passes("critical", "high") is True
    assert _severity_passes("critical", "critical") is True


def test_severity_passes_low_only_meets_low():
    assert _severity_passes("low", "low") is True
    assert _severity_passes("low", "medium") is False
    assert _severity_passes("low", "high") is False
    assert _severity_passes("low", "critical") is False


def test_severity_passes_medium_meets_medium_and_low():
    assert _severity_passes("medium", "medium") is True
    assert _severity_passes("medium", "low") is True
    assert _severity_passes("medium", "high") is False


def test_severity_passes_unknown_severity_fails():
    assert _severity_passes("unknown", "medium") is False


# ── get_alert_config ─────────────────────────────────────────────────


def test_get_alert_config_returns_defaults_when_no_setting(tmp_path: Path):
    engine = _make_engine(tmp_path)
    with Session(engine) as session:
        config = get_alert_config(session)
    assert config["enabled"] is True
    assert config["min_severity"] == "medium"
    assert config["min_confidence"] == 0.5


def test_get_alert_config_merges_saved_setting(tmp_path: Path):
    engine = _make_engine(tmp_path)
    with Session(engine) as session:
        update_alert_config(session, {"min_severity": "high", "min_confidence": 0.8})

    with Session(engine) as session:
        config = get_alert_config(session)
    assert config["min_severity"] == "high"
    assert config["min_confidence"] == 0.8
    assert config["enabled"] is True  # default preserved


# ── process_findings ─────────────────────────────────────────────────


def test_process_findings_empty_findings(tmp_path: Path):
    engine = _make_engine(tmp_path)
    with Session(engine) as session:
        alerts = process_findings(session, [])
    assert alerts == []


def test_process_findings_below_threshold(tmp_path: Path):
    engine = _make_engine(tmp_path)
    findings = [
        {
            "finding_id": "f-1",
            "rule_type": "repeated_transfers",
            "severity": "low",
            "confidence_score": 0.9,
            "summary": "Low severity finding",
        },
    ]
    with Session(engine) as session:
        alerts = process_findings(session, findings)
    # default min_severity is "medium", so "low" is filtered out
    assert len(alerts) == 0


def test_process_findings_below_confidence(tmp_path: Path):
    engine = _make_engine(tmp_path)
    findings = [
        {
            "finding_id": "f-2",
            "rule_type": "fan_in_accounts",
            "severity": "high",
            "confidence_score": 0.1,
            "summary": "Low confidence finding",
        },
    ]
    with Session(engine) as session:
        alerts = process_findings(session, findings)
    # default min_confidence is 0.5, so 0.1 is filtered out
    assert len(alerts) == 0


def test_process_findings_qualifying(tmp_path: Path):
    engine = _make_engine(tmp_path)
    findings = [
        {
            "finding_id": "f-3",
            "rule_type": "circular_paths",
            "severity": "high",
            "confidence_score": 0.85,
            "summary": "Circular flow detected",
        },
        {
            "finding_id": "f-4",
            "rule_type": "fan_out_accounts",
            "severity": "critical",
            "confidence_score": 0.95,
            "summary": "Fan-out pattern",
        },
    ]
    with Session(engine) as session:
        alerts = process_findings(session, findings, account_id="acct-x")
        session.commit()

    with Session(engine) as session:
        stored = session.scalars(select(Alert)).all()
    assert len(stored) == 2
    severities = {a.severity for a in stored}
    assert severities == {"high", "critical"}


def test_process_findings_skips_duplicate_finding_id(tmp_path: Path):
    engine = _make_engine(tmp_path)
    finding = {
        "finding_id": "dup-1",
        "rule_type": "high_degree_hubs",
        "severity": "high",
        "confidence_score": 0.9,
        "summary": "Hub detected",
    }
    with Session(engine) as session:
        first = process_findings(session, [finding])
        session.commit()
    assert len(first) == 1

    with Session(engine) as session:
        second = process_findings(session, [finding])
        session.commit()
    assert len(second) == 0


# ── review_alert ─────────────────────────────────────────────────────


def test_review_alert_changes_status_and_logs_audit(tmp_path: Path):
    engine = _make_engine(tmp_path)
    # Create an alert first
    finding = {
        "finding_id": "rev-1",
        "rule_type": "repeated_counterparties",
        "severity": "medium",
        "confidence_score": 0.7,
        "summary": "Repeated counterparty",
    }
    with Session(engine) as session:
        created = process_findings(session, [finding])
        session.commit()
        alert_id = created[0].id

    with Session(engine) as session:
        result = review_alert(
            session,
            alert_id,
            status="acknowledged",
            reviewer="tester",
            note="Reviewed and acknowledged",
        )
    assert result is not None
    assert result["status"] == "acknowledged"
    assert result["reviewed_by"] == "tester"

    with Session(engine) as session:
        audit = session.scalars(
            select(AuditLog).where(AuditLog.object_id == alert_id)
        ).first()
    assert audit is not None
    assert audit.action_type == "alert_reviewed"
    assert audit.old_value_json == "new"
    assert audit.new_value_json == "acknowledged"


def test_review_alert_returns_none_for_missing_id(tmp_path: Path):
    engine = _make_engine(tmp_path)
    with Session(engine) as session:
        result = review_alert(session, "nonexistent-id", status="resolved")
    assert result is None
