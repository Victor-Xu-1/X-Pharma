from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
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


class ClinicalTrialProfile(Base, TimestampMixin):
    __tablename__ = "clinical_trial_profiles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "registry", "registry_id"),
        CheckConstraint(
            "result_evaluation IS NULL OR result_evaluation IN "
            "('unfavorable','not_superior','non_inferior','similar','positive','superior','terminated')",
            name="ck_clinical_trial_result_evaluation",
        ),
        CheckConstraint(
            "initiation_type IS NULL OR initiation_type IN ('iit','ist')",
            name="ck_clinical_trial_initiation_type",
        ),
        CheckConstraint(
            "start_date_precision IS NULL OR start_date_precision IN ('day','month','year')",
            name="ck_clinical_trial_start_date_precision",
        ),
        CheckConstraint(
            "completion_date_precision IS NULL OR completion_date_precision IN ('day','month','year')",
            name="ck_clinical_trial_completion_date_precision",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    registry_name: Mapped[str] = mapped_column("registry", String(80), index=True, nullable=False)
    registry_id: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    official_title: Mapped[str] = mapped_column(Text, nullable=False)
    acronym: Mapped[str | None] = mapped_column(String(240), index=True)
    initiation_type: Mapped[str | None] = mapped_column(String(40), index=True)
    therapy_lines: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    overall_status: Mapped[str | None] = mapped_column(String(100), index=True)
    phases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    study_type: Mapped[str | None] = mapped_column(String(80), index=True)
    enrollment: Mapped[int | None]
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_date_precision: Mapped[str | None] = mapped_column(String(16))
    completion_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_date_precision: Mapped[str | None] = mapped_column(String(16))
    interventions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    conditions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    sponsors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    outcomes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    locations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    study_design: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    eligibility: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    arms: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    status_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    has_results: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    result_evaluation: Mapped[str | None] = mapped_column(String(40), index=True)
    results_first_posted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_update_posted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)


class ClinicalTrialEntityRole(Base, TimestampMixin):
    __tablename__ = "clinical_trial_entity_roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "trial_id", "entity_id", "role"),
        CheckConstraint(
            "role IN ('investigational_drug','combination_drug','investigational_target','combination_target')",
            name="ck_clinical_trial_entity_role",
        ),
        Index("ix_clinical_trial_entity_roles_lookup", "tenant_id", "role", "entity_id", "trial_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    trial_id: Mapped[str] = mapped_column(ForeignKey("clinical_trial_profiles.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)


class ClinicalTrialResultDisclosure(Base, TimestampMixin):
    __tablename__ = "clinical_trial_result_disclosures"
    __table_args__ = (
        UniqueConstraint("tenant_id", "trial_id", "disclosure_key", "version"),
        CheckConstraint("version > 0", name="ck_clinical_trial_disclosure_version"),
        CheckConstraint(
            "disclosure_type IN "
            "('journal_article','conference_abstract','conference_presentation','registry_result',"
            "'press_release','poster','other')",
            name="ck_clinical_trial_disclosure_type",
        ),
        CheckConstraint(
            "result_evaluation IS NULL OR result_evaluation IN "
            "('unfavorable','not_superior','non_inferior','similar','positive','superior','terminated')",
            name="ck_clinical_trial_disclosure_evaluation",
        ),
        Index("ix_clinical_trial_disclosures_trial_date", "tenant_id", "trial_id", "disclosed_at"),
        Index("ix_clinical_trial_disclosures_external_id", "tenant_id", "external_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    trial_id: Mapped[str] = mapped_column(ForeignKey("clinical_trial_profiles.id"), index=True, nullable=False)
    disclosure_key: Mapped[str] = mapped_column(String(240), index=True, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    disclosure_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(240))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    disclosed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    conference_name: Mapped[str | None] = mapped_column(String(500), index=True)
    is_key_result: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    result_evaluation: Mapped[str | None] = mapped_column(String(40), index=True)
    source_locator: Mapped[str | None] = mapped_column(String(500))
    source_quote: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)
