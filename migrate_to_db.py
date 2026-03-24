# migrate_to_db.py — One-time migration from JSON files to SQLite DB
from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


def migrate_json_to_db():
    """Migrate existing JSON file stores to SQLite. No-op if already migrated."""
    from database import get_session, MappingProfile, Override
    from sqlmodel import select

    with get_session() as session:
        _migrate_profiles(session)
        _migrate_overrides(session)
        session.commit()


def _migrate_profiles(session):
    from database import MappingProfile
    from sqlmodel import select
    from paths import PROFILES_DIR

    existing = session.exec(select(MappingProfile)).all()
    if existing:
        log.info("mapping_profile table already populated, skipping migration.")
        return

    if not PROFILES_DIR.exists():
        log.info("No mapping_profiles directory found, skipping.")
        return

    seen_sigs = set()
    seen_ids = set()
    migrated = 0
    skipped = 0
    for f in PROFILES_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sig = data.get("columns_signature", "")
            pid = data.get("profile_id", f.stem)
            # Skip duplicates — keep highest usage_count version
            if sig in seen_sigs or pid in seen_ids:
                log.warning(f"Skipping duplicate profile {f.name} (sig={sig})")
                skipped += 1
                continue
            seen_sigs.add(sig)
            seen_ids.add(pid)
            row = MappingProfile(
                profile_id=pid,
                bank=data.get("bank", ""),
                columns_json=json.dumps(data.get("columns", [])),
                columns_signature=sig,
                mapping_json=json.dumps(data.get("mapping", {})),
                usage_count=data.get("usage_count", 0),
                last_used=_parse_dt(data.get("last_used")),
                created_at=_parse_dt(data.get("created_at")) or datetime.utcnow(),
            )
            session.add(row)
            migrated += 1
        except Exception as e:
            log.warning(f"Skipping {f.name}: {e}")
            skipped += 1

    log.info(f"Migrated {migrated} mapping profiles to DB ({skipped} duplicates skipped).")


def _migrate_overrides(session):
    from database import Override
    from sqlmodel import select
    from paths import OVERRIDES_DIR

    existing = session.exec(select(Override)).all()
    if existing:
        log.info("override table already populated, skipping migration.")
        return

    overrides_file = OVERRIDES_DIR / "overrides.json"
    if not overrides_file.exists():
        log.info("No overrides.json found, skipping.")
        return

    try:
        data = json.loads(overrides_file.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"Could not read overrides.json: {e}")
        return

    migrated = 0
    for entry in data:
        try:
            row = Override(
                transaction_id=entry["transaction_id"],
                override_from_account=entry.get("override_from_account", ""),
                override_to_account=entry.get("override_to_account", ""),
                override_reason=entry.get("override_reason", entry.get("reason", "")),
                override_by=entry.get("override_by", entry.get("by", "analyst")),
                override_timestamp=_parse_dt(entry.get("override_timestamp", entry.get("timestamp"))) or datetime.utcnow(),
            )
            session.add(row)
            migrated += 1
        except Exception as e:
            log.warning(f"Skipping override entry: {e}")

    log.info(f"Migrated {migrated} overrides to DB.")


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None
