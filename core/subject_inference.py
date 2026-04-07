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

from collections import Counter
import re
from pathlib import Path
from typing import Any

import pandas as pd

from core.account_parser import parse_account


ACCOUNT_ALIASES = {
    "เลขที่บัญชี",
    "หมายเลขบัญชี",
    "บัญชีเลขที่",
    "บัญชีผู้โอน",
    "บัญชีผู้รับโอน",
    "เลขบัญชีผู้โอน",
    "เลขบัญชีผู้รับโอน",
    "account number",
    "account no",
    "account no.",
    "a/c no",
    "sender account",
    "receiver account",
    "from account",
    "to account",
    "account",
}

NAME_ALIASES = {
    "ชื่อบัญชี",
    "ชื่อเจ้าของบัญชี",
    "ชื่อบัญชีผู้ถือ",
    "ชื่อผู้โอน",
    "ชื่อผู้รับโอน",
    "ชื่อ-สกุล",
    "ชื่อสกุล",
    "account name",
    "account holder",
    "holder name",
    "sender name",
    "receiver name",
    "from name",
    "to name",
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
    "ตั้งแต่วันที่",
}

NAME_TRAILING_STOP_TOKENS = {
    "สาขา",
    "branch",
    "เลขที่บัญชี",
    "หมายเลขบัญชี",
    "account number",
    "account no",
    "account no.",
    "วันที่",
    "ตั้งแต่วันที่",
}


def infer_subject_identity(
    file_path: str | Path,
    preview_df: pd.DataFrame | None = None,
    transaction_df: pd.DataFrame | None = None,
) -> dict[str, str]:
    return infer_subject_identity_from_frames(
        file_path,
        preview_df=preview_df,
        transaction_df=transaction_df,
    )


def infer_subject_identity_from_frames(
    file_path: str | Path,
    *,
    preview_df: pd.DataFrame | None = None,
    transaction_df: pd.DataFrame | None = None,
) -> dict[str, str]:
    file_path = Path(file_path)

    filename_identity = _infer_from_filename(file_path.stem)
    workbook_identity = _infer_from_preview(preview_df)
    transaction_identity = _infer_from_transaction_rows(transaction_df)

    account = (
        filename_identity["account"]
        or workbook_identity["account"]
        or transaction_identity["account"]
    )
    name = (
        workbook_identity["name"]
        or filename_identity["name"]
        or transaction_identity["name"]
    )
    account_source = (
        filename_identity.get("account_source", "")
        or workbook_identity.get("account_source", "")
        or transaction_identity.get("account_source", "")
    )
    name_source = (
        workbook_identity.get("name_source", "")
        or filename_identity.get("name_source", "")
        or transaction_identity.get("name_source", "")
    )
    sources = {value for value in (account_source, name_source) if value}
    if not sources:
        source = ""
    elif len(sources) == 1:
        source = next(iter(sources))
    else:
        source = "mixed"

    return {
        "account": account,
        "name": name,
        "account_source": account_source,
        "name_source": name_source,
        "source": source,
    }


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

    return {
        "account": account,
        "name": name,
        "account_source": "filename" if account else "",
        "name_source": "filename" if name else "",
    }


def _infer_from_preview(preview_df: pd.DataFrame | None) -> dict[str, str]:
    if preview_df is None or preview_df.empty:
        return {"account": "", "name": "", "account_source": "", "name_source": ""}

    account = ""
    name = ""
    scan_rows = min(len(preview_df), 15)
    scan_cols = min(len(preview_df.columns), 8)

    for row_idx in range(scan_rows):
        row_values = [str(preview_df.iat[row_idx, col_idx] or "").strip() for col_idx in range(scan_cols)]
        next_row_values = (
            [str(preview_df.iat[row_idx + 1, col_idx] or "").strip() for col_idx in range(scan_cols)]
            if row_idx + 1 < scan_rows
            else []
        )
        alias_like_count = sum(1 for value in row_values if _looks_like_alias(value))
        for col_idx, cell in enumerate(row_values):
            lower = _norm(cell)
            if not account and any(alias in lower for alias in ACCOUNT_ALIASES):
                account = _extract_first_account(cell)
                if not account and alias_like_count <= 1:
                    account = _extract_neighbor_account(row_values, col_idx)
                if not account and next_row_values and alias_like_count <= 1:
                    account = _extract_neighbor_account(next_row_values, col_idx)
            if not name and any(alias in lower for alias in NAME_ALIASES):
                name = _extract_name_from_labeled_cell(cell)
                if not name:
                    name = _extract_inline_labeled_name(cell)
                if not name and alias_like_count <= 1:
                    name = _extract_neighbor_name(row_values, col_idx)
                if not name and next_row_values and alias_like_count <= 1:
                    name = _extract_neighbor_name(next_row_values, col_idx)
        if account and name:
            break

    return {
        "account": account,
        "name": name,
        "account_source": "workbook_header" if account else "",
        "name_source": "workbook_header" if name else "",
    }


def _infer_from_transaction_rows(transaction_df: pd.DataFrame | None) -> dict[str, str]:
    if transaction_df is None or transaction_df.empty:
        return {"account": "", "name": "", "account_source": "", "name_source": ""}

    scan_df = transaction_df.head(25).copy()
    account_columns = [column for column in scan_df.columns if _looks_like_account_column(column)]
    name_columns = [column for column in scan_df.columns if _looks_like_name_column(column)]
    if not account_columns:
        return {"account": "", "name": "", "account_source": "", "name_source": ""}

    account_counts: Counter[str] = Counter()
    for _, row in scan_df.iterrows():
        for column in account_columns:
            parsed = parse_account(row.get(column, ""))
            if parsed["type"] == "ACCOUNT" and parsed["clean"]:
                account_counts[parsed["clean"]] += 1

    if not account_counts:
        return {"account": "", "name": "", "account_source": "", "name_source": ""}

    ranked_accounts = account_counts.most_common(2)
    top_account, top_count = ranked_accounts[0]
    second_count = ranked_accounts[1][1] if len(ranked_accounts) > 1 else 0
    if top_count < 2 or top_count <= second_count:
        return {"account": "", "name": "", "account_source": "", "name_source": ""}

    name_counts: Counter[str] = Counter()
    if name_columns:
        for _, row in scan_df.iterrows():
            row_accounts = {
                parse_account(row.get(column, "")).get("clean", "")
                for column in account_columns
            }
            if top_account not in row_accounts:
                continue
            for column in name_columns:
                candidate = _clean_name_fragment(row.get(column, ""))
                if not candidate or _looks_like_alias(candidate):
                    continue
                if _extract_account_candidates(candidate):
                    continue
                name_counts[candidate] += 1

    top_name = ""
    if name_counts:
        ranked_names = name_counts.most_common(2)
        candidate_name, candidate_count = ranked_names[0]
        second_name_count = ranked_names[1][1] if len(ranked_names) > 1 else 0
        if candidate_count >= 2 and candidate_count > second_name_count:
            top_name = candidate_name

    return {
        "account": top_account,
        "name": top_name,
        "account_source": "transaction_pattern",
        "name_source": "transaction_pattern" if top_name else "",
    }


def _extract_account_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    stripped_text = str(text or "").strip()
    if re.match(r"^-?\d+(\.\d+)?[eE][+\-]?\d+$", stripped_text) or re.match(r"^-?\d+\.\d+$", stripped_text):
        parsed = parse_account(stripped_text)
        if parsed["type"] == "ACCOUNT" and parsed["clean"]:
            return [parsed["clean"]]
    for digits in re.findall(r"\d{10,12}", text):
        if digits not in seen:
            seen.add(digits)
            candidates.append(digits)
    parsed = parse_account(text)
    if parsed["type"] == "ACCOUNT" and parsed["clean"] and parsed["clean"] not in seen:
        seen.add(parsed["clean"])
        candidates.append(parsed["clean"])
    for raw in re.findall(r"[\d\- ]{8,20}", text):
        parsed = parse_account(raw)
        digits = str(parsed.get("clean") or "")
        if parsed["type"] == "ACCOUNT" and digits and digits not in seen:
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


def _extract_inline_labeled_name(cell: str) -> str:
    text = str(cell or "").strip()
    if not text:
        return ""

    for alias in sorted(NAME_ALIASES, key=len, reverse=True):
        pattern = rf"{re.escape(alias)}\s*[:：]?\s*(.+)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(1).strip()
        candidate = _trim_name_tail(candidate)
        cleaned = _clean_name_fragment(candidate)
        if cleaned and not _looks_like_alias(cleaned):
            return cleaned
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


def _trim_name_tail(text: str) -> str:
    for token in sorted(NAME_TRAILING_STOP_TOKENS, key=len, reverse=True):
        pattern = rf"\s+{re.escape(token)}"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return text[:match.start()].strip(" -_/")
    return text.strip(" -_/")


def _looks_like_alias(value: str) -> bool:
    lowered = _norm(value)
    return any(alias in lowered for alias in ACCOUNT_ALIASES | NAME_ALIASES)


def _looks_like_account_column(value: Any) -> bool:
    lowered = _norm(value)
    return any(alias in lowered for alias in ACCOUNT_ALIASES)


def _looks_like_name_column(value: Any) -> bool:
    lowered = _norm(value)
    return any(alias in lowered for alias in NAME_ALIASES)


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    return text
