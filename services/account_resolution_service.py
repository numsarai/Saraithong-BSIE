from __future__ import annotations

from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core.account_parser import parse_account
from persistence.base import utcnow
from persistence.models import Account
from utils.text_utils import normalize_text


def normalize_account_number(value: object) -> str | None:
    parsed = parse_account(value)
    if parsed["type"] != "ACCOUNT":
        return None
    return parsed["clean"]


def bank_code_from_name(bank_name: str | None) -> str:
    text = normalize_text(bank_name or "").lower()
    return text.replace(" ", "_")[:32] if text else "unknown"


def best_known_account_holder_name(
    session: Session,
    *,
    bank_name: str | None,
    raw_account_number: object,
) -> str | None:
    normalized = normalize_account_number(raw_account_number)
    if not normalized:
        return None

    bank_code = bank_code_from_name(bank_name)
    exact_match = session.scalars(
        select(Account).where(
            Account.bank_code == bank_code,
            Account.normalized_account_number == normalized,
        )
    ).first()
    if exact_match and str(exact_match.account_holder_name or "").strip():
        return str(exact_match.account_holder_name).strip()

    named_matches = session.scalars(
        select(Account).where(
            Account.normalized_account_number == normalized,
            Account.account_holder_name.is_not(None),
            Account.account_holder_name != "",
        ).order_by(Account.last_seen_at.desc())
    ).all()
    distinct_names = []
    seen_names: set[str] = set()
    for match in named_matches:
        name = str(match.account_holder_name or "").strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        distinct_names.append(name)
    if len(distinct_names) == 1:
        return distinct_names[0]

    return None


def resolve_account(
    session: Session,
    *,
    bank_name: str | None,
    raw_account_number: object,
    account_holder_name: str = "",
    account_type: str = "BANK_ACCOUNT",
    confidence_score: float = 1.0,
    notes: str = "",
) -> Account | None:
    normalized = normalize_account_number(raw_account_number)
    if not normalized:
        return None

    bank_code = bank_code_from_name(bank_name)
    resolved_name = str(account_holder_name or "").strip() or best_known_account_holder_name(
        session,
        bank_name=bank_name,
        raw_account_number=raw_account_number,
    )
    existing = session.scalars(
        select(Account).where(
            Account.bank_code == bank_code,
            Account.normalized_account_number == normalized,
        )
    ).first()
    now = utcnow()
    display = normalized

    if existing:
        existing.last_seen_at = now
        existing.source_count = int(existing.source_count or 0) + 1
        existing.raw_account_number = str(raw_account_number or existing.raw_account_number or "")
        existing.display_account_number = display
        if resolved_name and not existing.account_holder_name:
            existing.account_holder_name = resolved_name
        if notes:
            existing.notes = notes
        session.add(existing)
        session.flush()
        return existing

    row = Account(
        bank_name=bank_name or "UNKNOWN",
        bank_code=bank_code,
        raw_account_number=str(raw_account_number or ""),
        normalized_account_number=normalized,
        display_account_number=display,
        account_holder_name=resolved_name or None,
        account_type=account_type,
        first_seen_at=now,
        last_seen_at=now,
        confidence_score=Decimal(str(confidence_score)).quantize(Decimal("0.0001")),
        source_count=1,
        status="active",
        notes=notes or None,
    )
    session.add(row)
    session.flush()
    return row


def find_merge_candidates(session: Session, account_id: str) -> list[dict]:
    account = session.get(Account, account_id)
    if not account or not account.normalized_account_number:
        return []

    candidates = session.scalars(
        select(Account).where(
            Account.id != account_id,
            or_(
                Account.normalized_account_number == account.normalized_account_number,
                Account.account_holder_name == account.account_holder_name,
            ),
        )
    ).all()
    return [
        {
            "account_id": row.id,
            "bank_name": row.bank_name,
            "normalized_account_number": row.normalized_account_number,
            "account_holder_name": row.account_holder_name,
            "status": row.status,
        }
        for row in candidates
    ]
