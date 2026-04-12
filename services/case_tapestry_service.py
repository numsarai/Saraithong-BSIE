"""
case_tapestry_service.py
------------------------
Weave together data from multiple accounts into a unified case narrative.
Combines: transaction flows, alerts, annotations, entity relationships,
and investigation insights into a single case summary.
Inspired by the 'tapestry' skill pattern.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from persistence.models import Account, Alert, GraphAnnotation, Transaction
from services.fund_flow_service import get_account_flows
from services.insights_service import generate_account_insights


def build_case_tapestry(
    session: Session,
    accounts: list[str],
    *,
    case_name: str = "",
    analyst: str = "analyst",
) -> dict[str, Any]:
    """Build a unified case tapestry from multiple accounts.

    Weaves together: account profiles, transaction flows, cross-account
    connections, alerts, annotations, and auto-generated insights.
    """
    if not accounts:
        return {"error": "No accounts provided"}

    account_profiles: list[dict] = []
    all_alerts: list[dict] = []
    all_annotations: list[dict] = []
    all_insights: list[dict] = []
    cross_connections: list[dict] = []
    total_in = 0.0
    total_out = 0.0
    total_txns = 0

    account_set = set()

    for acct_num in accounts:
        norm = "".join(c for c in acct_num if c.isdigit())
        if not norm:
            continue

        acct = session.scalars(
            select(Account).where(Account.normalized_account_number == norm)
        ).first()
        if not acct:
            account_profiles.append({"account": norm, "status": "not_found"})
            continue

        account_set.add(norm)

        # Transaction stats
        txn_count = session.scalar(
            select(func.count(Transaction.id)).where(Transaction.account_id == acct.id)
        ) or 0
        acct_in = float(session.scalar(
            select(func.sum(func.abs(Transaction.amount)))
            .where(Transaction.account_id == acct.id, Transaction.direction == "IN")
        ) or 0)
        acct_out = float(session.scalar(
            select(func.sum(func.abs(Transaction.amount)))
            .where(Transaction.account_id == acct.id, Transaction.direction == "OUT")
        ) or 0)

        total_in += acct_in
        total_out += acct_out
        total_txns += txn_count

        # Get flows
        flows = get_account_flows(session, norm)

        # Get insights
        insights = generate_account_insights(session, norm)

        # Get alerts for this account
        acct_alerts = session.scalars(
            select(Alert).where(Alert.account_id == acct.id).order_by(Alert.severity.asc())
        ).all()

        # Get annotations
        acct_annotations = session.scalars(
            select(GraphAnnotation).where(GraphAnnotation.node_id == norm)
        ).all()

        account_profiles.append({
            "account": norm,
            "name": acct.account_holder_name or "",
            "bank": acct.bank_name or "",
            "status": acct.status,
            "txn_count": txn_count,
            "total_in": round(acct_in, 2),
            "total_out": round(acct_out, 2),
            "circulation": round(acct_in + acct_out, 2),
            "inbound_sources": len(flows.get("inbound", [])),
            "outbound_targets": len(flows.get("outbound", [])),
            "alert_count": len(acct_alerts),
            "insight_count": insights.get("insight_count", 0),
        })

        for alert in acct_alerts:
            all_alerts.append({
                "account": norm,
                "severity": alert.severity,
                "rule_type": alert.rule_type,
                "summary": alert.summary,
                "status": alert.status,
            })

        for ann in acct_annotations:
            all_annotations.append({
                "account": norm,
                "type": ann.annotation_type,
                "content": ann.content,
                "tag": ann.tag,
                "created_by": ann.created_by,
            })

        for insight in insights.get("insights", []):
            all_insights.append({
                "account": norm,
                **insight,
            })

    # Find cross-connections between case accounts
    for profile in account_profiles:
        if profile.get("status") == "not_found":
            continue
        norm = profile["account"]
        flows = get_account_flows(session, norm)
        for direction, flow_list in [("inbound", flows.get("inbound", [])), ("outbound", flows.get("outbound", []))]:
            for flow in flow_list:
                if flow["account"] in account_set and flow["account"] != norm:
                    cross_connections.append({
                        "from": norm if direction == "outbound" else flow["account"],
                        "to": flow["account"] if direction == "outbound" else norm,
                        "total": flow["total"],
                        "count": flow["count"],
                        "direction": direction,
                    })

    # Deduplicate cross-connections
    seen = set()
    unique_connections = []
    for conn in cross_connections:
        key = f"{conn['from']}→{conn['to']}"
        if key not in seen:
            seen.add(key)
            unique_connections.append(conn)

    # Build narrative summary
    narrative = _build_narrative(account_profiles, all_alerts, all_insights, unique_connections)

    return {
        "case_name": case_name or f"Case Analysis ({len(accounts)} accounts)",
        "analyst": analyst,
        "accounts": account_profiles,
        "account_count": len(account_profiles),
        "totals": {
            "total_in": round(total_in, 2),
            "total_out": round(total_out, 2),
            "circulation": round(total_in + total_out, 2),
            "transaction_count": total_txns,
        },
        "cross_connections": unique_connections,
        "alerts": all_alerts,
        "alert_count": len(all_alerts),
        "annotations": all_annotations,
        "insights": all_insights,
        "insight_count": len(all_insights),
        "narrative": narrative,
    }


def _build_narrative(
    profiles: list[dict],
    alerts: list[dict],
    insights: list[dict],
    connections: list[dict],
) -> list[str]:
    """Build auto-generated case narrative points."""
    narrative: list[str] = []

    active = [p for p in profiles if p.get("status") != "not_found"]
    if not active:
        return ["ไม่พบข้อมูลบัญชีในระบบ"]

    # Overview
    total_circulation = sum(p.get("circulation", 0) for p in active)
    total_txns = sum(p.get("txn_count", 0) for p in active)
    narrative.append(
        f"วิเคราะห์ {len(active)} บัญชี รวม {total_txns:,} ธุรกรรม ยอดหมุนเวียน {total_circulation:,.2f} บาท"
    )

    # Cross-connections
    if connections:
        narrative.append(
            f"พบการเชื่อมโยงระหว่างบัญชีในคดี {len(connections)} เส้นทาง"
        )

    # High-severity alerts
    critical_alerts = [a for a in alerts if a["severity"] in ("critical", "high")]
    if critical_alerts:
        narrative.append(
            f"พบสัญญาณผิดปกติระดับสูง {len(critical_alerts)} รายการ: "
            + ", ".join(set(a["rule_type"] for a in critical_alerts))
        )

    # Key insights
    high_insights = [i for i in insights if i.get("severity") in ("critical", "high")]
    if high_insights:
        for insight in high_insights[:3]:
            narrative.append(f"⚠ {insight.get('title_th', insight.get('title', ''))}: {insight.get('description', '')[:100]}")

    # Largest account
    if active:
        largest = max(active, key=lambda p: p.get("circulation", 0))
        narrative.append(
            f"บัญชียอดหมุนเวียนสูงสุด: {largest['account']} ({largest.get('name', '')}) — {largest['circulation']:,.2f} บาท"
        )

    return narrative
