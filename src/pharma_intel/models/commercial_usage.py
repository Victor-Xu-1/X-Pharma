from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid
from .enums import CommercialLedgerEventType, UsageReservationState


class UsageReservation(Base):
    __tablename__ = "usage_reservations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "agent_client_id", "actor_type", "subject_id", "idempotency_key"),
        Index("ix_usage_reservation_expiry", "tenant_id", "state", "lease_expires_at"),
        CheckConstraint("actor_type IN ('agent', 'api_key')", name="ck_usage_reservation_actor_type"),
        CheckConstraint("requested_result_limit > 0", name="ck_usage_reservation_result_limit"),
        CheckConstraint("client_max_units > 0", name="ck_usage_reservation_client_max"),
        CheckConstraint("estimated_units >= 0", name="ck_usage_reservation_estimated"),
        CheckConstraint("requested_compute_units >= 0", name="ck_usage_reservation_compute_units"),
        CheckConstraint("reserved_units > 0", name="ck_usage_reservation_reserved"),
        CheckConstraint("page_offset >= 0", name="ck_usage_reservation_page_offset"),
        CheckConstraint("page_depth > 0", name="ck_usage_reservation_page_depth"),
        CheckConstraint(
            "network_fingerprint IS NULL OR length(network_fingerprint) = 64",
            name="ck_usage_reservation_network_fingerprint",
        ),
        CheckConstraint(
            "credential_fingerprint IS NULL OR length(credential_fingerprint) = 64",
            name="ck_usage_reservation_credential_fingerprint",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    agent_client_id: Mapped[str] = mapped_column(ForeignKey("agent_clients.id"), index=True, nullable=False)
    rate_card_item_id: Mapped[str] = mapped_column(ForeignKey("rate_card_items.id"), index=True, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    network_fingerprint: Mapped[str | None] = mapped_column(String(64))
    credential_fingerprint: Mapped[str | None] = mapped_column(String(64))
    correlation_key_id: Mapped[str] = mapped_column(String(120), nullable=False)
    billing_class: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    query_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    cursor_chain_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    page_offset: Mapped[int] = mapped_column(default=0, nullable=False)
    page_depth: Mapped[int] = mapped_column(default=1, nullable=False)
    requested_result_limit: Mapped[int] = mapped_column(nullable=False)
    requested_compute_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"), nullable=False)
    client_max_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    estimated_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    reserved_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    state: Mapped[UsageReservationState] = mapped_column(
        Enum(UsageReservationState), default=UsageReservationState.RESERVED, index=True, nullable=False
    )
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    execution_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(String(500))


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_key"),
        CheckConstraint("result_count >= 0", name="ck_usage_event_result_count"),
        CheckConstraint("unique_record_count >= 0", name="ck_usage_event_unique_record_count"),
        CheckConstraint("new_unique_record_count >= 0", name="ck_usage_event_new_unique_record_count"),
        CheckConstraint(
            "new_unique_record_count <= unique_record_count",
            name="ck_usage_event_new_unique_within_total",
        ),
        CheckConstraint("response_bytes >= 0", name="ck_usage_event_response_bytes"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    reservation_id: Mapped[str] = mapped_column(ForeignKey("usage_reservations.id"), unique=True, index=True)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    billing_class: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    result_count: Mapped[int] = mapped_column(nullable=False)
    unique_record_count: Mapped[int] = mapped_column(default=0, nullable=False)
    new_unique_record_count: Mapped[int] = mapped_column(default=0, nullable=False)
    response_bytes: Mapped[int] = mapped_column(nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class CommercialCoverageRecord(Base):
    __tablename__ = "commercial_coverage_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "subscription_id",
            "agent_client_id",
            "entitlement_key",
            "period_start",
            "record_type",
            "record_identifier_sha256",
            name="uq_commercial_coverage_exact_record",
        ),
        Index(
            "ix_commercial_coverage_budget",
            "tenant_id",
            "subscription_id",
            "entitlement_key",
            "period_start",
        ),
        CheckConstraint("actor_type IN ('agent', 'api_key')", name="ck_coverage_actor_type"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    agent_client_id: Mapped[str] = mapped_column(ForeignKey("agent_clients.id"), index=True, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    entitlement_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    record_type: Mapped[str] = mapped_column(String(160), nullable=False)
    record_identifier_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    first_usage_event_id: Mapped[str] = mapped_column(ForeignKey("usage_events.id"), index=True, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CommercialPolicyEvent(Base):
    __tablename__ = "commercial_policy_events"
    __table_args__ = (
        Index(
            "ix_commercial_policy_scope",
            "tenant_id",
            "subscription_id",
            "occurred_at",
        ),
        Index(
            "ix_commercial_policy_risk_queue",
            "tenant_id",
            "decision",
            "occurred_at",
            "id",
        ),
        CheckConstraint("actor_type IN ('agent', 'api_key')", name="ck_policy_actor_type"),
        CheckConstraint("phase IN ('reserve', 'settle')", name="ck_policy_phase"),
        CheckConstraint("decision IN ('allow', 'deny')", name="ck_policy_decision"),
        CheckConstraint("requested_records >= 0", name="ck_policy_requested_records"),
        CheckConstraint("existing_unique_records >= 0", name="ck_policy_existing_records"),
        CheckConstraint("projected_unique_records >= 0", name="ck_policy_projected_records"),
        CheckConstraint("page_depth > 0", name="ck_policy_page_depth"),
        CheckConstraint(
            "projected_unique_records >= existing_unique_records",
            name="ck_policy_projected_after_existing",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    agent_client_id: Mapped[str] = mapped_column(ForeignKey("agent_clients.id"), index=True, nullable=False)
    reservation_id: Mapped[str | None] = mapped_column(ForeignKey("usage_reservations.id"), index=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    entitlement_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    phase: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    query_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    cursor_chain_id: Mapped[str] = mapped_column(String(36), nullable=False)
    page_depth: Mapped[int] = mapped_column(nullable=False)
    requested_records: Mapped[int] = mapped_column(nullable=False)
    existing_unique_records: Mapped[int] = mapped_column(nullable=False)
    projected_unique_records: Mapped[int] = mapped_column(nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class CommercialRiskCase(Base, TimestampMixin):
    __tablename__ = "commercial_risk_cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "policy_event_id"),
        CheckConstraint(
            "status IN ('acknowledged', 'resolved', 'dismissed')",
            name="ck_commercial_risk_case_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    policy_event_id: Mapped[str] = mapped_column(ForeignKey("commercial_policy_events.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    notes: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(500), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class UsageSettlement(Base):
    __tablename__ = "usage_settlements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "settlement_key"),
        CheckConstraint("charged_units >= 0", name="ck_usage_settlement_charged"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    settlement_key: Mapped[str] = mapped_column(String(200), nullable=False)
    reservation_id: Mapped[str] = mapped_column(
        ForeignKey("usage_reservations.id"), unique=True, index=True, nullable=False
    )
    usage_event_id: Mapped[str] = mapped_column(ForeignKey("usage_events.id"), unique=True, index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    rate_card_version_id: Mapped[str] = mapped_column(ForeignKey("rate_card_versions.id"), index=True, nullable=False)
    charged_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    price_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class CommercialLedgerEntry(Base):
    __tablename__ = "commercial_ledger_entries"
    __table_args__ = (UniqueConstraint("tenant_id", "event_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    reservation_id: Mapped[str | None] = mapped_column(ForeignKey("usage_reservations.id"), index=True)
    settlement_id: Mapped[str | None] = mapped_column(ForeignKey("usage_settlements.id"), index=True)
    adjustment_id: Mapped[str | None] = mapped_column(ForeignKey("billing_adjustments.id"), index=True)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[CommercialLedgerEventType] = mapped_column(
        Enum(CommercialLedgerEventType), index=True, nullable=False
    )
    granted_delta: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"), nullable=False)
    reserved_delta: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"), nullable=False)
    consumed_delta: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
