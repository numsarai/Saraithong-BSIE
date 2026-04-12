"""
fund_flow_service.py
--------------------
Cross-account fund flow analysis: inbound/outbound flows, pairwise
transactions, and multi-hop BFS path tracing.
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, and_, or_
from sqlalchemy.orm import Session

from persistence.models import Account, Transaction
from services.account_resolution_service import normalize_account_number

logger = logging.getLogger(__name__)


def _resolve_account_id(session: Session, account: str) -> str | None:
    """Resolve an account number to its DB id."""
    norm = normalize_account_number(account)
    if not norm:
        return None
    row = session.scalars(
        select(Account).where(Account.normalized_account_number == norm)
    ).first()
    return row.id if row else None


def _account_info(session: Session, account_id: str) -> dict[str, Any]:
    """Return display info for an account."""
    row = session.get(Account, account_id)
    if not row:
        return {"id": account_id, "account": "", "name": "", "bank": ""}
    return {
        "id": row.id,
        "account": row.normalized_account_number or "",
        "name": row.account_holder_name or "",
        "bank": row.bank_name or "",
    }


def get_account_flows(session: Session, account: str) -> dict[str, Any]:
    """Get inbound sources and outbound targets for an account.

    Returns aggregated flows grouped by counterparty.
    """
    account_id = _resolve_account_id(session, account)
    if not account_id:
        return {"account": account, "inbound": [], "outbound": [], "total_in": 0, "total_out": 0}

    txns = session.scalars(
        select(Transaction).where(Transaction.account_id == account_id)
    ).all()

    inbound: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0, "name": "", "dates": []})
    outbound: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "count": 0, "name": "", "dates": []})

    for txn in txns:
        cp = txn.counterparty_account_normalized or ""
        if not cp:
            continue
        amount = abs(float(txn.amount or 0))
        direction = str(txn.direction or "").upper()
        cp_name = txn.counterparty_name_normalized or txn.counterparty_name_raw or ""
        date_str = str(txn.posted_date or txn.transaction_datetime or "")[:10]

        if direction == "IN":
            inbound[cp]["total"] += amount
            inbound[cp]["count"] += 1
            if cp_name:
                inbound[cp]["name"] = cp_name
            if date_str:
                inbound[cp]["dates"].append(date_str)
        elif direction == "OUT":
            outbound[cp]["total"] += amount
            outbound[cp]["count"] += 1
            if cp_name:
                outbound[cp]["name"] = cp_name
            if date_str:
                outbound[cp]["dates"].append(date_str)

    def _format_flows(flows: dict) -> list[dict]:
        result = []
        for cp_acct, data in sorted(flows.items(), key=lambda x: -x[1]["total"]):
            dates = sorted(set(data["dates"]))
            result.append({
                "account": cp_acct,
                "name": data["name"],
                "total": round(data["total"], 2),
                "count": data["count"],
                "date_range": f"{dates[0]} to {dates[-1]}" if len(dates) >= 2 else (dates[0] if dates else ""),
            })
        return result

    info = _account_info(session, account_id)
    in_list = _format_flows(inbound)
    out_list = _format_flows(outbound)

    return {
        "account": info["account"],
        "name": info["name"],
        "bank": info["bank"],
        "inbound": in_list,
        "outbound": out_list,
        "total_in": round(sum(f["total"] for f in in_list), 2),
        "total_out": round(sum(f["total"] for f in out_list), 2),
        "inbound_count": len(in_list),
        "outbound_count": len(out_list),
    }


def get_matched_transactions(
    session: Session,
    account_a: str,
    account_b: str,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Get all transactions between two specific accounts."""
    norm_a = normalize_account_number(account_a)
    norm_b = normalize_account_number(account_b)
    if not norm_a or not norm_b:
        return []

    acct_a = session.scalars(select(Account).where(Account.normalized_account_number == norm_a)).first()
    if not acct_a:
        return []

    # Find transactions from A where counterparty is B
    txns = session.scalars(
        select(Transaction)
        .where(
            Transaction.account_id == acct_a.id,
            Transaction.counterparty_account_normalized == norm_b,
        )
        .order_by(Transaction.transaction_datetime.asc())
        .limit(limit)
    ).all()

    return [
        {
            "id": txn.id,
            "date": str(txn.posted_date or txn.transaction_datetime or "")[:10],
            "amount": float(txn.amount or 0),
            "direction": txn.direction or "",
            "description": txn.description_normalized or txn.description_raw or "",
            "transaction_type": txn.transaction_type or "",
            "reference_no": txn.reference_no or "",
            "counterparty_name": txn.counterparty_name_normalized or "",
        }
        for txn in txns
    ]


def trace_fund_path(
    session: Session,
    from_account: str,
    to_account: str,
    *,
    max_hops: int = 4,
) -> dict[str, Any]:
    """BFS path tracing from one account to another through counterparty links.

    Finds paths where money flows: from_account → intermediate → ... → to_account
    by following OUT transactions' counterparty accounts.
    """
    norm_from = normalize_account_number(from_account)
    norm_to = normalize_account_number(to_account)
    if not norm_from or not norm_to:
        return {"found": False, "paths": [], "from_account": from_account, "to_account": to_account}
    if norm_from == norm_to:
        return {"found": True, "paths": [{"hops": [norm_from], "amounts": [], "total": 0}],
                "from_account": norm_from, "to_account": norm_to}

    # Build adjacency from transaction data: account → set of counterparty accounts (outbound)
    # Only consider accounts that exist in DB for traversal
    all_accounts = {
        row.normalized_account_number: row.id
        for row in session.scalars(select(Account)).all()
        if row.normalized_account_number
    }

    # Build outbound edges: for each account, find unique counterparties from OUT transactions
    adjacency: dict[str, dict[str, dict]] = defaultdict(dict)  # from → {to → {total, count}}

    for acct_num, acct_id in all_accounts.items():
        out_txns = session.execute(
            select(
                Transaction.counterparty_account_normalized,
                func.sum(func.abs(Transaction.amount)).label("total"),
                func.count().label("cnt"),
            )
            .where(
                Transaction.account_id == acct_id,
                Transaction.direction == "OUT",
                Transaction.counterparty_account_normalized.isnot(None),
                Transaction.counterparty_account_normalized != "",
            )
            .group_by(Transaction.counterparty_account_normalized)
        ).all()

        for row in out_txns:
            cp = row.counterparty_account_normalized
            if cp:
                adjacency[acct_num][cp] = {"total": float(row.total or 0), "count": int(row.cnt or 0)}

    # BFS
    queue: deque[list[str]] = deque([[norm_from]])
    visited: set[str] = {norm_from}
    found_paths: list[dict] = []

    while queue:
        path = queue.popleft()
        if len(path) > max_hops + 1:
            continue

        current = path[-1]
        neighbors = adjacency.get(current, {})

        for neighbor, flow_data in neighbors.items():
            if neighbor == norm_to:
                full_path = path + [neighbor]
                # Collect amounts along path
                amounts = []
                for i in range(len(full_path) - 1):
                    edge = adjacency.get(full_path[i], {}).get(full_path[i + 1], {})
                    amounts.append({
                        "from": full_path[i],
                        "to": full_path[i + 1],
                        "total": edge.get("total", 0),
                        "count": edge.get("count", 0),
                    })
                found_paths.append({
                    "hops": full_path,
                    "hop_count": len(full_path) - 1,
                    "amounts": amounts,
                    "min_flow": min(a["total"] for a in amounts) if amounts else 0,
                })
                continue

            if neighbor not in visited and len(path) < max_hops + 1:
                visited.add(neighbor)
                queue.append(path + [neighbor])

    # Sort by fewest hops, then highest minimum flow
    found_paths.sort(key=lambda p: (p["hop_count"], -p["min_flow"]))

    return {
        "found": len(found_paths) > 0,
        "path_count": len(found_paths),
        "paths": found_paths[:20],  # Limit to top 20 paths
        "from_account": norm_from,
        "to_account": norm_to,
        "max_hops": max_hops,
    }
