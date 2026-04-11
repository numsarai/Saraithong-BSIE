"""Tests for services/anomaly_detection_service.py."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

from persistence.base import Base, utcnow
from persistence.models import Account, FileRecord, ParserRun, Transaction
from services.anomaly_detection_service import (
    _benford_detect,
    _iqr_detect,
    _zscore_detect,
    detect_anomalies,
)


def _make_engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'anomaly.sqlite'}", future=True)
    Base.metadata.create_all(engine)
    SQLModel.metadata.create_all(engine)
    return engine


def _make_txn_dict(amount: float, txn_id: str = "t") -> dict:
    """Build a minimal transaction dict matching _get_amounts output."""
    return {
        "id": txn_id,
        "date": "2026-01-01",
        "amount": amount,
        "abs_amount": abs(amount),
        "direction": "OUT",
        "counterparty": "",
        "counterparty_name": "",
        "description": "",
        "transaction_type": "",
    }


# ── _zscore_detect ───────────────────────────────────────────────────


def test_zscore_detect_normal_data():
    txns = [_make_txn_dict(100.0, f"t{i}") for i in range(20)]
    anomalies, stats = _zscore_detect(txns, sigma=2.0)
    assert len(anomalies) == 0
    assert stats["mean"] == 100.0
    assert stats["count"] == 20


def test_zscore_detect_with_outlier():
    txns = [_make_txn_dict(100.0, f"t{i}") for i in range(19)]
    txns.append(_make_txn_dict(10000.0, "outlier"))
    anomalies, stats = _zscore_detect(txns, sigma=2.0)
    assert len(anomalies) >= 1
    outlier_ids = [a["id"] for a in anomalies]
    assert "outlier" in outlier_ids


def test_zscore_detect_too_few_transactions():
    txns = [_make_txn_dict(100.0), _make_txn_dict(200.0)]
    anomalies, stats = _zscore_detect(txns)
    assert anomalies == []
    assert stats["count"] == 2


def test_zscore_detect_all_zero_amounts():
    txns = [_make_txn_dict(0.0, f"t{i}") for i in range(10)]
    anomalies, stats = _zscore_detect(txns)
    assert anomalies == []
    assert stats["count"] == 0


# ── _iqr_detect ──────────────────────────────────────────────────────


def test_iqr_detect_no_outliers():
    txns = [_make_txn_dict(float(100 + i), f"t{i}") for i in range(20)]
    anomalies, stats = _iqr_detect(txns)
    assert len(anomalies) == 0
    assert stats["count"] == 20
    assert stats["iqr"] >= 0


def test_iqr_detect_with_outlier():
    txns = [_make_txn_dict(100.0, f"t{i}") for i in range(19)]
    txns.append(_make_txn_dict(50000.0, "outlier"))
    anomalies, stats = _iqr_detect(txns)
    assert len(anomalies) >= 1
    outlier_ids = [a["id"] for a in anomalies]
    assert "outlier" in outlier_ids


def test_iqr_detect_too_few_transactions():
    txns = [_make_txn_dict(100.0, f"t{i}") for i in range(3)]
    anomalies, stats = _iqr_detect(txns)
    assert anomalies == []
    assert stats["count"] == 3


# ── _benford_detect ──────────────────────────────────────────────────


def test_benford_detect_too_few_transactions():
    txns = [_make_txn_dict(float(i * 10 + 100), f"t{i}") for i in range(10)]
    anomalies, stats = _benford_detect(txns)
    assert anomalies == []
    assert "Too few" in stats.get("message", "")


def test_benford_detect_with_enough_data():
    # Generate amounts following roughly natural distribution
    import random
    random.seed(42)
    amounts = [random.uniform(100, 99999) for _ in range(200)]
    txns = [_make_txn_dict(a, f"t{i}") for i, a in enumerate(amounts)]
    anomalies, stats = _benford_detect(txns)
    assert stats["count"] == 200
    assert "chi_squared" in stats
    assert stats["conformity"] in ("PASS", "FAIL")


# ── detect_anomalies (integration with DB) ───────────────────────────


def _seed_account_with_transactions(engine, count: int = 20) -> str:
    """Seed an account with transactions and return the account number."""
    now = utcnow()
    with Session(engine) as session:
        file_row = FileRecord(
            id="file-anom-1",
            original_filename="anom.xlsx",
            stored_path="/tmp/anom.xlsx",
            file_hash_sha256="anomhash",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            file_size_bytes=64,
            uploaded_by="tester",
            uploaded_at=now,
            import_status="uploaded",
        )
        run = ParserRun(
            id="run-anom-1",
            file_id="file-anom-1",
            parser_version="test",
            status="done",
            started_at=now,
            finished_at=now,
        )
        acct = Account(
            id="acct-anom-1",
            bank_name="SCB",
            bank_code="SCB",
            raw_account_number="3333333333",
            normalized_account_number="3333333333",
            account_holder_name="Charlie",
        )
        session.add_all([file_row, run, acct])

        for i in range(count):
            amount = Decimal("1000.00") if i < count - 1 else Decimal("99999.00")
            txn = Transaction(
                id=f"txn-anom-{i}",
                file_id="file-anom-1",
                parser_run_id="run-anom-1",
                account_id="acct-anom-1",
                transaction_datetime=datetime(2026, 1, 1 + i % 28, 10, 0, tzinfo=timezone.utc),
                posted_date=datetime(2026, 1, 1 + i % 28).date(),
                amount=amount,
                direction="OUT",
                currency="THB",
            )
            session.add(txn)

        session.commit()
    return "3333333333"


def test_detect_anomalies_invalid_account(tmp_path: Path):
    engine = _make_engine(tmp_path)
    with Session(engine) as session:
        result = detect_anomalies(session, "nonexistent")
    assert result["anomalies"] == []
    assert result["total_transactions"] == 0


def test_detect_anomalies_zscore_method(tmp_path: Path):
    engine = _make_engine(tmp_path)
    acct_num = _seed_account_with_transactions(engine, count=20)
    with Session(engine) as session:
        result = detect_anomalies(session, acct_num, method="zscore")
    assert result["method"] == "zscore"
    assert result["total_transactions"] == 20
    # The last transaction (99999) should be an anomaly
    assert result["anomaly_count"] >= 1


def test_detect_anomalies_iqr_method(tmp_path: Path):
    engine = _make_engine(tmp_path)
    acct_num = _seed_account_with_transactions(engine, count=20)
    with Session(engine) as session:
        result = detect_anomalies(session, acct_num, method="iqr")
    assert result["method"] == "iqr"
    assert result["total_transactions"] == 20
    assert result["anomaly_count"] >= 1
