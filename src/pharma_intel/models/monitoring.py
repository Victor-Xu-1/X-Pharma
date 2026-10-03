from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid
from .enums import SavedSearchVisibility


class SavedSearch(Base, TimestampMixin):
    __tablename__ = "saved_searches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "owner_user_id", "name"),
        CheckConstraint("query_version > 0", name="ck_saved_search_query_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    query_type: Mapped[str] = mapped_column(String(80), default="entity_search", index=True, nullable=False)
    query_version: Mapped[int] = mapped_column(default=1, nullable=False)
    query_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    visibility: Mapped[SavedSearchVisibility] = mapped_column(
        String(20), default=SavedSearchVisibility.PRIVATE, index=True, nullable=False
    )


class SavedSearchVersion(Base):
    __tablename__ = "saved_search_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "saved_search_id", "version"),
        CheckConstraint("version > 0", name="ck_saved_search_version_positive"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    saved_search_id: Mapped[str] = mapped_column(ForeignKey("saved_searches.id"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    query_type: Mapped[str] = mapped_column(String(80), nullable=False)
    query_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class MonitoringTopic(Base, TimestampMixin):
    __tablename__ = "monitoring_topics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "owner_user_id", "name"),
        CheckConstraint("query_version > 0", name="ck_monitoring_topic_query_version_positive"),
        ForeignKeyConstraint(
            ["tenant_id", "saved_search_id", "query_version"],
            [
                "saved_search_versions.tenant_id",
                "saved_search_versions.saved_search_id",
                "saved_search_versions.version",
            ],
            name="fk_monitoring_topic_saved_search_version",
        ),
        Index("ix_monitoring_topic_saved_search_version", "tenant_id", "saved_search_id", "query_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    saved_search_id: Mapped[str] = mapped_column(ForeignKey("saved_searches.id"), index=True, nullable=False)
    query_version: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)


class MonitoringAlert(Base):
    __tablename__ = "monitoring_alerts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "topic_id", "source_outbox_event_id"),
        Index("ix_monitoring_alerts_inbox", "tenant_id", "recipient_user_id", "occurred_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    topic_id: Mapped[str] = mapped_column(ForeignKey("monitoring_topics.id"), index=True, nullable=False)
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    source_outbox_event_id: Mapped[str] = mapped_column(ForeignKey("outbox_events.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class MonitoringAlertReceipt(Base):
    __tablename__ = "monitoring_alert_receipts"
    __table_args__ = (UniqueConstraint("tenant_id", "alert_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    alert_id: Mapped[str] = mapped_column(ForeignKey("monitoring_alerts.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
