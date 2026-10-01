from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class CommercialClientSubjectRead(BaseModel):
    actor_type: str
    subject_id: str
    active: bool


class CommercialClientRead(BaseModel):
    id: str
    client_key: str
    display_name: str
    active: bool
    subjects: list[CommercialClientSubjectRead]
    subscription_key: str | None
    subscription_status: str | None
    billing_account_key: str | None
    available_units: str | None
    active_reservations: int
    denial_count_24h: int
    last_policy_event_at: datetime | None
    created_at: datetime


class CommercialClientStatusUpdate(BaseModel):
    active: bool
    reason: str = Field(min_length=3, max_length=500)


class CommercialRiskEventRead(BaseModel):
    id: str
    client_id: str
    client_key: str
    client_name: str
    actor_type: str
    subject_id: str
    entitlement_key: str
    phase: str
    reason_code: str
    query_sha256: str
    page_depth: int
    requested_records: int
    existing_unique_records: int
    projected_unique_records: int
    request_id: str
    details: dict[str, Any]
    occurred_at: datetime
    case_status: Literal["open", "acknowledged", "resolved", "dismissed"]
    case_notes: str
    reviewed_by: str | None
    reviewed_at: datetime | None


class CommercialRiskEventPageRead(BaseModel):
    items: list[CommercialRiskEventRead]
    total_items: int = Field(ge=0)
    next_cursor: str | None


class CommercialRiskReview(BaseModel):
    status: Literal["acknowledged", "resolved", "dismissed"]
    notes: str = Field(default="", max_length=2000)
