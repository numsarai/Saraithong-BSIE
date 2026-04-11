"""
report_template_service.py
--------------------------
Manage report templates and analysis criteria stored in AdminSetting.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.base import utcnow
from persistence.models import AdminSetting

TEMPLATE_KEY_PREFIX = "report_template:"
CRITERIA_KEY_PREFIX = "analysis_criteria:"

DEFAULT_TEMPLATE: dict[str, Any] = {
    "name": "รายงานมาตรฐาน",
    "sections": [
        {"type": "cover", "enabled": True},
        {"type": "summary", "enabled": True},
        {"type": "counterparties", "enabled": True, "limit": 20},
        {"type": "anomalies", "enabled": False, "method": "zscore", "sigma": 2.0},
        {"type": "alerts", "enabled": True, "min_severity": "medium"},
        {"type": "transactions", "enabled": True, "limit": 50, "sort": "amount_desc"},
        {"type": "signature", "enabled": True},
    ],
    "criteria": {
        "min_amount": 0,
        "min_txn_per_day": 0,
        "min_confidence": 0.0,
        "flag_rules": [],
    },
}


def list_templates(session: Session) -> list[dict[str, Any]]:
    """List all saved report templates."""
    rows = session.scalars(
        select(AdminSetting).where(AdminSetting.key.startswith(TEMPLATE_KEY_PREFIX))
    ).all()
    templates = []
    for row in rows:
        tpl = dict(row.value_json or {})
        tpl["id"] = row.key.replace(TEMPLATE_KEY_PREFIX, "")
        tpl["updated_at"] = str(row.updated_at)
        tpl["updated_by"] = row.updated_by
        templates.append(tpl)
    if not templates:
        templates.append({**DEFAULT_TEMPLATE, "id": "default"})
    return templates


def get_template(session: Session, template_id: str) -> dict[str, Any]:
    """Get a specific report template."""
    key = f"{TEMPLATE_KEY_PREFIX}{template_id}"
    row = session.get(AdminSetting, key)
    if row and row.value_json:
        tpl = dict(row.value_json)
        tpl["id"] = template_id
        return tpl
    if template_id == "default":
        return {**DEFAULT_TEMPLATE, "id": "default"}
    return {}


def save_template(session: Session, template: dict[str, Any], updated_by: str = "analyst") -> dict[str, Any]:
    """Save or update a report template."""
    template_id = template.get("id") or str(uuid.uuid4())[:8]
    key = f"{TEMPLATE_KEY_PREFIX}{template_id}"

    data = {k: v for k, v in template.items() if k != "id"}
    row = session.get(AdminSetting, key)
    if row:
        row.value_json = data
        row.updated_at = utcnow()
        row.updated_by = updated_by
    else:
        row = AdminSetting(key=key, value_json=data, updated_at=utcnow(), updated_by=updated_by)
        session.add(row)
    session.commit()
    return {**data, "id": template_id}


def delete_template(session: Session, template_id: str) -> bool:
    """Delete a report template."""
    key = f"{TEMPLATE_KEY_PREFIX}{template_id}"
    row = session.get(AdminSetting, key)
    if not row:
        return False
    session.delete(row)
    session.commit()
    return True


def list_criteria(session: Session) -> list[dict[str, Any]]:
    """List all saved analysis criteria."""
    rows = session.scalars(
        select(AdminSetting).where(AdminSetting.key.startswith(CRITERIA_KEY_PREFIX))
    ).all()
    result = []
    for row in rows:
        c = dict(row.value_json or {})
        c["id"] = row.key.replace(CRITERIA_KEY_PREFIX, "")
        result.append(c)
    return result


def save_criteria(session: Session, criteria: dict[str, Any], updated_by: str = "analyst") -> dict[str, Any]:
    """Save analysis criteria."""
    criteria_id = criteria.get("id") or str(uuid.uuid4())[:8]
    key = f"{CRITERIA_KEY_PREFIX}{criteria_id}"
    data = {k: v for k, v in criteria.items() if k != "id"}
    row = session.get(AdminSetting, key)
    if row:
        row.value_json = data
        row.updated_at = utcnow()
        row.updated_by = updated_by
    else:
        row = AdminSetting(key=key, value_json=data, updated_at=utcnow(), updated_by=updated_by)
        session.add(row)
    session.commit()
    return {**data, "id": criteria_id}
