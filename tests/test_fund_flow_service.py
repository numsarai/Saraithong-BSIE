"""Tests for services/fund_flow_service.py."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

from persistence.base import Base, utcnow
from persistence.models import Account, FileRecord, ParserRun, Transaction
from services.fund_flow_service import (
    get_account_flows,
    get_matched_transactions,
    trace_fund_path,
)


def _make_engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fund-flow.sqlite'}", future=True)
    Base.metadata.create_all(engine)
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_accounts_and_transactions(engine) -> dict[str, str]:
    """Seed two accounts with transactions flowing between them.

    Returns a dict mapping account labels to their DB ids.
    """
    now = utcnow()
    with Session(engine) as session:
        file_row = FileRecord(
            id="file-ff-1",
            original_filename="flow.xlsx",
            stored_path="/tmp/flow.xlsx",
            file_hash_sha256="ff1hash",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            file_size_bytes=64,
            uploaded_by="tester",
            uploaded_at=now,
            import_status="uploaded",
        )
        run = ParserRun(
            id="run-ff-1",
            file_id="file-ff-1",
            parser_version="test",
            status="done",
            started_at=now,
            finished_at=now,
        )
        acct_a = Account(
            id="acct-a",
            bank_name="SCB",
            bank_code="SCB",
            raw_account_number="1111111111",
            normalized_account_number="1111111111",
            account_holder_name="Alice",
        )
        acct_b = Account(
            id="acct-b",
            bank_name="KBANK",
            bank_code="KBANK",
            raw_account_number="2222222222",
            normalized_account_number="2222222222",
            account_holder_name="Bob",
        )
        # Transactions: A sends to B (OUT from A, counterparty = B)
        txn1 = Transaction(
            id="txn-ff-1",
            file_id="file-ff-1",
            parser_run_id="run-ff-1",
            account_id="acct-a",
            transaction_datetime=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            posted_date=datetime(2026, 1, 15).date(),
            amount=Decimal("5000.00"),
            direction="OUT",
            counterparty_account_normalized="2222222222",
            counterparty_name_normalized="Bob",
            description_normalized="Transfer to Bob",
            currency="THB",
        )
        txn2 = Transaction(
            id="txn-ff-2",
            file_id="file-ff-1",
            parser_run_id="run-ff-1",
            account_id="acct-a",
            transaction_datetime=datetime(2026, 2, 1, 14, 0, tzinfo=timezone.utc),
            posted_date=datetime(2026, 2, 1).date(),
            amount=Decimal("3000.00"),
            direction="OUT",
            counterparty_account_normalized="2222222222",
            counterparty_name_normalized="Bob",
            description_normalized="Second transfer to Bob",
            currency="THB",
        )
        # B receives from A (IN to A's account perspective is not needed;
        # the service reads from A's transactions)
        txn3 = Transaction(
            id="txn-ff-3",
            file_id="file-ff-1",
            parser_run_id="run-ff-1",
            account_id="acct-a",
            transaction_datetime=datetime(2026, 2, 10, 9, 0, tzinfo=timezone.utc),
            posted_date=datetime(2026, 2, 10).date(),
            amount=Decimal("2000.00"),
            direction="IN",
            counterparty_account_normalized="2222222222",
            counterparty_name_normalized="Bob",
            description_normalized="Refund from Bob",
            currency="THB",
        )
        session.add_all([file_row, run, acct_a, acct_b, txn1, txn2, txn3])
        session.commit()

    return {"a": "acct-a", "b": "acct-b"}


# ── get_account_flows ────────────────────────────────────────────────


def test_get_account_flows_valid_account(tmp_path: Path):
    engine = _make_engine(tmp_path)
    _seed_accounts_and_transactions(engine)

    with Session(engine) as session:
        result = get_account_flows(session, "1111111111")

    assert result["account"] == "1111111111"
    assert result["name"] == "Alice"
    assert result["total_out"] == 8000.00  # 5000 + 3000
    assert result["total_in"] == 2000.00
    assert result["outbound_count"] == 1  # one unique counterparty
    assert result["inbound_count"] == 1


def test_get_account_flows_nonexistent_account(tmp_path: Path):
    engine = _make_engine(tmp_path)
    _seed_accounts_and_transactions(engine)

    with Session(engine) as session:
        result = get_account_flows(session, "9999999999")

    assert result["inbound"] == []
    assert result["outbound"] == []
    assert result["total_in"] == 0
    assert result["total_out"] == 0


# ── get_matched_transactions ─────────────────────────────────────────


def test_get_matched_transactions_returns_transactions(tmp_path: Path):
    engine = _make_engine(tmp_path)
    _seed_accounts_and_transactions(engine)

    with Session(engine) as session:
        matches = get_matched_transactions(session, "1111111111", "2222222222")

    # 3 transactions from A where counterparty is B
    assert len(matches) == 3
    amounts = sorted(m["amount"] for m in matches)
    assert amounts == [2000.0, 3000.0, 5000.0]


def test_get_matched_transactions_no_match(tmp_path: Path):
    engine = _make_engine(tmp_path)
    _seed_accounts_and_transactions(engine)

    with Session(engine) as session:
        matches = get_matched_transactions(session, "1111111111", "8888888888")

    assert matches == []


def test_get_matched_transactions_invalid_account(tmp_path: Path):
    engine = _make_engine(tmp_path)

    with Session(engine) as session:
        matches = get_matched_transactions(session, "", "2222222222")

    assert matches == []


# ── trace_fund_path ──────────────────────────────────────────────────


def test_trace_fund_path_same_account(tmp_path: Path):
    engine = _make_engine(tmp_path)
    _seed_accounts_and_transactions(engine)

    with Session(engine) as session:
        result = trace_fund_path(session, "1111111111", "1111111111")

    assert result["found"] is True
    assert len(result["paths"]) == 1
    assert result["paths"][0]["hops"] == ["1111111111"]


def test_trace_fund_path_nonexistent_returns_empty(tmp_path: Path):
    engine = _make_engine(tmp_path)

    with Session(engine) as session:
        result = trace_fund_path(session, "1111111111", "9999999999")

    assert result["found"] is False
    assert result["paths"] == []


def test_trace_fund_path_direct_connection(tmp_path: Path):
    engine = _make_engine(tmp_path)
    _seed_accounts_and_transactions(engine)

    with Session(engine) as session:
        result = trace_fund_path(session, "1111111111", "2222222222")

    assert result["found"] is True
    assert len(result["paths"]) >= 1
    first_path = result["paths"][0]
    assert first_path["hops"][0] == "1111111111"
    assert first_path["hops"][-1] == "2222222222"


def test_trace_fund_path_invalid_account(tmp_path: Path):
    engine = _make_engine(tmp_path)

    with Session(engine) as session:
        result = trace_fund_path(session, "", "2222222222")

    assert result["found"] is False
