from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class DataExportJob(Base):
    __tablename__ = "data_export_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "agent_client_id", "idempotency_key"),
        UniqueConstraint("reservation_id"),
        Index("ix_data_export_jobs_state_created", "tenant_id", "state", "created_at"),
        CheckConstraint("actor_type IN ('agent', 'api_key')", name="ck_export_job_actor_type"),
        CheckConstraint("export_format IN ('jsonl', 'csv')", name="ck_export_job_format"),
        CheckConstraint(
            "state IN ('pending_approval', 'queued', 'running', 'completed', 'failed', 'cancel_requested', "
            "'cancelled', 'expired')",
            name="ck_export_job_state",
        ),
        CheckConstraint("max_records > 0", name="ck_export_job_max_records"),
        CheckConstraint("record_count >= 0", name="ck_export_job_record_count"),
        CheckConstraint("artifact_bytes >= 0", name="ck_export_job_artifact_bytes"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    billing_account_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    agent_client_id: Mapped[str] = mapped_column(ForeignKey("agent_clients.id"), index=True, nullable=False)
    reservation_id: Mapped[str | None] = mapped_column(ForeignKey("usage_reservations.id"), index=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    license_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    license_policy_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    license_attribution: Mapped[str] = mapped_column(String(500), nullable=False)
    export_format: Mapped[str] = mapped_column(String(20), nullable=False)
    filters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    fields_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    max_records: Mapped[int] = mapped_column(nullable=False)
    max_billable_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="pending_approval", index=True, nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(500))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    workflow_id: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    record_count: Mapped[int] = mapped_column(default=0, nullable=False)
    artifact_uri: Mapped[str | None] = mapped_column(Text)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    artifact_bytes: Mapped[int] = mapped_column(default=0, nullable=False)
    manifest_uri: Mapped[str | None] = mapped_column(Text)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    manifest_signature: Mapped[str | None] = mapped_column(String(128))
    manifest_key_id: Mapped[str | None] = mapped_column(String(120))
    failure_code: Mapped[str | None] = mapped_column(String(120))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class DataRetentionPolicy(Base, TimestampMixin):
    __tablename__ = "data_retention_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "data_class"),
        CheckConstraint("retention_seconds >= 300", name="ck_retention_policy_minimum"),
        CheckConstraint(
            "data_class IN ('commercial_export_artifact', 'source_asset_snapshot')",
            name="ck_retention_policy_data_class",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    data_class: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    policy_version: Mapped[int] = mapped_column(default=1, nullable=False)
    retention_seconds: Mapped[int] = mapped_column(nullable=False)
    legal_basis: Mapped[str] = mapped_column(String(500), nullable=False)
    geographic_scope: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    configured_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class LegalHold(Base):
    __tablename__ = "legal_holds"
    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('tenant', 'billing_account', 'data_export_job', 'data_source', 'source_asset')",
            name="ck_legal_hold_scope_type",
        ),
        CheckConstraint("status IN ('active', 'released')", name="ck_legal_hold_status"),
        CheckConstraint(
            "(scope_type = 'tenant' AND scope_id IS NULL) OR (scope_type <> 'tenant' AND scope_id IS NOT NULL)",
            name="ck_legal_hold_scope_id",
        ),
        Index("ix_legal_holds_active_scope", "tenant_id", "status", "scope_type", "scope_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    scope_id: Mapped[str | None] = mapped_column(String(36), index=True)
    matter_reference: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True, nullable=False)
    placed_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    released_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(String(2000))


class DataLifecycleEvent(Base):
    __tablename__ = "data_lifecycle_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        CheckConstraint(
            "action IN ('purge', 'blocked', 'reauthorize')",
            name="ck_data_lifecycle_event_action",
        ),
        CheckConstraint(
            "outcome IN ('succeeded', 'blocked')",
            name="ck_data_lifecycle_event_outcome",
        ),
        Index("ix_data_lifecycle_target", "tenant_id", "target_type", "target_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    data_class: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_id: Mapped[str] = mapped_column(ForeignKey("data_retention_policies.id"), nullable=False)
    policy_version: Mapped[int] = mapped_column(nullable=False)
    legal_hold_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
