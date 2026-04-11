"""
export_i2_import.py
-------------------
Generate an IBM i2 Analyst's Notebook import package consisting of:

- a flat CSV transaction import file
- a matching `.ximp` import specification

This path is complementary to `.anx` export:
- `.anx` is for direct chart opening
- `.ximp + .csv` is for the i2 import wizard when analysts want a resilient
  import workflow, cards, and post-import layouting inside Analyst's Notebook
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any
from xml.sax.saxutils import escape

import pandas as pd


I2_IMPORT_CSV_FILENAME = "i2_import_transactions.csv"
I2_IMPORT_SPEC_FILENAME = "i2_import_spec.ximp"
I2_IMPORT_FLOW_EDGE_TYPES = {"SENT_TO", "RECEIVED_FROM"}
I2_IMPORT_NODE_SOURCE_COLUMNS = [
    "node_id",
    "label",
    "account_number",
    "partial_account",
    "entity_name",
    "identity_value",
    "bank_name",
]
I2_IMPORT_EDGE_SOURCE_COLUMNS = [
    "edge_id",
    "edge_type",
    "aggregation_level",
    "from_node_id",
    "to_node_id",
    "date",
    "time",
    "amount",
    "currency",
    "description",
    "reference_no",
    "review_status",
    "assertion_status",
    "confidence_score",
    "transaction_id",
    "source_transaction_ids",
    "file_id",
    "parser_run_id",
    "statement_batch_id",
    "source_file",
    "source_sheet",
    "source_row_number",
]

I2_IMPORT_COLUMNS = [
    "From Account Identity",
    "From Account Label",
    "From Account Number",
    "From Owner",
    "From Bank",
    "To Account Identity",
    "To Account Label",
    "To Account Number",
    "To Owner",
    "To Bank",
    "Transaction Date",
    "Transaction Time",
    "Transaction Amount",
    "Transaction Currency",
    "Transaction Link Label",
    "Transaction Description",
    "Reference No",
    "Review Status",
    "Assertion Status",
    "Confidence Score",
    "Transaction ID",
    "Source Transaction IDs",
    "File ID",
    "Parser Run ID",
    "Statement Batch ID",
    "Source File",
    "Source Sheet",
    "Source Row Number",
    "Edge Type",
]


def _text(value: object) -> str:
    return str(value or "").strip()


def _number_text(value: object) -> str:
    text = _text(value)
    if not text:
        return ""
    try:
        return f"{float(text):.6f}".rstrip("0").rstrip(".")
    except ValueError:
        return text


def _node_account_number(row: pd.Series) -> str:
    return _text(row.get("account_number")) or _text(row.get("partial_account"))


def _node_owner(row: pd.Series) -> str:
    return _text(row.get("entity_name")) or _text(row.get("identity_value"))


def _node_label(row: pd.Series) -> str:
    label = _text(row.get("label"))
    if label:
        return label
    account_number = _node_account_number(row)
    owner = _node_owner(row)
    return owner or account_number or _text(row.get("node_id"))


def _flow_edges_for_i2_import(edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        return pd.DataFrame(columns=edges.columns)
    mask = (
        edges["edge_type"].astype(str).isin(I2_IMPORT_FLOW_EDGE_TYPES)
        & (edges["aggregation_level"].astype(str) != "aggregate")
    )
    return edges[mask].copy()


def _link_label(row: pd.Series) -> str:
    reference = _text(row.get("reference_no"))
    if reference:
        return reference
    date_value = _text(row.get("date"))
    amount = _number_text(row.get("amount"))
    currency = _text(row.get("currency")) or "THB"
    edge_type = _text(row.get("edge_type")) or "Transaction"
    if date_value or amount:
        return " | ".join(part for part in [date_value, amount and f"{amount} {currency}".strip()] if part)
    return edge_type


def _with_default_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column not in result.columns:
            result[column] = ""
    return result


def build_i2_import_frame(nodes: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    nodes = _with_default_columns(nodes.fillna(""), I2_IMPORT_NODE_SOURCE_COLUMNS)
    edges = _with_default_columns(edges.fillna(""), I2_IMPORT_EDGE_SOURCE_COLUMNS)
    filtered_edges = _flow_edges_for_i2_import(edges)
    if filtered_edges.empty or nodes.empty:
        return pd.DataFrame(columns=I2_IMPORT_COLUMNS)

    node_map = {
        _text(row.get("node_id")): row
        for _, row in nodes.fillna("").iterrows()
        if _text(row.get("node_id"))
    }

    rows: list[dict[str, str]] = []
    for _, edge_row in filtered_edges.sort_values(["date", "time", "from_node_id", "to_node_id", "edge_id"]).iterrows():
        from_id = _text(edge_row.get("from_node_id"))
        to_id = _text(edge_row.get("to_node_id"))
        from_node = node_map.get(from_id)
        to_node = node_map.get(to_id)
        if from_node is None or to_node is None:
            continue

        rows.append(
            {
                "From Account Identity": from_id,
                "From Account Label": _node_label(from_node),
                "From Account Number": _node_account_number(from_node),
                "From Owner": _node_owner(from_node),
                "From Bank": _text(from_node.get("bank_name")),
                "To Account Identity": to_id,
                "To Account Label": _node_label(to_node),
                "To Account Number": _node_account_number(to_node),
                "To Owner": _node_owner(to_node),
                "To Bank": _text(to_node.get("bank_name")),
                "Transaction Date": _text(edge_row.get("date")),
                "Transaction Time": _text(edge_row.get("time")),
                "Transaction Amount": _number_text(edge_row.get("amount")),
                "Transaction Currency": _text(edge_row.get("currency")) or "THB",
                "Transaction Link Label": _link_label(edge_row),
                "Transaction Description": _text(edge_row.get("description")),
                "Reference No": _text(edge_row.get("reference_no")),
                "Review Status": _text(edge_row.get("review_status")),
                "Assertion Status": _text(edge_row.get("assertion_status")),
                "Confidence Score": _number_text(edge_row.get("confidence_score")),
                "Transaction ID": _text(edge_row.get("transaction_id")),
                "Source Transaction IDs": _text(edge_row.get("source_transaction_ids")),
                "File ID": _text(edge_row.get("file_id")),
                "Parser Run ID": _text(edge_row.get("parser_run_id")),
                "Statement Batch ID": _text(edge_row.get("statement_batch_id")),
                "Source File": _text(edge_row.get("source_file")),
                "Source Sheet": _text(edge_row.get("source_sheet")),
                "Source Row Number": _text(edge_row.get("source_row_number")),
                "Edge Type": _text(edge_row.get("edge_type")),
            }
        )

    return pd.DataFrame(rows, columns=I2_IMPORT_COLUMNS).fillna("")


def _ximp_attr_block(column_id: str, class_name: str, value_type: str = "") -> str:
    type_attr = f' Type="{escape(value_type)}"' if value_type else ""
    return dedent(
        f"""\
        <imp:Attribute{type_attr}>
          <imp:Class>
            <imp:Text Value="{escape(class_name)}" />
          </imp:Class>
          <imp:Value>
            <imp:Column ColumnId="{escape(column_id)}" />
          </imp:Value>
        </imp:Attribute>"""
    )


def _render_i2_import_spec(csv_filename: str, *, subject: str, comments: str, author: str) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entity_account_attrs = "\n".join(
        [
            _ximp_attr_block("From Account Number", "Account Number"),
            _ximp_attr_block("From Owner", "Owner"),
            _ximp_attr_block("From Bank", "Bank Name"),
        ]
    )
    target_account_attrs = "\n".join(
        [
            _ximp_attr_block("To Account Number", "Account Number"),
            _ximp_attr_block("To Owner", "Owner"),
            _ximp_attr_block("To Bank", "Bank Name"),
        ]
    )
    link_attrs = "\n".join(
        [
            _ximp_attr_block("Transaction Amount", "Transaction Amount", "Number"),
            _ximp_attr_block("Transaction Currency", "Currency"),
            _ximp_attr_block("Reference No", "Reference No"),
            _ximp_attr_block("Review Status", "Review Status"),
            _ximp_attr_block("Assertion Status", "Assertion Status"),
            _ximp_attr_block("Confidence Score", "Confidence Score", "Number"),
            _ximp_attr_block("Transaction ID", "Transaction ID"),
            _ximp_attr_block("Source Transaction IDs", "Source Transaction IDs"),
            _ximp_attr_block("File ID", "File ID"),
            _ximp_attr_block("Parser Run ID", "Parser Run ID"),
            _ximp_attr_block("Statement Batch ID", "Statement Batch ID"),
            _ximp_attr_block("Source File", "Source File"),
            _ximp_attr_block("Source Sheet", "Source Sheet"),
            _ximp_attr_block("Source Row Number", "Source Row Number"),
            _ximp_attr_block("Edge Type", "Edge Type"),
        ]
    )

    xml = f"""<?xml version="1.0" encoding="utf-16"?>
<imp:ImportSpecification Version="7.0.7" MinimumApplicationVersion="7.0.7" xmlns:imp="urn:import-specification">
  <imp:Data Source="File">
    <imp:File Encoding="utf-8" OpenAs="Text" Path=".\\{escape(csv_filename)}" />
  </imp:Data>
  <imp:ColumnDefinitions Format="Delimited">
    <imp:DelimitedColumns Delimiters="," IgnoreWhenPrecededBy="/" IgnoreWhenContainedBy="&quot;" />
    <imp:FixedWidthBreaks />
  </imp:ColumnDefinitions>
  <imp:ColumnReferenceDefinitions>
    <imp:RowContainingColumnIdentifiers RowIndex="1" Enabled="true" />
  </imp:ColumnReferenceDefinitions>
  <imp:RowDefinitions IgnoreRowsStartingWith="" />
  <imp:UserColumnDefinitions />
  <imp:ColumnProcessing />
  <imp:DateTimeFormats>
    <imp:DateTimeFormat ColumnId="Transaction Date" Format="yyyy-MM-dd" />
    <imp:DateTimeFormat ColumnId="Transaction Time" Format="HH:mm:ss" />
  </imp:DateTimeFormats>
  <imp:ColumnAssignment>
    <imp:Entities>
      <imp:Entity EntityId="Icon 1" X="120" Y="80">
        <imp:Identity>
          <imp:ColumnExpression>[From Account Identity]</imp:ColumnExpression>
        </imp:Identity>
        <imp:Label>
          <imp:ColumnExpression>[From Account Label]</imp:ColumnExpression>
        </imp:Label>
        <imp:Type>
          <imp:Text Value="Account" />
        </imp:Type>
        <imp:Attributes>
{entity_account_attrs}
        </imp:Attributes>
      </imp:Entity>
      <imp:Entity EntityId="Icon 2" X="420" Y="80">
        <imp:Identity>
          <imp:ColumnExpression>[To Account Identity]</imp:ColumnExpression>
        </imp:Identity>
        <imp:Label>
          <imp:ColumnExpression>[To Account Label]</imp:ColumnExpression>
        </imp:Label>
        <imp:Type>
          <imp:Text Value="Account" />
        </imp:Type>
        <imp:Attributes>
{target_account_attrs}
        </imp:Attributes>
      </imp:Entity>
    </imp:Entities>
    <imp:Connections>
      <imp:Connection FromEntityId="Icon 1" ToEntityId="Icon 2" ConnectionStyle="Multiple" />
    </imp:Connections>
    <imp:Links>
      <imp:Link FromEntityId="Icon 1" ToEntityId="Icon 2" LinkId="Link 1" XPosition="0">
        <imp:Date>
          <imp:Column ColumnId="Transaction Date" />
        </imp:Date>
        <imp:Time>
          <imp:Column ColumnId="Transaction Time" />
        </imp:Time>
        <imp:Label>
          <imp:ColumnExpression>[Transaction Link Label]</imp:ColumnExpression>
        </imp:Label>
        <imp:Type>
          <imp:Text Value="Transaction" />
        </imp:Type>
        <imp:Description>
          <imp:ColumnExpression>[Transaction Description]</imp:ColumnExpression>
        </imp:Description>
        <imp:SourceReference>
          <imp:ColumnExpression>[Transaction ID]</imp:ColumnExpression>
        </imp:SourceReference>
        <imp:Attributes>
{link_attrs}
        </imp:Attributes>
        <imp:Card Multiplicity="One" />
      </imp:Link>
    </imp:Links>
  </imp:ColumnAssignment>
  <imp:Layouts>
    <imp:Layout Order="1" LayoutId="GRAPHS.GroupLayoutCtrl.7" LayoutImportedItemsOnly="false">
      <imp:Properties />
    </imp:Layout>
  </imp:Layouts>
  <imp:Pruning />
  <imp:Selection Enabled="false" Action="ReplaceExisting" />
  <imp:Details>
    <imp:Subject Value="{escape(subject)}" />
    <imp:Author Value="{escape(author)}" />
    <imp:Category Value="Intelligence" />
    <imp:Comments>{escape(comments)}</imp:Comments>
    <imp:DateCreated Value="{escape(now)}" />
    <imp:DateModified Value="{escape(now)}" />
  </imp:Details>
</imp:ImportSpecification>
"""
    return xml


def write_i2_import_package(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    output_dir: str | Path,
    *,
    csv_filename: str = I2_IMPORT_CSV_FILENAME,
    spec_filename: str = I2_IMPORT_SPEC_FILENAME,
    subject: str = "",
    comments: str = "",
    author: str = "BSIE",
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / csv_filename
    spec_path = output_dir / spec_filename
    import_df = build_i2_import_frame(nodes, edges)
    import_df.to_csv(csv_path, index=False, encoding="utf-8")

    if not subject:
        subject = f"BSIE transaction import ({len(import_df)} flow rows)"
    if not comments:
        comments = (
            "Generated by BSIE from the shared graph export layer. "
            "Import this specification inside i2 Analyst's Notebook with the companion CSV in the same folder."
        )

    spec_xml = _render_i2_import_spec(csv_filename, subject=subject, comments=comments, author=author)
    spec_path.write_text(spec_xml, encoding="utf-16")

    return {
        "csv_path": csv_path,
        "spec_path": spec_path,
        "rows": len(import_df),
    }
