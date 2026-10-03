from __future__ import annotations

from typing import Any

from sqlalchemy import (
    JSON,
    Enum,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid
from .enums import MeasurementRelation


class CompoundStructure(Base, TimestampMixin):
    __tablename__ = "compound_structures"
    __table_args__ = (
        UniqueConstraint("tenant_id", "standard_inchi_key"),
        Index("ix_compound_structure_entity", "tenant_id", "entity_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    canonical_smiles: Mapped[str] = mapped_column(Text, nullable=False)
    isomeric_smiles: Mapped[str | None] = mapped_column(Text)
    standard_inchi: Mapped[str | None] = mapped_column(Text)
    standard_inchi_key: Mapped[str] = mapped_column(String(27), index=True, nullable=False)
    molecular_formula: Mapped[str | None] = mapped_column(String(120))
    molecular_weight: Mapped[float | None] = mapped_column(Float)
    exact_mass: Mapped[float | None] = mapped_column(Float)
    structure_version: Mapped[str] = mapped_column(String(40), default="source", nullable=False)
    standardization_version: Mapped[str] = mapped_column(
        String(100),
        default="legacy-source/v1",
        server_default="legacy-source/v1",
        nullable=False,
    )
    fingerprint_version: Mapped[str] = mapped_column(
        String(100),
        default="morganbv-radius2-2048/rdkit-2026.03.3",
        server_default="morganbv-radius2-2048/rdkit-2026.03.3",
        nullable=False,
    )


class Assay(Base, TimestampMixin):
    __tablename__ = "assays"
    __table_args__ = (UniqueConstraint("tenant_id", "source_system", "source_assay_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    source_assay_id: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    target_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    assay_type: Mapped[str | None] = mapped_column(String(80), index=True)
    assay_format: Mapped[str | None] = mapped_column(String(120), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    organism: Mapped[str | None] = mapped_column(String(160))
    cell_line: Mapped[str | None] = mapped_column(String(160))
    confidence_score: Mapped[int | None]
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"))


class ActivityMeasurement(Base, TimestampMixin):
    __tablename__ = "activity_measurements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_system", "source_activity_id"),
        Index(
            "ix_activity_target_type_value",
            "tenant_id",
            "target_entity_id",
            "standard_type",
            "standard_value",
        ),
        Index("ix_activity_compound", "tenant_id", "compound_entity_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    source_activity_id: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    assay_id: Mapped[str] = mapped_column(ForeignKey("assays.id"), index=True, nullable=False)
    compound_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    target_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    reported_type: Mapped[str] = mapped_column(String(80), nullable=False)
    reported_relation: Mapped[MeasurementRelation] = mapped_column(Enum(MeasurementRelation), nullable=False)
    reported_value: Mapped[str] = mapped_column(String(120), nullable=False)
    reported_units: Mapped[str | None] = mapped_column(String(40))
    standard_type: Mapped[str | None] = mapped_column(String(80), index=True)
    standard_relation: Mapped[MeasurementRelation | None] = mapped_column(Enum(MeasurementRelation))
    standard_value: Mapped[float | None] = mapped_column(Numeric(24, 8))
    standard_units: Mapped[str | None] = mapped_column(String(40))
    pchembl_value: Mapped[float | None] = mapped_column(Float, index=True)
    qualifiers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    validity_comment: Mapped[str | None] = mapped_column(String(500))
