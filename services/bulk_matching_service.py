"""
bulk_matching_service.py
------------------------
Cross-account bulk transaction matching — finds paired transactions
across multiple accounts simultaneously.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from persistence.models import Account, Transaction
from services.account_resolution_service import normalize_account_number


def bulk_cross_match(
    session: Session,
    accounts: list[str] | None = None,
    *,
    date_from: str = "",
    date_to: str = "",
    amount_tolerance: float = 0.01,
    time_window_hours: int = 24,
    limit: int = 500,
) -> dict[str, Any]:
    """Match transactions across multiple accounts.

    Finds pairs where:
    - Account A sends amount X → counterparty B
    - Account B receives ~amount X from counterparty A
    - Within time_window_hours of each other
    """
    # Resolve accounts
    account_map: dict[str, str] = {}  # normalized_number → account_id
    if accounts:
        for acct_num in accounts:
            norm = normalize_account_number(acct_num)
            if not norm:
                continue
            row = session.scalars(select(Account).where(Account.normalized_account_number == norm)).first()
            if row:
                account_map[norm] = row.id
    else:
        # All accounts
        for row in session.scalars(select(Account)).all():
            if row.normalized_account_number:
                account_map[row.normalized_account_number] = row.id

    if len(account_map) < 2:
        return {"matched_pairs": [], "total_pairs": 0, "accounts_checked": len(account_map)}

    # Load outbound transactions indexed by counterparty
    outbound: dict[str, list[dict]] = {}  # counterparty_account → [txn_data]

    for acct_num, acct_id in account_map.items():
        q = select(Transaction).where(
            Transaction.account_id == acct_id,
            Transaction.direction == "OUT",
            Transaction.counterparty_account_normalized.isnot(None),
            Transaction.counterparty_account_normalized != "",
        )
        if date_from:
            try:
                q = q.where(Transaction.transaction_datetime >= datetime.fromisoformat(date_from))
            except ValueError:
                pass
        if date_to:
            try:
                q = q.where(Transaction.transaction_datetime <= datetime.fromisoformat(date_to + "T23:59:59"))
            except ValueError:
                pass

        for txn in session.scalars(q).all():
            cp = txn.counterparty_account_normalized
            if cp and cp in account_map:  # Counterparty is also a known account
                outbound.setdefault(cp, []).append({
                    "id": txn.id,
                    "source_account": acct_num,
                    "source_account_id": acct_id,
                    "amount": abs(float(txn.amount)),
                    "datetime": txn.transaction_datetime,
                    "date": str(txn.posted_date or txn.transaction_datetime or "")[:10],
                    "description": txn.description_normalized or "",
                    "reference": txn.reference_no or "",
                    "counterparty": cp,
                })

    # Match: for each outbound to a known account, find inbound in that account
    matched_pairs: list[dict] = []
    matched_txn_ids: set[str] = set()

    for target_acct, out_txns in outbound.items():
        target_id = account_map.get(target_acct)
        if not target_id:
            continue

        # Load inbound for target account
        in_txns = session.scalars(
            select(Transaction).where(
                Transaction.account_id == target_id,
                Transaction.direction == "IN",
            )
        ).all()

        in_index: list[dict] = [
            {
                "id": t.id,
                "amount": abs(float(t.amount)),
                "datetime": t.transaction_datetime,
                "counterparty": t.counterparty_account_normalized or "",
                "description": t.description_normalized or "",
            }
            for t in in_txns
        ]

        for out_txn in out_txns:
            if out_txn["id"] in matched_txn_ids:
                continue

            for in_txn in in_index:
                if in_txn["id"] in matched_txn_ids:
                    continue
                # Check amount match
                if abs(out_txn["amount"] - in_txn["amount"]) > amount_tolerance * max(out_txn["amount"], 1):
                    continue
                # Check time proximity
                if out_txn["datetime"] and in_txn["datetime"]:
                    delta = abs((out_txn["datetime"] - in_txn["datetime"]).total_seconds())
                    if delta > time_window_hours * 3600:
                        continue
                    time_confidence = max(0.5, 1.0 - delta / (time_window_hours * 3600))
                else:
                    time_confidence = 0.5

                # Check counterparty match
                cp_match = in_txn["counterparty"] == out_txn["source_account"]
                confidence = round(0.7 * time_confidence + (0.3 if cp_match else 0.0), 3)

                matched_pairs.append({
                    "out_txn_id": out_txn["id"],
                    "in_txn_id": in_txn["id"],
                    "from_account": out_txn["source_account"],
                    "to_account": target_acct,
                    "amount": out_txn["amount"],
                    "out_date": out_txn["date"],
                    "in_date": str(in_txn["datetime"] or "")[:10],
                    "confidence": confidence,
                    "counterparty_confirmed": cp_match,
                    "out_description": out_txn["description"][:50],
                    "in_description": in_txn["description"][:50],
                })
                matched_txn_ids.add(out_txn["id"])
                matched_txn_ids.add(in_txn["id"])
                break  # One match per outbound

            if len(matched_pairs) >= limit:
                break
        if len(matched_pairs) >= limit:
            break

    matched_pairs.sort(key=lambda p: (-p["confidence"], -p["amount"]))

    return {
        "matched_pairs": matched_pairs[:limit],
        "total_pairs": len(matched_pairs),
        "accounts_checked": len(account_map),
    }
