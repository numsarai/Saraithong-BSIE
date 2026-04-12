"""
regulatory_export_service.py
----------------------------
Generate reports in regulatory formats for Thai agencies:
- STR (Suspicious Transaction Report) for ปปง. (AMLO)
- CTR (Currency Transaction Report) for transactions ≥ 200,000 THB
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from paths import OUTPUT_DIR
from persistence.models import Account, Alert, Transaction
from services.account_resolution_service import normalize_account_number

CTR_THRESHOLD = 200_000  # Thai reporting threshold in THB


def generate_str_report(
    session: Session,
    account: str,
    *,
    reason: str = "",
    analyst: str = "analyst",
) -> dict[str, Any]:
    """Generate Suspicious Transaction Report (STR) data for ปปง./AMLO.

    Returns structured data that can be exported to the agency's format.
    """
    norm = normalize_account_number(account)
    acct = session.scalars(select(Account).where(Account.normalized_account_number == norm)).first()
    if not acct:
        return {"error": "Account not found"}

    txns = session.scalars(
        select(Transaction).where(Transaction.account_id == acct.id)
        .order_by(Transaction.transaction_datetime.asc())
    ).all()

    alerts = session.scalars(
        select(Alert).where(Alert.account_id == acct.id)
    ).all()

    # Compute stats
    total_in = sum(abs(float(t.amount)) for t in txns if t.direction == "IN")
    total_out = sum(abs(float(t.amount)) for t in txns if t.direction == "OUT")
    dates = [str(t.posted_date or t.transaction_datetime or "")[:10] for t in txns if t.posted_date or t.transaction_datetime]

    # Top counterparties
    cp_totals: dict[str, float] = {}
    for t in txns:
        cp = t.counterparty_account_normalized or ""
        if cp:
            cp_totals[cp] = cp_totals.get(cp, 0) + abs(float(t.amount))
    top_cps = sorted(cp_totals.items(), key=lambda x: -x[1])[:20]

    # Suspicious indicators
    indicators = []
    for alert in alerts:
        indicators.append({
            "rule": alert.rule_type,
            "severity": alert.severity,
            "description": alert.summary or "",
        })

    str_data = {
        "report_type": "STR",
        "report_type_th": "รายงานธุรกรรมที่มีเหตุอันควรสงสัย",
        "generated_at": datetime.now().isoformat(),
        "generated_by": analyst,
        "subject": {
            "account_number": norm,
            "account_holder": acct.account_holder_name or "",
            "bank": acct.bank_name or "",
            "account_type": acct.account_type or "savings",
        },
        "period": {
            "from": min(dates) if dates else "",
            "to": max(dates) if dates else "",
        },
        "summary": {
            "total_transactions": len(txns),
            "total_inbound": round(total_in, 2),
            "total_outbound": round(total_out, 2),
            "total_circulation": round(total_in + total_out, 2),
        },
        "suspicious_indicators": indicators,
        "reason_for_suspicion": reason or "Flagged by automated analysis",
        "top_counterparties": [{"account": cp, "total": round(total, 2)} for cp, total in top_cps],
        "high_value_transactions": [
            {
                "date": str(t.posted_date or t.transaction_datetime or "")[:10],
                "amount": float(t.amount),
                "direction": t.direction,
                "counterparty": t.counterparty_account_normalized or "",
                "counterparty_name": t.counterparty_name_normalized or "",
                "description": t.description_normalized or "",
            }
            for t in sorted(txns, key=lambda x: -abs(float(x.amount)))[:50]
        ],
    }

    # Save to file
    output_dir = OUTPUT_DIR / norm
    output_dir.mkdir(parents=True, exist_ok=True)
    str_path = output_dir / f"STR_{norm}_{datetime.now().strftime('%Y%m%d')}.json"
    str_path.write_text(json.dumps(str_data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    return {**str_data, "file_path": str(str_path)}


def generate_ctr_report(
    session: Session,
    account: str = "",
    *,
    date_from: str = "",
    date_to: str = "",
    analyst: str = "analyst",
) -> dict[str, Any]:
    """Generate Currency Transaction Report (CTR) — transactions ≥ 200,000 THB.

    Required by Thai law for cash transactions at or above the threshold.
    """
    query = select(Transaction).where(
        func.abs(Transaction.amount) >= CTR_THRESHOLD,
    ).order_by(Transaction.transaction_datetime.desc())

    if account:
        norm = normalize_account_number(account)
        acct = session.scalars(select(Account).where(Account.normalized_account_number == norm)).first()
        if acct:
            query = query.where(Transaction.account_id == acct.id)

    txns = session.scalars(query.limit(1000)).all()

    ctr_items = [
        {
            "date": str(t.posted_date or t.transaction_datetime or "")[:10],
            "time": str(t.transaction_datetime or "")[11:19] if t.transaction_datetime else "",
            "amount": abs(float(t.amount)),
            "currency": "THB",
            "direction": t.direction,
            "account": t.counterparty_account_normalized or "",
            "account_holder": t.counterparty_name_normalized or "",
            "description": t.description_normalized or "",
            "transaction_type": t.transaction_type or "",
            "reference": t.reference_no or "",
        }
        for t in txns
    ]

    total = sum(item["amount"] for item in ctr_items)

    return {
        "report_type": "CTR",
        "report_type_th": "รายงานธุรกรรมเงินสด (≥200,000 บาท)",
        "generated_at": datetime.now().isoformat(),
        "generated_by": analyst,
        "threshold": CTR_THRESHOLD,
        "transactions": ctr_items,
        "total_count": len(ctr_items),
        "total_amount": round(total, 2),
    }
