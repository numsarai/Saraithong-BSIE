"""
link_builder.py
---------------
Builds from_account / to_account graph edges based on direction and the
Subject Account anchor logic.

RULE:
  IF direction == IN:
      from_account = counterparty_account OR partial_account OR "UNKNOWN"
      to_account   = subject_account

  IF direction == OUT:
      from_account = subject_account
      to_account   = counterparty_account OR partial_account OR "UNKNOWN"

DO NOT trust bank column labels like "to/from" — rely solely on direction + amount sign.
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def _resolve_counterparty(row: pd.Series) -> str:
    """
    Pick the best available counterparty identifier.
    Priority: valid account → partial → "UNKNOWN"
    """
    cp = str(row.get("counterparty_account", "") or "").strip()
    if cp:
        return cp

    partial = str(row.get("partial_account", "") or "").strip()
    if partial:
        return f"PARTIAL:{partial}"

    return "UNKNOWN"


def build_links(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add from_account and to_account columns to the transaction DataFrame.

    Parameters
    ----------
    df : classified transaction DataFrame

    Returns
    -------
    pd.DataFrame with from_account and to_account columns added
    """
    from_list: list[str] = []
    to_list:   list[str] = []

    for _, row in df.iterrows():
        direction       = str(row.get("direction", "UNKNOWN"))
        subject_account = str(row.get("subject_account", "") or "")
        counterparty    = _resolve_counterparty(row)

        if direction == "IN":
            from_list.append(counterparty)
            to_list.append(subject_account)
        elif direction == "OUT":
            from_list.append(subject_account)
            to_list.append(counterparty)
        else:
            # UNKNOWN direction – record both as UNKNOWN
            from_list.append("UNKNOWN")
            to_list.append("UNKNOWN")

    df = df.copy()
    df["from_account"] = from_list
    df["to_account"]   = to_list

    logger.info(f"Links built for {len(df)} transactions")
    return df


def extract_links(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract the graph-ready links DataFrame from a fully-processed
    transaction DataFrame.

    Returns
    -------
    pd.DataFrame with columns:
        transaction_id, from_account, to_account, amount, date, transaction_type
    """
    cols = ["transaction_id", "from_account", "to_account", "amount", "date", "transaction_type"]
    available = [c for c in cols if c in df.columns]
    links = df[available].copy()
    links.reset_index(drop=True, inplace=True)
    return links
