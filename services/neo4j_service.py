from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any

try:
    from neo4j import GraphDatabase
    from neo4j import __version__ as NEO4J_DRIVER_VERSION
except Exception:  # pragma: no cover - optional dependency
    GraphDatabase = None
    NEO4J_DRIVER_VERSION = ""

from sqlalchemy.orm import Session


NEO4J_INTEGRATION_VERSION = "neo4j-python-driver-5.x"
DEFAULT_DATABASE = "neo4j"
DEFAULT_BATCH_SIZE = 250


def _env_flag(name: str, default: bool = False) -> bool:
    value = str(os.getenv(name, "")).strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if "@" in value and "://" in value:
        prefix, rest = value.split("://", 1)
        if "@" in rest:
            auth, host = rest.split("@", 1)
            if ":" in auth:
                user, _ = auth.split(":", 1)
                return f"{prefix}://{user}:***@{host}"
        return f"{prefix}://***"
    return "***"


def _rel_type(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(value or "").strip().upper())
    return cleaned or "RELATED_TO"


def _label_type(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", str(value or "").strip())
    return cleaned or "Unknown"


@dataclass
class Neo4jSettings:
    enabled: bool
    uri: str
    user: str
    password: str
    database: str
    batch_size: int
    sync_findings: bool


def get_neo4j_settings() -> Neo4jSettings:
    return Neo4jSettings(
        enabled=_env_flag("BSIE_ENABLE_NEO4J_EXPORT", False),
        uri=str(os.getenv("NEO4J_URI", "")).strip(),
        user=str(os.getenv("NEO4J_USER", "")).strip(),
        password=str(os.getenv("NEO4J_PASSWORD", "")).strip(),
        database=str(os.getenv("NEO4J_DATABASE", DEFAULT_DATABASE)).strip() or DEFAULT_DATABASE,
        batch_size=max(1, int(os.getenv("BSIE_NEO4J_BATCH_SIZE", DEFAULT_BATCH_SIZE) or DEFAULT_BATCH_SIZE)),
        sync_findings=_env_flag("BSIE_NEO4J_SYNC_FINDINGS", True),
    )


def get_neo4j_status() -> dict[str, Any]:
    settings = get_neo4j_settings()
    configured = bool(settings.uri and settings.user and settings.password)
    # HIGH-2 fix: NEVER expose password in API response
    return {
        "enabled": settings.enabled,
        "uri_masked": _mask_secret(settings.uri),
        "user": settings.user,
        "database": settings.database,
        "batch_size": settings.batch_size,
        "sync_findings": settings.sync_findings,
        "configured": configured,
        "driver_available": GraphDatabase is not None,
        "driver_version": NEO4J_DRIVER_VERSION or "",
        "integration_version": NEO4J_INTEGRATION_VERSION,
    }


def _group_rows(rows: list[dict[str, Any]], key_name: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get(key_name, "") or "")
        grouped.setdefault(key, []).append(row)
    return grouped


def _jsonify(value: Any) -> str:
    if value in ("", None):
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _prepare_node_rows(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for row in nodes:
        payload = dict(row)
        payload["node_type"] = str(payload.get("node_type", "") or "")
        payload["label"] = str(payload.get("label", "") or payload.get("node_id", "") or "")
        payload["lineage_json"] = _jsonify(payload.get("lineage_json"))
        prepared.append(payload)
    return prepared


def _prepare_edge_rows(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for row in edges:
        payload = dict(row)
        payload["edge_type"] = str(payload.get("edge_type", "") or "")
        payload["lineage_json"] = _jsonify(payload.get("lineage_json"))
        prepared.append(payload)
    return prepared


def _prepare_finding_rows(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for row in findings:
        payload = dict(row)
        payload["evidence_json"] = _jsonify(payload.get("evidence_json"))
        payload["traceability_json"] = _jsonify(payload.get("traceability_json"))
        payload["thresholds_json"] = _jsonify(payload.get("thresholds_json"))
        payload["finding_type"] = str(payload.get("rule_type", "") or "")
        prepared.append(payload)
    return prepared


def sync_graph_to_neo4j(session: Session, *, limit: int = 2000, include_findings: bool = True, **filters) -> dict[str, Any]:
    from services.graph_analysis_service import get_graph_bundle_data

    settings = get_neo4j_settings()
    status = get_neo4j_status()
    if not status["driver_available"]:
        raise RuntimeError("Neo4j driver is not installed")
    if not settings.enabled:
        raise RuntimeError("Neo4j export is disabled")
    if not status["configured"]:
        raise RuntimeError("Neo4j connection is not configured")

    payload = get_graph_bundle_data(session, limit=limit, **filters)
    graph_bundle = payload["graph_bundle"]
    analysis = payload["analysis"]

    node_rows = _prepare_node_rows(graph_bundle["nodes_df"].to_dict(orient="records"))
    edge_rows = _prepare_edge_rows(graph_bundle["edges_df"].to_dict(orient="records"))
    derived_rows = _prepare_edge_rows(graph_bundle["derived_account_edges_df"].to_dict(orient="records"))
    finding_rows = _prepare_finding_rows(list(analysis.get("suspicious_findings", []))) if include_findings and settings.sync_findings else []

    # Use settings directly (not status) to access credentials securely
    driver = GraphDatabase.driver(settings.uri, auth=(settings.user, settings.password))
    try:
        with driver.session(database=status["database"]) as neo4j_session:
            for node_type, rows in _group_rows(node_rows, "node_type").items():
                if not rows:
                    continue
                label = _label_type(node_type)
                neo4j_session.run(
                    f"""
                    UNWIND $rows AS row
                    MERGE (n:BSIENode:{label} {{node_id: row.node_id}})
                    SET n += row,
                        n.synced_from = 'BSIE',
                        n.neo4j_integration_version = $integration_version
                    """,
                    rows=rows,
                    integration_version=NEO4J_INTEGRATION_VERSION,
                )

            for edge_type, rows in _group_rows(edge_rows + derived_rows, "edge_type").items():
                if not rows:
                    continue
                rel_type = _rel_type(edge_type)
                neo4j_session.run(
                    f"""
                    UNWIND $rows AS row
                    MATCH (src:BSIENode {{node_id: row.from_node_id}})
                    MATCH (dst:BSIENode {{node_id: row.to_node_id}})
                    MERGE (src)-[rel:{rel_type} {{edge_id: row.edge_id}}]->(dst)
                    SET rel += row,
                        rel.synced_from = 'BSIE',
                        rel.neo4j_integration_version = $integration_version
                    """,
                    rows=rows,
                    integration_version=NEO4J_INTEGRATION_VERSION,
                )

            if finding_rows:
                neo4j_session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (f:SuspiciousFinding {finding_id: row.finding_id})
                    SET f += row,
                        f.synced_from = 'BSIE',
                        f.neo4j_integration_version = $integration_version
                    """,
                    rows=finding_rows,
                    integration_version=NEO4J_INTEGRATION_VERSION,
                )
                neo4j_session.run(
                    """
                    UNWIND $rows AS row
                    WITH row, [node_id IN split(coalesce(row.subject_node_ids, ''), '|') WHERE node_id <> ''] AS node_ids
                    UNWIND node_ids AS node_id
                    MATCH (f:SuspiciousFinding {finding_id: row.finding_id})
                    MATCH (n:BSIENode {node_id: node_id})
                    MERGE (f)-[rel:FLAGS {finding_id: row.finding_id, node_id: node_id}]->(n)
                    SET rel.severity = row.severity,
                        rel.rule_type = row.rule_type,
                        rel.confidence_score = row.confidence_score
                    """,
                    rows=finding_rows,
                )
    finally:
        driver.close()

    return {
        "status": "ok",
        "integration_version": NEO4J_INTEGRATION_VERSION,
        "driver_version": status["driver_version"],
        "database": status["database"],
        "node_count": len(node_rows),
        "edge_count": len(edge_rows),
        "derived_edge_count": len(derived_rows),
        "finding_count": len(finding_rows),
        "query_meta": payload.get("query_meta", {}),
    }
