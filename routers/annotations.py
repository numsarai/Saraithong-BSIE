"""
routers/annotations.py
----------------------
Graph annotations API: notes and tags on nodes.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from persistence.base import get_db_session, utcnow
from persistence.models import GraphAnnotation

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


@router.get("")
async def api_list_annotations(node_id: str = "", limit: int = 100):
    with get_db_session() as session:
        q = select(GraphAnnotation).order_by(GraphAnnotation.created_at.desc())
        if node_id:
            q = q.where(GraphAnnotation.node_id == node_id)
        rows = session.scalars(q.limit(limit)).all()
        items = [
            {"id": r.id, "node_id": r.node_id, "type": r.annotation_type, "content": r.content,
             "tag": r.tag, "created_by": r.created_by, "created_at": str(r.created_at)}
            for r in rows
        ]
    return JSONResponse({"items": items})


@router.post("")
async def api_create_annotation(request: Request):
    payload = await request.json()
    node_id = str(payload.get("node_id", ""))
    if not node_id:
        raise HTTPException(400, "node_id required")
    with get_db_session() as session:
        ann = GraphAnnotation(
            node_id=node_id,
            annotation_type=str(payload.get("type", "note")),
            content=str(payload.get("content", "")),
            tag=str(payload.get("tag", "")) or None,
            created_by=str(payload.get("created_by", "analyst")),
            created_at=utcnow(),
        )
        session.add(ann)
        session.commit()
        return JSONResponse({"id": ann.id, "node_id": ann.node_id, "status": "created"})


@router.delete("/{annotation_id}")
async def api_delete_annotation(annotation_id: str):
    with get_db_session() as session:
        ann = session.get(GraphAnnotation, annotation_id)
        if not ann:
            raise HTTPException(404, "Annotation not found")
        session.delete(ann)
        session.commit()
    return JSONResponse({"status": "deleted"})
