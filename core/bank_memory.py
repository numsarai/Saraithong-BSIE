"""
bank_memory.py
--------------
Persistent header fingerprint memory for bank auto-detection.
"""

from __future__ import annotations

import hashlib
import json
import logging
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


def save_bank_fingerprint(
    bank_key: str,
    columns: List[str],
    header_row: int = 0,
    sheet_name: str = "",
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

    with get_session() as session:
        statement = select(BankFingerprint).where(BankFingerprint.ordered_signature == ordered_sig)
        existing = session.exec(statement).first()

        if existing:
            existing.bank_key = bank_key
            existing.columns_json = json.dumps(columns)
            existing.set_signature = set_sig
            existing.header_row = int(header_row or 0)
            existing.sheet_name = str(sheet_name or "")
            existing.usage_count = existing.usage_count + 1
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
            usage_count=1,
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
        exact = session.exec(
            select(BankFingerprint).where(BankFingerprint.ordered_signature == ordered_sig)
        ).first()
        if exact:
            result = exact.to_dict()
            result["match_type"] = "exact_order"
            result["match_score"] = 1.0
            return result

        set_match = session.exec(
            select(BankFingerprint).where(BankFingerprint.set_signature == set_sig)
        ).first()
        if set_match:
            result = set_match.to_dict()
            result["match_type"] = "exact_set"
            result["match_score"] = 0.97
            return result

        all_rows = [row.to_dict() for row in session.exec(select(BankFingerprint)).all()]

    current_set = {_norm(c) for c in columns if _norm(c)}
    best = None
    best_score = 0.0
    for row in all_rows:
        stored = {_norm(c) for c in row.get("columns", []) if _norm(c)}
        score = _jaccard(current_set, stored)
        if score > best_score:
            best = row
            best_score = score

    if best and best_score >= threshold:
        best["match_type"] = "jaccard"
        best["match_score"] = round(best_score, 3)
        return best
    return None
