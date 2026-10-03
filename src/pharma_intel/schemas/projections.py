from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class ProjectionMaintenanceRequest(BaseModel):
    operation: Literal["consistency_check", "rebuild"]


class ProjectionMaintenanceAccessRead(BaseModel):
    allowed: bool


class ProjectionMaintenanceJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation: Literal["consistency_check", "rebuild"]
    status: Literal["queued", "running", "succeeded", "failed"]
    build_id: str | None
    requested_by_user_id: str
    attempts: int
    worker_id: str | None
    lease_expires_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    result: dict[str, Any]
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class SearchProjectionStatusRead(BaseModel):
    available: bool
    version: str | None
    cluster_name: str | None
    cluster_status: str | None
    aliases: dict[str, list[str]]
    deliveries: dict[str, int]
    error: str | None = None
