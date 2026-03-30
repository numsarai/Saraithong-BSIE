from __future__ import annotations

import json

import pandas as pd

from core.graph_domain import DERIVED_ACCOUNT_EDGE_COLUMNS, GraphBuildResult
from services.graph_builder_service import build_graph_from_transactions


def _sample_transactions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "transaction_id": "TXN-2001",
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
                "reference_no": "REF001",
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
                "transaction_id": "TXN-2002",
                "transaction_fingerprint": "fp-2",
                "date": "2026-03-02",
                "time": "10:00:00",
                "transaction_type": "OUT_TRANSFER",
                "direction": "OUT",
                "amount": -500.0,
                "currency": "THB",
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
                "confidence": 0.92,
                "review_status": "reviewed",
                "duplicate_status": "unique",
                "reference_no": "REF002",
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
        ]
    )


def test_build_graph_from_transactions_returns_foundation_bundle():
    result = build_graph_from_transactions(_sample_transactions(), batch_identity="BATCH-1")

    assert isinstance(result, GraphBuildResult)
    assert list(result.derived_account_edges_df.columns) == DERIVED_ACCOUNT_EDGE_COLUMNS
    assert result.manifest["derived_account_edge_count"] == len(result.derived_account_edges_df)
    assert result.manifest["schema_version"] == "1.3"


def test_build_graph_from_transactions_derives_account_to_account_edges_with_traceability():
    result = build_graph_from_transactions(_sample_transactions(), batch_identity="BATCH-1")

    assert len(result.derived_account_edges_df) == 2
    assert set(result.derived_account_edges_df["edge_type"]) == {"DERIVED_ACCOUNT_TO_ACCOUNT"}
    assert set(result.derived_account_edges_df["from_node_id"]) == {"ACCOUNT:2222222222", "ACCOUNT:1111111111"}
    assert set(result.derived_account_edges_df["to_node_id"]) == {"ACCOUNT:1111111111", "ACCOUNT:3333333333"}
    assert all(result.derived_account_edges_df["source_transaction_ids"].astype(str).str.len() > 0)
    assert all(result.derived_account_edges_df["lineage_json"].astype(str).str.contains("source_transaction_ids"))

