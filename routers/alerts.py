"""
routers/alerts.py
-----------------
Alert management API routes: list, summary, config, and review.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from persistence.base import get_db_session
from services.alert_service import (
    get_alert_config,
    get_alert_summary,
    list_alerts,
    review_alert,
    update_alert_config,
)

router = APIRouter(prefix="/api", tags=["alerts"])


@router.get("/alerts")
async def api_list_alerts(
    status: str = "",
    severity: str = "",
    rule_type: str = "",
    account_id: str = "",
    limit: int = 200,
    offset: int = 0,
):
    with get_db_session() as session:
        items = list_alerts(
            session,
            status=status,
            severity=severity,
            rule_type=rule_type,
            account_id=account_id,
            limit=limit,
            offset=offset,
        )
    return JSONResponse({"items": items})


@router.get("/alerts/summary")
async def api_alert_summary():
    with get_db_session() as session:
        summary = get_alert_summary(session)
    return JSONResponse(summary)


@router.get("/alerts/config")
async def api_get_alert_config():
    with get_db_session() as session:
        config = get_alert_config(session)
    return JSONResponse(config)


@router.post("/alerts/config")
async def api_update_alert_config(request: Request):
    payload = await request.json()
    reviewer = str(payload.pop("reviewer", "analyst"))
    with get_db_session() as session:
        config = update_alert_config(session, payload, updated_by=reviewer)
    return JSONResponse(config)


@router.post("/alerts/{alert_id}/review")
async def api_review_alert(alert_id: str, request: Request):
    payload = await request.json()
    status = str(payload.get("status", ""))
    if status not in ("acknowledged", "resolved"):
        raise HTTPException(400, "status must be 'acknowledged' or 'resolved'")
    reviewer = str(payload.get("reviewer", "analyst"))
    note = str(payload.get("note", ""))
    with get_db_session() as session:
        result = review_alert(session, alert_id, status=status, reviewer=reviewer, note=note)
    if not result:
        raise HTTPException(404, "Alert not found")
    return JSONResponse(result)
