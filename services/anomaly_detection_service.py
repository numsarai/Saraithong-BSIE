"""
anomaly_detection_service.py
----------------------------
Statistical anomaly detection for financial transactions.
Methods: z-score, IQR, Benford's Law, moving average deviation.
"""
from __future__ import annotations

import math
from collections import Counter
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import Account, Transaction
from services.account_resolution_service import normalize_account_number

BENFORD_EXPECTED = {1: 0.301, 2: 0.176, 3: 0.125, 4: 0.097, 5: 0.079, 6: 0.067, 7: 0.058, 8: 0.051, 9: 0.046}


def _get_amounts(session: Session, account: str) -> list[dict]:
    """Fetch all transaction amounts for an account."""
    norm = normalize_account_number(account)
    if not norm:
        return []
    acct = session.scalars(select(Account).where(Account.normalized_account_number == norm)).first()
    if not acct:
        return []
    txns = session.scalars(
        select(Transaction).where(Transaction.account_id == acct.id).order_by(Transaction.transaction_datetime.asc())
    ).all()
    return [
        {
            "id": t.id,
            "date": str(t.posted_date or t.transaction_datetime or "")[:10],
            "amount": float(t.amount or 0),
            "abs_amount": abs(float(t.amount or 0)),
            "direction": t.direction or "",
            "counterparty": t.counterparty_account_normalized or "",
            "counterparty_name": t.counterparty_name_normalized or "",
            "description": t.description_normalized or "",
            "transaction_type": t.transaction_type or "",
        }
        for t in txns
    ]


def _zscore_detect(txns: list[dict], sigma: float = 2.0) -> tuple[list[dict], dict]:
    """Flag transactions with |amount| deviating > sigma standard deviations from mean."""
    amounts = [t["abs_amount"] for t in txns if t["abs_amount"] > 0]
    if len(amounts) < 3:
        return [], {"mean": 0, "std": 0, "count": len(amounts)}

    mean = sum(amounts) / len(amounts)
    variance = sum((a - mean) ** 2 for a in amounts) / len(amounts)
    std = math.sqrt(variance) if variance > 0 else 0.01

    anomalies = []
    for t in txns:
        if t["abs_amount"] <= 0:
            continue
        z = abs(t["abs_amount"] - mean) / std if std > 0 else 0
        if z >= sigma:
            anomalies.append({**t, "anomaly_score": round(z, 3), "method": "zscore", "reason": f"Z-score {z:.2f} (>{sigma}σ)"})

    return anomalies, {"mean": round(mean, 2), "std": round(std, 2), "count": len(amounts), "sigma": sigma}


def _iqr_detect(txns: list[dict]) -> tuple[list[dict], dict]:
    """Flag outliers using interquartile range method."""
    amounts = sorted(t["abs_amount"] for t in txns if t["abs_amount"] > 0)
    if len(amounts) < 4:
        return [], {"q1": 0, "q3": 0, "iqr": 0, "count": len(amounts)}

    q1 = amounts[len(amounts) // 4]
    q3 = amounts[3 * len(amounts) // 4]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    anomalies = []
    for t in txns:
        a = t["abs_amount"]
        if a <= 0:
            continue
        if a < lower or a > upper:
            score = abs(a - (q1 + q3) / 2) / (iqr if iqr > 0 else 1)
            anomalies.append({**t, "anomaly_score": round(score, 3), "method": "iqr", "reason": f"Outside IQR range [{lower:,.0f} - {upper:,.0f}]"})

    return anomalies, {"q1": round(q1, 2), "q3": round(q3, 2), "iqr": round(iqr, 2), "lower": round(lower, 2), "upper": round(upper, 2), "count": len(amounts)}


def _benford_detect(txns: list[dict]) -> tuple[list[dict], dict]:
    """Check first-digit distribution against Benford's Law."""
    first_digits = []
    for t in txns:
        a = t["abs_amount"]
        if a >= 1:
            digit = int(str(int(a))[0])
            if 1 <= digit <= 9:
                first_digits.append(digit)

    if len(first_digits) < 20:
        return [], {"count": len(first_digits), "message": "Too few transactions for Benford analysis"}

    counts = Counter(first_digits)
    total = len(first_digits)
    observed = {d: counts.get(d, 0) / total for d in range(1, 10)}

    # Chi-squared statistic
    chi_sq = sum(
        ((observed.get(d, 0) - BENFORD_EXPECTED[d]) ** 2) / BENFORD_EXPECTED[d]
        for d in range(1, 10)
    )

    # Find most deviating digits
    deviations = {}
    for d in range(1, 10):
        obs = observed.get(d, 0)
        exp = BENFORD_EXPECTED[d]
        deviations[d] = {"observed": round(obs, 4), "expected": round(exp, 4), "deviation": round(abs(obs - exp), 4)}

    # Flag transactions whose first digit is in a highly deviating group
    suspicious_digits = {d for d, v in deviations.items() if v["deviation"] > 0.05}
    anomalies = []
    for t in txns:
        a = t["abs_amount"]
        if a >= 1:
            digit = int(str(int(a))[0])
            if digit in suspicious_digits:
                anomalies.append({
                    **t, "anomaly_score": round(deviations[digit]["deviation"] * 10, 3),
                    "method": "benford", "reason": f"First digit {digit}: {deviations[digit]['observed']:.1%} vs expected {deviations[digit]['expected']:.1%}"
                })

    conformity = "PASS" if chi_sq < 15.51 else "FAIL"  # chi-sq critical value df=8, p=0.05
    return anomalies, {"chi_squared": round(chi_sq, 3), "conformity": conformity, "digit_distribution": deviations, "count": len(first_digits)}


def _moving_avg_detect(txns: list[dict], window: int = 30, sigma: float = 2.0) -> tuple[list[dict], dict]:
    """Flag transactions deviating from a rolling window average."""
    if len(txns) < window + 5:
        return [], {"window": window, "count": len(txns), "message": "Too few transactions for moving average"}

    anomalies = []
    for i in range(window, len(txns)):
        recent = [t["abs_amount"] for t in txns[i - window:i] if t["abs_amount"] > 0]
        if len(recent) < 5:
            continue
        avg = sum(recent) / len(recent)
        std = math.sqrt(sum((a - avg) ** 2 for a in recent) / len(recent)) if len(recent) > 1 else 1

        current = txns[i]["abs_amount"]
        if current <= 0 or std <= 0:
            continue
        z = abs(current - avg) / std
        if z >= sigma:
            anomalies.append({
                **txns[i], "anomaly_score": round(z, 3),
                "method": "moving_avg", "reason": f"Deviates {z:.1f}σ from {window}-txn average ({avg:,.0f})"
            })

    return anomalies, {"window": window, "sigma": sigma, "count": len(txns)}


def detect_anomalies(
    session: Session,
    account: str,
    *,
    method: str = "zscore",
    sigma: float = 2.0,
    window: int = 30,
) -> dict[str, Any]:
    """Run anomaly detection on an account's transactions."""
    txns = _get_amounts(session, account)
    if not txns:
        return {"account": account, "method": method, "anomalies": [], "stats": {}, "total_transactions": 0}

    if method == "iqr":
        anomalies, stats = _iqr_detect(txns)
    elif method == "benford":
        anomalies, stats = _benford_detect(txns)
    elif method == "moving_avg":
        anomalies, stats = _moving_avg_detect(txns, window=window, sigma=sigma)
    else:
        anomalies, stats = _zscore_detect(txns, sigma=sigma)

    # Sort by score desc
    anomalies.sort(key=lambda a: -a.get("anomaly_score", 0))

    return {
        "account": account,
        "method": method,
        "anomalies": anomalies[:100],  # limit to top 100
        "anomaly_count": len(anomalies),
        "total_transactions": len(txns),
        "stats": stats,
    }
