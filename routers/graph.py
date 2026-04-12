"""
routers/graph.py
----------------
Graph-analysis API routes extracted from app.py.
"""

from typing import Optional

from services.auth_service import require_auth
from fastapi import Depends, APIRouter
from fastapi.responses import JSONResponse

from persistence.base import get_db_session
from persistence.schemas import GraphNeo4jSyncRequest
from services.graph_analysis_service import (
    get_graph_analysis,
    get_graph_neighborhood,
    list_graph_derived_edges,
    list_graph_edges,
    list_graph_findings,
    list_graph_nodes,
)
from services.neo4j_service import get_neo4j_status, sync_graph_to_neo4j

router = APIRouter(prefix="/api", tags=["graph"], dependencies=[Depends(require_auth)])


def _graph_filter_payload(
    *,
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
) -> dict:
    return {
        "q": q,
        "account": account,
        "counterparty": counterparty,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "date_from": date_from,
        "date_to": date_to,
        "bank": bank,
        "reference_no": reference_no,
        "transaction_type": transaction_type,
        "duplicate_status": duplicate_status,
        "review_status": review_status,
        "match_status": match_status,
        "file_id": file_id,
        "parser_run_id": parser_run_id,
    }


@router.get("/graph-analysis")
async def api_graph_analysis(
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    limit: int = 5000,
):
    with get_db_session() as session:
        payload = get_graph_analysis(
            session,
            q=q,
            account=account,
            counterparty=counterparty,
            amount_min=amount_min,
            amount_max=amount_max,
            date_from=date_from,
            date_to=date_to,
            bank=bank,
            reference_no=reference_no,
            transaction_type=transaction_type,
            duplicate_status=duplicate_status,
            review_status=review_status,
            match_status=match_status,
            file_id=file_id,
            parser_run_id=parser_run_id,
            limit=limit,
        )
    return JSONResponse(payload)


@router.get("/graph/nodes")
async def api_graph_nodes(
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    limit: int = 5000,
):
    filters = _graph_filter_payload(
        q=q,
        account=account,
        counterparty=counterparty,
        amount_min=amount_min,
        amount_max=amount_max,
        date_from=date_from,
        date_to=date_to,
        bank=bank,
        reference_no=reference_no,
        transaction_type=transaction_type,
        duplicate_status=duplicate_status,
        review_status=review_status,
        match_status=match_status,
        file_id=file_id,
        parser_run_id=parser_run_id,
    )
    with get_db_session() as session:
        items = list_graph_nodes(session, limit=limit, **filters)
    effective_limit = max(1, min(limit, 5000))
    return JSONResponse({
        "items": items,
        "meta": {
            "requested_limit": limit,
            "effective_limit": effective_limit,
            "returned_count": len(items),
            "truncated": limit > effective_limit,
        },
    })


@router.get("/graph/edges")
async def api_graph_edges(
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    limit: int = 5000,
    include_relationships: bool = True,
):
    filters = _graph_filter_payload(
        q=q,
        account=account,
        counterparty=counterparty,
        amount_min=amount_min,
        amount_max=amount_max,
        date_from=date_from,
        date_to=date_to,
        bank=bank,
        reference_no=reference_no,
        transaction_type=transaction_type,
        duplicate_status=duplicate_status,
        review_status=review_status,
        match_status=match_status,
        file_id=file_id,
        parser_run_id=parser_run_id,
    )
    with get_db_session() as session:
        items = list_graph_edges(session, limit=limit, include_relationships=include_relationships, **filters)
    effective_limit = max(1, min(limit, 5000))
    return JSONResponse({
        "items": items,
        "meta": {
            "requested_limit": limit,
            "effective_limit": effective_limit,
            "returned_count": len(items),
            "include_relationships": include_relationships,
            "truncated": limit > effective_limit,
        },
    })


@router.get("/graph/derived-edges")
async def api_graph_derived_edges(
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    limit: int = 5000,
):
    filters = _graph_filter_payload(
        q=q,
        account=account,
        counterparty=counterparty,
        amount_min=amount_min,
        amount_max=amount_max,
        date_from=date_from,
        date_to=date_to,
        bank=bank,
        reference_no=reference_no,
        transaction_type=transaction_type,
        duplicate_status=duplicate_status,
        review_status=review_status,
        match_status=match_status,
        file_id=file_id,
        parser_run_id=parser_run_id,
    )
    with get_db_session() as session:
        items = list_graph_derived_edges(session, limit=limit, **filters)
    effective_limit = max(1, min(limit, 5000))
    return JSONResponse({
        "items": items,
        "meta": {
            "requested_limit": limit,
            "effective_limit": effective_limit,
            "returned_count": len(items),
            "truncated": limit > effective_limit,
        },
    })


@router.get("/graph/findings")
async def api_graph_findings(
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    severity: str = "",
    rule_type: str = "",
    limit: int = 5000,
):
    filters = _graph_filter_payload(
        q=q,
        account=account,
        counterparty=counterparty,
        amount_min=amount_min,
        amount_max=amount_max,
        date_from=date_from,
        date_to=date_to,
        bank=bank,
        reference_no=reference_no,
        transaction_type=transaction_type,
        duplicate_status=duplicate_status,
        review_status=review_status,
        match_status=match_status,
        file_id=file_id,
        parser_run_id=parser_run_id,
    )
    with get_db_session() as session:
        items = list_graph_findings(session, limit=limit, severity=severity, rule_type=rule_type, **filters)
    effective_limit = max(1, min(limit, 5000))
    return JSONResponse({
        "items": items,
        "meta": {
            "requested_limit": limit,
            "effective_limit": effective_limit,
            "returned_count": len(items),
            "severity": severity,
            "rule_type": rule_type,
            "truncated": limit > effective_limit,
        },
    })


@router.get("/graph/neighborhood/{node_id}")
async def api_graph_neighborhood(
    node_id: str,
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    limit: int = 5000,
    include_relationships: bool = True,
    max_nodes: int = 14,
    max_edges: int = 24,
):
    filters = _graph_filter_payload(
        q=q,
        account=account,
        counterparty=counterparty,
        amount_min=amount_min,
        amount_max=amount_max,
        date_from=date_from,
        date_to=date_to,
        bank=bank,
        reference_no=reference_no,
        transaction_type=transaction_type,
        duplicate_status=duplicate_status,
        review_status=review_status,
        match_status=match_status,
        file_id=file_id,
        parser_run_id=parser_run_id,
    )
    with get_db_session() as session:
        payload = get_graph_neighborhood(
            session,
            node_id=node_id,
            limit=limit,
            include_relationships=include_relationships,
            max_nodes=max_nodes,
            max_edges=max_edges,
            **filters,
        )
    return JSONResponse(payload)


@router.get("/graph/neo4j-status")
async def api_graph_neo4j_status():
    return JSONResponse(get_neo4j_status())


@router.post("/graph/neo4j-sync")
async def api_graph_neo4j_sync(body: GraphNeo4jSyncRequest):
    with get_db_session() as session:
        payload = sync_graph_to_neo4j(
            session,
            limit=body.limit,
            include_findings=body.include_findings,
            **(body.filters or {}),
        )
    return JSONResponse(payload)
