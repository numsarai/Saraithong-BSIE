from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, replace
from typing import Any

import httpx
import pandas as pd

from core.llm_agent import run_llm_pipeline
from services.llm_service import REQUEST_TIMEOUT, resolve_model
from services.search_service import search_transactions

logger = logging.getLogger(__name__)

SUPPORTED_TRANSACTION_TYPES = {
    "IN_TRANSFER",
    "OUT_TRANSFER",
    "DEPOSIT",
    "WITHDRAW",
    "FEE",
    "SALARY",
    "IN_UNKNOWN",
    "OUT_UNKNOWN",
}
LOCAL_CLASSIFICATION_BATCH_SIZE = 25
LOCAL_CLASSIFICATION_MAX_TOKENS = 2048
CLASSIFICATION_PREVIEW_MAX_TRANSACTIONS = 25


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
    llm_provider: str
    llm_api_key_present: bool
    llm_model_name: str
    llm_max_transactions: int
    llm_min_confidence: float
    allow_counterparty_name_override: bool
    allow_transaction_type_override: bool
    review_on_ai_divergence: bool


def _classification_provider() -> str:
    provider = (
        os.getenv("BSIE_CLASSIFICATION_LLM_PROVIDER")
        or os.getenv("BSIE_LLM_CLASSIFICATION_PROVIDER")
        or "local"
    )
    value = str(provider or "").strip().lower()
    if value in {"", "local", "ollama", "local_ollama", "local_llm"}:
        return "local"
    if value in {"legacy", "legacy_openai", "openai"}:
        return "legacy_openai"
    return value


def _classification_model_name(provider: str) -> str:
    if provider == "legacy_openai":
        return str(os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    configured = (
        os.getenv("OLLAMA_CLASSIFICATION_MODEL")
        or os.getenv("OLLAMA_TEXT_MODEL")
        or os.getenv("OLLAMA_DEFAULT_MODEL")
        or "qwen3.5:9b"
    )
    return str(configured or "").strip() or "qwen3.5:9b"


def get_classification_settings() -> ClassificationSettings:
    provider = _classification_provider()
    return ClassificationSettings(
        llm_enabled=_env_flag("BSIE_ENABLE_LLM_CLASSIFICATION", False),
        llm_provider=provider,
        llm_api_key_present=bool(str(os.getenv("LLM_API_KEY", "")).strip()),
        llm_model_name=_classification_model_name(provider),
        llm_max_transactions=_env_int("BSIE_LLM_MAX_TRANSACTIONS", 250),
        llm_min_confidence=max(0.0, min(1.0, _env_float("BSIE_LLM_MIN_CONFIDENCE", 0.85))),
        allow_counterparty_name_override=_env_flag("BSIE_LLM_ALLOW_NAME_OVERRIDE", True),
        allow_transaction_type_override=_env_flag("BSIE_LLM_ALLOW_TYPE_OVERRIDE", True),
        review_on_ai_divergence=_env_flag("BSIE_LLM_REVIEW_ON_DIVERGENCE", True),
    )


def _ollama_root_url() -> str:
    root = (os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip() or "http://localhost:11434").rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3].rstrip("/")
    return root or "http://localhost:11434"


def _ollama_api_url(path: str) -> str:
    return f"{_ollama_root_url()}/{path.lstrip('/')}"


def _safe_text(value: Any, *, limit: int = 240) -> str:
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value or "").strip()[:limit]


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _account_digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _extract_json_object(text: str) -> dict[str, Any]:
    content = str(text or "").strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        content = fence_match.group(1).strip()
    elif "{" in content and "}" in content:
        content = content[content.find("{"):content.rfind("}") + 1]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _classification_payload(df: pd.DataFrame) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for index, row in df.iterrows():
        txn_id = _safe_text(row.get("transaction_id", f"temp_{index}"), limit=120) or f"temp_{index}"
        date_text = _safe_text(row.get("date"), limit=40) or _safe_text(row.get("transaction_date"), limit=40)
        description = (
            _safe_text(row.get("description"), limit=320)
            or _safe_text(row.get("description_normalized"), limit=320)
            or _safe_text(row.get("description_raw"), limit=320)
        )
        payload.append(
            {
                "transaction_id": txn_id,
                "date": date_text,
                "direction": _safe_text(row.get("direction"), limit=12),
                "amount": _safe_float(row.get("amount")),
                "description": description,
                "channel": _safe_text(row.get("channel"), limit=80),
                "counterparty_account": _safe_text(row.get("counterparty_account"), limit=80),
                "counterparty_name": _safe_text(row.get("counterparty_name"), limit=160),
                "heuristic_transaction_type": _safe_text(
                    row.get("heuristic_transaction_type", row.get("transaction_type", "")),
                    limit=40,
                ),
                "heuristic_confidence": _safe_float(row.get("heuristic_confidence", row.get("confidence", 0.0))),
            }
        )
    return payload


def _build_local_classification_prompt(transactions: list[dict[str, Any]]) -> str:
    prompt_data = json.dumps(transactions, ensure_ascii=False, indent=2)
    allowed = ", ".join(sorted(SUPPORTED_TRANSACTION_TYPES))
    return (
        "You are BSIE's local-only transaction classification assistant.\n"
        "Analyze only the transaction rows provided below. Do not use external knowledge, do not invent accounts, names, dates, or amounts, "
        "and keep empty strings when evidence is missing.\n"
        f"Allowed transaction_type values: {allowed}.\n"
        "Return only a compact JSON object with this shape:\n"
        "{\"results\":[{\"transaction_id\":\"...\",\"transaction_type\":\"...\",\"counterparty_name\":\"\",\"confidence\":0.0,"
        "\"nlp_promptpay\":false,\"nlp_accounts\":\"\"}]}\n"
        "transaction_id must exactly match the input. confidence must be a number from 0.0 to 1.0. "
        "nlp_accounts must be a comma-separated string of account numbers found in the description only.\n\n"
        f"Transactions:\n{prompt_data}"
    )


def _clean_llm_results(raw: dict[str, Any], allowed_ids: set[str]) -> dict[str, dict[str, Any]]:
    items = raw.get("results")
    if items is None:
        items = raw.get("classifications")
    if not isinstance(items, list):
        return {}

    results: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        txn_id = _safe_text(item.get("transaction_id"), limit=120)
        if txn_id not in allowed_ids:
            continue
        tx_type = _safe_text(item.get("transaction_type"), limit=40).upper()
        if tx_type not in SUPPORTED_TRANSACTION_TYPES:
            continue
        confidence = max(0.0, min(1.0, _safe_float(item.get("confidence"))))
        results[txn_id] = {
            "transaction_type": tx_type,
            "counterparty_name": _safe_text(item.get("counterparty_name"), limit=160),
            "confidence": confidence,
            "nlp_promptpay": _safe_bool(item.get("nlp_promptpay")),
            "nlp_accounts": _safe_text(item.get("nlp_accounts"), limit=240),
        }
    return results


def _post_ollama_classification_chat(prompt: str, settings: ClassificationSettings) -> str:
    selected_model = resolve_model(settings.llm_model_name, "text")
    payload = {
        "model": selected_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a local BSIE assistant for Thai bank statement processing. "
                    "Return valid JSON only. Do not think step by step."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": "json",
        "think": False,
        "options": {
            "temperature": 0,
            "num_predict": LOCAL_CLASSIFICATION_MAX_TOKENS,
        },
    }
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        response = client.post(_ollama_api_url("/api/chat"), json=payload)
        response.raise_for_status()
        data = response.json()
    return str(data.get("message", {}).get("content", "") or "")


def _run_local_llm_pipeline(df: pd.DataFrame, settings: ClassificationSettings) -> dict[str, dict[str, Any]]:
    payload = _classification_payload(df)
    results: dict[str, dict[str, Any]] = {}
    for start in range(0, len(payload), LOCAL_CLASSIFICATION_BATCH_SIZE):
        batch = payload[start:start + LOCAL_CLASSIFICATION_BATCH_SIZE]
        allowed_ids = {str(item["transaction_id"]) for item in batch}
        prompt = _build_local_classification_prompt(batch)
        try:
            content = _post_ollama_classification_chat(prompt, settings)
        except httpx.ConnectError:
            logger.warning("  -> Local Ollama unavailable. Keeping heuristic classification.")
            return {}
        except httpx.TimeoutException:
            logger.warning("  -> Local Ollama classification timed out. Keeping heuristic classification.")
            return {}
        except httpx.RequestError as exc:
            logger.warning("  -> Local Ollama classification request failed: %s", exc)
            return {}
        except httpx.HTTPStatusError as exc:
            logger.warning("  -> Local Ollama classification failed: %s", exc)
            return {}
        except RuntimeError as exc:
            logger.warning("  -> Local Ollama classification failed: %s", exc)
            return {}

        cleaned = _clean_llm_results(_extract_json_object(content), allowed_ids)
        results.update(cleaned)
    return results


def _run_classification_provider(df: pd.DataFrame, settings: ClassificationSettings) -> dict[str, dict[str, Any]]:
    if settings.llm_provider == "local":
        return _run_local_llm_pipeline(df, settings)
    if settings.llm_provider == "legacy_openai":
        return run_llm_pipeline(df)
    logger.warning("  -> Unsupported classification LLM provider '%s'. Keeping heuristic classification.", settings.llm_provider)
    return {}


def _preview_settings(model: str = "") -> ClassificationSettings:
    base = get_classification_settings()
    selected_model = str(model or "").strip() or _classification_model_name("local")
    return replace(
        base,
        llm_enabled=True,
        llm_provider="local",
        llm_model_name=selected_model,
        llm_max_transactions=min(base.llm_max_transactions, CLASSIFICATION_PREVIEW_MAX_TRANSACTIONS),
    )


def _preview_record(row: dict[str, Any], index: int) -> dict[str, Any]:
    txn_id = (
        _safe_text(row.get("transaction_id"), limit=120)
        or _safe_text(row.get("id"), limit=120)
        or f"preview_{index + 1}"
    )
    current_type = (
        _safe_text(row.get("transaction_type"), limit=40)
        or _safe_text(row.get("heuristic_transaction_type"), limit=40)
    )
    confidence = row.get("confidence", row.get("heuristic_confidence", row.get("parse_confidence", 0.0)))
    description = (
        _safe_text(row.get("description"), limit=320)
        or _safe_text(row.get("description_normalized"), limit=320)
        or _safe_text(row.get("description_raw"), limit=320)
    )
    date_text = (
        _safe_text(row.get("date"), limit=40)
        or _safe_text(row.get("transaction_date"), limit=40)
        or _safe_text(row.get("posted_date"), limit=40)
        or _safe_text(row.get("transaction_datetime"), limit=40)
    )
    counterparty_account = (
        _safe_text(row.get("counterparty_account"), limit=80)
        or _safe_text(row.get("counterparty_account_normalized"), limit=80)
        or _safe_text(row.get("counterparty_account_raw"), limit=80)
    )
    counterparty_name = (
        _safe_text(row.get("counterparty_name"), limit=160)
        or _safe_text(row.get("counterparty_name_normalized"), limit=160)
        or _safe_text(row.get("counterparty_name_raw"), limit=160)
    )
    return {
        "transaction_id": txn_id,
        "date": date_text,
        "direction": _safe_text(row.get("direction"), limit=12).upper(),
        "amount": _safe_float(row.get("amount")),
        "description": description,
        "description_raw": description,
        "channel": _safe_text(row.get("channel"), limit=80),
        "counterparty_account": counterparty_account,
        "counterparty_name": counterparty_name,
        "transaction_type": current_type.upper(),
        "confidence": max(0.0, min(1.0, _safe_float(confidence))),
        "heuristic_transaction_type": current_type.upper(),
        "heuristic_confidence": max(0.0, min(1.0, _safe_float(confidence))),
    }


def _preview_item(record: dict[str, Any], llm: dict[str, Any] | None, settings: ClassificationSettings) -> dict[str, Any]:
    current_type = _safe_text(record.get("transaction_type"), limit=40)
    current_name = _safe_text(record.get("counterparty_name"), limit=160)
    current_confidence = max(0.0, min(1.0, _safe_float(record.get("confidence"))))
    current = {
        "transaction_type": current_type,
        "confidence": current_confidence,
        "counterparty_name": current_name,
    }

    base = {
        "transaction_id": record["transaction_id"],
        "direction": record["direction"],
        "amount": record["amount"],
        "description": record["description"],
        "current": current,
        "ai": None,
        "suggested": current,
        "review_required": False,
        "would_apply": False,
        "action": "no_ai_suggestion",
        "reason": "llm_empty",
    }
    if not llm:
        return base

    ai_type = _safe_text(llm.get("transaction_type"), limit=40)
    ai_name = _safe_text(llm.get("counterparty_name"), limit=160)
    ai_confidence = max(0.0, min(1.0, _safe_float(llm.get("confidence"))))
    ai = {
        "transaction_type": ai_type,
        "confidence": ai_confidence,
        "counterparty_name": ai_name,
        "nlp_promptpay": _safe_bool(llm.get("nlp_promptpay")),
        "nlp_accounts": _safe_text(llm.get("nlp_accounts"), limit=240),
    }
    if ai_confidence < settings.llm_min_confidence:
        return {
            **base,
            "ai": ai,
            "review_required": True,
            "action": "below_threshold",
            "reason": "llm_below_threshold",
        }

    suggested = dict(current)
    if settings.allow_transaction_type_override and ai_type:
        suggested["transaction_type"] = ai_type
        suggested["confidence"] = ai_confidence
    if settings.allow_counterparty_name_override and ai_name:
        suggested["counterparty_name"] = ai_name

    type_changed = bool(ai_type and ai_type != current_type)
    name_changed = bool(ai_name and ai_name != current_name)
    if type_changed:
        action = "review_divergence"
        reason = "ai_type_differs_from_current"
    elif name_changed:
        action = "review_name_suggestion"
        reason = "ai_name_differs_from_current"
    else:
        action = "ai_confirmed"
        reason = "ai_matches_current"

    return {
        **base,
        "ai": ai,
        "suggested": suggested,
        "review_required": bool(type_changed or name_changed),
        "would_apply": bool(suggested != current),
        "action": action,
        "reason": reason,
    }


def build_classification_preview(
    transactions: list[dict[str, Any]],
    *,
    model: str = "",
    source_scope: dict[str, Any] | None = None,
    preview_input: str = "manual",
) -> dict[str, Any]:
    """
    Run a read-only local classification preview over analyst-provided transaction rows.

    This intentionally bypasses BSIE_ENABLE_LLM_CLASSIFICATION because the preview is an explicit
    analyst action and does not mutate persisted evidence.
    """
    if not transactions:
        raise ValueError("transactions required")

    warnings: list[str] = []
    if len(transactions) > CLASSIFICATION_PREVIEW_MAX_TRANSACTIONS:
        warnings.append(f"truncated_to_{CLASSIFICATION_PREVIEW_MAX_TRANSACTIONS}_transactions")

    records = [
        _preview_record(row, index)
        for index, row in enumerate(transactions[:CLASSIFICATION_PREVIEW_MAX_TRANSACTIONS])
        if isinstance(row, dict)
    ]
    if not records:
        raise ValueError("no valid transaction objects")

    settings = _preview_settings(model)
    df = pd.DataFrame(records)
    llm_results = _run_local_llm_pipeline(df, settings)
    items = [_preview_item(record, llm_results.get(record["transaction_id"]), settings) for record in records]
    suggestions = [item for item in items if item.get("ai")]
    review_items = [item for item in items if item.get("review_required")]

    if not suggestions:
        warnings.append("local_llm_returned_no_valid_suggestions")

    return {
        "status": "ok" if suggestions else "no_suggestions",
        "source": "local_llm_classification_preview",
        "read_only": True,
        "mutations_allowed": False,
        "provider": "local",
        "model": settings.llm_model_name,
        "preview_input": preview_input,
        "scope": source_scope or {},
        "total": len(items),
        "suggestion_count": len(suggestions),
        "review_count": len(review_items),
        "min_confidence": settings.llm_min_confidence,
        "items": items,
        "warnings": warnings,
    }


def _scope_identity(scope: dict[str, Any]) -> dict[str, str]:
    parser_run_id = _safe_text(scope.get("parser_run_id"), limit=64)
    file_id = _safe_text(scope.get("file_id"), limit=64)
    account = _safe_text(scope.get("account"), limit=64)
    account_digits = _account_digits(account)
    return {
        "parser_run_id": parser_run_id,
        "file_id": file_id,
        "account": account,
        "account_digits": account_digits,
    }


def _scoped_preview_transactions(session: Any, scope: dict[str, Any], *, max_transactions: int) -> list[dict[str, Any]]:
    scope_ids = _scope_identity(scope)
    limit = max(1, min(CLASSIFICATION_PREVIEW_MAX_TRANSACTIONS, int(max_transactions or 1)))
    return search_transactions(
        session,
        account=scope_ids["account_digits"] or scope_ids["account"],
        file_id=scope_ids["file_id"],
        parser_run_id=scope_ids["parser_run_id"],
        limit=limit,
        offset=0,
    )


def build_scoped_classification_preview(
    session: Any,
    scope: dict[str, Any],
    *,
    model: str = "",
    max_transactions: int = 10,
) -> dict[str, Any]:
    scope_ids = _scope_identity(scope)
    if not (scope_ids["parser_run_id"] or scope_ids["file_id"] or scope_ids["account"] or scope_ids["account_digits"]):
        raise ValueError("classification preview scope requires parser_run_id, file_id, or account")

    limit = max(1, min(CLASSIFICATION_PREVIEW_MAX_TRANSACTIONS, int(max_transactions or 1)))
    rows = _scoped_preview_transactions(session, scope_ids, max_transactions=limit)
    if not rows:
        return {
            "status": "no_transactions",
            "source": "local_llm_classification_preview",
            "read_only": True,
            "mutations_allowed": False,
            "provider": "local",
            "model": _preview_settings(model).llm_model_name,
            "preview_input": "scope",
            "scope": scope_ids,
            "total": 0,
            "suggestion_count": 0,
            "review_count": 0,
            "min_confidence": get_classification_settings().llm_min_confidence,
            "items": [],
            "warnings": ["no_transactions_matched_scope"],
        }

    transactions = [
        {
            "transaction_id": row.get("transaction_id") or row.get("id"),
            "date": row.get("transaction_datetime") or row.get("posted_date") or "",
            "direction": row.get("direction") or "",
            "amount": row.get("amount") or 0,
            "description": row.get("description") or row.get("description_normalized") or "",
            "description_normalized": row.get("description_normalized") or "",
            "channel": row.get("channel") or "",
            "counterparty_account": row.get("counterparty_account") or row.get("counterparty_account_normalized") or "",
            "counterparty_name": row.get("counterparty_name") or row.get("counterparty_name_normalized") or "",
            "transaction_type": row.get("transaction_type") or "",
            "confidence": row.get("confidence", row.get("parse_confidence", 0.0)),
        }
        for row in rows
    ]
    return build_classification_preview(
        transactions,
        model=model,
        source_scope=scope_ids,
        preview_input="scope",
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

    if settings.llm_provider == "legacy_openai" and not settings.llm_api_key_present:
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

    llm_results = _run_classification_provider(enriched, settings)
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
