"""
routers/case_tags.py
--------------------
Case tag management endpoints.
"""

from decimal import Decimal
from typing import Any

from fastapi import Depends, APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from persistence.base import get_db_session
from persistence.models import Account, Alert, CaseTag, CaseTagLink, FileRecord, ParserRun, Transaction
from persistence.schemas import CaseTagAssignRequest, CaseTagRequest
from services.auth_service import require_auth

router = APIRouter(prefix="/api", tags=["case-tags"], dependencies=[Depends(require_auth)])


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _short_text(value: str | None, limit: int = 140) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _citation_id(object_type: str, object_id: str) -> str:
    citation_type_by_object = {
        "txn": "txn",
        "transaction": "txn",
        "account": "account",
        "file": "file",
        "file_record": "file",
        "run": "run",
        "parser_run": "run",
        "alert": "alert",
    }
    citation_type = citation_type_by_object.get(str(object_type or "").strip().lower())
    return f"{citation_type}:{object_id}" if citation_type else ""


def _case_tag_summary(row: CaseTag, link_counts: dict[str, dict[str, int]]) -> dict[str, Any]:
    counts = link_counts.get(row.id, {})
    return {
        "id": row.id,
        "tag": row.tag,
        "description": row.description,
        "created_at": _iso(row.created_at),
        "linked_object_count": sum(counts.values()),
        "linked_object_counts": counts,
    }


def _link_scope(session, object_type: str, object_id: str, row: Any | None) -> dict[str, str]:
    normalized = str(object_type or "").strip().lower()
    if normalized in {"file", "file_record"}:
        return {"file_id": object_id}
    if normalized in {"parser_run", "run"}:
        return {"parser_run_id": object_id}
    if normalized == "account":
        account = row if isinstance(row, Account) else session.get(Account, object_id)
        if account:
            return {"account": account.normalized_account_number or account.display_account_number or object_id}
        return {"account": object_id}
    if normalized in {"transaction", "txn"} and isinstance(row, Transaction):
        return {"parser_run_id": row.parser_run_id or "", "file_id": row.file_id or ""}
    if normalized == "alert" and isinstance(row, Alert):
        scope: dict[str, str] = {}
        if row.parser_run_id:
            scope["parser_run_id"] = row.parser_run_id
        if row.account_id:
            account = session.get(Account, row.account_id)
            if account:
                scope["account"] = account.normalized_account_number or account.display_account_number or row.account_id
        return scope
    return {}


def _link_detail(session, link: CaseTagLink) -> dict[str, Any]:
    object_type = str(link.object_type or "").strip()
    object_id = str(link.object_id or "").strip()
    normalized = object_type.lower()
    row: Any | None = None
    label = object_id
    summary = ""
    meta: dict[str, Any] = {}

    if normalized in {"file", "file_record"}:
        row = session.get(FileRecord, object_id)
        if row:
            label = row.original_filename
            summary = row.import_status
            meta = {"bank_detected": row.bank_detected or "", "uploaded_at": _iso(row.uploaded_at)}
    elif normalized in {"parser_run", "run"}:
        row = session.get(ParserRun, object_id)
        if row:
            label = f"{row.status} {row.bank_detected or ''}".strip()
            summary = row.parser_version
            meta = {
                "file_id": row.file_id,
                "started_at": _iso(row.started_at),
                "warning_count": row.warning_count,
                "error_count": row.error_count,
            }
    elif normalized == "account":
        row = session.get(Account, object_id)
        if row:
            display = row.display_account_number or row.normalized_account_number or row.id
            label = display
            summary = row.account_holder_name or row.bank_code or row.bank_name or ""
            meta = {"bank_code": row.bank_code or "", "status": row.status}
    elif normalized in {"transaction", "txn"}:
        row = session.get(Transaction, object_id)
        if row:
            amount = _as_float(row.amount)
            label = f"{row.direction} {abs(amount):,.2f} {row.currency}"
            summary = _short_text(row.description_raw or row.description_normalized)
            meta = {
                "parser_run_id": row.parser_run_id,
                "file_id": row.file_id,
                "account_id": row.account_id or "",
                "transaction_datetime": _iso(row.transaction_datetime),
                "review_status": row.review_status,
            }
    elif normalized == "alert":
        row = session.get(Alert, object_id)
        if row:
            label = f"{row.severity} {row.rule_type}"
            summary = _short_text(row.summary)
            meta = {
                "transaction_id": row.transaction_id or "",
                "parser_run_id": row.parser_run_id or "",
                "account_id": row.account_id or "",
                "status": row.status,
            }

    return {
        "link_id": link.id,
        "object_type": object_type,
        "object_id": object_id,
        "citation_id": _citation_id(object_type, object_id),
        "created_at": _iso(link.created_at),
        "found": row is not None,
        "label": label,
        "summary": summary,
        "scope": {key: value for key, value in _link_scope(session, object_type, object_id, row).items() if value},
        "meta": meta,
    }


def _link_counts(session) -> dict[str, dict[str, int]]:
    count_rows = session.execute(
        select(
            CaseTagLink.case_tag_id,
            CaseTagLink.object_type,
            func.count(CaseTagLink.id),
        ).group_by(CaseTagLink.case_tag_id, CaseTagLink.object_type)
    ).all()
    link_counts_by_tag: dict[str, dict[str, int]] = {}
    for case_tag_id, object_type, count in count_rows:
        if not case_tag_id or not object_type:
            continue
        tag_counts = link_counts_by_tag.setdefault(str(case_tag_id), {})
        tag_counts[str(object_type)] = int(count or 0)
    return link_counts_by_tag


@router.get("/case-tags")
async def api_case_tags():
    with get_db_session() as session:
        rows = session.scalars(select(CaseTag).order_by(CaseTag.tag.asc())).all()
        link_counts_by_tag = _link_counts(session)
        return JSONResponse({
            "items": [_case_tag_summary(row, link_counts_by_tag) for row in rows]
        })


@router.get("/case-tags/{case_tag_id}")
async def api_case_tag_detail(case_tag_id: str, limit: int = 100):
    bounded_limit = max(1, min(200, int(limit or 100)))
    with get_db_session() as session:
        row = session.get(CaseTag, case_tag_id)
        if row is None:
            raise HTTPException(404, "Case tag not found")
        link_counts_by_tag = _link_counts(session)
        links = list(
            session.scalars(
                select(CaseTagLink)
                .where(CaseTagLink.case_tag_id == row.id)
                .order_by(CaseTagLink.created_at.desc(), CaseTagLink.id.asc())
                .limit(bounded_limit)
            )
        )
        payload = _case_tag_summary(row, link_counts_by_tag)
        payload["links"] = [_link_detail(session, link) for link in links]
        payload["limit"] = bounded_limit
        return JSONResponse(payload)


@router.post("/case-tags")
async def api_case_tags_create(body: CaseTagRequest):
    with get_db_session() as session:
        row = CaseTag(tag=body.tag.strip(), description=body.description or None)
        session.add(row)
        session.commit()
        return JSONResponse({"id": row.id, "tag": row.tag, "description": row.description})


@router.post("/case-tags/assign")
async def api_case_tags_assign(body: CaseTagAssignRequest):
    with get_db_session() as session:
        link = CaseTagLink(
            case_tag_id=body.case_tag_id,
            object_type=body.object_type,
            object_id=body.object_id,
        )
        session.add(link)
        session.commit()
        return JSONResponse({"status": "ok", "link_id": link.id})
