from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class BillingAdjustment(Base):
    __tablename__ = "billing_adjustments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "adjustment_key"),
        UniqueConstraint(
            "tenant_id",
            "reverses_adjustment_id",
            name="uq_billing_adjustment_single_reversal",
        ),
        UniqueConstraint(
            "tenant_id",
            "reverses_settlement_id",
            name="uq_billing_settlement_single_reversal",
        ),
        CheckConstraint("units_delta != 0", name="ck_billing_adjustment_nonzero"),
        CheckConstraint(
            "adjustment_kind IN ('usage_adjustment', 'settlement_reversal', 'adjustment_reversal')",
            name="ck_billing_adjustment_kind",
        ),
        CheckConstraint(
            "(adjustment_kind = 'usage_adjustment' "
            "AND reverses_adjustment_id IS NULL AND reverses_settlement_id IS NULL) "
            "OR (adjustment_kind = 'settlement_reversal' "
            "AND reverses_adjustment_id IS NULL AND reverses_settlement_id IS NOT NULL AND units_delta < 0) "
            "OR (adjustment_kind = 'adjustment_reversal' "
            "AND reverses_adjustment_id IS NOT NULL AND reverses_settlement_id IS NULL)",
            name="ck_billing_adjustment_reference",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    adjustment_key: Mapped[str] = mapped_column(String(200), nullable=False)
    adjustment_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    reverses_adjustment_id: Mapped[str | None] = mapped_column(ForeignKey("billing_adjustments.id"), index=True)
    reverses_settlement_id: Mapped[str | None] = mapped_column(ForeignKey("usage_settlements.id"), index=True)
    units_delta: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_by: Mapped[str] = mapped_column(String(500), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class CommercialReconciliationRun(Base):
    __tablename__ = "commercial_reconciliation_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_key"),
        CheckConstraint("status IN ('clean', 'drift')", name="ck_commercial_reconciliation_status"),
        CheckConstraint("issue_count >= 0", name="ck_commercial_reconciliation_issue_count"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    run_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    issue_count: Mapped[int] = mapped_column(nullable=False)
    snapshot_granted_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    snapshot_reserved_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    snapshot_consumed_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    ledger_granted_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    ledger_reserved_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    ledger_consumed_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    source_granted_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    source_reserved_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    source_consumed_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    issues_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(500), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class BillingPeriodStatement(Base):
    __tablename__ = "billing_period_statements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "statement_key"),
        UniqueConstraint(
            "tenant_id",
            "subscription_id",
            "period_start",
            "period_end",
            "revision",
            name="uq_billing_statement_period_revision",
        ),
        UniqueConstraint("tenant_id", "manifest_sha256", name="uq_billing_statement_manifest"),
        CheckConstraint("period_end > period_start", name="ck_billing_statement_period"),
        CheckConstraint("revision > 0", name="ck_billing_statement_revision"),
        CheckConstraint("settlement_count >= 0", name="ck_billing_statement_settlement_count"),
        CheckConstraint("adjustment_count >= 0", name="ck_billing_statement_adjustment_count"),
        CheckConstraint("result_count >= 0", name="ck_billing_statement_result_count"),
        CheckConstraint("response_bytes >= 0", name="ck_billing_statement_response_bytes"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    billing_account_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.id"), index=True, nullable=False)
    statement_key: Mapped[str] = mapped_column(String(200), nullable=False)
    revision: Mapped[int] = mapped_column(nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    settlement_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    adjustment_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    net_consumed_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    settlement_count: Mapped[int] = mapped_column(nullable=False)
    adjustment_count: Mapped[int] = mapped_column(nullable=False)
    result_count: Mapped[int] = mapped_column(nullable=False)
    response_bytes: Mapped[int] = mapped_column(nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_key_id: Mapped[str] = mapped_column(String(120), nullable=False)
    manifest_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    generated_by: Mapped[str] = mapped_column(String(500), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class InvoiceReference(Base, TimestampMixin):
    __tablename__ = "invoice_references"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_invoice_id"),
        UniqueConstraint("statement_id", name="uq_invoice_reference_statement"),
        CheckConstraint("period_end > period_start", name="ck_invoice_period"),
        CheckConstraint("total_units >= 0", name="ck_invoice_total_units"),
        CheckConstraint("amount_due >= 0", name="ck_invoice_amount_due"),
        CheckConstraint("length(currency) = 3", name="ck_invoice_currency"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    billing_account_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.id"), index=True, nullable=False)
    statement_id: Mapped[str | None] = mapped_column(ForeignKey("billing_period_statements.id"), index=True)
    external_invoice_id: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    amount_due: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(100), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class BillingDispute(Base, TimestampMixin):
    __tablename__ = "billing_disputes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dispute_key"),
        CheckConstraint(
            "status IN ('open', 'investigating', 'resolved', 'rejected', 'cancelled')",
            name="ck_billing_dispute_status",
        ),
        CheckConstraint(
            "category IN ('usage', 'pricing', 'duplicate', 'authorization', 'service', 'other')",
            name="ck_billing_dispute_category",
        ),
        CheckConstraint("disputed_units > 0", name="ck_billing_dispute_positive_units"),
        CheckConstraint("version > 0", name="ck_billing_dispute_version"),
        CheckConstraint(
            "(status IN ('open', 'investigating') AND resolved_at IS NULL AND resolved_by IS NULL "
            "AND resolution_code IS NULL) OR "
            "(status = 'resolved' AND resolved_at IS NOT NULL AND resolved_by IS NOT NULL "
            "AND resolution_code IN ('credit', 'no_credit')) OR "
            "(status = 'rejected' AND resolved_at IS NOT NULL AND resolved_by IS NOT NULL "
            "AND resolution_code = 'rejected') OR "
            "(status = 'cancelled' AND resolved_at IS NOT NULL AND resolved_by IS NOT NULL "
            "AND resolution_code = 'cancelled')",
            name="ck_billing_dispute_resolution_state",
        ),
        CheckConstraint(
            "resolution_adjustment_key IS NULL OR (status = 'resolved' AND resolution_code = 'credit')",
            name="ck_billing_dispute_adjustment_state",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    dispute_key: Mapped[str] = mapped_column(String(120), nullable=False)
    billing_account_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    statement_id: Mapped[str] = mapped_column(ForeignKey("billing_period_statements.id"), index=True, nullable=False)
    invoice_reference_id: Mapped[str | None] = mapped_column(ForeignKey("invoice_references.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    disputed_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(4000), nullable=False)
    opened_by: Mapped[str] = mapped_column(String(500), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(500), index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    resolution_code: Mapped[str | None] = mapped_column(String(40))
    resolution_notes: Mapped[str] = mapped_column(String(4000), default="", nullable=False)
    resolved_by: Mapped[str | None] = mapped_column(String(500))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    resolution_adjustment_key: Mapped[str | None] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(default=1, nullable=False)


class BillingDisputeEvent(Base):
    __tablename__ = "billing_dispute_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dispute_id", "operation_key", name="uq_billing_dispute_operation"),
        CheckConstraint(
            "event_type IN ('opened', 'investigating', 'resolved', 'rejected', 'cancelled')",
            name="ck_billing_dispute_event_type",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    dispute_id: Mapped[str] = mapped_column(ForeignKey("billing_disputes.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(500), nullable=False)
    operation_key: Mapped[str] = mapped_column(String(120), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    note: Mapped[str] = mapped_column(String(4000), default="", nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
