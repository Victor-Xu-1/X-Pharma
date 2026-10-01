from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid
from .enums import OutboxState, ProjectionDeliveryState


class ProjectionMaintenanceJob(Base, TimestampMixin):
    __tablename__ = "projection_maintenance_jobs"
    __table_args__ = (
        UniqueConstraint("active_key"),
        CheckConstraint(
            "operation IN ('consistency_check','rebuild')",
            name="ck_projection_maintenance_operation",
        ),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed')",
            name="ck_projection_maintenance_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_projection_maintenance_attempts"),
        Index("ix_projection_maintenance_jobs_status_created", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    operation: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    active_key: Mapped[str | None] = mapped_column(String(40))
    build_id: Mapped[str | None] = mapped_column(String(80), index=True)
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(200), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_state_available", "state", "available_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    state: Mapped[OutboxState] = mapped_column(
        Enum(OutboxState), default=OutboxState.PENDING, index=True, nullable=False
    )
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class ProjectionDelivery(Base):
    __tablename__ = "projection_deliveries"
    __table_args__ = (
        UniqueConstraint("consumer_name", "outbox_event_id"),
        Index("ix_projection_delivery_due", "consumer_name", "state", "available_at"),
        CheckConstraint("attempts > 0", name="ck_projection_delivery_attempts"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    consumer_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    outbox_event_id: Mapped[str] = mapped_column(ForeignKey("outbox_events.id"), index=True, nullable=False)
    state: Mapped[ProjectionDeliveryState] = mapped_column(Enum(ProjectionDeliveryState), index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(default=1, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    worker_id: Mapped[str | None] = mapped_column(String(200), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
