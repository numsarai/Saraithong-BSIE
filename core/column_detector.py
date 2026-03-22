"""
column_detector.py
------------------
Detects and maps actual DataFrame column names to BSIE logical field names
using keyword dictionaries and fuzzy matching (rapidfuzz with difflib fallback).
"""

import logging
import re
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Logical field → candidate aliases (Thai + English) ────────────────────
FIELD_KEYWORDS: Dict[str, List[str]] = {
    "date": [
        "วันที่", "date", "transaction date", "txn date", "trans date",
        "วันที่ทำรายการ", "tran date", "posting date", "value date",
        "effective date", "booking date",
    ],
    "time": [
        "เวลา", "time", "transaction time", "txn time", "เวลาทำรายการ",
        "trans time",
    ],
    "description": [
        "รายการ", "รายละเอียด", "ประเภทรายการ", "description", "narration",
        "remark", "details", "detail", "memo", "note", "particulars",
        "หมายเหตุ", "คำอธิบาย", "รายการ/หมายเหตุ",
        "transaction description", "txn description",
    ],
    "amount": [
        "จำนวนเงิน", "amount", "net amount", "transaction amount",
        "debit/credit", "credit/debit", "amt", "จำนวน",
    ],
    "debit": [
        "ถอน", "เดบิต", "debit", "withdrawal", "dr", "จำนวนเงินถอน",
        "ถอนเงิน", "รายการถอน", "withdraw", "out",
    ],
    "credit": [
        "ฝาก", "เครดิต", "credit", "deposit", "cr", "จำนวนเงินฝาก",
        "ฝากเงิน", "เงินฝาก", "รายการฝาก", "in",
    ],
    "balance": [
        "ยอดคงเหลือ", "balance", "running balance", "outstanding",
        "คงเหลือ", "ยอดเงินคงเหลือ", "จำนวนเงินคงเหลือ", "bal",
        "avail balance", "available balance",
    ],
    "channel": [
        "ช่องทาง", "channel", "transaction channel", "medium", "via",
        "mode", "source",
    ],
    "counterparty_account": [
        "บัญชีคู่โอน", "เลขที่บัญชีคู่สัญญา", "บัญชีคู่สัญญา",
        "counterparty account", "to/from account",
        "ref account", "beneficiary account", "บัญชีผู้โอน/รับโอน",
        "บัญชีปลายทาง", "บัญชีผู้รับโอน", "บัญชีผู้โอน",
        "from account", "to account", "account no", "acc no",
        "account number", "ref no", "reference account",
    ],
    "counterparty_name": [
        "ชื่อคู่โอน", "ชื่อคู่สัญญา", "counterparty name", "to/from name",
        "beneficiary name", "ชื่อผู้โอน/รับโอน", "ชื่อผู้รับโอน",
        "ชื่อผู้โอน", "payee", "payer", "receiver name",
    ],
}

# Priority: required fields are checked first
REQUIRED_FIELDS  = ["date", "amount", "description"]
OPTIONAL_FIELDS  = ["time", "debit", "credit", "balance", "channel",
                    "counterparty_account", "counterparty_name"]
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS


def _norm(text: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return re.sub(r'\s+', ' ', str(text).strip().lower())


def _similarity(a: str, b: str) -> float:
    """Fuzzy string similarity, 0–1."""
    try:
        from rapidfuzz import fuzz
        return fuzz.token_set_ratio(a, b) / 100.0
    except ImportError:
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a, b).ratio()


def detect_columns(
    df: pd.DataFrame,
    threshold: float = 0.60,
) -> Dict:
    """
    Map actual DataFrame columns to BSIE logical field names.

    Parameters
    ----------
    df        : raw DataFrame
    threshold : minimum similarity to accept a fuzzy mapping

    Returns
    -------
    {
        "suggested_mapping"  : {field: column_or_None},
        "confidence_scores"  : {field: 0.0–1.0},
        "unmatched_columns"  : [columns not assigned to any field],
        "all_columns"        : [all actual column names],
        "required_found"     : bool  – True if date+amount+description all mapped
    }
    """
    actual_cols = list(df.columns)
    norm_to_orig = {_norm(c): c for c in actual_cols}

    suggested:   Dict[str, Optional[str]] = {}
    conf_scores: Dict[str, float]         = {}
    used_actual: set                       = set()

    def _try_map(field: str) -> None:
        keywords = FIELD_KEYWORDS.get(field, [])
        best_col   = None
        best_score = 0.0

        for kw in keywords:
            norm_kw = _norm(kw)

            # 1. Exact match
            if norm_kw in norm_to_orig:
                col = norm_to_orig[norm_kw]
                if col not in used_actual:
                    best_col   = col
                    best_score = 1.0
                    break

            # 2. Substring match
            for nc, col in norm_to_orig.items():
                if col in used_actual:
                    continue
                if norm_kw in nc or nc in norm_kw:
                    score = 0.88
                    if score > best_score:
                        best_score, best_col = score, col

        # 3. Fuzzy fallback
        if best_score < threshold:
            for kw in keywords:
                norm_kw = _norm(kw)
                for nc, col in norm_to_orig.items():
                    if col in used_actual:
                        continue
                    sc = _similarity(norm_kw, nc)
                    if sc > best_score and sc >= threshold:
                        best_score, best_col = sc, col

        if best_col and best_score >= threshold:
            suggested[field]   = best_col
            conf_scores[field] = round(best_score, 3)
            used_actual.add(best_col)
        else:
            suggested[field]   = None
            conf_scores[field] = 0.0

    # Map required fields first, then optional
    for f in ALL_FIELDS:
        _try_map(f)

    mapped   = {v for v in suggested.values() if v}
    unmatched = [c for c in actual_cols if c not in mapped]

    # "amount" can be satisfied by either a single amount column OR debit+credit pair
    has_amount = (
        suggested.get("amount") is not None
        or (suggested.get("debit") is not None and suggested.get("credit") is not None)
    )
    required_found = (
        suggested.get("date") is not None
        and suggested.get("description") is not None
        and has_amount
    )

    n_mapped = sum(1 for v in suggested.values() if v)
    logger.info(
        f"Column detection: {n_mapped}/{len(ALL_FIELDS)} fields mapped "
        f"(required={'OK' if required_found else 'MISSING'})"
    )

    return {
        "suggested_mapping":  suggested,
        "confidence_scores":  conf_scores,
        "unmatched_columns":  unmatched,
        "all_columns":        actual_cols,
        "required_found":     required_found,
    }


def apply_mapping(
    df: pd.DataFrame,
    confirmed_mapping: Dict[str, Optional[str]],
) -> Dict[str, Optional[str]]:
    """
    Validate a confirmed mapping against a DataFrame's actual columns.
    Returns the mapping with any columns that no longer exist set to None.
    """
    valid_cols = set(df.columns)
    return {
        field: col if col in valid_cols else None
        for field, col in confirmed_mapping.items()
    }
