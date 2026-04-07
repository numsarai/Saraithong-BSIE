from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from defusedxml import ElementTree as ET

from core.export_anx import export_anx_from_graph
from core.graph_export import (
    AGGREGATED_EDGE_COLUMNS,
    GRAPH_EDGE_COLUMNS,
    GRAPH_NODE_COLUMNS,
    build_derived_account_edges,
    build_graph_exports,
)


def _sample_transactions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "transaction_id": "TXN-000001",
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
                "transaction_id": "TXN-000002",
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
            {
                "transaction_id": "TXN-000003",
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
                "reference_no": "REF003",
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
            {
                "transaction_id": "TXN-000004",
                "transaction_fingerprint": "fp-4",
                "date": "2026-03-04",
                "time": "12:00:00",
                "transaction_type": "OUT_TRANSFER",
                "direction": "OUT",
                "amount": -250.0,
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
                "description": "second transfer out",
                "confidence": 0.91,
                "review_status": "pending",
                "duplicate_status": "unique",
                "reference_no": "REF004",
                "file_id": "FILE-1",
                "parser_run_id": "RUN-1",
                "statement_batch_id": "BATCH-1",
                "row_number": 5,
                "source_file": "statement.xlsx",
                "source_sheet": "Sheet1",
                "lineage_json": json.dumps(
                    {
                        "file_id": "FILE-1",
                        "parser_run_id": "RUN-1",
                        "statement_batch_id": "BATCH-1",
                        "sheet": "Sheet1",
                        "source_row_number": 5,
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
                "source_transaction_id": "TXN-000002",
                "target_transaction_id": "TXN-000004",
                "target_account_number": "",
                "match_type": "mirrored_transfer_match",
                "confidence_score": 0.9,
                "status": "confirmed",
                "is_manual_confirmed": True,
                "evidence_json": {"matched_on": "amount+time"},
            },
            {
                "id": "MATCH-2",
                "source_transaction_id": "TXN-000001",
                "target_transaction_id": "",
                "target_account_number": "2222222222",
                "match_type": "exact_account_match",
                "confidence_score": 1.0,
                "status": "suggested",
                "is_manual_confirmed": False,
                "evidence_json": {"matched_on": "counterparty_account"},
            },
            {
                "id": "MATCH-3",
                "source_transaction_id": "TXN-000003",
                "target_transaction_id": "TXN-000001",
                "target_account_number": "",
                "match_type": "bad_match",
                "confidence_score": 0.1,
                "status": "rejected",
                "is_manual_confirmed": False,
                "evidence_json": {},
            },
        ]
    )


def test_build_graph_exports_produces_stable_schema_and_ids():
    transactions = _sample_transactions()
    matches = _sample_matches()

    first = build_graph_exports(transactions, matches=matches, batch_identity="BATCH-1")
    second = build_graph_exports(transactions, matches=matches, batch_identity="BATCH-1")

    first_nodes, first_edges, first_agg, manifest = first
    second_nodes, second_edges, second_agg, _ = second

    assert list(first_nodes.columns) == GRAPH_NODE_COLUMNS
    assert list(first_edges.columns) == GRAPH_EDGE_COLUMNS
    assert list(first_agg.columns) == AGGREGATED_EDGE_COLUMNS
    assert manifest["schema_version"] == "1.3"
    assert manifest["derived_account_edge_columns"]

    assert first_nodes["node_id"].tolist() == second_nodes["node_id"].tolist()
    assert first_edges["edge_id"].tolist() == second_edges["edge_id"].tolist()
    assert first_agg["edge_id"].tolist() == second_agg["edge_id"].tolist()

    assert all(node_id.startswith(("ACCOUNT:", "ENTITY:", "BANK:", "STATEMENT_BATCH:", "TRANSACTION:", "PARTIAL_ACCOUNT:", "CASH:", "UNKNOWN_")) for node_id in first_nodes["node_id"].tolist())
    assert all(edge_id.startswith(("FLOW:", "OWNS:", "APPEARS_IN:", "MATCH:", "FLOW_AGG:")) for edge_id in list(first_edges["edge_id"]) + list(first_agg["edge_id"]))


def test_build_graph_exports_preserves_direction_and_aggregation_safety():
    nodes_df, edges_df, aggregated_df, _ = build_graph_exports(_sample_transactions(), matches=_sample_matches(), batch_identity="BATCH-1")

    flow_edges = edges_df[edges_df["edge_type"].isin(["SENT_TO", "RECEIVED_FROM"])]
    tx_in = flow_edges.loc[flow_edges["transaction_id"] == edges_df.loc[edges_df["reference_no"] == "REF001", "transaction_id"].iloc[0]].iloc[0]
    assert tx_in["from_node_id"] == "ACCOUNT:2222222222"
    assert tx_in["to_node_id"] == "ACCOUNT:1111111111"

    tx_out = flow_edges.loc[flow_edges["reference_no"] == "REF002"].iloc[0]
    assert tx_out["from_node_id"] == "ACCOUNT:1111111111"
    assert tx_out["to_node_id"] == "ACCOUNT:3333333333"

    tx_deposit = flow_edges.loc[flow_edges["reference_no"] == "REF003"].iloc[0]
    assert tx_deposit["from_node_id"] == "CASH:UNSPECIFIED"
    assert tx_deposit["to_node_id"] == "ACCOUNT:1111111111"

    agg = aggregated_df.loc[
        (aggregated_df["from_node_id"] == "ACCOUNT:1111111111")
        & (aggregated_df["to_node_id"] == "ACCOUNT:3333333333")
        & (aggregated_df["edge_type"] == "SENT_TO")
    ].iloc[0]
    assert agg["transaction_count"] == 2
    assert agg["total_amount_signed"] == -750.0
    assert agg["total_amount_abs"] == 750.0

    confirmed_match = edges_df.loc[edges_df["edge_type"] == "MATCHED_TO"].iloc[0]
    assert confirmed_match["assertion_status"] == "manual_confirmed"

    suggested_match = edges_df.loc[edges_df["edge_type"] == "POSSIBLE_SAME_AS"].iloc[0]
    assert suggested_match["assertion_status"] == "system_suggested"
    assert "MATCH-3" not in edges_df["edge_id"].tolist()

    assert set(edges_df["source"]).issubset(set(nodes_df["node_id"]))
    assert set(edges_df["target"]).issubset(set(nodes_df["node_id"]))

    derived_df = build_derived_account_edges(aggregated_df)
    assert set(derived_df["edge_type"]) == {"DERIVED_ACCOUNT_TO_ACCOUNT"}
    assert set(derived_df["from_node_id"]) == {"ACCOUNT:2222222222", "ACCOUNT:1111111111"}
    assert set(derived_df["to_node_id"]) == {"ACCOUNT:1111111111", "ACCOUNT:3333333333"}
    assert derived_df["source_transaction_ids"].astype(str).str.len().min() > 0


def test_build_graph_exports_includes_lineage_fields():
    _, edges_df, _, _ = build_graph_exports(_sample_transactions(), matches=_sample_matches(), batch_identity="BATCH-1")

    flow_edge = edges_df.loc[edges_df["reference_no"] == "REF001"].iloc[0]
    lineage = json.loads(flow_edge["lineage_json"])

    assert flow_edge["file_id"] == "FILE-1"
    assert flow_edge["parser_run_id"] == "RUN-1"
    assert flow_edge["statement_batch_id"] == "BATCH-1"
    assert flow_edge["source_row_number"] == "2"
    assert flow_edge["source_sheet"] == "Sheet1"
    assert flow_edge["source_file"] == "statement.xlsx"
    assert lineage["source_row_number"] == "2"
    assert lineage["sheet"] == "Sheet1"
    assert lineage["source_file"] == "statement.xlsx"


def test_export_anx_from_graph_uses_i2_safe_subset(tmp_path: Path):
    nodes_df, edges_df, _, _ = build_graph_exports(_sample_transactions(), matches=_sample_matches(), batch_identity="BATCH-1")
    output_path = tmp_path / "graph.anx"

    export_anx_from_graph(nodes_df, edges_df, output_path)

    xml_text = output_path.read_text(encoding="utf-8")
    assert "APPEARS_IN" not in xml_text
    assert "Assertion:manual_confirmed" in xml_text
    assert "Assertion:system_suggested" in xml_text

    root = ET.parse(output_path).getroot()
    chart_items = root.findall(".//ChartItem")
    assert chart_items
