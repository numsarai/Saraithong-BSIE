from __future__ import annotations

import pandas as pd

from services import neo4j_service


class _FakeNeo4jSession:
    def __init__(self, calls: list[tuple[str, dict]]):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, query: str, **params):
        self.calls.append((query, params))
        return None


class _FakeDriver:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def session(self, **kwargs):
        return _FakeNeo4jSession(self.calls)

    def close(self):
        return None


class _FakeGraphDatabase:
    last_driver: _FakeDriver | None = None

    @staticmethod
    def driver(uri: str, auth: tuple[str, str]):
        _FakeGraphDatabase.last_driver = _FakeDriver()
        return _FakeGraphDatabase.last_driver


def test_get_neo4j_status_reports_optional_driver(monkeypatch):
    monkeypatch.setenv("BSIE_ENABLE_NEO4J_EXPORT", "true")
    monkeypatch.setenv("NEO4J_URI", "bolt://neo4j:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")
    monkeypatch.setattr(neo4j_service, "GraphDatabase", _FakeGraphDatabase)
    monkeypatch.setattr(neo4j_service, "NEO4J_DRIVER_VERSION", "5.28.0")

    status = neo4j_service.get_neo4j_status()

    assert status["enabled"] is True
    assert status["configured"] is True
    assert status["driver_available"] is True
    assert status["driver_version"] == "5.28.0"


def test_sync_graph_to_neo4j_merges_nodes_edges_and_findings(monkeypatch):
    monkeypatch.setenv("BSIE_ENABLE_NEO4J_EXPORT", "true")
    monkeypatch.setenv("NEO4J_URI", "bolt://neo4j:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")
    monkeypatch.setattr(neo4j_service, "GraphDatabase", _FakeGraphDatabase)
    monkeypatch.setattr(neo4j_service, "NEO4J_DRIVER_VERSION", "5.28.0")

    from services import graph_analysis_service

    monkeypatch.setattr(
        graph_analysis_service,
        "get_graph_bundle_data",
        lambda session, limit=2000, **filters: {
            "graph_bundle": {
                "nodes_df": pd.DataFrame([{"node_id": "ACCOUNT:1111111111", "node_type": "Account", "label": "Subject Account", "lineage_json": "{}"}]),
                "edges_df": pd.DataFrame([{"edge_id": "FLOW:1", "edge_type": "SENT_TO", "from_node_id": "ACCOUNT:1111111111", "to_node_id": "ACCOUNT:2222222222", "lineage_json": "{}"}]),
                "derived_account_edges_df": pd.DataFrame([{"edge_id": "DERIVED:1", "edge_type": "DERIVED_ACCOUNT_TO_ACCOUNT", "from_node_id": "ACCOUNT:1111111111", "to_node_id": "ACCOUNT:2222222222", "lineage_json": "{}"}]),
            },
            "analysis": {
                "suspicious_findings": [
                    {
                        "finding_id": "FINDING:1",
                        "rule_type": "fan_out_accounts",
                        "severity": "high",
                        "subject_node_ids": "ACCOUNT:1111111111",
                        "evidence_json": {},
                        "traceability_json": {},
                        "thresholds_json": {},
                    }
                ]
            },
            "query_meta": {"transactions_loaded": 1},
        },
    )

    payload = neo4j_service.sync_graph_to_neo4j(session=None, limit=1000, include_findings=True)

    assert payload["status"] == "ok"
    assert payload["node_count"] == 1
    assert payload["edge_count"] == 1
    assert payload["derived_edge_count"] == 1
    assert payload["finding_count"] == 1
    assert _FakeGraphDatabase.last_driver is not None
    assert len(_FakeGraphDatabase.last_driver.calls) >= 3
