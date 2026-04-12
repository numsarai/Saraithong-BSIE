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
    channel: str = "",
) -> Tuple[str, float]:
    """
    Classify a single transaction using a priority chain.

    Parameters
    ----------
    direction            : "IN" | "OUT" | "UNKNOWN"
    counterparty_account : clean account number string (may be empty)
    description          : normalised description text
    nlp_type_hint        : hint from nlp_engine.classify_transaction_nlp
    nlp_confidence       : NLP confidence score
    channel              : channel label (ATM / CDM / K PLUS / etc.)

    Returns
    -------
    (transaction_type, confidence)
    """
    ch = (channel or "").strip().upper()

    # RULE 0: Channel-based cash classification (highest confidence for ATM/CDM)
    #   ATM  + OUT → WITHDRAW  (ถอนเงินสด)
    #   CDM  + IN  → DEPOSIT   (ฝากเงินสด)
    if ch == "ATM":
        if direction == "OUT":
            return WITHDRAW, 0.97
        # ATM IN (rare reversal) → still cash-related
        return DEPOSIT, 0.80
    if ch == "CDM":
        if direction == "IN":
            return DEPOSIT, 0.97
        return WITHDRAW, 0.80

    # RULE 0.5: Mobile app channel with no counterparty → OUT_UNKNOWN (not a cash withdrawal)
    _MOBILE_CHANNELS = {"k plus", "kplus", "scb easy", "krungthai next", "bay mobile"}
    if ch.lower() in _MOBILE_CHANNELS and not counterparty_account and direction == "OUT":
        return OUT_UNKNOWN, 0.72

    # RULE 1: Valid counterparty account → transfer
    if counterparty_account and len(counterparty_account) >= 10:
        return (IN_TRANSFER if direction == "IN" else OUT_TRANSFER), 0.95

    # RULE 2: NLP type hint
    if nlp_type_hint and nlp_type_hint != "unknown" and nlp_confidence >= 0.75:
        if nlp_type_hint == "transfer":
            return (IN_TRANSFER if direction == "IN" else OUT_TRANSFER), nlp_confidence
        mapped = _NLP_TYPE_MAP.get(nlp_type_hint)
        if mapped:
            return mapped, nlp_confidence

    # RULE 3: Keyword detection (description + channel text combined)
    combined_text = f"{description} {channel}"
    kw = detect_keyword_type(combined_text)
    if kw["is_transfer"]:
        return (IN_TRANSFER if direction == "IN" else OUT_TRANSFER), 0.80
    if kw["is_deposit"]:
        return DEPOSIT, 0.80
    if kw["is_withdraw"]:
        return WITHDRAW, 0.80

    # RULE 4: Fallback by direction → DEPOSIT / WITHDRAW (0.70)
    if direction == "IN":
        return DEPOSIT, 0.70
    if direction == "OUT":
        return WITHDRAW, 0.70
    return IN_UNKNOWN, 0.50


def classify_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply hybrid classification to an entire normalised DataFrame.
    Reads nlp_type_hint / nlp_confidence columns if present.
    Adds: transaction_type, confidence.
    """
    types: list = []
    confs: list = []

    for row in df.itertuples(index=False):
        direction = str(getattr(row, "direction", "UNKNOWN"))
        cp_acc    = str(getattr(row, "counterparty_account", "") or "")
        desc      = str(getattr(row, "description", "") or "")
        nlp_hint  = str(getattr(row, "nlp_type_hint", "unknown") or "unknown")
        nlp_conf  = float(getattr(row, "nlp_confidence", 0.0) or 0.0)
        channel   = str(getattr(row, "channel", "") or "")

        txn_type, conf = classify_transaction(
            direction, cp_acc, desc, nlp_hint, nlp_conf, channel
        )
        types.append(txn_type)
        confs.append(conf)

    df = df.copy()
    df["transaction_type"] = types
    df["confidence"]       = confs

    logger.info(f"Classification: { {t: types.count(t) for t in set(types)} }")
    return df
