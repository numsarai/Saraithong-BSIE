"""
subject_inference.py
--------------------
Conservative subject account/name inference for bulk statement intake.

The goal is not to guess aggressively. We prefer:
1. explicit account numbers in the filename
2. explicit account/name labels in the workbook header area
3. blank values when evidence is weak
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd


ACCOUNT_ALIASES = {
    "เลขที่บัญชี",
    "หมายเลขบัญชี",
    "บัญชีเลขที่",
    "account number",
    "account no",
    "account no.",
    "a/c no",
    "account",
}

NAME_ALIASES = {
    "ชื่อบัญชี",
    "ชื่อเจ้าของบัญชี",
    "ชื่อบัญชีผู้ถือ",
    "ชื่อ-สกุล",
    "ชื่อสกุล",
    "account name",
    "account holder",
    "holder name",
    "customer name",
    "name",
}

IGNORE_NAME_TOKENS = {
    "ตัวอย่าง",
    "statement",
    "estatment",
    "estatement",
    "sample",
    "stm",
    "bank statement",
    "e statement",
}


def infer_subject_identity(file_path: str | Path, preview_df: pd.DataFrame | None = None) -> dict[str, str]:
    file_path = Path(file_path)

    filename_identity = _infer_from_filename(file_path.stem)
    if filename_identity["account"]:
        return filename_identity

    workbook_identity = _infer_from_preview(preview_df)
    return workbook_identity


def _infer_from_filename(stem: str) -> dict[str, str]:
    compact = re.sub(r"\s+", " ", stem).strip()
    account_candidates = _extract_account_candidates(compact)
    account = account_candidates[0] if account_candidates else ""
    name = ""

    if account:
        pattern = re.escape(account)
        match = re.search(pattern, re.sub(r"[^\wก-๙]+", " ", compact).replace("_", " "))
        if match:
            tail = compact[match.end():]
        else:
            tail = compact.split(account, 1)[-1]
        name = _clean_name_fragment(tail)

    return {"account": account, "name": name}


def _infer_from_preview(preview_df: pd.DataFrame | None) -> dict[str, str]:
    if preview_df is None or preview_df.empty:
        return {"account": "", "name": ""}

    account = ""
    name = ""
    scan_rows = min(len(preview_df), 15)
    scan_cols = min(len(preview_df.columns), 8)

    for row_idx in range(scan_rows):
        row_values = [str(preview_df.iat[row_idx, col_idx] or "").strip() for col_idx in range(scan_cols)]
        for col_idx, cell in enumerate(row_values):
            lower = _norm(cell)
            if not account and any(alias in lower for alias in ACCOUNT_ALIASES):
                account = _extract_first_account(cell) or _extract_neighbor_account(row_values, col_idx)
            if not name and any(alias in lower for alias in NAME_ALIASES):
                name = _extract_name_from_labeled_cell(cell) or _extract_neighbor_name(row_values, col_idx)
        if account and name:
            break

    return {"account": account, "name": name}


def _extract_account_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for digits in re.findall(r"\d{10,12}", text):
        if digits not in seen:
            seen.add(digits)
            candidates.append(digits)
    for raw in re.findall(r"[\d\- ]{8,20}", text):
        digits = re.sub(r"\D", "", raw)
        if len(digits) in {10, 12} and digits not in seen:
            seen.add(digits)
            candidates.append(digits)
    return candidates


def _extract_first_account(text: str) -> str:
    candidates = _extract_account_candidates(text)
    return candidates[0] if candidates else ""


def _extract_neighbor_account(row_values: list[str], anchor_idx: int) -> str:
    for candidate in row_values[anchor_idx: anchor_idx + 3]:
        account = _extract_first_account(candidate)
        if account:
            return account
    return ""


def _extract_name_from_labeled_cell(cell: str) -> str:
    parts = re.split(r"[:：]", cell, maxsplit=1)
    if len(parts) == 2:
        return _clean_name_fragment(parts[1])
    return ""


def _extract_neighbor_name(row_values: list[str], anchor_idx: int) -> str:
    for candidate in row_values[anchor_idx: anchor_idx + 3]:
        cleaned = _clean_name_fragment(candidate)
        if cleaned and not _looks_like_alias(cleaned):
            return cleaned
    return ""


def _clean_name_fragment(value: Any) -> str:
    text = str(value or "").strip(" -_./")
    text = re.sub(r"\.(xlsx|xls)$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:A-\d+-)?EStatement\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""

    lowered = _norm(text)
    if lowered in IGNORE_NAME_TOKENS:
        return ""

    for token in IGNORE_NAME_TOKENS:
        if lowered.startswith(token):
            trimmed = text[len(token):].strip(" -_")
            return trimmed
    return text


def _looks_like_alias(value: str) -> bool:
    lowered = _norm(value)
    return any(alias in lowered for alias in ACCOUNT_ALIASES | NAME_ALIASES)


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    return text
