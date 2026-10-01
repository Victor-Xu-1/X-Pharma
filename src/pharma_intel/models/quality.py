from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class DataQualitySnapshot(Base):
    __tablename__ = "data_quality_snapshots"
    __table_args__ = (
        CheckConstraint("trigger IN ('scheduled','manual')", name="ck_data_quality_snapshot_trigger"),
        Index("ix_quality_snapshots_tenant_measured", "tenant_id", "measured_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    trigger: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    definitions_version: Mapped[str] = mapped_column(String(40), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class DataQualityIssue(Base, TimestampMixin):
    __tablename__ = "data_quality_issues"
    __table_args__ = (
        UniqueConstraint("tenant_id", "active_key"),
        CheckConstraint(
            "status IN ('open','acknowledged','ready_to_resolve','resolved','waived')",
            name="ck_data_quality_issue_status",
        ),
        CheckConstraint("severity IN ('critical','high','medium','low')", name="ck_data_quality_issue_severity"),
        CheckConstraint("comparison IN ('gte','lte')", name="ck_data_quality_issue_comparison"),
        CheckConstraint("version > 0", name="ck_data_quality_issue_version"),
        Index("ix_quality_issues_tenant_status_due", "tenant_id", "status", "sla_due_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    active_key: Mapped[str | None] = mapped_column(String(160))
    metric_key: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    scope_id: Mapped[str | None] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    comparison: Mapped[str] = mapped_column(String(8), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    sla_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    last_snapshot_id: Mapped[str] = mapped_column(ForeignKey("data_quality_snapshots.id"), index=True, nullable=False)


class DataQualityIssueEvent(Base):
    __tablename__ = "data_quality_issue_events"
    __table_args__ = (Index("ix_quality_issue_events_issue_occurred", "issue_id", "occurred_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    issue_id: Mapped[str] = mapped_column(ForeignKey("data_quality_issues.id"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(24))
    resulting_status: Mapped[str] = mapped_column(String(24), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
