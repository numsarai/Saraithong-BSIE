"""
routers/reports.py
------------------
PDF report generation API routes.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from persistence.base import get_db_session
from services.report_service import generate_account_report, generate_case_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/account")
async def api_generate_account_report(request: Request):
    """Generate a single-account investigation PDF report."""
    payload = await request.json()
    account = str(payload.get("account", ""))
    parser_run_id = str(payload.get("parser_run_id", ""))
    analyst = str(payload.get("analyst", "analyst"))

    if not account:
        raise HTTPException(400, "account is required")

    with get_db_session() as session:
        pdf_path = generate_account_report(
            session,
            account,
            parser_run_id=parser_run_id,
            analyst=analyst,
        )

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
    )


@router.post("/case")
async def api_generate_case_report(request: Request):
    """Generate a multi-account case investigation PDF report."""
    payload = await request.json()
    accounts = payload.get("accounts", [])
    analyst = str(payload.get("analyst", "analyst"))

    if not accounts:
        raise HTTPException(400, "accounts list is required")

    with get_db_session() as session:
        pdf_path = generate_case_report(
            session,
            accounts,
            analyst=analyst,
        )

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
    )
