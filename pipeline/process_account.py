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
    """Enrich every row with NLP extraction results.

    Counterparty name resolution priority (highest → lowest):
      1. Column name from bank statement (already in counterparty_name)
      2. NLP-extracted name from description text
      3. Counterparty account number (digits as display label)
      4. Channel label  ← for ATM/CDM cash transactions (no named counterparty)
    """
    # Cash channels: no named counterparty — use channel as label
    _CASH_CHANNELS = {"atm", "cdm", "cash"}

    def _clean(val) -> str:
        """Convert any value (including pandas NaN) to a clean string."""
        if val is None:
            return ""
        s = str(val).strip()
        return "" if s.lower() in ("nan", "none", "nat") else s

    rows = []
    for _, row in df.iterrows():
        r = enrich_transaction_row(row.to_dict())

        nlp_name  = _clean(r.get("nlp_best_name"))
        cp_name   = _clean(r.get("counterparty_name"))
        cp_acc    = _clean(r.get("counterparty_account"))
        partial   = _clean(r.get("partial_account"))
        channel   = _clean(r.get("channel"))
        direction = _clean(r.get("direction"))

        # ① Upgrade with NLP name if current name is blank / is just an account number
        if nlp_name and (not cp_name or cp_name == cp_acc or cp_name == partial):
            r["counterparty_name"] = nlp_name
            cp_name = nlp_name

        # ② Account number as label
        if not cp_name:
            cp_name = cp_acc or partial
            r["counterparty_name"] = cp_name

        # ③ Cash-machine channel as label (ATM withdrawal / CDM deposit)
        if not cp_name and channel.lower() in _CASH_CHANNELS:
            # Label: "ถอนเงิน ATM" or "ฝากเงิน CDM" for clarity
            if direction == "OUT":
                r["counterparty_name"] = f"ถอนเงิน {channel.upper()}"
            elif direction == "IN":
                r["counterparty_name"] = f"ฝากเงิน {channel.upper()}"
            else:
                r["counterparty_name"] = channel.upper()

        # ④ Any non-empty channel as last resort
        if not r.get("counterparty_name") and channel:
            r["counterparty_name"] = channel

        # ⑤ System/placeholder account → give human label
        cp_acc_final = _clean(r.get("counterparty_account"))
        if cp_acc_final and len(set(cp_acc_final)) == 1 and cp_acc_final.isdigit():
            # All-same-digit account (e.g. 9999999999) = bank system account
            if not r.get("counterparty_name") or r.get("counterparty_name") == cp_acc_final:
                r["counterparty_name"] = "หักบัญชีอัตโนมัติ"

        # ⑥ Description = bare time → use channel as description for readability
        import re as _re
        desc = _clean(r.get("description"))
        if _re.fullmatch(r'\d{1,2}:\d{2}(:\d{2})?', desc) or not desc:
            ch_label = _clean(r.get("channel"))
            if ch_label:
                r["description"] = ch_label

        rows.append(r)

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

    # Fall back to generic (standard format) config if detection fails
    if not _bank_cfg_key:
        _bank_cfg_key = "generic"
        logger.warning("  Bank detection failed — falling back to generic standard config")

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
    _format_type = bank_config.get("format_type", "standard")

    if _format_type in ("dual_account", "ktb_transfer"):
        # For format-specific types, PRESERVE all bank-config column mappings
        # (sender_account, receiver_account, sender_name, receiver_name, etc.)
        # and only override the generic common fields that the user confirmed.
        _common_fields = {"date", "time", "channel", "description"}
        _base_mapping = {
            field: list(aliases)
            for field, aliases in bank_config.get("column_mapping", {}).items()
        }
        for field, col in validated_mapping.items():
            if field in _common_fields and col:
                _base_mapping[field] = [col]
        _effective_config["column_mapping"] = _base_mapping
    else:
        # Standard format: use confirmed mapping directly
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

    # ── Step 10.5: AI Agent Override (if enabled) ─────────────────────────
    import os
    from core.llm_agent import run_llm_pipeline

    class_df = _assign_transaction_ids(class_df)

    if os.getenv("LLM_API_KEY"):
        logger.info("[Step 10.5] AI Agent Batch Enrichment")
        llm_results = run_llm_pipeline(class_df)
        if llm_results:
            logger.info(f"  -> Merging {len(llm_results)} AI Agent predictions into DataFrame")
            def merge_llm(row):
                txn_id = row.get("transaction_id")
                if txn_id in llm_results:
                    llm = llm_results[txn_id]
                    if llm.get("counterparty_name"):
                        row["counterparty_name"] = llm["counterparty_name"]
                    if llm.get("transaction_type"):
                        row["transaction_type"] = llm["transaction_type"]
                    if "confidence" in llm:
                        row["confidence"] = float(llm["confidence"])
                    row["nlp_promptpay"] = llm.get("nlp_promptpay", False)
                    row["nlp_accounts"] = llm.get("nlp_accounts", "")
                return row
            class_df = class_df.apply(merge_llm, axis=1)
        else:
            logger.warning("  -> AI Agent returned empty results, falling back to heuristic classification.")
    else:
        logger.info("  -> No LLM_API_KEY. Using heuristic rule-based classification only.")

    # ── Step 11: Build links ──────────────────────────────────────────────
    logger.info("[Step 11] Building links")
    linked_df = build_links(class_df)

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
        subject_name=subject_name,
    )

    logger.info(f"Pipeline COMPLETE -> {output_dir}")
    logger.info("=" * 60)
    return output_dir
