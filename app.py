"""
app.py
------
BSIE – Bank Statement Intelligence Engine
FastAPI web application backend.

Workflow:
  POST /api/upload          Upload Excel, detect bank + columns, return suggestions
  POST /api/mapping/confirm Confirm / edit column mapping, save profile
  POST /api/process         Run full 14-step pipeline (background)
  GET  /api/job/{id}        Poll pipeline job status
  GET  /api/results/{acct}  Retrieve processed transaction data
  POST /api/override        Add / update a relationship override
  DELETE /api/override/{id} Remove an override
  GET  /api/overrides       List all overrides
  GET  /api/profiles        List saved mapping profiles
  GET  /api/download/{acct}/{path} Download output file
"""

import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ── Path setup ───────────────────────────────────────────────────────────
# _BASE is intentionally retained: sys.path.insert ensures `pipeline`, `core`,
# etc. are importable when app.py is loaded by uvicorn in both source mode and
# bundle mode (PyInstaller sets sys._MEIPASS but uvicorn imports app lazily).
_BASE = Path(__file__).parent
sys.path.insert(0, str(_BASE))

# ── Bundled mode detection ────────────────────────────────────────────────
# When frozen by PyInstaller, skip Celery+Redis and run pipeline in-thread.
IS_BUNDLED = getattr(sys, "frozen", False)

from paths import (
    STATIC_DIR, TEMPLATES_DIR, CONFIG_DIR, BUILTIN_CONFIG_DIR,
    INPUT_DIR, OUTPUT_DIR,
)

from database import (
    init_db,
    db_create_job, db_update_job, db_get_job, db_append_log, insert_job_meta,
)
from migrate_to_db import migrate_json_to_db

if not IS_BUNDLED:
    from tasks import run_pipeline_task


def _celery_workers_available() -> bool:
    """Return True only if a Celery broker is reachable AND at least one worker is online."""
    try:
        inspect = run_pipeline_task.app.control.inspect(timeout=1)
        active = inspect.active_queues()
        return bool(active)
    except Exception:
        return False


def _dispatch_pipeline(job_id: str, upload_path_str: str, bank_key: str,
                        account: str, name: str, confirmed_mapping: dict) -> None:
    """Dispatch pipeline — Celery when broker is up, else thread."""
    import threading
    from tasks import run_pipeline_sync

    use_celery = (
        not IS_BUNDLED
        and hasattr(run_pipeline_task, 'delay')
        and _celery_workers_available()
    )

    if use_celery:
        logger.info("Dispatching pipeline via Celery")
        run_pipeline_task.delay(job_id, upload_path_str, bank_key, account, name, confirmed_mapping)
    else:
        logger.info("Dispatching pipeline via thread (no Celery broker)")
        t = threading.Thread(
            target=run_pipeline_sync,
            args=(job_id, upload_path_str, bank_key, account, name, confirmed_mapping),
            daemon=True,
        )
        t.start()

from core.loader               import load_config, find_best_sheet_and_header
from core.bank_detector        import detect_bank
from core.column_detector      import detect_columns, get_field_aliases, _norm
from core.mapping_memory       import find_matching_profile, list_profiles
from core.bank_memory          import find_matching_bank_fingerprint, save_bank_fingerprint
from core.override_manager     import (
    add_override, remove_override, get_all_overrides, apply_overrides_to_df,
)

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bsie.api")


# ── Startup / shutdown ────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure all directories exist
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Initialise DB tables
    init_db()
    # Migrate any existing JSON data to DB (no-op if already done)
    try:
        migrate_json_to_db()
    except Exception as e:
        logger.warning(f"Migration step encountered an issue (non-fatal): {e}")
    yield
    # shutdown — nothing to do


# ── FastAPI app ───────────────────────────────────────────────────────────
app = FastAPI(
    title="BSIE – Bank Statement Intelligence Engine",
    version="2.0.0",
    root_path="",
    lifespan=lifespan,
)

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
async def api_upload(file: UploadFile = File(...)):
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

    job_id    = str(uuid.uuid4())
    safe_name = f"{job_id}_{file.filename.replace(' ', '_')}"
    save_path = INPUT_DIR / safe_name

    contents = await file.read()
    save_path.write_bytes(contents)

    try:
        sheet_pick = find_best_sheet_and_header(save_path)
        header_row = int(sheet_pick["header_row"])
        sheet_name = str(sheet_pick["sheet_name"])
        data_df = pd.read_excel(
            str(save_path),
            sheet_name=sheet_name,
            header=header_row, dtype=str,
        ).dropna(how="all")
        data_df.columns = [str(c).strip() for c in data_df.columns]

        # Bank detection
        bank_result  = detect_bank(data_df, extra_text=f"{file.filename} {sheet_name}")
        # Column detection
        col_result   = detect_columns(data_df)
        # Memory lookup
        profile      = find_matching_profile(list(data_df.columns))
        bank_memory  = find_matching_bank_fingerprint(list(data_df.columns))

        # Sample rows (first 5)
        sample_rows = data_df.head(5).fillna("").to_dict(orient="records")

        # Prepare response
        suggested = col_result["suggested_mapping"]
        if profile:
            # Memory overrides auto-suggestion
            suggested = profile["mapping"]
            memory_match = {"profile_id": profile["profile_id"], "bank": profile["bank"],
                            "usage_count": profile["usage_count"]}
        else:
            memory_match = None

        return JSONResponse({
            "job_id":           job_id,
            "temp_file_path":   str(save_path),
            "file_name":        file.filename,
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
        save_path.unlink(missing_ok=True)
        logger.exception(f"Upload failed: {e}")
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════════════════════════
# Step 2 — Confirm mapping
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/mapping/confirm")
async def api_confirm_mapping(request: Request):
    """Validate and store confirmed column mapping."""
    body = await request.json()

    bank     = body.get("bank", "UNKNOWN")
    mapping  = body.get("mapping", {})
    columns  = body.get("columns", [])
    header_row = int(body.get("header_row", 0) or 0)
    sheet_name = str(body.get("sheet_name", "") or "")

    if not mapping:
        raise HTTPException(400, "mapping is required")

    from core.mapping_memory import save_profile
    profile = save_profile(bank, columns, mapping)
    fingerprint = None
    if bank and str(bank).strip().lower() not in {"", "unknown", "generic"}:
        fingerprint = save_bank_fingerprint(str(bank).strip(), columns, header_row=header_row, sheet_name=sheet_name)

    return JSONResponse({
        "status": "ok",
        "profile_id": profile["profile_id"],
        "fingerprint_id": fingerprint["fingerprint_id"] if fingerprint else None,
    })


# ═══════════════════════════════════════════════════════════════════════════
# Step 3 — Process
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/process")
async def api_process(request: Request):
    """
    Start the 14-step pipeline in a background thread.
    Returns {job_id} immediately.
    """
    body = await request.json()

    temp_file_path  = body.get("temp_file_path", "")
    bank_key        = body.get("bank_key", "")
    account         = body.get("account", "").strip()
    name            = body.get("name", "").strip()
    confirmed_mapping = body.get("confirmed_mapping")

    if not temp_file_path or not Path(temp_file_path).exists():
        raise HTTPException(400, "temp_file_path missing or file not found")
    if not account or not account.isdigit() or len(account) not in (10, 12):
        raise HTTPException(400, "account must be exactly 10 or 12 digits")

    job_id = str(uuid.uuid4())
    db_create_job(job_id, account=account)

    _dispatch_pipeline(job_id, temp_file_path, bank_key, account, name, confirmed_mapping)
    return JSONResponse({"job_id": job_id})


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
    txn_path = OUTPUT_DIR / safe / "processed" / "transactions.csv"
    if not txn_path.exists():
        raise HTTPException(404, f"No results for account {safe}")

    df = pd.read_csv(txn_path, dtype=str, encoding="utf-8-sig")
    df = df.fillna("")
    total = len(df)
    start = (page - 1) * page_size
    end   = start + page_size
    rows  = df.iloc[start:end].to_dict(orient="records")

    meta_path = OUTPUT_DIR / safe / "meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    return JSONResponse({
        "account":    safe,
        "meta":       meta,
        "total":      total,
        "page":       page,
        "page_size":  page_size,
        "rows":       rows,
    })


# ═══════════════════════════════════════════════════════════════════════════
# Overrides
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/override")
async def api_add_override(request: Request):
    """Add or update a manual relationship override."""
    body = await request.json()
    tid  = body.get("transaction_id", "").strip()
    # Accept both API-native and frontend-react payload keys for compatibility.
    frm  = (body.get("from_account") or body.get("override_from_account") or "").strip()
    to   = (body.get("to_account") or body.get("override_to_account") or "").strip()
    reason = body.get("reason") or body.get("override_reason") or ""
    by     = body.get("override_by", "analyst")

    if not tid or not frm or not to:
        raise HTTPException(400, "transaction_id, from_account, and to_account are required")

    record = add_override(tid, frm, to, reason, by)

    # Re-apply overrides to persisted CSV if it exists
    _reapply_overrides_to_csv(tid)

    return JSONResponse({"status": "ok", "override": record})


@app.delete("/api/override/{transaction_id}")
async def api_remove_override(transaction_id: str):
    removed = remove_override(transaction_id)
    if not removed:
        raise HTTPException(404, "Override not found")
    return JSONResponse({"status": "removed"})


@app.get("/api/overrides")
async def api_list_overrides():
    return JSONResponse({"overrides": get_all_overrides()})


def _reapply_overrides_to_csv(changed_txn_id: str) -> None:
    """Re-run override application on all account CSVs that contain the transaction."""
    for acct_dir in OUTPUT_DIR.iterdir():
        if not acct_dir.is_dir():
            continue
        txn_csv = acct_dir / "processed" / "transactions.csv"
        if not txn_csv.exists():
            continue
        try:
            df = pd.read_csv(txn_csv, dtype=str, encoding="utf-8-sig").fillna("")
            if changed_txn_id not in df.get("transaction_id", pd.Series()).values:
                continue
            df = apply_overrides_to_df(df)
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
    port = int(os.environ.get("PORT", 5001))
    logger.info("=" * 60)
    logger.info("  BSIE – Bank Statement Intelligence Engine v2.0")
    logger.info("  Web App  →  http://127.0.0.1:%d", port)
    logger.info("=" * 60)
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=False, log_level="info")
