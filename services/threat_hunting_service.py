"""
threat_hunting_service.py
-------------------------
Advanced financial crime detection patterns beyond graph_rules.
Implements AML/CFT threat hunting inspired by FATF typologies.

Patterns:
- Smurfing (structuring): breaking large amounts into small chunks
- Layering: rapid movement through multiple accounts
- Integration: funds consolidating into legitimate-looking patterns
- Rapid movement: funds entering and leaving within short window
- Dormant activation: sudden activity on inactive accounts
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from persistence.models import Account, Transaction
from services.account_resolution_service import normalize_account_number


def run_threat_hunt(
    session: Session,
    account: str = "",
    *,
    patterns: list[str] | None = None,
) -> dict[str, Any]:
    """Run all threat hunting patterns on an account or all accounts."""
    norm = normalize_account_number(account) if account else ""

    if norm:
        acct = session.scalars(select(Account).where(Account.normalized_account_number == norm)).first()
        if not acct:
            return {"account": account, "findings": [], "error": "Account not found"}
        txns = session.scalars(
            select(Transaction).where(Transaction.account_id == acct.id)
            .order_by(Transaction.transaction_datetime.asc())
        ).all()
    else:
        txns = session.scalars(
            select(Transaction).order_by(Transaction.transaction_datetime.asc()).limit(50000)
        ).all()

    if not txns:
        return {"account": norm, "findings": [], "total": 0}

    enabled = set(patterns) if patterns else {"smurfing", "layering", "rapid_movement", "dormant_activation", "round_tripping"}

    findings: list[dict[str, Any]] = []

    if "smurfing" in enabled:
        findings.extend(_detect_smurfing(txns))
    if "layering" in enabled:
        findings.extend(_detect_layering(txns))
    if "rapid_movement" in enabled:
        findings.extend(_detect_rapid_movement(txns))
    if "dormant_activation" in enabled:
        findings.extend(_detect_dormant_activation(txns))
    if "round_tripping" in enabled:
        findings.extend(_detect_round_tripping(txns))

    findings.sort(key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(f.get("severity", "low"), 99))

    return {
        "account": norm or "ALL",
        "findings": findings,
        "finding_count": len(findings),
        "transaction_count": len(txns),
        "patterns_checked": list(enabled),
    }


def _detect_smurfing(txns: list) -> list[dict]:
    """Detect structuring/smurfing — multiple deposits just below reporting threshold.

    FATF typology: Breaking large amounts into smaller deposits to avoid
    currency transaction reports (CTR). Thai threshold: 200,000 THB.
    """
    findings = []
    threshold = 200_000
    window_days = 3

    # Group by date windows
    for i, txn in enumerate(txns):
        if txn.direction != "IN" or not txn.transaction_datetime:
            continue
        amount = abs(float(txn.amount))
        if amount >= threshold or amount < threshold * 0.5:
            continue

        # Find nearby deposits within window
        window_txns = []
        for j in range(max(0, i - 20), min(len(txns), i + 20)):
            other = txns[j]
            if other.direction != "IN" or not other.transaction_datetime:
                continue
            delta = abs((txn.transaction_datetime - other.transaction_datetime).total_seconds())
            if delta <= window_days * 86400:
                window_txns.append(other)

        window_total = sum(abs(float(t.amount)) for t in window_txns)
        if len(window_txns) >= 3 and window_total >= threshold:
            findings.append({
                "pattern": "smurfing",
                "severity": "high",
                "title": "Smurfing / Structuring Detected",
                "title_th": "ตรวจพบการแบ่งรายการ (Smurfing)",
                "description": f"พบ {len(window_txns)} รายการฝากเงินรวม {window_total:,.0f} บาท ภายใน {window_days} วัน แต่ละรายการต่ำกว่า {threshold:,} บาท — อาจเป็นการหลีกเลี่ยง CTR",
                "total_amount": round(window_total, 2),
                "transaction_count": len(window_txns),
                "date": str(txn.transaction_datetime)[:10],
            })
            break  # One finding per account is enough

    return findings


def _detect_layering(txns: list) -> list[dict]:
    """Detect layering — rapid movement through many counterparties.

    FATF typology: Moving funds quickly through multiple accounts to
    obscure the audit trail. Look for high counterparty turnover.
    """
    findings = []

    # Count unique counterparties per day
    daily_cps: dict[str, set] = defaultdict(set)
    daily_amounts: dict[str, float] = defaultdict(float)
    for txn in txns:
        date = str(txn.posted_date or txn.transaction_datetime or "")[:10]
        cp = txn.counterparty_account_normalized or ""
        if date and cp:
            daily_cps[date].add(cp)
            daily_amounts[date] += abs(float(txn.amount))

    high_turnover_days = [
        (d, len(cps), daily_amounts[d])
        for d, cps in daily_cps.items()
        if len(cps) >= 8 and daily_amounts[d] >= 50_000
    ]

    if high_turnover_days:
        worst = max(high_turnover_days, key=lambda x: x[1])
        findings.append({
            "pattern": "layering",
            "severity": "high",
            "title": "Layering Pattern Detected",
            "title_th": "ตรวจพบรูปแบบ Layering",
            "description": f"พบวันที่มีธุรกรรมกับคู่สัญญาจำนวนมาก: {worst[0]} มี {worst[1]} คู่สัญญา ยอดรวม {worst[2]:,.0f} บาท — อาจเป็นการซ่อนเส้นทางเงิน",
            "worst_day": worst[0],
            "counterparty_count": worst[1],
            "total_amount": round(worst[2], 2),
            "high_turnover_days": len(high_turnover_days),
        })

    return findings


def _detect_rapid_movement(txns: list) -> list[dict]:
    """Detect rapid in-out — funds entering and leaving within hours.

    FATF typology: Pass-through accounts where money enters and exits
    the same day or within a few hours.
    """
    findings = []

    for i, txn_in in enumerate(txns):
        if txn_in.direction != "IN" or not txn_in.transaction_datetime:
            continue
        amount_in = abs(float(txn_in.amount))
        if amount_in < 10_000:
            continue

        # Look for matching OUT within 4 hours
        for j in range(i + 1, min(len(txns), i + 50)):
            txn_out = txns[j]
            if txn_out.direction != "OUT" or not txn_out.transaction_datetime:
                continue
            amount_out = abs(float(txn_out.amount))
            time_diff = (txn_out.transaction_datetime - txn_in.transaction_datetime).total_seconds()
            if time_diff < 0 or time_diff > 14400:  # 4 hours
                continue
            # Amount similarity (within 10%)
            if abs(amount_in - amount_out) / max(amount_in, 1) <= 0.1:
                findings.append({
                    "pattern": "rapid_movement",
                    "severity": "medium",
                    "title": "Rapid Fund Movement",
                    "title_th": "เงินเข้า-ออกรวดเร็ว",
                    "description": f"เงินเข้า {amount_in:,.0f} บาท แล้วออก {amount_out:,.0f} บาท ภายใน {time_diff/3600:.1f} ชั่วโมง — อาจเป็นบัญชีตัวกลาง",
                    "amount_in": round(amount_in, 2),
                    "amount_out": round(amount_out, 2),
                    "time_diff_hours": round(time_diff / 3600, 1),
                    "date": str(txn_in.transaction_datetime)[:10],
                })
                break  # One per IN transaction

        if len(findings) >= 5:
            break

    return findings


def _detect_dormant_activation(txns: list) -> list[dict]:
    """Detect sudden activation of dormant account.

    FATF typology: Account with no activity for extended period
    suddenly becomes very active — may indicate account takeover or laundering.
    """
    findings = []
    if len(txns) < 10:
        return findings

    # Find gaps in activity
    dates = [t.transaction_datetime for t in txns if t.transaction_datetime]
    if len(dates) < 10:
        return findings

    dates.sort()
    for i in range(1, len(dates)):
        gap_days = (dates[i] - dates[i - 1]).days
        if gap_days >= 60:  # 2 months dormant
            # Check post-gap activity
            post_gap = [t for t in txns if t.transaction_datetime and t.transaction_datetime >= dates[i]]
            if len(post_gap) >= 10:
                post_total = sum(abs(float(t.amount)) for t in post_gap[:20])
                findings.append({
                    "pattern": "dormant_activation",
                    "severity": "medium",
                    "title": "Dormant Account Activated",
                    "title_th": "บัญชีหยุดนิ่งกลับมาเคลื่อนไหว",
                    "description": f"บัญชีหยุดนิ่ง {gap_days} วัน แล้วกลับมามีธุรกรรม {len(post_gap)} รายการ ยอดรวม {post_total:,.0f} บาท",
                    "dormant_days": gap_days,
                    "post_gap_transactions": len(post_gap),
                    "post_gap_amount": round(post_total, 2),
                    "reactivation_date": str(dates[i])[:10],
                })
                break

    return findings


def _detect_round_tripping(txns: list) -> list[dict]:
    """Detect round-tripping — money sent out then returned from same source.

    FATF typology: Funds sent to an entity and returned back,
    potentially through a different channel, to create fake business activity.
    """
    findings = []

    # Track out→in pairs per counterparty
    cp_out: dict[str, list] = defaultdict(list)
    cp_in: dict[str, list] = defaultdict(list)

    for txn in txns:
        cp = txn.counterparty_account_normalized or ""
        if not cp:
            continue
        if txn.direction == "OUT":
            cp_out[cp].append(txn)
        elif txn.direction == "IN":
            cp_in[cp].append(txn)

    for cp in set(cp_out) & set(cp_in):
        out_total = sum(abs(float(t.amount)) for t in cp_out[cp])
        in_total = sum(abs(float(t.amount)) for t in cp_in[cp])
        if out_total >= 50_000 and in_total >= 50_000:
            ratio = min(out_total, in_total) / max(out_total, in_total)
            if ratio >= 0.7:  # 70%+ return ratio
                findings.append({
                    "pattern": "round_tripping",
                    "severity": "medium",
                    "title": "Round-Tripping Suspected",
                    "title_th": "สงสัยเงินวนกลับ (Round-Tripping)",
                    "description": f"โอนให้ {cp} รวม {out_total:,.0f} บาท และรับกลับจากบัญชีเดียวกัน {in_total:,.0f} บาท (อัตราคืน {ratio:.0%})",
                    "counterparty": cp,
                    "out_total": round(out_total, 2),
                    "in_total": round(in_total, 2),
                    "return_ratio": round(ratio, 3),
                })

    return findings[:5]  # Limit to top 5
