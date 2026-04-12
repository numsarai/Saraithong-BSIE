"""
routers/ingestion.py
--------------------
Ingestion-related API routes: upload, mapping confirmation, and process.
"""

import logging
import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from core.bank_detector import detect_bank
from core.bank_memory import find_matching_bank_fingerprint, save_bank_fingerprint
from core.column_detector import detect_columns
from core.image_loader import parse_image_file
from core.loader import find_best_sheet_and_header
from core.mapping_memory import find_matching_profile
from core.ofx_io import infer_identity_from_ofx, parse_ofx_file
from core.pdf_loader import parse_pdf_file
from core.subject_inference import infer_subject_identity_from_frames
from database import db_create_job
from persistence.base import get_db_session
from persistence.schemas import MappingConfirmRequest, ProcessRequest
from services.audit_service import record_learning_feedback
from services.file_ingestion_service import get_file_record, persist_upload
from services.persistence_pipeline_service import create_parser_run
from utils.app_helpers import (
    bank_feedback_status,
    detected_bank_key,
    dispatch_pipeline,
    feedback_message,
    feedback_mode as compute_feedback_mode,
    get_banks,
    mapping_feedback_status,
    repair_suggested_mapping,
    usage_increment_for_feedback,
)

logger = logging.getLogger("bsie.api")

router = APIRouter(prefix="/api", tags=["ingestion"])


# ═══════════════════════════════════════════════════════════════════════════
# Step 1 -- Upload + Detect
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/upload")
async def api_upload(file: UploadFile = File(...), uploaded_by: str = Form("analyst"), force_redetect: str = Form("")):
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

    # HIGH-5: File type allowlist
    ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".ofx", ".pdf", ".csv", ".png", ".jpg", ".jpeg", ".bmp"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type '{suffix}' not supported. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    contents = await file.read()
    persisted = persist_upload(
        content=contents,
        original_filename=file.filename,
        uploaded_by=(uploaded_by or "analyst").strip() or "analyst",
        mime_type=file.content_type,
    )
    save_path = Path(persisted["stored_path"])
    job_id = str(uuid.uuid4())

    # If file was reused and already processed, offer to skip to results
    # (skip this if force_redetect is set — user chose "reprocess")
    is_reused = persisted.get("reused", False)
    if is_reused and not force_redetect:
        with get_db_session() as session:
            from persistence.models import ParserRun, StatementBatch
            from sqlalchemy import select as sa_select
            # Find completed parser run for this file
            completed_run = session.scalars(
                sa_select(ParserRun).where(
                    ParserRun.file_id == persisted["file_id"],
                    ParserRun.status == "done",
                ).order_by(ParserRun.finished_at.desc())
            ).first()
            if completed_run and completed_run.summary_json:
                summary = completed_run.summary_json
                return JSONResponse({
                    "job_id": "",
                    "file_id": persisted["file_id"],
                    "temp_file_path": str(save_path),
                    "file_name": file.filename,
                    "duplicate_file_status": "exact_duplicate",
                    "prior_ingestions": persisted.get("prior_ingestions", []),
                    "already_processed": True,
                    "prior_result": {
                        "parser_run_id": completed_run.id,
                        "account": summary.get("subject_account", ""),
                        "bank_key": summary.get("bank_key", ""),
                        "bank_name": summary.get("bank_name", ""),
                        "subject_name": summary.get("subject_name", ""),
                        "transaction_count": summary.get("transaction_count", 0),
                        "output_dir": summary.get("output_dir", ""),
                    },
                })

    try:
        if save_path.suffix.lower() == ".ofx":
            data_df = parse_ofx_file(save_path)
            identity = infer_identity_from_ofx(save_path, data_df)
            sample_rows = data_df.head(5).fillna("").to_dict(orient="records")
            identity_guess = {
                "account": identity.get("account", ""),
                "name": identity.get("name", ""),
                "account_source": "ofx_account_block" if identity.get("account") else "",
                "name_source": "filename" if identity.get("name") else "",
                "source": "mixed" if identity.get("account") and identity.get("name") else ("ofx_account_block" if identity.get("account") else ("filename" if identity.get("name") else "")),
            }
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
                "banks": get_banks(),
                "header_row": 0,
                "sheet_name": "OFX",
                "account_guess": identity.get("account", ""),
                "name_guess": identity.get("name", ""),
                "identity_guess": identity_guess,
            })

        if save_path.suffix.lower() == ".pdf":
            pdf_result = parse_pdf_file(save_path)
            # If text extraction found too few rows, try OCR
            if pdf_result["tables_found"] == 0 or len(pdf_result["df"]) < 3:
                pdf_result = parse_image_file(save_path)
            data_df = pdf_result["df"]
            if data_df.empty:
                raise HTTPException(400, "Could not extract a transaction table from this PDF")
            data_df.columns = [str(c).strip() for c in data_df.columns]
            header_row = int(pdf_result.get("header_row", 0))
            sheet_name = pdf_result["source_format"]
            identity = infer_subject_identity_from_frames(
                save_path,
                preview_df=data_df.head(15),
                transaction_df=data_df,
            )
            bank_result  = detect_bank(data_df, extra_text=f"{file.filename}", sheet_name=sheet_name)
            col_result   = detect_columns(data_df)
            profile      = find_matching_profile(list(data_df.columns), bank=bank_result.get("config_key", "") or "")
            bank_memory  = find_matching_bank_fingerprint(list(data_df.columns), sheet_name=sheet_name)
            sample_rows  = data_df.head(5).fillna("").to_dict(orient="records")
            auto_suggested = dict(col_result["suggested_mapping"])
            suggested = dict(auto_suggested)
            if profile:
                suggested = repair_suggested_mapping(
                    {**auto_suggested, **profile["mapping"]},
                    auto_suggested,
                    list(data_df.columns),
                )
                memory_match = {"profile_id": profile["profile_id"], "bank": profile["bank"],
                                "usage_count": profile["usage_count"]}
            else:
                suggested = repair_suggested_mapping(suggested, auto_suggested, list(data_df.columns))
                memory_match = None
            return JSONResponse({
                "job_id": job_id, "file_id": persisted["file_id"],
                "temp_file_path": str(save_path), "file_name": file.filename,
                "duplicate_file_status": persisted["duplicate_file_status"],
                "prior_ingestions": persisted["prior_ingestions"],
                "detected_bank": bank_result, "suggested_mapping": suggested,
                "confidence_scores": col_result["confidence_scores"],
                "all_columns": col_result["all_columns"],
                "unmatched_columns": col_result["unmatched_columns"],
                "required_found": col_result["required_found"],
                "memory_match": memory_match, "bank_memory_match": bank_memory,
                "sample_rows": sample_rows, "banks": get_banks(),
                "header_row": header_row, "sheet_name": sheet_name,
                "account_guess": identity.get("account", ""),
                "name_guess": identity.get("name", ""),
                "identity_guess": identity,
            })

        if save_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
            img_result = parse_image_file(save_path)
            data_df = img_result["df"]
            if data_df.empty:
                raise HTTPException(400, "Could not extract a transaction table from this image")
            data_df.columns = [str(c).strip() for c in data_df.columns]
            header_row = int(img_result.get("header_row", 0))
            sheet_name = "IMAGE"
            identity = infer_subject_identity_from_frames(
                save_path,
                preview_df=data_df.head(15),
                transaction_df=data_df,
            )
            bank_result  = detect_bank(data_df, extra_text=f"{file.filename}", sheet_name=sheet_name)
            col_result   = detect_columns(data_df)
            profile      = find_matching_profile(list(data_df.columns), bank=bank_result.get("config_key", "") or "")
            bank_memory  = find_matching_bank_fingerprint(list(data_df.columns), sheet_name=sheet_name)
            sample_rows  = data_df.head(5).fillna("").to_dict(orient="records")
            auto_suggested = dict(col_result["suggested_mapping"])
            suggested = dict(auto_suggested)
            if profile:
                suggested = repair_suggested_mapping(
                    {**auto_suggested, **profile["mapping"]},
                    auto_suggested,
                    list(data_df.columns),
                )
                memory_match = {"profile_id": profile["profile_id"], "bank": profile["bank"],
                                "usage_count": profile["usage_count"]}
            else:
                suggested = repair_suggested_mapping(suggested, auto_suggested, list(data_df.columns))
                memory_match = None
            return JSONResponse({
                "job_id": job_id, "file_id": persisted["file_id"],
                "temp_file_path": str(save_path), "file_name": file.filename,
                "duplicate_file_status": persisted["duplicate_file_status"],
                "prior_ingestions": persisted["prior_ingestions"],
                "detected_bank": bank_result, "suggested_mapping": suggested,
                "confidence_scores": col_result["confidence_scores"],
                "all_columns": col_result["all_columns"],
                "unmatched_columns": col_result["unmatched_columns"],
                "required_found": col_result["required_found"],
                "memory_match": memory_match, "bank_memory_match": bank_memory,
                "sample_rows": sample_rows, "banks": get_banks(),
                "header_row": header_row, "sheet_name": sheet_name,
                "account_guess": identity.get("account", ""),
                "name_guess": identity.get("name", ""),
                "identity_guess": identity,
            })

        sheet_pick = find_best_sheet_and_header(save_path)
        header_row = int(sheet_pick["header_row"])
        sheet_name = str(sheet_pick["sheet_name"])
        identity_preview_df = pd.read_excel(
            str(save_path),
            sheet_name=sheet_name,
            header=None,
            dtype=str,
            nrows=max(header_row + 8, 15),
        ).fillna("")
        data_df = pd.read_excel(
            str(save_path),
            sheet_name=sheet_name,
            header=header_row, dtype=str,
        ).dropna(how="all")
        data_df.columns = [str(c).strip() for c in data_df.columns]
        identity = infer_subject_identity_from_frames(
            save_path,
            preview_df=identity_preview_df,
            transaction_df=data_df,
        )

        bank_result  = detect_bank(data_df, extra_text=f"{file.filename} {sheet_name}", sheet_name=sheet_name)
        col_result   = detect_columns(data_df)
        profile      = find_matching_profile(list(data_df.columns), bank=bank_result.get("config_key", "") or "")
        bank_memory  = find_matching_bank_fingerprint(list(data_df.columns), sheet_name=sheet_name)
        sample_rows = data_df.head(5).fillna("").to_dict(orient="records")

        auto_suggested = dict(col_result["suggested_mapping"])
        suggested = dict(auto_suggested)
        if profile:
            suggested = repair_suggested_mapping(
                {**auto_suggested, **profile["mapping"]},
                auto_suggested,
                list(data_df.columns),
            )
            memory_match = {"profile_id": profile["profile_id"], "bank": profile["bank"],
                            "usage_count": profile["usage_count"]}
        else:
            suggested = repair_suggested_mapping(suggested, auto_suggested, list(data_df.columns))
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
            "banks":            get_banks(),
            "header_row":       header_row,
            "sheet_name":       sheet_name,
            "account_guess":    identity.get("account", ""),
            "name_guess":       identity.get("name", ""),
            "identity_guess":   identity,
        })

    except Exception as e:
        logger.exception("Upload failed for file: %s", file.filename)
        raise HTTPException(500, "File processing failed. Please try again or contact support.")


# ═══════════════════════════════════════════════════════════════════════════
# Step 2 -- Confirm mapping
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/mapping/confirm")
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
    detected_bank = detected_bank_key(
        payload.get("detected_bank")
        if "detected_bank" in payload
        else payload.get("detectedBank"),
    )
    suggested_mapping = payload.get("suggested_mapping") or payload.get("suggestedMapping") or {}

    if not mapping:
        raise HTTPException(400, "mapping is required")

    from core.mapping_memory import save_profile
    bank_feedback = bank_feedback_status(bank, detected_bank)
    mapping_feedback = mapping_feedback_status(mapping, suggested_mapping)
    profile = save_profile(
        bank,
        columns,
        mapping,
        usage_increment=usage_increment_for_feedback(mapping_feedback),
    )
    fingerprint = None
    if bank and str(bank).strip().lower() not in {"", "unknown", "generic"}:
        fingerprint = save_bank_fingerprint(
            str(bank).strip(),
            columns,
            header_row=header_row,
            sheet_name=sheet_name,
            usage_increment=usage_increment_for_feedback(bank_feedback),
        )

    feedback_mode = compute_feedback_mode(bank_feedback, mapping_feedback)
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
                "usage_increment": usage_increment_for_feedback(mapping_feedback),
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
                    "usage_increment": usage_increment_for_feedback(bank_feedback),
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
        "message": feedback_message(bank_feedback, mapping_feedback),
        "learning_feedback_count": learning_feedback_count,
    })


# ═══════════════════════════════════════════════════════════════════════════
# Re-detect — run detection on an already-uploaded file
# ═══════════════════════════════════════════════════════════════════════════

from pydantic import BaseModel as _BaseModel

class _RedetectRequest(_BaseModel):
    file_id: str
    file_name: str = ""

@router.post("/redetect")
async def api_redetect(body: _RedetectRequest):
    """Re-run bank detection and column mapping on an existing file."""
    file_record = get_file_record(body.file_id)
    if not file_record:
        raise HTTPException(404, "File not found")

    save_path = Path(file_record.stored_path)
    if not save_path.exists():
        raise HTTPException(404, "File missing from storage")

    job_id = str(uuid.uuid4())
    filename = body.file_name or file_record.original_filename or save_path.name

    try:
        if save_path.suffix.lower() == ".ofx":
            data_df = parse_ofx_file(save_path)
            identity = infer_identity_from_ofx(save_path, data_df)
            sample_rows = data_df.head(5).fillna("").to_dict(orient="records")
            return JSONResponse({
                "job_id": job_id, "file_id": body.file_id,
                "temp_file_path": str(save_path), "file_name": filename,
                "duplicate_file_status": "redetect", "prior_ingestions": [],
                "detected_bank": {"bank": "OFX", "config_key": "ofx", "key": "ofx", "confidence": 1.0, "ambiguous": False, "scores": {"ofx": 1.0}, "top_candidates": ["ofx"], "evidence": {"positive": ["source:ofx"], "negative": [], "layout": "ofx"}},
                "suggested_mapping": {}, "confidence_scores": {}, "all_columns": list(data_df.columns),
                "unmatched_columns": [], "required_found": True, "memory_match": None, "bank_memory_match": None,
                "sample_rows": sample_rows, "banks": get_banks(), "header_row": 0, "sheet_name": "OFX",
                "account_guess": identity.get("account", ""), "name_guess": identity.get("name", ""),
                "identity_guess": identity,
            })

        if save_path.suffix.lower() == ".pdf":
            pdf_result = parse_pdf_file(save_path)
            if pdf_result["tables_found"] == 0 or len(pdf_result["df"]) < 3:
                pdf_result = parse_image_file(save_path)
            data_df = pdf_result["df"]
            if data_df.empty:
                raise HTTPException(400, "Could not extract table from PDF")
            data_df.columns = [str(c).strip() for c in data_df.columns]
            header_row = int(pdf_result.get("header_row", 0))
            sheet_name = pdf_result["source_format"]
        elif save_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp"):
            img_result = parse_image_file(save_path)
            data_df = img_result["df"]
            if data_df.empty:
                raise HTTPException(400, "Could not extract table from image")
            data_df.columns = [str(c).strip() for c in data_df.columns]
            header_row = int(img_result.get("header_row", 0))
            sheet_name = "IMAGE"
        else:
            # Excel
            sheet_pick = find_best_sheet_and_header(save_path)
            header_row = int(sheet_pick["header_row"])
            sheet_name = str(sheet_pick["sheet_name"])
            data_df = pd.read_excel(str(save_path), sheet_name=sheet_name, header=header_row, dtype=str).dropna(how="all")
            data_df.columns = [str(c).strip() for c in data_df.columns]

        identity = infer_subject_identity_from_frames(save_path, preview_df=data_df.head(15), transaction_df=data_df)
        bank_result = detect_bank(data_df, extra_text=f"{filename} {sheet_name}", sheet_name=sheet_name)
        col_result = detect_columns(data_df)
        profile = find_matching_profile(list(data_df.columns), bank=bank_result.get("config_key", "") or "")
        bank_memory = find_matching_bank_fingerprint(list(data_df.columns), sheet_name=sheet_name)
        sample_rows = data_df.head(5).fillna("").to_dict(orient="records")
        auto_suggested = dict(col_result["suggested_mapping"])
        suggested = dict(auto_suggested)
        memory_match = None
        if profile:
            suggested = repair_suggested_mapping({**auto_suggested, **profile["mapping"]}, auto_suggested, list(data_df.columns))
            memory_match = {"profile_id": profile["profile_id"], "bank": profile["bank"], "usage_count": profile["usage_count"]}
        else:
            suggested = repair_suggested_mapping(suggested, auto_suggested, list(data_df.columns))

        return JSONResponse({
            "job_id": job_id, "file_id": body.file_id,
            "temp_file_path": str(save_path), "file_name": filename,
            "duplicate_file_status": "redetect", "prior_ingestions": [],
            "detected_bank": bank_result, "suggested_mapping": suggested,
            "confidence_scores": col_result["confidence_scores"],
            "all_columns": col_result["all_columns"], "unmatched_columns": col_result["unmatched_columns"],
            "required_found": col_result["required_found"],
            "memory_match": memory_match, "bank_memory_match": bank_memory,
            "sample_rows": sample_rows, "banks": get_banks(),
            "header_row": header_row, "sheet_name": sheet_name,
            "account_guess": identity.get("account", ""), "name_guess": identity.get("name", ""),
            "identity_guess": identity,
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Redetect failed")
        raise HTTPException(500, f"Re-detection failed: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
# Step 3 -- Process
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/process")
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

    dispatch_pipeline(
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
