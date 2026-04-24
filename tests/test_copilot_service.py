from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from persistence.base import Base
from persistence.models import Account, Alert, AuditLog, CaseTag, CaseTagLink, FileRecord, ParserRun, ReviewDecision, Transaction
from services.copilot_service import (
    CopilotScopeError,
    answer_copilot_question,
    build_copilot_context_pack,
)


def _make_engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'copilot-service.sqlite'}", future=True)
    Base.metadata.create_all(engine)
    return engine


def _seed_scope(session: Session) -> None:
    file_row = FileRecord(
        id="file-copilot-1",
        original_filename="statement.xlsx",
        stored_path="/evidence/file-copilot-1/original.xlsx",
        file_hash_sha256="a" * 64,
        file_size_bytes=2048,
        uploaded_by="tester",
        bank_detected="scb",
        import_status="processed",
    )
    parser_run = ParserRun(
        id="run-copilot-1",
        file_id=file_row.id,
        parser_version="test",
        status="done",
        bank_detected="scb",
        summary_json={"rows": 2},
    )
    account = Account(
        id="acct-copilot-1",
        bank_name="SCB",
        bank_code="scb",
        raw_account_number="123-456-7890",
        normalized_account_number="1234567890",
        display_account_number="123-456-7890",
        account_holder_name="Known Holder",
    )
    session.add_all([file_row, parser_run, account])
    session.flush()
    session.add_all(
        [
            Transaction(
                id="txn-copilot-1",
                file_id=file_row.id,
                parser_run_id=parser_run.id,
                account_id=account.id,
                transaction_datetime=datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
                amount=Decimal("-1500.00"),
                direction="OUT",
                currency="THB",
                description_raw="TRANSFER TO 9876543210",
                counterparty_account_normalized="9876543210",
                counterparty_name_normalized="Counterparty A",
                transaction_type="OUT_TRANSFER",
                review_status="pending",
                linkage_status="linked",
            ),
            Transaction(
                id="txn-copilot-2",
                file_id=file_row.id,
                parser_run_id=parser_run.id,
                account_id=account.id,
                transaction_datetime=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
                amount=Decimal("2500.00"),
                direction="IN",
                currency="THB",
                description_raw="TRANSFER FROM 1111222233",
                counterparty_account_normalized="1111222233",
                counterparty_name_normalized="Counterparty B",
                transaction_type="IN_TRANSFER",
                review_status="pending",
                linkage_status="linked",
            ),
        ]
    )
    session.add(
        Alert(
            id="alert-copilot-1",
            account_id=account.id,
            parser_run_id=parser_run.id,
            rule_type="fan_out_accounts",
            severity="high",
            confidence=Decimal("0.8000"),
            summary="Fan-out behavior detected",
            evidence_json={"transaction_ids": ["txn-copilot-1"]},
        )
    )
    session.add_all(
        [
            CaseTag(
                id="case-tag-copilot-1",
                tag="CASE-ALPHA",
                description="Alpha evidence group",
                created_at=datetime(2026, 1, 3, 9, 0, tzinfo=timezone.utc),
            ),
            CaseTagLink(
                id="case-tag-link-copilot-1",
                case_tag_id="case-tag-copilot-1",
                object_type="transaction",
                object_id="txn-copilot-1",
                created_at=datetime(2026, 1, 3, 9, 1, tzinfo=timezone.utc),
            ),
        ]
    )
    session.add_all(
        [
            ReviewDecision(
                id="review-copilot-1",
                object_type="transaction",
                object_id="txn-copilot-1",
                decision_type="correction",
                decision_value="applied",
                reviewer="Case Reviewer",
                reviewer_note="Corrected counterparty name",
                created_at=datetime(2026, 1, 3, 10, 0, tzinfo=timezone.utc),
            ),
            AuditLog(
                id="audit-copilot-review-1",
                object_type="transaction",
                object_id="txn-copilot-1",
                action_type="field_update",
                field_name="counterparty_name_normalized",
                old_value_json="Counterparty Old",
                new_value_json="Counterparty A",
                changed_by="Case Reviewer",
                changed_at=datetime(2026, 1, 3, 10, 1, tzinfo=timezone.utc),
                reason="Corrected name from source evidence",
            ),
        ]
    )
    session.commit()


def test_build_copilot_context_pack_scopes_transactions_and_citations(tmp_path: Path):
    engine = _make_engine(tmp_path)
    with Session(engine) as session:
        _seed_scope(session)
        pack = build_copilot_context_pack(
            session,
            {"parser_run_id": "run-copilot-1", "account": "123-456-7890"},
            max_transactions=5,
        )

    assert pack["source"] == "deterministic_copilot_context"
    assert pack["read_only"] is True
    assert pack["mutations_allowed"] is False
    assert pack["scope"]["parser_run_id"] == "run-copilot-1"
    assert pack["scope"]["account_digits"] == "1234567890"
    assert pack["evidence"]["summary"]["transaction_count"] == 2
    assert pack["evidence"]["summary"]["total_in"] == 2500.0
    assert pack["evidence"]["summary"]["total_out"] == 1500.0
    graph_metrics = pack["evidence"]["graph_metrics"]
    assert graph_metrics["transaction_edge_count"] == 2
    assert graph_metrics["unique_counterparty_count"] == 2
    assert graph_metrics["inbound_counterparty_count"] == 1
    assert graph_metrics["outbound_counterparty_count"] == 1
    assert graph_metrics["directional_degree"] == 2
    assert graph_metrics["flow_in_value"] == 2500.0
    assert graph_metrics["flow_out_value"] == 1500.0
    assert graph_metrics["account_metrics"][0]["citation_id"] == "account:acct-copilot-1"
    citation_ids = {item["id"] for item in pack["citations"]}
    assert {"run:run-copilot-1", "file:file-copilot-1", "account:acct-copilot-1"} <= citation_ids
    assert {"txn:txn-copilot-1", "txn:txn-copilot-2", "alert:alert-copilot-1"} <= citation_ids
    review_history = pack["evidence"]["review_history"]
    assert review_history["decision_count"] == 1
    assert review_history["audit_event_count"] == 1
    assert review_history["review_decisions"][0]["citation_id"] == "txn:txn-copilot-1"
    assert review_history["audit_events"][0]["citation_id"] == "txn:txn-copilot-1"
    assert review_history["audit_events"][0]["field_name"] == "counterparty_name_normalized"
    assert len(pack["context_hash"]) == 64


def test_build_copilot_context_pack_requires_scope(tmp_path: Path):
    engine = _make_engine(tmp_path)
    with Session(engine) as session:
        try:
            build_copilot_context_pack(session, {})
        except CopilotScopeError as exc:
            assert "copilot_scope requires" in str(exc)
        else:
            raise AssertionError("empty copilot scope should fail closed")


def test_build_copilot_context_pack_accepts_case_tag_scope(tmp_path: Path):
    engine = _make_engine(tmp_path)
    with Session(engine) as session:
        _seed_scope(session)
        pack = build_copilot_context_pack(
            session,
            {"case_tag_id": "case-tag-copilot-1"},
            max_transactions=5,
        )

    assert pack["scope"]["case_tag_id"] == "case-tag-copilot-1"
    assert pack["evidence"]["case_tag"]["tag"] == "CASE-ALPHA"
    assert pack["evidence"]["case_tag"]["linked_object_count"] == 1
    assert pack["evidence"]["summary"]["transaction_count"] == 1
    assert pack["evidence"]["top_transactions"][0]["transaction_id"] == "txn-copilot-1"
    assert pack["evidence"]["graph_metrics"]["transaction_edge_count"] == 1
    assert pack["evidence"]["review_history"]["decision_count"] == 1


def test_answer_copilot_question_calls_llm_without_auto_context_and_audits(tmp_path: Path):
    engine = _make_engine(tmp_path)
    calls = []

    async def fake_chat(message, **kwargs):
        calls.append({"message": message, **kwargs})
        return {
            "model": kwargs["model"],
            "response": "บัญชีนี้มีรายการออกสำคัญ 1,500 บาท [txn:txn-copilot-1] และมี alert fan-out [alert:alert-copilot-1]",
            "prompt_tokens": 123,
            "completion_tokens": 45,
        }

    with Session(engine) as session:
        _seed_scope(session)
        result = asyncio.run(
            answer_copilot_question(
                session,
                question="ช่วยสรุปความเสี่ยงของบัญชีนี้",
                scope={"parser_run_id": "run-copilot-1", "account": "1234567890"},
                operator="Case Reviewer",
                llm_chat=fake_chat,
            )
        )
        session.commit()
        audit = session.scalars(select(AuditLog).where(AuditLog.id == result["audit_id"])).one()

    assert result["status"] == "ok"
    assert result["read_only"] is True
    assert result["citation_policy"]["status"] == "ok"
    assert calls[0]["auto_context"] is False
    assert calls[0]["think"] is False
    assert calls[0]["model"] == "qwen3.5:9b"
    assert "Deterministic context pack" in calls[0]["message"]
    assert "Task mode: freeform" in calls[0]["message"]
    assert "Case tags are scope filters" in calls[0]["message"]
    assert "When discussing graph_metrics" in calls[0]["message"]
    assert "When discussing review_history or audit_events" in calls[0]["message"]
    assert audit.object_type == "llm_copilot"
    assert audit.action_type == "copilot_answered"
    assert audit.changed_by == "Case Reviewer"
    assert audit.extra_context_json["context_hash"] == result["context_hash"]
    assert audit.extra_context_json["prompt_hash"] == result["prompt_hash"]
    assert audit.extra_context_json["model"] == "qwen3.5:9b"
    assert audit.extra_context_json["task_mode"] == "freeform"


def test_answer_copilot_question_flags_uncited_answers_for_review(tmp_path: Path):
    engine = _make_engine(tmp_path)

    async def fake_chat(*args, **kwargs):
        return {
            "model": kwargs["model"],
            "response": "บัญชีนี้มีความเสี่ยงสูง แต่ไม่ได้แนบ record id",
        }

    with Session(engine) as session:
        _seed_scope(session)
        result = asyncio.run(
            answer_copilot_question(
                session,
                question="ช่วยสรุปความเสี่ยง",
                scope={"parser_run_id": "run-copilot-1"},
                llm_chat=fake_chat,
            )
        )

    assert result["status"] == "needs_review"
    assert result["citation_policy"]["status"] == "missing_citation"
    assert any("required evidence citations" in warning for warning in result["warnings"])


def test_answer_copilot_question_applies_structured_task_mode(tmp_path: Path):
    engine = _make_engine(tmp_path)
    calls = []

    async def fake_chat(message, **kwargs):
        calls.append({"message": message, **kwargs})
        return {
            "model": kwargs["model"],
            "response": "รายการตรวจทานควรดูรายการออก 1,500 บาท [txn:txn-copilot-1] และ alert fan-out [alert:alert-copilot-1]",
        }

    with Session(engine) as session:
        _seed_scope(session)
        result = asyncio.run(
            answer_copilot_question(
                session,
                question="",
                scope={"parser_run_id": "run-copilot-1", "account": "1234567890"},
                task_mode="review_checklist",
                operator="Reviewer",
                llm_chat=fake_chat,
            )
        )
        audit = session.scalars(select(AuditLog).where(AuditLog.id == result["audit_id"])).one()

    assert result["status"] == "ok"
    assert result["task_mode"] == "review_checklist"
    assert "Task mode: review_checklist" in calls[0]["message"]
    assert "Create an analyst review checklist" in calls[0]["message"]
    assert "Do not mark anything final" in calls[0]["message"]
    assert audit.extra_context_json["task_mode"] == "review_checklist"


def test_answer_copilot_question_supports_report_analysis_task_mode(tmp_path: Path):
    engine = _make_engine(tmp_path)
    calls = []

    async def fake_chat(message, **kwargs):
        calls.append({"message": message, **kwargs})
        return {
            "model": kwargs["model"],
            "response": "บทวิเคราะห์รายงานระบุรายการออกสำคัญ [txn:txn-copilot-1] และ alert ที่ต้องตรวจสอบ [alert:alert-copilot-1]",
        }

    with Session(engine) as session:
        _seed_scope(session)
        result = asyncio.run(
            answer_copilot_question(
                session,
                question="",
                scope={"parser_run_id": "run-copilot-1", "account": "1234567890"},
                task_mode="investigation_report_analysis",
                operator="Reviewer",
                llm_chat=fake_chat,
            )
        )
        audit = session.scalars(select(AuditLog).where(AuditLog.id == result["audit_id"])).one()

    assert result["status"] == "ok"
    assert result["task_mode"] == "investigation_report_analysis"
    assert "Task mode: investigation_report_analysis" in calls[0]["message"]
    assert "not a final investigative or legal conclusion" in calls[0]["message"]
    assert audit.extra_context_json["task_mode"] == "investigation_report_analysis"


def test_answer_copilot_question_rejects_unknown_task_mode(tmp_path: Path):
    engine = _make_engine(tmp_path)
    with Session(engine) as session:
        _seed_scope(session)
        try:
            asyncio.run(
                answer_copilot_question(
                    session,
                    question="Summarize",
                    scope={"parser_run_id": "run-copilot-1"},
                    task_mode="mutate_evidence",
                )
            )
        except CopilotScopeError as exc:
            assert "unsupported copilot task_mode" in str(exc)
        else:
            raise AssertionError("unknown copilot task modes should fail closed")
