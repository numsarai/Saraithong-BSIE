"""
insights_service.py
-------------------
Auto-generate investigation insights from processed transaction data.
Detects: structuring, unusual timing, recurring patterns, high-value flows.
Inspired by CSV Data Summarizer skill pattern.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from persistence.models import Account, Alert, Transaction
from services.account_resolution_service import normalize_account_number


def generate_account_insights(session: Session, account: str) -> dict[str, Any]:
    """Generate investigation insights for an account."""
    norm = normalize_account_number(account)
    if not norm:
        return {"account": account, "insights": [], "summary": "No data"}

    acct = session.scalars(select(Account).where(Account.normalized_account_number == norm)).first()
    if not acct:
        return {"account": account, "insights": [], "summary": "Account not found"}

    txns = session.scalars(
        select(Transaction).where(Transaction.account_id == acct.id).order_by(Transaction.transaction_datetime.asc())
    ).all()

    if not txns:
        return {"account": norm, "insights": [], "summary": "No transactions"}

    insights: list[dict[str, Any]] = []

    # 1. Structuring detection — amounts just below reporting threshold
    _detect_structuring(txns, insights)

    # 2. Unusual timing — transactions outside business hours
    _detect_unusual_timing(txns, insights)

    # 3. Round amount patterns
    _detect_round_amounts(txns, insights)

    # 4. Recurring patterns — same amount + same counterparty + regular interval
    _detect_recurring(txns, insights)

    # 5. Sudden spikes — volume/amount anomalies
    _detect_spikes(txns, insights)

    # 6. One-way flow — accounts that only send or only receive
    _detect_one_way_flow(txns, insights)

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    insights.sort(key=lambda x: severity_order.get(x.get("severity", "info"), 99))

    # Build summary
    summary_parts = []
    if any(i["severity"] in ("critical", "high") for i in insights):
        summary_parts.append(f"พบสัญญาณผิดปกติ {sum(1 for i in insights if i['severity'] in ('critical', 'high'))} รายการที่ต้องตรวจสอบ")
    summary_parts.append(f"วิเคราะห์จาก {len(txns):,} ธุรกรรม")
    summary_parts.append(f"พบ {len(insights)} ข้อสังเกต")

    return {
        "account": norm,
        "name": acct.account_holder_name or "",
        "insights": insights,
        "insight_count": len(insights),
        "transaction_count": len(txns),
        "summary": " | ".join(summary_parts),
    }


def _detect_structuring(txns: list, insights: list) -> None:
    """Detect potential structuring — amounts just below 200,000 THB (Thai AML threshold)."""
    threshold = 200_000
    margin = 20_000  # 180K-200K range
    suspicious = [t for t in txns if threshold - margin <= abs(float(t.amount)) < threshold]
    if len(suspicious) >= 3:
        insights.append({
            "type": "structuring",
            "severity": "high",
            "title": "Possible Structuring Detected",
            "title_th": "อาจมีการ Structuring",
            "description": f"พบ {len(suspicious)} รายการที่มียอดใกล้เคียง {threshold:,} บาท (ช่วง {threshold-margin:,}-{threshold:,}) — อาจเป็นการแบ่งรายการเพื่อหลีกเลี่ยงการรายงาน",
            "count": len(suspicious),
            "threshold": threshold,
            "transactions": [t.id for t in suspicious[:10]],
        })


def _detect_unusual_timing(txns: list, insights: list) -> None:
    """Detect transactions during unusual hours (midnight to 5am)."""
    night_txns = []
    for t in txns:
        if t.transaction_datetime:
            hour = t.transaction_datetime.hour
            if 0 <= hour < 5:
                night_txns.append(t)

    if len(night_txns) >= 5:
        pct = len(night_txns) / len(txns) * 100
        insights.append({
            "type": "unusual_timing",
            "severity": "medium",
            "title": "Unusual Night Activity",
            "title_th": "ธุรกรรมช่วงกลางคืนผิดปกติ",
            "description": f"พบ {len(night_txns)} รายการ ({pct:.1f}%) ในช่วงเวลา 00:00-05:00 — ผิดปกติสำหรับบัญชีทั่วไป",
            "count": len(night_txns),
            "percentage": round(pct, 1),
        })


def _detect_round_amounts(txns: list, insights: list) -> None:
    """Detect high proportion of round amounts (multiples of 1000)."""
    round_txns = [t for t in txns if abs(float(t.amount)) >= 1000 and float(t.amount) % 1000 == 0]
    if len(txns) >= 20:
        pct = len(round_txns) / len(txns) * 100
        if pct > 70:
            insights.append({
                "type": "round_amounts",
                "severity": "medium",
                "title": "High Round Amount Proportion",
                "title_th": "สัดส่วนยอดกลมสูงผิดปกติ",
                "description": f"{pct:.0f}% ของรายการเป็นยอดกลม (หาร 1,000 ลงตัว) — อาจบ่งชี้ธุรกรรมที่ไม่ใช่การซื้อขายสินค้าจริง",
                "count": len(round_txns),
                "percentage": round(pct, 1),
            })


def _detect_recurring(txns: list, insights: list) -> None:
    """Detect recurring transactions — same amount + same counterparty."""
    patterns: dict[str, list] = defaultdict(list)
    for t in txns:
        cp = t.counterparty_account_normalized or ""
        if not cp:
            continue
        key = f"{cp}:{abs(float(t.amount)):.2f}"
        patterns[key].append(t)

    for key, group in patterns.items():
        if len(group) >= 5:
            cp, amount = key.rsplit(":", 1)
            insights.append({
                "type": "recurring_pattern",
                "severity": "low",
                "title": "Recurring Transaction Pattern",
                "title_th": "รูปแบบธุรกรรมซ้ำ",
                "description": f"พบ {len(group)} รายการยอด {float(amount):,.2f} บาท กับบัญชี {cp} — อาจเป็นค่างวดหรือรายจ่ายประจำ",
                "count": len(group),
                "counterparty": cp,
                "amount": float(amount),
            })


def _detect_spikes(txns: list, insights: list) -> None:
    """Detect sudden volume spikes — days with unusually many transactions."""
    daily_counts: dict[str, int] = Counter()
    for t in txns:
        date = str(t.posted_date or t.transaction_datetime or "")[:10]
        if date:
            daily_counts[date] += 1

    if len(daily_counts) < 7:
        return

    avg = sum(daily_counts.values()) / len(daily_counts)
    spike_days = [(d, c) for d, c in daily_counts.items() if c > avg * 3 and c >= 10]
    if spike_days:
        insights.append({
            "type": "volume_spike",
            "severity": "medium",
            "title": "Transaction Volume Spikes",
            "title_th": "ปริมาณธุรกรรมพุ่งสูง",
            "description": f"พบ {len(spike_days)} วันที่มีธุรกรรมมากกว่าค่าเฉลี่ย 3 เท่า (เฉลี่ย {avg:.0f} รายการ/วัน)",
            "spike_days": [{"date": d, "count": c} for d, c in sorted(spike_days, key=lambda x: -x[1])[:5]],
            "average_daily": round(avg, 1),
        })


def _detect_one_way_flow(txns: list, insights: list) -> None:
    """Detect counterparties with only one-way flow (send only or receive only)."""
    cp_directions: dict[str, set] = defaultdict(set)
    cp_totals: dict[str, float] = defaultdict(float)
    for t in txns:
        cp = t.counterparty_account_normalized or ""
        if not cp:
            continue
        cp_directions[cp].add(t.direction)
        cp_totals[cp] += abs(float(t.amount))

    # High-value one-way counterparties
    one_way = [
        (cp, dirs, cp_totals[cp])
        for cp, dirs in cp_directions.items()
        if len(dirs) == 1 and cp_totals[cp] >= 100_000
    ]

    if len(one_way) >= 3:
        send_only = sum(1 for _, dirs, _ in one_way if "OUT" in dirs)
        recv_only = sum(1 for _, dirs, _ in one_way if "IN" in dirs)
        insights.append({
            "type": "one_way_flow",
            "severity": "low",
            "title": "One-Way Flow Counterparties",
            "title_th": "คู่สัญญาทางเดียว",
            "description": f"พบ {len(one_way)} คู่สัญญายอดสูง (≥100K) ที่มีแค่ทิศทางเดียว — {send_only} ส่งอย่างเดียว, {recv_only} รับอย่างเดียว",
            "count": len(one_way),
            "send_only": send_only,
            "receive_only": recv_only,
        })
