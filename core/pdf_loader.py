"""
pdf_loader.py
-------------
Extract transaction tables from text-based PDF bank statements using pdfplumber.

Falls back to text-strategy extraction when line-based table detection finds nothing.
Multi-page tables with the same column structure are automatically concatenated.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pdfplumber

from core.loader import score_header_row

logger = logging.getLogger(__name__)


def parse_pdf_file(path: Path | str) -> dict:
    """Extract the best transaction table from a PDF file.

    Returns
    -------
    dict with keys:
        df : pd.DataFrame   – extracted table (empty if none found)
        source_format : str  – ``"PDF"``
        page_count : int
        ocr_used : bool      – always ``False`` for this loader
        header_row : int     – detected header row within the table
        tables_found : int
    """
    path = Path(path)
    logger.info("PDF loader: opening %s", path.name)

    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        tables = _extract_tables_from_pdf(pdf)

    if not tables:
        logger.info("PDF loader: no tables found in %s", path.name)
        return {
            "df": pd.DataFrame(),
            "source_format": "PDF",
            "page_count": page_count,
            "ocr_used": False,
            "header_row": 0,
            "tables_found": 0,
        }

    best_df, header_row = _select_best_table(tables)
    logger.info(
        "PDF loader: selected table with %d rows, header at row %d",
        len(best_df),
        header_row,
    )

    return {
        "df": best_df,
        "source_format": "PDF",
        "page_count": page_count,
        "ocr_used": False,
        "header_row": header_row,
        "tables_found": len(tables),
    }


def _extract_tables_from_pdf(pdf: pdfplumber.PDF) -> list[pd.DataFrame]:
    """Extract all tables from all pages, trying line-based then text-based."""
    all_tables: list[pd.DataFrame] = []

    for page in pdf.pages:
        # Try default (line-based) extraction first
        raw_tables = page.extract_tables()
        if not raw_tables:
            # Fallback: text-based strategy
            raw_tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                }
            )
        for raw in raw_tables:
            if raw and len(raw) >= 2:
                df = pd.DataFrame(raw)
                # Strip whitespace from all cells
                df = df.map(lambda x: str(x).strip() if x is not None else "")
                all_tables.append(df)

    # Concatenate tables with same column count (multi-page continuations)
    return _merge_compatible_tables(all_tables)


def _merge_compatible_tables(tables: list[pd.DataFrame]) -> list[pd.DataFrame]:
    """Merge tables that share the same number of columns (multi-page spans)."""
    if len(tables) <= 1:
        return tables

    groups: dict[int, list[pd.DataFrame]] = {}
    for df in tables:
        ncols = len(df.columns)
        groups.setdefault(ncols, []).append(df)

    merged: list[pd.DataFrame] = []
    for ncols, group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
        else:
            # Use the first table's header, skip header rows of subsequent tables
            base = group[0]
            header_vals = [str(v).strip().lower() for v in base.iloc[0].values]
            parts = [base]
            for continuation in group[1:]:
                first_row = [str(v).strip().lower() for v in continuation.iloc[0].values]
                # Skip the header row if it matches the first table's header
                if first_row == header_vals:
                    parts.append(continuation.iloc[1:])
                else:
                    parts.append(continuation)
            merged.append(pd.concat(parts, ignore_index=True))

    return merged


def _select_best_table(tables: list[pd.DataFrame]) -> tuple[pd.DataFrame, int]:
    """Pick the table most likely to contain transactions and detect its header."""
    best_df = tables[0]
    best_score = -1.0
    best_header = 0

    for df in tables:
        scan_limit = min(15, len(df))
        table_best_row = 0
        table_best_score = -1.0
        for idx in range(scan_limit):
            row_vals = [str(v) for v in df.iloc[idx].values]
            score = score_header_row(row_vals)
            if score > table_best_score:
                table_best_score = score
                table_best_row = idx

        # Bonus for more data rows
        data_rows = max(0, len(df) - table_best_row - 1)
        total = table_best_score + min(data_rows, 500) * 0.01

        if total > best_score:
            best_score = total
            best_df = df
            best_header = table_best_row

    # Set column names from header row and drop rows above it
    if best_header < len(best_df):
        header_values = [str(v).strip() for v in best_df.iloc[best_header].values]
        # Deduplicate column names
        seen: dict[str, int] = {}
        unique_cols: list[str] = []
        for col in header_values:
            if col in seen:
                seen[col] += 1
                unique_cols.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                unique_cols.append(col)
        best_df = best_df.iloc[best_header + 1:].reset_index(drop=True)
        best_df.columns = unique_cols

    # Drop fully empty rows
    best_df = best_df.loc[~(best_df == "").all(axis=1)].reset_index(drop=True)

    return best_df, best_header
