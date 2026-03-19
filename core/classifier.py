"""
classifier.py
-------------
Hybrid rule-based + NLP transaction classifier with confidence scoring.

Priority (highest to lowest):
  RULE 1 – Valid counterparty_account (>=10 digits)  -> IN/OUT_TRANSFER  (0.95)
  RULE 2 – NLP type hint from nlp_engine             -> type-specific    (0.85)
  RULE 3 – Keyword detection (Thai + English)        -> type-specific    (0.80)
  RULE 4 – Fallback by direction                     -> IN/OUT_UNKNOWN   (0.60)
"""

import logging
from typing import Tuple

import pandas as pd

from utils.text_utils import detect_keyword_type

logger = logging.getLogger(__name__)

# Transaction type constants
IN_TRANSFER  = "IN_TRANSFER"
OUT_TRANSFER = "OUT_TRANSFER"
DEPOSIT      = "DEPOSIT"
WITHDRAW     = "WITHDRAW"
FEE          = "FEE"
SALARY       = "SALARY"
IN_UNKNOWN   = "IN_UNKNOWN"
OUT_UNKNOWN  = "OUT_UNKNOWN"

_NLP_TYPE_MAP = {
    "deposit":  DEPOSIT,
    "withdraw": WITHDRAW,
    "fee":      FEE,
    "salary":   SALARY,
}


def classify_transaction(
    direction: str,
    counterparty_account: str,
    description: str,
    nlp_type_hint: str = "unknown",
    nlp_confidence: float = 0.0,
) -> Tuple[str, float]:
    """
    Classify a single transaction using a 4-rule priority chain.

    Parameters
    ----------
    direction            : "IN" | "OUT" | "UNKNOWN"
    counterparty_account : clean account number string (may be empty)
    description          : normalised description text
    nlp_type_hint        : hint from nlp_engine.classify_transaction_nlp
    nlp_confidence       : NLP confidence score

    Returns
    -------
    (transaction_type, confidence)
    """
    # RULE 1: Valid counterparty account
    if counterparty_account and len(counterparty_account) >= 10:
        return (IN_TRANSFER if direction == "IN" else OUT_TRANSFER), 0.95

    # RULE 2: NLP type hint
    if nlp_type_hint and nlp_type_hint != "unknown" and nlp_confidence >= 0.75:
        if nlp_type_hint == "transfer":
            return (IN_TRANSFER if direction == "IN" else OUT_TRANSFER), nlp_confidence
        mapped = _NLP_TYPE_MAP.get(nlp_type_hint)
        if mapped:
            return mapped, nlp_confidence

    # RULE 3: Keyword detection
    kw = detect_keyword_type(description)
    if kw["is_transfer"]:
        return (IN_TRANSFER if direction == "IN" else OUT_TRANSFER), 0.80
    if kw["is_deposit"]:
        return DEPOSIT, 0.80
    if kw["is_withdraw"]:
        return WITHDRAW, 0.80

    # RULE 4: Fallback
    if direction == "IN":
        return IN_UNKNOWN, 0.60
    if direction == "OUT":
        return OUT_UNKNOWN, 0.60
    return IN_UNKNOWN, 0.50


def classify_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply hybrid classification to an entire normalised DataFrame.
    Reads nlp_type_hint / nlp_confidence columns if present.
    Adds: transaction_type, confidence.
    """
    types: list = []
    confs: list = []

    for _, row in df.iterrows():
        direction = str(row.get("direction", "UNKNOWN"))
        cp_acc    = str(row.get("counterparty_account", "") or "")
        desc      = str(row.get("description", "") or "")
        nlp_hint  = str(row.get("nlp_type_hint", "unknown") or "unknown")
        nlp_conf  = float(row.get("nlp_confidence", 0.0) or 0.0)

        txn_type, conf = classify_transaction(direction, cp_acc, desc, nlp_hint, nlp_conf)
        types.append(txn_type)
        confs.append(conf)

    df = df.copy()
    df["transaction_type"] = types
    df["confidence"]       = confs

    logger.info(f"Classification: { {t: types.count(t) for t in set(types)} }")
    return df
