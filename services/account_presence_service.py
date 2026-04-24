from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from services.subject_context_service import normalize_subject_account


EXCEL_SUFFIXES = {".xlsx", ".xls"}


def verify_account_presence(
    *,
    file_path: str | Path,
    subject_account: Any,
    sheet_name: str = "",
    header_row: int = 0,
    max_matches: int = 25,
) -> dict[str, Any]:
    """Scan workbook cells for an analyst-selected subject account."""
    path = Path(file_path)
    normalized_account = normalize_subject_account(subject_account)
    max_items = max(1, min(int(max_matches or 25), 100))
    if not normalized_account:
        return _empty_result(
            path=path,
            subject_account=subject_account,
            normalized_account="",
            sheet_name=sheet_name,
            header_row=header_row,
            status="invalid_account",
            match_status="invalid_account",
            warnings=["Subject account must be exactly 10 or 12 digits after normalization."],
        )

    if path.suffix.lower() not in EXCEL_SUFFIXES:
        return _empty_result(
            path=path,
            subject_account=subject_account,
            normalized_account=normalized_account,
            sheet_name=sheet_name,
            header_row=header_row,
            status="unsupported_file",
            match_status="unsupported_file",
            warnings=["Full account-presence verification is currently supported for Excel workbooks only."],
        )

    if not path.exists():
        return _empty_result(
            path=path,
            subject_account=subject_account,
            normalized_account=normalized_account,
            sheet_name=sheet_name,
            header_row=header_row,
            status="file_not_found",
            match_status="file_not_found",
            warnings=["Source evidence file was not found."],
        )

    exact_locations: list[dict[str, Any]] = []
    possible_locations: list[dict[str, Any]] = []
    scanned_sheets: list[str] = []
    cells_scanned = 0
    exact_match_count = 0
    possible_match_count = 0
    try:
        with pd.ExcelFile(path) as workbook:
            sheet_names = [str(name) for name in workbook.sheet_names]
            target_sheets = [sheet_name] if sheet_name and sheet_name in sheet_names else sheet_names
            for active_sheet in target_sheets:
                raw_df = pd.read_excel(path, sheet_name=active_sheet, header=None, dtype=str).fillna("")
                scanned_sheets.append(active_sheet)
                header_labels = _header_labels(raw_df, int(header_row or 0))
                for row_index, row in raw_df.iterrows():
                    for column_index, raw_value in enumerate(row.tolist()):
                        cells_scanned += 1
                        match_type = _match_type(raw_value, normalized_account)
                        if not match_type:
                            continue
                        location = {
                            "sheet_name": active_sheet,
                            "row_index": int(row_index),
                            "row_number": int(row_index) + 1,
                            "column_index": int(column_index),
                            "column_number": int(column_index) + 1,
                            "column_label": header_labels.get(int(column_index), ""),
                            "row_zone": _row_zone(int(row_index), int(header_row or 0)),
                            "match_type": match_type,
                            "value_preview": str(raw_value or "").strip()[:160],
                        }
                        if match_type == "possible_leading_zero_loss":
                            possible_match_count += 1
                            if len(possible_locations) < max_items:
                                possible_locations.append(location)
                        else:
                            exact_match_count += 1
                            if len(exact_locations) < max_items:
                                exact_locations.append(location)
    except Exception as exc:
        return _empty_result(
            path=path,
            subject_account=subject_account,
            normalized_account=normalized_account,
            sheet_name=sheet_name,
            header_row=header_row,
            status="read_error",
            match_status="read_error",
            warnings=[f"Could not scan workbook for account presence: {exc}"],
        )

    found = exact_match_count > 0
    possible_match = possible_match_count > 0 and not found
    match_status = "exact_found" if found else "possible_leading_zero_loss" if possible_match else "not_found"
    warnings: list[str] = []
    if possible_match:
        warnings.append("Only leading-zero-loss candidates were found; analyst review is required.")
    elif not found:
        warnings.append("Selected account was not found in the scanned workbook cells.")

    return {
        "status": "ok",
        "source": "deterministic_account_presence",
        "file_type": "excel",
        "file_name": path.name,
        "subject_account_raw": str(subject_account or "").strip()[:80],
        "normalized_account": normalized_account,
        "sheet_name": sheet_name,
        "header_row": int(header_row or 0),
        "scanned_sheets": scanned_sheets,
        "found": found,
        "possible_match": possible_match,
        "match_status": match_status,
        "locations": exact_locations,
        "possible_locations": possible_locations,
        "summary": {
            "exact_match_count": exact_match_count,
            "possible_match_count": possible_match_count,
            "sheets_scanned": len(scanned_sheets),
            "cells_scanned": cells_scanned,
            "locations_returned": len(exact_locations) + len(possible_locations),
        },
        "warnings": warnings,
    }


def _empty_result(
    *,
    path: Path,
    subject_account: Any,
    normalized_account: str,
    sheet_name: str,
    header_row: int,
    status: str,
    match_status: str,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "status": status,
        "source": "deterministic_account_presence",
        "file_type": path.suffix.lower().lstrip(".") or "unknown",
        "file_name": path.name,
        "subject_account_raw": str(subject_account or "").strip()[:80],
        "normalized_account": normalized_account,
        "sheet_name": sheet_name,
        "header_row": int(header_row or 0),
        "scanned_sheets": [],
        "found": False,
        "possible_match": False,
        "match_status": match_status,
        "locations": [],
        "possible_locations": [],
        "summary": {
            "exact_match_count": 0,
            "possible_match_count": 0,
            "sheets_scanned": 0,
            "cells_scanned": 0,
            "locations_returned": 0,
        },
        "warnings": warnings,
    }


def _header_labels(raw_df: pd.DataFrame, header_row: int) -> dict[int, str]:
    if header_row < 0 or header_row >= len(raw_df):
        return {}
    return {int(index): str(value or "").strip()[:80] for index, value in enumerate(raw_df.iloc[header_row].tolist())}


def _row_zone(row_index: int, header_row: int) -> str:
    if row_index < header_row:
        return "pre_header"
    if row_index == header_row:
        return "header"
    return "body"


def _match_type(raw_value: Any, normalized_account: str) -> str:
    text = str(raw_value or "").strip()
    if not text:
        return ""
    parsed_account = normalize_subject_account(text)
    if parsed_account == normalized_account:
        return "normalized_account"
    digits = "".join(ch for ch in text if ch.isdigit())
    if normalized_account and normalized_account in digits:
        return "exact_digits"
    stripped = normalized_account.lstrip("0")
    if normalized_account.startswith("0") and stripped and stripped in digits:
        return "possible_leading_zero_loss"
    return ""
