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

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd

from core.loader       import load_excel, load_config, find_best_sheet_and_header
from core.bank_detector import detect_bank
from core.column_detector import detect_columns, apply_mapping
from core.mapping_memory  import find_matching_profile, save_profile
from core.bank_memory     import save_bank_fingerprint
from core.normalizer   import normalize
from core.nlp_engine   import enrich_transaction_row
from core.classifier   import classify_dataframe
from core.link_builder import build_links, extract_links
from core.override_manager import apply_overrides_to_df
from core.entity       import build_entities
from core.reconciliation import reconcile_balances
from core.exporter     import export_package
from core.ofx_io       import parse_ofx_file
from persistence.base import get_db_session
from services.account_resolution_service import best_known_account_holder_name
from services.classification_service import apply_ai_classification_enrichment
from services.persistence_pipeline_service import persist_pipeline_run

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
    "classification_source", "classification_reason", "classification_review_flag", "classification_model",
    "heuristic_transaction_type", "heuristic_confidence", "ai_transaction_type", "ai_confidence", "ai_counterparty_name",
    "from_account", "to_account",
    "raw_account_value", "parsed_account_type",
    "is_overridden",
    "override_from_account", "override_to_account",
    "override_reason", "override_by", "override_timestamp",
    "balance",
    "balance_source", "expected_balance", "balance_difference", "balance_check_status",
    "nlp_type_hint", "nlp_confidence", "nlp_best_name",
]


def _effective_subject_name(subject_account: str, subject_name: str, bank_name: str) -> str:
    explicit_name = str(subject_name or "").strip()
    if explicit_name:
        return explicit_name
    try:
        with get_db_session() as session:
            return best_known_account_holder_name(
                session,
                bank_name=bank_name,
                raw_account_number=subject_account,
            ) or ""
    except Exception as exc:
        logger.warning("Could not resolve subject name from account memory (non-fatal): %s", exc)
        return ""


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
    save_mapping_profile: bool = False,
    file_id: str = "",
    parser_run_id: str = "",
    operator: str = "analyst",
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
                            (explicit only; default off)

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

    if input_file.suffix.lower() == ".ofx" or bank_key.lower() == "ofx":
        logger.info("[Step 1] Loading OFX")
        effective_subject_name = _effective_subject_name(subject_account, subject_name, "OFX")
        norm_df = parse_ofx_file(input_file)
        if norm_df.empty:
            raise ValueError(f"No transactions found in OFX file: {input_file.name}")
        raw_df = norm_df.copy()
        raw_df["_source_sheet_name"] = "OFX"
        raw_df["_source_row_number"] = [idx + 1 for idx in range(len(raw_df))]
        raw_df["_raw_row_json"] = raw_df.apply(lambda row: json.dumps({k: str(v) for k, v in row.to_dict().items()}, ensure_ascii=False), axis=1)
        raw_df["_parser_run_id"] = parser_run_id or ""
        norm_df["subject_account"] = subject_account
        norm_df["subject_name"] = effective_subject_name
        norm_df["bank"] = "OFX"
        logger.info("[Step 2-8] OFX input already normalized to standard schema")
        logger.info("[Step 9] NLP enrichment")
        norm_df = _run_nlp(norm_df)
        logger.info("[Step 10] Classifying transactions")
        class_df = classify_dataframe(norm_df)
        class_df = _assign_transaction_ids(class_df)
        logger.info("[Step 10.5] Applying optional AI classification guardrails")
        class_df = apply_ai_classification_enrichment(class_df)
        logger.info("[Step 11] Building links")
        linked_df = build_links(class_df)
        logger.info("[Step 12] Applying manual overrides")
        final_df = apply_overrides_to_df(linked_df)
        logger.info("[Step 13] Building entity list")
        final_df = _enforce_schema(final_df)
        reconciliation = reconcile_balances(final_df)
        final_df = reconciliation.transactions
        entities_df = build_entities(final_df)
        links_df = extract_links(final_df)
        logger.info("[Step 14] Exporting Account Package")
        output_dir = export_package(
            transactions=final_df,
            entities=entities_df,
            links=links_df,
            account_number=subject_account,
            bank="OFX",
            original_file=input_file,
            subject_name=effective_subject_name,
            reconciliation_df=reconciliation.reconciliation,
            reconciliation_summary=reconciliation.summary,
        )
        if file_id and parser_run_id:
            persist_pipeline_run(
                file_id=file_id,
                parser_run_id=parser_run_id,
                source_file=input_file,
                raw_df=raw_df,
                transactions_df=final_df,
                entities_df=entities_df,
                bank_key="ofx",
                bank_name="OFX",
                subject_account=subject_account,
                subject_name=effective_subject_name,
                confirmed_mapping=confirmed_mapping or {},
                header_row=0,
                sheet_name="OFX",
                output_dir=output_dir,
                operator=operator,
            )
        logger.info(f"Pipeline COMPLETE -> {output_dir}")
        logger.info("=" * 60)
        return output_dir

    # ── Step 1: Load Excel ────────────────────────────────────────────────
    logger.info("[Step 1] Loading Excel")
    # We need a bank config for the loader; try auto-detect if not given
    _bank_cfg_key = bank_key

    # Load raw without config first to allow detection
    sheet_pick = find_best_sheet_and_header(input_file, preview_rows=30, scan_rows=12)
    _sheet_name = sheet_pick["sheet_name"]
    _header_row = int(sheet_pick["header_row"])
    _raw_preview = pd.read_excel(
        input_file,
        sheet_name=_sheet_name,
        header=_header_row,
        engine="openpyxl",
        dtype=str,
    ).dropna(how="all")
    _raw_preview.columns = [str(c).strip() for c in _raw_preview.columns]

    # ── Step 2: Detect bank ───────────────────────────────────────────────
    logger.info("[Step 2] Detecting bank")
    if not _bank_cfg_key:
        detection = detect_bank(_raw_preview, extra_text=f"{input_file.stem} {_sheet_name}", sheet_name=_sheet_name)
        _bank_cfg_key = detection.get("config_key", "")
        logger.info(f"  Detected: {detection['bank']} (conf={detection['confidence']})")
    else:
        logger.info(f"  Using provided bank_key: {_bank_cfg_key}")

    # Fall back to generic (standard format) config if detection fails
    if not _bank_cfg_key:
        _bank_cfg_key = "generic"
        logger.warning("  Bank detection failed — falling back to generic standard config")

    bank_config = load_config(_bank_cfg_key)
    bank_config = {**bank_config}
    if "sheet_index" not in bank_config or bank_config.get("sheet_index") is None:
        bank_config["sheet_index"] = 0
    bank_config["header_row"] = _header_row
    try:
        preview_book = pd.ExcelFile(input_file, engine="openpyxl")
        if _sheet_name in preview_book.sheet_names:
            bank_config["sheet_index"] = preview_book.sheet_names.index(_sheet_name)
    except Exception:
        pass
    raw_df = load_excel(input_file, bank_config)
    raw_df = raw_df.copy()
    raw_df["_source_sheet_name"] = _sheet_name
    raw_df["_source_row_number"] = [int(_header_row) + idx + 2 for idx in range(len(raw_df))]
    raw_df["_raw_row_json"] = raw_df.apply(
        lambda row: json.dumps({str(k): ("" if pd.isna(v) else str(v)) for k, v in row.to_dict().items() if not str(k).startswith("_")},
                               ensure_ascii=False),
        axis=1,
    )
    raw_df["_parser_run_id"] = parser_run_id or ""

    # ── Step 3: Detect columns ────────────────────────────────────────────
    logger.info("[Step 3] Detecting columns")
    col_detection = detect_columns(raw_df)

    # ── Step 4: Suggest mapping from auto-detect + memory ─────────────────
    logger.info("[Step 4] Loading mapping memory")
    profile = find_matching_profile(
        [column for column in raw_df.columns if not str(column).startswith("_")],
        bank=_bank_cfg_key,
    )

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
    _has_extended_mapping = any(
        field in bank_config.get("column_mapping", {})
        for field in ("sender_account", "receiver_account", "sender_name", "receiver_name", "direction_marker")
    )

    if _format_type in ("dual_account", "ktb_transfer", "direction_marker") or _has_extended_mapping:
        # For format-specific types, PRESERVE all bank-config column mappings
        # (sender_account, receiver_account, sender_name, receiver_name, etc.)
        # and only override the generic common fields that the user confirmed.
        _common_fields = {"date", "time", "channel", "description", "amount", "debit", "credit", "balance"}
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
    effective_subject_name = _effective_subject_name(
        subject_account,
        subject_name,
        bank_config.get("bank_name", _bank_cfg_key.upper()),
    )
    norm_df = normalize(raw_df, _effective_config, subject_account, effective_subject_name, source_file=input_file.name)

    # ── Steps 7+8 are inside normalize (account parsing + description extraction)
    logger.info("[Step 7-8] Account parsing + description extraction (done in normalize)")

    # ── Step 9: NLP processing ────────────────────────────────────────────
    logger.info("[Step 9] NLP enrichment")
    norm_df = _run_nlp(norm_df)

    # ── Step 10: Classify transactions ────────────────────────────────────
    logger.info("[Step 10] Classifying transactions")
    class_df = classify_dataframe(norm_df)

    class_df = _assign_transaction_ids(class_df)
    logger.info("[Step 10.5] Applying optional AI classification guardrails")
    class_df = apply_ai_classification_enrichment(class_df)

    # ── Step 11: Build links ──────────────────────────────────────────────
    logger.info("[Step 11] Building links")
    linked_df = build_links(class_df)

    # ── Step 12: Apply overrides ──────────────────────────────────────────
    logger.info("[Step 12] Applying manual overrides")
    final_df = apply_overrides_to_df(linked_df, account_number=subject_account)

    # ── Step 13: Build entities ───────────────────────────────────────────
    logger.info("[Step 13] Building entity list")
    final_df   = _enforce_schema(final_df)
    reconciliation = reconcile_balances(final_df)
    final_df = reconciliation.transactions
    entities_df = build_entities(final_df)
    links_df    = extract_links(final_df)

    # ── Step 14: Export package ───────────────────────────────────────────
    logger.info("[Step 14] Exporting Account Package")

    # Save confirmed mapping as a profile for future reuse
    if save_mapping_profile and confirmed_mapping:
        bank_name = bank_config.get("bank_name", _bank_cfg_key.upper())
        learned_columns = [col for col in raw_df.columns if not str(col).startswith("_")]
        save_profile(bank_name, learned_columns, confirmed_mapping)
        if _bank_cfg_key and _bank_cfg_key.lower() not in {"", "generic"}:
            try:
                save_bank_fingerprint(_bank_cfg_key, learned_columns)
            except Exception as exc:
                logger.warning("Could not save bank fingerprint (non-fatal): %s", exc)

    output_dir = export_package(
        transactions=final_df,
        entities=entities_df,
        links=links_df,
        account_number=subject_account,
        bank=bank_config.get("bank_name", _bank_cfg_key.upper()),
        original_file=input_file,
        subject_name=effective_subject_name,
        reconciliation_df=reconciliation.reconciliation,
        reconciliation_summary=reconciliation.summary,
    )

    if file_id and parser_run_id:
        persist_pipeline_run(
            file_id=file_id,
            parser_run_id=parser_run_id,
            source_file=input_file,
            raw_df=raw_df,
            transactions_df=final_df,
            entities_df=entities_df,
            bank_key=_bank_cfg_key,
            bank_name=bank_config.get("bank_name", _bank_cfg_key.upper()),
            subject_account=subject_account,
            subject_name=effective_subject_name,
            confirmed_mapping=confirmed_mapping or {},
            header_row=_header_row,
            sheet_name=_sheet_name,
            output_dir=output_dir,
            operator=operator,
        )

    logger.info(f"Pipeline COMPLETE -> {output_dir}")
    logger.info("=" * 60)
    return output_dir
