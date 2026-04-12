"""Tests for services/sna_service.py."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

from persistence.base import Base, utcnow
from persistence.models import Account, FileRecord, ParserRun, Transaction
from services.sna_service import compute_sna_metrics


def _make_engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sna.sqlite'}", future=True)
    Base.metadata.create_all(engine)
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_network(engine) -> None:
    """Seed a small 3-node network: A -> B -> C with transactions."""
    now = utcnow()
    with Session(engine) as session:
        file_row = FileRecord(
            id="file-sna-1",
            original_filename="sna.xlsx",
            stored_path="/tmp/sna.xlsx",
            file_hash_sha256="snahash",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            file_size_bytes=64,
            uploaded_by="tester",
            uploaded_at=now,
            import_status="uploaded",
        )
        run = ParserRun(
            id="run-sna-1",
            file_id="file-sna-1",
            parser_version="test",
            status="done",
            started_at=now,
            finished_at=now,
        )
        acct_a = Account(
            id="sna-a",
            bank_name="SCB",
            bank_code="SCB",
            raw_account_number="4444444444",
            normalized_account_number="4444444444",
            account_holder_name="Node A",
        )
        acct_b = Account(
            id="sna-b",
            bank_name="KBANK",
            bank_code="KBANK",
            raw_account_number="5555555555",
            normalized_account_number="5555555555",
            account_holder_name="Node B",
        )
        acct_c = Account(
            id="sna-c",
            bank_name="BBL",
            bank_code="BBL",
            raw_account_number="6666666666",
            normalized_account_number="6666666666",
            account_holder_name="Node C",
        )

        # A -> B (OUT from A)
        txn1 = Transaction(
            id="txn-sna-1",
            file_id="file-sna-1",
            parser_run_id="run-sna-1",
            account_id="sna-a",
            transaction_datetime=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
            posted_date=datetime(2026, 3, 1).date(),
            amount=Decimal("10000.00"),
            direction="OUT",
            counterparty_account_normalized="5555555555",
            counterparty_name_normalized="Node B",
            currency="THB",
        )
        # B -> C (OUT from B)
        txn2 = Transaction(
            id="txn-sna-2",
            file_id="file-sna-1",
            parser_run_id="run-sna-1",
            account_id="sna-b",
            transaction_datetime=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
            posted_date=datetime(2026, 3, 2).date(),
            amount=Decimal("7000.00"),
            direction="OUT",
            counterparty_account_normalized="6666666666",
            counterparty_name_normalized="Node C",
            currency="THB",
        )
        # A -> C (OUT from A, direct)
        txn3 = Transaction(
            id="txn-sna-3",
            file_id="file-sna-1",
            parser_run_id="run-sna-1",
            account_id="sna-a",
            transaction_datetime=datetime(2026, 3, 3, 10, 0, tzinfo=timezone.utc),
            posted_date=datetime(2026, 3, 3).date(),
            amount=Decimal("3000.00"),
            direction="OUT",
            counterparty_account_normalized="6666666666",
            counterparty_name_normalized="Node C",
            currency="THB",
        )

        session.add_all([file_row, run, acct_a, acct_b, acct_c, txn1, txn2, txn3])
        session.commit()


# ── compute_sna_metrics ──────────────────────────────────────────────


def test_compute_sna_metrics_empty_db(tmp_path: Path):
    engine = _make_engine(tmp_path)
    with Session(engine) as session:
        result = compute_sna_metrics(session)
    assert result["nodes"] == []
    assert result["summary"]["node_count"] == 0
    assert result["summary"]["edge_count"] == 0


def test_compute_sna_metrics_returns_all_nodes(tmp_path: Path):
    engine = _make_engine(tmp_path)
    _seed_network(engine)

    with Session(engine) as session:
        result = compute_sna_metrics(session)

    assert result["summary"]["node_count"] == 3
    node_ids = {n["id"] for n in result["nodes"]}
    assert "4444444444" in node_ids
    assert "5555555555" in node_ids
    assert "6666666666" in node_ids


def test_compute_sna_metrics_structure(tmp_path: Path):
    engine = _make_engine(tmp_path)
    _seed_network(engine)

    with Session(engine) as session:
        result = compute_sna_metrics(session)

    assert "nodes" in result
    assert "summary" in result

    node = result["nodes"][0]
    assert "id" in node
    assert "degree" in node
    assert "degree_normalized" in node
    assert "betweenness" in node
    assert "betweenness_normalized" in node
    assert "closeness" in node
    assert "flow_in" in node
    assert "flow_out" in node
    assert "flow_total" in node
    assert "txn_count" in node

    summary = result["summary"]
    assert "node_count" in summary
    assert "edge_count" in summary
    assert "max_degree" in summary
    assert "max_betweenness" in summary
    assert "avg_closeness" in summary


def test_compute_sna_metrics_degree_values(tmp_path: Path):
    engine = _make_engine(tmp_path)
    _seed_network(engine)

    with Session(engine) as session:
        result = compute_sna_metrics(session)

    nodes_by_id = {n["id"]: n for n in result["nodes"]}

    # A has edges to B and C (degree >= 2)
    assert nodes_by_id["4444444444"]["degree"] >= 2
    # B has edges from A and to C (degree >= 2)
    assert nodes_by_id["5555555555"]["degree"] >= 2
    # C has edges from A and B (degree >= 2)
    assert nodes_by_id["6666666666"]["degree"] >= 2


def test_compute_sna_metrics_with_account_filter(tmp_path: Path):
    engine = _make_engine(tmp_path)
    _seed_network(engine)

    with Session(engine) as session:
        result = compute_sna_metrics(session, accounts=["4444444444", "5555555555"])

    node_ids = {n["id"] for n in result["nodes"]}
    # Only the filtered accounts should appear
    assert "6666666666" not in node_ids
    assert result["summary"]["node_count"] <= 2


def test_compute_sna_metrics_edge_count(tmp_path: Path):
    engine = _make_engine(tmp_path)
    _seed_network(engine)

    with Session(engine) as session:
        result = compute_sna_metrics(session)

    # 3 transactions create 3 directed edges: A->B, B->C, A->C
    assert result["summary"]["edge_count"] == 3
