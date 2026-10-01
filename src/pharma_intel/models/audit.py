from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_uuid


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_tenant_occurred", "tenant_id", "occurred_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(200), index=True)
    outcome: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
