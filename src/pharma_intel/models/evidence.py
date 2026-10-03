from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid
from .enums import ReviewStatus


class SourceDocument(Base, TimestampMixin):
    __tablename__ = "source_documents"
    __table_args__ = (UniqueConstraint("tenant_id", "content_sha256"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_uri: Mapped[str | None] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    # Legacy upgrade data only; retained until customers approve the destructive column-removal migration.
    ragflow_dataset_id: Mapped[str | None] = mapped_column(String(64), index=True)
    ragflow_document_id: Mapped[str | None] = mapped_column(String(64), index=True)


class Relationship(Base, TimestampMixin):
    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "subject_id", "predicate", "object_id", "valid_from"),
        Index("ix_relationships_subject_predicate", "tenant_id", "subject_id", "predicate"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subject_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    predicate: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    object_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.DRAFT, nullable=False)


class EvidenceClaim(Base, TimestampMixin):
    __tablename__ = "evidence_claims"
    __table_args__ = (Index("ix_claims_entity_predicate", "tenant_id", "subject_id", "predicate"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subject_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    predicate: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    object_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True, nullable=False)
    page_number: Mapped[int | None]
    source_locator: Mapped[str | None] = mapped_column(String(500))
    quote: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.DRAFT, index=True, nullable=False
    )
