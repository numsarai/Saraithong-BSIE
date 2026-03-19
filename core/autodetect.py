import pandas as pd
import re
from collections import Counter
from typing import Dict, Any, List

def analyze_file(filepath: str, configs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scans the first 100 rows of an Excel file to auto-detect:
    - The most likely Bank Configuration
    - The Subject Account Number (10 or 12 digits)
    - Likely Account Holder Names (using common Thai prefixes)
    """
    result = {
        "detected_bank": "",
        "detected_account": "",
        "detected_name": "",
        "account_candidates": [],
        "name_candidates": []
    }

    try:
        # Read the first 100 rows across all sheets to gather text
        xls = pd.ExcelFile(filepath)
        all_text = []
        all_headers = []

        for sheet in xls.sheet_names:
            df = pd.read_excel(filepath, sheet_name=sheet, header=None, nrows=100)
            df = df.fillna("")
            
            # Extract headers for bank detection (first 10 rows usually)
            head_df = df.head(10)
            for _, row in head_df.iterrows():
                all_headers.extend([str(val).strip() for val in row.values if str(val).strip()])

            # Extract all text for account/name detection
            for _, row in df.iterrows():
                all_text.extend([str(val).strip() for val in row.values if str(val).strip()])

        # 1. Detect Bank based on headers
        bank_scores = {key: 0 for key in configs.keys()}
        for key, cfg in configs.items():
            col_map = cfg.get("column_mapping", {})
            aliases = []
            for mapped_aliases in col_map.values():
                aliases.extend(mapped_aliases)
            
            # Score this bank if we find its exact aliases in the document
            for h in all_headers:
                if h in aliases:
                    bank_scores[key] += 1

        if bank_scores:
            best_bank = max(bank_scores.items(), key=lambda x: x[1])
            if best_bank[1] > 0:
                result["detected_bank"] = best_bank[0]

        # 2. Detect Account Numbers (10 or 12 digits)
        accounts = []
        acct_pattern = re.compile(r'\b\d{10}\b|\b\d{12}\b')
        for text in all_text:
            matches = acct_pattern.findall(text)
            accounts.extend(matches)
        
        if accounts:
            # Sort by frequency (most common is usually the subject account)
            counter = Counter(accounts)
            sorted_accounts = [acc for acc, count in counter.most_common()]
            result["account_candidates"] = sorted_accounts
            result["detected_account"] = sorted_accounts[0]

        # 3. Detect Names (Look for Strings starting with common Thai prefixes)
        prefixes = ["นาย ", "นาย", "นาง ", "นาง", "นางสาว ", "นางสาว", "น.ส. ", "น.ส.", "ด.ช. ", "ด.ช.", "ด.ญ. ", "ด.ญ.", "บริษัท ", "บจก.", "หจก."]
        names = set()
        for text in all_text:
            text_str = str(text).strip()
            # If the cell is exactly a prefix, skip it
            if text_str in prefixes:
                continue
            for p in prefixes:
                if text_str.startswith(p) and len(text_str) > len(p):
                    # Clean up multiple spaces
                    clean_name = re.sub(r'\s+', ' ', text_str).strip()
                    names.add(clean_name)
                    break # Don't match multiple prefixes

        sorted_names = sorted(list(names))
        result["name_candidates"] = sorted_names
        if sorted_names:
            result["detected_name"] = sorted_names[0]

    except Exception as e:
        import traceback
        print(f"Auto-detect error: {e}")
        traceback.print_exc()

    return result
