"""
app.py
------
BSIE – Bank Statement Intelligence Engine
FastAPI web application backend.

Workflow:
  POST /api/upload          Upload Excel, detect bank + columns, return suggestions
  POST /api/mapping/confirm Confirm / edit column mapping, save profile
  POST /api/process         Run full 14-step pipeline (background)
  POST /api/process-folder  Run bulk folder intake and return case summary
  GET  /api/job/{id}        Poll pipeline job status
  GET  /api/results/{acct}  Retrieve processed transaction data
  GET  /api/files           Search persisted file evidence
  GET  /api/parser-runs     Search parser run history
  GET  /api/accounts        Search account registry
  GET  /api/accounts/remembered-name Lookup remembered account holder name
  GET  /api/transactions/search Search persisted transactions
  GET  /api/duplicates      Review duplicate groups
  GET  /api/matches         Review match candidates
  GET  /api/audit-logs      Review audit trail
  GET  /api/learning-feedback Review learning feedback signals
  GET  /api/admin/db-status Database runtime and schema status
  GET  /api/admin/backups   List database backups
  GET  /api/admin/backup-settings Get scheduled backup settings
  GET  /api/admin/backups/{name}/preview Preview a restore against current DB
  POST /api/admin/backup-settings Update scheduled backup settings
  POST /api/admin/backup    Create database backup
  POST /api/admin/reset     Reset database after confirmation
  POST /api/admin/restore   Restore database backup after confirmation
  POST /api/exports         Create reproducible export job
  POST /api/override        Add / update a relationship override
  DELETE /api/override/{id} Remove an override
  GET  /api/overrides       List all overrides
  GET  /api/profiles        List saved mapping profiles
  GET  /api/download/{acct}/{path} Download output file
  GET  /api/download-export/{job}/{path} Download export job file
  GET  /api/download-bulk/{run_id}/{path} Download bulk summary output
"""

import json
import logging
import os
import sys
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, inspect, select

# ── Path setup ───────────────────────────────────────────────────────────
# _BASE is intentionally retained: sys.path.insert ensures `pipeline`, `core`,
# etc. are importable when app.py is loaded by uvicorn in both source mode and
# bundle mode (PyInstaller sets sys._MEIPASS but uvicorn imports app lazily).
_BASE = Path(__file__).parent
sys.path.insert(0, str(_BASE))

from paths import (
    STATIC_DIR, TEMPLATES_DIR, CONFIG_DIR, BUILTIN_CONFIG_DIR,
    INPUT_DIR, OUTPUT_DIR, EVIDENCE_DIR, EXPORTS_DIR, BACKUPS_DIR,
)

from database import (
    init_db,
    db_create_job, db_update_job, db_get_job, db_append_log, insert_job_meta,
)
from migrate_to_db import migrate_json_to_db
from tasks import run_pipeline_sync


def _dispatch_pipeline(
    job_id: str,
    upload_path_str: str,
    bank_key: str,
    account: str,
    name: str,
    confirmed_mapping: dict,
    *,
    file_id: str = "",
    parser_run_id: str = "",
    operator: str = "analyst",
    header_row: int = 0,
    sheet_name: str = "",
) -> None:
    """Dispatch the pipeline using the local background thread."""
    logger.info("Dispatching pipeline via local background thread")
    t = threading.Thread(
        target=run_pipeline_sync,
        kwargs={
            "job_id": job_id,
            "upload_path_str": upload_path_str,
            "bank_key": bank_key,
            "account": account,
            "name": name,
            "confirmed_mapping": confirmed_mapping,
            "file_id": file_id,
            "parser_run_id": parser_run_id,
            "operator": operator,
            "header_row": header_row,
            "sheet_name": sheet_name,
        },
        daemon=True,
    )
    t.start()

from core.loader               import load_config, find_best_sheet_and_header
from core.bank_detector        import detect_bank
from core.column_detector      import detect_columns, get_field_aliases, _norm
from core.mapping_memory       import find_matching_profile, list_profiles
from core.bank_memory          import find_matching_bank_fingerprint, save_bank_fingerprint
from core.bulk_processor       import process_folder
from core.ofx_io              import infer_identity_from_ofx, parse_ofx_file
from core.override_manager     import (
    add_override, remove_override, get_all_overrides, apply_overrides_to_df,
)
from persistence.base import DATABASE_RUNTIME_SOURCE, DATABASE_URL, IS_SQLITE, engine, get_db_session
from persistence.models import (
    Account,
    AuditLog,
    CaseTag,
    CaseTagLink,
    DuplicateGroup,
    Entity,
    ExportJob,
    FileRecord,
    MappingProfileRecord,
    ParserRun,
    RawImportRow,
    StatementBatch,
    Transaction,
    TransactionMatch,
)
from persistence.schemas import (
    AccountCorrectionRequest,
    CaseTagAssignRequest,
    CaseTagRequest,
    DatabaseBackupRequest,
    DatabaseBackupSettingsRequest,
    DatabaseResetRequest,
    DatabaseRestoreRequest,
    ExportRequest,
    GraphNeo4jSyncRequest,
    MappingConfirmRequest,
    OverrideRequest,
    ProcessRequest,
    ReviewRequest,
    TransactionCorrectionRequest,
)
from services.admin_service import (
    RESET_CONFIRMATION_TEXT,
    RESTORE_CONFIRMATION_TEXT,
    create_database_backup,
    get_database_backup_preview,
    get_backup_settings,
    list_database_backups,
    maybe_run_scheduled_backup,
    reset_database,
    restore_database,
    update_backup_settings,
)
from services.audit_service import log_audit, record_learning_feedback
from services.export_service import create_export_job, run_export_job
from services.file_ingestion_service import get_file_record, persist_upload
from services.graph_analysis_service import (
    get_graph_analysis,
    get_graph_neighborhood,
    list_graph_derived_edges,
    list_graph_edges,
    list_graph_findings,
    list_graph_nodes,
)
from services.neo4j_service import get_neo4j_status, sync_graph_to_neo4j
from services.persistence_pipeline_service import create_parser_run, mark_parser_run_failed
from services.account_resolution_service import best_known_account_holder_name, normalize_account_number
from services.review_service import get_account_review_payload, review_duplicate_group, review_match, update_account_fields, update_transaction_fields
from services.search_service import (
    get_account_detail,
    get_file_detail,
    list_accounts,
    list_audit_logs,
    list_duplicate_groups,
    list_export_jobs,
    list_learning_feedback_logs,
    list_files,
    list_matches,
    list_parser_runs,
    serialize_transaction,
    search_transactions,
)

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bsie.api")


def _auto_backup_poll_seconds() -> float:
    raw = os.getenv("BSIE_BACKUP_POLL_SECONDS", "60").strip() or "60"
    try:
        return max(15.0, float(raw))
    except ValueError:
        return 60.0


def _run_auto_backup_loop(stop_event: threading.Event) -> None:
    poll_seconds = _auto_backup_poll_seconds()
    logger.info("Auto-backup scheduler started (poll=%ss)", poll_seconds)
    while not stop_event.is_set():
        try:
            settings = get_backup_settings()
            backup = maybe_run_scheduled_backup(operator="system")
            if backup:
                logger.info("Scheduled backup created: %s", backup["filename"])
            elif settings.get("enabled"):
                logger.debug("Auto-backup checked; next run not due yet")
        except Exception:
            logger.exception("Scheduled backup run failed")
        stop_event.wait(poll_seconds)
    logger.info("Auto-backup scheduler stopped")


def _repair_suggested_mapping(
    suggested: dict,
    auto_suggested: dict,
    available_columns: list[str],
) -> dict:
    """Keep profile-assisted mappings deterministic and debit/credit-safe."""
    repaired = {
        field: (value if value in available_columns else None)
        for field, value in (suggested or {}).items()
    }
    auto_suggested = auto_suggested or {}

    if repaired.get("debit") and repaired.get("credit"):
        repaired["amount"] = None

    if repaired.get("amount") and repaired.get("balance") and repaired["amount"] == repaired["balance"]:
        repaired["amount"] = None

    if not repaired.get("balance") and auto_suggested.get("balance") in available_columns:
        repaired["balance"] = auto_suggested.get("balance")

    for field, value in auto_suggested.items():
        if field not in repaired or repaired.get(field) is None:
            repaired[field] = value if value in available_columns else None

    return repaired


def _normalize_feedback_text(value: object) -> str:
    return str(value or "").strip().lower()


def _normalized_mapping_snapshot(mapping: dict | None) -> dict[str, str]:
    if not isinstance(mapping, dict):
        return {}
    snapshot: dict[str, str] = {}
    for key, value in mapping.items():
        text_key = str(key or "").strip()
        if not text_key:
            continue
        text_value = str(value or "").strip()
        snapshot[text_key] = text_value
    return snapshot


def _detected_bank_key(value: object) -> str:
    if isinstance(value, dict):
        for key in ("config_key", "key", "bank_key"):
            candidate = _normalize_feedback_text(value.get(key))
            if candidate:
                return candidate
        return _normalize_feedback_text(value.get("bank"))
    return _normalize_feedback_text(value)


def _bank_feedback_status(chosen_bank: str, detected_bank: str) -> str:
    chosen = _normalize_feedback_text(chosen_bank)
    detected = _normalize_feedback_text(detected_bank)
    if not detected:
        return "accepted"
    return "confirmed" if chosen == detected else "corrected"


def _mapping_feedback_status(confirmed_mapping: dict, suggested_mapping: dict) -> str:
    suggested_snapshot = _normalized_mapping_snapshot(suggested_mapping)
    if not suggested_snapshot:
        return "accepted"

    confirmed_snapshot = _normalized_mapping_snapshot(confirmed_mapping)
    all_keys = sorted(set(confirmed_snapshot) | set(suggested_snapshot))
    for key in all_keys:
        confirmed_value = confirmed_snapshot.get(key, "")
        suggested_value = suggested_snapshot.get(key, "")
        if confirmed_value != suggested_value and (confirmed_value or suggested_value):
            return "corrected"
    return "confirmed"


def _usage_increment_for_feedback(status: str) -> int:
    return 2 if status == "corrected" else 1


def _feedback_mode(bank_feedback: str, mapping_feedback: str) -> str:
    statuses = {bank_feedback, mapping_feedback}
    if "corrected" in statuses:
        return "corrected"
    if "confirmed" in statuses:
        return "confirmed"
    return "accepted"


def _feedback_message(bank_feedback: str, mapping_feedback: str) -> str:
    mode = _feedback_mode(bank_feedback, mapping_feedback)
    if mode == "corrected":
        return "Saved and reinforced your correction"
    if mode == "confirmed":
        return "Saved and reinforced the confirmed pattern"
    return "Mapping saved"


def _masked_database_url(url: str) -> str:
    """Hide database credentials in status responses."""
    if "://" not in url or "@" not in url:
        return url
    prefix, rest = url.split("://", 1)
    credentials, suffix = rest.split("@", 1)
    username = credentials.split(":", 1)[0]
    return f"{prefix}://{username}:***@{suffix}"


# ── Startup / shutdown ────────────────────────────────────────────────────

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
    auto_backup_stop = threading.Event()
    auto_backup_thread = threading.Thread(
        target=_run_auto_backup_loop,
        args=(auto_backup_stop,),
        daemon=True,
    )
    auto_backup_thread.start()
    try:
        yield
    finally:
        auto_backup_stop.set()
        auto_backup_thread.join(timeout=2.0)


# ── FastAPI app ───────────────────────────────────────────────────────────
app = FastAPI(
    title="BSIE – Bank Statement Intelligence Engine",
    version="3.0.0",
    root_path="",
    lifespan=lifespan,
)

# Ensure the compatibility and investigation schemas exist even when the app
# is imported directly in tests without a full startup cycle.
init_db()

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Serve the React build if it exists
_REACT_DIST = STATIC_DIR / "dist"
if _REACT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_REACT_DIST / "assets")), name="assets")


# ═══════════════════════════════════════════════════════════════════════════
# UI routes
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # Serve the React SPA if built, fallback to legacy Jinja2 template
    react_index = _REACT_DIST / "index.html"
    if react_index.exists():
        return FileResponse(str(react_index))
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/favicon.svg")
async def favicon():
    """Serve the built frontend favicon from the path requested by browsers."""
    for candidate in (_REACT_DIST / "favicon.svg", STATIC_DIR / "favicon.svg"):
        if candidate.exists():
            return FileResponse(str(candidate), media_type="image/svg+xml")
    raise HTTPException(404, "favicon.svg not found")


@app.get("/app", response_class=HTMLResponse)
@app.get("/bank-manager", response_class=HTMLResponse)
async def react_spa():
    """Serve React SPA for all frontend routes."""
    react_index = _REACT_DIST / "index.html"
    if react_index.exists():
        return FileResponse(str(react_index))
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/")


@app.get("/health")
def health():
    return JSONResponse({"status": "ok"})


# ═══════════════════════════════════════════════════════════════════════════
# Helper: list available bank configs
# ═══════════════════════════════════════════════════════════════════════════

def _get_banks() -> List[Dict]:
    banks: Dict[str, Dict] = {}
    # Merge built-in configs first, then user overrides on top
    for config_dir in [BUILTIN_CONFIG_DIR, CONFIG_DIR]:
        if not config_dir.exists():
            continue
        for f in sorted(config_dir.glob("*.json")):
            try:
                cfg = json.loads(f.read_text(encoding="utf-8"))
                banks[f.stem] = {"key": f.stem, "name": cfg.get("bank_name", f.stem.upper())}
            except Exception:
                logger.debug("Skipping malformed bank config: %s", f)
    return sorted(banks.values(), key=lambda b: b["name"])


# ═══════════════════════════════════════════════════════════════════════════
# Step 1 — Upload + Detect
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...), uploaded_by: str = Form("analyst")):
    """
    Accept an Excel file, run bank + column auto-detection, and return:
    - detected bank
    - suggested column mapping
    - all column names
    - sample rows for display
    - matching memory profile (if any)
    """
    if not file.filename:
        raise HTTPException(400, "No filename")

    contents = await file.read()
    persisted = persist_upload(
        content=contents,
        original_filename=file.filename,
        uploaded_by=(uploaded_by or "analyst").strip() or "analyst",
        mime_type=file.content_type,
    )
    save_path = Path(persisted["stored_path"])
    job_id = str(uuid.uuid4())

    try:
        if save_path.suffix.lower() == ".ofx":
            data_df = parse_ofx_file(save_path)
            identity = infer_identity_from_ofx(save_path, data_df)
            sample_rows = data_df.head(5).fillna("").to_dict(orient="records")
            return JSONResponse({
                "job_id": job_id,
                "file_id": persisted["file_id"],
                "temp_file_path": str(save_path),
                "file_name": file.filename,
                "duplicate_file_status": persisted["duplicate_file_status"],
                "prior_ingestions": persisted["prior_ingestions"],
                "detected_bank": {
                    "bank": "OFX",
                    "config_key": "ofx",
                    "key": "ofx",
                    "confidence": 1.0,
                    "ambiguous": False,
                    "scores": {"ofx": 1.0},
                    "top_candidates": ["ofx"],
                    "evidence": {"positive": ["source:ofx"], "negative": [], "layout": "ofx"},
                },
                "suggested_mapping": {},
                "confidence_scores": {},
                "all_columns": list(data_df.columns),
                "unmatched_columns": [],
                "required_found": True,
                "memory_match": None,
                "bank_memory_match": None,
                "sample_rows": sample_rows,
                "banks": _get_banks(),
                "header_row": 0,
                "sheet_name": "OFX",
                "account_guess": identity.get("account", ""),
                "name_guess": identity.get("name", ""),
            })

        sheet_pick = find_best_sheet_and_header(save_path)
        header_row = int(sheet_pick["header_row"])
        sheet_name = str(sheet_pick["sheet_name"])
        data_df = pd.read_excel(
            str(save_path),
            sheet_name=sheet_name,
            header=header_row, dtype=str,
        ).dropna(how="all")
        data_df.columns = [str(c).strip() for c in data_df.columns]

        bank_result  = detect_bank(data_df, extra_text=f"{file.filename} {sheet_name}", sheet_name=sheet_name)
        col_result   = detect_columns(data_df)
        profile      = find_matching_profile(list(data_df.columns), bank=bank_result.get("config_key", "") or "")
        bank_memory  = find_matching_bank_fingerprint(list(data_df.columns), sheet_name=sheet_name)
        sample_rows = data_df.head(5).fillna("").to_dict(orient="records")

        auto_suggested = dict(col_result["suggested_mapping"])
        suggested = dict(auto_suggested)
        if profile:
            suggested = _repair_suggested_mapping(
                {**auto_suggested, **profile["mapping"]},
                auto_suggested,
                list(data_df.columns),
            )
            memory_match = {"profile_id": profile["profile_id"], "bank": profile["bank"],
                            "usage_count": profile["usage_count"]}
        else:
            suggested = _repair_suggested_mapping(suggested, auto_suggested, list(data_df.columns))
            memory_match = None

        return JSONResponse({
            "job_id":           job_id,
            "file_id":          persisted["file_id"],
            "temp_file_path":   str(save_path),
            "file_name":        file.filename,
            "duplicate_file_status": persisted["duplicate_file_status"],
            "prior_ingestions": persisted["prior_ingestions"],
            "detected_bank":    bank_result,
            "suggested_mapping": suggested,
            "confidence_scores": col_result["confidence_scores"],
            "all_columns":      col_result["all_columns"],
            "unmatched_columns": col_result["unmatched_columns"],
            "required_found":   col_result["required_found"],
            "memory_match":     memory_match,
            "bank_memory_match": bank_memory,
            "sample_rows":      sample_rows,
            "banks":            _get_banks(),
            "header_row":       header_row,
            "sheet_name":       sheet_name,
        })

    except Exception as e:
        logger.exception(f"Upload failed: {e}")
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════════════════════════
# Step 2 — Confirm mapping
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/mapping/confirm")
async def api_confirm_mapping(request: Request):
    """Validate and store confirmed column mapping."""
    payload = await request.json()
    body = MappingConfirmRequest.model_validate(payload)
    bank = body.bank or "UNKNOWN"
    mapping = body.mapping
    columns = body.columns
    header_row = int(body.header_row or 0)
    sheet_name = str(body.sheet_name or "")
    reviewer = str(body.reviewer or "analyst").strip() or "analyst"
    detected_bank = _detected_bank_key(
        payload.get("detected_bank")
        if "detected_bank" in payload
        else payload.get("detectedBank"),
    )
    suggested_mapping = payload.get("suggested_mapping") or payload.get("suggestedMapping") or {}

    if not mapping:
        raise HTTPException(400, "mapping is required")

    from core.mapping_memory import save_profile
    bank_feedback = _bank_feedback_status(bank, detected_bank)
    mapping_feedback = _mapping_feedback_status(mapping, suggested_mapping)
    profile = save_profile(
        bank,
        columns,
        mapping,
        usage_increment=_usage_increment_for_feedback(mapping_feedback),
    )
    fingerprint = None
    if bank and str(bank).strip().lower() not in {"", "unknown", "generic"}:
        fingerprint = save_bank_fingerprint(
            str(bank).strip(),
            columns,
            header_row=header_row,
            sheet_name=sheet_name,
            usage_increment=_usage_increment_for_feedback(bank_feedback),
        )

    feedback_mode = _feedback_mode(bank_feedback, mapping_feedback)
    learning_feedback_count = 0
    with get_db_session() as session:
        record_learning_feedback(
            session,
            learning_domain="mapping_memory",
            action_type="mapping_confirmation",
            source_object_type="mapping_profile",
            source_object_id=profile["profile_id"],
            feedback_status=mapping_feedback,
            changed_by=reviewer,
            old_value=suggested_mapping or None,
            new_value=mapping,
            extra_context={
                "bank": bank,
                "columns": list(columns or []),
                "usage_increment": _usage_increment_for_feedback(mapping_feedback),
            },
        )
        learning_feedback_count += 1
        if fingerprint:
            record_learning_feedback(
                session,
                learning_domain="bank_memory",
                action_type="bank_confirmation",
                source_object_type="bank_fingerprint",
                source_object_id=fingerprint["fingerprint_id"],
                feedback_status=bank_feedback,
                changed_by=reviewer,
                old_value={"detected_bank": detected_bank or None},
                new_value={"selected_bank": bank},
                extra_context={
                    "header_row": header_row,
                    "sheet_name": sheet_name,
                    "usage_increment": _usage_increment_for_feedback(bank_feedback),
                },
            )
            learning_feedback_count += 1
        session.commit()
    return JSONResponse({
        "status": "ok",
        "profile_id": profile["profile_id"],
        "fingerprint_id": fingerprint["fingerprint_id"] if fingerprint else None,
        "bank_feedback": bank_feedback,
        "mapping_feedback": mapping_feedback,
        "feedback_mode": feedback_mode,
        "message": _feedback_message(bank_feedback, mapping_feedback),
        "learning_feedback_count": learning_feedback_count,
    })


# ═══════════════════════════════════════════════════════════════════════════
# Step 3 — Process
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/process")
async def api_process(body: ProcessRequest):
    """
    Start the 14-step pipeline in a background thread.
    Returns {job_id} immediately.
    """
    temp_file_path = str(body.temp_file_path or "").strip()
    file_id = str(body.file_id or "").strip()
    bank_key = str(body.bank_key or "").strip()
    account = str(body.account or "").strip()
    name = str(body.name or "").strip()
    operator = str(body.operator or "analyst").strip() or "analyst"
    confirmed_mapping = body.confirmed_mapping

    file_record = None
    if file_id:
        file_record = get_file_record(file_id)
        if file_record:
            temp_file_path = temp_file_path or file_record.stored_path
    if not temp_file_path or not Path(temp_file_path).exists():
        raise HTTPException(400, "temp_file_path missing or file not found")
    if not account or not account.isdigit() or len(account) not in (10, 12):
        raise HTTPException(400, "account must be exactly 10 or 12 digits")

    job_id = str(uuid.uuid4())
    db_create_job(job_id, account=account)

    if not file_id and file_record is None:
        inferred_upload = persist_upload(
            content=Path(temp_file_path).read_bytes(),
            original_filename=Path(temp_file_path).name,
            uploaded_by=operator,
            mime_type=None,
        )
        file_id = inferred_upload["file_id"]

    parser_run = create_parser_run(
        file_id=file_id,
        bank_detected=bank_key,
        confirmed_mapping=confirmed_mapping,
        operator=operator,
    )

    _dispatch_pipeline(
        job_id,
        temp_file_path,
        bank_key,
        account,
        name,
        confirmed_mapping,
        file_id=file_id,
        parser_run_id=parser_run["parser_run_id"],
        operator=operator,
        header_row=body.header_row,
        sheet_name=body.sheet_name,
    )
    return JSONResponse({"job_id": job_id, "file_id": file_id, "parser_run_id": parser_run["parser_run_id"]})


@app.post("/api/process-folder")
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


@app.get("/api/bulk/{run_id}/analytics")
async def api_bulk_analytics(run_id: str):
    safe_run_id = "".join(c for c in run_id if c.isdigit() or c == "_")
    if not safe_run_id:
        raise HTTPException(400, "Invalid run_id")
    analytics_path = OUTPUT_DIR / "bulk_runs" / safe_run_id / "case_analytics.json"
    if not analytics_path.exists():
        raise HTTPException(404, "Bulk analytics not found")
    return JSONResponse(json.loads(analytics_path.read_text(encoding="utf-8")))


@app.get("/api/job/{job_id}")
async def api_job_status(job_id: str):
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


# ═══════════════════════════════════════════════════════════════════════════
# Results
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/results/{account}")
async def api_results(account: str, page: int = 1, page_size: int = 100):
    """Return paginated transaction results for an account."""
    safe = "".join(c for c in account if c.isdigit())
    processed_dir = OUTPUT_DIR / safe / "processed"
    meta = {}
    rows = []
    total = 0

    with get_db_session() as session:
        account_row = session.scalars(
            select(Account).where(Account.normalized_account_number == safe).order_by(Account.last_seen_at.desc())
        ).first()
        if account_row:
            all_rows = session.scalars(
                select(Transaction).where(Transaction.account_id == account_row.id).order_by(Transaction.transaction_datetime.desc())
            ).all()
            total = len(all_rows)
            start = (page - 1) * page_size
            end = start + page_size
            rows = [serialize_transaction(row) for row in all_rows[start:end]]
            latest_run = session.scalars(
                select(ParserRun).join(StatementBatch, StatementBatch.parser_run_id == ParserRun.id).where(
                    StatementBatch.account_id == account_row.id
                ).order_by(ParserRun.started_at.desc())
            ).first()
            if latest_run:
                meta = latest_run.summary_json or {}

    txn_path = processed_dir / "transactions.csv"
    if not rows and txn_path.exists():
        df = pd.read_csv(txn_path, dtype=str, encoding="utf-8-sig")
        df = df.fillna("")
        total = len(df)
        start = (page - 1) * page_size
        end = start + page_size
        rows = df.iloc[start:end].to_dict(orient="records")

    meta_path = OUTPUT_DIR / safe / "meta.json"
    if not meta and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not rows and not txn_path.exists():
        raise HTTPException(404, f"No results for account {safe}")

    entities = []
    entities_path = processed_dir / "entities.csv"
    if entities_path.exists():
        entities_df = pd.read_csv(entities_path, dtype=str, encoding="utf-8-sig").fillna("")
        entities = entities_df.to_dict(orient="records")

    links = []
    links_path = processed_dir / "links.csv"
    if links_path.exists():
        links_df = pd.read_csv(links_path, dtype=str, encoding="utf-8-sig").fillna("")
        links = links_df.to_dict(orient="records")

    return JSONResponse({
        "account":    safe,
        "meta":       meta,
        "total":      total,
        "page":       page,
        "page_size":  page_size,
        "items":      rows,
        "rows":       rows,
        "entities":   entities,
        "links":      links,
    })


# ═══════════════════════════════════════════════════════════════════════════
# Investigation / Search
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/files")
async def api_files(limit: int = 100, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_files(session, limit=limit, offset=offset)})


@app.get("/api/files/{file_id}")
async def api_file_detail(file_id: str):
    with get_db_session() as session:
        payload = get_file_detail(session, file_id)
    if not payload:
        raise HTTPException(404, "File not found")
    return JSONResponse(payload)


@app.get("/api/admin/db-status")
async def api_db_status():
    inspector = inspect(engine)
    table_names = sorted(inspector.get_table_names())
    key_counts: dict[str, int] = {}

    with get_db_session() as session:
        count_targets = {
            "files": FileRecord,
            "parser_runs": ParserRun,
            "statement_batches": StatementBatch,
            "raw_import_rows": RawImportRow,
            "accounts": Account,
            "transactions": Transaction,
            "entities": Entity,
            "duplicate_groups": DuplicateGroup,
            "transaction_matches": TransactionMatch,
            "audit_logs": AuditLog,
            "mapping_profiles": MappingProfileRecord,
            "export_jobs": ExportJob,
        }
        for label, model in count_targets.items():
            key_counts[label] = int(session.scalar(select(func.count()).select_from(model)) or 0)

    return JSONResponse(
        {
            "database_configured": bool(DATABASE_URL),
            "database_backend": "sqlite" if IS_SQLITE else "postgresql",
            "database_runtime_source": DATABASE_RUNTIME_SOURCE,
            "database_url_masked": _masked_database_url(DATABASE_URL),
            "table_count": len(table_names),
            "tables": table_names,
            "key_record_counts": key_counts,
            "has_investigation_schema": all(
                table in table_names
                for table in [
                    "files",
                    "parser_runs",
                    "statement_batches",
                    "raw_import_rows",
                    "accounts",
                    "transactions",
                    "entities",
                    "transaction_matches",
                    "audit_logs",
                    "export_jobs",
                ]
            ),
        }
    )


@app.get("/api/admin/backups")
async def api_list_backups():
    return JSONResponse(
        {
            "items": list_database_backups(),
            "settings": get_backup_settings(),
            "reset_confirmation_text": RESET_CONFIRMATION_TEXT,
            "restore_confirmation_text": RESTORE_CONFIRMATION_TEXT,
        }
    )


@app.get("/api/admin/backup-settings")
async def api_get_backup_settings():
    return JSONResponse(get_backup_settings())


@app.post("/api/admin/backup-settings")
async def api_update_backup_settings(body: DatabaseBackupSettingsRequest):
    try:
        payload = update_backup_settings(
            enabled=body.enabled,
            interval_hours=body.interval_hours,
            backup_format=body.backup_format,
            retention_enabled=body.retention_enabled,
            retain_count=body.retain_count,
            updated_by=body.updated_by,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse(payload)


@app.get("/api/admin/backups/{backup_name}/preview")
async def api_backup_preview(backup_name: str):
    try:
        payload = get_database_backup_preview(backup_name)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return JSONResponse(payload)


@app.post("/api/admin/backup")
async def api_create_backup(body: DatabaseBackupRequest):
    try:
        payload = create_database_backup(operator=body.operator, note=body.note, backup_format=body.backup_format)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return JSONResponse(payload)


@app.post("/api/admin/reset")
async def api_reset_database(body: DatabaseResetRequest):
    try:
        payload = reset_database(
            confirm_text=body.confirm_text,
            operator=body.operator,
            note=body.note,
            create_pre_reset_backup=body.create_pre_reset_backup,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse(payload)


@app.post("/api/admin/restore")
async def api_restore_database(body: DatabaseRestoreRequest):
    try:
        payload = restore_database(
            backup_filename=body.backup_filename,
            confirm_text=body.confirm_text,
            operator=body.operator,
            note=body.note,
            create_pre_restore_backup=body.create_pre_restore_backup,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return JSONResponse(payload)


@app.get("/api/parser-runs")
async def api_parser_runs(limit: int = 100, offset: int = 0, file_id: str = ""):
    with get_db_session() as session:
        return JSONResponse({"items": list_parser_runs(session, limit=limit, offset=offset, file_id=file_id or None)})


@app.get("/api/parser-runs/{parser_run_id}")
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


@app.post("/api/parser-runs/{parser_run_id}/reprocess")
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
    _dispatch_pipeline(
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


@app.get("/api/accounts")
async def api_accounts(q: str = "", limit: int = 100, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_accounts(session, q=q, limit=limit, offset=offset)})


@app.get("/api/accounts/remembered-name")
async def api_account_remembered_name(bank_key: str = "", account: str = ""):
    resolved_bank = str(bank_key or "").strip()
    raw_account = str(account or "").strip()
    normalized_account = normalize_account_number(raw_account) or ""
    remembered_name = ""

    if normalized_account:
        with get_db_session() as session:
            remembered_name = best_known_account_holder_name(
                session,
                bank_name=resolved_bank,
                raw_account_number=raw_account,
            ) or ""

    return JSONResponse({
        "bank_key": resolved_bank,
        "account": raw_account,
        "normalized_account_number": normalized_account,
        "remembered_name": remembered_name,
        "matched": bool(remembered_name),
    })


@app.get("/api/accounts/{account_id}")
async def api_account_detail(account_id: str):
    with get_db_session() as session:
        payload = get_account_detail(session, account_id)
    if not payload:
        raise HTTPException(404, "Account not found")
    return JSONResponse(payload)


@app.get("/api/accounts/{account_id}/review")
async def api_account_review_payload(account_id: str):
    with get_db_session() as session:
        payload = get_account_review_payload(session, account_id)
    if not payload:
        raise HTTPException(404, "Account not found")
    return JSONResponse(payload)


@app.get("/api/transactions/search")
async def api_search_transactions(
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    limit: int = 100,
    offset: int = 0,
):
    with get_db_session() as session:
        rows = search_transactions(
            session,
            q=q,
            account=account,
            counterparty=counterparty,
            amount_min=amount_min,
            amount_max=amount_max,
            date_from=date_from,
            date_to=date_to,
            bank=bank,
            reference_no=reference_no,
            transaction_type=transaction_type,
            duplicate_status=duplicate_status,
            review_status=review_status,
            match_status=match_status,
            file_id=file_id,
            parser_run_id=parser_run_id,
            limit=limit,
            offset=offset,
        )
    return JSONResponse({"items": rows})


@app.get("/api/transactions/{transaction_id}")
async def api_transaction_detail(transaction_id: str):
    with get_db_session() as session:
        row = session.get(Transaction, transaction_id)
        if not row:
            raise HTTPException(404, "Transaction not found")
        return JSONResponse(serialize_transaction(row))


@app.get("/api/graph-analysis")
async def api_graph_analysis(
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    limit: int = 5000,
):
    with get_db_session() as session:
        payload = get_graph_analysis(
            session,
            q=q,
            account=account,
            counterparty=counterparty,
            amount_min=amount_min,
            amount_max=amount_max,
            date_from=date_from,
            date_to=date_to,
            bank=bank,
            reference_no=reference_no,
            transaction_type=transaction_type,
            duplicate_status=duplicate_status,
            review_status=review_status,
            match_status=match_status,
            file_id=file_id,
            parser_run_id=parser_run_id,
            limit=limit,
        )
    return JSONResponse(payload)


def _graph_filter_payload(
    *,
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
) -> dict:
    return {
        "q": q,
        "account": account,
        "counterparty": counterparty,
        "amount_min": amount_min,
        "amount_max": amount_max,
        "date_from": date_from,
        "date_to": date_to,
        "bank": bank,
        "reference_no": reference_no,
        "transaction_type": transaction_type,
        "duplicate_status": duplicate_status,
        "review_status": review_status,
        "match_status": match_status,
        "file_id": file_id,
        "parser_run_id": parser_run_id,
    }


@app.get("/api/graph/nodes")
async def api_graph_nodes(
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    limit: int = 5000,
):
    filters = _graph_filter_payload(
        q=q,
        account=account,
        counterparty=counterparty,
        amount_min=amount_min,
        amount_max=amount_max,
        date_from=date_from,
        date_to=date_to,
        bank=bank,
        reference_no=reference_no,
        transaction_type=transaction_type,
        duplicate_status=duplicate_status,
        review_status=review_status,
        match_status=match_status,
        file_id=file_id,
        parser_run_id=parser_run_id,
    )
    with get_db_session() as session:
        items = list_graph_nodes(session, limit=limit, **filters)
    effective_limit = max(1, min(limit, 5000))
    return JSONResponse({
        "items": items,
        "meta": {
            "requested_limit": limit,
            "effective_limit": effective_limit,
            "returned_count": len(items),
            "truncated": limit > effective_limit,
        },
    })


@app.get("/api/graph/edges")
async def api_graph_edges(
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    limit: int = 5000,
    include_relationships: bool = True,
):
    filters = _graph_filter_payload(
        q=q,
        account=account,
        counterparty=counterparty,
        amount_min=amount_min,
        amount_max=amount_max,
        date_from=date_from,
        date_to=date_to,
        bank=bank,
        reference_no=reference_no,
        transaction_type=transaction_type,
        duplicate_status=duplicate_status,
        review_status=review_status,
        match_status=match_status,
        file_id=file_id,
        parser_run_id=parser_run_id,
    )
    with get_db_session() as session:
        items = list_graph_edges(session, limit=limit, include_relationships=include_relationships, **filters)
    effective_limit = max(1, min(limit, 5000))
    return JSONResponse({
        "items": items,
        "meta": {
            "requested_limit": limit,
            "effective_limit": effective_limit,
            "returned_count": len(items),
            "include_relationships": include_relationships,
            "truncated": limit > effective_limit,
        },
    })


@app.get("/api/graph/derived-edges")
async def api_graph_derived_edges(
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    limit: int = 5000,
):
    filters = _graph_filter_payload(
        q=q,
        account=account,
        counterparty=counterparty,
        amount_min=amount_min,
        amount_max=amount_max,
        date_from=date_from,
        date_to=date_to,
        bank=bank,
        reference_no=reference_no,
        transaction_type=transaction_type,
        duplicate_status=duplicate_status,
        review_status=review_status,
        match_status=match_status,
        file_id=file_id,
        parser_run_id=parser_run_id,
    )
    with get_db_session() as session:
        items = list_graph_derived_edges(session, limit=limit, **filters)
    effective_limit = max(1, min(limit, 5000))
    return JSONResponse({
        "items": items,
        "meta": {
            "requested_limit": limit,
            "effective_limit": effective_limit,
            "returned_count": len(items),
            "truncated": limit > effective_limit,
        },
    })


@app.get("/api/graph/findings")
async def api_graph_findings(
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    severity: str = "",
    rule_type: str = "",
    limit: int = 5000,
):
    filters = _graph_filter_payload(
        q=q,
        account=account,
        counterparty=counterparty,
        amount_min=amount_min,
        amount_max=amount_max,
        date_from=date_from,
        date_to=date_to,
        bank=bank,
        reference_no=reference_no,
        transaction_type=transaction_type,
        duplicate_status=duplicate_status,
        review_status=review_status,
        match_status=match_status,
        file_id=file_id,
        parser_run_id=parser_run_id,
    )
    with get_db_session() as session:
        items = list_graph_findings(session, limit=limit, severity=severity, rule_type=rule_type, **filters)
    effective_limit = max(1, min(limit, 5000))
    return JSONResponse({
        "items": items,
        "meta": {
            "requested_limit": limit,
            "effective_limit": effective_limit,
            "returned_count": len(items),
            "severity": severity,
            "rule_type": rule_type,
            "truncated": limit > effective_limit,
        },
    })


@app.get("/api/graph/neighborhood/{node_id}")
async def api_graph_neighborhood(
    node_id: str,
    q: str = "",
    account: str = "",
    counterparty: str = "",
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: str = "",
    date_to: str = "",
    bank: str = "",
    reference_no: str = "",
    transaction_type: str = "",
    duplicate_status: str = "",
    review_status: str = "",
    match_status: str = "",
    file_id: str = "",
    parser_run_id: str = "",
    limit: int = 5000,
    include_relationships: bool = True,
    max_nodes: int = 14,
    max_edges: int = 24,
):
    filters = _graph_filter_payload(
        q=q,
        account=account,
        counterparty=counterparty,
        amount_min=amount_min,
        amount_max=amount_max,
        date_from=date_from,
        date_to=date_to,
        bank=bank,
        reference_no=reference_no,
        transaction_type=transaction_type,
        duplicate_status=duplicate_status,
        review_status=review_status,
        match_status=match_status,
        file_id=file_id,
        parser_run_id=parser_run_id,
    )
    with get_db_session() as session:
        payload = get_graph_neighborhood(
            session,
            node_id=node_id,
            limit=limit,
            include_relationships=include_relationships,
            max_nodes=max_nodes,
            max_edges=max_edges,
            **filters,
        )
    return JSONResponse(payload)


@app.get("/api/graph/neo4j-status")
async def api_graph_neo4j_status():
    return JSONResponse(get_neo4j_status())


@app.post("/api/graph/neo4j-sync")
async def api_graph_neo4j_sync(body: GraphNeo4jSyncRequest):
    with get_db_session() as session:
        payload = sync_graph_to_neo4j(
            session,
            limit=body.limit,
            include_findings=body.include_findings,
            **(body.filters or {}),
        )
    return JSONResponse(payload)


@app.get("/api/duplicates")
async def api_duplicates(limit: int = 100, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_duplicate_groups(session, limit=limit, offset=offset)})


@app.post("/api/duplicates/{group_id}/review")
async def api_review_duplicate(group_id: str, body: ReviewRequest):
    with get_db_session() as session:
        group = review_duplicate_group(
            session,
            group_id=group_id,
            decision_value=body.decision_value,
            reviewer=body.reviewer,
            reviewer_note=body.reviewer_note,
        )
        if not group:
            raise HTTPException(404, "Duplicate group not found")
        session.commit()
        return JSONResponse({"status": "ok", "group_id": group.id, "resolution_status": group.resolution_status})


@app.get("/api/matches")
async def api_matches(status: str = "", limit: int = 100, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_matches(session, status=status, limit=limit, offset=offset)})


@app.post("/api/matches/{match_id}/review")
async def api_review_match(match_id: str, body: ReviewRequest):
    with get_db_session() as session:
        match = review_match(
            session,
            match_id=match_id,
            decision_value=body.decision_value,
            reviewer=body.reviewer,
            reviewer_note=body.reviewer_note,
        )
        if not match:
            raise HTTPException(404, "Match not found")
        session.commit()
        return JSONResponse({"status": "ok", "match_id": match.id, "match_status": match.status})


@app.post("/api/transactions/{transaction_id}/review")
async def api_review_transaction(transaction_id: str, body: TransactionCorrectionRequest):
    with get_db_session() as session:
        transaction = update_transaction_fields(
            session,
            transaction_id=transaction_id,
            changes=body.changes,
            reviewer=body.reviewer,
            reason=body.reason,
        )
        if not transaction:
            raise HTTPException(404, "Transaction not found")
        session.commit()
        return JSONResponse({"status": "ok", "transaction_id": transaction.id, "review_status": transaction.review_status})


@app.post("/api/accounts/{account_id}/review")
async def api_review_account(account_id: str, body: AccountCorrectionRequest):
    with get_db_session() as session:
        account_row = update_account_fields(
            session,
            account_id=account_id,
            changes=body.changes,
            reviewer=body.reviewer,
            reason=body.reason,
        )
        if not account_row:
            raise HTTPException(404, "Account not found")
        session.commit()
        return JSONResponse({"status": "ok", "account_id": account_row.id})


@app.get("/api/audit-logs")
async def api_audit_logs(object_type: str = "", object_id: str = "", limit: int = 200, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_audit_logs(session, object_type=object_type, object_id=object_id, limit=limit, offset=offset)})


@app.get("/api/learning-feedback")
async def api_learning_feedback(object_id: str = "", limit: int = 200, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_learning_feedback_logs(session, object_id=object_id, limit=limit, offset=offset)})


@app.get("/api/export-jobs")
async def api_export_jobs(limit: int = 100, offset: int = 0):
    with get_db_session() as session:
        return JSONResponse({"items": list_export_jobs(session, limit=limit, offset=offset)})


@app.post("/api/exports")
async def api_create_export(body: ExportRequest):
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


@app.get("/api/case-tags")
async def api_case_tags():
    with get_db_session() as session:
        rows = session.scalars(select(CaseTag).order_by(CaseTag.tag.asc())).all()
        return JSONResponse({
            "items": [
                {
                    "id": row.id,
                    "tag": row.tag,
                    "description": row.description,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
        })


@app.post("/api/case-tags")
async def api_create_case_tag(body: CaseTagRequest):
    with get_db_session() as session:
        row = CaseTag(tag=body.tag.strip(), description=body.description or None)
        session.add(row)
        session.commit()
        return JSONResponse({"id": row.id, "tag": row.tag, "description": row.description})


@app.post("/api/case-tags/assign")
async def api_assign_case_tag(body: CaseTagAssignRequest):
    with get_db_session() as session:
        link = CaseTagLink(
            case_tag_id=body.case_tag_id,
            object_type=body.object_type,
            object_id=body.object_id,
        )
        session.add(link)
        session.commit()
        return JSONResponse({"status": "ok", "link_id": link.id})


# ═══════════════════════════════════════════════════════════════════════════
# Overrides
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/override")
async def api_add_override(body: OverrideRequest):
    """Add or update a manual relationship override."""
    tid = body.transaction_id.strip()
    # Accept both API-native and frontend-react payload keys for compatibility.
    frm = (body.from_account or body.override_from_account or "").strip()
    to = (body.to_account or body.override_to_account or "").strip()
    reason = body.reason or body.override_reason or ""
    by = body.override_by or "analyst"
    account_number = (body.account_number or body.account or "").strip()

    if not tid or not frm or not to:
        raise HTTPException(400, "transaction_id, from_account, and to_account are required")

    record = add_override(tid, frm, to, reason, by, account_number=account_number)

    with get_db_session() as session:
        log_audit(
            session,
            object_type="override",
            object_id=f"{account_number or 'global'}::{tid}",
            action_type="upsert_override",
            field_name="override_flow",
            old_value=None,
            new_value=record,
            changed_by=by,
            reason=reason,
        )
        session.commit()

    # Re-apply overrides to persisted CSV if it exists
    _reapply_overrides_to_csv(tid, account_number=account_number)

    return JSONResponse({"status": "ok", "override": record})


@app.delete("/api/override/{transaction_id}")
async def api_remove_override(transaction_id: str, account_number: str = "", operator: str = "analyst"):
    removed = remove_override(transaction_id, account_number=account_number)
    if not removed:
        raise HTTPException(404, "Override not found")
    changed_by = str(operator or "analyst").strip() or "analyst"
    with get_db_session() as session:
        log_audit(
            session,
            object_type="override",
            object_id=f"{account_number or 'global'}::{transaction_id}",
            action_type="delete_override",
            changed_by=changed_by,
            reason="override removed",
        )
        session.commit()
    return JSONResponse({"status": "removed"})


@app.get("/api/overrides")
async def api_list_overrides():
    return JSONResponse({"overrides": get_all_overrides()})


def _reapply_overrides_to_csv(changed_txn_id: str, account_number: str = "") -> None:
    """Re-run override application on all account CSVs that contain the transaction."""
    for acct_dir in OUTPUT_DIR.iterdir():
        if not acct_dir.is_dir():
            continue
        if account_number and acct_dir.name != "".join(c for c in account_number if c.isdigit()):
            continue
        txn_csv = acct_dir / "processed" / "transactions.csv"
        if not txn_csv.exists():
            continue
        try:
            df = pd.read_csv(txn_csv, dtype=str, encoding="utf-8-sig").fillna("")
            if changed_txn_id not in df.get("transaction_id", pd.Series()).values:
                continue
            df = apply_overrides_to_df(df, account_number=acct_dir.name)
            df.to_csv(txn_csv, index=False, encoding="utf-8-sig")
        except Exception as e:
            logger.warning(f"Could not reapply overrides to {txn_csv}: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# Mapping profiles
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/profiles")
async def api_list_profiles():
    return JSONResponse({"profiles": list_profiles()})


# ═══════════════════════════════════════════════════════════════════════════
# Download
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/download/{account}/{file_path:path}")
async def api_download(account: str, file_path: str, download_name: str = ""):
    safe = "".join(c for c in account if c.isdigit())
    base = (OUTPUT_DIR / safe).resolve()
    full = (base / file_path).resolve()
    if not str(full).startswith(str(base)):
        raise HTTPException(400, "Invalid file path")
    if not full.exists() or not full.is_file():
        raise HTTPException(404, "File not found")
    preferred_name = Path(str(download_name or "")).name.strip() or full.name
    return FileResponse(str(full), filename=preferred_name)


@app.get("/api/download-bulk/{run_id}/{file_path:path}")
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

    preferred_name = Path(str(download_name or "")).name.strip() or full.name
    return FileResponse(str(full), filename=preferred_name)


@app.get("/api/download-export/{job_id}/{file_path:path}")
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
    preferred_name = Path(str(download_name or "")).name.strip() or full.name
    return FileResponse(str(full), filename=preferred_name)


@app.get("/api/download-backup/{backup_name}")
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
    preferred_name = Path(str(download_name or "")).name.strip() or full.name
    return FileResponse(str(full), filename=preferred_name)


# ═══════════════════════════════════════════════════════════════════════════
# Banks list
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/banks")
async def api_banks():
    return JSONResponse(_get_banks())


@app.get("/api/banks/{key}")
async def api_bank_get(key: str):
    """Return full config for a specific bank (user override takes priority)."""
    f = CONFIG_DIR / f"{key}.json"
    if not f.exists():
        f = BUILTIN_CONFIG_DIR / f"{key}.json"
    if not f.exists():
        raise HTTPException(404, f"Bank '{key}' not found")
    cfg = json.loads(f.read_text(encoding="utf-8"))
    return JSONResponse({"key": key, **cfg})


@app.post("/api/banks")
async def api_bank_create(request: Request):
    """Create or update a bank config file from JSON body."""
    body = await request.json()
    key  = body.get("key", "").strip().lower().replace(" ", "_")
    if not key:
        raise HTTPException(400, "Bank key is required")
    # Protect built-in banks from overwrite unless flagged
    builtin = {"generic", "scb", "kbank", "ktb", "bbl", "bay", "ttb", "gsb", "baac"}
    if key in builtin and not body.get("overwrite_builtin"):
        raise HTTPException(400, f"'{key}' is a built-in bank. Set overwrite_builtin=true to overwrite.")
    cfg = {
        "bank_name":       body.get("bank_name", key.upper()),
        "sheet_index":     int(body.get("sheet_index", 0)),
        "header_row":      int(body.get("header_row", 0)),
        "format_type":     body.get("format_type", "standard"),
        "currency":        body.get("currency", "THB"),
        "amount_mode":     body.get("amount_mode", "signed"),
        "column_mapping":  body.get("column_mapping", {}),
    }
    dest = CONFIG_DIR / f"{key}.json"
    dest.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Bank config saved: %s", dest)
    return JSONResponse({"status": "ok", "key": key, "name": cfg["bank_name"]})


@app.delete("/api/banks/{key}")
async def api_bank_delete(key: str):
    """Delete a bank config. Built-in banks are protected."""
    builtin = {"generic", "scb", "kbank", "ktb", "bbl", "bay", "ttb", "gsb", "baac"}
    if key in builtin:
        raise HTTPException(400, f"Cannot delete built-in bank '{key}'")
    f = CONFIG_DIR / f"{key}.json"
    if not f.exists():
        raise HTTPException(404, f"Bank '{key}' not found")
    f.unlink()
    return JSONResponse({"status": "deleted", "key": key})


@app.post("/api/banks/learn")
async def api_bank_learn(request: Request):
    """
    Learn a new bank template from a confirmed column mapping.
    Accepts: { key, bank_name, format_type, amount_mode, confirmed_mapping, all_columns }
    Generates a bank config with the actual column names as aliases.
    """
    body = await request.json()
    key  = body.get("key", "").strip().lower().replace(" ", "_")
    if not key:
        raise HTTPException(400, "Bank key is required")

    confirmed_mapping: dict = body.get("confirmed_mapping", {})
    # Build column_mapping: each logical field → [the actual column name used]
    col_mapping = {}
    for field, col in confirmed_mapping.items():
        if col:
            col_mapping[field] = [col]

    cfg = {
        "bank_name":      body.get("bank_name", key.upper()),
        "sheet_index":    int(body.get("sheet_index", 0)),
        "header_row":     int(body.get("header_row", 0)),
        "format_type":    body.get("format_type", "standard"),
        "currency":       "THB",
        "amount_mode":    body.get("amount_mode", "signed"),
        "column_mapping": col_mapping,
    }
    dest = CONFIG_DIR / f"{key}.json"
    dest.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Learned new bank config: %s (%s)", key, cfg["bank_name"])
    return JSONResponse({"status": "learned", "key": key, "name": cfg["bank_name"]})


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8757))
    logger.info("=" * 60)
    logger.info("  BSIE – Bank Statement Intelligence Engine v3.0")
    logger.info("  Web App  →  http://127.0.0.1:%d", port)
    logger.info("=" * 60)
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=False, log_level="info")
