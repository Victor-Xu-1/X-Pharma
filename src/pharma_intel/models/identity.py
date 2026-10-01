from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid
from .enums import EntityType, ResolutionStatus, ReviewStatus


class Entity(Base, TimestampMixin):
    __tablename__ = "entities"
    __table_args__ = (
        Index("ix_entities_tenant_type_normalized_name", "tenant_id", "entity_type", "normalized_name"),
        Index("ix_entities_tenant_type_name", "tenant_id", "entity_type", "name"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    external_ids: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.DRAFT, index=True, nullable=False
    )
    aliases: Mapped[list[EntityAlias]] = relationship(back_populates="entity", cascade="all, delete-orphan")
    identity_identifiers: Mapped[list[EntityIdentifier]] = relationship(
        cascade="all, delete-orphan",
        foreign_keys="EntityIdentifier.entity_id",
        order_by="(EntityIdentifier.namespace, EntityIdentifier.normalized_value)",
    )
    canonical_link: Mapped[EntityCanonicalLink | None] = relationship(
        foreign_keys="EntityCanonicalLink.alias_entity_id", uselist=False
    )

    @property
    def canonical_entity_id(self) -> str:
        if self.canonical_link is not None and self.canonical_link.active:
            return self.canonical_link.canonical_entity_id
        return self.id


class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (UniqueConstraint("tenant_id", "entity_id", "normalized_alias"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    alias: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16))
    entity: Mapped[Entity] = relationship(back_populates="aliases")


class EntityIdentifier(Base, TimestampMixin):
    __tablename__ = "entity_identifiers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_id", "namespace", "normalized_value"),
        Index(
            "ix_entity_identifiers_lookup",
            "tenant_id",
            "entity_type",
            "namespace",
            "normalized_value",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType), index=True, nullable=False)
    namespace: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(500), nullable=False)
    trusted_namespace: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.DRAFT, index=True, nullable=False
    )


class OntologyTerm(Base, TimestampMixin):
    __tablename__ = "ontology_terms"
    __table_args__ = (
        UniqueConstraint("tenant_id", "ontology_name", "ontology_version", "term_id"),
        Index("ix_ontology_terms_lookup", "tenant_id", "ontology_name", "term_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    ontology_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ontology_version: Mapped[str] = mapped_column(String(100), nullable=False)
    term_id: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType), index=True, nullable=False)
    preferred_label: Mapped[str] = mapped_column(String(500), nullable=False)
    definition: Mapped[str | None] = mapped_column(Text)
    synonyms: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    parent_term_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_uri: Mapped[str | None] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)


class EntityOntologyMapping(Base, TimestampMixin):
    __tablename__ = "entity_ontology_mappings"
    __table_args__ = (UniqueConstraint("tenant_id", "entity_id", "ontology_term_id", "mapping_type"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    ontology_term_id: Mapped[str] = mapped_column(ForeignKey("ontology_terms.id"), index=True, nullable=False)
    mapping_type: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.DRAFT, index=True, nullable=False
    )


class EntityResolutionCase(Base, TimestampMixin):
    __tablename__ = "entity_resolution_cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_entity_id", "candidate_entity_id"),
        CheckConstraint("source_entity_id <> candidate_entity_id", name="ck_resolution_distinct_entities"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    candidate_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[ResolutionStatus] = mapped_column(
        Enum(ResolutionStatus), default=ResolutionStatus.PENDING, index=True, nullable=False
    )
    proposed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(String(4000))


class EntityCanonicalLink(Base, TimestampMixin):
    __tablename__ = "entity_canonical_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "alias_entity_id"),
        CheckConstraint("alias_entity_id <> canonical_entity_id", name="ck_canonical_link_distinct_entities"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    alias_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    canonical_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    resolution_case_id: Mapped[str] = mapped_column(
        ForeignKey("entity_resolution_cases.id"), index=True, nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)


class EntityResolutionDecision(Base):
    __tablename__ = "entity_resolution_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    resolution_case_id: Mapped[str] = mapped_column(
        ForeignKey("entity_resolution_cases.id"), index=True, nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    decided_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(4000))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
