"""
period_comparison_service.py
----------------------------
Compare financial metrics between two time periods for an account.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import func, select, and_
from sqlalchemy.orm import Session

from persistence.models import Account, Transaction
from services.account_resolution_service import normalize_account_number


def _period_stats(session: Session, account_id: str, start: date, end: date) -> dict[str, Any]:
    """Compute aggregate stats for a date range."""
    base = select(Transaction).where(
        Transaction.account_id == account_id,
        Transaction.transaction_datetime >= datetime.combine(start, time.min),
        Transaction.transaction_datetime <= datetime.combine(end, time.max),
    )

    txns = session.scalars(base).all()
    if not txns:
        return {"total_in": 0, "total_out": 0, "txn_count": 0, "avg_amount": 0, "max_amount": 0, "unique_counterparties": 0}

    amounts = [abs(float(t.amount)) for t in txns]
    total_in = sum(abs(float(t.amount)) for t in txns if t.direction == "IN")
    total_out = sum(abs(float(t.amount)) for t in txns if t.direction == "OUT")
    cps = {t.counterparty_account_normalized for t in txns if t.counterparty_account_normalized}

    return {
        "total_in": round(total_in, 2),
        "total_out": round(total_out, 2),
        "circulation": round(total_in + total_out, 2),
        "txn_count": len(txns),
        "avg_amount": round(sum(amounts) / len(amounts), 2) if amounts else 0,
        "max_amount": round(max(amounts), 2) if amounts else 0,
        "unique_counterparties": len(cps),
        "in_count": sum(1 for t in txns if t.direction == "IN"),
        "out_count": sum(1 for t in txns if t.direction == "OUT"),
    }


def _pct_change(a: float, b: float) -> float | None:
    if a == 0:
        return None
    return round(((b - a) / a) * 100, 1)


def compare_periods(
    session: Session,
    account: str,
    a_from: str,
    a_to: str,
    b_from: str,
    b_to: str,
) -> dict[str, Any]:
    """Compare metrics between two date ranges for an account."""
    norm = normalize_account_number(account)
    if not norm:
        return {"error": "Invalid account"}

    acct = session.scalars(select(Account).where(Account.normalized_account_number == norm)).first()
    if not acct:
        return {"error": "Account not found"}

    try:
        period_a_start = date.fromisoformat(a_from)
        period_a_end = date.fromisoformat(a_to)
        period_b_start = date.fromisoformat(b_from)
        period_b_end = date.fromisoformat(b_to)
    except ValueError:
        return {"error": "Invalid date format (use YYYY-MM-DD)"}

    stats_a = _period_stats(session, acct.id, period_a_start, period_a_end)
    stats_b = _period_stats(session, acct.id, period_b_start, period_b_end)

    changes = {
        "total_in_pct": _pct_change(stats_a["total_in"], stats_b["total_in"]),
        "total_out_pct": _pct_change(stats_a["total_out"], stats_b["total_out"]),
        "circulation_pct": _pct_change(stats_a["circulation"], stats_b["circulation"]),
        "txn_count_pct": _pct_change(stats_a["txn_count"], stats_b["txn_count"]),
        "avg_amount_pct": _pct_change(stats_a["avg_amount"], stats_b["avg_amount"]),
        "counterparty_pct": _pct_change(stats_a["unique_counterparties"], stats_b["unique_counterparties"]),
    }

    return {
        "account": norm,
        "name": acct.account_holder_name or "",
        "bank": acct.bank_name or "",
        "period_a": {"from": a_from, "to": a_to, **stats_a},
        "period_b": {"from": b_from, "to": b_to, **stats_b},
        "changes": changes,
    }
