"""
promptpay_graph_service.py
--------------------------
Build a specialized graph linking PromptPay identifiers, phone numbers,
and national IDs to bank accounts. Surfaces hidden connections that
regular account-to-account graphs miss.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import Account, Transaction


_PHONE_RE = re.compile(r'0[689]\d{8}')
_NATIONAL_ID_RE = re.compile(r'\b\d{13}\b')


def build_promptpay_graph(session: Session, account: str = "") -> dict[str, Any]:
    """Build a graph of PromptPay/phone/national ID connections.

    Scans transaction descriptions for phone numbers and national IDs,
    then maps them to counterparty accounts to reveal hidden linkages.
    """
    query = select(Transaction)
    if account:
        acct = session.scalars(
            select(Account).where(Account.normalized_account_number == account)
        ).first()
        if acct:
            query = query.where(Transaction.account_id == acct.id)

    txns = session.scalars(query.limit(50000)).all()

    # Extract identifiers from descriptions
    phone_to_accounts: dict[str, set[str]] = defaultdict(set)
    id_to_accounts: dict[str, set[str]] = defaultdict(set)
    account_phones: dict[str, set[str]] = defaultdict(set)
    account_ids: dict[str, set[str]] = defaultdict(set)

    for txn in txns:
        desc = txn.description_normalized or txn.description_raw or ""
        cp = txn.counterparty_account_normalized or ""
        subject = ""
        if txn.account_id:
            acct_row = session.get(Account, txn.account_id)
            if acct_row:
                subject = acct_row.normalized_account_number or ""

        # Find phones
        phones = _PHONE_RE.findall(desc)
        for phone in phones:
            if cp:
                phone_to_accounts[phone].add(cp)
            if subject:
                phone_to_accounts[phone].add(subject)
                account_phones[subject].add(phone)

        # Find national IDs
        ids = _NATIONAL_ID_RE.findall(desc)
        for nid in ids:
            if cp:
                id_to_accounts[nid].add(cp)
            if subject:
                id_to_accounts[nid].add(subject)
                account_ids[subject].add(nid)

    # Build graph nodes and edges
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()

    def _add_node(nid: str, ntype: str, label: str = "") -> None:
        if nid not in seen_nodes:
            seen_nodes.add(nid)
            nodes.append({"id": nid, "type": ntype, "label": label or nid})

    # Phone → account edges
    for phone, accounts in phone_to_accounts.items():
        if len(accounts) >= 1:
            _add_node(phone, "phone", f"Tel: {phone}")
            for acct_num in accounts:
                _add_node(acct_num, "account")
                edges.append({
                    "from": phone, "to": acct_num,
                    "type": "phone_linked",
                    "label": "PromptPay/Phone",
                })

    # National ID → account edges
    for nid, accounts in id_to_accounts.items():
        if len(accounts) >= 1:
            _add_node(nid, "national_id", f"ID: {nid[:4]}...{nid[-2:]}")
            for acct_num in accounts:
                _add_node(acct_num, "account")
                edges.append({
                    "from": nid, "to": acct_num,
                    "type": "id_linked",
                    "label": "National ID",
                })

    # Find multi-account connections (same phone/ID → multiple accounts)
    multi_connections = []
    for phone, accounts in phone_to_accounts.items():
        if len(accounts) >= 2:
            multi_connections.append({
                "identifier": phone,
                "type": "phone",
                "accounts": sorted(accounts),
                "description": f"เบอร์ {phone} เชื่อมโยงกับ {len(accounts)} บัญชี",
            })
    for nid, accounts in id_to_accounts.items():
        if len(accounts) >= 2:
            multi_connections.append({
                "identifier": nid,
                "type": "national_id",
                "accounts": sorted(accounts),
                "description": f"บัตร {nid[:4]}...{nid[-2:]} เชื่อมโยงกับ {len(accounts)} บัญชี",
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "multi_connections": multi_connections,
        "phones_found": len(phone_to_accounts),
        "national_ids_found": len(id_to_accounts),
    }
