"""
loader.py
---------
Loads bank statement Excel files, supporting multiple sheets,
flexible header detection, and empty-row removal.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Union

from paths import CONFIG_DIR

import pandas as pd

logger = logging.getLogger(__name__)


def load_config(bank_key: str) -> dict:
    """
    Load bank configuration from config/<bank_key>.json.

    Parameters
    ----------
    bank_key : str
        e.g. "scb", "kbank"

    Returns
    -------
    dict – parsed JSON config
    """
    config_path = CONFIG_DIR / f"{bank_key.lower()}.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Bank config not found: {config_path}")
    with config_path.open(encoding="utf-8") as f:
        return json.load(f)


def load_excel(
    file_path: Union[str, Path],
    bank_config: dict,
) -> pd.DataFrame:
    """
    Load an Excel bank statement according to bank_config.

    Strategy:
    1. Try configured sheet_index
    2. Fall back to first non-empty sheet
    3. Try to auto-detect header row if it doesn't match column_mapping keys
    4. Drop fully empty rows

    Parameters
    ----------
    file_path  : str | Path  – path to .xlsx / .xls file
    bank_config : dict       – parsed bank config JSON

    Returns
    -------
    pd.DataFrame with raw data
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    sheet_index: int = bank_config.get("sheet_index", 0)
    header_row: int  = bank_config.get("header_row", 0)

    logger.info(f"Loading Excel: {file_path}  configured sheet_index={sheet_index}  header_row={header_row}")

    # Read all sheet names first
    xf = pd.ExcelFile(file_path, engine="openpyxl")
    sheet_names = xf.sheet_names

    # If the configured sheet works AND has data, use it. Otherwise, search.
    sheets_to_try = []
    if sheet_index < len(sheet_names):
        sheets_to_try.append(sheet_names[sheet_index])
    for s in sheet_names:
        if s not in sheets_to_try:
            sheets_to_try.append(s)

    best_df = None
    
    # We need to check if a dataframe has actual data and matching columns
    date_aliases = bank_config.get("column_mapping", {}).get("date", [])
    amount_aliases = bank_config.get("column_mapping", {}).get("amount", []) + bank_config.get("column_mapping", {}).get("credit", [])

    for sheet_name in sheets_to_try:
        try:
            # Preview sheet to find dynamic header row
            df_preview = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                header=None,
                nrows=30,
                engine="openpyxl",
                dtype=str,
            )
            
            best_header_idx = header_row
            for idx, row in df_preview.iterrows():
                # Check for matching aliases in this row
                row_vals = [str(v).lower().strip() for v in row.values if pd.notna(v)]
                has_date = any(alias.lower() in row_vals for alias in date_aliases)
                has_amt = any(alias.lower() in row_vals for alias in amount_aliases)
                if has_date and has_amt:
                    best_header_idx = idx
                    break

            # Load actual data with detected header
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                header=best_header_idx,
                engine="openpyxl",
                dtype=str,
            )
            df.dropna(how="all", inplace=True)
            df.reset_index(drop=True, inplace=True)
            df.columns = [str(c).strip() for c in df.columns]

            if len(df) == 0:
                continue

            # Check if this sheet has Date or Amount columns
            has_date = detect_column(df, date_aliases) is not None
            has_amount = detect_column(df, amount_aliases) is not None

            if has_date or has_amount:
                best_df = df
                logger.info(f"Selected sheet '{sheet_name}' with {len(df)} rows using header row {best_header_idx}")
                break
            
            # Keep as fallback if we find nothing else
            if best_df is None and len(df) > 0:
                best_df = df

        except Exception as e:
            logger.debug(f"Failed to read sheet '{sheet_name}': {e}")

    if best_df is None:
        raise ValueError(f"No valid data sheets found in {file_path}")

    logger.info(f"Returning DataFrame with {len(best_df)} rows")
    return best_df


def detect_column(
    df: pd.DataFrame,
    aliases: list[str],
) -> Optional[str]:
    """
    Find the first column in df.columns that matches any alias (case-insensitive).

    Parameters
    ----------
    df      : pd.DataFrame
    aliases : list[str] – candidate column name aliases

    Returns
    -------
    str | None – matched column name in df, or None
    """
    lower_to_original = {c.lower(): c for c in df.columns}
    for alias in aliases:
        key = alias.lower().strip()
        if key in lower_to_original:
            return lower_to_original[key]
    return None
