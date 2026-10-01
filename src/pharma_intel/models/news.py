from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class NewsEvent(Base, TimestampMixin):
    __tablename__ = "news_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_identifier"),
        CheckConstraint(
            "event_type IN ('news', 'press_release', 'corporate_announcement', 'publication', "
            "'conference_abstract', 'poster', 'presentation', 'other')",
            name="ck_news_event_type",
        ),
        Index("ix_news_event_published", "tenant_id", "published_at"),
        Index("ix_news_event_publisher", "tenant_id", "publisher_entity_id", "published_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    event_identifier: Mapped[str] = mapped_column(String(240), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    language: Mapped[str | None] = mapped_column(String(32), index=True)
    publisher_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    related_entity_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    venue: Mapped[str | None] = mapped_column(String(240), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)
