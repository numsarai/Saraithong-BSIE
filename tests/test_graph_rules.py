from __future__ import annotations

import json

import pandas as pd

from core.graph_domain import DERIVED_ACCOUNT_EDGE_COLUMNS
from core.graph_rules import DEFAULT_RULE_CONFIG, run_graph_rules


def _only(rule_name: str, overrides: dict) -> dict:
    config = {name: {"enabled": False} for name in DEFAULT_RULE_CONFIG}
    config[rule_name] = {"enabled": True, **overrides}
    return config


def _derived_edges(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=DERIVED_ACCOUNT_EDGE_COLUMNS).fillna("")


def _base_edge(
    *,
    edge_id: str,
    from_node_id: str,
    to_node_id: str,
    transaction_count: int,
    total_amount_abs: float,
    confidence_score_avg: float = 0.9,
    source_transaction_ids: str = "TX-1|TX-2|TX-3",
    statement_batch_id: str = "BATCH-1",
    parser_run_id: str = "RUN-1",
    file_id: str = "FILE-1",
    source_row_numbers: str = "2|3|4",
    source_sheets: str = "Sheet1",
    source_files: str = "statement.xlsx",
    date_range: str = "01 03 2026 | 02 03 2026",
) -> dict:
    return {
        "id": edge_id,
        "edge_id": edge_id,
        "source": from_node_id,
        "from_node_id": from_node_id,
        "target": to_node_id,
        "to_node_id": to_node_id,
        "label": "Account to Account Flow",
        "type": "DERIVED_ACCOUNT_TO_ACCOUNT",
        "edge_type": "DERIVED_ACCOUNT_TO_ACCOUNT",
        "aggregation_level": "derived_account",
        "directionality": "directed",
        "transaction_count": transaction_count,
        "total_amount_signed": total_amount_abs,
        "total_amount_abs": total_amount_abs,
        "total_amount_display": f"{int(total_amount_abs):,}",
        "currency": "THB",
        "date_range": date_range,
        "confidence_score_avg": confidence_score_avg,
        "confidence_score_min": confidence_score_avg,
        "confidence_score_max": confidence_score_avg,
        "review_status": "pending",
        "assertion_status": "derived_from_statement_flow",
        "source_transaction_ids": source_transaction_ids,
        "statement_batch_id": statement_batch_id,
        "parser_run_id": parser_run_id,
        "file_id": file_id,
        "source_row_numbers": source_row_numbers,
        "source_sheets": source_sheets,
        "source_files": source_files,
        "lineage_json": json.dumps({"source_transaction_ids": source_transaction_ids.split("|")}),
    }


def _business_nodes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"node_id": "ACCOUNT:1111111111", "label": "A", "node_type": "Account", "review_status": "pending"},
            {"node_id": "ACCOUNT:2222222222", "label": "B", "node_type": "Account", "review_status": "pending"},
            {"node_id": "ACCOUNT:3333333333", "label": "C", "node_type": "Account", "review_status": "pending"},
            {"node_id": "ACCOUNT:4444444444", "label": "D", "node_type": "Account", "review_status": "pending"},
        ]
    )


def _top_nodes() -> list[dict]:
    return [
        {
            "node_id": "ACCOUNT:1111111111",
            "label": "A",
            "node_type": "Account",
            "degree": 7,
            "in_degree": 3,
            "out_degree": 4,
            "total_flow_value": 15000.0,
            "source_transaction_ids": "TX-1|TX-2|TX-3",
            "statement_batch_ids": "BATCH-1",
            "parser_run_ids": "RUN-1",
            "file_ids": "FILE-1",
            "source_row_numbers": "2|3|4",
            "source_sheets": "Sheet1",
            "source_files": "statement.xlsx",
            "review_status": "pending",
        }
    ]


def _tx_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "transaction_id": "TX-1",
                "subject_account": "1111111111",
                "counterparty_account": "2222222222",
                "counterparty_name": "Alice",
                "date": "2026-03-01",
                "statement_batch_id": "BATCH-1",
                "parser_run_id": "RUN-1",
                "file_id": "FILE-1",
                "row_number": "2",
                "source_sheet": "Sheet1",
                "source_file": "statement.xlsx",
            },
            {
                "transaction_id": "TX-2",
                "subject_account": "1111111111",
                "counterparty_account": "2222222222",
                "counterparty_name": "Alice",
                "date": "2026-03-02",
                "statement_batch_id": "BATCH-1",
                "parser_run_id": "RUN-1",
                "file_id": "FILE-1",
                "row_number": "3",
                "source_sheet": "Sheet1",
                "source_file": "statement.xlsx",
            },
            {
                "transaction_id": "TX-3",
                "subject_account": "1111111111",
                "counterparty_account": "2222222222",
                "counterparty_name": "Alice",
                "date": "2026-03-03",
                "statement_batch_id": "BATCH-1",
                "parser_run_id": "RUN-1",
                "file_id": "FILE-1",
                "row_number": "4",
                "source_sheet": "Sheet1",
                "source_file": "statement.xlsx",
            },
        ]
    )


def test_repeated_transfers_rule_flags_repeated_account_path():
    findings = run_graph_rules(
        tx_df=pd.DataFrame(),
        business_nodes_df=_business_nodes(),
        derived_account_edges_df=_derived_edges([
            _base_edge(edge_id="DER-1", from_node_id="ACCOUNT:1111111111", to_node_id="ACCOUNT:2222222222", transaction_count=3, total_amount_abs=1200.0)
        ]),
        top_nodes=[],
        config_overrides=_only("repeated_transfers", {"min_transaction_count": 3, "min_total_amount_abs": 1000.0}),
    )["findings"]
    assert findings[0]["rule_type"] == "repeated_transfers"


def test_fan_in_accounts_rule_flags_multi_source_receiver():
    findings = run_graph_rules(
        tx_df=pd.DataFrame(),
        business_nodes_df=_business_nodes(),
        derived_account_edges_df=_derived_edges([
            _base_edge(edge_id="DER-1", from_node_id="ACCOUNT:1111111111", to_node_id="ACCOUNT:4444444444", transaction_count=3, total_amount_abs=3000.0, source_transaction_ids="A1|A2|A3"),
            _base_edge(edge_id="DER-2", from_node_id="ACCOUNT:2222222222", to_node_id="ACCOUNT:4444444444", transaction_count=2, total_amount_abs=2500.0, source_transaction_ids="B1|B2"),
            _base_edge(edge_id="DER-3", from_node_id="ACCOUNT:3333333333", to_node_id="ACCOUNT:4444444444", transaction_count=2, total_amount_abs=2200.0, source_transaction_ids="C1|C2"),
        ]),
        top_nodes=[],
        config_overrides=_only("fan_in_accounts", {"min_inbound_transactions": 5, "min_unique_sources": 3, "min_total_in_value": 5000.0}),
    )["findings"]
    assert findings[0]["rule_type"] == "fan_in_accounts"


def test_fan_out_accounts_rule_flags_multi_target_sender():
    findings = run_graph_rules(
        tx_df=pd.DataFrame(),
        business_nodes_df=_business_nodes(),
        derived_account_edges_df=_derived_edges([
            _base_edge(edge_id="DER-1", from_node_id="ACCOUNT:1111111111", to_node_id="ACCOUNT:2222222222", transaction_count=2, total_amount_abs=2500.0, source_transaction_ids="A1|A2"),
            _base_edge(edge_id="DER-2", from_node_id="ACCOUNT:1111111111", to_node_id="ACCOUNT:3333333333", transaction_count=2, total_amount_abs=2400.0, source_transaction_ids="B1|B2"),
            _base_edge(edge_id="DER-3", from_node_id="ACCOUNT:1111111111", to_node_id="ACCOUNT:4444444444", transaction_count=2, total_amount_abs=2300.0, source_transaction_ids="C1|C2"),
        ]),
        top_nodes=[],
        config_overrides=_only("fan_out_accounts", {"min_outbound_transactions": 5, "min_unique_targets": 3, "min_total_out_value": 5000.0}),
    )["findings"]
    assert findings[0]["rule_type"] == "fan_out_accounts"


def test_circular_paths_rule_flags_reciprocal_flows():
    findings = run_graph_rules(
        tx_df=pd.DataFrame(),
        business_nodes_df=_business_nodes(),
        derived_account_edges_df=_derived_edges([
            _base_edge(edge_id="DER-1", from_node_id="ACCOUNT:1111111111", to_node_id="ACCOUNT:2222222222", transaction_count=2, total_amount_abs=3000.0, source_transaction_ids="A1|A2"),
            _base_edge(edge_id="DER-2", from_node_id="ACCOUNT:2222222222", to_node_id="ACCOUNT:1111111111", transaction_count=2, total_amount_abs=2800.0, source_transaction_ids="B1|B2"),
        ]),
        top_nodes=[],
        config_overrides=_only("circular_paths", {"min_edge_transaction_count": 2, "min_combined_transactions": 4, "min_total_cycle_value": 5000.0}),
    )["findings"]
    assert findings[0]["rule_type"] == "circular_paths"


def test_pass_through_behavior_rule_flags_balanced_in_and_out():
    findings = run_graph_rules(
        tx_df=pd.DataFrame(),
        business_nodes_df=_business_nodes(),
        derived_account_edges_df=_derived_edges([
            _base_edge(edge_id="DER-1", from_node_id="ACCOUNT:2222222222", to_node_id="ACCOUNT:1111111111", transaction_count=3, total_amount_abs=5000.0, source_transaction_ids="A1|A2|A3"),
            _base_edge(edge_id="DER-2", from_node_id="ACCOUNT:3333333333", to_node_id="ACCOUNT:1111111111", transaction_count=2, total_amount_abs=4500.0, source_transaction_ids="B1|B2"),
            _base_edge(edge_id="DER-3", from_node_id="ACCOUNT:1111111111", to_node_id="ACCOUNT:4444444444", transaction_count=3, total_amount_abs=4800.0, source_transaction_ids="C1|C2|C3"),
            _base_edge(edge_id="DER-4", from_node_id="ACCOUNT:1111111111", to_node_id="ACCOUNT:5555555555", transaction_count=2, total_amount_abs=4300.0, source_transaction_ids="D1|D2"),
        ]),
        top_nodes=[],
        config_overrides=_only("pass_through_behavior", {"min_inbound_transactions": 5, "min_outbound_transactions": 5, "min_total_flow_value": 10000.0, "max_flow_gap_ratio": 0.25, "min_unique_sources": 2, "min_unique_targets": 2}),
    )["findings"]
    assert findings[0]["rule_type"] == "pass_through_behavior"


def test_high_degree_hubs_rule_flags_central_node():
    findings = run_graph_rules(
        tx_df=pd.DataFrame(),
        business_nodes_df=_business_nodes(),
        derived_account_edges_df=_derived_edges([]),
        top_nodes=_top_nodes(),
        config_overrides=_only("high_degree_hubs", {"min_degree": 6, "min_total_flow_value": 10000.0}),
    )["findings"]
    assert findings[0]["rule_type"] == "high_degree_hubs"


def test_repeated_counterparties_rule_flags_repeated_counterparty_activity():
    findings = run_graph_rules(
        tx_df=_tx_df(),
        business_nodes_df=_business_nodes(),
        derived_account_edges_df=_derived_edges([]),
        top_nodes=[],
        config_overrides=_only("repeated_counterparties", {"min_transaction_count": 3, "min_unique_days": 2}),
    )["findings"]
    assert findings[0]["rule_type"] == "repeated_counterparties"
    assert "transaction_ids" in findings[0]
    assert "traceability_json" in findings[0]

