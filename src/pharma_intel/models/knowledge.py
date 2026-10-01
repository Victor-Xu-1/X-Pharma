from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
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
from .enums import KnowledgePageStatus


class KnowledgePage(Base, TimestampMixin):
    __tablename__ = "knowledge_pages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "page_key"),
        Index("ix_knowledge_pages_tenant_type_title", "tenant_id", "page_type", "title"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    page_key: Mapped[str] = mapped_column(String(240), nullable=False)
    page_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    subject_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    status: Mapped[KnowledgePageStatus] = mapped_column(
        Enum(KnowledgePageStatus), default=KnowledgePageStatus.DRAFT, index=True, nullable=False
    )
    current_version_id: Mapped[str | None] = mapped_column(String(36), index=True)


class KnowledgePageVersion(Base):
    __tablename__ = "knowledge_page_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "knowledge_page_id", "version_number"),
        UniqueConstraint("tenant_id", "knowledge_page_id", "content_sha256"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    knowledge_page_id: Mapped[str] = mapped_column(ForeignKey("knowledge_pages.id"), index=True, nullable=False)
    version_number: Mapped[int] = mapped_column(nullable=False)
    compiler_version: Mapped[str] = mapped_column(String(80), nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rendered_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_run_id: Mapped[str | None] = mapped_column(String(200), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class KnowledgeCitation(Base):
    __tablename__ = "knowledge_citations"
    __table_args__ = (UniqueConstraint("tenant_id", "page_version_id", "ordinal"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    page_version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_page_versions.id"), index=True, nullable=False)
    ordinal: Mapped[int] = mapped_column(nullable=False)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True, nullable=False)
    evidence_claim_id: Mapped[str | None] = mapped_column(ForeignKey("evidence_claims.id"), index=True)
    source_locator: Mapped[str | None] = mapped_column(String(500))
    quote: Mapped[str | None] = mapped_column(Text)


class KnowledgeLink(Base):
    __tablename__ = "knowledge_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "page_version_id", "relationship", "target_key"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_knowledge_link_confidence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    page_version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_page_versions.id"), index=True, nullable=False)
    relationship: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    target_key: Mapped[str] = mapped_column(String(240), index=True, nullable=False)
    target_page_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_pages.id"), index=True)
    target_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
