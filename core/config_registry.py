"""
config_registry.py
------------------
Repo-local validation for built-in bank configs and golden sample files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.bank_detector import detect_bank
from core.loader import find_best_sheet_and_header, load_excel, load_config
from core.normalizer import normalize
from paths import BUILTIN_CONFIG_DIR


REGISTRY_PATH = Path(__file__).resolve().parent.parent / "config_registry" / "registry.json"


def load_registry(registry_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(registry_path) if registry_path else REGISTRY_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def validate_registry(registry_path: str | Path | None = None) -> dict[str, Any]:
    registry = load_registry(registry_path)
    project_root = Path(registry_path).resolve().parent.parent if registry_path else REGISTRY_PATH.parent.parent
    entries = registry.get("entries", [])
    results: list[dict[str, Any]] = []

    for entry in entries:
        sample_path = (project_root / entry["sample_path"]).resolve()
        config_key = str(entry["config_key"])
        config_path = BUILTIN_CONFIG_DIR / f"{config_key}.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Missing built-in config: {config_path}")
        config = load_config(config_key)
        detection = config.get("detection") or {}
        if not detection.get("keywords") or not detection.get("strong_headers"):
            raise ValueError(f"Config {config_key} is missing required detection metadata")
        if not sample_path.exists():
            raise FileNotFoundError(f"Missing sample file: {sample_path}")

        pick = find_best_sheet_and_header(sample_path)
        import pandas as pd

        df = pd.read_excel(sample_path, sheet_name=pick["sheet_name"], header=pick["header_row"], dtype=str).dropna(how="all")
        df.columns = [str(col).strip() for col in df.columns]
        detection_result = detect_bank(df, extra_text=f"{sample_path.stem} {pick['sheet_name']}")
        if detection_result["config_key"] != entry["expected_bank"]:
            raise AssertionError(
                f"{entry['sample_path']} detected as {detection_result['config_key']} instead of {entry['expected_bank']}"
            )

        result = {
            "sample_path": entry["sample_path"],
            "config_key": config_key,
            "expected_bank": entry["expected_bank"],
            "detected_bank": detection_result["config_key"],
            "normalized": False,
        }

        normalize_assert = entry.get("normalize_assert")
        if normalize_assert:
            raw_df = load_excel(sample_path, config)
            norm_df = normalize(
                raw_df,
                config,
                subject_account=str(normalize_assert.get("subject_account", "")),
                subject_name=str(normalize_assert.get("subject_name", "")),
            )
            if norm_df.empty:
                raise AssertionError(f"{entry['sample_path']} normalized to an empty dataframe")
            required_columns = normalize_assert.get("required_columns", [])
            missing = [column for column in required_columns if column not in norm_df.columns]
            if missing:
                raise AssertionError(f"{entry['sample_path']} missing normalized columns: {missing}")
            result["normalized"] = True
            result["normalized_rows"] = int(len(norm_df))

        results.append(result)

    return {
        "registry_version": registry.get("registry_version", 1),
        "entry_count": len(results),
        "results": results,
    }
