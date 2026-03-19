"""
text_utils.py
-------------
Text normalization utilities supporting Thai and English mixed content.
"""

import re
import unicodedata


# Common Thai keyword lists for quick lookup
_THAI_DEPOSIT_KEYWORDS = {"ฝาก", "รับฝาก", "เงินเข้า", "ยอดเงินเข้า"}
_THAI_WITHDRAW_KEYWORDS = {"ถอน", "จ่าย", "เงินออก", "ยอดเงินออก"}
_THAI_TRANSFER_KEYWORDS = {"โอน", "รับโอน", "โอนเงิน"}

_EN_DEPOSIT_KEYWORDS  = {"deposit", "cdm", "cash deposit"}
_EN_WITHDRAW_KEYWORDS = {"withdraw", "atm", "withdrawal"}
_EN_TRANSFER_KEYWORDS = {"transfer", "promptpay", "prompt pay", "trf", "interbank"}


def normalize_text(text: object) -> str:
    """
    Normalize a text value:
    - Convert to string
    - Strip leading/trailing whitespace
    - Collapse internal whitespace
    - Unicode normalize (NFC)

    Works correctly with Thai and English mixed input.
    """
    if text is None:
        return ""
    s = str(text).strip()
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r'\s+', ' ', s)
    return s


def text_lower(text: str) -> str:
    """Return lower-cased, stripped version of text."""
    return normalize_text(text).lower()


def contains_keyword(text: str, keywords: set) -> bool:
    """
    Check if text contains any keyword from a set.
    Case-insensitive for English; exact substring for Thai.
    """
    t = text_lower(text)
    for kw in keywords:
        if kw in t:
            return True
    return False


def detect_keyword_type(description: str) -> dict:
    """
    Scan description for deposit / withdraw / transfer keywords
    in both Thai and English.

    Returns
    -------
    dict:
        is_deposit  : bool
        is_withdraw : bool
        is_transfer : bool
        matched_keywords : list[str]
    """
    desc = normalize_text(description)
    desc_lower = desc.lower()

    matched: list[str] = []

    def _check(keywords: set, label: str) -> bool:
        for kw in keywords:
            if kw in desc_lower or kw in desc:
                matched.append(f"{label}:{kw}")
                return True
        return False

    is_deposit  = _check(_THAI_DEPOSIT_KEYWORDS,  "deposit-th")  or \
                  _check(_EN_DEPOSIT_KEYWORDS,     "deposit-en")
    is_withdraw = _check(_THAI_WITHDRAW_KEYWORDS,  "withdraw-th") or \
                  _check(_EN_WITHDRAW_KEYWORDS,     "withdraw-en")
    is_transfer = _check(_THAI_TRANSFER_KEYWORDS,  "transfer-th") or \
                  _check(_EN_TRANSFER_KEYWORDS,     "transfer-en")

    return {
        "is_deposit":  is_deposit,
        "is_withdraw": is_withdraw,
        "is_transfer": is_transfer,
        "matched_keywords": matched,
    }
