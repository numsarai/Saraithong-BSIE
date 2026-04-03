"""
mapping_memory.py
-----------------
Self-learning column mapping profile system.
Profiles are stored in the SQLite DB (mapping_profile table).

Profile structure (as returned dict):
{
  "profile_id"         : uuid,
  "bank"               : str,
  "columns"            : [str],   – original column names
  "columns_signature"  : str,     – SHA-256 hash of sorted normalised columns
  "mapping"            : {field: column|null},
  "usage_count"        : int,
  "last_used"          : ISO timestamp,
  "created_at"         : ISO timestamp
}
"""

import hashlib
import json
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Internal helpers ───────────────────────────────────────────────────────


def _normalized_columns(columns: List[str]) -> List[str]:
    normalized: List[str] = []
    for column in columns:
        text = str(column or "").strip().lower()
        if not text or text.startswith("_"):
            continue
        normalized.append(text)
    return normalized

def _signature(columns: List[str]) -> str:
    """Stable SHA-256 hash of the sorted normalised column list."""
    normalised = sorted(_normalized_columns(columns))
    raw = "|".join(normalised).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def _jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    return len(set_a & set_b) / len(union) if union else 0.0


def _bank_hint_score(candidate_bank: str, requested_bank: str) -> float:
    requested = str(requested_bank or "").strip().lower()
    candidate = str(candidate_bank or "").strip().lower()
    if not requested or not candidate:
        return 0.0
    if candidate == requested:
        return 0.12
    return -0.04


def _usage_bonus(usage_count: int) -> float:
    if usage_count <= 0:
        return 0.0
    return min(math.log1p(usage_count) / 18.0, 0.08)


def _usage_increment_value(usage_increment: int) -> int:
    try:
        return max(1, int(usage_increment or 1))
    except (TypeError, ValueError):
        return 1


# ── Public API ─────────────────────────────────────────────────────────────

def find_matching_profile(
    columns: List[str],
    bank: str = "",
    threshold: float = 0.75,
) -> Optional[Dict]:
    """
    Find the best-matching stored profile for the given column list.

    Strategy:
    1. Exact signature match  → returns immediately
    2. Jaccard similarity     → returns if >= threshold

    Returns
    -------
    profile dict or None
    """
    from database import get_session, MappingProfile
    from sqlmodel import select

    sig = _signature(columns)

    with get_session() as session:
        # Exact match by signature
        statement = select(MappingProfile).where(MappingProfile.columns_signature == sig)
        exact = session.exec(statement).first()
        if exact:
            logger.info(f"Exact profile match: {exact.profile_id} bank={exact.bank}")
            return exact.to_dict()

        # Jaccard similarity against all profiles — convert to dicts inside session
        all_profiles = [p.to_dict() for p in session.exec(select(MappingProfile)).all()]

    col_set = set(_normalized_columns(columns))
    best: Optional[Dict] = None
    best_rank: tuple[float, int, str, str] | None = None
    best_match_score = 0.0

    for p in all_profiles:
        stored = set(_normalized_columns(p.get("columns", [])))
        if not stored:
            continue
        raw_score = _jaccard(col_set, stored)
        if raw_score < threshold:
            continue
        score = raw_score
        score += _bank_hint_score(p.get("bank", ""), bank)
        score += _usage_bonus(int(p.get("usage_count", 0) or 0))
        rank = (
            round(score, 6),
            int(p.get("usage_count", 0) or 0),
            str(p.get("last_used") or ""),
            str(p.get("profile_id") or ""),
        )
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best = p
            best_match_score = raw_score

    if best_rank is not None and best:
        best = dict(best)
        best["match_score"] = round(best_match_score, 3)
        best["rank_score"] = round(best_rank[0], 3)
        logger.info(
            f"Fuzzy profile match: {best['profile_id']} "
            f"bank={best['bank']} requested_bank={bank or 'any'} score={best_rank[0]:.2f}"
        )
        return best

    logger.info(f"No matching profile found for {len(col_set)} columns")
    return None


def save_profile(
    bank: str,
    columns: List[str],
    mapping: Dict[str, Optional[str]],
    usage_increment: int = 1,
) -> Dict:
    """
    Persist a confirmed column mapping as a reusable profile.
    If a profile with the same column signature already exists, update it.

    Returns the saved profile dict.
    """
    from database import get_session, MappingProfile
    from sqlmodel import select

    sig = _signature(columns)
    now = datetime.now(timezone.utc)
    increment = _usage_increment_value(usage_increment)

    with get_session() as session:
        statement = select(MappingProfile).where(MappingProfile.columns_signature == sig)
        existing = session.exec(statement).first()

        if existing:
            existing.mapping_json = json.dumps(mapping)
            existing.bank = bank
            existing.usage_count = int(existing.usage_count or 0) + increment
            existing.last_used = now
            session.add(existing)
            session.commit()
            session.refresh(existing)
            result = existing.to_dict()
            logger.info(f"Updated profile {existing.profile_id} (count={existing.usage_count})")
            return result

        # Create new profile
        pid = str(uuid.uuid4())
        profile = MappingProfile(
            profile_id=pid,
            bank=bank,
            columns_json=json.dumps(columns),
            columns_signature=sig,
            mapping_json=json.dumps(mapping),
            usage_count=increment,
            last_used=now,
            created_at=now,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        result = profile.to_dict()
        logger.info(f"Saved new profile {pid} for bank={bank}")
        return result


def list_profiles() -> List[Dict]:
    """Return all stored profiles sorted by last_used descending."""
    from database import get_session, MappingProfile
    from sqlmodel import select

    with get_session() as session:
        all_profiles = session.exec(select(MappingProfile)).all()
        result = [p.to_dict() for p in all_profiles]

    result.sort(key=lambda p: p.get("last_used") or "", reverse=True)
    return result
