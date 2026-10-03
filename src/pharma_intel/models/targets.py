from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
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


class TargetProfile(Base, TimestampMixin):
    __tablename__ = "target_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "entity_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    gene_symbol: Mapped[str | None] = mapped_column(String(80), index=True)
    uniprot_accession: Mapped[str | None] = mapped_column(String(20), index=True)
    organism: Mapped[str] = mapped_column(String(120), default="Homo sapiens", nullable=False)
    target_class: Mapped[str | None] = mapped_column(String(160), index=True)
    sequence: Mapped[str | None] = mapped_column(Text)
    function_summary: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)


class TargetEvidenceObservation(Base, TimestampMixin):
    __tablename__ = "target_evidence_observations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_system", "source_record_id"),
        Index("ix_target_evidence_target_type", "tenant_id", "target_entity_id", "evidence_type"),
        Index("ix_target_evidence_disease_type", "tenant_id", "disease_entity_id", "evidence_type"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(240), index=True, nullable=False)
    target_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    disease_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    study_name: Mapped[str | None] = mapped_column(String(500))
    population: Mapped[str | None] = mapped_column(String(500))
    tissue: Mapped[str | None] = mapped_column(String(240), index=True)
    variant: Mapped[str | None] = mapped_column(String(240), index=True)
    effect_size: Mapped[float | None] = mapped_column(Float)
    effect_unit: Mapped[str | None] = mapped_column(String(80))
    p_value: Mapped[float | None] = mapped_column(Float)
    sample_size: Mapped[int | None]
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    qualifiers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)
