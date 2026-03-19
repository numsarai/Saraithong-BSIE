"""
exporter.py
-----------
Exports the Account Package to disk in BOTH CSV and Excel (.xlsx) formats.

Output structure:
  /data/output/{account_number}/
      raw/original.xlsx
      processed/
          transactions.csv   transactions.xlsx
          entities.csv       entities.xlsx
          links.csv          links.xlsx
      meta.json
"""

import json
import logging
import shutil
from pathlib import Path
from datetime import date
from typing import Union, Tuple

import pandas as pd

from utils.date_utils import format_date_range

logger = logging.getLogger(__name__)

BASE_OUTPUT = Path(__file__).parent.parent / "data" / "output"


def _ensure_dirs(account_number: str) -> Tuple[Path, Path, Path]:
    """
    Create output directory structure for an account.
    Returns (account_dir, raw_dir, processed_dir).
    """
    account_dir  = BASE_OUTPUT / account_number
    raw_dir      = account_dir / "raw"
    processed_dir = account_dir / "processed"

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    return account_dir, raw_dir, processed_dir


def _write_csv_and_excel(df: pd.DataFrame, processed_dir: Path, stem: str) -> None:
    """Write a DataFrame as both CSV and Excel."""
    csv_path   = processed_dir / f"{stem}.csv"
    excel_path = processed_dir / f"{stem}.xlsx"

    df.to_csv(csv_path,   index=False, encoding="utf-8-sig")   # utf-8-sig for Excel Thai compat
    df.to_excel(excel_path, index=False, engine="openpyxl")

    logger.info(f"  Exported: {csv_path.name} + {excel_path.name}")


def export_package(
    transactions: pd.DataFrame,
    entities: pd.DataFrame,
    links: pd.DataFrame,
    account_number: str,
    bank: str,
    original_file: Union[str, Path],
) -> Path:
    """
    Export the full Account Package to disk.

    Parameters
    ----------
    transactions   : processed transaction DataFrame
    entities       : entity DataFrame
    links          : graph links DataFrame
    account_number : subject account number (used as folder name)
    bank           : bank name string
    original_file  : path to original Excel input file

    Returns
    -------
    Path – path to account output directory
    """
    account_dir, raw_dir, processed_dir = _ensure_dirs(account_number)

    # 1. Copy original file
    orig_path = Path(original_file)
    dest_orig = raw_dir / "original.xlsx"
    try:
        shutil.copy2(orig_path, dest_orig)
        logger.info(f"Copied original: {dest_orig}")
    except Exception as e:
        logger.warning(f"Could not copy original file: {e}")

    # 2. Export transactions (CSV + Excel)
    _write_csv_and_excel(transactions, processed_dir, "transactions")

    # 3. Export entities (CSV + Excel)
    _write_csv_and_excel(entities, processed_dir, "entities")

    # 4. Export links (CSV + Excel)
    _write_csv_and_excel(links, processed_dir, "links")

    # 5. Build and write meta.json
    meta = _build_meta(transactions, account_number, bank)
    meta_path = account_dir / "meta.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"  Meta written: {meta_path}")

    logger.info(f"Account package complete: {account_dir}")
    return account_dir


def _build_meta(transactions: pd.DataFrame, account_number: str, bank: str) -> dict:
    """Compute summary statistics for meta.json."""
    if transactions.empty:
        return {
            "account_number": account_number,
            "bank": bank,
            "total_in": 0,
            "total_out": 0,
            "num_transactions": 0,
            "date_range": "",
            "num_unknown": 0,
            "num_partial_accounts": 0,
        }

    amounts  = transactions["amount"].fillna(0)
    total_in  = float(amounts[amounts > 0].sum())
    total_out = float(amounts[amounts < 0].sum())

    raw_dates = transactions["date"].dropna().tolist()
    date_range = format_date_range(raw_dates) if raw_dates else ""

    if "counterparty_account" in transactions.columns:
        num_unknown = int((transactions["counterparty_account"] == "").sum())
    else:
        num_unknown = 0
    if "partial_account" in transactions.columns:
        num_partial = int((transactions["partial_account"] != "").sum())
    else:
        num_partial = 0

    return {
        "account_number":      account_number,
        "bank":                bank,
        "total_in":            round(total_in, 2),
        "total_out":           round(total_out, 2),
        "num_transactions":    len(transactions),
        "date_range":          date_range,
        "num_unknown":         num_unknown,
        "num_partial_accounts": num_partial,
    }
