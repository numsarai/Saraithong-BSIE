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
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ── Path setup ───────────────────────────────────────────────────────────
_BASE = Path(__file__).parent
sys.path.insert(0, str(_BASE))

from pipeline.process_account import process_account
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

# ── Directory setup ───────────────────────────────────────────────────────
UPLOAD_DIR = _BASE / "data" / "input"
OUTPUT_DIR = _BASE / "data" / "output"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
(_BASE / "overrides").mkdir(exist_ok=True)
(_BASE / "mapping_profiles").mkdir(exist_ok=True)

# ── FastAPI app ───────────────────────────────────────────────────────────
app = FastAPI(
    title="BSIE – Bank Statement Intelligence Engine",
    version="2.0.0",
    root_path="",
)

app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(_BASE / "templates"))

# ── In-memory job store ───────────────────────────────────────────────────
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════════════════════
# UI routes
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ═══════════════════════════════════════════════════════════════════════════
# Helper: list available bank configs
# ═══════════════════════════════════════════════════════════════════════════

def _get_banks() -> List[Dict]:
    banks = []
    for f in sorted((_BASE / "config").glob("*.json")):
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
    save_path = UPLOAD_DIR / safe_name

    contents = await file.read()
    save_path.write_bytes(contents)

    try:
        xf = pd.ExcelFile(str(save_path), engine="openpyxl")
        raw_df = pd.read_excel(
            str(save_path),
            sheet_name=xf.sheet_names[0],
            header=None, nrows=40, dtype=str,
        ).fillna("")

        # Auto-detect header row (look for date/amount aliases in first 15 rows)
        header_row = 0
        for i in range(min(15, len(raw_df))):
            row_vals = [str(v).lower().strip() for v in raw_df.iloc[i].values]
            has_date = any(kw in row_vals for kw in ["วันที่", "date", "transaction date"])
            has_amt  = any(kw in row_vals for kw in ["จำนวนเงิน", "amount", "debit", "credit", "เดบิต", "เครดิต"])
            if has_date or has_amt:
                header_row = i
                break

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
    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "log": [], "result": None, "error": None}

    t = threading.Thread(
        target=_run_pipeline,
        args=(job_id, Path(temp_file_path), bank_key, account, name, confirmed_mapping),
        daemon=True,
    )
    t.start()
    return JSONResponse({"job_id": job_id})


def _run_pipeline(
    job_id: str,
    upload_path: Path,
    bank_key: str,
    account: str,
    name: str,
    confirmed_mapping: Optional[Dict],
) -> None:
    """Background worker — runs the full pipeline and stores results."""

    class _JobHandler(logging.Handler):
        def emit(self, record):
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]["log"].append(self.format(record))

    handler = _JobHandler()
    handler.setFormatter(logging.Formatter("%(levelname)-8s %(name)s — %(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    try:
        with _jobs_lock:
            _jobs[job_id]["status"] = "running"

        output_dir = process_account(
            input_file=upload_path,
            subject_account=account,
            subject_name=name,
            bank_key=bank_key,
            confirmed_mapping=confirmed_mapping,
        )

        meta = {}
        meta_path = output_dir / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        # Load transaction preview (first 500 rows)
        txn_path = output_dir / "processed" / "transactions.csv"
        txn_data = []
        if txn_path.exists():
            df = pd.read_csv(txn_path, dtype=str, encoding="utf-8-sig", nrows=500)
            txn_data = df.fillna("").to_dict(orient="records")

        ent_path = output_dir / "processed" / "entities.csv"
        ent_data = []
        if ent_path.exists():
            df = pd.read_csv(ent_path, dtype=str, encoding="utf-8-sig")
            ent_data = df.fillna("").to_dict(orient="records")

        lnk_path = output_dir / "processed" / "links.csv"
        lnk_data = []
        if lnk_path.exists():
            df = pd.read_csv(lnk_path, dtype=str, encoding="utf-8-sig")
            lnk_data = df.fillna("").to_dict(orient="records")

        with _jobs_lock:
            _jobs[job_id].update({
                "status": "done",
                "result": {
                    "meta":         meta,
                    "transactions": txn_data,
                    "entities":     ent_data,
                    "links":        lnk_data,
                    "output_dir":   str(output_dir),
                    "account":      account,
                },
            })

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}\n{traceback.format_exc()}")
        with _jobs_lock:
            _jobs[job_id].update({"status": "error", "error": str(e)})
    finally:
        root_logger.removeHandler(handler)


@app.get("/api/job/{job_id}")
async def api_job_status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JSONResponse({
        "status": job["status"],
        "log":    job["log"][-200:],
        "result": job["result"],
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
            # Also update Excel
            txn_xlsx = acct_dir / "processed" / "transactions.xlsx"
            df.to_excel(str(txn_xlsx), index=False, engine="openpyxl")
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
