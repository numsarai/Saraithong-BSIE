"""
graph_domain.py
---------------
Typed graph-domain foundation for BSIE graph modeling.

This module is intentionally small and dependency-light. It does not parse raw
files and it does not reach into persistence. Its job is to define the stable
graph objects and exported column contracts that downstream services can rely on
after BSIE has already produced finalized normalized transactions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


DERIVED_ACCOUNT_EDGE_COLUMNS = [
    "id",
    "edge_id",
    "source",
    "from_node_id",
    "target",
    "to_node_id",
    "label",
    "type",
    "edge_type",
    "aggregation_level",
    "directionality",
    "transaction_count",
    "total_amount_signed",
    "total_amount_abs",
    "total_amount_display",
    "currency",
    "date_range",
    "confidence_score_avg",
    "confidence_score_min",
    "confidence_score_max",
    "review_status",
    "assertion_status",
    "source_transaction_ids",
    "statement_batch_id",
    "parser_run_id",
    "file_id",
    "source_row_numbers",
    "source_sheets",
    "source_files",
    "lineage_json",
]


@dataclass(frozen=True)
class GraphNodeRecord:
    node_id: str
    node_type: str
    label: str
    confidence_score: float = 0.0
    review_status: str = ""
    lineage_json: str = ""


@dataclass(frozen=True)
class GraphEdgeRecord:
    edge_id: str
    edge_type: str
    from_node_id: str
    to_node_id: str
    confidence_score: float = 0.0
    review_status: str = ""
    assertion_status: str = ""
    lineage_json: str = ""


@dataclass(frozen=True)
class GraphBuildResult:
    """
    Canonical in-memory graph build result for finalized BSIE transactions.
    """

    nodes_df: pd.DataFrame
    edges_df: pd.DataFrame
    aggregated_edges_df: pd.DataFrame
    derived_account_edges_df: pd.DataFrame
    manifest: dict[str, Any]

