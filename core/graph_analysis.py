"""
graph_analysis.py
-----------------
Reusable BSIE graph-analysis helpers built on top of normalized transactions.

Pipeline position:
raw import -> parsing -> mapping -> normalization -> validation
-> existing BSIE structured output -> graph modeling -> graph analytics -> export/API/UI

This module intentionally reuses the deterministic graph model from
`core.graph_export` so analytics, CSV export, ANX export, API responses, and UI
all speak the same graph language.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from core.graph_export import build_derived_account_edges
from core.graph_export import build_graph_exports
from core.graph_rules import run_graph_rules


GRAPH_ANALYSIS_JSON = "graph_analysis.json"
GRAPH_ANALYSIS_XLSX = "graph_analysis.xlsx"
SUSPICIOUS_FINDINGS_CSV = "suspicious_findings.csv"
SUSPICIOUS_FINDINGS_JSON = "suspicious_findings.json"
ANALYSIS_SCHEMA_VERSION = "1.0"
EXCLUDED_ANALYSIS_NODE_TYPES = {"Transaction", "StatementBatch"}
IGNORED_COMPONENT_EDGE_TYPES = {"APPEARS_IN"}


def _string(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"", "nan", "none", "nat"} else text


def _float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _split_pipe(value: object) -> set[str]:
    if value in ("", None):
        return set()
    return {part.strip() for part in str(value).split("|") if part.strip()}


def _stable_join(values: set[str] | list[str]) -> str:
    return "|".join(sorted({value for value in values if value}))


def _json_dict(value: object) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _business_nodes(nodes_df: pd.DataFrame) -> pd.DataFrame:
    if nodes_df.empty:
        return nodes_df.copy()
    return nodes_df[~nodes_df["node_type"].isin(EXCLUDED_ANALYSIS_NODE_TYPES)].copy()


def _business_edges(edges_df: pd.DataFrame, valid_node_ids: set[str]) -> pd.DataFrame:
    if edges_df.empty or not valid_node_ids:
        return pd.DataFrame(columns=list(edges_df.columns))
    return edges_df[
        ~edges_df["edge_type"].isin(IGNORED_COMPONENT_EDGE_TYPES)
        & edges_df["from_node_id"].isin(valid_node_ids)
        & edges_df["to_node_id"].isin(valid_node_ids)
    ].copy()


def _component_rows(nodes_df: pd.DataFrame, edges_df: pd.DataFrame) -> list[dict[str, Any]]:
    node_lookup = {
        row["node_id"]: {
            "label": _string(row.get("label")),
            "node_type": _string(row.get("node_type")),
        }
        for _, row in nodes_df.iterrows()
    }
    adjacency: dict[str, set[str]] = defaultdict(set)
    for _, row in edges_df.iterrows():
        left = _string(row.get("from_node_id"))
        right = _string(row.get("to_node_id"))
        if not left or not right or left == right:
            continue
        adjacency[left].add(right)
        adjacency[right].add(left)

    components: list[dict[str, Any]] = []
    visited: set[str] = set()
    for node_id in sorted(node_lookup):
        if node_id in visited:
            continue
        if node_id not in adjacency:
            components.append(
                {
                    "component_id": f"COMP-{len(components) + 1:03d}",
                    "size": 1,
                    "node_ids": node_id,
                    "node_labels": node_lookup[node_id]["label"],
                    "node_types": node_lookup[node_id]["node_type"],
                }
            )
            visited.add(node_id)
            continue
        stack = [node_id]
        members: list[str] = []
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            members.append(current)
            stack.extend(sorted(adjacency[current] - visited))
        labels = [node_lookup[item]["label"] for item in sorted(members) if item in node_lookup]
        node_types = [node_lookup[item]["node_type"] for item in sorted(members) if item in node_lookup]
        components.append(
            {
                "component_id": f"COMP-{len(components) + 1:03d}",
                "size": len(members),
                "node_ids": "|".join(sorted(members)),
                "node_labels": "|".join(labels),
                "node_types": "|".join(node_types),
            }
        )
    return sorted(components, key=lambda item: (-int(item["size"]), item["component_id"]))


def build_graph_analysis(
    transactions: pd.DataFrame,
    *,
    matches: pd.DataFrame | None = None,
    batch_identity: str = "",
    batch_label: str = "",
    graph_bundle: dict[str, Any] | None = None,
    rule_config_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build deterministic graph analytics from BSIE normalized transactions.

    The function prefers an already-built graph bundle to avoid remodelling the
    graph when the caller has just exported it. When absent, it safely rebuilds
    the graph from the normalized transaction outputs.
    """

    if graph_bundle is None:
        nodes_df, edges_df, aggregated_df, manifest = build_graph_exports(
            transactions,
            matches=matches,
            batch_identity=batch_identity,
            batch_label=batch_label,
        )
    else:
        nodes_df = graph_bundle["nodes_df"].copy().fillna("")
        edges_df = graph_bundle["edges_df"].copy().fillna("")
        aggregated_df = graph_bundle["aggregated_df"].copy().fillna("")
        manifest = dict(graph_bundle["manifest"])
    derived_account_edges_df = (
        graph_bundle["derived_account_edges_df"].copy().fillna("")
        if graph_bundle is not None and "derived_account_edges_df" in graph_bundle
        else build_derived_account_edges(aggregated_df)
    )

    tx_df = transactions.copy().fillna("")
    nodes_df = nodes_df.copy().fillna("")
    edges_df = edges_df.copy().fillna("")
    aggregated_df = aggregated_df.copy().fillna("")

    business_nodes_df = _business_nodes(nodes_df)
    business_node_ids = set(business_nodes_df["node_id"].astype(str).tolist())
    business_edges_df = _business_edges(edges_df, business_node_ids)
    flow_edges_df = aggregated_df[aggregated_df["edge_type"].isin(["SENT_TO", "RECEIVED_FROM"])].copy() if not aggregated_df.empty else pd.DataFrame()

    node_type_counts = [
        {"node_type": node_type, "count": int(count)}
        for node_type, count in sorted(Counter(nodes_df["node_type"].astype(str).tolist()).items(), key=lambda item: (-item[1], item[0]))
    ]
    edge_type_counts = [
        {"edge_type": edge_type, "count": int(count)}
        for edge_type, count in sorted(Counter(edges_df["edge_type"].astype(str).tolist()).items(), key=lambda item: (-item[1], item[0]))
    ]

    degree_in: Counter[str] = Counter()
    degree_out: Counter[str] = Counter()
    review_pending_nodes: set[str] = set()
    suggested_match_nodes: set[str] = set()
    low_confidence_nodes: set[str] = set()

    for _, edge in business_edges_df.iterrows():
        source = _string(edge.get("from_node_id"))
        target = _string(edge.get("to_node_id"))
        degree_out[source] += 1
        degree_in[target] += 1
        if _string(edge.get("edge_type")) == "POSSIBLE_SAME_AS":
            suggested_match_nodes.add(source)
            suggested_match_nodes.add(target)
        if _float(edge.get("confidence_score")) < 0.75:
            low_confidence_nodes.add(source)
            low_confidence_nodes.add(target)

    flow_in_count: Counter[str] = Counter()
    flow_out_count: Counter[str] = Counter()
    flow_in_value: Counter[str] = Counter()
    flow_out_value: Counter[str] = Counter()

    for _, edge in flow_edges_df.iterrows():
        source = _string(edge.get("from_node_id"))
        target = _string(edge.get("to_node_id"))
        count = int(_float(edge.get("transaction_count")))
        total_abs = _float(edge.get("total_amount_abs"))
        if source:
            flow_out_count[source] += count
            flow_out_value[source] += total_abs
        if target:
            flow_in_count[target] += count
            flow_in_value[target] += total_abs

    top_nodes: list[dict[str, Any]] = []
    review_candidates: list[dict[str, Any]] = []
    for _, node in business_nodes_df.iterrows():
        node_id = _string(node.get("node_id"))
        node_type = _string(node.get("node_type"))
        review_status = _string(node.get("review_status"))
        if any(flag in review_status for flag in ["pending", "needs_review"]):
            review_pending_nodes.add(node_id)
        degree = degree_in[node_id] + degree_out[node_id]
        in_value = round(float(flow_in_value[node_id]), 2)
        out_value = round(float(flow_out_value[node_id]), 2)
        total_value = round(in_value + out_value, 2)
        row = {
            "node_id": node_id,
            "label": _string(node.get("label")),
            "node_type": node_type,
            "degree": int(degree),
            "in_degree": int(degree_in[node_id]),
            "out_degree": int(degree_out[node_id]),
            "flow_in_transactions": int(flow_in_count[node_id]),
            "flow_out_transactions": int(flow_out_count[node_id]),
            "total_in_value": in_value,
            "total_out_value": out_value,
            "total_flow_value": total_value,
            "review_status": review_status,
            "confidence_score": round(_float(node.get("confidence_score")), 4),
            "source_transaction_ids": _string(node.get("source_transaction_ids")),
            "file_ids": _string(node.get("file_ids")),
            "parser_run_ids": _string(node.get("parser_run_ids")),
            "statement_batch_ids": _string(node.get("statement_batch_ids")),
            "source_row_numbers": _string(node.get("source_row_numbers")),
            "source_sheets": _string(node.get("source_sheets")),
            "source_files": _string(node.get("source_files")),
        }
        top_nodes.append(row)

        reason_codes: list[str] = []
        if node_type == "Unknown":
            reason_codes.append("unknown_counterparty")
        if node_type == "PartialAccount":
            reason_codes.append("partial_account_only")
        if node_id in suggested_match_nodes:
            reason_codes.append("suggested_match_link")
        if node_id in review_pending_nodes:
            reason_codes.append("review_pending")
        if node_id in low_confidence_nodes:
            reason_codes.append("low_confidence_edge")
        if reason_codes:
            review_candidates.append(
                {
                    **row,
                    "reason_codes": "|".join(reason_codes),
                    "reason_count": len(reason_codes),
                }
            )

    top_nodes_by_degree = sorted(
        top_nodes,
        key=lambda item: (-int(item["degree"]), -float(item["total_flow_value"]), item["label"], item["node_id"]),
    )[:15]
    top_nodes_by_flow = sorted(
        top_nodes,
        key=lambda item: (-float(item["total_flow_value"]), -int(item["degree"]), item["label"], item["node_id"]),
    )[:15]
    review_candidates = sorted(
        review_candidates,
        key=lambda item: (-int(item["reason_count"]), -float(item["total_flow_value"]), item["label"], item["node_id"]),
    )[:20]

    components = _component_rows(business_nodes_df, business_edges_df)
    suspicious = run_graph_rules(
        tx_df=tx_df,
        business_nodes_df=business_nodes_df,
        derived_account_edges_df=derived_account_edges_df,
        top_nodes=top_nodes,
        config_overrides=rule_config_overrides,
    )

    lineage_summary = {
        "file_count": len({value for cell in nodes_df.get("file_ids", pd.Series(dtype=str)).astype(str).tolist() for value in _split_pipe(cell)}),
        "parser_run_count": len({value for cell in nodes_df.get("parser_run_ids", pd.Series(dtype=str)).astype(str).tolist() for value in _split_pipe(cell)}),
        "statement_batch_count": len({value for cell in nodes_df.get("statement_batch_ids", pd.Series(dtype=str)).astype(str).tolist() for value in _split_pipe(cell)}),
        "source_transaction_count": len({value for cell in nodes_df.get("source_transaction_ids", pd.Series(dtype=str)).astype(str).tolist() for value in _split_pipe(cell)}),
        "source_row_count": len({value for cell in nodes_df.get("source_row_numbers", pd.Series(dtype=str)).astype(str).tolist() for value in _split_pipe(cell)}),
        "source_sheet_count": len({value for cell in nodes_df.get("source_sheets", pd.Series(dtype=str)).astype(str).tolist() for value in _split_pipe(cell)}),
        "source_file_count": len({value for cell in nodes_df.get("source_files", pd.Series(dtype=str)).astype(str).tolist() for value in _split_pipe(cell)}),
    }

    overview = {
        "transaction_rows": int(len(tx_df)),
        "node_count": int(len(nodes_df)),
        "edge_count": int(len(edges_df)),
        "aggregated_edge_count": int(len(aggregated_df)),
        "derived_account_edge_count": int(len(derived_account_edges_df)),
        "business_node_count": int(len(business_nodes_df)),
        "business_edge_count": int(len(business_edges_df)),
        "connected_components": int(len(components)),
        "largest_component_size": int(max((item["size"] for item in components), default=0)),
        "confirmed_match_edges": int((edges_df["edge_type"] == "MATCHED_TO").sum()) if not edges_df.empty else 0,
        "suggested_match_edges": int((edges_df["edge_type"] == "POSSIBLE_SAME_AS").sum()) if not edges_df.empty else 0,
        "review_candidate_nodes": int(len(review_candidates)),
        "suspicious_finding_count": int(suspicious["summary"]["total_findings"]),
        "suspicious_highest_severity": suspicious["summary"]["highest_severity"],
        "unknown_nodes": int((nodes_df["node_type"] == "Unknown").sum()) if not nodes_df.empty else 0,
        "partial_account_nodes": int((nodes_df["node_type"] == "PartialAccount").sum()) if not nodes_df.empty else 0,
        "top_node_by_degree": top_nodes_by_degree[0] if top_nodes_by_degree else None,
        "top_node_by_flow": top_nodes_by_flow[0] if top_nodes_by_flow else None,
    }

    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "batch_identity": batch_identity,
        "batch_label": batch_label,
        "overview": overview,
        "graph_manifest": manifest,
        "lineage_summary": lineage_summary,
        "node_type_counts": node_type_counts,
        "edge_type_counts": edge_type_counts,
        "suspicious_rule_config": suspicious["config"],
        "suspicious_summary": suspicious["summary"],
        "suspicious_findings": suspicious["findings"],
        "top_nodes_by_degree": top_nodes_by_degree,
        "top_nodes_by_flow": top_nodes_by_flow,
        "connected_components": components[:20],
        "review_candidates": review_candidates,
    }


def write_graph_analysis_exports(output_dir: Path, analysis: dict[str, Any]) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / GRAPH_ANALYSIS_JSON
    xlsx_path = output_dir / GRAPH_ANALYSIS_XLSX
    suspicious_csv_path = output_dir / SUSPICIOUS_FINDINGS_CSV
    suspicious_json_path = output_dir / SUSPICIOUS_FINDINGS_JSON

    json_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    suspicious_df = pd.DataFrame(analysis.get("suspicious_findings", []))
    suspicious_df.to_csv(suspicious_csv_path, index=False, encoding="utf-8-sig")
    suspicious_json_path.write_text(
        suspicious_df.to_json(orient="records", force_ascii=False, indent=2),
        encoding="utf-8",
    )
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        pd.DataFrame([analysis.get("overview", {})]).to_excel(writer, sheet_name="Overview", index=False)
        pd.DataFrame([analysis.get("lineage_summary", {})]).to_excel(writer, sheet_name="Lineage", index=False)
        pd.DataFrame(analysis.get("node_type_counts", [])).to_excel(writer, sheet_name="Node_Types", index=False)
        pd.DataFrame(analysis.get("edge_type_counts", [])).to_excel(writer, sheet_name="Edge_Types", index=False)
        pd.DataFrame(analysis.get("top_nodes_by_degree", [])).to_excel(writer, sheet_name="Top_Degree", index=False)
        pd.DataFrame(analysis.get("top_nodes_by_flow", [])).to_excel(writer, sheet_name="Top_Flow", index=False)
        pd.DataFrame(analysis.get("connected_components", [])).to_excel(writer, sheet_name="Components", index=False)
        pd.DataFrame(analysis.get("review_candidates", [])).to_excel(writer, sheet_name="Review_Candidates", index=False)
        pd.DataFrame(analysis.get("suspicious_summary", {}).get("counts_by_rule", [])).to_excel(writer, sheet_name="Finding_Rules", index=False)
        pd.DataFrame(analysis.get("suspicious_summary", {}).get("counts_by_severity", [])).to_excel(writer, sheet_name="Finding_Severity", index=False)
        suspicious_df.to_excel(writer, sheet_name="Suspicious_Findings", index=False)
    return {
        "json_path": json_path,
        "xlsx_path": xlsx_path,
        "suspicious_csv_path": suspicious_csv_path,
        "suspicious_json_path": suspicious_json_path,
    }
