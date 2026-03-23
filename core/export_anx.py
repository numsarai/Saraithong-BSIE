"""
export_anx.py
-------------
Export BSIE data to IBM i2 Analyst's Notebook XML format (.anx).

The output file can be imported into i2 directly via:
  Data → Import from File → Import XML → select the .anx file
  ✔ Check "Layout Imported Items"

Format: non-rigorous transformed XML (i2 ANB 9+).
  - Rigorous="false"  → i2 auto-merges entities with the same Identity
  - IdReferenceLinking="false" → no xsd:ID/IDREF requirements

Mapping:
  BSIE entity_type  →  i2 IconStyle Type
  ─────────────────────────────────────
  ACCOUNT           →  BankAccount
  PARTIAL_ACCOUNT   →  BankAccount
  NAME              →  Person
  UNKNOWN           →  Person

  BSIE transaction  →  i2 Link
  ─────────────────────────────────────
  from_account      →  End1Id   (money source)
  to_account        →  End2Id   (money destination)
  amount + date     →  Label
  transaction_id    →  Description (full detail)
"""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Union

import pandas as pd

logger = logging.getLogger(__name__)

# ── i2 icon type mapping ──────────────────────────────────────────────────
_ICON_TYPE: dict[str, str] = {
    "ACCOUNT":          "BankAccount",
    "PARTIAL_ACCOUNT":  "BankAccount",
    "NAME":             "Person",
    "UNKNOWN":          "Person",
}


# ── Helpers ───────────────────────────────────────────────────────────────

def _entity_identity(row: pd.Series) -> str:
    """
    Unique key used by i2 for entity deduplication.
    Use account_number when available, else name, else 'UNKNOWN'.
    """
    acct = str(row.get("account_number", "") or "").strip()
    if acct:
        return acct
    name = str(row.get("name", "") or "").strip()
    return name or "UNKNOWN"


def _entity_label(row: pd.Series) -> str:
    """
    Display label shown on the chart node.
    Format: "Name (account)" if both known, else whichever is available.
    """
    name = str(row.get("name", "") or "").strip()
    acct = str(row.get("account_number", "") or "").strip()
    if name and acct:
        return f"{name} ({acct})"
    return name or acct or "UNKNOWN"


def _resolve_end_id(account: str) -> str:
    """
    Convert a from_account/to_account value to an i2 EntityId.

    link_builder.py stores partial accounts as "PARTIAL:1234".
    The entity table stores them as "1234" (without prefix).
    Strip the prefix so End1Id/End2Id match the Entity's EntityId.
    """
    account = str(account or "").strip()
    if account.startswith("PARTIAL:"):
        return account[len("PARTIAL:"):]
    return account or "UNKNOWN"


def _link_label(row: pd.Series) -> str:
    """Short link label: '฿5,000.00 | 2024-01-15'"""
    amount = row.get("amount", "")
    date   = str(row.get("date", "") or "")[:10]
    try:
        amount_str = f"\u0e3f{float(amount):,.2f}"   # ฿ Thai baht symbol
    except (ValueError, TypeError):
        amount_str = str(amount) if amount != "" else "?"
    parts = [p for p in [amount_str, date] if p]
    return " | ".join(parts) or "Transaction"


def _link_description(row: pd.Series) -> str:
    """Full transaction detail stored in i2 Description field."""
    fields = [
        ("ID",   row.get("transaction_id", "")),
        ("Type", row.get("transaction_type", "")),
        ("Desc", row.get("description", "")),
        ("Ch",   row.get("channel", "")),
    ]
    return " | ".join(f"{k}:{v}" for k, v in fields if str(v or "").strip())


# ── Main export function ──────────────────────────────────────────────────

def export_anx(
    entities: pd.DataFrame,
    transactions: pd.DataFrame,
    output_path: Union[str, Path],
) -> Path:
    """
    Generate an i2 Analyst's Notebook XML (.anx) file.

    Parameters
    ----------
    entities     : entity DataFrame (from entity.build_entities())
    transactions : full transaction DataFrame with from_account, to_account columns
    output_path  : path to write the .anx file

    Returns
    -------
    Path to the written .anx file
    """
    output_path = Path(output_path)

    # ── Root element ──────────────────────────────────────────────────────
    # Non-rigorous mode: i2 will merge duplicate EntityIds by Identity value.
    # This is the same approach used in the i2 "Phone Calls" reference example.
    chart = ET.Element("Chart", {
        "IdReferenceLinking": "false",
        "Rigorous":           "false",
    })
    collection = ET.SubElement(chart, "ChartItemCollection")

    # ── 1. Entity ChartItems ──────────────────────────────────────────────
    # One ChartItem per unique entity. i2 merges entities with same Identity.
    for _, row in entities.iterrows():
        identity  = _entity_identity(row)
        label     = _entity_label(row)
        etype     = str(row.get("entity_type", "UNKNOWN"))
        icon_type = _ICON_TYPE.get(etype, "Person")

        item = ET.SubElement(collection, "ChartItem", {"Label": label})
        end  = ET.SubElement(item, "End")

        # LabelIsIdentity="false" because label (name+account) may differ from
        # identity (account number only). This is correct per i2 schema.
        entity_el = ET.SubElement(end, "Entity", {
            "EntityId":        identity,
            "Identity":        identity,
            "LabelIsIdentity": "false",
        })
        icon = ET.SubElement(entity_el, "Icon")
        ET.SubElement(icon, "IconStyle", {"Type": icon_type})

    # ── 2. Link ChartItems (one per transaction) ──────────────────────────
    required_cols = {"from_account", "to_account"}
    if not required_cols.issubset(set(transactions.columns)):
        logger.warning(
            "Transactions missing from_account/to_account — skipping ANX links. "
            "Ensure build_links() ran before export."
        )
    else:
        for _, row in transactions.iterrows():
            from_id = _resolve_end_id(str(row.get("from_account", "") or ""))
            to_id   = _resolve_end_id(str(row.get("to_account",   "") or ""))
            label   = _link_label(row)

            item    = ET.SubElement(collection, "ChartItem", {"Label": label})
            link_el = ET.SubElement(item, "Link", {
                "End1Id": from_id,   # money source
                "End2Id": to_id,     # money destination
            })
            # ArrowOnHead: arrow points from End1 (source) to End2 (destination)
            # MultiplicityMultiple: multiple links allowed between same pair
            ET.SubElement(link_el, "LinkStyle", {
                "ArrowStyle": "ArrowOnHead",
                "MlStyle":    "MultiplicityMultiple",
                "Type":       "Link",
            })

            # Store full transaction detail in Description for analyst review
            desc_text = _link_description(row)
            if desc_text:
                desc = ET.SubElement(item, "Description")
                desc.text = desc_text

    # ── 3. Serialize to file ──────────────────────────────────────────────
    tree = ET.ElementTree(chart)
    ET.indent(tree, space="  ")   # requires Python 3.9+

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as fh:
        tree.write(fh, encoding="utf-8", xml_declaration=True)

    logger.info(
        f"ANX export complete: {output_path.name} "
        f"({len(entities)} entities, {len(transactions)} links)"
    )
    return output_path
