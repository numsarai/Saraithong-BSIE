"""
routers/exports.py
------------------
Export jobs, profiles, downloads, audit logs, and learning feedback endpoints.
"""

import re
import unicodedata
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from services.auth_service import require_auth
from fastapi.responses import FileResponse, JSONResponse


def _sanitize_filename(name: str) -> str:
    """Remove dangerous Unicode characters (RTLO, zero-width, homoglyphs) from filenames."""
    # Strip Unicode control characters (Bidi overrides, zero-width chars)
    cleaned = "".join(
        c for c in name
        if unicodedata.category(c) not in ("Cf", "Cc", "Co")  # format, control, private-use
    )
    # Keep only safe filename characters (alphanumeric, Thai, dot, dash, underscore, space)
    cleaned = re.sub(r'[^\w.\-\s\u0E00-\u0E7F]', '_', cleaned)
    return cleaned.strip() or "download"

from paths import OUTPUT_DIR, EXPORTS_DIR, BACKUPS_DIR
from core.mapping_memory import list_profiles
from persistence.base import get_db_session
from persistence.schemas import ExportRequest
from services.export_service import create_export_job, run_export_job
from services.search_service import (
    list_audit_logs,
    list_export_jobs,
    list_learning_feedback_logs,
)

router = APIRouter(prefix="/api", tags=["exports"], dependencies=[Depends(require_auth)])


@router.get("/export-jobs")
async def api_export_jobs(limit: int = 100, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_export_jobs(session, limit=limit, offset=offset)})


@router.post("/exports")
async def api_export_create(body: ExportRequest):
    with get_db_session() as session:
        job = create_export_job(session, export_type=body.export_type, filters=body.filters, created_by=body.created_by)
        run_export_job(session, job)
        session.commit()
        return JSONResponse({
            "id": job.id,
            "export_type": job.export_type,
            "status": job.status,
            "output_path": job.output_path,
            "summary_json": job.summary_json or {},
        })


@router.get("/profiles")
async def api_profiles():
    return JSONResponse({"profiles": list_profiles()})


@router.get("/download/{account}/{file_path:path}")
async def api_download(account: str, file_path: str, download_name: str = ""):
    safe = "".join(c for c in account if c.isdigit())
    base = (OUTPUT_DIR / safe).resolve()
    full = (base / file_path).resolve()
    if not str(full).startswith(str(base)):
        raise HTTPException(400, "Invalid file path")
    if not full.exists() or not full.is_file():
        raise HTTPException(404, "File not found")
    preferred_name = _sanitize_filename(Path(str(download_name or "")).name.strip() or full.name)
    return FileResponse(str(full), filename=preferred_name)


@router.get("/download-bulk/{run_id}/{file_path:path}")
async def api_download_bulk(run_id: str, file_path: str, download_name: str = ""):
    safe_run_id = "".join(c for c in run_id if c.isdigit() or c == "_")
    if not safe_run_id:
        raise HTTPException(400, "Invalid run_id")

    base = (OUTPUT_DIR / "bulk_runs" / safe_run_id).resolve()
    full = (base / file_path).resolve()
    if not str(full).startswith(str(base)):
        raise HTTPException(400, "Invalid file path")
    if not full.exists() or not full.is_file():
        raise HTTPException(404, "File not found")

    preferred_name = _sanitize_filename(Path(str(download_name or "")).name.strip() or full.name)
    return FileResponse(str(full), filename=preferred_name)


@router.get("/download-export/{job_id}/{file_path:path}")
async def api_download_export(job_id: str, file_path: str, download_name: str = ""):
    safe_job_id = "".join(c for c in job_id if c.isalnum() or c in {"-", "_"})
    if not safe_job_id:
        raise HTTPException(400, "Invalid export job id")
    base = (EXPORTS_DIR / safe_job_id).resolve()
    full = (base / file_path).resolve()
    if not str(full).startswith(str(base)):
        raise HTTPException(400, "Invalid file path")
    if not full.exists() or not full.is_file():
        raise HTTPException(404, "File not found")
    preferred_name = _sanitize_filename(Path(str(download_name or "")).name.strip() or full.name)
    return FileResponse(str(full), filename=preferred_name)


@router.get("/download-backup/{backup_name}")
async def api_download_backup(backup_name: str, download_name: str = ""):
    safe_name = Path(str(backup_name or "")).name.strip()
    if not safe_name:
        raise HTTPException(400, "Invalid backup name")
    base = BACKUPS_DIR.resolve()
    full = (base / safe_name).resolve()
    if not str(full).startswith(str(base)):
        raise HTTPException(400, "Invalid file path")
    if not full.exists() or not full.is_file():
        raise HTTPException(404, "File not found")
    preferred_name = _sanitize_filename(Path(str(download_name or "")).name.strip() or full.name)
    return FileResponse(str(full), filename=preferred_name)


@router.get("/audit-logs")
async def api_audit_logs(object_type: str = "", object_id: str = "", limit: int = 200, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_audit_logs(session, object_type=object_type, object_id=object_id, limit=limit, offset=offset)})


@router.get("/audit-trail/{object_type}/{object_id}")
async def api_audit_trail(object_type: str, object_id: str):
    """Get full chain of custody / audit trail for a specific object."""
    with get_db_session() as session:
        items = list_audit_logs(session, object_type=object_type, object_id=object_id, limit=500, offset=0)
    return JSONResponse({"object_type": object_type, "object_id": object_id, "items": items, "total": len(items)})


@router.get("/learning-feedback")
async def api_learning_feedback(object_id: str = "", limit: int = 200, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_learning_feedback_logs(session, object_id=object_id, limit=limit, offset=offset)})
