"""
process_account.py
------------------
14-Step BSIE pipeline orchestrator.

Steps:
  1.  Load Excel
  2.  Detect bank (auto or use provided key)
  3.  Detect columns (auto or use confirmed mapping)
  4.  Suggest mapping (merged auto + memory)
  5.  Apply confirmed mapping
  6.  Normalize data
  7.  Parse account fields
  8.  Extract accounts from descriptions
  9.  NLP processing (counterparty + classification hint)
  10. Classify transactions (hybrid)
  11. Build links (from/to)
  12. Apply manual overrides
  13. Build entity list
  14. Export Account Package (CSV + Excel + meta.json)
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd

from core.loader       import load_excel, load_config
from core.bank_detector import detect_bank
from core.column_detector import detect_columns, apply_mapping
from core.mapping_memory  import find_matching_profile, save_profile
from core.normalizer   import normalize
from core.nlp_engine   import enrich_transaction_row
from core.classifier   import classify_dataframe
from core.link_builder import build_links, extract_links
from core.override_manager import apply_overrides_to_df
from core.entity       import build_entities
from core.exporter     import export_package

logger = logging.getLogger(__name__)

# ── Canonical column order ─────────────────────────────────────────────────
TRANSACTION_COLUMNS: List[str] = [
    "transaction_id",
    "date", "time",
    "amount", "currency",
    "subject_account", "subject_name", "bank",
    "counterparty_account", "counterparty_name", "partial_account",
    "description", "channel",
    "direction", "transaction_type", "confidence",
    "from_account", "to_account",
    "raw_account_value", "parsed_account_type",
    "is_overridden",
    "override_from_account", "override_to_account",
    "override_reason", "override_by", "override_timestamp",
    "balance",
    "nlp_type_hint", "nlp_confidence", "nlp_best_name",
]


def _assign_transaction_ids(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["transaction_id"] = [f"TXN-{i+1:06d}" for i in range(len(df))]
    return df


def _enforce_schema(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in TRANSACTION_COLUMNS:
        if col not in df.columns:
            df[col] = False if col == "is_overridden" else ""
    extra   = [c for c in df.columns if c not in TRANSACTION_COLUMNS and not c.startswith("_")]
    ordered = TRANSACTION_COLUMNS + extra
    return df[[c for c in ordered if c in df.columns]]


def _run_nlp(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich every row with NLP extraction results."""
    rows = []
    for _, row in df.iterrows():
        rows.append(enrich_transaction_row(row.to_dict()))
    enriched = pd.DataFrame(rows)
    # Restore original index
    enriched.index = df.index
    return enriched


# ── Main pipeline ──────────────────────────────────────────────────────────

def process_account(
    input_file: Union[str, Path],
    subject_account: str,
    subject_name: str = "",
    bank_key: str = "",
    confirmed_mapping: Optional[Dict[str, Optional[str]]] = None,
    save_mapping_profile: bool = True,
) -> Path:
    """
    Run the full 14-step BSIE pipeline for one bank account statement.

    Parameters
    ----------
    input_file            : path to .xlsx bank statement
    subject_account       : account number under investigation
    subject_name          : optional account holder name
    bank_key              : bank config key (e.g. "scb"); auto-detected if ""
    confirmed_mapping     : dict {logical_field: actual_column} confirmed by user;
                            auto-detected if None
    save_mapping_profile  : whether to persist the mapping as a reusable profile

    Returns
    -------
    Path - path to the generated Account Package directory
    """
    input_file = Path(input_file)
    logger.info("=" * 60)
    logger.info("BSIE 14-Step Pipeline START")
    logger.info(f"  File    : {input_file.name}")
    logger.info(f"  Account : {subject_account}")
    logger.info("=" * 60)

    # ── Step 1: Load Excel ────────────────────────────────────────────────
    logger.info("[Step 1] Loading Excel")
    # We need a bank config for the loader; try auto-detect if not given
    _bank_cfg_key = bank_key

    # Load raw without config first to allow detection
    from core.loader import load_config
    import pandas as _pd
    _xf = _pd.ExcelFile(str(input_file), engine="openpyxl")
    _raw_preview = _pd.read_excel(
        str(input_file),
        sheet_name=_xf.sheet_names[0],
        header=None, nrows=30, dtype=str,
    ).fillna("")

    # ── Step 2: Detect bank ───────────────────────────────────────────────
    logger.info("[Step 2] Detecting bank")
    if not _bank_cfg_key:
        detection = detect_bank(_raw_preview, extra_text=input_file.stem)
        _bank_cfg_key = detection.get("config_key", "")
        logger.info(f"  Detected: {detection['bank']} (conf={detection['confidence']})")
    else:
        logger.info(f"  Using provided bank_key: {_bank_cfg_key}")

    # Fall back to SCB config if detection fails
    if not _bank_cfg_key:
        _bank_cfg_key = "scb"
        logger.warning("  Bank detection failed — falling back to SCB config")

    bank_config = load_config(_bank_cfg_key)
    raw_df = load_excel(input_file, bank_config)

    # ── Step 3: Detect columns ────────────────────────────────────────────
    logger.info("[Step 3] Detecting columns")
    col_detection = detect_columns(raw_df)

    # ── Step 4: Suggest mapping from auto-detect + memory ─────────────────
    logger.info("[Step 4] Loading mapping memory")
    profile = find_matching_profile(list(raw_df.columns))

    if confirmed_mapping is None:
        if profile:
            logger.info(f"  Using profile: {profile['profile_id']}")
            confirmed_mapping = profile["mapping"]
        else:
            confirmed_mapping = col_detection["suggested_mapping"]
            logger.info("  Using auto-detected mapping (no profile found)")

    # ── Step 5: Apply confirmed mapping ──────────────────────────────────
    logger.info("[Step 5] Applying column mapping")
    validated_mapping = apply_mapping(raw_df, confirmed_mapping)

    # Build a synthetic bank_config that uses the confirmed mapping
    _effective_config = dict(bank_config)
    # Convert {field: column} -> {field: [column]} for normalizer
    _effective_config["column_mapping"] = {
        field: [col] if col else []
        for field, col in validated_mapping.items()
        if col
    }

    # ── Step 6: Normalize data ────────────────────────────────────────────
    logger.info("[Step 6] Normalizing data")
    norm_df = normalize(raw_df, _effective_config, subject_account, subject_name)

    # ── Steps 7+8 are inside normalize (account parsing + description extraction)
    logger.info("[Step 7-8] Account parsing + description extraction (done in normalize)")

    # ── Step 9: NLP processing ────────────────────────────────────────────
    logger.info("[Step 9] NLP enrichment")
    norm_df = _run_nlp(norm_df)

    # ── Step 10: Classify transactions ────────────────────────────────────
    logger.info("[Step 10] Classifying transactions")
    class_df = classify_dataframe(norm_df)

    # ── Step 11: Build links ──────────────────────────────────────────────
    logger.info("[Step 11] Building links")
    linked_df = build_links(class_df)

    # Assign IDs before override application
    linked_df = _assign_transaction_ids(linked_df)

    # ── Step 12: Apply overrides ──────────────────────────────────────────
    logger.info("[Step 12] Applying manual overrides")
    final_df = apply_overrides_to_df(linked_df)

    # ── Step 13: Build entities ───────────────────────────────────────────
    logger.info("[Step 13] Building entity list")
    final_df   = _enforce_schema(final_df)
    entities_df = build_entities(final_df)
    links_df    = extract_links(final_df)

    # ── Step 14: Export package ───────────────────────────────────────────
    logger.info("[Step 14] Exporting Account Package")

    # Save confirmed mapping as a profile for future reuse
    if save_mapping_profile and confirmed_mapping:
        bank_name = bank_config.get("bank_name", _bank_cfg_key.upper())
        save_profile(bank_name, list(raw_df.columns), confirmed_mapping)

    output_dir = export_package(
        transactions=final_df,
        entities=entities_df,
        links=links_df,
        account_number=subject_account,
        bank=bank_config.get("bank_name", _bank_cfg_key.upper()),
        original_file=input_file,
    )

    logger.info(f"Pipeline COMPLETE -> {output_dir}")
    logger.info("=" * 60)
    return output_dir
