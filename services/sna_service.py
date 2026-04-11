"""
sna_service.py
--------------
Social Network Analysis — degree, betweenness, and closeness centrality
for account networks. Inspired by i2 Analyst's Notebook SNA capabilities.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from persistence.models import Account, Transaction


def compute_sna_metrics(session: Session, accounts: list[str] | None = None) -> dict[str, Any]:
    """Compute SNA centrality metrics for the account network.

    Returns node-level metrics: degree, betweenness, closeness, and flow totals.
    """
    # Build adjacency from transactions
    adjacency: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    node_flow: dict[str, dict[str, float]] = defaultdict(lambda: {"in": 0.0, "out": 0.0, "total": 0.0, "count": 0})

    # Query all outbound flows grouped by account pair
    query = select(
        Transaction.account_id,
        Transaction.counterparty_account_normalized,
        Transaction.direction,
        func.sum(func.abs(Transaction.amount)).label("total"),
        func.count().label("cnt"),
    ).where(
        Transaction.counterparty_account_normalized.isnot(None),
        Transaction.counterparty_account_normalized != "",
    ).group_by(
        Transaction.account_id,
        Transaction.counterparty_account_normalized,
        Transaction.direction,
    )

    # Map account_id to normalized number
    acct_map: dict[str, str] = {}
    for acct in session.scalars(select(Account)).all():
        if acct.normalized_account_number:
            acct_map[acct.id] = acct.normalized_account_number

    for row in session.execute(query).all():
        acct_num = acct_map.get(row.account_id, "")
        cp_num = row.counterparty_account_normalized or ""
        if not acct_num or not cp_num or acct_num == cp_num:
            continue

        amount = float(row.total or 0)
        count = int(row.cnt or 0)

        if row.direction == "OUT":
            adjacency[acct_num][cp_num] += amount
        elif row.direction == "IN":
            adjacency[cp_num][acct_num] += amount

        node_flow[acct_num]["count"] += count
        if row.direction == "IN":
            node_flow[acct_num]["in"] += amount
        else:
            node_flow[acct_num]["out"] += amount
        node_flow[acct_num]["total"] += amount

    all_nodes = set(adjacency.keys())
    for src, targets in adjacency.items():
        all_nodes.update(targets.keys())

    if accounts:
        all_nodes = {n for n in all_nodes if n in set(accounts)}

    if len(all_nodes) < 2:
        return {"nodes": [], "summary": {"node_count": len(all_nodes), "edge_count": 0}}

    # 1. Degree centrality
    degree: dict[str, int] = defaultdict(int)
    for src, targets in adjacency.items():
        for tgt in targets:
            if src in all_nodes:
                degree[src] += 1
            if tgt in all_nodes:
                degree[tgt] += 1

    max_degree = max(degree.values()) if degree else 1

    # 2. Betweenness centrality (simplified BFS)
    betweenness: dict[str, float] = defaultdict(float)
    node_list = list(all_nodes)

    for source in node_list[:200]:  # Limit for performance
        # BFS shortest paths
        dist: dict[str, int] = {source: 0}
        paths: dict[str, int] = {source: 1}
        order: list[str] = []
        queue = deque([source])

        while queue:
            v = queue.popleft()
            order.append(v)
            for w in adjacency.get(v, {}):
                if w not in all_nodes:
                    continue
                if w not in dist:
                    dist[w] = dist[v] + 1
                    paths[w] = 0
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    paths[w] += paths[v]

        # Accumulate betweenness
        delta: dict[str, float] = defaultdict(float)
        for w in reversed(order):
            for v in adjacency.get(w, {}):
                if v in dist and dist[v] == dist[w] - 1 and paths[w] > 0:
                    delta[v] += (paths[v] / paths[w]) * (1 + delta[w])
            if w != source:
                betweenness[w] += delta[w]

    max_betweenness = max(betweenness.values()) if betweenness else 1

    # 3. Closeness centrality
    closeness: dict[str, float] = {}
    for source in node_list[:200]:
        dist: dict[str, int] = {source: 0}
        queue = deque([source])
        while queue:
            v = queue.popleft()
            for w in adjacency.get(v, {}):
                if w not in all_nodes or w in dist:
                    continue
                dist[w] = dist[v] + 1
                queue.append(w)
        reachable = len(dist) - 1
        if reachable > 0:
            avg_dist = sum(dist.values()) / reachable
            closeness[source] = round(1.0 / avg_dist, 4) if avg_dist > 0 else 0
        else:
            closeness[source] = 0

    # Build result
    nodes = []
    for node_id in all_nodes:
        flow = node_flow.get(node_id, {"in": 0, "out": 0, "total": 0, "count": 0})
        nodes.append({
            "id": node_id,
            "degree": degree.get(node_id, 0),
            "degree_normalized": round(degree.get(node_id, 0) / max_degree, 4) if max_degree else 0,
            "betweenness": round(betweenness.get(node_id, 0), 4),
            "betweenness_normalized": round(betweenness.get(node_id, 0) / max_betweenness, 4) if max_betweenness else 0,
            "closeness": closeness.get(node_id, 0),
            "flow_in": round(flow["in"], 2),
            "flow_out": round(flow["out"], 2),
            "flow_total": round(flow["total"], 2),
            "txn_count": flow["count"],
        })

    nodes.sort(key=lambda n: -n["betweenness"])

    return {
        "nodes": nodes,
        "summary": {
            "node_count": len(nodes),
            "edge_count": sum(len(t) for t in adjacency.values()),
            "max_degree": max_degree,
            "max_betweenness": round(max_betweenness, 4),
            "avg_closeness": round(sum(closeness.values()) / len(closeness), 4) if closeness else 0,
        },
    }
