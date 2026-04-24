from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from persistence.base import Base
from persistence.models import Account, Alert, AuditLog, FileRecord, ParserRun, Transaction
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
    citation_ids = {item["id"] for item in pack["citations"]}
    assert {"run:run-copilot-1", "file:file-copilot-1", "account:acct-copilot-1"} <= citation_ids
    assert {"txn:txn-copilot-1", "txn:txn-copilot-2", "alert:alert-copilot-1"} <= citation_ids
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
    assert audit.object_type == "llm_copilot"
    assert audit.action_type == "copilot_answered"
    assert audit.changed_by == "Case Reviewer"
    assert audit.extra_context_json["context_hash"] == result["context_hash"]
    assert audit.extra_context_json["prompt_hash"] == result["prompt_hash"]
    assert audit.extra_context_json["model"] == "qwen3.5:9b"


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
