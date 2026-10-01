from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid
from .enums import ReviewStatus


class PatientPopulation(Base, TimestampMixin):
    __tablename__ = "patient_populations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "population_key"),
        Index("ix_patient_populations_tenant_name", "tenant_id", "name"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    population_key: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.VERIFIED, index=True, nullable=False
    )
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)


class PatientPopulationEntityLink(Base):
    __tablename__ = "patient_population_entity_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "patient_population_id", "entity_id", "relationship"),
        CheckConstraint(
            "relationship IN ('disease', 'target')",
            name="ck_patient_population_entity_relationship",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    patient_population_id: Mapped[str] = mapped_column(ForeignKey("patient_populations.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    relationship: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)


class EpidemiologyObservation(Base, TimestampMixin):
    __tablename__ = "epidemiology_observations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "observation_identifier"),
        CheckConstraint(
            "measure IN ('prevalence', 'incidence', 'mortality', 'patient_count', "
            "'diagnosed_count', 'treated_count', 'survival_rate', 'daly', 'other')",
            name="ck_epidemiology_measure",
        ),
        CheckConstraint("value >= 0", name="ck_epidemiology_value_nonnegative"),
        CheckConstraint(
            "lower_bound IS NULL OR lower_bound >= 0",
            name="ck_epidemiology_lower_bound_nonnegative",
        ),
        CheckConstraint(
            "upper_bound IS NULL OR upper_bound >= value",
            name="ck_epidemiology_upper_bound_order",
        ),
        CheckConstraint(
            "lower_bound IS NULL OR lower_bound <= value",
            name="ck_epidemiology_lower_bound_order",
        ),
        CheckConstraint(
            "period_end IS NULL OR period_start IS NULL OR period_end >= period_start",
            name="ck_epidemiology_period_order",
        ),
        CheckConstraint(
            "sample_size IS NULL OR sample_size > 0",
            name="ck_epidemiology_sample_size_positive",
        ),
        Index("ix_epidemiology_disease_period", "tenant_id", "disease_entity_id", "period_end"),
        Index("ix_epidemiology_geography_measure", "tenant_id", "geography", "measure"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    observation_identifier: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    disease_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    patient_population_id: Mapped[str | None] = mapped_column(ForeignKey("patient_populations.id"), index=True)
    measure: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    lower_bound: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    upper_bound: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    unit: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    geography: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    population_scope: Mapped[str] = mapped_column(String(500), nullable=False)
    age_group: Mapped[str | None] = mapped_column(String(120), index=True)
    sex: Mapped[str | None] = mapped_column(String(80), index=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    sample_size: Mapped[Decimal | None] = mapped_column(Numeric(24, 0))
    methodology: Mapped[str | None] = mapped_column(Text)
    publisher_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)
