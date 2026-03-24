"""
override_manager.py
-------------------
Manages manual relationship overrides for transactions.
Overrides are stored in the SQLite DB (override table).

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

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


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
    from database import get_session, Override
    from sqlmodel import select

    now = datetime.now(timezone.utc)

    with get_session() as session:
        statement = select(Override).where(Override.transaction_id == transaction_id)
        existing = session.exec(statement).first()

        if existing:
            existing.override_from_account = from_account
            existing.override_to_account = to_account
            existing.override_reason = reason
            existing.override_by = override_by
            existing.override_timestamp = now
            session.add(existing)
            session.commit()
            session.refresh(existing)
            result = existing.to_dict()
            logger.info(f"Updated override for {transaction_id}")
            return result

        row = Override(
            transaction_id=transaction_id,
            override_from_account=from_account,
            override_to_account=to_account,
            override_reason=reason,
            override_by=override_by,
            override_timestamp=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        result = row.to_dict()
        logger.info(f"Added override for {transaction_id}")
        return result


def remove_override(transaction_id: str) -> bool:
    """Remove an override by transaction_id. Returns True if removed."""
    from database import get_session, Override
    from sqlmodel import select

    with get_session() as session:
        statement = select(Override).where(Override.transaction_id == transaction_id)
        existing = session.exec(statement).first()
        if existing:
            session.delete(existing)
            session.commit()
            logger.info(f"Removed override for {transaction_id}")
            return True
    return False


def get_all_overrides() -> List[Dict]:
    """Return all stored overrides."""
    from database import get_session, Override
    from sqlmodel import select

    with get_session() as session:
        all_overrides = session.exec(select(Override)).all()
        return [o.to_dict() for o in all_overrides]


def get_override(transaction_id: str) -> Optional[Dict]:
    """Return override for a specific transaction_id or None."""
    from database import get_session, Override
    from sqlmodel import select

    with get_session() as session:
        statement = select(Override).where(Override.transaction_id == transaction_id)
        row = session.exec(statement).first()
        if row:
            return row.to_dict()
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
    overrides = get_all_overrides()
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
