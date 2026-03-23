"""
bank_detector.py
----------------
Auto-detects the bank from an Excel DataFrame's column names, cell content,
and description patterns. Scores all known bank configs and returns the winner.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

from paths import CONFIG_DIR as _CONFIG_DIR

# Hard-coded bank signatures for banks NOT yet in config/
_EXTRA_SIGNATURES: Dict[str, Dict] = {
    "BBL": {
        "keywords": ["bbl", "กรุงเทพ", "bangkok bank"],
        "column_clues": ["debit", "credit", "balance"],
    },
    "KTB": {
        "keywords": ["ktb", "กรุงไทย", "krungthai"],
        "column_clues": ["ถอน", "ฝาก", "คงเหลือ"],
    },
    "BAY": {
        "keywords": ["bay", "กรุงศรี", "krungsri", "ayudhya"],
        "column_clues": [],
    },
    "TTB": {
        "keywords": ["ttb", "tmb", "ทหารไทย", "ธนชาต"],
        "column_clues": [],
    },
    "GSB": {
        "keywords": ["gsb", "ออมสิน", "government savings"],
        "column_clues": [],
    },
    "BAAC": {
        "keywords": ["baac", "ธกส", "เพื่อการเกษตร"],
        "column_clues": [],
    },
}


def _load_all_configs() -> Dict[str, dict]:
    """Load all bank JSON configs from the config directory."""
    configs: Dict[str, dict] = {}
    if not _CONFIG_DIR.exists():
        return configs
    for f in _CONFIG_DIR.glob("*.json"):
        try:
            configs[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            logger.debug(f"Could not load config {f}: {e}")
    return configs


def detect_bank(
    df: pd.DataFrame,
    extra_text: str = "",
) -> Dict:
    """
    Score every known bank config against the DataFrame columns and cell content.

    Parameters
    ----------
    df         : raw DataFrame (columns + first rows are examined)
    extra_text : additional context string (e.g. filename, sheet name)

    Returns
    -------
    {
        "bank"       : str   – best-match bank name
        "config_key" : str   – config file key (e.g. "scb")
        "confidence" : float – 0.0–1.0
        "scores"     : dict  – {key: score} for all candidates
    }
    """
    configs = _load_all_configs()

    # Build flat text from columns + first 20 rows
    col_text   = " ".join(str(c) for c in df.columns).lower()
    cell_text  = ""
    for _, row in df.head(20).iterrows():
        for val in row.values:
            s = str(val).strip()
            if s and s.lower() not in {"nan", "none", ""}:
                cell_text += " " + s.lower()

    haystack = col_text + " " + cell_text + " " + extra_text.lower()

    scores: Dict[str, float] = {}

    # ── Score config-defined banks ─────────────────────────────────────────
    for key, cfg in configs.items():
        score = 0.0
        bank_name = cfg.get("bank_name", "").lower()
        col_mapping: dict = cfg.get("column_mapping", {})

        # Bank name present in doc?
        if bank_name and bank_name in haystack:
            score += 2.5

        # How many logical field aliases appear in column headers?
        total_fields = len(col_mapping)
        matched = 0
        for field, aliases in col_mapping.items():
            for alias in aliases:
                if alias.lower() in col_text:
                    matched += 1
                    score += 0.4
                    break

        if total_fields > 0:
            score += (matched / total_fields) * 2.0

        scores[key] = score

    # ── Score extra known banks ────────────────────────────────────────────
    for bank_key, sig in _EXTRA_SIGNATURES.items():
        if bank_key.lower() in scores:
            continue
        score = 0.0
        for kw in sig["keywords"]:
            if kw in haystack:
                score += 1.5
        for clue in sig.get("column_clues", []):
            if clue.lower() in col_text:
                score += 0.5
        if score > 0:
            scores[bank_key.lower()] = score

    if not scores:
        return {"bank": "UNKNOWN", "config_key": "", "confidence": 0.0, "scores": {}}

    best_key   = max(scores, key=lambda k: scores[k])
    best_score = scores[best_key]

    # Normalise confidence (rough ceiling = 7.0)
    confidence = min(best_score / 7.0, 1.0) if best_score > 0 else 0.0

    if best_score < 1.0:
        bank_name  = "UNKNOWN"
        config_key = ""
    else:
        # Use bank_name from config if available
        if best_key in configs:
            bank_name = configs[best_key].get("bank_name", best_key.upper())
        else:
            bank_name = best_key.upper()
        config_key = best_key if best_key in configs else ""

    logger.info(f"Bank detected: {bank_name} (conf={confidence:.2f})")

    return {
        "bank":        bank_name,
        "config_key":  config_key,
        "confidence":  round(confidence, 3),
        "scores":      {k: round(v, 3) for k, v in scores.items()},
    }
