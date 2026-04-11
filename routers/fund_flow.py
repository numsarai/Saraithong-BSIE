"""
routers/fund_flow.py
--------------------
Cross-account fund flow analysis API routes.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from persistence.base import get_db_session
from services.fund_flow_service import (
    get_account_flows,
    get_matched_transactions,
    trace_fund_path,
)

router = APIRouter(prefix="/api/fund-flow", tags=["fund-flow"])


@router.get("/{account}")
async def api_account_flows(account: str):
    """Get inbound sources and outbound targets for an account."""
    with get_db_session() as session:
        result = get_account_flows(session, account)
    return JSONResponse(result)


@router.get("/{account_a}/to/{account_b}")
async def api_matched_transactions(account_a: str, account_b: str, limit: int = 200):
    """Get all transactions between two specific accounts."""
    with get_db_session() as session:
        items = get_matched_transactions(session, account_a, account_b, limit=limit)
    return JSONResponse({"items": items, "total": len(items)})


@router.get("/trace")
async def api_trace_path(
    from_account: str = "",
    to_account: str = "",
    max_hops: int = 4,
):
    """Trace fund flow path from one account to another (BFS)."""
    with get_db_session() as session:
        result = trace_fund_path(
            session,
            from_account=from_account,
            to_account=to_account,
            max_hops=min(max_hops, 6),
        )
    return JSONResponse(result)
