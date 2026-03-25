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
    STATIC_DIR, TEMPLATES_DIR, CONFIG_DIR,
    INPUT_DIR, OUTPUT_DIR,
)

from database import (
    init_db,
    db_create_job, db_update_job, db_get_job, db_append_log, insert_job_meta,
)
from migrate_to_db import migrate_json_to_db

if not IS_BUNDLED:
    from tasks import run_pipeline_task


def _dispatch_pipeline(job_id: str, upload_path_str: str, bank_key: str,
                        account: str, name: str, confirmed_mapping: dict) -> None:
    """Dispatch pipeline — thread in bundled mode, Celery in server mode."""
    if IS_BUNDLED:
        import threading
        from tasks import run_pipeline_sync
        t = threading.Thread(
            target=run_pipeline_sync,
            args=(job_id, upload_path_str, bank_key, account, name, confirmed_mapping),
            daemon=True,
        )
        t.start()
    else:
        run_pipeline_task.delay(job_id, upload_path_str, bank_key, account, name, confirmed_mapping)

from core.loader               import load_config
from core.bank_detector        import detect_bank
from core.column_detector      import detect_columns
from core.mapping_memory       import find_matching_profile, list_profiles
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
    banks = []
    for f in sorted(CONFIG_DIR.glob("*.json")):
        try:
            cfg = json.loads(f.read_text(encoding="utf-8"))
            banks.append({"key": f.stem, "name": cfg.get("bank_name", f.stem.upper())})
        except Exception:
            pass
    return banks


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
        xf = pd.ExcelFile(str(save_path), engine="openpyxl")
        raw_df = pd.read_excel(
            str(save_path),
            sheet_name=xf.sheet_names[0],
            header=None, nrows=40, dtype=str,
        ).fillna("")

        # Auto-detect header row (score-based: check date + amount aliases in first 15 rows)
        _DATE_KW = {"วันที่", "วันที่ทำรายการ", "date", "transaction date"}
        _AMT_KW  = {"จำนวนเงิน", "amount", "debit", "credit", "เดบิต", "เครดิต",
                     "ถอนเงิน", "ฝากเงิน", "เงินฝาก", "ถอน",
                     "หมายเลขบัญชีต้นทาง", "หมายเลขบัญชีปลายทาง",
                     "บัญชีผู้โอน", "บัญชีผู้รับโอน", "ชื่อผู้โอน", "ชื่อผู้รับโอน"}
        header_row = 0
        best_score = 0
        for i in range(min(15, len(raw_df))):
            row_vals = {str(v).lower().strip() for v in raw_df.iloc[i].values if pd.notna(v)}
            score = len(row_vals & _DATE_KW) * 2 + len(row_vals & _AMT_KW)
            if score > best_score:
                best_score = score
                header_row = i

        data_df = pd.read_excel(
            str(save_path),
            sheet_name=xf.sheet_names[0],
            header=header_row, dtype=str,
        ).dropna(how="all")
        data_df.columns = [str(c).strip() for c in data_df.columns]

        # Bank detection
        bank_result  = detect_bank(data_df, extra_text=file.filename)
        # Column detection
        col_result   = detect_columns(data_df)
        # Memory lookup
        profile      = find_matching_profile(list(data_df.columns))

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
            "sample_rows":      sample_rows,
            "banks":            _get_banks(),
            "header_row":       header_row,
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

    if not mapping:
        raise HTTPException(400, "mapping is required")

    from core.mapping_memory import save_profile
    profile = save_profile(bank, columns, mapping)

    return JSONResponse({"status": "ok", "profile_id": profile["profile_id"]})


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
    frm  = body.get("from_account", "").strip()
    to   = body.get("to_account", "").strip()
    reason = body.get("reason", "")
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
async def api_download(account: str, file_path: str):
    safe = "".join(c for c in account if c.isdigit())
    full = OUTPUT_DIR / safe / file_path
    if not full.exists() or not full.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(str(full), filename=full.name)


# ═══════════════════════════════════════════════════════════════════════════
# Banks list
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/banks")
async def api_banks():
    return JSONResponse(_get_banks())


@app.get("/api/banks/{key}")
async def api_bank_get(key: str):
    """Return full config for a specific bank."""
    f = CONFIG_DIR / f"{key}.json"
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
    print("=" * 60)
    print("  BSIE – Bank Statement Intelligence Engine v2.0")
    print(f"  Web App  →  http://127.0.0.1:{port}")
    print("=" * 60)
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=False, log_level="info")
