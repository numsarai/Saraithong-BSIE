"""
app.py
------
BSIE – Bank Statement Intelligence Engine
FastAPI web application backend.

Routes are organized into APIRouter modules under ``routers/``.
This file handles application lifecycle, static mounts, and router registration.
"""

import logging
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import time as _time

from fastapi import FastAPI, Request as _Request, Response as _Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

# ── Path setup ───────────────────────────────────────────────────────────
_BASE = Path(__file__).parent
sys.path.insert(0, str(_BASE))

from paths import (
    STATIC_DIR, CONFIG_DIR,
    INPUT_DIR, OUTPUT_DIR, EVIDENCE_DIR, EXPORTS_DIR, BACKUPS_DIR,
)
from database import init_db
from migrate_to_db import migrate_json_to_db
from utils.app_helpers import run_auto_backup_loop

# ── Routers ──────────────────────────────────────────────────────────────
from routers.ui import router as ui_router
from routers.ingestion import router as ingestion_router
from routers.bulk import router as bulk_router
from routers.jobs import router as jobs_router
from routers.results import router as results_router
from routers.search import router as search_router
from routers.graph import router as graph_router
from routers.review import router as review_router
from routers.admin import router as admin_router
from routers.case_tags import router as case_tags_router
from routers.overrides import router as overrides_router
from routers.banks import router as banks_router
from routers.annotations import router as annotations_router
from routers.auth import router as auth_router
from routers.workspace import router as workspace_router
from routers.alerts import router as alerts_router
from routers.analytics import router as analytics_router
from routers.dashboard import router as dashboard_router
from routers.reports import router as reports_router
from routers.fund_flow import router as fund_flow_router
from routers.exports import router as exports_router

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bsie.api")


# ── Startup / shutdown ───────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure all directories exist
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Initialise DB tables
    init_db()
    # Migrate any existing JSON data to DB (no-op if already done)
    try:
        migrate_json_to_db()
    except Exception as e:
        logger.warning(f"Migration step encountered an issue (non-fatal): {e}")
    # Ensure default admin user exists
    try:
        from services.auth_service import ensure_default_admin
        from persistence.base import get_db_session as _get_session
        with _get_session() as _session:
            ensure_default_admin(_session)
    except Exception:
        pass

    auto_backup_stop = threading.Event()
    auto_backup_thread = threading.Thread(
        target=run_auto_backup_loop,
        args=(auto_backup_stop,),
        daemon=True,
    )
    auto_backup_thread.start()
    try:
        yield
    finally:
        auto_backup_stop.set()
        auto_backup_thread.join(timeout=2.0)


# ── FastAPI app ──────────────────────────────────────────────────────────
app = FastAPI(
    title="BSIE – Bank Statement Intelligence Engine",
    version="3.0.1",
    root_path="",
    lifespan=lifespan,
)

# Request timing middleware
class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: _Request, call_next):
        start = _time.time()
        response: _Response = await call_next(request)
        duration_ms = round((_time.time() - start) * 1000, 1)
        response.headers["X-Process-Time-Ms"] = str(duration_ms)
        if duration_ms > 1000:
            logger.warning("Slow request: %s %s took %.0fms", request.method, request.url.path, duration_ms)
        return response

app.add_middleware(TimingMiddleware)

# Security: limit request body size (50 MB max for file uploads)
class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    MAX_BODY_SIZE = 50 * 1024 * 1024  # 50 MB

    async def dispatch(self, request: _Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_BODY_SIZE:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Request body too large (max 50 MB)"}, status_code=413)
        return await call_next(request)

app.add_middleware(MaxBodySizeMiddleware)

# CORS — allow frontend dev server and same-origin production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:6776", "http://127.0.0.1:6776", "http://localhost:8757"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure the compatibility and investigation schemas exist even when the app
# is imported directly in tests without a full startup cycle.
init_db()

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Serve the React build if it exists
_REACT_DIST = STATIC_DIR / "dist"
if _REACT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_REACT_DIST / "assets")), name="assets")


# ── Register routers ─────────────────────────────────────────────────────
# Order matters: specific paths before parameterized paths.
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(ingestion_router)
app.include_router(bulk_router)
app.include_router(jobs_router)
app.include_router(results_router)
app.include_router(search_router)
app.include_router(graph_router)
app.include_router(review_router)
app.include_router(admin_router)
app.include_router(case_tags_router)
app.include_router(overrides_router)
app.include_router(alerts_router)
app.include_router(analytics_router)
app.include_router(fund_flow_router)
app.include_router(reports_router)
app.include_router(annotations_router)
app.include_router(workspace_router)
app.include_router(banks_router)
app.include_router(exports_router)
app.include_router(ui_router)  # UI catch-all routes last

# ── Test compatibility re-exports ────────────────────────────────────────
# Existing tests use ``patch.object(app, "<name>")`` to mock symbols that
# were previously defined in this module. The re-exports below keep those
# patches working without touching every test file.
import pandas as pd  # noqa: F401,E402 — used via app.pd in tests
from tasks import get_runtime_job  # noqa: F401,E402
from paths import OUTPUT_DIR, BACKUPS_DIR  # noqa: F401,E402
from core.bank_detector import detect_bank  # noqa: F401,E402
from core.column_detector import detect_columns  # noqa: F401,E402
from core.loader import find_best_sheet_and_header  # noqa: F401,E402
from core.mapping_memory import find_matching_profile  # noqa: F401,E402
from core.bank_memory import find_matching_bank_fingerprint, save_bank_fingerprint  # noqa: F401,E402
from core.bulk_processor import process_folder  # noqa: F401,E402
from core.ofx_io import infer_identity_from_ofx, parse_ofx_file  # noqa: F401,E402
from core.override_manager import add_override, remove_override, get_all_overrides  # noqa: F401,E402
from persistence.base import get_db_session  # noqa: F401,E402
from services.audit_service import log_audit, record_learning_feedback  # noqa: F401,E402
from services.graph_analysis_service import (  # noqa: F401,E402
    get_graph_analysis, get_graph_neighborhood, list_graph_nodes, list_graph_findings,
)
from services.neo4j_service import get_neo4j_status, sync_graph_to_neo4j  # noqa: F401,E402
from services.account_resolution_service import best_known_account_holder_name  # noqa: F401,E402
from services.search_service import list_learning_feedback_logs  # noqa: F401,E402
from utils.app_helpers import reapply_overrides_to_csv as _reapply_overrides_to_csv  # noqa: F401,E402
