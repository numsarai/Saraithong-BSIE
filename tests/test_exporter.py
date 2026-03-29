"""Regression tests for i2-oriented export packaging."""
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import core.exporter as exporter


def _sample_transactions() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "transaction_id": "TXN-000001",
            "date": "2026-03-01",
            "time": "09:00:00",
            "transaction_type": "IN_TRANSFER",
            "direction": "IN",
            "amount": 1000.0,
            "currency": "THB",
            "balance": 1000.0,
            "subject_account": "1111111111",
            "subject_name": "Subject",
            "counterparty_account": "2222222222",
            "partial_account": "",
            "counterparty_name": "Alice",
            "from_account": "2222222222",
            "to_account": "1111111111",
            "bank": "SCB",
            "channel": "APP",
            "description": "transfer in",
            "confidence": 0.95,
            "is_overridden": False,
        },
        {
            "transaction_id": "TXN-000002",
            "date": "2026-03-02",
            "time": "10:00:00",
            "transaction_type": "OUT_TRANSFER",
            "direction": "OUT",
            "amount": -500.0,
            "currency": "THB",
            "balance": 500.0,
            "subject_account": "1111111111",
            "subject_name": "Subject",
            "counterparty_account": "3333333333",
            "partial_account": "",
            "counterparty_name": "Bob",
            "from_account": "1111111111",
            "to_account": "3333333333",
            "bank": "SCB",
            "channel": "APP",
            "description": "transfer out",
            "confidence": 0.95,
            "is_overridden": False,
        },
        {
            "transaction_id": "TXN-000003",
            "date": "2026-03-03",
            "time": "11:00:00",
            "transaction_type": "DEPOSIT",
            "direction": "IN",
            "amount": 200.0,
            "currency": "THB",
            "balance": 700.0,
            "subject_account": "1111111111",
            "subject_name": "Subject",
            "counterparty_account": "",
            "partial_account": "",
            "counterparty_name": "Cash Deposit",
            "from_account": "UNKNOWN",
            "to_account": "1111111111",
            "bank": "SCB",
            "channel": "CDM",
            "description": "deposit",
            "confidence": 0.97,
            "is_overridden": False,
        },
        {
            "transaction_id": "TXN-000004",
            "date": "2026-03-04",
            "time": "12:00:00",
            "transaction_type": "WITHDRAW",
            "direction": "OUT",
            "amount": -100.0,
            "currency": "THB",
            "balance": 600.0,
            "subject_account": "1111111111",
            "subject_name": "Subject",
            "counterparty_account": "",
            "partial_account": "",
            "counterparty_name": "ATM Cash",
            "from_account": "1111111111",
            "to_account": "UNKNOWN",
            "bank": "SCB",
            "channel": "ATM",
            "description": "withdraw",
            "confidence": 0.97,
            "is_overridden": False,
        },
    ])


def _sample_entities() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "entity_id": "E1",
            "entity_type": "ACCOUNT",
            "account_number": "1111111111",
            "name": "Subject",
            "first_seen": "2026-03-01",
            "last_seen": "2026-03-04",
            "transaction_count": 4,
            "source_transaction_ids": "TXN-000001|TXN-000002|TXN-000003|TXN-000004",
        },
        {
            "entity_id": "E2",
            "entity_type": "ACCOUNT",
            "account_number": "2222222222",
            "name": "Alice",
            "first_seen": "2026-03-01",
            "last_seen": "2026-03-01",
            "transaction_count": 1,
            "source_transaction_ids": "TXN-000001",
        },
        {
            "entity_id": "E3",
            "entity_type": "ACCOUNT",
            "account_number": "3333333333",
            "name": "Bob",
            "first_seen": "2026-03-02",
            "last_seen": "2026-03-02",
            "transaction_count": 1,
            "source_transaction_ids": "TXN-000002",
        },
        {
            "entity_id": "E4",
            "entity_type": "NAME",
            "account_number": "",
            "name": "UNKNOWN",
            "first_seen": "2026-03-03",
            "last_seen": "2026-03-04",
            "transaction_count": 2,
            "source_transaction_ids": "TXN-000003|TXN-000004",
        },
    ])


def _sample_links() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "transaction_id": "TXN-000001",
            "from_account": "2222222222",
            "to_account": "1111111111",
            "amount": 1000.0,
            "date": "2026-03-01",
            "transaction_type": "IN_TRANSFER",
        },
        {
            "transaction_id": "TXN-000002",
            "from_account": "1111111111",
            "to_account": "3333333333",
            "amount": -500.0,
            "date": "2026-03-02",
            "transaction_type": "OUT_TRANSFER",
        },
        {
            "transaction_id": "TXN-000003",
            "from_account": "UNKNOWN",
            "to_account": "1111111111",
            "amount": 200.0,
            "date": "2026-03-03",
            "transaction_type": "DEPOSIT",
        },
        {
            "transaction_id": "TXN-000004",
            "from_account": "1111111111",
            "to_account": "UNKNOWN",
            "amount": -100.0,
            "date": "2026-03-04",
            "transaction_type": "WITHDRAW",
        },
    ])


def test_export_package_writes_i2_split_outputs(tmp_path):
    """The exporter should create split transaction files and i2-friendly sheets."""
    source_file = tmp_path / "input.xlsx"
    source_file.write_bytes(b"test")

    with patch.object(exporter, "BASE_OUTPUT", tmp_path):
        out_dir = exporter.export_package(
            transactions=_sample_transactions(),
            entities=_sample_entities(),
            links=_sample_links(),
            account_number="1111111111",
            bank="SCB",
            original_file=source_file,
            subject_name="Subject",
        )

    processed_dir = out_dir / "processed"
    expected_files = [
        "transactions.csv",
        "transfer_in.csv",
        "transfer_out.csv",
        "deposit.csv",
        "withdraw.csv",
        "entities.csv",
        "entities.xlsx",
        "links.csv",
        "links.xlsx",
        "i2_chart.anx",
        "Subject_SCB_report.xlsx",
    ]

    for filename in expected_files:
        assert (processed_dir / filename).exists(), f"Missing export file: {filename}"

    workbook = pd.ExcelFile(processed_dir / "Subject_SCB_report.xlsx")
    assert workbook.sheet_names == [
        "All_Transactions",
        "Transfer_In",
        "Transfer_Out",
        "Deposits",
        "Withdrawals",
        "Entities",
        "Links",
    ]

    entities_df = pd.read_csv(processed_dir / "entities.csv", dtype=str).fillna("")
    links_df = pd.read_csv(processed_dir / "links.csv", dtype=str).fillna("")

    assert "entity_label" in entities_df.columns
    assert "identity_value" in entities_df.columns
    assert "from_entity_id" in links_df.columns
    assert "to_entity_id" in links_df.columns
