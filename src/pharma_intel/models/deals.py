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
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid
from .enums import DealDirection, DealStatus
from .phase_constraints import development_phase_check


class DealProfile(Base, TimestampMixin):
    __tablename__ = "deal_profiles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_id"),
        CheckConstraint(
            "status IN ('announced','active','completed','terminated','withdrawn','superseded','unknown')",
            name="ck_deal_profile_status",
        ),
        CheckConstraint(
            "direction IN ('domestic','inbound','outbound','cross_border','global','undisclosed')",
            name="ck_deal_profile_direction",
        ),
        CheckConstraint(
            "direction NOT IN ('inbound','outbound') OR direction_reference_jurisdiction IS NOT NULL",
            name="ck_deal_direction_reference",
        ),
        CheckConstraint(
            "terminated_at IS NULL OR announced_at IS NULL OR terminated_at >= announced_at",
            name="ck_deal_termination_window",
        ),
        Index("ix_deal_profiles_tenant_status_date", "tenant_id", "status", "announced_at"),
        Index("ix_deal_profiles_tenant_direction", "tenant_id", "direction"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    deal_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default=DealStatus.UNKNOWN.value, index=True, nullable=False)
    direction: Mapped[str] = mapped_column(
        String(40), default=DealDirection.UNDISCLOSED.value, index=True, nullable=False
    )
    direction_reference_jurisdiction: Mapped[str | None] = mapped_column(String(120), index=True)
    announced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    parties: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    asset_entity_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    territory: Mapped[str | None] = mapped_column(String(240))
    upfront_amount: Mapped[float | None] = mapped_column(Numeric(24, 2))
    total_potential_amount: Mapped[float | None] = mapped_column(Numeric(24, 2))
    currency: Mapped[str | None] = mapped_column(String(8))
    terms: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"))


class DealPartyAssociation(Base, TimestampMixin):
    __tablename__ = "deal_party_associations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "deal_id", "party_entity_id", "role"),
        CheckConstraint(
            "role IN "
            "('licensor','licensee','seller','buyer','acquirer','target','partner','investor','investee','other')",
            name="ck_deal_party_role",
        ),
        Index("ix_deal_party_role_lookup", "tenant_id", "role", "party_entity_id", "deal_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deal_profiles.id"), index=True, nullable=False)
    party_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    country_region: Mapped[str | None] = mapped_column(String(120), index=True)
    organization_type: Mapped[str | None] = mapped_column(String(120), index=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)


class DealAssetAssociation(Base, TimestampMixin):
    __tablename__ = "deal_asset_associations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "deal_id", "asset_entity_id"),
        development_phase_check("development_phase_at_transaction", "ck_deal_asset_transaction_phase"),
        Index(
            "ix_deal_asset_phase_lookup",
            "tenant_id",
            "development_phase_at_transaction",
            "asset_entity_id",
            "deal_id",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deal_profiles.id"), index=True, nullable=False)
    asset_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    development_phase_at_transaction: Mapped[str | None] = mapped_column(String(40), index=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)


class DealRight(Base, TimestampMixin):
    __tablename__ = "deal_rights"
    __table_args__ = (
        UniqueConstraint("tenant_id", "deal_id", "holder_entity_id", "right_type", "territory"),
        CheckConstraint(
            "right_type IN ('research','development','manufacturing','commercialization','co_development',"
            "'co_promotion','distribution','option','other')",
            name="ck_deal_right_type",
        ),
        Index("ix_deal_right_lookup", "tenant_id", "right_type", "territory", "deal_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deal_profiles.id"), index=True, nullable=False)
    holder_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    right_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    territory: Mapped[str] = mapped_column(String(240), index=True, nullable=False)
    exclusive: Mapped[bool | None] = mapped_column(Boolean)
    scope_description: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)
