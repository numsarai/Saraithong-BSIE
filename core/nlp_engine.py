"""
nlp_engine.py
-------------
Pattern-based NLP engine for Thai/English financial text.
Extracts counterparty information and classifies transaction types.
No heavy ML dependencies — uses regex + keyword matching only.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Thai title / entity prefixes ───────────────────────────────────────────
_THAI_PREFIXES = [
    "นาย", "นาง", "นางสาว", "น.ส.",
    "ด.ช.", "ด.ญ.",
    "พล.อ.", "พล.ต.", "พล.ท.", "พล.ร.ต.", "พ.ต.อ.", "พ.ต.ท.", "พ.ต.ต.",
    "บริษัท", "บจก.", "บมจ.", "หจก.", "ห้างหุ้นส่วน",
    "มูลนิธิ", "สมาคม", "องค์กร", "หน่วยงาน",
]

_PREFIX_ALT = "|".join(re.escape(p) for p in sorted(_THAI_PREFIXES, key=len, reverse=True))

# Thai name: prefix + Thai-Unicode chars (2–40 chars, optional spaces)
_THAI_NAME_RE = re.compile(
    rf'(?:{_PREFIX_ALT})\s*[\u0E00-\u0E7F][\u0E00-\u0E7F\s]{{1,39}}',
    re.UNICODE,
)

# English name: 2+ capitalised words (Title Case), not pure uppercase abbreviations
_EN_NAME_RE = re.compile(
    r'\b([A-Z][a-z]{1,25})(?:\s+[A-Z][a-z]{1,25}){1,4}\b'
)

# Thai mobile numbers: 06x / 08x / 09x + 7 more digits
_PHONE_RE = re.compile(r'\b0[689]\d{8}\b')

# PromptPay markers
_PROMPTPAY_RE = re.compile(
    r'\b(?:promptpay|พร้อมเพย์|prompt\s*pay|pp\s*id)\b'
    r'|@[\w.\-]+',
    re.IGNORECASE | re.UNICODE,
)

# Thai National ID: 13 digits, optionally formatted as X-XXXX-XXXXX-XX-X
_NATIONAL_ID_RE = re.compile(
    r'\b\d{1}[-\s]?\d{4}[-\s]?\d{5}[-\s]?\d{2}[-\s]?\d{1}\b'
)

# Account numbers embedded in text
_ACCT_GROUPED_RE = re.compile(r'\b\d{3}[-\s]\d{3}[-\s]\d{4}\b')
_ACCT_PLAIN_RE   = re.compile(r'\b\d{10,12}\b')

# ── Transaction type patterns ──────────────────────────────────────────────
_TRANSFER_RE = re.compile(
    r'โอน|transfer|trf|interbk|interbank|internet\s*banking|'
    r'promptpay|พร้อมเพย์|mobile\s*banking|i-banking|bill\s*pay|'
    r'scan\s*&\s*pay|qr\s*pay|qr\s*code',
    re.IGNORECASE | re.UNICODE,
)
_DEPOSIT_RE = re.compile(
    r'ฝาก|cdm|cash\s*deposit|deposit|เงินเข้า|รับโอน|cash\s*in|'
    r'bill\s*payment\s*receive',
    re.IGNORECASE | re.UNICODE,
)
_WITHDRAW_RE = re.compile(
    r'ถอน|atm|cash\s*withdrawal|withdrawal|withdraw|เงินออก|cash\s*out',
    re.IGNORECASE | re.UNICODE,
)
_FEE_RE = re.compile(
    r'ค่าธรรมเนียม|fee|charge|service\s*fee|commission|ค่าบริการ',
    re.IGNORECASE | re.UNICODE,
)
_SALARY_RE = re.compile(
    r'เงินเดือน|salary|payroll|bonus|เงินโบนัส',
    re.IGNORECASE | re.UNICODE,
)


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

def extract_counterparty(text: str) -> Dict:
    """
    Extract counterparty identifiers from a transaction description.

    Parameters
    ----------
    text : transaction description (Thai, English, or mixed)

    Returns
    -------
    {
        "thai_names"    : [str]  – Thai names found
        "english_names" : [str]  – English names found
        "phone_numbers" : [str]  – mobile numbers found
        "promptpay"     : bool   – PromptPay indicator detected
        "accounts"      : [str]  – 10–12 digit account numbers
        "best_name"     : str|None – top counterparty name candidate
    }
    """
    if not text or not isinstance(text, str):
        return {
            "thai_names": [], "english_names": [], "phone_numbers": [],
            "promptpay": False, "accounts": [], "best_name": None,
        }

    thai_names = [m.group().strip() for m in _THAI_NAME_RE.finditer(text)]

    en_raw = _EN_NAME_RE.findall(text)
    # Filter out all-caps strings and known financial keywords
    _skip = {"ATM", "CDM", "SCB", "KTB", "BBL", "BAY", "TTB", "GSB", "KBANK",
             "THB", "USD", "EUR", "NLP", "IBM", "QR"}
    en_names = [
        " ".join(parts) if isinstance(parts, tuple) else parts
        for parts in en_raw
        if (parts if isinstance(parts, str) else " ".join(parts)) not in _skip
    ]

    phones = _PHONE_RE.findall(text)
    is_promptpay = bool(_PROMPTPAY_RE.search(text))

    # Detect Thai National IDs (13 digits)
    national_ids: List[str] = []
    for m in _NATIONAL_ID_RE.finditer(text):
        digits = re.sub(r'\D', '', m.group())
        if len(digits) == 13 and digits not in national_ids:
            national_ids.append(digits)

    # Collect account numbers from text
    accounts: List[str] = []
    for m in _ACCT_GROUPED_RE.finditer(text):
        digits = re.sub(r'\D', '', m.group())
        if digits not in accounts:
            accounts.append(digits)
    for m in _ACCT_PLAIN_RE.finditer(text):
        d = m.group()
        if d not in accounts:
            accounts.append(d)

    best_name = thai_names[0] if thai_names else (en_names[0] if en_names else None)

    return {
        "thai_names":    thai_names,
        "english_names": en_names,
        "phone_numbers": phones,
        "national_ids":  national_ids,
        "promptpay":     is_promptpay,
        "accounts":      accounts,
        "best_name":     best_name,
    }


def classify_transaction_nlp(text: str) -> Tuple[str, float]:
    """
    Classify a transaction description using pattern matching.

    Returns
    -------
    (type_hint, confidence)
    type_hint: "transfer" | "deposit" | "withdraw" | "fee" | "salary" | "unknown"
    """
    if not text or not isinstance(text, str):
        return "unknown", 0.50

    t = text.strip()

    if _FEE_RE.search(t):
        return "fee", 0.82

    if _SALARY_RE.search(t):
        return "salary", 0.85

    if _TRANSFER_RE.search(t):
        return "transfer", 0.87

    if _DEPOSIT_RE.search(t):
        return "deposit", 0.85

    if _WITHDRAW_RE.search(t):
        return "withdraw", 0.88

    return "unknown", 0.55


def enrich_transaction_row(row: dict) -> dict:
    """
    Run NLP on a transaction row's description and augment it with:
    - nlp_best_name   : inferred counterparty name
    - nlp_type_hint   : NLP-based transaction type
    - nlp_confidence  : NLP confidence

    Parameters
    ----------
    row : dict with at least "description" key

    Returns
    -------
    row dict with nlp_* fields added
    """
    desc = str(row.get("description", "") or "")
    cp   = extract_counterparty(desc)
    hint, conf = classify_transaction_nlp(desc)

    row["nlp_best_name"]  = cp["best_name"] or ""
    row["nlp_type_hint"]  = hint
    row["nlp_confidence"] = conf
    row["nlp_promptpay"]  = cp["promptpay"]
    row["nlp_accounts"]   = ",".join(cp["accounts"])
    row["nlp_national_ids"] = ",".join(cp.get("national_ids", []))
    return row
