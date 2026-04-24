"""Regression tests for guarded bank template variant learning."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from persistence.base import Base
from persistence.models import BankTemplateVariant
from services.template_variant_service import (
    build_auto_pass_gate,
    find_matching_template_variant,
    list_template_variants,
    promote_template_variant,
    upsert_template_variant,
)


def _session_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'template_variants.db'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_upsert_template_variant_starts_as_candidate_and_reuses_signature(tmp_path):
    factory = _session_factory(tmp_path)
    with factory() as session:
        first = upsert_template_variant(
            session,
            bank_key="SCB",
            source_type="excel",
            sheet_name="Sheet1",
            header_row=1,
            columns=["วันที่", "รายละเอียด", "จำนวนเงิน"],
            mapping={"date": "วันที่", "description": "รายละเอียด", "amount": "จำนวนเงิน"},
            reviewer="reviewer.one",
            feedback_status="accepted",
            dry_run_summary={"valid_transaction_rows": 1},
        )
        second = upsert_template_variant(
            session,
            bank_key="scb",
            source_type="excel",
            sheet_name="Sheet1",
            header_row=1,
            columns=["วันที่", "รายละเอียด", "จำนวนเงิน"],
            mapping={"date": "วันที่", "description": "รายละเอียด", "amount": "จำนวนเงิน"},
            reviewer="reviewer.one",
            feedback_status="accepted",
            dry_run_summary={"valid_transaction_rows": 1},
        )
        session.commit()

        rows = session.scalars(select(BankTemplateVariant)).all()

    assert len(rows) == 1
    assert first["variant_id"] == second["variant_id"]
    assert first["trust_state"] == "candidate"
    assert second["confirmation_count"] == 2
    assert second["trust_state"] == "verified"


def test_template_variant_can_become_trusted_after_multiple_reviewers(tmp_path):
    factory = _session_factory(tmp_path)
    with factory() as session:
        for reviewer in ("reviewer.one", "reviewer.two", "reviewer.two"):
            variant = upsert_template_variant(
                session,
                bank_key="ktb",
                source_type="excel",
                sheet_name="",
                header_row=0,
                columns=["date", "description", "amount"],
                mapping={"date": "date", "description": "description", "amount": "amount"},
                reviewer=reviewer,
                feedback_status="accepted",
                dry_run_summary={"valid_transaction_rows": 3},
            )
        session.commit()

    assert variant["confirmation_count"] == 3
    assert variant["reviewer_count"] == 2
    assert variant["trust_state"] == "trusted"
    assert variant["auto_pass_gate"]["status"] == "ready_observe_only"
    assert variant["auto_pass_gate"]["would_auto_pass"] is True
    assert variant["auto_pass_gate"]["auto_pass_eligible"] is False


def test_auto_pass_gate_reports_blockers_and_rollback_conditions():
    gate = build_auto_pass_gate({
        "source_type": "excel",
        "trust_state": "trusted",
        "confirmation_count": 1,
        "reviewer_count": 1,
        "correction_count": 1,
        "correction_rate": 1.0,
        "dry_run_summary": {"valid_transaction_rows": 0},
    })

    assert gate["mode"] == "observe_only"
    assert gate["would_auto_pass"] is False
    assert gate["auto_pass_eligible"] is False
    assert gate["status"] == "rollback_review"
    assert gate["rollback_recommended"] is True
    assert "insufficient_confirmations" in gate["blocked_reasons"]
    assert "trusted_correction_rate_high" in gate["rollback_reasons"]


def test_find_matching_template_variant_keeps_candidate_exact_order_only(tmp_path):
    factory = _session_factory(tmp_path)
    with factory() as session:
        variant = upsert_template_variant(
            session,
            bank_key="scb",
            source_type="excel",
            sheet_name="Sheet1",
            header_row=0,
            columns=["date", "description", "amount"],
            mapping={"date": "date", "description": "description", "amount": "amount"},
            reviewer="reviewer.one",
            dry_run_summary={"valid_transaction_rows": 1},
        )
        exact = find_matching_template_variant(
            session,
            columns=["date", "description", "amount"],
            bank_key="scb",
            source_type="excel",
            sheet_name="Sheet1",
            header_row=0,
            include_candidate=True,
        )
        reordered = find_matching_template_variant(
            session,
            columns=["amount", "date", "description"],
            bank_key="scb",
            source_type="excel",
            sheet_name="Sheet1",
            header_row=0,
            include_candidate=True,
        )

    assert variant["trust_state"] == "candidate"
    assert exact is not None
    assert exact["variant_id"] == variant["variant_id"]
    assert exact["match_type"] == "ordered_signature"
    assert reordered is None


def test_find_matching_template_variant_allows_trusted_set_signature(tmp_path):
    factory = _session_factory(tmp_path)
    with factory() as session:
        for reviewer in ("reviewer.one", "reviewer.two", "reviewer.two"):
            variant = upsert_template_variant(
                session,
                bank_key="kbank",
                source_type="excel",
                sheet_name="Sheet1",
                header_row=0,
                columns=["date", "description", "amount"],
                mapping={"date": "date", "description": "description", "amount": "amount"},
                reviewer=reviewer,
                dry_run_summary={"valid_transaction_rows": 2},
            )
        matched = find_matching_template_variant(
            session,
            columns=["amount", "date", "description"],
            bank_key="kbank",
            source_type="excel",
            sheet_name="Sheet1",
            header_row=0,
            include_candidate=False,
            allowed_trust_states={"trusted"},
        )

    assert variant["trust_state"] == "trusted"
    assert matched is not None
    assert matched["variant_id"] == variant["variant_id"]
    assert matched["match_type"] == "set_signature"
    assert matched["auto_pass_gate"]["auto_pass_eligible"] is False
    assert "match_not_exact" in matched["auto_pass_gate"]["blocked_reasons"]


def test_manual_promotion_requires_named_reviewer_and_lists_variants(tmp_path):
    factory = _session_factory(tmp_path)
    with factory() as session:
        variant = upsert_template_variant(
            session,
            bank_key="scb",
            columns=["date", "description", "amount"],
            mapping={"date": "date", "description": "description", "amount": "amount"},
            reviewer="reviewer.one",
            dry_run_summary={"valid_transaction_rows": 1},
        )
        try:
            promote_template_variant(
                session,
                variant_id=variant["variant_id"],
                target_state="verified",
                reviewer="analyst",
            )
        except PermissionError:
            pass
        else:
            raise AssertionError("anonymous reviewer should not promote a template variant")

        promoted = promote_template_variant(
            session,
            variant_id=variant["variant_id"],
            target_state="verified",
            reviewer="reviewer.two",
            note="two cases confirmed",
        )
        items = list_template_variants(session, bank_key="scb", trust_state="verified")

    assert promoted["trust_state"] == "verified"
    assert promoted["promoted_by"] == "reviewer.two"
    assert len(items) == 1
    assert items[0]["variant_id"] == variant["variant_id"]
