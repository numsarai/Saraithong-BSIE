"""
normalizer.py
-------------
Applies bank-config column mapping to a raw DataFrame, cleans amounts,
normalises dates/times, and calls account_parser on account columns.
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


# ---------------------------------------------------------------------------
# Core normalizer
# ---------------------------------------------------------------------------

def normalize(
    df: pd.DataFrame,
    bank_config: dict,
    subject_account: str,
    subject_name: str = "",
) -> pd.DataFrame:
    """
    Apply config-driven column mapping; clean, parse, and standardise all fields.

    Parameters
    ----------
    df               : raw DataFrame from loader
    bank_config      : parsed bank config JSON
    subject_account  : the account number under investigation
    subject_name     : optional name of account holder

    Returns
    -------
    pd.DataFrame with STANDARD schema columns
    """
    mapping: dict = bank_config.get("column_mapping", {})
    bank_name: str = bank_config.get("bank_name", "UNKNOWN")
    currency: str  = bank_config.get("currency", "THB")
    amount_mode: str = bank_config.get("amount_mode", "signed")

    records = []

    for idx, row in df.iterrows():
        rec: dict = {}

        # ── Helpers ─────────────────────────────────────────────────────────
        def get_col(field: str) -> Optional[object]:
            """Get raw value for a logical field by alias lookup."""
            aliases = mapping.get(field, [])
            col = detect_column(df, aliases)
            if col is None:
                return None
            return row.get(col)

        # ── Date / Time ──────────────────────────────────────────────────────
        raw_date = get_col("date")
        raw_time = get_col("time")
        rec["date"] = str(parse_date(raw_date)) if parse_date(raw_date) else ""
        rec["time"] = parse_time(raw_time) or ""

        # ── Description ──────────────────────────────────────────────────────
        raw_desc = get_col("description")
        rec["description"] = normalize_text(raw_desc)

        # ── Amount (signed vs debit/credit mode) ─────────────────────────────
        if amount_mode == "debit_credit":
            raw_debit  = _clean_amount(get_col("debit"))   or 0.0
            raw_credit = _clean_amount(get_col("credit"))  or 0.0
            amount = round(raw_credit - raw_debit, 6)
        else:
            amount = _clean_amount(get_col("amount"))
            if amount is None:
                # Try debit/credit fallback even for "signed" mode
                raw_debit  = _clean_amount(get_col("debit"))  or 0.0
                raw_credit = _clean_amount(get_col("credit")) or 0.0
                amount = round(raw_credit - raw_debit, 6) if (raw_debit or raw_credit) else None

        rec["amount"]   = amount
        rec["currency"] = currency

        # ── Balance ──────────────────────────────────────────────────────────
        raw_balance = get_col("balance")
        rec["balance"] = _clean_amount(raw_balance)

        # ── Channel ───────────────────────────────────────────────────────────
        rec["channel"] = normalize_text(get_col("channel"))

        # ── Subject ───────────────────────────────────────────────────────────
        rec["subject_account"] = subject_account
        rec["subject_name"]    = subject_name
        rec["bank"]            = bank_name

        # ── Counterparty account ──────────────────────────────────────────────
        cp_aliases = mapping.get("counterparty_account", [])
        cp_cols = []
        for c in df.columns:
            if c.lower().strip() in [a.lower().strip() for a in cp_aliases]:
                cp_cols.append(c)

        parsed_cp = {"raw": "", "clean": "", "type": "UNKNOWN"}
        raw_cp_account = ""

        # Try to find a counterparty account that is NOT the subject account
        for col in cp_cols:
            val = row.get(col)
            if not val or pd.isna(val):
                continue
            p = parse_account(val)
            if p["type"] in ("ACCOUNT", "PARTIAL_ACCOUNT") and p["clean"] != subject_account:
                parsed_cp = p
                raw_cp_account = val
                break
        
        # If none found, grab the first one as fallback
        if parsed_cp["type"] == "UNKNOWN" and cp_cols:
            raw_cp_account = row.get(cp_cols[0])
            parsed_cp = parse_account(raw_cp_account)

        rec["raw_account_value"]    = parsed_cp["raw"]
        rec["parsed_account_type"]  = parsed_cp["type"]

        if parsed_cp["type"] == "ACCOUNT":
            rec["counterparty_account"] = parsed_cp["clean"]
            rec["partial_account"]       = ""
        elif parsed_cp["type"] == "PARTIAL_ACCOUNT":
            rec["counterparty_account"] = ""
            rec["partial_account"]       = parsed_cp["clean"]
        else:
            rec["counterparty_account"] = ""
            rec["partial_account"]       = ""

        # ── Counterparty name ─────────────────────────────────────────────────
        name_aliases = mapping.get("counterparty_name", [])
        name_cols = []
        for c in df.columns:
            if c.lower().strip() in [a.lower().strip() for a in name_aliases]:
                name_cols.append(c)
                
        # Try to find a name that is NOT the subject name
        best_name = ""
        for col in name_cols:
            val = normalize_text(row.get(col))
            if val and val != subject_name:
                best_name = val
                break
        
        # Fallback
        if not best_name and name_cols:
            best_name = normalize_text(row.get(name_cols[0]))
            
        rec["counterparty_name"] = best_name

        # ── Extract accounts from description (augment if still missing) ──────
        extracted = extract_accounts_from_description(rec["description"])

        if not rec["counterparty_account"] and extracted["valid_accounts"]:
            rec["counterparty_account"]  = extracted["valid_accounts"][0]
            rec["parsed_account_type"]   = "ACCOUNT"

        if not rec["partial_account"] and extracted["partial_accounts"]:
            rec["partial_account"] = extracted["partial_accounts"][0]

        # ── Direction ─────────────────────────────────────────────────────────
        if rec["amount"] is not None:
            rec["direction"] = "IN" if rec["amount"] > 0 else "OUT"
        else:
            rec["direction"] = "UNKNOWN"

        # ── Preserve raw row for traceability ─────────────────────────────────
        rec["_raw_idx"] = idx

        records.append(rec)

    result = pd.DataFrame(records)
    # Drop rows with no amount (non-transaction rows)
    result = result[result["amount"].notna()].copy()
    result.reset_index(drop=True, inplace=True)

    logger.info(f"Normalized {len(result)} valid transaction rows")
    return result
