from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class PatentFamily(Base, TimestampMixin):
    __tablename__ = "patent_families"
    __table_args__ = (UniqueConstraint("tenant_id", "family_identifier"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    family_identifier: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    priority_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    applicants: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    inventors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    publications: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    legal_status: Mapped[str | None] = mapped_column(String(120), index=True)
    legal_status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    legal_events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    independent_claims: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    expiration_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    linked_entity_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"))
