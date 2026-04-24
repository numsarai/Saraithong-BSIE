from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from services.subject_context_service import normalize_subject_account


EXCEL_SUFFIXES = {".xlsx", ".xls"}
PDF_SUFFIXES = {".pdf"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}
SUPPORTED_SUFFIXES = EXCEL_SUFFIXES | PDF_SUFFIXES | IMAGE_SUFFIXES


def verify_account_presence(
    *,
    file_path: str | Path,
    subject_account: Any,
    sheet_name: str = "",
    header_row: int = 0,
    max_matches: int = 25,
) -> dict[str, Any]:
    """Scan stored evidence for an analyst-selected subject account."""
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

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        return _empty_result(
            path=path,
            subject_account=subject_account,
            normalized_account=normalized_account,
            sheet_name=sheet_name,
            header_row=header_row,
            status="unsupported_file",
            match_status="unsupported_file",
            warnings=["Account-presence verification supports Excel, text PDF, and OCR-supported image/PDF evidence."],
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

    if suffix in EXCEL_SUFFIXES:
        return _verify_excel_account_presence(
            path=path,
            subject_account=subject_account,
            normalized_account=normalized_account,
            sheet_name=sheet_name,
            header_row=header_row,
            max_items=max_items,
        )
    if suffix in PDF_SUFFIXES:
        return _verify_pdf_account_presence(
            path=path,
            subject_account=subject_account,
            normalized_account=normalized_account,
            sheet_name=sheet_name,
            header_row=header_row,
            max_items=max_items,
        )
    return _verify_image_account_presence(
        path=path,
        subject_account=subject_account,
        normalized_account=normalized_account,
        sheet_name=sheet_name,
        header_row=header_row,
        max_items=max_items,
    )


def _verify_excel_account_presence(
    *,
    path: Path,
    subject_account: Any,
    normalized_account: str,
    sheet_name: str,
    header_row: int,
    max_items: int,
) -> dict[str, Any]:
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

    return _presence_result(
        path=path,
        subject_account=subject_account,
        normalized_account=normalized_account,
        sheet_name=sheet_name,
        header_row=header_row,
        file_type="excel",
        scanned_sheets=scanned_sheets,
        exact_locations=exact_locations,
        possible_locations=possible_locations,
        exact_match_count=exact_match_count,
        possible_match_count=possible_match_count,
        cells_scanned=cells_scanned,
        not_found_warning="Selected account was not found in the scanned workbook cells.",
    )


def _verify_pdf_account_presence(
    *,
    path: Path,
    subject_account: Any,
    normalized_account: str,
    sheet_name: str,
    header_row: int,
    max_items: int,
) -> dict[str, Any]:
    exact_locations: list[dict[str, Any]] = []
    possible_locations: list[dict[str, Any]] = []
    scanned_sources: list[str] = []
    cells_scanned = 0
    exact_match_count = 0
    possible_match_count = 0
    page_count = 0
    text_lines_scanned = 0
    tables_found = 0
    ocr_used = False
    ocr_tokens_scanned = 0
    warnings: list[str] = []

    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            for page_index, page in enumerate(pdf.pages):
                page_number = page_index + 1
                page_label = f"PDF page {page_number}"
                text = page.extract_text() or ""
                lines = [line for line in text.splitlines() if line.strip()]
                if lines and page_label not in scanned_sources:
                    scanned_sources.append(page_label)
                for line_index, line in enumerate(lines):
                    cells_scanned += 1
                    text_lines_scanned += 1
                    matched = _record_match(
                        raw_value=line,
                        normalized_account=normalized_account,
                        location={
                            "sheet_name": page_label,
                            "row_index": line_index,
                            "row_number": line_index + 1,
                            "column_index": 0,
                            "column_number": 1,
                            "column_label": "page_text",
                            "row_zone": "page_text",
                            "page_number": page_number,
                            "source_region": "page_text",
                        },
                        max_items=max_items,
                        exact_locations=exact_locations,
                        possible_locations=possible_locations,
                    )
                    if matched == "possible_leading_zero_loss":
                        possible_match_count += 1
                    elif matched:
                        exact_match_count += 1
    except Exception as exc:
        warnings.append(f"Could not scan PDF text for account presence: {exc}")

    try:
        from core.pdf_loader import parse_pdf_file

        pdf_result = parse_pdf_file(path)
        tables_found = int(pdf_result.get("tables_found") or 0)
        table_df = pdf_result.get("df")
        if isinstance(table_df, pd.DataFrame) and not table_df.empty:
            scanned_sources.append("PDF table")
            table_counts = _scan_dataframe_cells(
                df=table_df,
                normalized_account=normalized_account,
                sheet_label="PDF table",
                header_row=int(pdf_result.get("header_row") or 0),
                row_zone="body",
                source_region="pdf_table",
                max_items=max_items,
                exact_locations=exact_locations,
                possible_locations=possible_locations,
            )
            cells_scanned += table_counts["cells_scanned"]
            exact_match_count += table_counts["exact_match_count"]
            possible_match_count += table_counts["possible_match_count"]
    except Exception as exc:
        warnings.append(f"Could not scan PDF tables for account presence: {exc}")

    should_try_ocr = cells_scanned == 0 or (exact_match_count == 0 and possible_match_count == 0 and tables_found == 0)
    if should_try_ocr:
        try:
            from core.image_loader import parse_image_file

            ocr_result = parse_image_file(path)
            ocr_used = True
            ocr_df = ocr_result.get("df")
            ocr_tokens = _coerce_ocr_tokens(ocr_result.get("ocr_tokens"))
            if isinstance(ocr_df, pd.DataFrame) and not ocr_df.empty:
                scanned_sources.append("PDF OCR")
                ocr_counts = _scan_dataframe_cells(
                    df=ocr_df,
                    normalized_account=normalized_account,
                    sheet_label="PDF OCR",
                    header_row=int(ocr_result.get("header_row") or 0),
                    row_zone="body",
                    source_region="ocr_table",
                    max_items=max_items,
                    exact_locations=exact_locations,
                    possible_locations=possible_locations,
                )
                cells_scanned += ocr_counts["cells_scanned"]
                exact_match_count += ocr_counts["exact_match_count"]
                possible_match_count += ocr_counts["possible_match_count"]
            if ocr_tokens:
                scanned_sources.append("PDF OCR tokens")
                token_counts = _scan_ocr_tokens(
                    tokens=ocr_tokens,
                    normalized_account=normalized_account,
                    sheet_label="PDF OCR tokens",
                    max_items=max_items,
                    exact_locations=exact_locations,
                    possible_locations=possible_locations,
                )
                cells_scanned += token_counts["cells_scanned"]
                ocr_tokens_scanned += token_counts["cells_scanned"]
                exact_match_count += token_counts["exact_match_count"]
                possible_match_count += token_counts["possible_match_count"]
            if (not isinstance(ocr_df, pd.DataFrame) or ocr_df.empty) and not ocr_tokens:
                warnings.append("OCR completed but produced no searchable text tokens or table cells for account presence.")
        except Exception as exc:
            warnings.append(f"OCR scan unavailable for account presence: {exc}")

    if cells_scanned == 0:
        return _empty_result(
            path=path,
            subject_account=subject_account,
            normalized_account=normalized_account,
            sheet_name=sheet_name,
            header_row=header_row,
            status="read_error",
            match_status="read_error",
            warnings=warnings or ["No searchable PDF text, table cells, or OCR cells were available for account presence verification."],
            summary_extra={
                "page_count": page_count,
                "text_lines_scanned": text_lines_scanned,
                "tables_found": tables_found,
                "ocr_used": ocr_used,
                "ocr_tokens_scanned": ocr_tokens_scanned,
                "search_units_scanned": cells_scanned,
            },
        )

    return _presence_result(
        path=path,
        subject_account=subject_account,
        normalized_account=normalized_account,
        sheet_name=sheet_name,
        header_row=header_row,
        file_type="pdf",
        scanned_sheets=scanned_sources,
        exact_locations=exact_locations,
        possible_locations=possible_locations,
        exact_match_count=exact_match_count,
        possible_match_count=possible_match_count,
        cells_scanned=cells_scanned,
        warnings=warnings,
        not_found_warning="Selected account was not found in the scanned PDF text/table evidence.",
        summary_extra={
            "page_count": page_count,
            "text_lines_scanned": text_lines_scanned,
            "tables_found": tables_found,
            "ocr_used": ocr_used,
            "ocr_tokens_scanned": ocr_tokens_scanned,
            "search_units_scanned": cells_scanned,
        },
    )


def _verify_image_account_presence(
    *,
    path: Path,
    subject_account: Any,
    normalized_account: str,
    sheet_name: str,
    header_row: int,
    max_items: int,
) -> dict[str, Any]:
    try:
        from core.image_loader import parse_image_file

        ocr_result = parse_image_file(path)
        ocr_df = ocr_result.get("df")
        ocr_tokens = _coerce_ocr_tokens(ocr_result.get("ocr_tokens"))
    except Exception as exc:
        return _empty_result(
            path=path,
            subject_account=subject_account,
            normalized_account=normalized_account,
            sheet_name=sheet_name,
            header_row=header_row,
            status="read_error",
            match_status="read_error",
            warnings=[f"OCR scan unavailable for account presence: {exc}"],
            summary_extra={"ocr_used": False, "search_units_scanned": 0},
        )

    if (not isinstance(ocr_df, pd.DataFrame) or ocr_df.empty) and not ocr_tokens:
        return _empty_result(
            path=path,
            subject_account=subject_account,
            normalized_account=normalized_account,
            sheet_name=sheet_name,
            header_row=header_row,
            status="no_searchable_text",
            match_status="no_searchable_text",
            warnings=["OCR completed but produced no searchable text tokens or table cells for account presence."],
            summary_extra={
                "page_count": int(ocr_result.get("page_count") or 1),
                "ocr_used": True,
                "ocr_tokens_scanned": 0,
                "search_units_scanned": 0,
            },
        )

    exact_locations: list[dict[str, Any]] = []
    possible_locations: list[dict[str, Any]] = []
    scanned_sources: list[str] = []
    total_counts = {"cells_scanned": 0, "exact_match_count": 0, "possible_match_count": 0}
    if isinstance(ocr_df, pd.DataFrame) and not ocr_df.empty:
        scanned_sources.append("IMAGE OCR")
        table_counts = _scan_dataframe_cells(
            df=ocr_df,
            normalized_account=normalized_account,
            sheet_label="IMAGE OCR",
            header_row=int(ocr_result.get("header_row") or 0),
            row_zone="body",
            source_region="ocr_table",
            max_items=max_items,
            exact_locations=exact_locations,
            possible_locations=possible_locations,
        )
        total_counts = _merge_counts(total_counts, table_counts)
    ocr_tokens_scanned = 0
    if ocr_tokens:
        scanned_sources.append("IMAGE OCR tokens")
        token_counts = _scan_ocr_tokens(
            tokens=ocr_tokens,
            normalized_account=normalized_account,
            sheet_label="IMAGE OCR tokens",
            max_items=max_items,
            exact_locations=exact_locations,
            possible_locations=possible_locations,
        )
        ocr_tokens_scanned = token_counts["cells_scanned"]
        total_counts = _merge_counts(total_counts, token_counts)

    return _presence_result(
        path=path,
        subject_account=subject_account,
        normalized_account=normalized_account,
        sheet_name=sheet_name,
        header_row=header_row,
        file_type="image_ocr",
        scanned_sheets=scanned_sources,
        exact_locations=exact_locations,
        possible_locations=possible_locations,
        exact_match_count=total_counts["exact_match_count"],
        possible_match_count=total_counts["possible_match_count"],
        cells_scanned=total_counts["cells_scanned"],
        not_found_warning="Selected account was not found in OCR text tokens or table cells.",
        summary_extra={
            "page_count": int(ocr_result.get("page_count") or 1),
            "ocr_used": True,
            "ocr_tokens_scanned": ocr_tokens_scanned,
            "search_units_scanned": total_counts["cells_scanned"],
        },
    )


def _presence_result(
    *,
    path: Path,
    subject_account: Any,
    normalized_account: str,
    sheet_name: str,
    header_row: int,
    file_type: str,
    scanned_sheets: list[str],
    exact_locations: list[dict[str, Any]],
    possible_locations: list[dict[str, Any]],
    exact_match_count: int,
    possible_match_count: int,
    cells_scanned: int,
    not_found_warning: str,
    warnings: list[str] | None = None,
    summary_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    found = exact_match_count > 0
    possible_match = possible_match_count > 0 and not found
    match_status = "exact_found" if found else "possible_leading_zero_loss" if possible_match else "not_found"
    result_warnings = list(warnings or [])
    if possible_match:
        result_warnings.append("Only leading-zero-loss candidates were found; analyst review is required.")
    elif not found:
        result_warnings.append(not_found_warning)
    summary = {
        "exact_match_count": exact_match_count,
        "possible_match_count": possible_match_count,
        "sheets_scanned": len(scanned_sheets),
        "cells_scanned": cells_scanned,
        "locations_returned": len(exact_locations) + len(possible_locations),
    }
    if summary_extra:
        summary.update(summary_extra)

    return {
        "status": "ok",
        "source": "deterministic_account_presence",
        "file_type": file_type,
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
        "summary": summary,
        "warnings": result_warnings,
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
    summary_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = {
        "exact_match_count": 0,
        "possible_match_count": 0,
        "sheets_scanned": 0,
        "cells_scanned": 0,
        "locations_returned": 0,
    }
    if summary_extra:
        summary.update(summary_extra)
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
        "summary": summary,
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


def _scan_dataframe_cells(
    *,
    df: pd.DataFrame,
    normalized_account: str,
    sheet_label: str,
    header_row: int,
    row_zone: str | None = None,
    source_region: str = "table",
    max_items: int,
    exact_locations: list[dict[str, Any]],
    possible_locations: list[dict[str, Any]],
) -> dict[str, int]:
    cells_scanned = 0
    exact_match_count = 0
    possible_match_count = 0
    header_labels = {int(index): str(value or "").strip()[:80] for index, value in enumerate(df.columns.tolist())}
    for row_index, row in df.iterrows():
        for column_index, raw_value in enumerate(row.tolist()):
            cells_scanned += 1
            matched = _record_match(
                raw_value=raw_value,
                normalized_account=normalized_account,
                location={
                    "sheet_name": sheet_label,
                    "row_index": int(row_index),
                    "row_number": int(row_index) + 1,
                    "column_index": int(column_index),
                    "column_number": int(column_index) + 1,
                    "column_label": header_labels.get(int(column_index), ""),
                    "row_zone": row_zone or _row_zone(int(row_index), int(header_row or 0)),
                    "source_region": source_region,
                },
                max_items=max_items,
                exact_locations=exact_locations,
                possible_locations=possible_locations,
            )
            if matched == "possible_leading_zero_loss":
                possible_match_count += 1
            elif matched:
                exact_match_count += 1
    return {
        "cells_scanned": cells_scanned,
        "exact_match_count": exact_match_count,
        "possible_match_count": possible_match_count,
    }


def _scan_ocr_tokens(
    *,
    tokens: list[dict[str, Any]],
    normalized_account: str,
    sheet_label: str,
    max_items: int,
    exact_locations: list[dict[str, Any]],
    possible_locations: list[dict[str, Any]],
) -> dict[str, int]:
    cells_scanned = 0
    exact_match_count = 0
    possible_match_count = 0
    for token_index, token in enumerate(tokens):
        raw_value = token.get("text")
        if not raw_value:
            continue
        cells_scanned += 1
        page_number = int(token.get("page_number") or 1)
        ocr_bbox = _coerce_ocr_bbox(token.get("bbox"))
        matched = _record_match(
            raw_value=raw_value,
            normalized_account=normalized_account,
            location={
                "sheet_name": sheet_label,
                "row_index": int(token_index),
                "row_number": int(token_index) + 1,
                "column_index": 0,
                "column_number": 1,
                "column_label": "ocr_token",
                "row_zone": "ocr_token",
                "source_region": "ocr_token",
                "page_number": page_number,
                "ocr_confidence": float(token.get("confidence") or 0),
                "x_center": token.get("x_center"),
                "y_center": token.get("y_center"),
                "ocr_bbox": ocr_bbox,
            },
            max_items=max_items,
            exact_locations=exact_locations,
            possible_locations=possible_locations,
        )
        if matched == "possible_leading_zero_loss":
            possible_match_count += 1
        elif matched:
            exact_match_count += 1
    return {
        "cells_scanned": cells_scanned,
        "exact_match_count": exact_match_count,
        "possible_match_count": possible_match_count,
    }


def _coerce_ocr_tokens(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    tokens: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict) and str(item.get("text") or "").strip():
            tokens.append(item)
    return tokens


def _coerce_ocr_bbox(value: Any) -> list[list[float]]:
    if not isinstance(value, list):
        return []
    points: list[list[float]] = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return []
        try:
            points.append([float(point[0]), float(point[1])])
        except (TypeError, ValueError):
            return []
    return points


def _merge_counts(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {
        "cells_scanned": int(left.get("cells_scanned") or 0) + int(right.get("cells_scanned") or 0),
        "exact_match_count": int(left.get("exact_match_count") or 0) + int(right.get("exact_match_count") or 0),
        "possible_match_count": int(left.get("possible_match_count") or 0) + int(right.get("possible_match_count") or 0),
    }


def _record_match(
    *,
    raw_value: Any,
    normalized_account: str,
    location: dict[str, Any],
    max_items: int,
    exact_locations: list[dict[str, Any]],
    possible_locations: list[dict[str, Any]],
) -> str:
    match_type = _match_type(raw_value, normalized_account)
    if not match_type:
        return ""
    next_location = {
        **location,
        "match_type": match_type,
        "value_preview": str(raw_value or "").strip()[:160],
    }
    if match_type == "possible_leading_zero_loss":
        if len(possible_locations) < max_items:
            possible_locations.append(next_location)
        return match_type
    if len(exact_locations) < max_items:
        exact_locations.append(next_location)
    return match_type


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
