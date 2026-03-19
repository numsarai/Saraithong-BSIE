"""
mapping_memory.py
-----------------
Self-learning column mapping profile system.
Profiles are stored as JSON files in /mapping_profiles/.

Profile structure:
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
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_PROFILES_DIR = Path(__file__).parent.parent / "mapping_profiles"


# ── Internal helpers ───────────────────────────────────────────────────────

def _dir() -> Path:
    _PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return _PROFILES_DIR


def _signature(columns: List[str]) -> str:
    """Stable SHA-256 hash of the sorted normalised column list."""
    normalised = sorted(c.strip().lower() for c in columns)
    raw = "|".join(normalised).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def _load_all() -> List[Dict]:
    profiles = []
    for f in _dir().glob("*.json"):
        try:
            profiles.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            logger.debug(f"Skipping corrupt profile {f.name}: {e}")
    return profiles


def _jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    return len(set_a & set_b) / len(union) if union else 0.0


# ── Public API ─────────────────────────────────────────────────────────────

def find_matching_profile(
    columns: List[str],
    threshold: float = 0.75,
) -> Optional[Dict]:
    """
    Find the best-matching stored profile for the given column list.

    Strategy:
    1. Exact signature match  → returns immediately
    2. Jaccard similarity     → returns if ≥ threshold

    Returns
    -------
    profile dict or None
    """
    sig = _signature(columns)
    profiles = _load_all()

    # Exact match
    for p in profiles:
        if p.get("columns_signature") == sig:
            logger.info(f"Exact profile match: {p['profile_id']} bank={p.get('bank')}")
            return p

    # Jaccard similarity
    col_set = {c.strip().lower() for c in columns}
    best: Optional[Dict] = None
    best_score = 0.0

    for p in profiles:
        stored = {c.strip().lower() for c in p.get("columns", [])}
        if not stored:
            continue
        score = _jaccard(col_set, stored)
        if score > best_score:
            best_score = score
            best = p

    if best_score >= threshold and best:
        logger.info(
            f"Fuzzy profile match: {best['profile_id']} "
            f"bank={best.get('bank')} score={best_score:.2f}"
        )
        return best

    logger.info(f"No matching profile found for {len(columns)} columns")
    return None


def save_profile(
    bank: str,
    columns: List[str],
    mapping: Dict[str, Optional[str]],
) -> Dict:
    """
    Persist a confirmed column mapping as a reusable profile.
    If a profile with the same column signature already exists, update it.

    Returns the saved profile dict.
    """
    d   = _dir()
    sig = _signature(columns)
    now = datetime.now(timezone.utc).isoformat()

    # Update existing profile if signature matches
    for f in d.glob("*.json"):
        try:
            existing = json.loads(f.read_text(encoding="utf-8"))
            if existing.get("columns_signature") == sig:
                existing["mapping"]     = mapping
                existing["bank"]        = bank
                existing["usage_count"] = existing.get("usage_count", 0) + 1
                existing["last_used"]   = now
                f.write_text(
                    json.dumps(existing, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                logger.info(f"Updated profile {existing['profile_id']} (count={existing['usage_count']})")
                return existing
        except Exception:
            pass

    # Create new profile
    pid = str(uuid.uuid4())
    profile = {
        "profile_id":        pid,
        "bank":              bank,
        "columns":           columns,
        "columns_signature": sig,
        "mapping":           mapping,
        "usage_count":       1,
        "last_used":         now,
        "created_at":        now,
    }
    (d / f"{pid}.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Saved new profile {pid} for bank={bank}")
    return profile


def list_profiles() -> List[Dict]:
    """Return all stored profiles sorted by last_used descending."""
    profiles = _load_all()
    profiles.sort(key=lambda p: p.get("last_used", ""), reverse=True)
    return profiles
