"""
utils/app_helpers.py
--------------------
Helper functions extracted from app.py to reduce module size and improve
testability.  Every function is importable; the leading underscore has been
dropped so callers use e.g. ``from utils.app_helpers import dispatch_pipeline``.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from core.bank_logo_registry import build_bank_logo_catalog, find_bank_logo_record
from core.override_manager import apply_overrides_to_df
from paths import BUILTIN_CONFIG_DIR, CONFIG_DIR, OUTPUT_DIR
from services.admin_service import get_backup_settings, maybe_run_scheduled_backup
from tasks import run_pipeline_sync

logger = logging.getLogger("bsie.api")


# ---------------------------------------------------------------------------
# Pipeline dispatch
# ---------------------------------------------------------------------------

def dispatch_pipeline(
    job_id: str,
    upload_path_str: str,
    bank_key: str,
    account: str,
    name: str,
    confirmed_mapping: dict,
    *,
    file_id: str = "",
    parser_run_id: str = "",
    operator: str = "analyst",
    header_row: int = 0,
    sheet_name: str = "",
) -> None:
    """Dispatch the pipeline via the serialized job queue (prevents DB lock)."""
    from services.job_queue_service import enqueue_job
    logger.info("Dispatching pipeline via job queue")
    enqueue_job(
        job_id,
        run_pipeline_sync,
        upload_path_str=upload_path_str,
        bank_key=bank_key,
        account=account,
        name=name,
        confirmed_mapping=confirmed_mapping,
        file_id=file_id,
        parser_run_id=parser_run_id,
        operator=operator,
        header_row=header_row,
        sheet_name=sheet_name,
    )


# ---------------------------------------------------------------------------
# Auto-backup helpers
# ---------------------------------------------------------------------------

def auto_backup_poll_seconds() -> float:
    """Return the backup polling interval from the environment (min 15 s)."""
    raw = os.getenv("BSIE_BACKUP_POLL_SECONDS", "60").strip() or "60"
    try:
        return max(15.0, float(raw))
    except ValueError:
        return 60.0


def run_auto_backup_loop(stop_event: threading.Event) -> None:
    """Continuously check whether a scheduled backup is due."""
    poll_seconds = auto_backup_poll_seconds()
    logger.info("Auto-backup scheduler started (poll=%ss)", poll_seconds)
    while not stop_event.is_set():
        try:
            settings = get_backup_settings()
            backup = maybe_run_scheduled_backup(operator="system")
            if backup:
                logger.info("Scheduled backup created: %s", backup["filename"])
            elif settings.get("enabled"):
                logger.debug("Auto-backup checked; next run not due yet")
        except Exception:
            logger.exception("Scheduled backup run failed")
        stop_event.wait(poll_seconds)
    logger.info("Auto-backup scheduler stopped")


# ---------------------------------------------------------------------------
# Mapping repair / feedback helpers
# ---------------------------------------------------------------------------

def repair_suggested_mapping(
    suggested: dict,
    auto_suggested: dict,
    available_columns: list[str],
) -> dict:
    """Keep profile-assisted mappings deterministic and debit/credit-safe."""
    repaired = {
        field: (value if value in available_columns else None)
        for field, value in (suggested or {}).items()
    }
    auto_suggested = auto_suggested or {}

    if repaired.get("amount") and repaired.get("direction_marker"):
        repaired["debit"] = None
        repaired["credit"] = None

    if repaired.get("debit") and repaired.get("credit"):
        repaired["amount"] = None
        repaired["direction_marker"] = None

    if repaired.get("amount") and repaired.get("balance") and repaired["amount"] == repaired["balance"]:
        repaired["amount"] = None

    if not repaired.get("balance") and auto_suggested.get("balance") in available_columns:
        repaired["balance"] = auto_suggested.get("balance")

    for field, value in auto_suggested.items():
        if field == "amount" and repaired.get("debit") and repaired.get("credit"):
            continue
        if field == "direction_marker" and (repaired.get("debit") or repaired.get("credit")):
            continue
        if field in {"debit", "credit"} and repaired.get("amount") and repaired.get("direction_marker"):
            continue
        if field not in repaired or repaired.get(field) is None:
            repaired[field] = value if value in available_columns else None

    if repaired.get("amount") and repaired.get("direction_marker"):
        repaired["debit"] = None
        repaired["credit"] = None

    return repaired


def normalize_feedback_text(value: object) -> str:
    """Lowercase-strip a value for feedback comparison."""
    return str(value or "").strip().lower()


def normalized_mapping_snapshot(mapping: dict | None) -> dict[str, str]:
    """Return a cleaned {str: str} copy of a mapping dict."""
    if not isinstance(mapping, dict):
        return {}
    snapshot: dict[str, str] = {}
    for key, value in mapping.items():
        text_key = str(key or "").strip()
        if not text_key:
            continue
        text_value = str(value or "").strip()
        snapshot[text_key] = text_value
    return snapshot


def detected_bank_key(value: object) -> str:
    """Extract a normalised bank key from a detection result or plain string."""
    if isinstance(value, dict):
        for key in ("config_key", "key", "bank_key"):
            candidate = normalize_feedback_text(value.get(key))
            if candidate:
                return candidate
        return normalize_feedback_text(value.get("bank"))
    return normalize_feedback_text(value)


def bank_feedback_status(chosen_bank: str, detected_bank: str) -> str:
    """Classify the user's bank selection relative to auto-detection."""
    chosen = normalize_feedback_text(chosen_bank)
    detected = normalize_feedback_text(detected_bank)
    if not detected:
        return "accepted"
    return "confirmed" if chosen == detected else "corrected"


def mapping_feedback_status(confirmed_mapping: dict, suggested_mapping: dict) -> str:
    """Classify the user's mapping confirmation relative to the suggestion."""
    suggested_snapshot = normalized_mapping_snapshot(suggested_mapping)
    if not suggested_snapshot:
        return "accepted"

    confirmed_snapshot = normalized_mapping_snapshot(confirmed_mapping)
    all_keys = sorted(set(confirmed_snapshot) | set(suggested_snapshot))
    for key in all_keys:
        confirmed_value = confirmed_snapshot.get(key, "")
        suggested_value = suggested_snapshot.get(key, "")
        if confirmed_value != suggested_value and (confirmed_value or suggested_value):
            return "corrected"
    return "confirmed"


def usage_increment_for_feedback(status: str) -> int:
    """Return the profile usage bump appropriate for the feedback status."""
    return 2 if status == "corrected" else 1


def feedback_mode(bank_feedback: str, mapping_feedback: str) -> str:
    """Summarise bank + mapping feedback into a single mode label."""
    statuses = {bank_feedback, mapping_feedback}
    if "corrected" in statuses:
        return "corrected"
    if "confirmed" in statuses:
        return "confirmed"
    return "accepted"


def feedback_message(bank_feedback: str, mapping_feedback: str) -> str:
    """Return a user-facing message describing what was saved."""
    mode = feedback_mode(bank_feedback, mapping_feedback)
    if mode == "corrected":
        return "Saved and reinforced your correction"
    if mode == "confirmed":
        return "Saved and reinforced the confirmed pattern"
    return "Mapping saved"


def masked_database_url(url: str) -> str:
    """Hide database credentials in status responses."""
    if "://" not in url or "@" not in url:
        return url
    prefix, rest = url.split("://", 1)
    credentials, suffix = rest.split("@", 1)
    username = credentials.split(":", 1)[0]
    return f"{prefix}://{username}:***@{suffix}"


# ---------------------------------------------------------------------------
# Bank config helpers
# ---------------------------------------------------------------------------

def collect_bank_configs() -> Dict[str, Dict]:
    """Scan builtin and custom config directories for bank JSON files."""
    banks: Dict[str, Dict] = {}
    for config_dir, template_source in ((BUILTIN_CONFIG_DIR, "builtin"), (CONFIG_DIR, "custom")):
        if not config_dir.exists():
            continue
        for f in sorted(config_dir.glob("*.json")):
            try:
                cfg = json.loads(f.read_text(encoding="utf-8"))
                banks[f.stem] = {
                    "key": f.stem,
                    "name": cfg.get("bank_name", f.stem.upper()),
                    "template_source": template_source,
                    "is_builtin": template_source == "builtin",
                }
            except Exception:
                logger.debug("Skipping malformed bank config: %s", f)
    return banks


def get_banks() -> List[Dict]:
    """Return a sorted list of bank metadata enriched with logo info."""
    banks = []
    for meta in collect_bank_configs().values():
        bank = find_bank_logo_record(
            str(meta.get("key") or ""),
            display_name=str(meta.get("name") or ""),
            has_template=True,
            template_source=str(meta.get("template_source") or "config"),
        )
        bank["is_builtin"] = bool(meta.get("is_builtin"))
        banks.append(bank)
    return sorted(banks, key=lambda b: str(b.get("name") or ""))


def get_bank_logo_catalog() -> List[Dict]:
    """Build the full bank-logo catalog from all known configs."""
    return build_bank_logo_catalog(collect_bank_configs().values())


def builtin_bank_keys() -> set[str]:
    """Return the set of lowercase keys for built-in bank templates."""
    return {
        str(key).strip().lower()
        for key, meta in collect_bank_configs().items()
        if meta.get("is_builtin")
    }


# ---------------------------------------------------------------------------
# Graph filter helper
# ---------------------------------------------------------------------------

def graph_filter_payload(
    *,
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
) -> dict:
    """Assemble the filter dict used by graph query endpoints."""
    return {
        "q": q,
        "account": account,
        "counterparty": counterparty,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "date_from": date_from,
        "date_to": date_to,
        "bank": bank,
        "reference_no": reference_no,
        "transaction_type": transaction_type,
        "duplicate_status": duplicate_status,
        "review_status": review_status,
        "match_status": match_status,
        "file_id": file_id,
        "parser_run_id": parser_run_id,
    }


# ---------------------------------------------------------------------------
# Override CSV reapplication
# ---------------------------------------------------------------------------

def reapply_overrides_to_csv(changed_txn_id: str, account_number: str = "") -> None:
    """Re-run override application on all account CSVs that contain the transaction."""
    for acct_dir in OUTPUT_DIR.iterdir():
        if not acct_dir.is_dir():
            continue
        if account_number and acct_dir.name != "".join(c for c in account_number if c.isdigit()):
            continue
        txn_csv = acct_dir / "processed" / "transactions.csv"
        if not txn_csv.exists():
            continue
        try:
            df = pd.read_csv(txn_csv, dtype=str, encoding="utf-8-sig").fillna("")
            if changed_txn_id not in df.get("transaction_id", pd.Series()).values:
                continue
            df = apply_overrides_to_df(df, account_number=acct_dir.name)
            df.to_csv(txn_csv, index=False, encoding="utf-8-sig")
        except Exception as e:
            logger.warning(f"Could not reapply overrides to {txn_csv}: {e}")
