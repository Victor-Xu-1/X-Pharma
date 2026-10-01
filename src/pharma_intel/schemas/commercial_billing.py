from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class CommercialUsageAdjustmentCreate(BaseModel):
    subscription_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")
    adjustment_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")
    units_delta: Decimal = Field(max_digits=28, decimal_places=8)
    reason: str = Field(min_length=1, max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommercialReversalCreate(BaseModel):
    adjustment_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")
    reason: str = Field(min_length=1, max_length=1000)


class CommercialAdjustmentRead(BaseModel):
    id: str
    subscription_id: str
    adjustment_key: str
    adjustment_kind: str
    reverses_adjustment_id: str | None
    reverses_settlement_id: str | None
    units_delta: str
    reason: str
    request_id: str
    created_by: str
    created_at: datetime


class CommercialExpirationRequest(BaseModel):
    limit: int = Field(default=1000, ge=1, le=10_000)


class CommercialExpirationRead(BaseModel):
    expired_reservations: int
    released_units: str
    completed_at: datetime


class CommercialReconciliationCreate(BaseModel):
    subscription_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,119}$")
    run_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")


class CommercialReconciliationRead(BaseModel):
    id: str
    subscription_id: str
    run_key: str
    status: str
    issue_count: int
    snapshot_granted_units: str
    snapshot_reserved_units: str
    snapshot_consumed_units: str
    ledger_granted_units: str
    ledger_reserved_units: str
    ledger_consumed_units: str
    source_granted_units: str
    source_reserved_units: str
    source_consumed_units: str
    issues: list[dict[str, Any]]
    requested_by: str
    request_id: str
    started_at: datetime
    completed_at: datetime


class BillingStatementCreate(BaseModel):
    subscription_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,119}$")
    statement_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")
    period_start: datetime
    period_end: datetime
    revision: int = Field(default=1, ge=1)


class BillingStatementRead(BaseModel):
    id: str
    subscription_id: str
    billing_account_id: str
    statement_key: str
    revision: int
    period_start: datetime
    period_end: datetime
    settlement_units: str
    adjustment_units: str
    net_consumed_units: str
    settlement_count: int
    adjustment_count: int
    result_count: int
    response_bytes: int
    manifest_sha256: str
    signature_key_id: str
    manifest_signature: str
    payload: dict[str, Any]
    generated_by: str
    request_id: str
    generated_at: datetime


class BillingAccountRead(BaseModel):
    id: str
    account_key: str
    display_name: str
    currency: str
    status: Literal["active", "suspended", "closed"]
    mapping_configured: bool
    external_customer_reference_masked: str | None
    statement_count: int
    unresolved_statement_count: int
    invoice_count: int
    updated_at: datetime


class BillingCustomerMappingUpdate(BaseModel):
    external_customer_reference: str = Field(
        min_length=1,
        max_length=500,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,499}$",
    )
    reason: str = Field(min_length=3, max_length=500)


class BillingDeliveryRead(BaseModel):
    delivery_id: str | None
    event_id: str
    statement_id: str
    statement_key: str
    billing_account_id: str
    billing_account_key: str
    billing_account_name: str
    state: Literal["pending", "processing", "retry", "succeeded", "dead"]
    attempts: int
    available_at: datetime
    lease_expires_at: datetime | None
    processed_at: datetime | None
    last_error: str | None
    invoice_provider: str | None
    external_invoice_id: str | None
    invoice_status: str | None
    created_at: datetime


class BillingDeliveryReplayRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class BillingDisputeCreate(BaseModel):
    dispute_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,119}$")
    statement_id: str = Field(min_length=1, max_length=36)
    invoice_reference_id: str | None = Field(default=None, min_length=1, max_length=36)
    category: Literal["usage", "pricing", "duplicate", "authorization", "service", "other"]
    disputed_units: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=4000)


class BillingDisputeTransition(BaseModel):
    operation_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,119}$")
    expected_version: int = Field(ge=1)
    action: Literal["investigate", "resolve_credit", "resolve_no_credit", "reject", "cancel"]
    notes: str = Field(min_length=3, max_length=4000)
    assigned_to: str | None = Field(default=None, min_length=1, max_length=500)
    adjustment_key: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")
    credit_units: Decimal | None = Field(default=None, gt=0, max_digits=28, decimal_places=8)

    @model_validator(mode="after")
    def validate_credit_fields(self) -> BillingDisputeTransition:
        if self.action == "resolve_credit":
            if self.adjustment_key is None or self.credit_units is None:
                raise ValueError("Credit resolution requires adjustment_key and credit_units")
        elif self.adjustment_key is not None or self.credit_units is not None:
            raise ValueError("Adjustment fields are only accepted for credit resolution")
        return self


class BillingDisputeRead(BaseModel):
    id: str
    dispute_key: str
    billing_account_id: str
    billing_account_key: str
    billing_account_name: str
    subscription_id: str
    statement_id: str
    statement_key: str
    invoice_reference_id: str | None
    external_invoice_id: str | None
    status: Literal["open", "investigating", "resolved", "rejected", "cancelled"]
    category: Literal["usage", "pricing", "duplicate", "authorization", "service", "other"]
    disputed_units: str
    subject: str
    description: str
    opened_by: str
    opened_at: datetime
    assigned_to: str | None
    due_at: datetime
    overdue: bool
    resolution_code: str | None
    resolution_notes: str
    resolved_by: str | None
    resolved_at: datetime | None
    resolution_adjustment_key: str | None
    version: int
    created_at: datetime
    updated_at: datetime
