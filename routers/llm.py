"""
LLM Router — API endpoints for local LLM interaction with DB access.

All endpoints require Ollama to be running on localhost:11434.
The LLM automatically queries the BSIE database for context.
No data leaves the machine.
"""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from services.auth_service import require_auth
from pydantic import BaseModel, Field

from persistence.base import get_db_session
from services.classification_service import build_classification_preview, build_scoped_classification_preview
from services.copilot_service import (
    CopilotNotFoundError,
    CopilotScopeError,
    answer_copilot_question,
)
from services.llm_service import (
    benchmark_llm_roles,
    chat,
    chat_with_file,
    check_ollama_status,
    classify_transaction,
    get_account_summary,
    get_all_accounts_summary,
    summarize_account,
)

logger = logging.getLogger("bsie.llm.router")
router = APIRouter(prefix="/api/llm", tags=["llm"], dependencies=[Depends(require_auth)])


import re as _re

_MODEL_PATTERN = _re.compile(r"^[a-zA-Z0-9_:\-\.]{1,100}$")


def _validate_model(model: str) -> str:
    if not _MODEL_PATTERN.match(model):
        raise ValueError("Invalid model name")
    return model


class ChatRequest(BaseModel):
    message: str = Field(max_length=4000)
    account: str = ""
    transactions: list[dict] = Field(default_factory=list)
    model: str = ""


class SummarizeRequest(BaseModel):
    account: str
    model: str = ""


class ClassifyRequest(BaseModel):
    transaction: dict = Field(default_factory=dict)
    model: str = ""


class ClassificationPreviewRequest(BaseModel):
    transactions: list[dict] = Field(default_factory=list)
    scope: dict = Field(default_factory=dict)
    model: str = Field(default="", max_length=100)
    max_transactions: int = Field(default=10, ge=1, le=25)


class BenchmarkRequest(BaseModel):
    roles: list[str] = Field(default_factory=list)
    iterations: int = Field(default=1, ge=1, le=5)
    include_vision: bool = False
    model_overrides: dict[str, str] = Field(default_factory=dict)


class CopilotScopeRequest(BaseModel):
    parser_run_id: str = Field(default="", max_length=64)
    file_id: str = Field(default="", max_length=64)
    account: str = Field(default="", max_length=64)
    case_tag_id: str = Field(default="", max_length=64)
    case_tag: str = Field(default="", max_length=128)


class CopilotRequest(BaseModel):
    question: str = Field(default="", max_length=2000)
    scope: CopilotScopeRequest = Field(default_factory=CopilotScopeRequest)
    operator: str = Field(default="analyst", max_length=255)
    model: str = Field(default="", max_length=100)
    max_transactions: int = Field(default=20, ge=1, le=50)
    task_mode: str = Field(default="freeform", max_length=64)


@router.get("/status")
async def api_llm_status():
    """Check Ollama connection and available models."""
    return await check_ollama_status()


@router.get("/accounts")
async def api_llm_accounts():
    """List all accounts in the database with summary stats."""
    import asyncio
    return await asyncio.to_thread(get_all_accounts_summary)


@router.get("/account/{account}")
async def api_llm_account_summary(account: str):
    """Get detailed summary for a specific account from the database."""
    import asyncio
    return await asyncio.to_thread(get_account_summary, account)


@router.post("/chat")
async def api_llm_chat(req: ChatRequest):
    """
    Chat with the LLM. When an account is specified, the system
    automatically queries the database for that account's transactions
    and summary — no need to pass transactions manually.
    """
    try:
        result = await chat(
            req.message,
            account=req.account,
            transactions=req.transactions if req.transactions else None,
            model=req.model,
        )
        return result
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/summarize")
async def api_llm_summarize(req: SummarizeRequest):
    """Summarize an account — auto-pulls data from database."""
    try:
        result = await summarize_account(req.account, model=req.model)
        return result
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/classify")
async def api_llm_classify(req: ClassifyRequest):
    """Classify a single transaction as normal/suspicious/review."""
    if not req.transaction:
        raise HTTPException(status_code=400, detail="ต้องระบุข้อมูลธุรกรรม")
    try:
        result = await classify_transaction(req.transaction, model=req.model)
        return result
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/classification-preview")
async def api_llm_classification_preview(req: ClassificationPreviewRequest):
    """Run a read-only local transaction classification preview."""
    has_transactions = bool(req.transactions)
    has_scope = any(str((req.scope or {}).get(key) or "").strip() for key in ("parser_run_id", "file_id", "account"))
    if not has_transactions and not has_scope:
        raise HTTPException(status_code=400, detail="ต้องระบุรายการธุรกรรมหรือ scope อย่างน้อย 1 รายการ")
    model = ""
    if req.model.strip():
        try:
            model = _validate_model(req.model.strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    try:
        import asyncio
        if has_transactions:
            result = await asyncio.to_thread(
                build_classification_preview,
                req.transactions,
                model=model,
            )
        else:
            def run_scoped_preview():
                with get_db_session() as session:
                    return build_scoped_classification_preview(
                        session,
                        req.scope,
                        model=model,
                        max_transactions=req.max_transactions,
                    )

            result = await asyncio.to_thread(run_scoped_preview)
        return JSONResponse(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/benchmark")
async def api_llm_benchmark(req: BenchmarkRequest):
    """Run a small local-only benchmark against configured Ollama model roles."""
    try:
        overrides = {
            role: _validate_model(model.strip())
            for role, model in req.model_overrides.items()
            if model.strip()
        }
        result = await benchmark_llm_roles(
            roles=req.roles,
            iterations=req.iterations,
            include_vision=req.include_vision,
            model_overrides=overrides,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/copilot")
async def api_llm_copilot(req: CopilotRequest):
    """Answer a scoped, read-only investigation question with evidence citations."""
    model = ""
    if req.model.strip():
        try:
            model = _validate_model(req.model.strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    scope_payload = req.scope.model_dump() if hasattr(req.scope, "model_dump") else req.scope.dict()
    with get_db_session() as session:
        try:
            result = await answer_copilot_question(
                session,
                question=req.question,
                scope=scope_payload,
                operator=req.operator,
                model=model,
                max_transactions=req.max_transactions,
                task_mode=req.task_mode,
            )
            session.commit()
            return JSONResponse(result)
        except CopilotNotFoundError as exc:
            session.rollback()
            raise HTTPException(status_code=404, detail=str(exc))
        except CopilotScopeError as exc:
            session.rollback()
            raise HTTPException(status_code=400, detail=str(exc))
        except ConnectionError as exc:
            session.commit()
            raise HTTPException(status_code=503, detail=str(exc))
        except RuntimeError as exc:
            session.commit()
            raise HTTPException(status_code=502, detail=str(exc))


ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/bmp"}
ALLOWED_DOC_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
}
ALLOWED_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_DOC_TYPES
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/analyze-file")
async def api_llm_analyze_file(
    file: UploadFile = File(...),
    message: str = Form(default="วิเคราะห์เอกสารนี้ สรุปข้อมูลที่พบ"),
    model: str = Form(default=""),
):
    """
    Upload a file for LLM analysis.

    - **Images** (PNG, JPEG, WebP, BMP): sent directly to the configured vision model.
    - **PDF**: first page rendered to image, then sent to vision.
    - **Excel/CSV**: parsed to text rows, then sent to the configured text model.
    """
    from services.llm_service import chat_with_file, chat

    content_type = file.content_type or ""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # Infer type from extension if content_type is generic
    if content_type == "application/octet-stream" or content_type not in ALLOWED_TYPES:
        ext_map = {
            "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp", "bmp": "image/bmp",
            "pdf": "application/pdf",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xls": "application/vnd.ms-excel",
            "csv": "text/csv",
        }
        content_type = ext_map.get(ext, content_type)

    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"ไม่รองรับไฟล์ประเภท {content_type} — รองรับ: รูปภาพ, PDF, Excel, CSV",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="ไฟล์ใหญ่เกิน 20 MB")

    try:
        if content_type in ALLOWED_IMAGE_TYPES:
            # Direct multimodal vision
            result = await chat_with_file(message, file_bytes, content_type, model=model)

        elif content_type == "application/pdf":
            # Render first page of PDF to image, then send to vision
            import fitz  # PyMuPDF

            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = doc.page_count
            page = doc[0]
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            doc.close()
            result = await chat_with_file(
                f"{message}\n(ไฟล์ PDF: {filename}, {page_count} หน้า — แสดงหน้าแรก)",
                img_bytes, "image/png", model=model,
            )

        else:
            # Excel/CSV — parse to text and use text chat
            import io
            text_rows: list[str] = []

            if content_type == "text/csv" or ext == "csv":
                import csv
                reader = csv.reader(io.StringIO(file_bytes.decode("utf-8", errors="replace")))
                for i, row in enumerate(reader):
                    if i >= 60:
                        text_rows.append(f"... (แสดง 60 แถวแรก)")
                        break
                    text_rows.append(" | ".join(row))
            else:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
                ws = wb.active
                if ws:
                    for i, row in enumerate(ws.iter_rows(values_only=True)):
                        if i >= 60:
                            text_rows.append(f"... (แสดง 60 แถวแรก)")
                            break
                        text_rows.append(" | ".join(str(c or "") for c in row))
                wb.close()

            file_text = f"ไฟล์: {filename}\n\n" + "\n".join(text_rows)
            result = await chat(
                f"{message}\n\nข้อมูลจากไฟล์:\n{file_text}",
                auto_context=False, model=model,
            )

        return result
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.exception("LLM analyze-file error")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {exc}")
