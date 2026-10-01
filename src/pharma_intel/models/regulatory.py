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


class RegulatoryEvent(Base, TimestampMixin):
    __tablename__ = "regulatory_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "agency", "event_identifier"),
        CheckConstraint(
            "event_type IN ('submission', 'acceptance', 'priority_review', 'approval', "
            "'conditional_approval', 'designation', 'label_update', 'safety_signal', "
            "'safety_communication', 'rejection', "
            "'withdrawal', 'suspension', 'other')",
            name="ck_regulatory_event_type",
        ),
        CheckConstraint(
            "designation_type IS NULL OR designation_type IN ('breakthrough_therapy','fast_track',"
            "'priority_review','accelerated_approval','orphan_drug','prime','sakigake',"
            "'conditional_marketing_authorisation','other')",
            name="ck_regulatory_designation_type",
        ),
        CheckConstraint(
            "label_change_type IS NULL OR label_change_type IN ('initial_label','indication_expansion',"
            "'population_expansion','restriction','dosing_update','administration_update','safety_update',"
            "'boxed_warning','contraindication','other')",
            name="ck_regulatory_label_change_type",
        ),
        CheckConstraint(
            "safety_signal_type IS NULL OR safety_signal_type IN ('adverse_event','boxed_warning',"
            "'contraindication','risk_management','recall','clinical_hold','postmarketing_requirement','other')",
            name="ck_regulatory_safety_signal_type",
        ),
        CheckConstraint(
            "safety_severity IS NULL OR safety_severity IN ('informational','moderate','serious','severe',"
            "'life_threatening','fatal','unknown')",
            name="ck_regulatory_safety_severity",
        ),
        CheckConstraint(
            "safety_status IS NULL OR safety_status IN ('detected','under_evaluation','confirmed','monitoring',"
            "'resolved','withdrawn','unknown')",
            name="ck_regulatory_safety_status",
        ),
        CheckConstraint(
            "safety_confirmed_at IS NULL OR safety_identified_at IS NULL OR "
            "safety_confirmed_at >= safety_identified_at",
            name="ck_regulatory_safety_confirmation_window",
        ),
        CheckConstraint(
            "safety_resolved_at IS NULL OR safety_identified_at IS NULL OR safety_resolved_at >= safety_identified_at",
            name="ck_regulatory_safety_resolution_window",
        ),
        Index("ix_regulatory_subject_date", "tenant_id", "subject_entity_id", "decision_date"),
        Index("ix_regulatory_application", "tenant_id", "application_number"),
        Index(
            "ix_regulatory_designation_lookup",
            "tenant_id",
            "designation_type",
            "jurisdiction",
            "subject_entity_id",
        ),
        Index(
            "ix_regulatory_label_lookup",
            "tenant_id",
            "label_change_type",
            "has_boxed_warning",
            "subject_entity_id",
        ),
        Index(
            "ix_regulatory_safety_lookup",
            "tenant_id",
            "safety_status",
            "safety_severity",
            "subject_entity_id",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subject_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    agency: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    event_identifier: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    application_number: Mapped[str | None] = mapped_column(String(120), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    status: Mapped[str | None] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    decision_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    designation_type: Mapped[str | None] = mapped_column(String(80), index=True)
    label_change_type: Mapped[str | None] = mapped_column(String(80), index=True)
    label_version: Mapped[str | None] = mapped_column(String(160), index=True)
    label_effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    approved_population: Mapped[str | None] = mapped_column(Text)
    line_of_therapy: Mapped[str | None] = mapped_column(String(240), index=True)
    biomarker: Mapped[str | None] = mapped_column(String(240), index=True)
    route_of_administration: Mapped[str | None] = mapped_column(String(160), index=True)
    dosage_form: Mapped[str | None] = mapped_column(String(160), index=True)
    has_boxed_warning: Mapped[bool | None] = mapped_column(Boolean, index=True)
    safety_signal_type: Mapped[str | None] = mapped_column(String(80), index=True)
    safety_term: Mapped[str | None] = mapped_column(String(500), index=True)
    safety_severity: Mapped[str | None] = mapped_column(String(40), index=True)
    safety_status: Mapped[str | None] = mapped_column(String(40), index=True)
    safety_identified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    safety_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    safety_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    affected_population: Mapped[str | None] = mapped_column(Text)
    risk_actions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    indication_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    organization_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)
