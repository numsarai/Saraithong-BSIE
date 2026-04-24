from __future__ import annotations

from collections import defaultdict
from typing import Any

from core.normalizer import _clean_amount
from utils.date_utils import parse_date, parse_time
from utils.text_utils import normalize_text


AMOUNT_COLUMN_HINTS = {
    "debit": ("ถอน", "เดบิต", "debit", "withdraw", "withdrawal", "dr", "เงินออก", "outgoing"),
    "credit": ("ฝาก", "เครดิต", "credit", "deposit", "cr", "เงินเข้า", "incoming"),
}

MAPPING_FIELDS = {
    "date",
    "time",
    "description",
    "amount",
    "debit",
    "credit",
    "balance",
    "channel",
    "counterparty_account",
    "counterparty_name",
    "sender_account",
    "sender_name",
    "receiver_account",
    "receiver_name",
    "direction_marker",
}

DIRECTION_IN_MARKERS = {
    "credit",
    "cr",
    "c",
    "in",
    "deposit",
    "credit/in",
    "ฝาก",
    "ฝากเงิน",
    "รับ",
    "เข้า",
    "เงินเข้า",
}
DIRECTION_OUT_MARKERS = {
    "debit",
    "dr",
    "d",
    "out",
    "withdraw",
    "debit/out",
    "ถอน",
    "ถอนเงิน",
    "จ่าย",
    "ออก",
    "เงินออก",
}


def _issue(code: str, message: str, *, field: str = "", column: str = "", fields: list[str] | None = None) -> dict:
    item = {"code": code, "message": message}
    if field:
        item["field"] = field
    if column:
        item["column"] = column
    if fields:
        item["fields"] = fields
    return item


def clean_mapping(mapping: dict[str, Any] | None) -> dict[str, str | None]:
    cleaned: dict[str, str | None] = {}
    if not isinstance(mapping, dict):
        return cleaned
    for field, column in mapping.items():
        field_key = str(field or "").strip()
        if not field_key:
            continue
        if column is None:
            cleaned[field_key] = None
            continue
        column_text = str(column).strip()
        cleaned[field_key] = column_text or None
    return cleaned


def _clean_columns(columns: list[Any] | None) -> list[str]:
    result: list[str] = []
    for column in columns or []:
        text = str(column or "").strip()
        if text:
            result.append(text)
    return result


def validate_mapping(
    mapping: dict[str, Any] | None,
    columns: list[Any] | None,
    *,
    bank: str = "",
) -> dict:
    cleaned = clean_mapping(mapping)
    cleaned_columns = _clean_columns(columns)
    available_columns = set(cleaned_columns)
    errors: list[dict] = []
    warnings: list[dict] = []

    if not cleaned:
        errors.append(_issue("mapping_required", "Mapping is required."))

    unknown_fields = sorted(field for field in cleaned if field not in MAPPING_FIELDS)
    for field in unknown_fields:
        errors.append(_issue("unknown_field", f"Unknown mapping field '{field}'.", field=field))

    mapped_by_column: dict[str, list[str]] = defaultdict(list)
    for field, column in cleaned.items():
        if not column:
            continue
        if column not in available_columns:
            errors.append(
                _issue(
                    "unknown_column",
                    f"Mapped column '{column}' for '{field}' is not present in the uploaded sheet.",
                    field=field,
                    column=column,
                )
            )
            continue
        mapped_by_column[column].append(field)

    for column, fields in sorted(mapped_by_column.items()):
        if len(fields) > 1:
            errors.append(
                _issue(
                    "duplicate_column_assignment",
                    f"Column '{column}' is assigned to multiple fields: {', '.join(fields)}.",
                    column=column,
                    fields=fields,
                )
            )

    for field in ("date", "description"):
        if not cleaned.get(field):
            errors.append(
                _issue(
                    "missing_required_field",
                    f"Required field '{field}' must be mapped before confirmation.",
                    field=field,
                )
            )

    has_amount = bool(cleaned.get("amount"))
    has_debit = bool(cleaned.get("debit"))
    has_credit = bool(cleaned.get("credit"))
    has_direction_marker = bool(cleaned.get("direction_marker"))
    if not has_amount and not (has_debit or has_credit):
        errors.append(
            _issue(
                "missing_amount_path",
                "Map either a signed amount column, an amount + direction marker pair, or at least one debit/credit column.",
            )
        )
    if has_direction_marker and not has_amount:
        errors.append(
            _issue(
                "direction_marker_requires_amount",
                "Direction marker layouts must also map the unsigned amount column.",
                field="amount",
            )
        )
    if (has_amount or has_direction_marker) and (has_debit or has_credit):
        errors.append(
            _issue(
                "conflicting_amount_paths",
                "Use either signed/direction-marker amount or debit/credit columns, not both.",
                fields=[
                    *([field for field in ("amount", "direction_marker") if cleaned.get(field)]),
                    *([field for field in ("debit", "credit") if cleaned.get(field)]),
                ],
            )
        )
    if not has_direction_marker and ((has_debit and not has_credit) or (has_credit and not has_debit)):
        missing_side = "credit" if has_debit else "debit"
        warnings.append(
            _issue(
                "one_sided_amount_path",
                f"Only one side of the debit/credit pair is mapped; {missing_side} rows may need review.",
                field=missing_side,
            )
        )

    if not str(bank or "").strip():
        warnings.append(_issue("missing_bank", "Selected bank is empty; mapping can be used for this run but should not be promoted."))

    if has_amount and has_direction_marker:
        amount_mode = "direction_marker"
    elif has_amount:
        amount_mode = "signed"
    elif has_debit or has_credit:
        amount_mode = "debit_credit"
    else:
        amount_mode = "missing"

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "mapping": cleaned,
        "columns": cleaned_columns,
        "amount_mode": amount_mode,
        "mapped_fields": sorted(field for field, column in cleaned.items() if column),
    }


def build_mapping_preview(
    mapping: dict[str, Any] | None,
    sample_rows: list[dict[str, Any]] | None,
    *,
    max_rows: int = 5,
) -> dict:
    cleaned = clean_mapping(mapping)
    preview_rows: list[dict] = []
    invalid_date_rows = 0
    missing_amount_rows = 0
    valid_transaction_rows = 0

    for index, row in enumerate((sample_rows or [])[:max_rows], start=1):
        if not isinstance(row, dict):
            continue
        raw_date = row.get(cleaned.get("date") or "")
        parsed_date = parse_date(raw_date)
        raw_time = row.get(cleaned.get("time") or "")
        parsed_time = parse_time(raw_time) or ""
        raw_description = row.get(cleaned.get("description") or "")
        description = normalize_text(raw_description)

        raw_amount = row.get(cleaned.get("amount") or "")
        raw_debit = row.get(cleaned.get("debit") or "")
        raw_credit = row.get(cleaned.get("credit") or "")
        raw_direction_marker = row.get(cleaned.get("direction_marker") or "")
        direction_marker_sign = _direction_marker_sign(raw_direction_marker) if cleaned.get("direction_marker") else None
        amount = _preview_amount(raw_amount, raw_debit, raw_credit, direction_marker_sign, cleaned)
        balance = _clean_amount(row.get(cleaned.get("balance") or ""))

        row_warnings: list[str] = []
        if raw_date not in (None, "") and not parsed_date:
            invalid_date_rows += 1
            row_warnings.append("date_unparseable")
        if not description:
            row_warnings.append("description_missing")
        if amount is None:
            missing_amount_rows += 1
            row_warnings.append("amount_missing")
            if cleaned.get("direction_marker") and raw_direction_marker not in (None, "") and direction_marker_sign is None:
                row_warnings.append("direction_marker_unrecognized")
        else:
            valid_transaction_rows += 1

        direction = "UNKNOWN"
        if amount is not None:
            if amount > 0:
                direction = "IN"
            elif amount < 0:
                direction = "OUT"

        preview_rows.append(
            {
                "row_index": index,
                "date": parsed_date.isoformat() if parsed_date else "",
                "time": parsed_time,
                "description": description,
                "amount": amount,
                "direction": direction,
                "balance": balance,
                "source": {
                    "date": raw_date,
                    "description": raw_description,
                    "amount": raw_amount,
                    "debit": raw_debit,
                    "credit": raw_credit,
                    "direction_marker": raw_direction_marker,
                    "balance": row.get(cleaned.get("balance") or ""),
                },
                "warnings": row_warnings,
                "status": "ok" if amount is not None and parsed_date else ("warning" if amount is not None else "rejected"),
            }
        )

    return {
        "rows": preview_rows,
        "summary": {
            "sample_row_count": len(sample_rows or []),
            "preview_row_count": len(preview_rows),
            "valid_transaction_rows": valid_transaction_rows,
            "invalid_date_rows": invalid_date_rows,
            "missing_amount_rows": missing_amount_rows,
        },
    }


def validate_and_preview_mapping(
    *,
    bank: str,
    mapping: dict[str, Any] | None,
    columns: list[Any] | None,
    sample_rows: list[dict[str, Any]] | None = None,
) -> dict:
    validation = validate_mapping(mapping, columns, bank=bank)
    amount_sample_errors = _amount_sample_sanity_errors(
        validation["mapping"],
        validation["columns"],
        sample_rows or [],
    )
    if amount_sample_errors:
        validation = {
            **validation,
            "errors": [*validation["errors"], *amount_sample_errors],
            "ok": False,
        }
    preview = build_mapping_preview(validation["mapping"], sample_rows or [])
    return {
        **validation,
        "dry_run_preview": preview,
    }


def _direction_marker_sign(raw_marker: Any) -> int | None:
    marker = normalize_text(raw_marker).lower()
    if not marker:
        return None
    if marker in DIRECTION_IN_MARKERS:
        return 1
    if marker in DIRECTION_OUT_MARKERS:
        return -1
    return None


def _preview_amount(
    raw_amount: Any,
    raw_debit: Any,
    raw_credit: Any,
    direction_marker_sign: int | None,
    mapping: dict[str, str | None],
) -> float | None:
    if mapping.get("amount"):
        amount = _clean_amount(raw_amount)
        if amount is None:
            return None
        if mapping.get("direction_marker"):
            if direction_marker_sign is None:
                return None
            return round(abs(amount) * direction_marker_sign, 6)
        return amount

    debit = _clean_amount(raw_debit) or 0.0
    credit = _clean_amount(raw_credit) or 0.0
    if not debit and not credit:
        return None
    return round(credit - debit, 6)


def _amount_sample_sanity_errors(
    mapping: dict[str, str | None],
    columns: list[str],
    sample_rows: list[dict[str, Any]],
) -> list[dict]:
    if not sample_rows or not mapping.get("debit") or not mapping.get("credit"):
        return []

    errors: list[dict] = []
    for field in ("debit", "credit"):
        mapped_column = mapping.get(field)
        if not mapped_column:
            continue
        mapped_nonzero = _nonzero_numeric_count(sample_rows, mapped_column)
        if mapped_nonzero:
            continue

        candidate = _best_amount_hint_column(field, columns, exclude=mapped_column)
        if not candidate:
            continue
        candidate_nonzero = _nonzero_numeric_count(sample_rows, candidate)
        if not candidate_nonzero:
            continue

        errors.append(
            _issue(
                "suspicious_amount_column",
                f"Mapped '{field}' column '{mapped_column}' has no numeric values in the sample, "
                f"but likely column '{candidate}' has transaction amounts.",
                field=field,
                column=mapped_column,
            )
        )

    return errors


def _best_amount_hint_column(field: str, columns: list[str], *, exclude: str) -> str:
    hints = AMOUNT_COLUMN_HINTS.get(field, ())
    for column in columns:
        if column == exclude:
            continue
        normalized = normalize_text(column).lower()
        if any(hint in normalized for hint in hints):
            return column
    return ""


def _nonzero_numeric_count(sample_rows: list[dict[str, Any]], column: str) -> int:
    count = 0
    for row in sample_rows:
        if not isinstance(row, dict):
            continue
        amount = _clean_amount(row.get(column))
        if amount:
            count += 1
    return count
