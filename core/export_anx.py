"""
export_anx.py
-------------
Export BSIE graph data to IBM i2 Analyst's Notebook XML format (.anx).

The ANX export intentionally uses a simplified, analyst-friendly subgraph:
- includes investigation nodes such as accounts, entities, cash, and unknowns
- includes relationship edges such as flow, ownership, and reviewed/suggested matches
- excludes aggregate rows and bookkeeping-only lineage edges from the chart surface

This keeps the ANX chart practical for downstream manual review while preserving
the richer CSV graph exports for machine processing.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Union

import pandas as pd

from core.graph_export import build_graph_exports

logger = logging.getLogger(__name__)


ANX_EDGE_TYPES = {"OWNS", "SENT_TO", "RECEIVED_FROM", "MATCHED_TO", "POSSIBLE_SAME_AS"}

_ICON_TYPE: dict[str, str] = {
    "Account": "BankAccount",
    "PartialAccount": "BankAccount",
    "Entity": "Person",
    "Unknown": "Person",
    "Cash": "Person",
    "Bank": "Person",
}


def _description_text(parts: list[tuple[str, object]]) -> str:
    return " | ".join(f"{key}:{value}" for key, value in parts if str(value or "").strip())


def _graph_nodes_for_anx(nodes: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    if nodes.empty or edges.empty:
        return pd.DataFrame(columns=nodes.columns)
    used_node_ids = set(edges["from_node_id"].astype(str).tolist()) | set(edges["to_node_id"].astype(str).tolist())
    return nodes[nodes["node_id"].astype(str).isin(used_node_ids)].copy()


def _graph_edges_for_anx(edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        return pd.DataFrame(columns=edges.columns)
    mask = (
        edges["edge_type"].astype(str).isin(ANX_EDGE_TYPES)
        & (edges["aggregation_level"].astype(str) != "aggregate")
        & ~(
            (edges["from_node_id"].astype(str) == "UNKNOWN_COUNTERPARTY")
            & (edges["to_node_id"].astype(str) == "UNKNOWN_COUNTERPARTY")
        )
    )
    return edges[mask].copy()


def export_anx_from_graph(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    output_path: Union[str, Path],
) -> Path:
    """
    Generate an i2 Analyst's Notebook XML (.anx) file from graph-export CSV frames.
    """
    output_path = Path(output_path)
    filtered_edges = _graph_edges_for_anx(edges).fillna("")
    filtered_nodes = _graph_nodes_for_anx(nodes.fillna(""), filtered_edges)

    chart = ET.Element("Chart", {"IdReferenceLinking": "false", "Rigorous": "false"})
    collection = ET.SubElement(chart, "ChartItemCollection")

    for _, row in filtered_nodes.sort_values(["node_type", "label", "node_id"]).iterrows():
        node_id = str(row.get("node_id", "") or "").strip()
        if not node_id:
            continue
        label = str(row.get("label", "") or node_id).strip()
        node_type = str(row.get("node_type", "Entity") or "Entity")
        icon_type = _ICON_TYPE.get(node_type, "Person")

        item = ET.SubElement(collection, "ChartItem", {"Label": label})
        end = ET.SubElement(item, "End")
        entity_el = ET.SubElement(
            end,
            "Entity",
            {
                "EntityId": node_id,
                "Identity": node_id,
                "LabelIsIdentity": "false",
            },
        )
        icon = ET.SubElement(entity_el, "Icon")
        ET.SubElement(icon, "IconStyle", {"Type": icon_type})

        desc_text = _description_text(
            [
                ("NodeType", node_type),
                ("Identity", row.get("identity_value")),
                ("Account", row.get("account_number")),
                ("Partial", row.get("partial_account")),
                ("Entity", row.get("entity_name")),
                ("Bank", row.get("bank_name")),
                ("Review", row.get("review_status")),
                ("Confidence", row.get("confidence_score")),
                ("Files", row.get("file_ids")),
                ("ParserRuns", row.get("parser_run_ids")),
                ("Rows", row.get("source_row_numbers")),
            ]
        )
        if desc_text:
            desc = ET.SubElement(item, "Description")
            desc.text = desc_text

    for _, row in filtered_edges.sort_values(["edge_type", "from_node_id", "to_node_id", "edge_id"]).iterrows():
        from_id = str(row.get("from_node_id", "") or "").strip()
        to_id = str(row.get("to_node_id", "") or "").strip()
        if not from_id or not to_id:
            continue

        label = str(row.get("label", "") or row.get("edge_type", "Link")).strip()
        item = ET.SubElement(collection, "ChartItem", {"Label": label})
        link_el = ET.SubElement(item, "Link", {"End1Id": from_id, "End2Id": to_id})
        ET.SubElement(
            link_el,
            "LinkStyle",
            {
                "ArrowStyle": "ArrowOnHead",
                "MlStyle": "MultiplicityMultiple",
                "Type": "Link",
            },
        )

        desc_text = _description_text(
            [
                ("EdgeType", row.get("edge_type")),
                ("Date", row.get("date")),
                ("Time", row.get("time")),
                ("Amount", row.get("amount_display") or row.get("amount")),
                ("Confidence", row.get("confidence_score")),
                ("Review", row.get("review_status")),
                ("Assertion", row.get("assertion_status")),
                ("Transaction", row.get("transaction_id")),
                ("Transactions", row.get("source_transaction_ids")),
                ("Reference", row.get("reference_no")),
                ("Description", row.get("description")),
                ("Files", row.get("file_id")),
                ("ParserRuns", row.get("parser_run_id")),
                ("Batch", row.get("statement_batch_id")),
                ("Row", row.get("source_row_number")),
                ("Sheet", row.get("source_sheet")),
                ("SourceFile", row.get("source_file")),
            ]
        )
        if desc_text:
            desc = ET.SubElement(item, "Description")
            desc.text = desc_text

    tree = ET.ElementTree(chart)
    ET.indent(tree, space="  ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        tree.write(handle, encoding="utf-8", xml_declaration=True)

    logger.info(
        "ANX export complete: %s (%s nodes, %s edges)",
        output_path.name,
        len(filtered_nodes),
        len(filtered_edges),
    )
    return output_path


def export_anx(
    entities: pd.DataFrame,
    transactions: pd.DataFrame,
    output_path: Union[str, Path],
) -> Path:
    """
    Backwards-compatible wrapper that builds graph exports from transactions first.

    The `entities` parameter is kept for compatibility with older callers, but the
    ANX content now comes from the shared graph-export layer so the XML matches
    the CSV graph schema and its safety semantics.
    """
    nodes_df, edges_df, _, _ = build_graph_exports(transactions)
    return export_anx_from_graph(nodes_df, edges_df, output_path)
