from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from utils.text_utils import normalize_text


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def mapping_profile_version(mapping: dict[str, Any]) -> str:
    return hashlib.sha256(_stable_json(mapping).encode("utf-8")).hexdigest()[:16]


def batch_fingerprint(payload: dict[str, Any]) -> str:
    parts = [
        str(payload.get("account_number", "") or ""),
        str(payload.get("statement_start_date", "") or ""),
        str(payload.get("statement_end_date", "") or ""),
        str(payload.get("transaction_count", "") or ""),
        str(payload.get("opening_balance", "") or ""),
        str(payload.get("closing_balance", "") or ""),
        str(payload.get("debit_total", "") or ""),
        str(payload.get("credit_total", "") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def transaction_fingerprint(payload: dict[str, Any]) -> str:
    parts = [
        str(payload.get("account_id", "") or ""),
        str(payload.get("transaction_datetime", "") or ""),
        str(payload.get("amount", "") or ""),
        str(payload.get("direction", "") or ""),
        normalize_text(payload.get("description_normalized", "") or "").lower(),
        str(payload.get("reference_no", "") or "").strip(),
        str(payload.get("counterparty_account_normalized", "") or "").strip(),
        str(payload.get("balance_after", "") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, "", "nan", "None"):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return None


def parse_datetime(date_value: Any, time_value: Any = "") -> datetime | None:
    text = str(date_value or "").strip()
    if not text:
        return None

    time_text = str(time_value or "").strip()
    candidate = f"{text} {time_text}".strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None
