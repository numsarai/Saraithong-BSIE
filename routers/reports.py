"""
routers/reports.py
------------------
PDF report generation API routes.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from persistence.base import get_db_session
from services.report_service import generate_account_report, generate_case_report
from services.report_template_service import (
    list_templates, get_template, save_template, delete_template,
    list_criteria, save_criteria,
)

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


@router.get("/templates")
async def api_list_templates():
    with get_db_session() as session:
        return JSONResponse({"items": list_templates(session)})


@router.get("/templates/{template_id}")
async def api_get_template(template_id: str):
    with get_db_session() as session:
        tpl = get_template(session, template_id)
    if not tpl:
        raise HTTPException(404, "Template not found")
    return JSONResponse(tpl)


@router.post("/templates")
async def api_save_template(request: Request):
    payload = await request.json()
    reviewer = str(payload.pop("reviewer", "analyst"))
    with get_db_session() as session:
        result = save_template(session, payload, updated_by=reviewer)
    return JSONResponse(result)


@router.delete("/templates/{template_id}")
async def api_delete_template(template_id: str):
    with get_db_session() as session:
        ok = delete_template(session, template_id)
    if not ok:
        raise HTTPException(404, "Template not found")
    return JSONResponse({"status": "deleted"})


@router.get("/criteria")
async def api_list_criteria():
    with get_db_session() as session:
        return JSONResponse({"items": list_criteria(session)})


@router.post("/criteria")
async def api_save_criteria(request: Request):
    payload = await request.json()
    reviewer = str(payload.pop("reviewer", "analyst"))
    with get_db_session() as session:
        result = save_criteria(session, payload, updated_by=reviewer)
    return JSONResponse(result)


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
