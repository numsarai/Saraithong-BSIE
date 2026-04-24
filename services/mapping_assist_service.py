from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any

from services.llm_service import chat, chat_with_file, resolve_model
from services.mapping_validation_service import validate_mapping
from utils.app_helpers import repair_suggested_mapping

ASSIST_FIELDS = (
    "date",
    "time",
    "description",
    "amount",
    "direction_marker",
    "debit",
    "credit",
    "balance",
    "channel",
    "counterparty_account",
    "counterparty_name",
)
DEFAULT_MAPPING_MODEL = os.getenv("OLLAMA_MAPPING_MODEL", "gemma4:26b").strip() or "gemma4:26b"
MAX_VISION_ASSIST_BYTES = 25 * 1024 * 1024
MAPPING_ASSIST_MAX_TOKENS = 1024
VISION_IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".bmp": "image/bmp",
}


def _clean_columns(columns: list[Any] | None) -> list[str]:
    result: list[str] = []
    for column in columns or []:
        text = str(column or "").strip()
        if text and text not in result:
            result.append(text[:160])
    return result[:80]


def _clean_sample_rows(sample_rows: list[dict[str, Any]] | None, columns: list[str]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    allowed = set(columns)
    for row in (sample_rows or [])[:5]:
        if not isinstance(row, dict):
            continue
        item: dict[str, str] = {}
        for key, value in row.items():
            key_text = str(key or "").strip()
            if key_text not in allowed:
                continue
            item[key_text] = str(value or "").strip()[:160]
        cleaned.append(item)
    return cleaned


def _clean_current_mapping(mapping: dict[str, Any] | None, columns: list[str]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    available = set(columns)
    if not isinstance(mapping, dict):
        return result
    for field in ASSIST_FIELDS:
        value = mapping.get(field)
        if value is None:
            result[field] = None
            continue
        text = str(value or "").strip()
        result[field] = text if text in available else None
    return result


def _extract_json_object(text: str) -> dict[str, Any]:
    content = str(text or "").strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        content = fence_match.group(1).strip()
    elif "{" in content and "}" in content:
        content = content[content.find("{"):content.rfind("}") + 1]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM mapping assist did not return valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("LLM mapping assist JSON must be an object")
    return parsed


def _list_text(value: Any, *, limit: int = 6) -> list[str]:
    if isinstance(value, list):
        return [str(item or "").strip()[:240] for item in value[:limit] if str(item or "").strip()]
    text = str(value or "").strip()
    return [text[:240]] if text else []


def _clean_llm_mapping(raw_mapping: Any, columns: list[str]) -> tuple[dict[str, str | None], list[str]]:
    warnings: list[str] = []
    available = set(columns)
    cleaned: dict[str, str | None] = {field: None for field in ASSIST_FIELDS}
    if not isinstance(raw_mapping, dict):
        warnings.append("LLM response did not include a mapping object.")
        return cleaned, warnings

    for field in ASSIST_FIELDS:
        value = raw_mapping.get(field)
        if value in (None, ""):
            continue
        column = str(value or "").strip()
        if column in available:
            cleaned[field] = column
        else:
            warnings.append(f"Ignored {field}: column '{column}' is not present in the uploaded sheet.")
    return cleaned, warnings


def _build_prompt(
    *,
    bank: str,
    detected_bank: Any,
    columns: list[str],
    sample_rows: list[dict[str, str]],
    current_mapping: dict[str, str | None],
    sheet_name: str,
    header_row: int,
) -> str:
    payload = {
        "bank": bank,
        "detected_bank": detected_bank if isinstance(detected_bank, dict) else {},
        "sheet_name": sheet_name,
        "header_row": header_row,
        "columns": columns,
        "sample_rows": sample_rows,
        "current_mapping": current_mapping,
        "allowed_fields": list(ASSIST_FIELDS),
    }
    return (
        "You are assisting a Thai bank statement mapping review inside BSIE.\n"
        "Use only the provided column names. Do not invent columns, accounts, dates, amounts, banks, or transactions.\n"
        "For unsigned amount columns paired with DR/CR, IN/OUT, or ฝาก/ถอน markers, map the amount column to amount and the marker column to direction_marker.\n"
        "Return JSON only with this exact shape:\n"
        "{\n"
        "  \"mapping\": {\"date\": null, \"time\": null, \"description\": null, \"amount\": null, \"direction_marker\": null, \"debit\": null, \"credit\": null, \"balance\": null, \"channel\": null, \"counterparty_account\": null, \"counterparty_name\": null},\n"
        "  \"confidence\": 0.0,\n"
        "  \"reasons\": [\"short evidence-based reason\"],\n"
        "  \"warnings\": [\"uncertainty or missing evidence\"]\n"
        "}\n"
        "If unsure, leave the field null and explain in warnings. Prefer exactly one amount path: signed amount, amount + direction_marker, or debit/credit.\n\n"
        f"Context JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _build_vision_prompt(
    *,
    bank: str,
    detected_bank: Any,
    columns: list[str],
    sample_rows: list[dict[str, str]],
    current_mapping: dict[str, str | None],
    sheet_name: str,
    header_row: int,
    file_context: dict[str, Any],
) -> str:
    payload = {
        "bank": bank,
        "detected_bank": detected_bank if isinstance(detected_bank, dict) else {},
        "sheet_name": sheet_name,
        "header_row": header_row,
        "source_type": file_context.get("source_type", ""),
        "page_count": file_context.get("page_count"),
        "columns": columns,
        "ocr_sample_rows": sample_rows,
        "current_mapping": current_mapping,
        "allowed_fields": list(ASSIST_FIELDS),
    }
    return (
        "You are assisting a Thai bank statement mapping review inside BSIE using the original PDF/image preview.\n"
        "Use the visual evidence only to choose among the provided OCR/extracted column names.\n"
        "Do not invent columns, rows, transactions, accounts, names, dates, amounts, banks, or balances.\n"
        "For unsigned amount columns paired with DR/CR, IN/OUT, or ฝาก/ถอน markers, map the amount column to amount and the marker column to direction_marker.\n"
        "Return JSON only with this exact shape:\n"
        "{\n"
        "  \"mapping\": {\"date\": null, \"time\": null, \"description\": null, \"amount\": null, \"direction_marker\": null, \"debit\": null, \"credit\": null, \"balance\": null, \"channel\": null, \"counterparty_account\": null, \"counterparty_name\": null},\n"
        "  \"confidence\": 0.0,\n"
        "  \"reasons\": [\"short visual evidence-based reason\"],\n"
        "  \"warnings\": [\"uncertainty, OCR issue, cropped area, or missing evidence\"]\n"
        "}\n"
        "If unsure, leave the field null and explain in warnings. Prefer exactly one amount path: signed amount, amount + direction_marker, or debit/credit.\n\n"
        f"Context JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _load_vision_preview(file_path: Path) -> tuple[bytes, str, dict[str, Any]]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix not in {".pdf", *VISION_IMAGE_TYPES.keys()}:
        raise ValueError("Vision mapping assist supports PDF and image files only")
    if not path.exists():
        raise FileNotFoundError("Source evidence file not found")
    if path.stat().st_size > MAX_VISION_ASSIST_BYTES:
        raise ValueError("Source file is too large for vision mapping assist")

    if suffix == ".pdf":
        import fitz  # PyMuPDF

        doc = fitz.open(path)
        try:
            page_count = int(doc.page_count or 0)
            if page_count <= 0:
                raise ValueError("PDF has no pages for vision mapping assist")
            page = doc[0]
            pix = page.get_pixmap(dpi=180)
            return (
                pix.tobytes("png"),
                "image/png",
                {"source_type": "pdf_vision", "page_count": page_count, "preview_page": 1},
            )
        finally:
            doc.close()

    return (
        path.read_bytes(),
        VISION_IMAGE_TYPES[suffix],
        {"source_type": "image_vision", "page_count": 1, "preview_page": 1},
    )


async def suggest_mapping_with_llm(
    *,
    bank: str,
    detected_bank: Any = None,
    columns: list[Any] | None = None,
    sample_rows: list[dict[str, Any]] | None = None,
    current_mapping: dict[str, Any] | None = None,
    sheet_name: str = "",
    header_row: int = 0,
    model: str = "",
) -> dict[str, Any]:
    clean_columns = _clean_columns(columns)
    clean_rows = _clean_sample_rows(sample_rows, clean_columns)
    clean_current = _clean_current_mapping(current_mapping, clean_columns)
    prompt = _build_prompt(
        bank=str(bank or "").strip(),
        detected_bank=detected_bank,
        columns=clean_columns,
        sample_rows=clean_rows,
        current_mapping=clean_current,
        sheet_name=str(sheet_name or "").strip(),
        header_row=int(header_row or 0),
    )
    selected_model = resolve_model(str(model or "").strip() or DEFAULT_MAPPING_MODEL, "text")
    result = await chat(
        prompt,
        auto_context=False,
        model=selected_model,
        max_tokens=MAPPING_ASSIST_MAX_TOKENS,
        think=False,
    )
    raw = _extract_json_object(result.get("response", ""))
    llm_mapping, mapping_warnings = _clean_llm_mapping(raw.get("mapping"), clean_columns)
    merged_mapping = repair_suggested_mapping(
        {**clean_current, **{field: value for field, value in llm_mapping.items() if value}},
        clean_current,
        clean_columns,
    )
    validation = validate_mapping(merged_mapping, clean_columns, bank=str(bank or ""))
    confidence = raw.get("confidence", 0)
    try:
        confidence_float = max(0.0, min(1.0, float(confidence or 0)))
    except (TypeError, ValueError):
        confidence_float = 0.0
    warnings = [*mapping_warnings, *_list_text(raw.get("warnings"))]

    return {
        "status": "ok",
        "source": "local_llm_mapping_assist",
        "suggestion_only": True,
        "auto_pass_eligible": False,
        "model": result.get("model") or selected_model,
        "mapping": merged_mapping,
        "confidence": confidence_float,
        "reasons": _list_text(raw.get("reasons")),
        "warnings": warnings,
        "validation": {
            "ok": validation["ok"],
            "errors": validation.get("errors", []),
            "warnings": validation.get("warnings", []),
            "amount_mode": validation.get("amount_mode"),
            "mapped_fields": validation.get("mapped_fields", []),
        },
    }


async def suggest_mapping_with_vision_llm(
    *,
    file_path: str | Path,
    bank: str,
    detected_bank: Any = None,
    columns: list[Any] | None = None,
    sample_rows: list[dict[str, Any]] | None = None,
    current_mapping: dict[str, Any] | None = None,
    sheet_name: str = "",
    header_row: int = 0,
    model: str = "",
) -> dict[str, Any]:
    clean_columns = _clean_columns(columns)
    clean_rows = _clean_sample_rows(sample_rows, clean_columns)
    clean_current = _clean_current_mapping(current_mapping, clean_columns)
    preview_bytes, content_type, file_context = _load_vision_preview(Path(file_path))
    prompt = _build_vision_prompt(
        bank=str(bank or "").strip(),
        detected_bank=detected_bank,
        columns=clean_columns,
        sample_rows=clean_rows,
        current_mapping=clean_current,
        sheet_name=str(sheet_name or "").strip(),
        header_row=int(header_row or 0),
        file_context=file_context,
    )
    selected_model = resolve_model(str(model or "").strip() or DEFAULT_MAPPING_MODEL, "vision")
    result = await chat_with_file(
        prompt,
        preview_bytes,
        content_type,
        model=selected_model,
        max_tokens=MAPPING_ASSIST_MAX_TOKENS,
        think=False,
    )
    raw = _extract_json_object(result.get("response", ""))
    llm_mapping, mapping_warnings = _clean_llm_mapping(raw.get("mapping"), clean_columns)
    merged_mapping = repair_suggested_mapping(
        {**clean_current, **{field: value for field, value in llm_mapping.items() if value}},
        clean_current,
        clean_columns,
    )
    validation = validate_mapping(merged_mapping, clean_columns, bank=str(bank or ""))
    confidence = raw.get("confidence", 0)
    try:
        confidence_float = max(0.0, min(1.0, float(confidence or 0)))
    except (TypeError, ValueError):
        confidence_float = 0.0
    warnings = [*mapping_warnings, *_list_text(raw.get("warnings"))]

    return {
        "status": "ok",
        "source": "local_llm_vision_mapping_assist",
        "suggestion_only": True,
        "auto_pass_eligible": False,
        "model": result.get("model") or selected_model,
        "mapping": merged_mapping,
        "confidence": confidence_float,
        "reasons": _list_text(raw.get("reasons")),
        "warnings": warnings,
        "file_context": file_context,
        "validation": {
            "ok": validation["ok"],
            "errors": validation.get("errors", []),
            "warnings": validation.get("warnings", []),
            "amount_mode": validation.get("amount_mode"),
            "mapped_fields": validation.get("mapped_fields", []),
        },
    }
