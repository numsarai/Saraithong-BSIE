"""
routers/jobs.py
---------------
Job and parser-run related API routes.
"""

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from database import db_create_job, db_get_job
from persistence.base import get_db_session
from persistence.models import ParserRun
from persistence.schemas import ReviewRequest
from services.file_ingestion_service import get_file_record
from services.persistence_pipeline_service import create_parser_run
from services.search_service import list_parser_runs
from tasks import get_runtime_job
from utils.app_helpers import dispatch_pipeline

logger = logging.getLogger("bsie.api")

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/job/{job_id}")
async def api_job_status(job_id: str):
    runtime_job = get_runtime_job(job_id)
    if runtime_job:
        return JSONResponse({
            "status": runtime_job.get("status"),
            "log": list(runtime_job.get("log") or [])[-200:],
            "result": runtime_job.get("result"),
            "error": runtime_job.get("error"),
        })

    job = db_get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    # Parse log_text into a list of lines (last 200)
    log_lines = (job["log_text"] or "").splitlines()
    log_lines = log_lines[-200:]

    # Parse result_json back to dict
    result = None
    if job["result_json"]:
        try:
            result = json.loads(job["result_json"])
        except Exception:
            result = None

    return JSONResponse({
        "status": job["status"],
        "log":    log_lines,
        "result": result,
        "error":  job["error"],
    })


@router.get("/parser-runs")
async def api_parser_runs(limit: int = 100, offset: int = 0, file_id: str = ""):
    with get_db_session() as session:
        return JSONResponse({"items": list_parser_runs(session, limit=limit, offset=offset, file_id=file_id or None)})


@router.get("/parser-runs/{parser_run_id}")
async def api_parser_run_detail(parser_run_id: str):
    with get_db_session() as session:
        row = session.get(ParserRun, parser_run_id)
        if not row:
            raise HTTPException(404, "Parser run not found")
        return JSONResponse({
            "id": row.id,
            "file_id": row.file_id,
            "status": row.status,
            "parser_version": row.parser_version,
            "mapping_profile_version": row.mapping_profile_version,
            "bank_detected": row.bank_detected,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "summary_json": row.summary_json or {},
        })


@router.post("/parser-runs/{parser_run_id}/reprocess")
async def api_parser_run_reprocess(parser_run_id: str, body: ReviewRequest):
    with get_db_session() as session:
        parser_run = session.get(ParserRun, parser_run_id)
        if not parser_run:
            raise HTTPException(404, "Parser run not found")
        file_row = get_file_record(parser_run.file_id)
        if not file_row:
            raise HTTPException(404, "Source file not found")
        summary = parser_run.summary_json or {}
        account = str(summary.get("subject_account", "") or "")
        name = str(summary.get("subject_name", "") or "")
        bank_key = str(summary.get("bank_key", parser_run.bank_detected or "") or "")
        if not account:
            raise HTTPException(400, "Parser run is missing subject_account in summary")

    job_id = str(uuid.uuid4())
    db_create_job(job_id, account=account)
    new_run = create_parser_run(
        file_id=parser_run.file_id,
        bank_detected=bank_key,
        confirmed_mapping={},
        operator=body.reviewer,
    )
    dispatch_pipeline(
        job_id,
        file_row.stored_path,
        bank_key,
        account,
        name,
        {},
        file_id=parser_run.file_id,
        parser_run_id=new_run["parser_run_id"],
        operator=body.reviewer,
        header_row=int(summary.get("header_row", 0) or 0),
        sheet_name=str(summary.get("sheet_name", "") or ""),
    )
    return JSONResponse({"job_id": job_id, "parser_run_id": new_run["parser_run_id"]})
