"""
routers/bulk.py
---------------
Bulk folder processing and analytics endpoints.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from paths import OUTPUT_DIR
from core.bulk_processor import process_folder

logger = logging.getLogger("bsie.api")

router = APIRouter(prefix="/api", tags=["bulk"])


@router.post("/process-folder")
async def api_process_folder(request: Request):
    """Process a local folder of bank statements into a single case summary."""
    body = await request.json()
    folder_path = body.get("folder_path", "")
    recursive = bool(body.get("recursive", False))
    operator = str(body.get("operator", "bulk-intake") or "bulk-intake").strip() or "bulk-intake"

    if not folder_path:
        raise HTTPException(400, "folder_path is required")

    try:
        summary = process_folder(folder_path, recursive=recursive, operator=operator)
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Bulk folder processing failed: %s", exc)
        raise HTTPException(500, str(exc)) from exc

    return JSONResponse(summary)


@router.get("/bulk/{run_id}/analytics")
async def api_bulk_analytics(run_id: str):
    safe_run_id = "".join(c for c in run_id if c.isdigit() or c == "_")
    if not safe_run_id:
        raise HTTPException(400, "Invalid run_id")
    analytics_path = OUTPUT_DIR / "bulk_runs" / safe_run_id / "case_analytics.json"
    if not analytics_path.exists():
        raise HTTPException(404, "Bulk analytics not found")
    return JSONResponse(json.loads(analytics_path.read_text(encoding="utf-8")))
