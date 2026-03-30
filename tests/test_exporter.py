"""Regression tests for i2-oriented export packaging."""
import json
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
        "account.ofx",
        "entities.csv",
        "entities.xlsx",
        "links.csv",
        "links.xlsx",
        "nodes.csv",
        "nodes.json",
        "edges.csv",
        "edges.json",
        "aggregated_edges.csv",
        "aggregated_edges.json",
        "derived_account_edges.csv",
        "derived_account_edges.json",
        "graph_manifest.json",
        "graph_analysis.json",
        "graph_analysis.xlsx",
        "suspicious_findings.csv",
        "suspicious_findings.json",
        "reconciliation.csv",
        "reconciliation.xlsx",
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
        "Reconciliation",
    ]

    entities_df = pd.read_csv(processed_dir / "entities.csv", dtype=str).fillna("")
    links_df = pd.read_csv(processed_dir / "links.csv", dtype=str).fillna("")
    nodes_df = pd.read_csv(processed_dir / "nodes.csv", dtype=str).fillna("")
    edges_df = pd.read_csv(processed_dir / "edges.csv", dtype=str).fillna("")
    aggregated_df = pd.read_csv(processed_dir / "aggregated_edges.csv", dtype=str).fillna("")
    derived_df = pd.read_csv(processed_dir / "derived_account_edges.csv", dtype=str).fillna("")
    transactions_df = pd.read_csv(processed_dir / "transactions.csv", dtype=str).fillna("")
    transfer_out_df = pd.read_csv(processed_dir / "transfer_out.csv", dtype=str).fillna("")

    assert "entity_label" in entities_df.columns
    assert "identity_value" in entities_df.columns
    assert "from_entity_id" in links_df.columns
    assert "to_entity_id" in links_df.columns
    assert "node_type" in nodes_df.columns
    assert "edge_type" in edges_df.columns
    assert "assertion_status" in edges_df.columns
    assert "transaction_count" in aggregated_df.columns
    assert "edge_type" in derived_df.columns
    assert transactions_df.loc[0, "date"] == "01 03 2026"
    assert transactions_df.loc[0, "amount"] == "1,000"
    assert transfer_out_df.loc[0, "amount"] == "500"

    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["report_filename"] == "Subject_SCB_report.xlsx"
    assert meta["reconciliation"]["status"] in {"VERIFIED", "PARTIAL", "FAILED", "INFERRED"}
    assert meta["category_files"]["reconciliation"] == "reconciliation.csv"
    assert meta["category_files"]["ofx"] == "account.ofx"
    assert meta["category_files"]["nodes"] == "nodes.csv"
    assert meta["category_files"]["nodes_json"] == "nodes.json"
    assert meta["category_files"]["edges"] == "edges.csv"
    assert meta["category_files"]["edges_json"] == "edges.json"
    assert meta["category_files"]["aggregated_edges"] == "aggregated_edges.csv"
    assert meta["category_files"]["aggregated_edges_json"] == "aggregated_edges.json"
    assert meta["category_files"]["derived_account_edges"] == "derived_account_edges.csv"
    assert meta["category_files"]["derived_account_edges_json"] == "derived_account_edges.json"
    assert meta["category_files"]["graph_manifest"] == "graph_manifest.json"
    assert meta["category_files"]["graph_analysis"] == "graph_analysis.json"
    assert meta["category_files"]["graph_analysis_workbook"] == "graph_analysis.xlsx"
    assert meta["category_files"]["suspicious_findings"] == "suspicious_findings.csv"
    assert meta["category_files"]["suspicious_findings_json"] == "suspicious_findings.json"
    assert meta["graph_analysis"]["overview"]["transaction_rows"] == 4
    assert meta["original_filename"] == "input.xlsx"


def test_export_package_removes_stale_report_variants_on_rerun(tmp_path):
    source_file = tmp_path / "input.xlsx"
    source_file.write_bytes(b"test")

    account_dir = tmp_path / "1111111111"
    processed_dir = account_dir / "processed"
    processed_dir.mkdir(parents=True)
    stale_one = processed_dir / "นาย ทวีกิจ แก้วฤทธิ์_SCB_report.xlsx"
    stale_two = processed_dir / "นายทวีกิจ แก้วฤทธิ์_SCB_report.xlsx"
    stale_one.write_text("old", encoding="utf-8")
    stale_two.write_text("old", encoding="utf-8")

    with patch.object(exporter, "BASE_OUTPUT", tmp_path):
        out_dir = exporter.export_package(
            transactions=_sample_transactions(),
            entities=_sample_entities(),
            links=_sample_links(),
            account_number="1111111111",
            bank="SCB",
            original_file=source_file,
            subject_name="นาย ทวีกิจ แก้วฤทธิ์",
        )

    processed_dir = out_dir / "processed"
    assert (processed_dir / "นาย ทวีกิจ แก้วฤทธิ์_SCB_report.xlsx").exists()
    assert not (processed_dir / "นายทวีกิจ แก้วฤทธิ์_SCB_report.xlsx").exists()
