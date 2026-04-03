"""
bank_memory.py
--------------
Persistent header fingerprint memory for bank auto-detection.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.column_detector import _norm

logger = logging.getLogger(__name__)


def _ordered_signature(columns: List[str]) -> str:
    """Stable signature preserving column order."""
    normalized = [_norm(c) for c in columns if _norm(c)]
    raw = "|".join(normalized).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def _set_signature(columns: List[str]) -> str:
    """Stable signature ignoring column order."""
    normalized = sorted({_norm(c) for c in columns if _norm(c)})
    raw = "|".join(normalized).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _usage_bonus(usage_count: int) -> float:
    if usage_count <= 0:
        return 0.0
    return min(math.log1p(usage_count) / 20.0, 0.08)


def _usage_increment_value(usage_increment: int) -> int:
    try:
        return max(1, int(usage_increment or 1))
    except (TypeError, ValueError):
        return 1


def _sheet_name_bonus(candidate_sheet: str, current_sheet: str) -> float:
    current = str(current_sheet or "").strip().lower()
    candidate = str(candidate_sheet or "").strip().lower()
    if not current or not candidate:
        return 0.0
    if candidate == current:
        return 0.05
    if candidate in current or current in candidate:
        return 0.025
    return 0.0


def _rank_score(row: Dict, *, base_score: float, sheet_name: str) -> float:
    return round(
        base_score
        + _usage_bonus(int(row.get("usage_count", 0) or 0))
        + _sheet_name_bonus(str(row.get("sheet_name", "") or ""), sheet_name),
        6,
    )


def save_bank_fingerprint(
    bank_key: str,
    columns: List[str],
    header_row: int = 0,
    sheet_name: str = "",
    usage_increment: int = 1,
) -> Dict:
    """Persist or update a confirmed bank fingerprint from a header set."""
    from database import BankFingerprint, get_session
    from sqlmodel import select

    bank_key = str(bank_key or "").strip().lower()
    if not bank_key or bank_key == "generic":
        raise ValueError("bank_key must be a specific bank, not generic")

    ordered_sig = _ordered_signature(columns)
    set_sig = _set_signature(columns)
    now = datetime.now(timezone.utc)
    increment = _usage_increment_value(usage_increment)

    with get_session() as session:
        statement = select(BankFingerprint).where(BankFingerprint.ordered_signature == ordered_sig)
        existing = session.exec(statement).first()

        if existing:
            existing.bank_key = bank_key
            existing.columns_json = json.dumps(columns)
            existing.set_signature = set_sig
            existing.header_row = int(header_row or 0)
            existing.sheet_name = str(sheet_name or "")
            existing.usage_count = int(existing.usage_count or 0) + increment
            existing.last_used = now
            session.add(existing)
            session.commit()
            session.refresh(existing)
            logger.info("Updated bank fingerprint %s bank=%s", existing.fingerprint_id, bank_key)
            return existing.to_dict()

        row = BankFingerprint(
            fingerprint_id=str(uuid.uuid4()),
            bank_key=bank_key,
            columns_json=json.dumps(columns),
            ordered_signature=ordered_sig,
            set_signature=set_sig,
            header_row=int(header_row or 0),
            sheet_name=str(sheet_name or ""),
            usage_count=increment,
            last_used=now,
            created_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        logger.info("Saved bank fingerprint %s bank=%s", row.fingerprint_id, bank_key)
        return row.to_dict()


def find_matching_bank_fingerprint(
    columns: List[str],
    sheet_name: str = "",
    threshold: float = 0.82,
) -> Optional[Dict]:
    """
    Find the best matching saved bank fingerprint for this header set.

    Strategy:
    1. Exact ordered signature
    2. Exact set signature
    3. Jaccard similarity on normalized column sets
    """
    from database import BankFingerprint, get_session
    from sqlmodel import select

    ordered_sig = _ordered_signature(columns)
    set_sig = _set_signature(columns)

    with get_session() as session:
        exact_matches = session.exec(
            select(BankFingerprint).where(BankFingerprint.ordered_signature == ordered_sig)
        ).all()
        if exact_matches:
            exact = max(
                (row.to_dict() for row in exact_matches),
                key=lambda row: (
                    _rank_score(row, base_score=1.0, sheet_name=sheet_name),
                    int(row.get("usage_count", 0) or 0),
                    str(row.get("last_used") or ""),
                    str(row.get("fingerprint_id") or ""),
                ),
            )
            result = dict(exact)
            result["match_type"] = "exact_order"
            result["match_score"] = 1.0
            result["rank_score"] = round(_rank_score(result, base_score=1.0, sheet_name=sheet_name), 3)
            return result

        set_matches = session.exec(
            select(BankFingerprint).where(BankFingerprint.set_signature == set_sig)
        ).all()
        if set_matches:
            set_match = max(
                (row.to_dict() for row in set_matches),
                key=lambda row: (
                    _rank_score(row, base_score=0.97, sheet_name=sheet_name),
                    int(row.get("usage_count", 0) or 0),
                    str(row.get("last_used") or ""),
                    str(row.get("fingerprint_id") or ""),
                ),
            )
            result = dict(set_match)
            result["match_type"] = "exact_set"
            result["match_score"] = 0.97
            result["rank_score"] = round(_rank_score(result, base_score=0.97, sheet_name=sheet_name), 3)
            return result

        all_rows = [row.to_dict() for row in session.exec(select(BankFingerprint)).all()]

    current_set = {_norm(c) for c in columns if _norm(c)}
    best = None
    best_rank = None
    best_match_score = 0.0
    for row in all_rows:
        stored = {_norm(c) for c in row.get("columns", []) if _norm(c)}
        raw_score = _jaccard(current_set, stored)
        if raw_score < threshold:
            continue
        score = _rank_score(row, base_score=raw_score, sheet_name=sheet_name)
        rank = (
            round(score, 6),
            int(row.get("usage_count", 0) or 0),
            str(row.get("last_used") or ""),
            str(row.get("fingerprint_id") or ""),
        )
        if best_rank is None or rank > best_rank:
            best = row
            best_rank = rank
            best_match_score = raw_score

    if best and best_rank is not None:
        best["match_type"] = "jaccard"
        best["match_score"] = round(best_match_score, 3)
        best["rank_score"] = round(best_rank[0], 3)
        return best
    return None
