"""
exporter.py
-----------
Exports the Account Package to disk in CSV and multi-sheet Excel (.xlsx).

Output structure:
  /data/output/{account_number}/
      raw/original.xlsx
      processed/
          {name}_{bank}_report.xlsx    ← multi-sheet report
          transactions.csv
          entities.csv   entities.xlsx
          links.csv
      meta.json
"""

import json
import logging
import re
import shutil
from pathlib import Path
from datetime import date
from typing import Union, Tuple

import pandas as pd

from utils.date_utils import format_date_range

logger = logging.getLogger(__name__)

BASE_OUTPUT = Path(__file__).parent.parent / "data" / "output"


def _safe_filename(name: str) -> str:
    """Sanitise a string for use in a file name (keep Thai, alphanumeric, space, dash)."""
    s = re.sub(r'[\\/:*?"<>|]', '', name).strip()
    # collapse multiple spaces / dots
    s = re.sub(r'\s+', ' ', s)
    return s or "unknown"


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


def _write_transactions_multisheet(
    transactions: pd.DataFrame,
    entities: pd.DataFrame,
    links: pd.DataFrame,
    processed_dir: Path,
    report_filename: str = "report.xlsx",
) -> Path:
    """Write transactions Excel with multiple categorised sheets + entities + links.

    Returns the Path to the written Excel file.
    """
    excel_path = processed_dir / report_filename

    _KNOWN_TYPES = {"OUT_TRANSFER", "IN_TRANSFER", "DEPOSIT", "WITHDRAW"}

    sheet_map = {
        "รายการทั้งหมด": transactions,
        "โอนออก":       transactions[transactions["transaction_type"] == "OUT_TRANSFER"],
        "โอนเข้า":      transactions[transactions["transaction_type"] == "IN_TRANSFER"],
        "ฝากเงิน":      transactions[transactions["transaction_type"] == "DEPOSIT"],
        "ถอนเงิน":      transactions[transactions["transaction_type"] == "WITHDRAW"],
        "อื่นๆ":        transactions[~transactions["transaction_type"].isin(_KNOWN_TYPES)],
        "Entities":     entities,
        "Links":        links,
    }

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        for sheet_name, df in sheet_map.items():
            df_clean = df.reset_index(drop=True)
            df_clean.to_excel(writer, sheet_name=sheet_name, index=False)

            # Auto-fit column widths
            ws = writer.sheets[sheet_name]
            for col_cells in ws.columns:
                max_len = max(
                    (len(str(cell.value)) for cell in col_cells if cell.value is not None),
                    default=8,
                )
                col_letter = col_cells[0].column_letter
                ws.column_dimensions[col_letter].width = min(max_len + 2, 40)

    logger.info(f"  Multi-sheet report: {excel_path.name} ({len(sheet_map)} sheets)")
    return excel_path


def export_package(
    transactions: pd.DataFrame,
    entities: pd.DataFrame,
    links: pd.DataFrame,
    account_number: str,
    bank: str,
    original_file: Union[str, Path],
    subject_name: str = "",
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
    subject_name   : account holder name (used in report filename)

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

    # 2. Export transactions CSV (for programmatic access)
    transactions.to_csv(processed_dir / "transactions.csv", index=False, encoding="utf-8-sig")
    logger.info("  Exported: transactions.csv")

    # 3. Export entities CSV + Excel
    _write_csv_and_excel(entities, processed_dir, "entities")

    # 4. Export links CSV
    links.to_csv(processed_dir / "links.csv", index=False, encoding="utf-8-sig")
    logger.info("  Exported: links.csv")

    # 5. Multi-sheet report Excel (all sheets in one file)
    #    Filename: {subject_name}_{bank}_report.xlsx  (or report.xlsx if no name)
    if subject_name:
        report_name = f"{_safe_filename(subject_name)}_{_safe_filename(bank)}_report.xlsx"
    else:
        report_name = "report.xlsx"
    report_path = _write_transactions_multisheet(
        transactions, entities, links, processed_dir, report_filename=report_name,
    )

    # 7. Build and write meta.json
    meta = _build_meta(transactions, account_number, bank)
    meta["report_filename"] = report_path.name
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

    total_circulation = round(total_in + abs(total_out), 2)

    return {
        "account_number":      account_number,
        "bank":                bank,
        "total_in":            round(total_in, 2),
        "total_out":           round(total_out, 2),
        "total_circulation":   total_circulation,
        "num_transactions":    len(transactions),
        "date_range":          date_range,
        "num_unknown":         num_unknown,
        "num_partial_accounts": num_partial,
    }
