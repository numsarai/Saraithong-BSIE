"""
routers/case_tags.py
--------------------
Case tag management endpoints.
"""

from services.auth_service import require_auth
from fastapi import Depends, APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from persistence.base import get_db_session
from persistence.models import CaseTag, CaseTagLink
from persistence.schemas import CaseTagAssignRequest, CaseTagRequest

router = APIRouter(prefix="/api", tags=["case-tags"], dependencies=[Depends(require_auth)])


@router.get("/case-tags")
async def api_case_tags():
    with get_db_session() as session:
        rows = session.scalars(select(CaseTag).order_by(CaseTag.tag.asc())).all()
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
        return JSONResponse({
            "items": [
                {
                    "id": row.id,
                    "tag": row.tag,
                    "description": row.description,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "linked_object_count": sum(link_counts_by_tag.get(row.id, {}).values()),
                    "linked_object_counts": link_counts_by_tag.get(row.id, {}),
                }
                for row in rows
            ]
        })


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
