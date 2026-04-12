"""
response_models.py
------------------
Standardized Pydantic response models for API consistency.
All list endpoints return { items: [], total: int }.
All mutation endpoints return { status: str, ... }.
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ListResponse(BaseModel):
    """Standard paginated list response."""
    items: list[Any]
    total: int = 0


class StatusResponse(BaseModel):
    """Standard mutation response."""
    status: str = "ok"
    message: str = ""


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    code: str = "error"


class DashboardResponse(BaseModel):
    """Dashboard overview data."""
    counts: dict[str, int]
    totals: dict[str, float]
    alerts: dict[str, int]
    recent_activity: list[dict[str, Any]]
    top_accounts: list[dict[str, Any]]


class AlertSummaryResponse(BaseModel):
    """Alert summary counts."""
    total: int = 0
    by_severity: dict[str, int] = {}
    by_status: dict[str, int] = {}
    new_count: int = 0
    critical_count: int = 0
    high_count: int = 0


class SnaResponse(BaseModel):
    """Social Network Analysis metrics."""
    nodes: list[dict[str, Any]]
    summary: dict[str, Any]
