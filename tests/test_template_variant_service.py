"""Regression tests for guarded bank template variant learning."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from persistence.base import Base
from persistence.models import BankTemplateVariant
from services.template_variant_service import (
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
