"""
routers/ingestion.py
--------------------
Ingestion-related API routes: upload, mapping confirmation, and process.
"""

import logging
import uuid
from pathlib import Path

import pandas as pd
from services.auth_service import require_auth
from fastapi import Depends, APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

_limiter = Limiter(key_func=get_remote_address)

from core.bank_detector import detect_bank
from core.bank_memory import find_matching_bank_fingerprint
from core.column_detector import detect_columns
from core.image_loader import parse_image_file
from core.loader import find_best_sheet_and_header
from core.mapping_memory import find_matching_profile
from core.ofx_io import infer_identity_from_ofx, parse_ofx_file
from core.pdf_loader import parse_pdf_file
from core.subject_inference import infer_subject_identity_from_frames
from database import db_create_job
from persistence.base import get_db_session
from persistence.schemas import MappingAssistRequest, MappingConfirmRequest, MappingPreviewRequest, MappingVisionAssistRequest, ProcessRequest, TemplateVariantPromotionRequest
from services.audit_service import record_learning_feedback
from services.file_ingestion_service import get_file_record, persist_upload
from services.mapping_assist_service import suggest_mapping_with_llm, suggest_mapping_with_vision_llm
from services.mapping_validation_service import validate_and_preview_mapping, validate_mapping
from services.persistence_pipeline_service import create_parser_run
from services.template_variant_service import (
    find_matching_template_variant,
    list_template_variants,
    promote_template_variant,
    upsert_template_variant,
)
from utils.app_helpers import (
    bank_feedback_status,
    detected_bank_key,
    dispatch_pipeline,
    feedback_message,
    feedback_mode as compute_feedback_mode,
    get_banks,
    mapping_feedback_status,
    repair_suggested_mapping,
)

logger = logging.getLogger("bsie.api")

router = APIRouter(prefix="/api", tags=["ingestion"], dependencies=[Depends(require_auth)])

VARIANT_BANK_CONFIDENCE_THRESHOLD = 0.75


# ═══════════════════════════════════════════════════════════════════════════
# Step 1 -- Upload + Detect
# ═══════════════════════════════════════════════════════════════════════════

def _source_type_from_suffix(suffix: str) -> str:
    suffix = str(suffix or "").lower()
    if suffix in {".xlsx", ".xls"}:
        return "excel"
    if suffix == ".pdf":
        return "pdf_ocr"
    if suffix in {".png", ".jpg", ".jpeg", ".bmp"}:
        return "image_ocr"
    return suffix.lstrip(".") or "unknown"


def _is_stable_variant_bank(bank_result: dict, source_type: str) -> bool:
    if source_type != "excel":
        return False
    bank_key = str(bank_result.get("config_key") or bank_result.get("key") or "").strip().lower()
    if not bank_key or bank_key in {"unknown", "generic"}:
        return False
    if bool(bank_result.get("ambiguous")):
        return False
    try:
        confidence = float(bank_result.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return confidence >= VARIANT_BANK_CONFIDENCE_THRESHOLD


def _suggest_mapping_with_memory(
    data_df: pd.DataFrame,
    bank_result: dict,
    col_result: dict,
    *,
    source_type: str,
    sheet_name: str,
    header_row: int,
) -> dict:
    columns = list(data_df.columns)
    bank_key = bank_result.get("config_key", "") or bank_result.get("key", "") or ""
    profile = find_matching_profile(columns, bank=bank_key)
    bank_memory = find_matching_bank_fingerprint(columns, sheet_name=sheet_name)
    auto_suggested = dict(col_result["suggested_mapping"])
    suggested = dict(auto_suggested)
    suggestion_source = "auto"
    template_variant_match = None

    if profile:
        suggested = repair_suggested_mapping(
            {**auto_suggested, **profile["mapping"]},
            auto_suggested,
            columns,
        )
        memory_match = {
            "profile_id": profile["profile_id"],
            "bank": profile["bank"],
            "usage_count": profile["usage_count"],
        }
        suggestion_source = "mapping_profile"
    else:
        suggested = repair_suggested_mapping(suggested, auto_suggested, columns)
        memory_match = None

    if _is_stable_variant_bank(bank_result, source_type):
        with get_db_session() as session:
            variant = find_matching_template_variant(
                session,
                columns=columns,
                bank_key=bank_key,
                source_type=source_type,
                sheet_name=sheet_name,
                header_row=header_row,
                include_candidate=True,
            )
        if variant:
            variant_suggested = repair_suggested_mapping(
                {**suggested, **variant["confirmed_mapping"]},
                auto_suggested,
                columns,
            )
            if validate_mapping(variant_suggested, columns, bank=bank_key)["ok"]:
                suggested = variant_suggested
                suggestion_source = "template_variant"
                template_variant_match = {
                    "variant_id": variant["variant_id"],
                    "bank_key": variant["bank_key"],
                    "trust_state": variant["trust_state"],
                    "match_type": variant["match_type"],
                    "match_score": variant["match_score"],
                    "confirmation_count": variant["confirmation_count"],
                    "correction_count": variant["correction_count"],
                    "reviewer_count": variant["reviewer_count"],
                    "suggestion_only": True,
                    "auto_pass_eligible": False,
                }

    return {
        "suggested_mapping": suggested,
        "memory_match": memory_match,
        "bank_memory_match": bank_memory,
        "template_variant_match": template_variant_match,
        "suggestion_source": suggestion_source,
    }


@router.post("/upload")
@_limiter.limit("10/minute")
async def api_upload(request: Request, file: UploadFile = File(...), uploaded_by: str = Form("analyst"), force_redetect: str = Form("")):
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
    ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".ofx", ".pdf", ".png", ".jpg", ".jpeg", ".bmp"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type '{suffix}' not supported. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    # SEC-H1: Read with size limit (50 MB) to prevent memory exhaustion
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
    contents = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"File too large (max {MAX_UPLOAD_SIZE // 1024 // 1024} MB)")

    # SEC-H2: Magic byte validation — verify actual file type matches extension
    _MAGIC_BYTES: dict[str, list[bytes]] = {
        ".xlsx": [b"PK\x03\x04"],  # ZIP-based (Office Open XML)
        ".xls":  [b"\xd0\xcf\x11\xe0"],  # OLE2 compound document
        ".pdf":  [b"%PDF"],
        ".png":  [b"\x89PNG"],
        ".jpg":  [b"\xff\xd8\xff"],
        ".jpeg": [b"\xff\xd8\xff"],
        ".bmp":  [b"BM"],
    }
    expected_magics = _MAGIC_BYTES.get(suffix)
    if expected_magics and not any(contents[:8].startswith(m) for m in expected_magics):
        raise HTTPException(
            400,
            f"File content does not match extension '{suffix}'. "
            f"The file may be corrupted or have an incorrect extension.",
        )
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
                "template_variant_match": None,
                "suggestion_source": "ofx",
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
            sample_rows  = data_df.head(5).fillna("").to_dict(orient="records")
            suggestion_context = _suggest_mapping_with_memory(
                data_df,
                bank_result,
                col_result,
                source_type=_source_type_from_suffix(save_path.suffix),
                sheet_name=sheet_name,
                header_row=header_row,
            )
            return JSONResponse({
                "job_id": job_id, "file_id": persisted["file_id"],
                "temp_file_path": str(save_path), "file_name": file.filename,
                "duplicate_file_status": persisted["duplicate_file_status"],
                "prior_ingestions": persisted["prior_ingestions"],
                "detected_bank": bank_result, "suggested_mapping": suggestion_context["suggested_mapping"],
                "confidence_scores": col_result["confidence_scores"],
                "all_columns": col_result["all_columns"],
                "unmatched_columns": col_result["unmatched_columns"],
                "required_found": col_result["required_found"],
                "memory_match": suggestion_context["memory_match"], "bank_memory_match": suggestion_context["bank_memory_match"],
                "template_variant_match": suggestion_context["template_variant_match"],
                "suggestion_source": suggestion_context["suggestion_source"],
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
            sample_rows  = data_df.head(5).fillna("").to_dict(orient="records")
            suggestion_context = _suggest_mapping_with_memory(
                data_df,
                bank_result,
                col_result,
                source_type=_source_type_from_suffix(save_path.suffix),
                sheet_name=sheet_name,
                header_row=header_row,
            )
            return JSONResponse({
                "job_id": job_id, "file_id": persisted["file_id"],
                "temp_file_path": str(save_path), "file_name": file.filename,
                "duplicate_file_status": persisted["duplicate_file_status"],
                "prior_ingestions": persisted["prior_ingestions"],
                "detected_bank": bank_result, "suggested_mapping": suggestion_context["suggested_mapping"],
                "confidence_scores": col_result["confidence_scores"],
                "all_columns": col_result["all_columns"],
                "unmatched_columns": col_result["unmatched_columns"],
                "required_found": col_result["required_found"],
                "memory_match": suggestion_context["memory_match"], "bank_memory_match": suggestion_context["bank_memory_match"],
                "template_variant_match": suggestion_context["template_variant_match"],
                "suggestion_source": suggestion_context["suggestion_source"],
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
        sample_rows = data_df.head(5).fillna("").to_dict(orient="records")
        suggestion_context = _suggest_mapping_with_memory(
            data_df,
            bank_result,
            col_result,
            source_type=_source_type_from_suffix(save_path.suffix),
            sheet_name=sheet_name,
            header_row=header_row,
        )

        return JSONResponse({
            "job_id":           job_id,
            "file_id":          persisted["file_id"],
            "temp_file_path":   str(save_path),
            "file_name":        file.filename,
            "duplicate_file_status": persisted["duplicate_file_status"],
            "prior_ingestions": persisted["prior_ingestions"],
            "detected_bank":    bank_result,
            "suggested_mapping": suggestion_context["suggested_mapping"],
            "confidence_scores": col_result["confidence_scores"],
            "all_columns":      col_result["all_columns"],
            "unmatched_columns": col_result["unmatched_columns"],
            "required_found":   col_result["required_found"],
            "memory_match":     suggestion_context["memory_match"],
            "bank_memory_match": suggestion_context["bank_memory_match"],
            "template_variant_match": suggestion_context["template_variant_match"],
            "suggestion_source": suggestion_context["suggestion_source"],
            "sample_rows":      sample_rows,
            "banks":            get_banks(),
            "header_row":       header_row,
            "sheet_name":       sheet_name,
            "account_guess":    identity.get("account", ""),
            "name_guess":       identity.get("name", ""),
            "identity_guess":   identity,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Upload failed for file: %s", file.filename)
        raise HTTPException(500, "File processing failed. Please try again or contact support.")


# ═══════════════════════════════════════════════════════════════════════════
# Step 2 -- Confirm mapping
# ═══════════════════════════════════════════════════════════════════════════

def _mapping_validation_error(validation: dict) -> dict:
    return {
        "message": "Mapping validation failed",
        "errors": validation.get("errors", []),
        "warnings": validation.get("warnings", []),
        "dry_run_preview": validation.get("dry_run_preview", {}),
    }


def _can_promote_shared_mapping(reviewer: str) -> bool:
    return str(reviewer or "").strip().lower() not in {"", "analyst", "unknown"}


def _template_variant_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(404, str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(403, str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(400, str(exc))
    return HTTPException(500, "Template variant operation failed")


@router.post("/mapping/preview")
async def api_preview_mapping(request: Request):
    """Validate a proposed mapping and return a sample normalization preview."""
    payload = await request.json()
    body = MappingPreviewRequest.model_validate(payload)
    validation = validate_and_preview_mapping(
        bank=body.bank or "UNKNOWN",
        mapping=body.mapping,
        columns=body.columns,
        sample_rows=body.sample_rows,
    )
    return JSONResponse({
        "status": "ok" if validation["ok"] else "invalid",
        **validation,
    })


@router.post("/mapping/assist")
async def api_assist_mapping(request: Request):
    """Return a local-LLM mapping suggestion for analyst review only."""
    payload = await request.json()
    body = MappingAssistRequest.model_validate(payload)
    try:
        result = await suggest_mapping_with_llm(
            bank=body.bank,
            detected_bank=body.detected_bank,
            columns=body.columns,
            sample_rows=body.sample_rows,
            current_mapping=body.current_mapping,
            sheet_name=body.sheet_name,
            header_row=body.header_row,
            model=body.model,
        )
        return JSONResponse(result)
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/mapping/assist/vision")
async def api_assist_mapping_vision(request: Request):
    """Return a local vision-LLM mapping suggestion for PDF/image analyst review only."""
    payload = await request.json()
    body = MappingVisionAssistRequest.model_validate(payload)
    file_id = str(body.file_id or "").strip()
    if not file_id:
        raise HTTPException(400, "file_id is required for vision mapping assist")
    file_record = get_file_record(file_id)
    if not file_record:
        raise HTTPException(404, "File not found")
    file_path = Path(file_record.stored_path)
    from paths import EVIDENCE_DIR
    evidence_root = EVIDENCE_DIR.resolve()
    resolved_path = file_path.resolve()
    if resolved_path != evidence_root and evidence_root not in resolved_path.parents:
        raise HTTPException(400, "Source file is outside evidence storage")
    if not resolved_path.exists():
        raise HTTPException(404, "Source evidence file not found")
    try:
        result = await suggest_mapping_with_vision_llm(
            file_path=resolved_path,
            bank=body.bank,
            detected_bank=body.detected_bank,
            columns=body.columns,
            sample_rows=body.sample_rows,
            current_mapping=body.current_mapping,
            sheet_name=body.sheet_name,
            header_row=body.header_row,
            model=body.model,
        )
        return JSONResponse(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
    detected_bank_raw = payload.get("detected_bank") if "detected_bank" in payload else payload.get("detectedBank")
    detected_bank = detected_bank_key(detected_bank_raw)
    suggested_mapping = payload.get("suggested_mapping") or payload.get("suggestedMapping") or {}

    validation = validate_and_preview_mapping(
        bank=bank,
        mapping=mapping,
        columns=columns,
        sample_rows=body.sample_rows,
    )
    if not validation["ok"]:
        raise HTTPException(400, detail=_mapping_validation_error(validation))

    mapping = validation["mapping"]
    columns = validation["columns"]
    bank_feedback = bank_feedback_status(bank, detected_bank)
    mapping_feedback = mapping_feedback_status(mapping, suggested_mapping)
    bank_override_detected = bool(detected_bank and bank_feedback == "corrected")
    bank_authority_context = {
        "selected_bank": str(bank or "").strip().lower(),
        "detected_bank": detected_bank,
        "bank_override_detected": bank_override_detected,
        "authority": "analyst_selected" if bank_override_detected else "detected_or_selected",
    }
    promote_shared = bool(body.promote_shared)
    if promote_shared and not _can_promote_shared_mapping(reviewer):
        raise HTTPException(403, "Shared mapping promotion requires a named reviewer")

    variant = None
    feedback_mode = compute_feedback_mode(bank_feedback, mapping_feedback)
    learning_feedback_count = 0
    with get_db_session() as session:
        if promote_shared:
            variant = upsert_template_variant(
                session,
                bank_key=bank,
                columns=columns,
                mapping=mapping,
                source_type=body.source_type,
                sheet_name=sheet_name,
                header_row=header_row,
                layout_type=body.layout_type,
                reviewer=reviewer,
                feedback_status=mapping_feedback,
                dry_run_summary=validation["dry_run_preview"]["summary"],
            )
            record_learning_feedback(
                session,
                learning_domain="bank_template_variant",
                action_type="template_variant_confirmation",
                source_object_type="bank_template_variant",
                source_object_id=variant["variant_id"],
                feedback_status=mapping_feedback,
                changed_by=reviewer,
                old_value=suggested_mapping or None,
                new_value=mapping,
                extra_context={
                    "bank": bank,
                    "bank_authority": bank_authority_context,
                    "detected_bank": detected_bank_raw if isinstance(detected_bank_raw, dict) else detected_bank,
                    "bank_feedback": bank_feedback,
                    "columns": list(columns or []),
                    "variant_action": variant["action"],
                    "trust_state": variant["trust_state"],
                    "dry_run_summary": validation["dry_run_preview"]["summary"],
                },
            )
            learning_feedback_count += 1
        else:
            record_learning_feedback(
                session,
                learning_domain="mapping_confirmation",
                action_type="mapping_confirmation",
                source_object_type="mapping_confirmation",
                source_object_id=str(uuid.uuid4()),
                feedback_status=mapping_feedback,
                changed_by=reviewer,
                old_value=suggested_mapping or None,
                new_value=mapping,
                extra_context={
                    "bank": bank,
                    "bank_authority": bank_authority_context,
                    "detected_bank": detected_bank_raw if isinstance(detected_bank_raw, dict) else detected_bank,
                    "bank_feedback": bank_feedback,
                    "columns": list(columns or []),
                    "promotion_requested": False,
                    "dry_run_summary": validation["dry_run_preview"]["summary"],
                },
            )
            learning_feedback_count += 1
        session.commit()
    return JSONResponse({
        "status": "ok",
        "profile_id": None,
        "fingerprint_id": None,
        "variant_id": variant["variant_id"] if variant else None,
        "bank_feedback": bank_feedback,
        "bank_authority": bank_authority_context,
        "mapping_feedback": mapping_feedback,
        "feedback_mode": feedback_mode,
        "validation": {
            "warnings": validation.get("warnings", []),
            "amount_mode": validation.get("amount_mode"),
            "mapped_fields": validation.get("mapped_fields", []),
        },
        "dry_run_preview": validation["dry_run_preview"],
        "shared_learning": {
            "requested": promote_shared,
            "status": "variant_recorded" if variant else "skipped",
            "trust_state": variant["trust_state"] if variant else "",
            "reason": "" if variant else "Mapping was confirmed for this run only; shared promotion is opt-in.",
        },
        "message": feedback_message(bank_feedback, mapping_feedback),
        "learning_feedback_count": learning_feedback_count,
    })


@router.get("/mapping/variants")
async def api_list_mapping_variants(bank: str = "", trust_state: str = "", limit: int = 100):
    with get_db_session() as session:
        items = list_template_variants(session, bank_key=bank, trust_state=trust_state, limit=limit)
    return JSONResponse({"items": items, "count": len(items)})


@router.post("/mapping/variants/{variant_id}/promote")
async def api_promote_mapping_variant(variant_id: str, body: TemplateVariantPromotionRequest):
    try:
        with get_db_session() as session:
            before = next((item for item in list_template_variants(session, limit=500) if item["variant_id"] == variant_id), None)
            variant = promote_template_variant(
                session,
                variant_id=variant_id,
                target_state=body.trust_state,
                reviewer=body.reviewer,
                note=body.note,
            )
            record_learning_feedback(
                session,
                learning_domain="bank_template_variant",
                action_type="template_variant_promotion",
                source_object_type="bank_template_variant",
                source_object_id=variant_id,
                feedback_status=variant["trust_state"],
                changed_by=body.reviewer,
                old_value={"trust_state": before["trust_state"]} if before else None,
                new_value={"trust_state": variant["trust_state"]},
                reason=body.note,
                extra_context={
                    "bank": variant["bank_key"],
                    "confirmation_count": variant["confirmation_count"],
                    "correction_count": variant["correction_count"],
                    "reviewer_count": variant["reviewer_count"],
                },
            )
            session.commit()
        return JSONResponse({"status": "ok", "variant": variant})
    except Exception as exc:
        raise _template_variant_error(exc) from exc


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
        sample_rows = data_df.head(5).fillna("").to_dict(orient="records")
        suggestion_context = _suggest_mapping_with_memory(
            data_df,
            bank_result,
            col_result,
            source_type=_source_type_from_suffix(save_path.suffix),
            sheet_name=sheet_name,
            header_row=header_row,
        )

        return JSONResponse({
            "job_id": job_id, "file_id": body.file_id,
            "temp_file_path": str(save_path), "file_name": filename,
            "duplicate_file_status": "redetect", "prior_ingestions": [],
            "detected_bank": bank_result, "suggested_mapping": suggestion_context["suggested_mapping"],
            "confidence_scores": col_result["confidence_scores"],
            "all_columns": col_result["all_columns"], "unmatched_columns": col_result["unmatched_columns"],
            "required_found": col_result["required_found"],
            "memory_match": suggestion_context["memory_match"], "bank_memory_match": suggestion_context["bank_memory_match"],
            "template_variant_match": suggestion_context["template_variant_match"],
            "suggestion_source": suggestion_context["suggestion_source"],
            "sample_rows": sample_rows, "banks": get_banks(),
            "header_row": header_row, "sheet_name": sheet_name,
            "account_guess": identity.get("account", ""), "name_guess": identity.get("name", ""),
            "identity_guess": identity,
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Redetect failed")
        raise HTTPException(500, "Re-detection failed. Please try again or contact support.")


# ═══════════════════════════════════════════════════════════════════════════
# Step 3 -- Process
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/process")
@_limiter.limit("10/minute")
async def api_process(request: Request, body: ProcessRequest):
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
    if not temp_file_path:
        raise HTTPException(400, "temp_file_path missing")

    # SEC-H5: Confine temp_file_path to allowed data directories via realpath
    # + prefix check BEFORE any filesystem read. `resolved_path` becomes the
    # single authoritative path used downstream; the raw `temp_file_path` is
    # never touched again after this point.
    from paths import INPUT_DIR, EVIDENCE_DIR
    allowed_bases = [INPUT_DIR.resolve(), EVIDENCE_DIR.resolve()]
    resolved_path = Path(temp_file_path).resolve()  # codeql[py/path-injection]
    if not any(
        resolved_path == b or b in resolved_path.parents
        for b in allowed_bases
    ):
        raise HTTPException(403, "File path outside allowed directories")
    # At this point resolved_path is provably under an allowed base.
    if not resolved_path.is_file():  # codeql[py/path-injection]
        raise HTTPException(400, "temp_file_path not found")
    if not account or not account.isdigit() or len(account) not in (10, 12):
        raise HTTPException(400, "account must be exactly 10 or 12 digits")

    job_id = str(uuid.uuid4())
    db_create_job(job_id, account=account)

    if not file_id and file_record is None:
        inferred_upload = persist_upload(
            content=resolved_path.read_bytes(),  # codeql[py/path-injection]
            original_filename=resolved_path.name,
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
        str(resolved_path),
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
