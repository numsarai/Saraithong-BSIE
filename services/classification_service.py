from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass

import pandas as pd

from core.llm_agent import run_llm_pipeline

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool = False) -> bool:
    value = str(os.getenv(name, "")).strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, default) or default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default) or default)
    except (TypeError, ValueError):
        return default


@dataclass
class ClassificationSettings:
    llm_enabled: bool
    llm_api_key_present: bool
    llm_model_name: str
    llm_max_transactions: int
    llm_min_confidence: float
    allow_counterparty_name_override: bool
    allow_transaction_type_override: bool
    review_on_ai_divergence: bool


def get_classification_settings() -> ClassificationSettings:
    return ClassificationSettings(
        llm_enabled=_env_flag("BSIE_ENABLE_LLM_CLASSIFICATION", False),
        llm_api_key_present=bool(str(os.getenv("LLM_API_KEY", "")).strip()),
        llm_model_name=str(os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")).strip() or "gpt-4o-mini",
        llm_max_transactions=_env_int("BSIE_LLM_MAX_TRANSACTIONS", 250),
        llm_min_confidence=max(0.0, min(1.0, _env_float("BSIE_LLM_MIN_CONFIDENCE", 0.85))),
        allow_counterparty_name_override=_env_flag("BSIE_LLM_ALLOW_NAME_OVERRIDE", True),
        allow_transaction_type_override=_env_flag("BSIE_LLM_ALLOW_TYPE_OVERRIDE", True),
        review_on_ai_divergence=_env_flag("BSIE_LLM_REVIEW_ON_DIVERGENCE", True),
    )


def apply_ai_classification_enrichment(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    settings = get_classification_settings()

    if "classification_source" not in enriched.columns:
        enriched["classification_source"] = "heuristic"
    if "classification_reason" not in enriched.columns:
        enriched["classification_reason"] = "rule_nlp_hybrid"
    if "classification_review_flag" not in enriched.columns:
        enriched["classification_review_flag"] = False
    if "classification_model" not in enriched.columns:
        enriched["classification_model"] = ""
    if "heuristic_transaction_type" not in enriched.columns:
        enriched["heuristic_transaction_type"] = enriched.get("transaction_type", "").astype(str)
    if "heuristic_confidence" not in enriched.columns:
        enriched["heuristic_confidence"] = pd.to_numeric(enriched.get("confidence", 0.0), errors="coerce").fillna(0.0)
    if "ai_transaction_type" not in enriched.columns:
        enriched["ai_transaction_type"] = ""
    if "ai_confidence" not in enriched.columns:
        enriched["ai_confidence"] = ""
    if "ai_counterparty_name" not in enriched.columns:
        enriched["ai_counterparty_name"] = ""

    if not settings.llm_enabled:
        logger.info("  -> AI classification disabled by BSIE_ENABLE_LLM_CLASSIFICATION")
        enriched["classification_model"] = "heuristic-only"
        return enriched

    if not settings.llm_api_key_present:
        logger.info("  -> No LLM_API_KEY. Keeping heuristic classification.")
        enriched["classification_reason"] = "rule_nlp_hybrid|llm_unavailable"
        enriched["classification_model"] = "heuristic-only"
        return enriched

    if len(enriched.index) > settings.llm_max_transactions:
        logger.warning(
            "  -> Skipping AI classification because %s rows exceed BSIE_LLM_MAX_TRANSACTIONS=%s",
            len(enriched.index),
            settings.llm_max_transactions,
        )
        enriched["classification_reason"] = "rule_nlp_hybrid|llm_skipped_batch_limit"
        enriched["classification_model"] = "heuristic-only"
        return enriched

    llm_results = run_llm_pipeline(enriched)
    if not llm_results:
        logger.warning("  -> AI classification returned empty results; keeping heuristic values.")
        enriched["classification_reason"] = "rule_nlp_hybrid|llm_empty"
        enriched["classification_model"] = "heuristic-only"
        return enriched

    logger.info("  -> Merging %s AI classification results", len(llm_results))

    def merge_llm(row: pd.Series) -> pd.Series:
        txn_id = str(row.get("transaction_id", "") or "")
        llm = llm_results.get(txn_id)
        if not llm:
            return row

        ai_confidence = float(llm.get("confidence", 0.0) or 0.0)
        row["ai_transaction_type"] = str(llm.get("transaction_type", "") or "")
        row["ai_confidence"] = ai_confidence
        row["ai_counterparty_name"] = str(llm.get("counterparty_name", "") or "")
        row["classification_model"] = settings.llm_model_name

        if ai_confidence < settings.llm_min_confidence:
            row["classification_reason"] = "rule_nlp_hybrid|llm_below_threshold"
            return row

        heuristic_type = str(row.get("heuristic_transaction_type", row.get("transaction_type", "")) or "")
        ai_type = str(llm.get("transaction_type", "") or "")
        ai_name = str(llm.get("counterparty_name", "") or "")

        applied_parts: list[str] = []
        if settings.allow_counterparty_name_override and ai_name:
            row["counterparty_name"] = ai_name
            applied_parts.append("name")

        if settings.allow_transaction_type_override and ai_type:
            if ai_type != heuristic_type and settings.review_on_ai_divergence:
                row["classification_review_flag"] = True
            row["transaction_type"] = ai_type
            row["confidence"] = ai_confidence
            applied_parts.append("type")

        if llm.get("nlp_promptpay") is not None:
            row["nlp_promptpay"] = llm.get("nlp_promptpay", False)
        if llm.get("nlp_accounts") is not None:
            row["nlp_accounts"] = llm.get("nlp_accounts", "")

        if applied_parts:
            row["classification_source"] = "heuristic+ai"
            row["classification_reason"] = f"rule_nlp_hybrid|llm_override_{'+'.join(applied_parts)}"
        else:
            row["classification_reason"] = "rule_nlp_hybrid|llm_confirmed"
        return row

    enriched = enriched.apply(merge_llm, axis=1)
    logger.info("  -> Classification settings: %s", asdict(settings))
    return enriched
