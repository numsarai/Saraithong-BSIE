from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from core.graph_analysis import (
    GRAPH_ANALYSIS_JSON,
    GRAPH_ANALYSIS_XLSX,
    SUSPICIOUS_FINDINGS_CSV,
    SUSPICIOUS_FINDINGS_JSON,
    build_graph_analysis,
    write_graph_analysis_exports,
)
from core.graph_export import build_graph_exports


def _sample_transactions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "transaction_id": "TXN-1001",
                "transaction_fingerprint": "fp-1",
                "date": "2026-03-01",
                "time": "09:00:00",
                "transaction_type": "IN_TRANSFER",
                "direction": "IN",
                "amount": 1000.0,
                "currency": "THB",
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
                "review_status": "pending",
                "duplicate_status": "unique",
                "reference_no": "REF-1",
                "file_id": "FILE-1",
                "parser_run_id": "RUN-1",
                "statement_batch_id": "BATCH-1",
                "row_number": 2,
                "source_file": "statement.xlsx",
                "source_sheet": "Sheet1",
                "lineage_json": json.dumps(
                    {
                        "file_id": "FILE-1",
                        "parser_run_id": "RUN-1",
                        "statement_batch_id": "BATCH-1",
                        "sheet": "Sheet1",
                        "source_row_number": 2,
                        "source_file": "statement.xlsx",
                    }
                ),
            },
            {
                "transaction_id": "TXN-1002",
                "transaction_fingerprint": "fp-2",
                "date": "2026-03-02",
                "time": "10:00:00",
                "transaction_type": "OUT_TRANSFER",
                "direction": "OUT",
                "amount": -300.0,
                "currency": "THB",
                "subject_account": "1111111111",
                "subject_name": "Subject",
                "counterparty_account": "",
                "partial_account": "12345",
                "counterparty_name": "Partial Bob",
                "from_account": "1111111111",
                "to_account": "PARTIAL:12345",
                "bank": "SCB",
                "channel": "APP",
                "description": "partial transfer out",
                "confidence": 0.88,
                "review_status": "needs_review",
                "duplicate_status": "unique",
                "reference_no": "REF-2",
                "file_id": "FILE-1",
                "parser_run_id": "RUN-1",
                "statement_batch_id": "BATCH-1",
                "row_number": 3,
                "source_file": "statement.xlsx",
                "source_sheet": "Sheet1",
                "lineage_json": json.dumps(
                    {
                        "file_id": "FILE-1",
                        "parser_run_id": "RUN-1",
                        "statement_batch_id": "BATCH-1",
                        "sheet": "Sheet1",
                        "source_row_number": 3,
                        "source_file": "statement.xlsx",
                    }
                ),
            },
            {
                "transaction_id": "TXN-1003",
                "transaction_fingerprint": "fp-3",
                "date": "2026-03-03",
                "time": "11:00:00",
                "transaction_type": "DEPOSIT",
                "direction": "IN",
                "amount": 200.0,
                "currency": "THB",
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
                "review_status": "pending",
                "duplicate_status": "unique",
                "reference_no": "REF-3",
                "file_id": "FILE-1",
                "parser_run_id": "RUN-1",
                "statement_batch_id": "BATCH-1",
                "row_number": 4,
                "source_file": "statement.xlsx",
                "source_sheet": "Sheet1",
                "lineage_json": json.dumps(
                    {
                        "file_id": "FILE-1",
                        "parser_run_id": "RUN-1",
                        "statement_batch_id": "BATCH-1",
                        "sheet": "Sheet1",
                        "source_row_number": 4,
                        "source_file": "statement.xlsx",
                    }
                ),
            },
        ]
    )


def _sample_matches() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": "MATCH-1",
                "source_transaction_id": "TXN-1002",
                "target_transaction_id": "",
                "target_account_number": "2222222222",
                "match_type": "probable_internal_transfer",
                "confidence_score": 0.72,
                "status": "suggested",
                "is_manual_confirmed": False,
                "evidence_json": {"matched_on": "amount+window"},
            }
        ]
    )


def test_build_graph_analysis_consumes_bsie_graph_bundle_with_traceability():
    transactions = _sample_transactions()
    matches = _sample_matches()
    nodes_df, edges_df, aggregated_df, manifest = build_graph_exports(transactions, matches=matches, batch_identity="BATCH-1")

    analysis = build_graph_analysis(
        transactions,
        matches=matches,
        batch_identity="BATCH-1",
        graph_bundle={
            "nodes_df": nodes_df,
            "edges_df": edges_df,
            "aggregated_df": aggregated_df,
            "manifest": manifest,
        },
    )

    assert analysis["schema_version"] == "1.0"
    assert analysis["overview"]["transaction_rows"] == 3
    assert analysis["overview"]["node_count"] == len(nodes_df)
    assert analysis["overview"]["suggested_match_edges"] >= 1
    assert analysis["overview"]["review_candidate_nodes"] >= 1
    assert analysis["overview"]["derived_account_edge_count"] >= 1
    assert "suspicious_findings" in analysis
    assert "suspicious_summary" in analysis
    assert any(row["node_type"] == "PartialAccount" for row in analysis["review_candidates"])
    assert any("partial_account_only" in row["reason_codes"] for row in analysis["review_candidates"])
    assert any(row["edge_type"] == "POSSIBLE_SAME_AS" for row in analysis["edge_type_counts"])
    assert analysis["lineage_summary"]["file_count"] == 1
    assert analysis["top_nodes_by_degree"][0]["node_id"] == "ACCOUNT:1111111111"


def test_write_graph_analysis_exports_writes_json_and_workbook(tmp_path: Path):
    analysis = build_graph_analysis(_sample_transactions(), matches=_sample_matches(), batch_identity="BATCH-1")

    output = write_graph_analysis_exports(tmp_path, analysis)

    assert output["json_path"].name == GRAPH_ANALYSIS_JSON
    assert output["xlsx_path"].name == GRAPH_ANALYSIS_XLSX
    assert output["suspicious_csv_path"].name == SUSPICIOUS_FINDINGS_CSV
    assert output["suspicious_json_path"].name == SUSPICIOUS_FINDINGS_JSON
    assert (tmp_path / GRAPH_ANALYSIS_JSON).exists()
    assert (tmp_path / GRAPH_ANALYSIS_XLSX).exists()
    assert (tmp_path / SUSPICIOUS_FINDINGS_CSV).exists()
    assert (tmp_path / SUSPICIOUS_FINDINGS_JSON).exists()

    payload = json.loads((tmp_path / GRAPH_ANALYSIS_JSON).read_text(encoding="utf-8"))
    assert payload["overview"]["review_candidate_nodes"] >= 1
    suspicious_payload = json.loads((tmp_path / SUSPICIOUS_FINDINGS_JSON).read_text(encoding="utf-8"))
    assert isinstance(suspicious_payload, list)

    workbook = pd.ExcelFile(tmp_path / GRAPH_ANALYSIS_XLSX)
    assert workbook.sheet_names == [
        "Overview",
        "Lineage",
        "Node_Types",
        "Edge_Types",
        "Top_Degree",
        "Top_Flow",
        "Components",
        "Review_Candidates",
        "Finding_Rules",
        "Finding_Severity",
        "Suspicious_Findings",
    ]
