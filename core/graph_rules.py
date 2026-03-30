"""
graph_rules.py
--------------
Reusable suspicious-analytics rule engine for BSIE graph analysis.

The rule engine consumes finalized BSIE graph outputs, not parser internals.
It is deterministic, threshold-driven, and preserves traceability back to
transactions, source rows, files, parser runs, and statement batches.
"""

from __future__ import annotations

import json
import hashlib
from collections import Counter, defaultdict
from copy import deepcopy
from typing import Any

import pandas as pd


RULE_CONFIG_VERSION = "1.0"

DEFAULT_RULE_CONFIG: dict[str, dict[str, Any]] = {
    "repeated_transfers": {
        "enabled": True,
        "min_transaction_count": 3,
        "min_total_amount_abs": 1000.0,
        "min_avg_confidence": 0.70,
        "severity": "medium",
    },
    "fan_in_accounts": {
        "enabled": True,
        "min_inbound_transactions": 5,
        "min_unique_sources": 3,
        "min_total_in_value": 5000.0,
        "severity": "high",
    },
    "fan_out_accounts": {
        "enabled": True,
        "min_outbound_transactions": 5,
        "min_unique_targets": 3,
        "min_total_out_value": 5000.0,
        "severity": "high",
    },
    "circular_paths": {
        "enabled": True,
        "min_edge_transaction_count": 2,
        "min_combined_transactions": 4,
        "min_total_cycle_value": 5000.0,
        "severity": "high",
    },
    "pass_through_behavior": {
        "enabled": True,
        "min_inbound_transactions": 3,
        "min_outbound_transactions": 3,
        "min_total_flow_value": 5000.0,
        "max_flow_gap_ratio": 0.25,
        "min_unique_sources": 2,
        "min_unique_targets": 2,
        "severity": "high",
    },
    "high_degree_hubs": {
        "enabled": True,
        "min_degree": 6,
        "min_total_flow_value": 10000.0,
        "severity": "medium",
    },
    "repeated_counterparties": {
        "enabled": True,
        "min_transaction_count": 4,
        "min_unique_days": 2,
        "severity": "medium",
    },
}


def _string(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"", "none", "nan", "nat"} else text


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _split_pipe(value: object) -> set[str]:
    if value in ("", None):
        return set()
    return {part.strip() for part in str(value).split("|") if part.strip()}


def _stable_join(values: set[str] | list[str]) -> str:
    return "|".join(sorted({value for value in values if value}))


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def get_rule_config(overrides: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    config = deepcopy(DEFAULT_RULE_CONFIG)
    if not overrides:
        return config
    for rule_name, values in overrides.items():
        if rule_name not in config or not isinstance(values, dict):
            continue
        config[rule_name].update(values)
    return config


def _severity_rank(severity: str) -> int:
    return {"critical": 3, "high": 2, "medium": 1, "low": 0}.get(str(severity or "").lower(), 0)


def _make_finding(
    *,
    rule_type: str,
    severity: str,
    confidence_score: float,
    summary: str,
    reason: str,
    subject_node_ids: list[str],
    subject_edge_ids: list[str],
    transaction_ids: list[str],
    statement_batch_ids: list[str],
    parser_run_ids: list[str],
    file_ids: list[str],
    source_row_numbers: list[str],
    source_sheets: list[str],
    source_files: list[str],
    reason_codes: list[str],
    evidence: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    stable_raw = "|".join(
        [
            rule_type,
            *sorted(subject_node_ids),
            *sorted(subject_edge_ids),
            *sorted(transaction_ids),
        ]
    )
    finding_id = f"FINDING:{rule_type}:{hashlib.sha1(stable_raw.encode('utf-8')).hexdigest()[:16].upper()}"
    traceability = {
        "file_ids": sorted({value for value in file_ids if value}),
        "parser_run_ids": sorted({value for value in parser_run_ids if value}),
        "statement_batch_ids": sorted({value for value in statement_batch_ids if value}),
        "transaction_ids": sorted({value for value in transaction_ids if value}),
        "source_row_numbers": sorted({value for value in source_row_numbers if value}),
        "source_sheets": sorted({value for value in source_sheets if value}),
        "source_files": sorted({value for value in source_files if value}),
    }
    return {
        "finding_id": finding_id,
        "rule_type": rule_type,
        "severity": severity,
        "confidence_score": round(confidence_score, 4),
        "subject_node_ids": _stable_join(subject_node_ids),
        "subject_edge_ids": _stable_join(subject_edge_ids),
        "transaction_ids": _stable_join(transaction_ids),
        "statement_batch_ids": _stable_join(statement_batch_ids),
        "parser_run_ids": _stable_join(parser_run_ids),
        "file_ids": _stable_join(file_ids),
        "source_row_numbers": _stable_join(source_row_numbers),
        "source_sheets": _stable_join(source_sheets),
        "source_files": _stable_join(source_files),
        "summary": summary,
        "reason": reason,
        "reason_codes": _stable_join(reason_codes),
        "evidence_json": _json_text(evidence),
        "thresholds_json": _json_text(thresholds),
        "traceability_json": _json_text(traceability),
    }


def _account_flow_groups(derived_edges_df: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in derived_edges_df.fillna("").iterrows():
        rows.append(
            {
                "edge_id": _string(row.get("edge_id")),
                "from_node_id": _string(row.get("from_node_id")),
                "to_node_id": _string(row.get("to_node_id")),
                "transaction_count": _int(row.get("transaction_count")),
                "total_amount_abs": _float(row.get("total_amount_abs")),
                "confidence_score_avg": _float(row.get("confidence_score_avg")),
                "review_status": _string(row.get("review_status")),
                "source_transaction_ids": _split_pipe(row.get("source_transaction_ids")),
                "statement_batch_ids": _split_pipe(row.get("statement_batch_id")),
                "parser_run_ids": _split_pipe(row.get("parser_run_id")),
                "file_ids": _split_pipe(row.get("file_id")),
                "source_row_numbers": _split_pipe(row.get("source_row_numbers")),
                "source_sheets": _split_pipe(row.get("source_sheets")),
                "source_files": _split_pipe(row.get("source_files")),
                "date_range": _string(row.get("date_range")),
            }
        )
    return rows


def _rule_repeated_transfers(derived_edges_df: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in _account_flow_groups(derived_edges_df):
        if row["transaction_count"] < int(config["min_transaction_count"]):
            continue
        if row["total_amount_abs"] < float(config["min_total_amount_abs"]):
            continue
        if row["confidence_score_avg"] < float(config["min_avg_confidence"]):
            continue
        findings.append(
            _make_finding(
                rule_type="repeated_transfers",
                severity=str(config["severity"]),
                confidence_score=min(0.99, 0.6 + min(row["transaction_count"], 10) * 0.03),
                summary=f"Repeated transfers between {row['from_node_id']} and {row['to_node_id']}",
                reason="The same account-to-account path repeats above the configured transaction threshold.",
                subject_node_ids=[row["from_node_id"], row["to_node_id"]],
                subject_edge_ids=[row["edge_id"]],
                transaction_ids=sorted(row["source_transaction_ids"]),
                statement_batch_ids=sorted(row["statement_batch_ids"]),
                parser_run_ids=sorted(row["parser_run_ids"]),
                file_ids=sorted(row["file_ids"]),
                source_row_numbers=sorted(row["source_row_numbers"]),
                source_sheets=sorted(row["source_sheets"]),
                source_files=sorted(row["source_files"]),
                reason_codes=["repeated_path", "account_to_account"],
                evidence={
                    "transaction_count": row["transaction_count"],
                    "total_amount_abs": row["total_amount_abs"],
                    "date_range": row["date_range"],
                },
                thresholds=config,
            )
        )
    return findings


def _rule_fan_in_accounts(derived_edges_df: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "total": 0.0, "sources": set(), "edges": set(), "tx": set(), "batches": set(), "runs": set(), "files": set(), "rows": set(), "sheets": set(), "source_files": set()})
    for row in _account_flow_groups(derived_edges_df):
        bucket = groups[row["to_node_id"]]
        bucket["count"] += row["transaction_count"]
        bucket["total"] += row["total_amount_abs"]
        bucket["sources"].add(row["from_node_id"])
        bucket["edges"].add(row["edge_id"])
        bucket["tx"].update(row["source_transaction_ids"])
        bucket["batches"].update(row["statement_batch_ids"])
        bucket["runs"].update(row["parser_run_ids"])
        bucket["files"].update(row["file_ids"])
        bucket["rows"].update(row["source_row_numbers"])
        bucket["sheets"].update(row["source_sheets"])
        bucket["source_files"].update(row["source_files"])

    findings: list[dict[str, Any]] = []
    for node_id, bucket in groups.items():
        if bucket["count"] < int(config["min_inbound_transactions"]):
            continue
        if len(bucket["sources"]) < int(config["min_unique_sources"]):
            continue
        if bucket["total"] < float(config["min_total_in_value"]):
            continue
        findings.append(
            _make_finding(
                rule_type="fan_in_accounts",
                severity=str(config["severity"]),
                confidence_score=min(0.99, 0.65 + min(bucket["count"], 10) * 0.025),
                summary=f"High fan-in into {node_id}",
                reason="The account receives many transactions from multiple distinct source accounts.",
                subject_node_ids=[node_id, *sorted(bucket["sources"])],
                subject_edge_ids=sorted(bucket["edges"]),
                transaction_ids=sorted(bucket["tx"]),
                statement_batch_ids=sorted(bucket["batches"]),
                parser_run_ids=sorted(bucket["runs"]),
                file_ids=sorted(bucket["files"]),
                source_row_numbers=sorted(bucket["rows"]),
                source_sheets=sorted(bucket["sheets"]),
                source_files=sorted(bucket["source_files"]),
                reason_codes=["fan_in", "multi_source"],
                evidence={
                    "inbound_transaction_count": bucket["count"],
                    "unique_sources": len(bucket["sources"]),
                    "total_in_value": round(bucket["total"], 2),
                },
                thresholds=config,
            )
        )
    return findings


def _rule_fan_out_accounts(derived_edges_df: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "total": 0.0, "targets": set(), "edges": set(), "tx": set(), "batches": set(), "runs": set(), "files": set(), "rows": set(), "sheets": set(), "source_files": set()})
    for row in _account_flow_groups(derived_edges_df):
        bucket = groups[row["from_node_id"]]
        bucket["count"] += row["transaction_count"]
        bucket["total"] += row["total_amount_abs"]
        bucket["targets"].add(row["to_node_id"])
        bucket["edges"].add(row["edge_id"])
        bucket["tx"].update(row["source_transaction_ids"])
        bucket["batches"].update(row["statement_batch_ids"])
        bucket["runs"].update(row["parser_run_ids"])
        bucket["files"].update(row["file_ids"])
        bucket["rows"].update(row["source_row_numbers"])
        bucket["sheets"].update(row["source_sheets"])
        bucket["source_files"].update(row["source_files"])

    findings: list[dict[str, Any]] = []
    for node_id, bucket in groups.items():
        if bucket["count"] < int(config["min_outbound_transactions"]):
            continue
        if len(bucket["targets"]) < int(config["min_unique_targets"]):
            continue
        if bucket["total"] < float(config["min_total_out_value"]):
            continue
        findings.append(
            _make_finding(
                rule_type="fan_out_accounts",
                severity=str(config["severity"]),
                confidence_score=min(0.99, 0.65 + min(bucket["count"], 10) * 0.025),
                summary=f"High fan-out from {node_id}",
                reason="The account sends many transactions to multiple distinct target accounts.",
                subject_node_ids=[node_id, *sorted(bucket["targets"])],
                subject_edge_ids=sorted(bucket["edges"]),
                transaction_ids=sorted(bucket["tx"]),
                statement_batch_ids=sorted(bucket["batches"]),
                parser_run_ids=sorted(bucket["runs"]),
                file_ids=sorted(bucket["files"]),
                source_row_numbers=sorted(bucket["rows"]),
                source_sheets=sorted(bucket["sheets"]),
                source_files=sorted(bucket["source_files"]),
                reason_codes=["fan_out", "multi_target"],
                evidence={
                    "outbound_transaction_count": bucket["count"],
                    "unique_targets": len(bucket["targets"]),
                    "total_out_value": round(bucket["total"], 2),
                },
                thresholds=config,
            )
        )
    return findings


def _rule_circular_paths(derived_edges_df: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _account_flow_groups(derived_edges_df)
    pair_map = {(row["from_node_id"], row["to_node_id"]): row for row in rows}
    findings: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for (left, right), forward in pair_map.items():
        reverse_key = (right, left)
        if reverse_key not in pair_map:
            continue
        pair_key = tuple(sorted((left, right)))
        if pair_key in seen_pairs:
            continue
        reverse = pair_map[reverse_key]
        seen_pairs.add(pair_key)
        if forward["transaction_count"] < int(config["min_edge_transaction_count"]):
            continue
        if reverse["transaction_count"] < int(config["min_edge_transaction_count"]):
            continue
        combined_count = forward["transaction_count"] + reverse["transaction_count"]
        combined_value = forward["total_amount_abs"] + reverse["total_amount_abs"]
        if combined_count < int(config["min_combined_transactions"]):
            continue
        if combined_value < float(config["min_total_cycle_value"]):
            continue
        findings.append(
            _make_finding(
                rule_type="circular_paths",
                severity=str(config["severity"]),
                confidence_score=min(0.99, 0.7 + min(combined_count, 10) * 0.02),
                summary=f"Circular path detected between {left} and {right}",
                reason="The same pair of accounts shows repeated flow in both directions.",
                subject_node_ids=[left, right],
                subject_edge_ids=[forward["edge_id"], reverse["edge_id"]],
                transaction_ids=sorted(forward["source_transaction_ids"] | reverse["source_transaction_ids"]),
                statement_batch_ids=sorted(forward["statement_batch_ids"] | reverse["statement_batch_ids"]),
                parser_run_ids=sorted(forward["parser_run_ids"] | reverse["parser_run_ids"]),
                file_ids=sorted(forward["file_ids"] | reverse["file_ids"]),
                source_row_numbers=sorted(forward["source_row_numbers"] | reverse["source_row_numbers"]),
                source_sheets=sorted(forward["source_sheets"] | reverse["source_sheets"]),
                source_files=sorted(forward["source_files"] | reverse["source_files"]),
                reason_codes=["circular_flow", "reciprocal_edges"],
                evidence={
                    "forward_transaction_count": forward["transaction_count"],
                    "reverse_transaction_count": reverse["transaction_count"],
                    "combined_transaction_count": combined_count,
                    "combined_total_value": round(combined_value, 2),
                },
                thresholds=config,
            )
        )
    return findings


def _rule_pass_through_behavior(derived_edges_df: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    inbound: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "total": 0.0, "sources": set(), "edges": set(), "tx": set(), "batches": set(), "runs": set(), "files": set(), "rows": set(), "sheets": set(), "source_files": set()})
    outbound: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "total": 0.0, "targets": set(), "edges": set(), "tx": set(), "batches": set(), "runs": set(), "files": set(), "rows": set(), "sheets": set(), "source_files": set()})

    for row in _account_flow_groups(derived_edges_df):
        in_bucket = inbound[row["to_node_id"]]
        in_bucket["count"] += row["transaction_count"]
        in_bucket["total"] += row["total_amount_abs"]
        in_bucket["sources"].add(row["from_node_id"])
        in_bucket["edges"].add(row["edge_id"])
        in_bucket["tx"].update(row["source_transaction_ids"])
        in_bucket["batches"].update(row["statement_batch_ids"])
        in_bucket["runs"].update(row["parser_run_ids"])
        in_bucket["files"].update(row["file_ids"])
        in_bucket["rows"].update(row["source_row_numbers"])
        in_bucket["sheets"].update(row["source_sheets"])
        in_bucket["source_files"].update(row["source_files"])

        out_bucket = outbound[row["from_node_id"]]
        out_bucket["count"] += row["transaction_count"]
        out_bucket["total"] += row["total_amount_abs"]
        out_bucket["targets"].add(row["to_node_id"])
        out_bucket["edges"].add(row["edge_id"])
        out_bucket["tx"].update(row["source_transaction_ids"])
        out_bucket["batches"].update(row["statement_batch_ids"])
        out_bucket["runs"].update(row["parser_run_ids"])
        out_bucket["files"].update(row["file_ids"])
        out_bucket["rows"].update(row["source_row_numbers"])
        out_bucket["sheets"].update(row["source_sheets"])
        out_bucket["source_files"].update(row["source_files"])

    findings: list[dict[str, Any]] = []
    candidate_nodes = sorted(set(inbound) & set(outbound))
    for node_id in candidate_nodes:
        incoming = inbound[node_id]
        outgoing = outbound[node_id]
        if incoming["count"] < int(config["min_inbound_transactions"]):
            continue
        if outgoing["count"] < int(config["min_outbound_transactions"]):
            continue
        if len(incoming["sources"]) < int(config["min_unique_sources"]):
            continue
        if len(outgoing["targets"]) < int(config["min_unique_targets"]):
            continue
        total_flow = incoming["total"] + outgoing["total"]
        if total_flow < float(config["min_total_flow_value"]):
            continue
        max_total = max(incoming["total"], outgoing["total"], 1.0)
        gap_ratio = abs(incoming["total"] - outgoing["total"]) / max_total
        if gap_ratio > float(config["max_flow_gap_ratio"]):
            continue
        findings.append(
            _make_finding(
                rule_type="pass_through_behavior",
                severity=str(config["severity"]),
                confidence_score=min(0.99, 0.72 + min(incoming["count"] + outgoing["count"], 12) * 0.015),
                summary=f"Possible pass-through behavior on {node_id}",
                reason="Inbound and outbound account flow are both high and closely balanced, suggesting rapid relay behavior.",
                subject_node_ids=[node_id, *sorted(incoming["sources"]), *sorted(outgoing["targets"])],
                subject_edge_ids=sorted(incoming["edges"] | outgoing["edges"]),
                transaction_ids=sorted(incoming["tx"] | outgoing["tx"]),
                statement_batch_ids=sorted(incoming["batches"] | outgoing["batches"]),
                parser_run_ids=sorted(incoming["runs"] | outgoing["runs"]),
                file_ids=sorted(incoming["files"] | outgoing["files"]),
                source_row_numbers=sorted(incoming["rows"] | outgoing["rows"]),
                source_sheets=sorted(incoming["sheets"] | outgoing["sheets"]),
                source_files=sorted(incoming["source_files"] | outgoing["source_files"]),
                reason_codes=["pass_through", "balanced_in_out"],
                evidence={
                    "inbound_transactions": incoming["count"],
                    "outbound_transactions": outgoing["count"],
                    "incoming_total": round(incoming["total"], 2),
                    "outgoing_total": round(outgoing["total"], 2),
                    "flow_gap_ratio": round(gap_ratio, 4),
                },
                thresholds=config,
            )
        )
    return findings


def _rule_high_degree_hubs(business_nodes_df: pd.DataFrame, top_nodes: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    node_lookup = {str(row.get("node_id", "")): row for row in business_nodes_df.fillna("").to_dict(orient="records")}
    for row in top_nodes:
        if row["node_type"] not in {"Account", "Entity", "PartialAccount", "Unknown"}:
            continue
        if int(row["degree"]) < int(config["min_degree"]):
            continue
        if float(row["total_flow_value"]) < float(config["min_total_flow_value"]):
            continue
        node_meta = node_lookup.get(row["node_id"], {})
        findings.append(
            _make_finding(
                rule_type="high_degree_hubs",
                severity=str(config["severity"]),
                confidence_score=min(0.99, 0.6 + min(int(row["degree"]), 12) * 0.025),
                summary=f"High-degree hub detected at {row['node_id']}",
                reason="This node connects to many other business nodes and carries significant flow value.",
                subject_node_ids=[row["node_id"]],
                subject_edge_ids=[],
                transaction_ids=sorted(_split_pipe(row.get("source_transaction_ids", ""))),
                statement_batch_ids=sorted(_split_pipe(row.get("statement_batch_ids", ""))),
                parser_run_ids=sorted(_split_pipe(row.get("parser_run_ids", ""))),
                file_ids=sorted(_split_pipe(row.get("file_ids", ""))),
                source_row_numbers=sorted(_split_pipe(row.get("source_row_numbers", ""))),
                source_sheets=sorted(_split_pipe(row.get("source_sheets", ""))),
                source_files=sorted(_split_pipe(row.get("source_files", ""))),
                reason_codes=["high_degree_hub"],
                evidence={
                    "degree": int(row["degree"]),
                    "in_degree": int(row["in_degree"]),
                    "out_degree": int(row["out_degree"]),
                    "total_flow_value": float(row["total_flow_value"]),
                    "node_label": row["label"],
                    "node_type": row["node_type"],
                    "review_status": _string(node_meta.get("review_status", row.get("review_status", ""))),
                },
                thresholds=config,
            )
        )
    return findings


def _rule_repeated_counterparties(tx_df: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    if tx_df.empty:
        return []
    findings: list[dict[str, Any]] = []
    groups: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"count": 0, "days": set(), "tx": set(), "batches": set(), "runs": set(), "files": set(), "rows": set(), "sheets": set(), "source_files": set()})
    for _, row in tx_df.fillna("").iterrows():
        subject_account = _string(row.get("subject_account", ""))
        counterparty_key = _string(row.get("counterparty_account", "")) or _string(row.get("counterparty_name", ""))
        if not (subject_account and counterparty_key):
            continue
        key = (subject_account, counterparty_key)
        bucket = groups[key]
        bucket["count"] += 1
        bucket["days"].add(_string(row.get("date", "")))
        tx_id = _string(row.get("transaction_id", "")) or _string(row.get("db_transaction_id", ""))
        if tx_id:
            bucket["tx"].add(tx_id)
        bucket["batches"].update(_split_pipe(row.get("statement_batch_id", "")))
        bucket["runs"].update(_split_pipe(row.get("parser_run_id", "")))
        bucket["files"].update(_split_pipe(row.get("file_id", "")))
        bucket["rows"].update(_split_pipe(row.get("row_number", "")))
        bucket["sheets"].update(_split_pipe(row.get("source_sheet", "")))
        bucket["source_files"].update(_split_pipe(row.get("source_file", "")))

    for (subject_account, counterparty_key), bucket in groups.items():
        if bucket["count"] < int(config["min_transaction_count"]):
            continue
        if len({day for day in bucket["days"] if day}) < int(config["min_unique_days"]):
            continue
        findings.append(
            _make_finding(
                rule_type="repeated_counterparties",
                severity=str(config["severity"]),
                confidence_score=min(0.99, 0.58 + min(bucket["count"], 10) * 0.03),
                summary=f"Repeated counterparty activity between {subject_account} and {counterparty_key}",
                reason="The same subject account interacts with the same counterparty repeatedly across multiple days.",
                subject_node_ids=[f"ACCOUNT:{subject_account}"],
                subject_edge_ids=[],
                transaction_ids=sorted(bucket["tx"]),
                statement_batch_ids=sorted(bucket["batches"]),
                parser_run_ids=sorted(bucket["runs"]),
                file_ids=sorted(bucket["files"]),
                source_row_numbers=sorted(bucket["rows"]),
                source_sheets=sorted(bucket["sheets"]),
                source_files=sorted(bucket["source_files"]),
                reason_codes=["repeated_counterparty"],
                evidence={
                    "subject_account": subject_account,
                    "counterparty_key": counterparty_key,
                    "transaction_count": bucket["count"],
                    "unique_days": len({day for day in bucket["days"] if day}),
                },
                thresholds=config,
            )
        )
    return findings


def run_graph_rules(
    *,
    tx_df: pd.DataFrame,
    business_nodes_df: pd.DataFrame,
    derived_account_edges_df: pd.DataFrame,
    top_nodes: list[dict[str, Any]],
    config_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = get_rule_config(config_overrides)
    findings: list[dict[str, Any]] = []

    if config["repeated_transfers"]["enabled"]:
        findings.extend(_rule_repeated_transfers(derived_account_edges_df, config["repeated_transfers"]))
    if config["fan_in_accounts"]["enabled"]:
        findings.extend(_rule_fan_in_accounts(derived_account_edges_df, config["fan_in_accounts"]))
    if config["fan_out_accounts"]["enabled"]:
        findings.extend(_rule_fan_out_accounts(derived_account_edges_df, config["fan_out_accounts"]))
    if config["circular_paths"]["enabled"]:
        findings.extend(_rule_circular_paths(derived_account_edges_df, config["circular_paths"]))
    if config["pass_through_behavior"]["enabled"]:
        findings.extend(_rule_pass_through_behavior(derived_account_edges_df, config["pass_through_behavior"]))
    if config["high_degree_hubs"]["enabled"]:
        findings.extend(_rule_high_degree_hubs(business_nodes_df, top_nodes, config["high_degree_hubs"]))
    if config["repeated_counterparties"]["enabled"]:
        findings.extend(_rule_repeated_counterparties(tx_df, config["repeated_counterparties"]))

    findings = sorted(
        findings,
        key=lambda item: (
            -_severity_rank(item["severity"]),
            -float(item["confidence_score"]),
            item["rule_type"],
            item["finding_id"],
        ),
    )

    counts_by_rule = Counter(row["rule_type"] for row in findings)
    counts_by_severity = Counter(row["severity"] for row in findings)
    summary = {
        "total_findings": len(findings),
        "counts_by_rule": [{"rule_type": key, "count": int(value)} for key, value in sorted(counts_by_rule.items())],
        "counts_by_severity": [{"severity": key, "count": int(value)} for key, value in sorted(counts_by_severity.items(), key=lambda item: (-_severity_rank(item[0]), item[0]))],
        "highest_severity": max((row["severity"] for row in findings), key=_severity_rank, default=""),
    }
    return {
        "config_version": RULE_CONFIG_VERSION,
        "config": config,
        "summary": summary,
        "findings": findings,
    }
