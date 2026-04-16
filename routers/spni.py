"""
routers/spni.py
---------------
SPNI integration API routes.

Exposes BSIE data (accounts, transactions, entities) for consumption
by SPNI's BSIEAdapter via the Module Adapter Pattern.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text

from persistence.base import get_db_session
from services.auth_service import require_auth
from services.spni_service import (
    APP_VERSION,
    export_data,
    get_run_preview,
    list_completed_runs,
)

logger = logging.getLogger("bsie.api")

router = APIRouter(prefix="/api/spni", tags=["spni"], dependencies=[Depends(require_auth)])


@router.get("/health")
async def api_spni_health():
    """Health check for SPNI to verify BSIE is reachable."""
    db_ready = False
    try:
        with get_db_session() as session:
            session.execute(text("SELECT 1"))
            db_ready = True
    except Exception as exc:
        logger.warning("SPNI health check: database unreachable — %s", exc)

    return JSONResponse({
        "status": "ok",
        "version": APP_VERSION,
        "db_ready": db_ready,
    })


@router.get("/runs")
async def api_spni_runs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List completed parser runs with metadata for SPNI's run selector."""
    with get_db_session() as session:
        result = list_completed_runs(session, limit=limit, offset=offset)
    return JSONResponse(result)


@router.get("/runs/{run_id}/preview")
async def api_spni_run_preview(run_id: str):
    """Preview data available in a parser run before import."""
    with get_db_session() as session:
        result = get_run_preview(session, run_id)
    if result is None:
        raise HTTPException(404, "Parser run not found")
    return JSONResponse(result)


@router.get("/export")
async def api_spni_export(
    run_id: str = "",
    accounts: str = "",
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    limit: int = Query(default=5000, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
):
    """Export accounts, transactions, and entities for SPNI adapter."""
    if not run_id:
        raise HTTPException(400, "run_id is required")

    account_filter = [a.strip() for a in accounts.split(",") if a.strip()] if accounts else None

    with get_db_session() as session:
        result = export_data(
            session,
            run_id=run_id,
            account_filter=account_filter,
            date_from=date_from,
            date_to=date_to,
            amount_min=amount_min,
            amount_max=amount_max,
            limit=limit,
            offset=offset,
        )
    return JSONResponse(result)
