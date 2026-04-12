"""
routers/workspace.py
--------------------
Workspace management: save/load link chart state.
"""

import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from persistence.base import get_db_session, utcnow
from persistence.models import AdminSetting

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

WORKSPACE_PREFIX = "workspace:"


@router.get("")
async def api_list_workspaces():
    with get_db_session() as session:
        rows = session.scalars(
            select(AdminSetting).where(AdminSetting.key.startswith(WORKSPACE_PREFIX))
        ).all()
        items = [
            {"id": r.key.replace(WORKSPACE_PREFIX, ""), "name": (r.value_json or {}).get("name", "Untitled"),
             "updated_at": str(r.updated_at), "updated_by": r.updated_by,
             "node_count": len((r.value_json or {}).get("expanded_nodes", []))}
            for r in rows
        ]
    return JSONResponse({"items": items})


@router.post("")
async def api_save_workspace(request: Request):
    payload = await request.json()
    ws_id = payload.get("id") or str(uuid.uuid4())[:8]
    key = f"{WORKSPACE_PREFIX}{ws_id}"
    reviewer = str(payload.pop("reviewer", "analyst"))

    with get_db_session() as session:
        row = session.get(AdminSetting, key)
        if row:
            row.value_json = payload
            row.updated_at = utcnow()
            row.updated_by = reviewer
        else:
            row = AdminSetting(key=key, value_json=payload, updated_at=utcnow(), updated_by=reviewer)
            session.add(row)
        session.commit()
    return JSONResponse({"id": ws_id, "status": "saved"})


@router.get("/{workspace_id}")
async def api_get_workspace(workspace_id: str):
    with get_db_session() as session:
        row = session.get(AdminSetting, f"{WORKSPACE_PREFIX}{workspace_id}")
        if not row:
            raise HTTPException(404, "Workspace not found")
        data = dict(row.value_json or {})
        data["id"] = workspace_id
    return JSONResponse(data)


@router.delete("/{workspace_id}")
async def api_delete_workspace(workspace_id: str):
    with get_db_session() as session:
        row = session.get(AdminSetting, f"{WORKSPACE_PREFIX}{workspace_id}")
        if not row:
            raise HTTPException(404, "Workspace not found")
        session.delete(row)
        session.commit()
    return JSONResponse({"status": "deleted"})
