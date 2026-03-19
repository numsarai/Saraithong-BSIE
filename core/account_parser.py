"""
account_parser.py
-----------------
CRITICAL MODULE: Handles account number parsing, validation, and classification.

Bank account numbers MUST:
- Contain digits only
- Be EXACTLY 10 or 12 digits → VALID (type = "ACCOUNT")
- <10 digits only → "PARTIAL_ACCOUNT"
- Otherwise → "INVALID_ACCOUNT"
"""

import re
from typing import Optional, List, Set


# Regex patterns for extracting account numbers from free-text
_GROUPED_PATTERN = re.compile(r'\b\d{3}[-\s]\d{3}[-\s]\d{4}\b')        # 123-456-7890
_PLAIN_10_PATTERN = re.compile(r'\b\d{10}\b')                           # 10 contiguous digits
_PLAIN_12_PATTERN = re.compile(r'\b\d{12}\b')                           # 12 contiguous digits
_PARTIAL_PATTERN  = re.compile(r'\b\d{4,9}\b')                          # 4-9 digits (partial)

# Valid account lengths
VALID_LENGTHS = {10, 12}


def _safe_to_int_str(value: object) -> Optional[str]:
    """
    Safely convert a float/scientific-notation value (e.g. 1.23456789E+9)
    to a pure integer string WITHOUT losing information.

    Returns None if the value is not a numeric that can be cleanly converted.
    """
    try:
        f = float(str(value))
        if f != int(f):          # has decimal part → not a valid account candidate
            return None
        return str(int(f))
    except (ValueError, TypeError, OverflowError):
        return None


def _classify(digits: str) -> str:
    """Return the account type string based on digit-only string length."""
    n = len(digits)
    if n in VALID_LENGTHS:
        return "ACCOUNT"
    elif n < 10:
        return "PARTIAL_ACCOUNT"
    else:
        return "INVALID_ACCOUNT"


def parse_account(value: object) -> dict:
    """
    Parse and classify a single account number value.

    Parameters
    ----------
    value : object
        Raw value from a cell (str, int, float, None, etc.)

    Returns
    -------
    dict with keys:
        raw                 – original value as-is
        clean               – digits-only string (best effort)
        type                – "ACCOUNT" | "PARTIAL_ACCOUNT" | "INVALID_ACCOUNT"
        length              – length of clean string
        numeric_conversion  – True if value was numeric and was converted
    """
    raw = value
    numeric_conversion = False

    if value is None or (isinstance(value, float) and str(value).lower() == 'nan'):
        return {
            "raw": raw,
            "clean": "",
            "type": "INVALID_ACCOUNT",
            "length": 0,
            "numeric_conversion": False,
        }

    raw_str = str(value).strip()

    digits_only = ""
    # Only do numeric conversion if it's actually an int/float, OR if it's a scientific notation string. 
    # If it's a plain string of digits (possibly with leading zeros), DON'T do float conversion.
    is_scientific = isinstance(value, str) and bool(re.match(r'^-?\d+(\.\d+)?[eE][+\-]?\d+$', raw_str))
    is_float_str = isinstance(value, str) and bool(re.match(r'^-?\d+\.\d+$', raw_str))
    
    if isinstance(value, (int, float)) or is_scientific or is_float_str:
        converted = _safe_to_int_str(value)
        if converted is not None:
            digits_only = converted
            numeric_conversion = True
        else:
            # Has decimal part or other non-clean numeric format, strip non-digit chars
            digits_only = re.sub(r'\D', '', raw_str)
    else:
        # String path: it's just a string, preserve all digits including leading zeros
        digits_only = re.sub(r'\D', '', raw_str)

    if not digits_only:
        clean = ""
        acct_type = "INVALID_ACCOUNT"
        length = 0
    else:
        # If it's exactly 10 or 12 digits, it's valid as-is (preserves leading zeros)
        if len(digits_only) in VALID_LENGTHS:
            clean = digits_only
            acct_type = "ACCOUNT"
        else:
            # Otherwise, strip leading zeros and re-evaluate
            clean_val_stripped = digits_only.lstrip('0')
            if len(clean_val_stripped) in VALID_LENGTHS:
                clean = clean_val_stripped
                acct_type = "ACCOUNT"
            else:
                # If stripping didn't make it valid, classify based on the stripped length
                clean = clean_val_stripped
                acct_type = _classify(clean)
        length = len(clean)

    return {
        "raw": raw,
        "clean": clean,
        "type": acct_type,
        "length": length,
        "numeric_conversion": numeric_conversion,
    }


def extract_accounts_from_description(description: str) -> dict:
    """
    Use regex to extract potential account numbers embedded in a free-text
    description/narration field.

    Parameters
    ----------
    description : str
        Free-text transaction description (Thai or English).

    Returns
    -------
    dict with keys:
        valid_accounts    – list of 10/12-digit strings
        partial_accounts  – list of 4-9-digit strings
    """
    if not isinstance(description, str):
        description = str(description) if description is not None else ""

    valid: List[str] = []
    partial: List[str] = []

    # Grouped format (e.g. 123-456-7890) → strip separators
    for m in _GROUPED_PATTERN.finditer(description):
        digits = re.sub(r'\D', '', m.group())
        if len(digits) in VALID_LENGTHS:
            valid.append(digits)

    # 12-digit sequences
    for m in _PLAIN_12_PATTERN.finditer(description):
        digits = m.group()
        if digits not in valid:
            valid.append(digits)

    # 10-digit sequences (re-scan on description with grouped removed)
    for m in _PLAIN_10_PATTERN.finditer(description):
        digits = m.group()
        if digits not in valid:
            valid.append(digits)

    # Partial sequences (4-9 digits) – only if no full account found
    for m in _PARTIAL_PATTERN.finditer(description):
        digits = m.group()
        if digits not in valid:
            partial.append(digits)

    # Deduplicate preserving order
    seen: Set[str] = set()
    unique_valid: List[str] = []
    for acc in valid:
        if acc not in seen:
            seen.add(acc)
            unique_valid.append(acc)

    seen_p: Set[str] = set()
    unique_partial: List[str] = []
    for acc in partial:
        if acc not in seen_p:
            seen_p.add(acc)
            unique_partial.append(acc)

    return {
        "valid_accounts": unique_valid,
        "partial_accounts": unique_partial,
    }
