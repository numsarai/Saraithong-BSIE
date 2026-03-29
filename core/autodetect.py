"""Workbook-level auto-detection helpers."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from core.bank_detector import detect_bank
from core.loader import find_best_sheet_and_header


def analyze_file(filepath: str, configs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scan workbook previews to detect the bank, likely subject account, and names.

    The `configs` parameter is retained for backward compatibility with existing
    callers, but bank detection now delegates to `core.bank_detector.detect_bank`
    so all code paths share the same normalized scoring logic.
    """
    _ = configs
    result = {
        "detected_bank": "",
        "detected_account": "",
        "detected_name": "",
        "account_candidates": [],
        "name_candidates": [],
    }

    try:
        workbook_path = Path(filepath)
        pick = find_best_sheet_and_header(filepath, preview_rows=60, scan_rows=20)
        best_df = pd.read_excel(
            filepath,
            sheet_name=pick["sheet_name"],
            header=int(pick["header_row"]),
            dtype=str,
        ).fillna("")
        best_df.columns = [str(col).strip() for col in best_df.columns]
        best_bank = detect_bank(best_df, extra_text=f"{workbook_path.stem} {pick['sheet_name']}")
        all_text: list[str] = []
        for _, row in best_df.head(200).iterrows():
            all_text.extend(str(val).strip() for val in row.values if str(val).strip())

        result["detected_bank"] = best_bank.get("config_key", "") or ""

        accounts = []
        acct_pattern = re.compile(r"\b\d{10}\b|\b\d{12}\b")
        for text in all_text:
            accounts.extend(acct_pattern.findall(text))

        if accounts:
            counter = Counter(accounts)
            sorted_accounts = [acc for acc, _count in counter.most_common()]
            result["account_candidates"] = sorted_accounts
            result["detected_account"] = sorted_accounts[0]

        prefixes = [
            "นาย ", "นาย", "นาง ", "นาง", "นางสาว ", "นางสาว",
            "น.ส. ", "น.ส.", "ด.ช. ", "ด.ช.", "ด.ญ. ", "ด.ญ.",
            "บริษัท ", "บจก.", "หจก.",
        ]
        names = set()
        for text in all_text:
            clean_text = re.sub(r"\s+", " ", str(text).strip())
            if clean_text in prefixes:
                continue
            for prefix in prefixes:
                if clean_text.startswith(prefix) and len(clean_text) > len(prefix):
                    names.add(clean_text)
                    break

        sorted_names = sorted(names)
        result["name_candidates"] = sorted_names
        if sorted_names:
            result["detected_name"] = sorted_names[0]

    except Exception:
        import traceback
        traceback.print_exc()

    return result
