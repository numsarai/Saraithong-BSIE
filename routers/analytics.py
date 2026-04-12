"""
routers/analytics.py
--------------------
Analytics API: anomaly detection, period comparison, bulk cross-matching.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from persistence.base import get_db_session
from services.anomaly_detection_service import detect_anomalies
from services.period_comparison_service import compare_periods
from services.bulk_matching_service import bulk_cross_match
from services.sna_service import compute_sna_metrics
from services.file_metadata_service import extract_file_metadata
from services.insights_service import generate_account_insights
from services.case_tapestry_service import build_case_tapestry

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/anomalies")
async def api_detect_anomalies(
    account: str = "",
    method: str = "zscore",
    sigma: float = 2.0,
    window: int = 30,
):
    """Detect statistical anomalies in an account's transactions."""
    if not account:
        return JSONResponse({"error": "account parameter required"}, status_code=400)
    with get_db_session() as session:
        result = detect_anomalies(session, account, method=method, sigma=sigma, window=window)
    return JSONResponse(result)


@router.get("/compare-periods")
async def api_compare_periods(
    account: str = "",
    a_from: str = "",
    a_to: str = "",
    b_from: str = "",
    b_to: str = "",
):
    """Compare financial metrics between two time periods."""
    if not account or not a_from or not a_to or not b_from or not b_to:
        return JSONResponse({"error": "account, a_from, a_to, b_from, b_to required"}, status_code=400)
    with get_db_session() as session:
        result = compare_periods(session, account, a_from, a_to, b_from, b_to)
    return JSONResponse(result)


@router.get("/sna")
async def api_sna_metrics():
    """Compute Social Network Analysis centrality metrics for the account network."""
    with get_db_session() as session:
        result = compute_sna_metrics(session)
    return JSONResponse(result)


@router.get("/file-metadata")
async def api_file_metadata(file_path: str = ""):
    """Extract and verify file metadata for forensic integrity checks."""
    if not file_path:
        return JSONResponse({"error": "file_path required"}, status_code=400)
    result = extract_file_metadata(file_path)
    return JSONResponse(result)


@router.get("/insights")
async def api_account_insights(account: str = ""):
    """Generate auto investigation insights for an account."""
    if not account:
        return JSONResponse({"error": "account required"}, status_code=400)
    with get_db_session() as session:
        result = generate_account_insights(session, account)
    return JSONResponse(result)


@router.post("/case-tapestry")
async def api_case_tapestry(request: Request):
    """Build unified case tapestry from multiple accounts."""
    payload = await request.json()
    accounts = payload.get("accounts", [])
    case_name = str(payload.get("case_name", ""))
    analyst = str(payload.get("analyst", "analyst"))
    if not accounts:
        return JSONResponse({"error": "accounts list required"}, status_code=400)
    with get_db_session() as session:
        result = build_case_tapestry(session, accounts, case_name=case_name, analyst=analyst)
    return JSONResponse(result)


@router.post("/bulk-cross-match")
async def api_bulk_cross_match(request: Request):
    """Match transactions across multiple accounts simultaneously."""
    payload = await request.json()
    accounts = payload.get("accounts", [])
    date_from = str(payload.get("date_from", ""))
    date_to = str(payload.get("date_to", ""))
    with get_db_session() as session:
        result = bulk_cross_match(
            session,
            accounts=accounts or None,
            date_from=date_from,
            date_to=date_to,
        )
    return JSONResponse(result)
