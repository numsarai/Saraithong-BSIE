"""
normalizer.py
-------------
Applies bank-config column mapping to a raw DataFrame, cleans amounts,
normalises dates/times, and calls account_parser on account columns.

Supports three format types:
  standard      – single amount/debit/credit + optional counterparty columns
  dual_account  – separate sender/receiver account+name columns (KBANK, SCB)
                  Direction determined by debit/credit values.
  ktb_transfer  – KTB transfer log: unsigned amount, direction from blank side
"""

import re
import logging
from typing import Optional

import pandas as pd

from core.loader import detect_column
from core.account_parser import parse_account, extract_accounts_from_description
from utils.text_utils import normalize_text
from utils.date_utils import parse_date, parse_time

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Amount helpers
# ---------------------------------------------------------------------------

def _clean_amount(value: object) -> Optional[float]:
    """
    Convert a raw amount string/number to signed float.

    Handles:
    - Commas as thousands separators ("1,234.56")
    - Thai minus signs or parentheses for negatives
    - Already numeric values
    """
    if value is None:
        return None
    s = str(value).strip()
    if s.lower() in {"nan", "none", "-", ""}:
        return None

    # Remove commas (thousands separators) and currency symbols
    s = re.sub(r'[,\u0e3f฿$]', '', s)   # \u0e3f = ฿

    # Parentheses indicate negative: (1234.56) → -1234.56
    m = re.match(r'^\(([0-9.]+)\)$', s.strip())
    if m:
        s = "-" + m.group(1)

    try:
        return float(s)
    except ValueError:
        logger.debug(f"Could not parse amount: {value!r}")
        return None


def _resolve_mapping_columns(df, mapping):
    """Resolve logical fields to actual DataFrame columns once per normalize call."""
    resolved = {}
    for field, aliases in mapping.items():
        resolved[field] = detect_column(df, aliases) if aliases else None
    return resolved


def _get_col_value(row, mapping, field):
    """Get raw value for a logical field from a resolved mapping."""
    col = mapping.get(field)
    if not col:
        return None
    return row.get(col)


def _parse_cp_account(val, subject_account):
    """Parse a counterparty account value; return parsed dict."""
    if not val or (isinstance(val, float) and pd.isna(val)):
        return {"raw": "", "clean": "", "type": "UNKNOWN"}
    p = parse_account(val)
    # Accept ACCOUNT or PARTIAL even if it equals subject (will show as self-transfer)
    return p


# ---------------------------------------------------------------------------
# Format: dual_account (KBANK, SCB)
# ---------------------------------------------------------------------------

def _normalize_dual_account(row, df, mapping, subject_account, subject_name, bank_name, currency):
    """
    Normalise a single row for dual_account format (KBANK, SCB).

    Direction logic:
      debit  > 0 → OUT  → subject sent money  → counterparty = receiver side
      credit > 0 → IN   → subject received    → counterparty = sender side

    Counterparty name fallback:
      1. name from sender/receiver name column
      2. account number from sender/receiver account column
      3. ""
    """
    def get(field):
        return _get_col_value(row, mapping, field)

    rec = {}

    # ── Date / Time ─────────────────────────────────────────────────────────
    raw_date = get("date")
    raw_time = get("time")
    rec["date"] = str(parse_date(raw_date)) if parse_date(raw_date) else ""
    rec["time"] = parse_time(raw_time) or ""

    # ── Description ─────────────────────────────────────────────────────────
    rec["description"] = normalize_text(get("description"))

    # ── Amount via debit/credit ──────────────────────────────────────────────
    raw_debit  = _clean_amount(get("debit"))  or 0.0
    raw_credit = _clean_amount(get("credit")) or 0.0
    amount = round(raw_credit - raw_debit, 6) if (raw_debit or raw_credit) else None
    rec["amount"]   = amount
    rec["currency"] = currency

    # ── Balance / Channel ────────────────────────────────────────────────────
    rec["balance"] = _clean_amount(get("balance"))
    rec["channel"] = normalize_text(get("channel"))

    # ── Subject ──────────────────────────────────────────────────────────────
    rec["subject_account"] = subject_account
    rec["subject_name"]    = subject_name
    rec["bank"]            = bank_name

    # ── Direction determines which side is the counterparty ──────────────────
    if raw_debit > 0:
        direction = "OUT"
        cp_acc_raw  = get("receiver_account")
        cp_name_raw = get("receiver_name")
    elif raw_credit > 0:
        direction = "IN"
        cp_acc_raw  = get("sender_account")
        cp_name_raw = get("sender_name")
    else:
        direction = "UNKNOWN"
        # Try both sides; pick non-subject
        cp_acc_raw  = get("receiver_account") or get("sender_account")
        cp_name_raw = get("receiver_name")    or get("sender_name")

    rec["direction"] = direction

    # ── Parse counterparty account ───────────────────────────────────────────
    parsed_cp = _parse_cp_account(cp_acc_raw, subject_account)
    rec["raw_account_value"]   = parsed_cp["raw"]
    rec["parsed_account_type"] = parsed_cp["type"]

    if parsed_cp["type"] == "ACCOUNT":
        rec["counterparty_account"] = parsed_cp["clean"]
        rec["partial_account"]      = ""
    elif parsed_cp["type"] == "PARTIAL_ACCOUNT":
        rec["counterparty_account"] = ""
        rec["partial_account"]      = parsed_cp["clean"]
    else:
        rec["counterparty_account"] = ""
        rec["partial_account"]      = ""

    # ── Counterparty name ────────────────────────────────────────────────────
    cp_name = normalize_text(cp_name_raw) or ""
    # Reject if name looks like subject name or is the subject account number
    if cp_name and (cp_name == subject_name or cp_name == subject_account):
        cp_name = ""
    rec["counterparty_name"] = cp_name

    # ── Extract accounts from description (augment missing account) ──────────
    extracted = extract_accounts_from_description(rec["description"])
    if not rec["counterparty_account"] and extracted["valid_accounts"]:
        rec["counterparty_account"] = extracted["valid_accounts"][0]
        rec["parsed_account_type"]  = "ACCOUNT"
    if not rec["partial_account"] and extracted["partial_accounts"]:
        rec["partial_account"] = extracted["partial_accounts"][0]

    # ── Fallback: use account number as name when no name available ──────────
    if not rec["counterparty_name"]:
        rec["counterparty_name"] = (
            rec["counterparty_account"]
            or rec["partial_account"]
            or ""
        )

    return rec


# ---------------------------------------------------------------------------
# Format: standard
# ---------------------------------------------------------------------------

def _normalize_standard(row, df, mapping, subject_account, subject_name, bank_name, currency, amount_mode):
    """Normalise a single row for standard format."""
    def get(field):
        return _get_col_value(row, mapping, field)

    rec = {}

    # ── Date / Time ─────────────────────────────────────────────────────────
    raw_date = get("date")
    raw_time = get("time")
    rec["date"] = str(parse_date(raw_date)) if parse_date(raw_date) else ""
    rec["time"] = parse_time(raw_time) or ""

    # ── Description ─────────────────────────────────────────────────────────
    rec["description"] = normalize_text(get("description"))

    # ── Amount ──────────────────────────────────────────────────────────────
    if amount_mode == "debit_credit":
        raw_debit  = _clean_amount(get("debit"))  or 0.0
        raw_credit = _clean_amount(get("credit")) or 0.0
        amount = round(raw_credit - raw_debit, 6)
        if not amount and mapping.get("direction_marker"):
            raw_amount = _clean_amount(get("amount"))
            marker = normalize_text(get("direction_marker")).lower()
            if raw_amount is not None:
                if marker in {"credit", "cr", "in", "deposit"}:
                    amount = abs(raw_amount)
                elif marker in {"debit", "dr", "out", "withdraw"}:
                    amount = -abs(raw_amount)
    else:
        amount = _clean_amount(get("amount"))
        if amount is None:
            raw_debit  = _clean_amount(get("debit"))  or 0.0
            raw_credit = _clean_amount(get("credit")) or 0.0
            amount = round(raw_credit - raw_debit, 6) if (raw_debit or raw_credit) else None

    rec["amount"]   = amount
    rec["currency"] = currency

    # ── Balance / Channel ────────────────────────────────────────────────────
    rec["balance"] = _clean_amount(get("balance"))
    rec["channel"] = normalize_text(get("channel"))

    # ── Subject ──────────────────────────────────────────────────────────────
    rec["subject_account"] = subject_account
    rec["subject_name"]    = subject_name
    rec["bank"]            = bank_name

    # ── Counterparty account ─────────────────────────────────────────────────
    parsed_cp = {"raw": "", "clean": "", "type": "UNKNOWN"}
    cp_col = mapping.get("counterparty_account")
    if cp_col:
        val = row.get(cp_col)
        if val and not (isinstance(val, float) and pd.isna(val)):
            parsed_cp = parse_account(val)

    rec["raw_account_value"]   = parsed_cp["raw"]
    rec["parsed_account_type"] = parsed_cp["type"]

    if parsed_cp["type"] == "ACCOUNT":
        rec["counterparty_account"] = parsed_cp["clean"]
        rec["partial_account"]      = ""
    elif parsed_cp["type"] == "PARTIAL_ACCOUNT":
        rec["counterparty_account"] = ""
        rec["partial_account"]      = parsed_cp["clean"]
    else:
        rec["counterparty_account"] = ""
        rec["partial_account"]      = ""

    # ── Counterparty name ────────────────────────────────────────────────────
    best_name = ""
    name_col = mapping.get("counterparty_name")
    if name_col:
        val = normalize_text(row.get(name_col))
        if val and val != subject_name:
            best_name = val
        elif val:
            best_name = val or ""

    rec["counterparty_name"] = best_name

    # ── Extract accounts from description ────────────────────────────────────
    extracted = extract_accounts_from_description(rec["description"])
    if not rec["counterparty_account"] and extracted["valid_accounts"]:
        rec["counterparty_account"] = extracted["valid_accounts"][0]
        rec["parsed_account_type"]  = "ACCOUNT"
    if not rec["partial_account"] and extracted["partial_accounts"]:
        rec["partial_account"] = extracted["partial_accounts"][0]

    # ── Fallback: account number as name ────────────────────────────────────
    if not rec["counterparty_name"]:
        rec["counterparty_name"] = (
            rec["counterparty_account"]
            or rec["partial_account"]
            or ""
        )

    # ── Direction ────────────────────────────────────────────────────────────
    if rec["amount"] is not None:
        rec["direction"] = "IN" if rec["amount"] > 0 else "OUT"
    else:
        rec["direction"] = "UNKNOWN"

    # ── Sender/receiver fallback for bank formats with both sides ───────────
    if (
        not rec["counterparty_account"]
        and not rec["partial_account"]
        and not rec["counterparty_name"]
        and (mapping.get("sender_account") or mapping.get("receiver_account"))
    ):
        if rec["direction"] == "IN":
            cp_acc_raw = get("sender_account")
            cp_name_raw = get("sender_name")
        elif rec["direction"] == "OUT":
            cp_acc_raw = get("receiver_account")
            cp_name_raw = get("receiver_name")
        else:
            cp_acc_raw = get("receiver_account") or get("sender_account")
            cp_name_raw = get("receiver_name") or get("sender_name")

        parsed_cp = _parse_cp_account(cp_acc_raw, subject_account)
        rec["raw_account_value"] = parsed_cp["raw"]
        rec["parsed_account_type"] = parsed_cp["type"]
        if parsed_cp["type"] == "ACCOUNT":
            rec["counterparty_account"] = parsed_cp["clean"]
        elif parsed_cp["type"] == "PARTIAL_ACCOUNT":
            rec["partial_account"] = parsed_cp["clean"]

        cp_name = normalize_text(cp_name_raw) or ""
        if cp_name and (cp_name == subject_name or cp_name == subject_account):
            cp_name = ""
        rec["counterparty_name"] = cp_name or rec["counterparty_account"] or rec["partial_account"] or ""

    return rec


# ---------------------------------------------------------------------------
# Format: ktb_transfer (KTB transfer log — unsigned amounts, direction from side)
# ---------------------------------------------------------------------------

def _normalize_ktb_transfer(row, df, mapping, subject_account, subject_name, bank_name, currency):
    """
    Normalise a single row for KTB transfer format.

    The KTB log has separate sender_account / receiver_account columns.
    Direction is determined by comparing each side to the subject_account:
      sender_account == subject  → OUT (subject sent money)
      receiver_account == subject → IN  (subject received money)
      Neither matches → UNKNOWN (use sender side as counterparty)
    Amount is always unsigned (positive); direction sign is derived from above.
    """
    def get(field):
        return _get_col_value(row, mapping, field)

    rec = {}

    # ── Date / Time ──────────────────────────────────────────────────────
    raw_date = get("date")
    raw_time = get("time")
    rec["date"] = str(parse_date(raw_date)) if parse_date(raw_date) else ""
    rec["time"] = parse_time(raw_time) or ""

    # ── Description ──────────────────────────────────────────────────────
    rec["description"] = normalize_text(get("description"))

    # ── Amount ───────────────────────────────────────────────────────────
    amount = _clean_amount(get("amount"))
    rec["amount"]   = amount
    rec["currency"] = currency

    # ── Balance / Channel ────────────────────────────────────────────────
    rec["balance"] = _clean_amount(get("balance"))
    rec["channel"] = normalize_text(get("channel"))

    # ── Subject ──────────────────────────────────────────────────────────
    rec["subject_account"] = subject_account
    rec["subject_name"]    = subject_name
    rec["bank"]            = bank_name

    # ── Parse both sides ─────────────────────────────────────────────────
    sender_raw   = get("sender_account")
    receiver_raw = get("receiver_account")

    sender_parsed   = _parse_cp_account(sender_raw,   subject_account)
    receiver_parsed = _parse_cp_account(receiver_raw, subject_account)

    sender_clean   = sender_parsed.get("clean", "")   if sender_parsed["type"] == "ACCOUNT" else ""
    receiver_clean = receiver_parsed.get("clean", "") if receiver_parsed["type"] == "ACCOUNT" else ""

    # ── Determine direction ───────────────────────────────────────────────
    if sender_clean == subject_account:
        direction   = "OUT"
        cp_acc      = receiver_clean
        cp_name_raw = get("receiver_name") if hasattr(get, "__call__") else None
    elif receiver_clean == subject_account:
        direction   = "IN"
        cp_acc      = sender_clean
        cp_name_raw = get("sender_name") if hasattr(get, "__call__") else None
    else:
        # Neither side matches subject — record as UNKNOWN, use receiver as counterparty
        direction   = "UNKNOWN"
        cp_acc      = receiver_clean or sender_clean
        cp_name_raw = None

    # Re-fetch names properly using the mapping function
    if direction == "OUT":
        cp_name_raw = _get_col_value(row, mapping, "receiver_name")
    elif direction == "IN":
        cp_name_raw = _get_col_value(row, mapping, "sender_name")
    else:
        cp_name_raw = _get_col_value(row, mapping, "receiver_name") or _get_col_value(row, mapping, "sender_name")

    rec["direction"] = direction

    # ── Counterparty ─────────────────────────────────────────────────────
    if cp_acc:
        rec["counterparty_account"] = cp_acc
        rec["partial_account"]      = ""
        rec["raw_account_value"]    = cp_acc
        rec["parsed_account_type"]  = "ACCOUNT"
    else:
        # Try partial
        if direction == "OUT" and receiver_parsed["type"] == "PARTIAL_ACCOUNT":
            rec["counterparty_account"] = ""
            rec["partial_account"]      = receiver_parsed["clean"]
        elif direction == "IN" and sender_parsed["type"] == "PARTIAL_ACCOUNT":
            rec["counterparty_account"] = ""
            rec["partial_account"]      = sender_parsed["clean"]
        else:
            rec["counterparty_account"] = ""
            rec["partial_account"]      = ""
        rec["raw_account_value"]   = ""
        rec["parsed_account_type"] = "UNKNOWN"

    # ── Counterparty name ────────────────────────────────────────────────
    cp_name = normalize_text(cp_name_raw) or ""
    if cp_name and (cp_name == subject_name or cp_name == subject_account):
        cp_name = ""
    rec["counterparty_name"] = cp_name

    # ── Fallback: account as name ────────────────────────────────────────
    if not rec["counterparty_name"]:
        rec["counterparty_name"] = (
            rec["counterparty_account"]
            or rec.get("partial_account", "")
            or ""
        )

    # ── Adjust amount sign to match direction ────────────────────────────
    if rec["amount"] is not None:
        if direction == "OUT" and rec["amount"] > 0:
            rec["amount"] = -rec["amount"]
        elif direction == "IN" and rec["amount"] < 0:
            rec["amount"] = -rec["amount"]

    return rec


def _normalize_direction_marker(row, df, mapping, subject_account, subject_name, bank_name, currency):
    """
    Normalize a format with one amount column plus a separate direction marker.

    Example:
      amount column:      380.00
      direction marker:   Debit / Credit
    """
    def get(field):
        return _get_col_value(row, mapping, field)

    rec = {}

    raw_date = get("date")
    raw_time = get("time")
    rec["date"] = str(parse_date(raw_date)) if parse_date(raw_date) else ""
    rec["time"] = parse_time(raw_time) or ""
    rec["description"] = normalize_text(get("description"))

    raw_amount = _clean_amount(get("amount"))
    marker = normalize_text(get("direction_marker")).lower()
    direction = "UNKNOWN"
    signed_amount = raw_amount

    if marker in {"credit", "cr", "in", "deposit"}:
        direction = "IN"
        signed_amount = abs(raw_amount) if raw_amount is not None else None
    elif marker in {"debit", "dr", "out", "withdraw"}:
        direction = "OUT"
        signed_amount = -abs(raw_amount) if raw_amount is not None else None

    rec["amount"] = signed_amount
    rec["currency"] = currency
    rec["balance"] = _clean_amount(get("balance"))
    rec["channel"] = normalize_text(get("channel"))
    rec["subject_account"] = subject_account
    rec["subject_name"] = subject_name
    rec["bank"] = bank_name
    rec["direction"] = direction

    sender_acc_raw = get("sender_account")
    receiver_acc_raw = get("receiver_account")
    sender_name_raw = get("sender_name")
    receiver_name_raw = get("receiver_name")

    if direction == "IN":
        cp_acc_raw = sender_acc_raw
        cp_name_raw = sender_name_raw
    elif direction == "OUT":
        cp_acc_raw = receiver_acc_raw
        cp_name_raw = receiver_name_raw
    else:
        cp_acc_raw = receiver_acc_raw or sender_acc_raw
        cp_name_raw = receiver_name_raw or sender_name_raw

    parsed_cp = _parse_cp_account(cp_acc_raw, subject_account)
    rec["raw_account_value"] = parsed_cp["raw"]
    rec["parsed_account_type"] = parsed_cp["type"]

    if parsed_cp["type"] == "ACCOUNT":
        rec["counterparty_account"] = parsed_cp["clean"]
        rec["partial_account"] = ""
    elif parsed_cp["type"] == "PARTIAL_ACCOUNT":
        rec["counterparty_account"] = ""
        rec["partial_account"] = parsed_cp["clean"]
    else:
        rec["counterparty_account"] = ""
        rec["partial_account"] = ""

    cp_name = normalize_text(cp_name_raw) or ""
    if cp_name and (cp_name == subject_name or cp_name == subject_account):
        cp_name = ""
    rec["counterparty_name"] = cp_name

    extracted = extract_accounts_from_description(rec["description"])
    if not rec["counterparty_account"] and extracted["valid_accounts"]:
        rec["counterparty_account"] = extracted["valid_accounts"][0]
        rec["parsed_account_type"] = "ACCOUNT"
    if not rec["partial_account"] and extracted["partial_accounts"]:
        rec["partial_account"] = extracted["partial_accounts"][0]

    if not rec["counterparty_name"]:
        rec["counterparty_name"] = rec["counterparty_account"] or rec["partial_account"] or ""

    return rec


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def normalize(
    df: pd.DataFrame,
    bank_config: dict,
    subject_account: str,
    subject_name: str = "",
    source_file: str = "",
) -> pd.DataFrame:
    """
    Apply config-driven column mapping; clean, parse, and standardise all fields.

    Dispatches to the correct normaliser based on bank_config["format_type"].

    Parameters
    ----------
    df               : raw DataFrame from loader
    bank_config      : parsed bank config JSON
    subject_account  : the account number under investigation
    subject_name     : optional name of account holder
    source_file      : original filename for traceability

    Returns
    -------
    pd.DataFrame with STANDARD schema columns
    """
    mapping:     dict = bank_config.get("column_mapping", {})
    resolved_mapping = _resolve_mapping_columns(df, mapping)
    bank_name:   str  = bank_config.get("bank_name", "UNKNOWN")
    currency:    str  = bank_config.get("currency", "THB")
    amount_mode: str  = bank_config.get("amount_mode", "signed")
    fmt_type:    str  = bank_config.get("format_type", "standard")

    records = []

    for idx, row in df.iterrows():
        try:
            if fmt_type == "dual_account":
                rec = _normalize_dual_account(
                    row, df, resolved_mapping, subject_account, subject_name, bank_name, currency
                )
            elif fmt_type == "direction_marker":
                rec = _normalize_direction_marker(
                    row, df, resolved_mapping, subject_account, subject_name, bank_name, currency
                )
            elif fmt_type == "ktb_transfer":
                rec = _normalize_ktb_transfer(
                    row, df, resolved_mapping, subject_account, subject_name, bank_name, currency
                )
            else:
                rec = _normalize_standard(
                    row, df, resolved_mapping, subject_account, subject_name, bank_name, currency, amount_mode
                )
        except Exception as e:
            logger.debug(f"Row {idx} normalisation error: {e}")
            continue

        # ── Traceability ─────────────────────────────────────────────────────
        rec["_raw_idx"]    = idx
        rec["source_file"] = source_file or ""
        rec["row_number"]  = int(idx) + 2  # +2: 1-indexed + header row

        # ── Direction (set for dual_account if still missing) ────────────────
        if "direction" not in rec:
            amount = rec.get("amount")
            if amount is not None:
                rec["direction"] = "IN" if amount > 0 else "OUT"
            else:
                rec["direction"] = "UNKNOWN"

        records.append(rec)

    result = pd.DataFrame(records)
    # Drop rows with no amount (non-transaction rows)
    result = result[result["amount"].notna()].copy()
    result.reset_index(drop=True, inplace=True)

    # ── Auto-calculate balance if bank statement didn't provide it ─────────
    # Balance = running cumulative sum of amounts (ยอดคงเหลือสะสม)
    if "balance" in result.columns:
        has_balance = result["balance"].notna().any()
    else:
        has_balance = False

    if not has_balance:
        result["balance"] = result["amount"].astype(float).cumsum().round(2)
        logger.info("  Balance auto-calculated (running cumulative sum)")
    else:
        logger.info("  Balance from bank statement column")

    logger.info(f"Normalized {len(result)} valid transaction rows [{fmt_type}]")
    return result
