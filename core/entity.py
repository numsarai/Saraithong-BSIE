"""
entity.py
---------
Builds a deduplicated entity list from the transaction DataFrame.

Entity types:
  ACCOUNT         – valid 10 or 12-digit account number
  PARTIAL_ACCOUNT – partial digit sequence (< 10 digits)
  NAME            – person/company name
  UNKNOWN         – no identifier available

Each entity gets a unique entity_id and all source transaction_ids are
preserved for full traceability.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _make_entity_id(entity_type: str, value: str) -> str:
    """Generate a stable, short entity_id from type + value."""
    raw = f"{entity_type}::{value}".encode("utf-8")
    # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1 -- This is a deterministic short identifier, not a cryptographic signature or security boundary.
    return "E_" + hashlib.sha1(raw).hexdigest()[:10].upper()


def _classify_entity_type(account: str, name: str) -> tuple[str, str]:
    """
    Determine entity type and canonical value.

    Returns
    -------
    (entity_type, canonical_value)
    """
    if account:
        if account.startswith("PARTIAL:"):
            return "PARTIAL_ACCOUNT", account.replace("PARTIAL:", "")
        if account == "UNKNOWN":
            if name:
                return "NAME", name
            return "UNKNOWN", "UNKNOWN"
        return "ACCOUNT", account
    if name:
        return "NAME", name
    return "UNKNOWN", "UNKNOWN"


def build_entities(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a deduplicated entity table from the transaction DataFrame.

    Collects all unique participants:
    - subject_account / subject_name
    - counterparty_account / counterparty_name / partial_account
    - from_account / to_account (if they differ from above)

    Parameters
    ----------
    df : fully-processed transaction DataFrame

    Returns
    -------
    pd.DataFrame with columns:
        entity_id, entity_type, account_number, name,
        first_seen, last_seen, transaction_count, source_transaction_ids
    """
    # Map: canonical_value → entity data accumulator
    entity_map: dict[str, dict] = {}

    def upsert(account: str, name: str, txn_id: Optional[str], date: Optional[str]) -> None:
        """Insert or update an entity entry."""
        etype, canonical = _classify_entity_type(account, name)
        eid = _make_entity_id(etype, canonical)

        if eid not in entity_map:
            entity_map[eid] = {
                "entity_id":   eid,
                "entity_type": etype,
                "account_number": canonical if etype in {"ACCOUNT", "PARTIAL_ACCOUNT"} else "",
                "name":        name if etype in {"NAME", "ACCOUNT"} else "",
                "dates":       [],
                "txn_ids":     [],
            }
        rec = entity_map[eid]
        if name and not rec["name"]:
            rec["name"] = name
        if txn_id:
            rec["txn_ids"].append(txn_id)
        if date:
            rec["dates"].append(str(date))

    for _, row in df.iterrows():
        tid  = str(row.get("transaction_id", ""))
        date = str(row.get("date", "") or "")

        # Subject
        upsert(
            str(row.get("subject_account", "") or ""),
            str(row.get("subject_name", "") or ""),
            tid, date,
        )
        # Counterparty
        cp_acc  = str(row.get("counterparty_account", "") or "")
        partial = str(row.get("partial_account", "") or "")
        cp_name = str(row.get("counterparty_name", "") or "")

        if cp_acc:
            upsert(cp_acc, cp_name, tid, date)
        elif partial:
            upsert(f"PARTIAL:{partial}", cp_name, tid, date)
        else:
            upsert("UNKNOWN", cp_name, tid, date)

    # Build final DataFrame
    rows = []
    for eid, rec in entity_map.items():
        dates = sorted(set(d for d in rec["dates"] if d))
        rows.append({
            "entity_id":            rec["entity_id"],
            "entity_type":          rec["entity_type"],
            "account_number":       rec["account_number"],
            "name":                 rec["name"],
            "first_seen":           dates[0] if dates else "",
            "last_seen":            dates[-1] if dates else "",
            "transaction_count":    len(rec["txn_ids"]),
            "source_transaction_ids": "|".join(sorted(set(rec["txn_ids"]))),
        })

    entities = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[
        "entity_id", "entity_type", "account_number", "name",
        "first_seen", "last_seen", "transaction_count", "source_transaction_ids",
    ])
    if not entities.empty:
        entities.sort_values("entity_type", inplace=True)
    entities.reset_index(drop=True, inplace=True)

    logger.info(f"Built {len(entities)} unique entities")
    return entities
