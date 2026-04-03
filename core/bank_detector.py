"""
bank_detector.py
----------------
Weighted auto-detection of bank statement source based on workbook structure,
header aliases, format clues, and bank-specific signatures.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd

from core.column_detector import _compact, _norm, _score_alias_match, best_match_for_aliases
from paths import BUILTIN_CONFIG_DIR, CONFIG_DIR

logger = logging.getLogger(__name__)


DEFAULT_DETECTION = {
    "keywords": [],
    "strong_headers": [],
    "weak_headers": [],
    "negative_headers": [],
}


@dataclass
class DetectionContext:
    actual_columns: List[str]
    header_candidates: List[str]
    header_text: str
    body_text: str
    haystack: str
    keyword_text: str
    observed_layout: str


def _load_all_configs() -> Dict[str, dict]:
    """Load built-in configs first, then user configs on top."""
    configs: Dict[str, dict] = {}
    for config_dir in (BUILTIN_CONFIG_DIR, CONFIG_DIR):
        if not config_dir.exists():
            continue
        for path in sorted(config_dir.glob("*.json")):
            try:
                configs[path.stem] = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.debug("Could not load config %s: %s", path, exc)
    return configs


def _clean_text(value: object) -> str:
    text = _norm(value)
    return "" if text in {"", "nan", "none", "nat"} else text


def _dedupe_keep_order(values: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for value in values:
        key = _clean_text(value)
        if key and key not in seen:
            seen.add(key)
            out.append(str(value).strip())
    return out


def _extract_header_candidates(df: pd.DataFrame) -> List[str]:
    """Collect likely header labels from columns and the first preview rows."""
    candidates: List[str] = []
    textual_cols = 0

    for col in df.columns:
        text = _clean_text(col)
        if not text or text.isdigit() or text.startswith("unnamed"):
            continue
        textual_cols += 1
        candidates.append(str(col).strip())

    # If the DataFrame already has a real header row, trust it and do not
    # pollute header evidence with transaction body values.
    if textual_cols >= max(4, len(df.columns) // 2):
        return _dedupe_keep_order(candidates)

    preview_limit = min(8, len(df))
    for _, row in df.head(preview_limit).iterrows():
        row_values = [str(v).strip() for v in row.values if _clean_text(v)]
        if not row_values:
            continue
        if len(row_values) <= max(12, len(df.columns) + 2):
            candidates.extend(row_values)

    return _dedupe_keep_order(candidates)


def _extract_body_values(df: pd.DataFrame, max_rows: int = 30) -> List[str]:
    values: List[str] = []
    for _, row in df.head(max_rows).iterrows():
        values.extend(str(v).strip() for v in row.values if _clean_text(v))
    return _dedupe_keep_order(values)


def _field_present(candidates: List[str], aliases: List[str], threshold: float = 0.84) -> bool:
    matched, _ = best_match_for_aliases(candidates, aliases, threshold=threshold)
    return matched is not None


def _infer_layout(candidates: List[str], cfg: dict) -> str:
    mapping = cfg.get("column_mapping", {})
    has_sender = _field_present(candidates, mapping.get("sender_account", []), 0.86)
    has_receiver = _field_present(candidates, mapping.get("receiver_account", []), 0.86)
    has_debit = _field_present(candidates, mapping.get("debit", []), 0.82)
    has_credit = _field_present(candidates, mapping.get("credit", []), 0.82)
    has_amount = _field_present(candidates, mapping.get("amount", []), 0.82)
    has_direction_marker = _field_present(candidates, mapping.get("direction_marker", []), 0.86)

    if has_sender and has_receiver and has_amount and has_direction_marker:
        return "direction_marker_like"
    if has_sender and has_receiver and has_amount and not (has_debit and has_credit):
        return "ktb_transfer_like"
    if has_sender and has_receiver and has_debit and has_credit:
        return "dual_account_like"
    if has_debit and has_credit:
        return "debit_credit_like"
    if has_amount:
        return "signed_amount_like"
    return "unknown"


def _build_context(df: pd.DataFrame, extra_text: str = "") -> DetectionContext:
    header_candidates = _extract_header_candidates(df)
    body_values = _extract_body_values(df)
    actual_columns = [str(c).strip() for c in df.columns]
    header_text = " ".join(_clean_text(v) for v in header_candidates if _clean_text(v))
    body_text = " ".join(_clean_text(v) for v in body_values if _clean_text(v))
    haystack = " ".join(part for part in [header_text, body_text, _clean_text(extra_text)] if part)
    keyword_text = " ".join(part for part in [header_text, _clean_text(extra_text)] if part)
    observed_layout = _infer_layout(header_candidates or actual_columns, {"column_mapping": {
        "sender_account": ["sender account", "บัญชีผู้โอน", "หมายเลขบัญชีต้นทาง", "เลขที่บัญชีผู้โอน"],
        "receiver_account": ["receiver account", "บัญชีผู้รับโอน", "หมายเลขบัญชีปลายทาง", "เลขที่บัญชีผู้รับโอน"],
        "debit": ["debit", "withdraw", "ถอนเงิน", "เดบิต"],
        "credit": ["credit", "deposit", "ฝากเงิน", "เครดิต", "เงินฝาก"],
        "amount": ["amount", "จำนวนเงิน"],
        "direction_marker": ["ฝาก-ถอน", "debit/credit", "dr/cr"],
    }})
    return DetectionContext(
        actual_columns=actual_columns,
        header_candidates=header_candidates or actual_columns,
        header_text=header_text,
        body_text=body_text,
        haystack=haystack,
        keyword_text=keyword_text,
        observed_layout=observed_layout,
    )


def _match_header_phrase(candidates: List[str], phrase: str, threshold: float) -> Tuple[str, float] | Tuple[None, float]:
    best_header = None
    best_score = 0.0
    for candidate in candidates:
        score = _score_alias_match(phrase, candidate)
        if score > best_score:
            best_score = score
            best_header = candidate
    if best_header and best_score >= threshold:
        return best_header, round(best_score, 3)
    return None, 0.0


def _text_contains(haystack: str, phrase: str) -> bool:
    if not haystack or not phrase:
        return False
    haystack_norm = _clean_text(haystack)
    phrase_norm = _clean_text(phrase)
    if not haystack_norm or not phrase_norm:
        return False
    return phrase_norm in haystack_norm


def _layout_score(cfg: dict, observed_layout: str) -> Tuple[float, List[str], List[str]]:
    positives: List[str] = []
    negatives: List[str] = []
    fmt = cfg.get("format_type", "standard")
    amount_mode = cfg.get("amount_mode", "signed")
    score = 0.0

    if observed_layout == "unknown":
        return score, positives, negatives

    if fmt == "ktb_transfer":
        if observed_layout == "ktb_transfer_like":
            score += 3.2
            positives.append("layout:ktb_transfer_like")
        else:
            score -= 1.6
            negatives.append(f"layout_mismatch:{observed_layout}")
        return score, positives, negatives

    if fmt == "direction_marker":
        if observed_layout == "direction_marker_like":
            score += 2.4
            positives.append("layout:direction_marker_like")
        elif observed_layout == "debit_credit_like":
            score += 0.9
            positives.append("layout:debit_credit_like_fallback")
        else:
            score -= 0.8
            negatives.append(f"layout_mismatch:{observed_layout}")
        return score, positives, negatives

    if fmt == "dual_account":
        if observed_layout == "dual_account_like":
            score += 2.6
            positives.append("layout:dual_account_like")
        elif observed_layout == "ktb_transfer_like":
            score -= 1.2
            negatives.append("layout_mismatch:ktb_transfer_like")
    elif amount_mode == "debit_credit":
        if observed_layout == "debit_credit_like":
            score += 1.8
            positives.append("layout:debit_credit_like")
        elif observed_layout == "direction_marker_like" and cfg.get("column_mapping", {}).get("direction_marker"):
            score += 1.6
            positives.append("layout:direction_marker_like_fallback")
        elif observed_layout == "signed_amount_like":
            score -= 0.5
            negatives.append("layout_mismatch:signed_amount_like")
    elif amount_mode == "signed":
        if observed_layout == "signed_amount_like":
            score += 1.8
            positives.append("layout:signed_amount_like")
        elif observed_layout == "debit_credit_like":
            score -= 0.5
            negatives.append("layout_mismatch:debit_credit_like")

    return score, positives, negatives


def _score_config_candidate(key: str, cfg: dict, context: DetectionContext) -> Tuple[float, List[str], List[str]]:
    score = 0.0
    positives: List[str] = []
    negatives: List[str] = []

    detection = dict(DEFAULT_DETECTION)
    detection.update(cfg.get("detection", {}))
    bank_name = str(cfg.get("bank_name", key)).strip()
    column_mapping = cfg.get("column_mapping", {})

    keyword_phrases: List[str] = []
    seen_phrases: set[str] = set()
    for phrase in [bank_name, key] + list(detection.get("keywords", [])):
        normalized = _clean_text(phrase)
        if normalized and normalized not in seen_phrases:
            seen_phrases.add(normalized)
            keyword_phrases.append(str(phrase).strip())

    for phrase in keyword_phrases:
        if phrase and _text_contains(context.keyword_text, phrase):
            score += 2.6 if phrase in detection.get("keywords", []) else 3.0
            positives.append(f"keyword:{phrase}")

    for phrase in detection.get("strong_headers", []):
        matched_header, matched_score = _match_header_phrase(context.header_candidates, phrase, 0.86)
        if matched_header:
            score += 2.1
            positives.append(f"strong_header:{phrase}->{matched_header}:{matched_score}")

    for phrase in detection.get("weak_headers", []):
        matched_header, matched_score = _match_header_phrase(context.header_candidates, phrase, 0.80)
        if matched_header:
            score += 0.8
            positives.append(f"weak_header:{phrase}->{matched_header}:{matched_score}")

    for phrase in detection.get("negative_headers", []):
        matched_header, matched_score = _match_header_phrase(context.header_candidates, phrase, 0.94)
        if matched_header:
            score -= 1.6
            negatives.append(f"negative_header:{phrase}->{matched_header}:{matched_score}")

    field_hits = 0
    total_fields = len(column_mapping) or 1
    weighted_hits = 0.0
    for field, aliases in column_mapping.items():
        best_col, best_score = best_match_for_aliases(context.header_candidates, aliases, threshold=0.84)
        if not best_col:
            continue
        field_hits += 1
        weight = 0.5
        if field in {"sender_account", "receiver_account", "sender_name", "receiver_name"}:
            weight = 1.25
        elif field in {"amount", "debit", "credit", "balance"}:
            weight = 0.8
        weighted_hits += weight
        positives.append(f"field:{field}->{best_col}:{best_score}")

    coverage_bonus = weighted_hits + ((field_hits / total_fields) * 1.8)
    score += coverage_bonus

    layout_delta, layout_positive, layout_negative = _layout_score(cfg, context.observed_layout)
    score += layout_delta
    positives.extend(layout_positive)
    negatives.extend(layout_negative)

    strong_headers = detection.get("strong_headers", [])
    if strong_headers and not any(item.startswith("strong_header:") for item in positives):
        score -= 0.6
        negatives.append("missing_strong_header")

    return round(score, 3), positives, negatives


def detect_bank(
    df: pd.DataFrame,
    extra_text: str = "",
    sheet_name: str = "",
) -> Dict:
    """
    Score every known bank config against the DataFrame structure and text.

    Returns the best candidate plus evidence and ranked alternatives.
    """
    configs = _load_all_configs()
    if not configs:
        return {
            "bank": "UNKNOWN",
            "config_key": "",
            "key": "",
            "score": 0.0,
            "confidence": 0.0,
            "scores": {},
            "top_candidates": [],
            "evidence": {"positive": [], "negative": [], "layout": "unknown"},
            "ambiguous": False,
        }

    context = _build_context(df, extra_text)
    score_map: Dict[str, float] = {}
    evidence_map: Dict[str, Dict[str, List[str] | str]] = {}

    for key, cfg in configs.items():
        score, positives, negatives = _score_config_candidate(key, cfg, context)
        score_map[key] = score
        evidence_map[key] = {
            "positive": positives,
            "negative": negatives,
            "layout": context.observed_layout,
        }

    fingerprint_match = None
    try:
        from core.bank_memory import find_matching_bank_fingerprint

        fingerprint_match = find_matching_bank_fingerprint(context.actual_columns, sheet_name=sheet_name)
    except Exception as exc:
        logger.debug("Bank fingerprint lookup skipped: %s", exc)

    if fingerprint_match:
        bank_key = str(fingerprint_match.get("bank_key", "") or "").strip().lower()
        match_type = str(fingerprint_match.get("match_type", "") or "")
        match_score = float(fingerprint_match.get("match_score", 0.0) or 0.0)
        rank_score = float(fingerprint_match.get("rank_score", match_score) or match_score)
        if bank_key in score_map:
            boost = 4.0 if match_type == "exact_order" else 3.2 if match_type == "exact_set" else 2.0 * match_score
            boost += min(max(rank_score - match_score, 0.0), 1.0)
            score_map[bank_key] = round(score_map[bank_key] + boost, 3)
            evidence_map[bank_key]["positive"].append(
                f"fingerprint:{match_type}:{match_score}:rank={rank_score}->{bank_key}"
            )

    ranked = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
    best_key, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = best_score - second_score

    absolute_conf = max(0.0, min(best_score / 12.0, 1.0))
    margin_conf = max(0.0, min(margin / 4.0, 1.0))
    confidence = round((absolute_conf * 0.65) + (margin_conf * 0.35), 3)
    ambiguous = second_score > 0 and margin < 1.2

    if best_score < 2.0:
        bank_name = "UNKNOWN"
        config_key = ""
    else:
        config_key = best_key
        bank_name = configs[best_key].get("bank_name", best_key.upper())
        if ambiguous:
            confidence = min(confidence, 0.64)
        if best_key == "generic":
            confidence = min(confidence, 0.55)
            ambiguous = True

    top_candidates = [key for key, score in ranked[:3] if score > 0]
    logger.info(
        "Bank detected: %s (score=%.2f conf=%.2f margin=%.2f layout=%s)",
        bank_name,
        best_score,
        confidence,
        margin,
        context.observed_layout,
    )

    return {
        "bank": bank_name,
        "config_key": config_key,
        "key": config_key,
        "score": round(best_score, 3),
        "confidence": confidence,
        "scores": {key: round(score, 3) for key, score in ranked},
        "top_candidates": top_candidates,
        "evidence": evidence_map.get(best_key, {"positive": [], "negative": [], "layout": context.observed_layout}),
        "ambiguous": ambiguous,
    }
