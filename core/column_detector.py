"""
column_detector.py
------------------
Detects and maps actual DataFrame column names to BSIE logical field names
using deterministic Thai/English alias dictionaries plus fuzzy matching.
"""

import json
import logging
import re
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

from paths import BUILTIN_CONFIG_DIR, CONFIG_DIR

logger = logging.getLogger(__name__)

# ── Standard English schema field → candidate aliases (Thai + English) ───
BASE_FIELD_KEYWORDS: Dict[str, List[str]] = {
    "date": [
        "วันที่", "date", "transaction date", "txn date", "trans date",
        "วันที่ทำรายการ", "วันทำรายการ", "วันรายการ", "tran date",
        "posting date", "value date", "effective date", "booking date",
        "วันที่รายการ", "วันที่ตัดบัญชี", "วันที่โอน", "วันที่ฝาก", "วันที่ถอน",
        "date posted", "entry date", "posted date", "process date",
    ],
    "time": [
        "เวลา", "time", "transaction time", "txn time", "เวลาทำรายการ",
        "trans time", "เวลารายการ", "เวลาตัดบัญชี", "เวลาที่ทำรายการ",
        "time posted", "posting time", "process time",
    ],
    "description": [
        "รายการ", "รายละเอียด", "ประเภทรายการ", "description", "narration",
        "remark", "details", "detail", "memo", "note", "particulars",
        "หมายเหตุ", "คำอธิบาย", "รายการ/หมายเหตุ",
        "transaction description", "txn description",
        "transaction details", "transaction detail", "รายการธุรกรรม",
        "รายการเคลื่อนไหว", "รายละเอียดรายการ", "คำบรรยายรายการ",
        "description/details", "narrative", "reference details",
    ],
    "amount": [
        "จำนวนเงิน", "amount", "net amount", "transaction amount",
        "debit/credit", "credit/debit", "amt", "จำนวน",
        "จำนวนเงิน(บาท)", "จำนวนเงิน บาท", "ยอดเงิน", "value",
        "ยอดรายการ", "จำนวนเงินสุทธิ", "net", "total amount",
        "transaction value", "movement amount",
    ],
    "debit": [
        "ถอน", "เดบิต", "debit", "withdrawal", "dr", "จำนวนเงินถอน",
        "ถอนเงิน", "รายการถอน", "withdraw", "out",
        "เงินออก", "ยอดถอน", "debit amount", "withdraw amount",
        "paid out", "money out", "outgoing amount",
    ],
    "credit": [
        "ฝาก", "เครดิต", "credit", "deposit", "cr", "จำนวนเงินฝาก",
        "ฝากเงิน", "เงินฝาก", "รายการฝาก", "in",
        "เงินเข้า", "ยอดฝาก", "credit amount", "deposit amount",
        "received amount", "money in", "incoming amount",
    ],
    "balance": [
        "ยอดคงเหลือ", "balance", "running balance", "outstanding",
        "คงเหลือ", "ยอดเงินคงเหลือ", "จำนวนเงินคงเหลือ", "bal",
        "avail balance", "available balance", "available",
        "closing balance", "ending balance", "remaining balance",
        "ยอดคงเหลือหลังรายการ", "ยอดหลังทำรายการ", "balance after transaction",
    ],
    "channel": [
        "ช่องทาง", "channel", "transaction channel", "medium", "via",
        "mode", "source", "ช่องทางทำรายการ", "service channel",
        "service type", "platform", "device", "terminal", "ช่องทางบริการ",
    ],
    "counterparty_account": [
        "บัญชีคู่โอน", "เลขที่บัญชีคู่สัญญา", "บัญชีคู่สัญญา",
        "counterparty account", "to/from account",
        "ref account", "beneficiary account", "บัญชีผู้โอน/รับโอน",
        "บัญชีปลายทาง", "บัญชีผู้รับโอน", "บัญชีผู้โอน",
        "from account", "to account", "account no", "acc no",
        "account number", "ref no", "reference account",
        "เลขที่บัญชี", "เลขบัญชี", "หมายเลขบัญชี", "เลขที่บัญชีปลายทาง",
        "หมายเลขบัญชีปลายทาง", "หมายเลขบัญชีต้นทาง", "เลขที่บัญชีผู้รับโอน",
        "เลขที่บัญชีผู้โอน", "beneficiary acc no", "receiver account",
        "sender account", "destination account", "source account",
    ],
    "counterparty_name": [
        "ชื่อคู่โอน", "ชื่อคู่สัญญา", "counterparty name", "to/from name",
        "beneficiary name", "ชื่อผู้โอน/รับโอน", "ชื่อผู้รับโอน",
        "ชื่อผู้โอน", "payee", "payer", "receiver name",
        "sender name", "beneficiary", "account name", "ชื่อบัญชี",
        "ชื่อบัญชีปลายทาง", "ชื่อบัญชีต้นทาง", "ชื่อผู้รับเงิน",
        "ชื่อผู้จ่าย", "ชื่อผู้โอนเงิน", "ชื่อผู้รับโอนเงิน",
    ],
}

FIELD_ALIAS_CROSSWALK: Dict[str, List[str]] = {
    "counterparty_account": ["sender_account", "receiver_account"],
    "counterparty_name": ["sender_name", "receiver_name"],
}

# Priority order matters. Map explicit debit/credit layouts before generic amount.
REQUIRED_FIELDS  = ["date", "description"]
OPTIONAL_FIELDS  = ["time", "debit", "credit", "amount", "balance", "channel",
                    "counterparty_account", "counterparty_name"]
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS


def _norm(text: str) -> str:
    """Normalize a header for deterministic Thai/English matching."""
    text = str(text or "").strip().lower()
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[_/\\|:;,+\-]+", " ", text)
    text = re.sub(r"[()\[\]{}]+", " ", text)
    text = re.sub(r"[^0-9a-z\u0E00-\u0E7F ]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _compact(text: str) -> str:
    """Compact normalized text for punctuation-insensitive exact matching."""
    return _norm(text).replace(" ", "")


def _tokenize(text: str) -> set[str]:
    """Tokenize normalized text into non-empty words."""
    return {tok for tok in _norm(text).split(" ") if tok}


def _similarity(a: str, b: str) -> float:
    """Fuzzy string similarity, 0–1."""
    try:
        from rapidfuzz import fuzz
        return fuzz.token_set_ratio(a, b) / 100.0
    except ImportError:
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a, b).ratio()


@lru_cache(maxsize=1)
def _load_config_aliases() -> Dict[str, List[str]]:
    """Load alias supplements from built-in and custom bank configs."""
    merged: Dict[str, List[str]] = {}
    for config_dir in (BUILTIN_CONFIG_DIR, CONFIG_DIR):
        if not config_dir.exists():
            continue
        for path in sorted(config_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                logger.debug("Skipping malformed config aliases from %s", path)
                continue
            for field, aliases in payload.get("column_mapping", {}).items():
                if isinstance(aliases, list):
                    merged.setdefault(field, []).extend(str(a) for a in aliases if str(a).strip())
    return merged


def get_field_aliases(field: str) -> List[str]:
    """Return the full Thai/English alias list for one standard schema field."""
    aliases: list[str] = list(BASE_FIELD_KEYWORDS.get(field, []))
    config_aliases = _load_config_aliases()
    aliases.extend(config_aliases.get(field, []))
    for related_field in FIELD_ALIAS_CROSSWALK.get(field, []):
        aliases.extend(config_aliases.get(related_field, []))

    deduped: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        normalized = _norm(alias)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(alias)
    return deduped


def _score_alias_match(alias: str, header: str) -> float:
    """Return a deterministic similarity score between alias and actual header."""
    alias_norm = _norm(alias)
    header_norm = _norm(header)
    if not alias_norm or not header_norm:
        return 0.0
    if alias_norm == header_norm:
        return 1.0

    alias_compact = _compact(alias)
    header_compact = _compact(header)
    length_ratio = (
        min(len(alias_compact), len(header_compact)) / max(len(alias_compact), len(header_compact))
        if alias_compact and header_compact else 0.0
    )
    if alias_compact == header_compact:
        return 0.99

    alias_tokens = _tokenize(alias)
    header_tokens = _tokenize(header)
    if alias_tokens and header_tokens:
        if (
            (alias_tokens.issubset(header_tokens) or header_tokens.issubset(alias_tokens))
            and (length_ratio >= 0.65 or min(len(alias_tokens), len(header_tokens)) >= 2)
        ):
            return 0.94

    if alias_compact and header_compact and (
        alias_compact in header_compact or header_compact in alias_compact
    ) and length_ratio >= 0.65:
        return 0.90

    fuzzy = _similarity(alias_norm, header_norm)
    if alias_tokens and header_tokens:
        token_overlap = len(alias_tokens & header_tokens) / max(len(alias_tokens), len(header_tokens))
        fuzzy = max(fuzzy, round((fuzzy * 0.7) + (token_overlap * 0.3), 3))
    if length_ratio < 0.55 and not (alias_tokens & header_tokens):
        fuzzy = min(fuzzy, 0.79)
    return fuzzy


def best_match_for_aliases(
    actual_columns: Sequence[str],
    aliases: Sequence[str],
    used_actual: Optional[set[str]] = None,
    threshold: float = 0.60,
) -> Tuple[Optional[str], float]:
    """Find the best available actual column for the given alias list."""
    used_actual = used_actual or set()
    best_col: Optional[str] = None
    best_score = 0.0

    for col in actual_columns:
        if col in used_actual:
            continue
        for alias in aliases:
            score = _score_alias_match(alias, col)
            if score > best_score:
                best_score = score
                best_col = col
                if best_score >= 0.99:
                    return best_col, best_score

    if best_score >= threshold:
        return best_col, round(best_score, 3)
    return None, 0.0


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

    suggested:   Dict[str, Optional[str]] = {}
    conf_scores: Dict[str, float]         = {}
    used_actual: set                       = set()

    def _try_map(field: str) -> None:
        if field == "amount" and suggested.get("debit") and suggested.get("credit"):
            suggested[field] = None
            conf_scores[field] = 0.0
            return
        aliases = get_field_aliases(field)
        best_col, best_score = best_match_for_aliases(actual_cols, aliases, used_actual, threshold)
        if best_col:
            suggested[field]   = best_col
            conf_scores[field] = float(best_score)
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
