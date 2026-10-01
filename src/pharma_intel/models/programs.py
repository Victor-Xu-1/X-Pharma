from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid
from .enums import DevelopmentPhase, ProgramTargetRole


class DevelopmentProgram(Base, TimestampMixin):
    __tablename__ = "development_programs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "drug_entity_id", "disease_entity_id", "organization_entity_id"),
        Index("ix_program_target_phase", "tenant_id", "target_entity_id", "phase"),
        Index("ix_program_target_combination_lookup", "tenant_id", "target_combination_key"),
        Index("ix_program_regional_phase", "tenant_id", "global_phase", "china_phase"),
        CheckConstraint(
            "global_phase IS NULL OR global_phase IN "
            "('discovery','preclinical','ind','phase_1','phase_1_2','phase_2','phase_2_3','phase_3',"
            "'filed','approved','discontinued')",
            name="ck_program_global_phase",
        ),
        CheckConstraint(
            "china_phase IS NULL OR china_phase IN "
            "('discovery','preclinical','ind','phase_1','phase_1_2','phase_2','phase_2_3','phase_3',"
            "'filed','approved','discontinued')",
            name="ck_program_china_phase",
        ),
        CheckConstraint(
            "program_status IS NULL OR program_status IN ('active', 'inactive', 'unknown')",
            name="ck_program_status",
        ),
        CheckConstraint(
            "global_phase_started_at IS NULL OR global_phase IS NOT NULL",
            name="ck_program_global_phase_date_requires_phase",
        ),
        CheckConstraint(
            "china_phase_started_at IS NULL OR china_phase IS NOT NULL",
            name="ck_program_china_phase_date_requires_phase",
        ),
        CheckConstraint("target_set_version > 0", name="ck_development_program_target_set_version"),
        CheckConstraint("organization_set_version > 0", name="ck_development_program_org_set_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    drug_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    target_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    disease_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    organization_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    modality: Mapped[str | None] = mapped_column(String(120), index=True)
    innovation_type: Mapped[str | None] = mapped_column(String(120), index=True)
    therapeutic_area: Mapped[str | None] = mapped_column(String(120), index=True)
    drug_category: Mapped[str | None] = mapped_column(String(120), index=True)
    mechanism_of_action: Mapped[str | None] = mapped_column(String(240))
    phase: Mapped[DevelopmentPhase] = mapped_column(Enum(DevelopmentPhase), index=True, nullable=False)
    status_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    geography: Mapped[str | None] = mapped_column(String(120), index=True)
    status_detail: Mapped[str | None] = mapped_column(Text)
    program_status: Mapped[str | None] = mapped_column(String(20), index=True)
    organization_set_version: Mapped[int] = mapped_column(default=1, nullable=False)
    status_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    milestones: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    global_phase: Mapped[str | None] = mapped_column(String(40), index=True)
    china_phase: Mapped[str | None] = mapped_column(String(40), index=True)
    global_phase_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    china_phase_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    development_rights_regions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    commercialization_rights_regions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    program_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    target_set_version: Mapped[int] = mapped_column(default=1, nullable=False)
    target_combination_key: Mapped[str | None] = mapped_column(String(760), index=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"))


class DevelopmentProgramTarget(Base, TimestampMixin):
    __tablename__ = "development_program_targets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "program_id", "target_set_version", "target_entity_id"),
        UniqueConstraint("tenant_id", "program_id", "target_set_version", "position"),
        Index(
            "ix_program_targets_current_lookup",
            "tenant_id",
            "program_id",
            "target_set_version",
            "position",
        ),
        Index(
            "ix_program_targets_target_lookup",
            "tenant_id",
            "target_entity_id",
            "program_id",
            "target_set_version",
        ),
        CheckConstraint("target_set_version > 0", name="ck_program_target_set_version"),
        CheckConstraint("position >= 0 AND position < 20", name="ck_program_target_position"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    program_id: Mapped[str] = mapped_column(ForeignKey("development_programs.id"), index=True, nullable=False)
    target_set_version: Mapped[int] = mapped_column(index=True, nullable=False)
    target_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    role: Mapped[ProgramTargetRole] = mapped_column(
        Enum(ProgramTargetRole, values_callable=lambda members: [member.value for member in members]),
        index=True,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)


class DevelopmentProgramOrganization(Base, TimestampMixin):
    """Versioned organization roles for one development program.

    Mirrors `DevelopmentProgramTarget` for set versioning and `DealPartyAssociation`
    for per-association governed attributes, so originator and collaborator are
    distinguishable instead of collapsing into one nullable column.
    """

    __tablename__ = "development_program_organizations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "program_id",
            "organization_set_version",
            "organization_entity_id",
            name="uq_program_org_entity",
        ),
        UniqueConstraint(
            "tenant_id",
            "program_id",
            "organization_set_version",
            "position",
            name="uq_program_org_position",
        ),
        Index(
            "ix_program_orgs_current_lookup",
            "tenant_id",
            "program_id",
            "organization_set_version",
            "position",
        ),
        Index(
            "ix_program_orgs_entity_lookup",
            "tenant_id",
            "organization_entity_id",
            "program_id",
            "organization_set_version",
        ),
        CheckConstraint("organization_set_version > 0", name="ck_program_org_set_version"),
        CheckConstraint("position >= 0 AND position < 20", name="ck_program_org_position"),
        CheckConstraint(
            "role IN ('originator','collaborator','licensee','licensor','manufacturer','other')",
            name="ck_program_org_role",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    program_id: Mapped[str] = mapped_column(ForeignKey("development_programs.id"), index=True, nullable=False)
    organization_set_version: Mapped[int] = mapped_column(index=True, nullable=False)
    organization_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    country_region: Mapped[str | None] = mapped_column(String(120), index=True)
    organization_type: Mapped[str | None] = mapped_column(String(120), index=True)
    position: Mapped[int] = mapped_column(nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)
