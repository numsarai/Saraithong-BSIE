from __future__ import annotations

import pandas as pd

from core.graph_domain import GraphBuildResult
from core.graph_export import build_graph_bundle


def build_graph_from_transactions(
    transactions: pd.DataFrame,
    *,
    matches: pd.DataFrame | None = None,
    batch_identity: str = "",
    batch_label: str = "",
) -> GraphBuildResult:
    """
    Build the Phase 1 BSIE graph foundation from finalized normalized
    transactions.

    This service intentionally consumes the existing BSIE structured transaction
    output and does not re-run parsing, mapping, or normalization.
    """

    graph_bundle = build_graph_bundle(
        transactions,
        matches=matches,
        batch_identity=batch_identity,
        batch_label=batch_label,
    )
    return GraphBuildResult(
        nodes_df=graph_bundle["nodes_df"],
        edges_df=graph_bundle["edges_df"],
        aggregated_edges_df=graph_bundle["aggregated_df"],
        derived_account_edges_df=graph_bundle["derived_account_edges_df"],
        manifest=graph_bundle["manifest"],
    )

