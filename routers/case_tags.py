"""
routers/case_tags.py
--------------------
Case tag management endpoints.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import select

from persistence.base import get_db_session
from persistence.models import CaseTag, CaseTagLink
from persistence.schemas import CaseTagAssignRequest, CaseTagRequest

router = APIRouter(prefix="/api", tags=["case-tags"])


@router.get("/case-tags")
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
