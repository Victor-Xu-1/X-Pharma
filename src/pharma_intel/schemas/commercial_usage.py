from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from pharma_intel.models.enums import (
    UsageReservationState,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class CommercialEntitlementRead(BaseModel):
    key: str
    max_result_rows: int
    daily_unit_limit: str | None
    max_page_depth: int
    daily_unique_record_limit: int | None
    max_response_bytes: int
    data_domains: list[str]


class CommercialAccessRead(BaseModel):
    client_id: str
    subscription_id: str
    status: str
    available_units: str
    consumed_units: str
    reserved_units: str
    entitlements: list[CommercialEntitlementRead]
    as_of: datetime


class CommercialEstimateRequest(BaseModel):
    billing_class: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    requested_result_limit: int = Field(gt=0, le=5000)
    requested_compute_units: Decimal = Field(default=Decimal("0"), ge=0, max_digits=28, decimal_places=8)


class CommercialEstimateRead(BaseModel):
    billing_class: str
    entitlement_key: str
    requested_result_limit: int
    requested_compute_units: str
    estimated_units_before_response_bytes: str
    base_units: str
    per_result_units: str
    per_kib_units: str
    per_compute_unit: str
    maximum_licensed_result_rows: int
    available_units: str
    rate_card_key: str
    rate_card_revision: int
    currency: str
    as_of: datetime


class CommercialUsageSummaryRead(BaseModel):
    client_id: str
    subscription_id: str
    rate_card_key: str
    rate_card_revision: int
    currency: str
    period_start: datetime
    as_of: datetime
    settlement_count: int
    charged_units: str
    result_count: int
    response_bytes: int
    active_reservations: int
    granted_units: str
    consumed_units: str
    reserved_units: str
    available_units: str
    latest_statement_id: str | None
    latest_statement_period_end: datetime | None


class CommercialDailyUsageRead(BaseModel):
    settlement_count: int
    result_count: int
    unique_record_count: int
    new_unique_record_count: int
    response_bytes: int


class CommercialSubscriptionOverviewRead(BaseModel):
    subscription_id: str
    subscription_key: str
    status: str
    client_key: str
    client_name: str
    billing_account_key: str
    billing_account_name: str
    rate_card_key: str
    rate_card_revision: int
    starts_at: datetime
    ends_at: datetime | None
    granted_units: str
    consumed_units: str
    reserved_units: str
    available_units: str
    active_reservations: int
    daily_unique_records: int
    daily_usage: CommercialDailyUsageRead
    entitlements: list[CommercialEntitlementRead]


class CommercialOverviewRead(BaseModel):
    as_of: datetime
    period_start: datetime
    open_risk_count: int = Field(ge=0)
    active_client_count: int = Field(default=0, ge=0)
    pending_export_count: int = Field(default=0, ge=0)
    dead_billing_delivery_count: int = Field(default=0, ge=0)
    open_dispute_count: int = Field(default=0, ge=0)
    subscriptions: list[CommercialSubscriptionOverviewRead]


class CommercialReserveRequest(BaseModel):
    billing_class: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    request_arguments: dict[str, Any]
    requested_result_limit: int = Field(gt=0, le=5000)
    max_billable_units: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    requested_compute_units: Decimal = Field(default=Decimal("0"), ge=0, max_digits=28, decimal_places=8)


class CommercialSettlementRequest(BaseModel):
    result_count: int = Field(ge=0, le=5000)
    result: dict[str, Any] | list[Any]
    metrics: dict[str, Any] = Field(default_factory=dict)


class CommercialReleaseRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class CommercialSettlementRead(BaseModel):
    settlement_id: str
    usage_event_id: str
    charged_units: str
    result_count: int
    unique_record_count: int
    new_unique_record_count: int
    response_bytes: int
    price_breakdown: dict[str, Any]
    result: dict[str, Any] | list[Any]
    created_at: datetime


class CommercialReservationRead(BaseModel):
    reservation_id: str
    state: UsageReservationState
    billing_class: str
    estimated_units: str
    reserved_units: str
    requested_compute_units: str
    lease_expires_at: datetime
    page_depth: int
    replayed: bool
    settlement: CommercialSettlementRead | None = None
