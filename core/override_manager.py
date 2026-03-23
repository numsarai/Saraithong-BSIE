"""
override_manager.py
-------------------
Manages manual relationship overrides for transactions.
Overrides are persisted in /overrides/overrides.json.

Override record:
{
  "transaction_id"       : str,
  "override_from_account": str,
  "override_to_account"  : str,
  "override_reason"      : str,
  "override_by"          : str,
  "override_timestamp"   : ISO str
}
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

from paths import OVERRIDES_DIR as _OVERRIDES_DIR
_OVERRIDES_FILE = _OVERRIDES_DIR / "overrides.json"


# ── Persistence helpers ────────────────────────────────────────────────────

def _ensure_file() -> Path:
    _OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _OVERRIDES_FILE.exists():
        _OVERRIDES_FILE.write_text("[]", encoding="utf-8")
    return _OVERRIDES_FILE


def _load() -> List[Dict]:
    f = _ensure_file()
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(overrides: List[Dict]) -> None:
    _ensure_file()
    _OVERRIDES_FILE.write_text(
        json.dumps(overrides, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Public API ─────────────────────────────────────────────────────────────

def add_override(
    transaction_id: str,
    from_account: str,
    to_account: str,
    reason: str = "",
    override_by: str = "analyst",
) -> Dict:
    """
    Add or update a manual relationship override.
    If an override for the same transaction_id already exists, it is replaced.

    Returns the saved override record.
    """
    overrides = _load()
    now = datetime.now(timezone.utc).isoformat()

    record = {
        "transaction_id":        transaction_id,
        "override_from_account": from_account,
        "override_to_account":   to_account,
        "override_reason":       reason,
        "override_by":           override_by,
        "override_timestamp":    now,
    }

    # Replace existing override for the same transaction
    existing_ids = [o["transaction_id"] for o in overrides]
    if transaction_id in existing_ids:
        idx = existing_ids.index(transaction_id)
        overrides[idx] = record
        logger.info(f"Updated override for {transaction_id}")
    else:
        overrides.append(record)
        logger.info(f"Added override for {transaction_id}")

    _save(overrides)
    return record


def remove_override(transaction_id: str) -> bool:
    """Remove an override by transaction_id. Returns True if removed."""
    overrides = _load()
    new_list = [o for o in overrides if o["transaction_id"] != transaction_id]
    if len(new_list) < len(overrides):
        _save(new_list)
        logger.info(f"Removed override for {transaction_id}")
        return True
    return False


def get_all_overrides() -> List[Dict]:
    """Return all stored overrides."""
    return _load()


def get_override(transaction_id: str) -> Optional[Dict]:
    """Return override for a specific transaction_id or None."""
    for o in _load():
        if o["transaction_id"] == transaction_id:
            return o
    return None


def apply_overrides_to_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all stored overrides to a transaction DataFrame.

    Adds / updates columns:
        is_overridden         : bool
        override_from_account : str
        override_to_account   : str
        override_reason       : str
        override_by           : str
        override_timestamp    : str

    For overridden rows:
        from_account = override_from_account
        to_account   = override_to_account
        confidence   = 1.0
    """
    overrides = _load()
    if not overrides:
        # Ensure override columns exist even with no overrides
        df = df.copy()
        for col in ["is_overridden", "override_from_account", "override_to_account",
                    "override_reason", "override_by", "override_timestamp"]:
            if col not in df.columns:
                df[col] = "" if col != "is_overridden" else False
        return df

    override_map: Dict[str, Dict] = {o["transaction_id"]: o for o in overrides}
    df = df.copy()

    # Initialise override columns
    df["is_overridden"]         = False
    df["override_from_account"] = ""
    df["override_to_account"]   = ""
    df["override_reason"]       = ""
    df["override_by"]           = ""
    df["override_timestamp"]    = ""

    applied = 0
    for idx, row in df.iterrows():
        tid = str(row.get("transaction_id", ""))
        if tid in override_map:
            ov = override_map[tid]
            df.at[idx, "is_overridden"]         = True
            df.at[idx, "override_from_account"] = ov["override_from_account"]
            df.at[idx, "override_to_account"]   = ov["override_to_account"]
            df.at[idx, "override_reason"]       = ov.get("override_reason", "")
            df.at[idx, "override_by"]           = ov.get("override_by", "")
            df.at[idx, "override_timestamp"]    = ov.get("override_timestamp", "")
            # Apply to link columns
            df.at[idx, "from_account"]          = ov["override_from_account"]
            df.at[idx, "to_account"]            = ov["override_to_account"]
            df.at[idx, "confidence"]            = 1.0
            applied += 1

    if applied:
        logger.info(f"Applied {applied} manual overrides to DataFrame")
    return df
