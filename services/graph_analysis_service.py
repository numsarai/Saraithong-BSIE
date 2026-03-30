from __future__ import annotations

import copy
import time
from collections import defaultdict
from hashlib import sha256
import json

import pandas as pd
from sqlalchemy.orm import Session

from core.graph_analysis import build_graph_analysis
from core.graph_export import build_graph_bundle
from services.export_service import _build_graph_match_frame, _build_graph_transactions_frame

GRAPH_QUERY_LIMIT_DEFAULT = 2000
GRAPH_QUERY_LIMIT_HARD_MAX = 5000
GRAPH_NEIGHBORHOOD_NODE_LIMIT = 14
GRAPH_NEIGHBORHOOD_EDGE_LIMIT = 24
GRAPH_CACHE_TTL_SECONDS = 30
_GRAPH_CACHE: dict[str, tuple[float, dict]] = {}


def _sanitize_limit(limit: int | None) -> tuple[int, int]:
    requested = int(limit or GRAPH_QUERY_LIMIT_DEFAULT)
    if requested <= 0:
        requested = GRAPH_QUERY_LIMIT_DEFAULT
    effective = min(requested, GRAPH_QUERY_LIMIT_HARD_MAX)
    return requested, effective


def _cache_key(prefix: str, *, limit: int, filters: dict) -> str:
    payload = {
        "prefix": prefix,
        "limit": limit,
        "filters": {key: value for key, value in filters.items() if value not in ("", None)},
    }
    return sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _get_cached_graph_payload(cache_key: str) -> dict | None:
    cached = _GRAPH_CACHE.get(cache_key)
    if not cached:
        return None
    cached_at, payload = cached
    if time.time() - cached_at > GRAPH_CACHE_TTL_SECONDS:
        _GRAPH_CACHE.pop(cache_key, None)
        return None
    return copy.deepcopy(payload)


def _set_cached_graph_payload(cache_key: str, payload: dict) -> dict:
    stored = copy.deepcopy(payload)
    _GRAPH_CACHE[cache_key] = (time.time(), stored)
    return copy.deepcopy(stored)


def _load_graph_inputs(
    session: Session,
    *,
    limit: int = 5000,
    **filters,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    transactions_df = _build_graph_transactions_frame(session, limit=limit, **filters)
    transaction_ids = set(transactions_df["db_transaction_id"].astype(str).tolist()) if not transactions_df.empty else set()

    account_ids = set()
    if not transactions_df.empty:
        subject_accounts = {value for value in transactions_df["subject_account"].astype(str).tolist() if value}
        if subject_accounts:
            from persistence.models import Account
            from sqlalchemy import select

            for account in session.scalars(select(Account).where(Account.normalized_account_number.in_(sorted(subject_accounts)))).all():
                account_ids.add(account.id)

    matches_df = _build_graph_match_frame(
        session,
        source_transaction_ids=transaction_ids,
        target_account_ids=account_ids,
    )
    return transactions_df, matches_df


def get_graph_analysis(
    session: Session,
    *,
    limit: int = 5000,
    **filters,
) -> dict:
    """
    Build graph analytics directly from persisted BSIE normalized transactions.

    This keeps the graph module inside the existing BSIE investigation platform
    and guarantees that analytics consume the same normalized transaction layer
    used by exports and the UI.
    """

    payload = get_graph_bundle_data(session, limit=limit, **filters)
    analysis = copy.deepcopy(payload["analysis"])
    analysis["query_meta"] = copy.deepcopy(payload["query_meta"])
    return analysis


def get_graph_bundle_data(
    session: Session,
    *,
    limit: int = 5000,
    **filters,
) -> dict:
    requested_limit, effective_limit = _sanitize_limit(limit)
    cache_key = _cache_key("bundle", limit=effective_limit, filters=filters)
    cached = _get_cached_graph_payload(cache_key)
    if cached is not None:
        cached["query_meta"]["cache_hit"] = True
        cached["query_meta"]["requested_limit"] = requested_limit
        cached["query_meta"]["effective_limit"] = effective_limit
        cached["query_meta"]["truncated"] = requested_limit > effective_limit
        return cached

    transactions_df, matches_df = _load_graph_inputs(session, limit=effective_limit, **filters)
    graph_bundle = build_graph_bundle(
        transactions_df,
        matches=matches_df,
        batch_identity=str(filters.get("parser_run_id", "") or filters.get("file_id", "") or ""),
        batch_label="",
    )
    analysis = build_graph_analysis(
        transactions_df,
        matches=matches_df,
        batch_identity=str(filters.get("parser_run_id", "") or filters.get("file_id", "") or ""),
        batch_label="",
        graph_bundle=graph_bundle,
    )
    payload = {
        "transactions_df": transactions_df,
        "matches_df": matches_df,
        "graph_bundle": graph_bundle,
        "analysis": analysis,
        "query_meta": {
            "requested_limit": requested_limit,
            "effective_limit": effective_limit,
            "cache_enabled": True,
            "cache_hit": False,
            "cache_ttl_seconds": GRAPH_CACHE_TTL_SECONDS,
            "transactions_loaded": int(len(transactions_df.index)),
            "nodes_loaded": int(len(graph_bundle["nodes_df"].index)),
            "edges_loaded": int(len(graph_bundle["edges_df"].index)),
            "derived_edges_loaded": int(len(graph_bundle["derived_account_edges_df"].index)),
            "findings_loaded": int(len(analysis.get("suspicious_findings", []))),
            "truncated": requested_limit > effective_limit,
        },
    }
    return _set_cached_graph_payload(cache_key, payload)


def list_graph_nodes(session: Session, *, limit: int = 5000, **filters) -> list[dict]:
    payload = get_graph_bundle_data(session, limit=limit, **filters)
    return payload["graph_bundle"]["nodes_df"].to_dict(orient="records")


def list_graph_edges(session: Session, *, limit: int = 5000, include_relationships: bool = True, **filters) -> list[dict]:
    payload = get_graph_bundle_data(session, limit=limit, **filters)
    edges_df = payload["graph_bundle"]["edges_df"]
    if not include_relationships:
        edges_df = edges_df[edges_df["aggregation_level"] == "transaction"].copy()
    return edges_df.to_dict(orient="records")


def list_graph_derived_edges(session: Session, *, limit: int = 5000, **filters) -> list[dict]:
    payload = get_graph_bundle_data(session, limit=limit, **filters)
    return payload["graph_bundle"]["derived_account_edges_df"].to_dict(orient="records")


def list_graph_findings(session: Session, *, limit: int = 5000, severity: str = "", rule_type: str = "", **filters) -> list[dict]:
    payload = get_graph_bundle_data(session, limit=limit, **filters)
    findings = list(payload["analysis"].get("suspicious_findings", []))
    if severity:
        findings = [row for row in findings if str(row.get("severity", "")).lower() == severity.lower()]
    if rule_type:
        findings = [row for row in findings if str(row.get("rule_type", "")).lower() == rule_type.lower()]
    return findings


def get_graph_neighborhood(
    session: Session,
    *,
    node_id: str,
    limit: int = 5000,
    include_relationships: bool = True,
    max_nodes: int = GRAPH_NEIGHBORHOOD_NODE_LIMIT,
    max_edges: int = GRAPH_NEIGHBORHOOD_EDGE_LIMIT,
    **filters,
) -> dict:
    payload = get_graph_bundle_data(session, limit=limit, **filters)
    nodes_df = payload["graph_bundle"]["nodes_df"].copy()
    edges_df = payload["graph_bundle"]["edges_df"].copy()
    findings = list(payload["analysis"].get("suspicious_findings", []))

    if not include_relationships:
        edges_df = edges_df[edges_df["aggregation_level"] == "transaction"].copy()

    adjacent_edge_rows = edges_df[
        (edges_df["from_node_id"] == node_id) | (edges_df["to_node_id"] == node_id)
    ].copy()

    if not adjacent_edge_rows.empty:
        adjacent_edge_rows["__priority"] = adjacent_edge_rows["edge_type"].astype(str).map(
            {
                "DERIVED_ACCOUNT_TO_ACCOUNT": 0,
                "SENT_TO": 1,
                "RECEIVED_FROM": 1,
                "POSSIBLE_SAME_AS": 2,
                "MATCHED_TO": 2,
            }
        ).fillna(3)
        adjacent_edge_rows["__flow"] = (
            pd.to_numeric(adjacent_edge_rows.get("total_amount_abs"), errors="coerce")
            .fillna(pd.to_numeric(adjacent_edge_rows.get("amount"), errors="coerce").abs())
            .fillna(0.0)
        )
        adjacent_edge_rows = adjacent_edge_rows.sort_values(
            by=["__priority", "__flow"],
            ascending=[True, False],
        ).head(max(1, int(max_edges)))

    neighbor_ids = set(adjacent_edge_rows["from_node_id"].astype(str).tolist()) | set(adjacent_edge_rows["to_node_id"].astype(str).tolist())
    if node_id:
        neighbor_ids.add(node_id)

    neighborhood_nodes = nodes_df[nodes_df["node_id"].isin(sorted(neighbor_ids))].copy()

    suspicious_nodes: set[str] = set()
    findings_by_node: dict[str, list[dict]] = defaultdict(list)
    for finding in findings:
        subject_nodes = {part for part in str(finding.get("subject_node_ids", "")).split("|") if part}
        if node_id in subject_nodes or subject_nodes & neighbor_ids:
            for subject_node in subject_nodes:
                suspicious_nodes.add(subject_node)
                findings_by_node[subject_node].append(finding)

    if not neighborhood_nodes.empty:
        neighborhood_nodes["__priority"] = neighborhood_nodes["node_id"].astype(str).map(
            lambda value: 0 if value == node_id else (1 if value in suspicious_nodes else 2)
        )
        neighborhood_nodes["__degree"] = neighborhood_nodes["node_id"].astype(str).map(
            lambda value: int(
                ((adjacent_edge_rows["from_node_id"] == value) | (adjacent_edge_rows["to_node_id"] == value)).sum()
            )
        )
        neighborhood_nodes = neighborhood_nodes.sort_values(
            by=["__priority", "__degree", "label"],
            ascending=[True, False, True],
        ).head(max(1, int(max_nodes)))
        visible_node_ids = set(neighborhood_nodes["node_id"].astype(str).tolist())
        adjacent_edge_rows = adjacent_edge_rows[
            adjacent_edge_rows["from_node_id"].astype(str).isin(visible_node_ids)
            & adjacent_edge_rows["to_node_id"].astype(str).isin(visible_node_ids)
        ].copy()
    else:
        visible_node_ids = set()

    hidden_node_ids = sorted(neighbor_ids - visible_node_ids) if visible_node_ids else sorted(neighbor_ids)
    omitted_findings = [
        row for row in findings
        if set(str(row.get("subject_node_ids", "")).split("|")) & set(hidden_node_ids)
    ]

    adjacent_edge_rows = adjacent_edge_rows.drop(columns=["__priority", "__flow"], errors="ignore")
    neighborhood_nodes = neighborhood_nodes.drop(columns=["__priority", "__degree"], errors="ignore")

    return {
        "center_node_id": node_id,
        "nodes": neighborhood_nodes.to_dict(orient="records"),
        "edges": adjacent_edge_rows.to_dict(orient="records"),
        "suspicious_node_ids": sorted(suspicious_nodes & visible_node_ids),
        "findings": [row for row in findings if node_id in str(row.get("subject_node_ids", "")).split("|") or (set(str(row.get("subject_node_ids", "")).split("|")) & neighbor_ids)],
        "findings_by_node": {key: value for key, value in findings_by_node.items() if key in visible_node_ids},
        "query_meta": payload["query_meta"],
        "graph_meta": {
            "requested_max_nodes": int(max_nodes),
            "requested_max_edges": int(max_edges),
            "visible_node_count": int(len(neighborhood_nodes.index)),
            "visible_edge_count": int(len(adjacent_edge_rows.index)),
            "hidden_node_count": int(len(hidden_node_ids)),
            "hidden_node_ids": hidden_node_ids[:20],
            "hidden_findings_count": int(len(omitted_findings)),
            "include_relationships": bool(include_relationships),
            "layout_mode": "focused-neighborhood",
        },
    }
