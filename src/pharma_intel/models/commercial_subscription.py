from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid
from .enums import SubscriptionStatus


class RateCardVersion(Base):
    __tablename__ = "rate_card_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "rate_card_key", "revision"),
        UniqueConstraint("tenant_id", "content_sha256"),
        CheckConstraint("revision > 0", name="ck_rate_card_revision"),
        CheckConstraint("length(currency) = 3", name="ck_rate_card_currency"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from",
            name="ck_rate_card_effective_window",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    rate_card_key: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    revision: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(500), nullable=False)


class RateCardItem(Base):
    __tablename__ = "rate_card_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "rate_card_version_id", "billing_class"),
        CheckConstraint("base_units >= 0", name="ck_rate_card_item_base_units"),
        CheckConstraint("per_result_units >= 0", name="ck_rate_card_item_result_units"),
        CheckConstraint("per_kib_units >= 0", name="ck_rate_card_item_kib_units"),
        CheckConstraint("per_compute_unit >= 0", name="ck_rate_card_item_compute_units"),
        CheckConstraint("max_result_rows > 0", name="ck_rate_card_item_max_rows"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    rate_card_version_id: Mapped[str] = mapped_column(ForeignKey("rate_card_versions.id"), index=True, nullable=False)
    billing_class: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    entitlement_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    base_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    per_result_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    per_kib_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    per_compute_unit: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"), nullable=False)
    max_result_rows: Mapped[int] = mapped_column(nullable=False)


class CommercialSubscription(Base, TimestampMixin):
    __tablename__ = "commercial_subscriptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "subscription_key"),
        UniqueConstraint("tenant_id", "agent_client_id"),
        CheckConstraint("granted_units >= 0", name="ck_subscription_granted_units"),
        CheckConstraint("consumed_units >= 0", name="ck_subscription_consumed_units"),
        CheckConstraint("reserved_units >= 0", name="ck_subscription_reserved_units"),
        CheckConstraint(
            "consumed_units + reserved_units <= granted_units",
            name="ck_subscription_credit_conservation",
        ),
        CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="ck_subscription_window"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_key: Mapped[str] = mapped_column(String(120), nullable=False)
    billing_account_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.id"), index=True, nullable=False)
    agent_client_id: Mapped[str] = mapped_column(ForeignKey("agent_clients.id"), index=True, nullable=False)
    rate_card_version_id: Mapped[str] = mapped_column(ForeignKey("rate_card_versions.id"), index=True, nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, index=True, nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    granted_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"), nullable=False)
    consumed_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"), nullable=False)
    reserved_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"), nullable=False)
    row_version: Mapped[int] = mapped_column(default=1, nullable=False)


class CommercialEntitlement(Base, TimestampMixin):
    __tablename__ = "commercial_entitlements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "subscription_id", "entitlement_key"),
        CheckConstraint("max_result_rows > 0", name="ck_entitlement_max_rows"),
        CheckConstraint(
            "daily_unit_limit IS NULL OR daily_unit_limit > 0",
            name="ck_entitlement_daily_limit",
        ),
        CheckConstraint("max_page_depth > 0", name="ck_entitlement_max_page_depth"),
        CheckConstraint(
            "daily_unique_record_limit IS NULL OR daily_unique_record_limit > 0",
            name="ck_entitlement_daily_unique_records",
        ),
        CheckConstraint("max_response_bytes > 0", name="ck_entitlement_max_response_bytes"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    entitlement_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    max_result_rows: Mapped[int] = mapped_column(nullable=False)
    daily_unit_limit: Mapped[Decimal | None] = mapped_column(Numeric(28, 8))
    max_page_depth: Mapped[int] = mapped_column(default=10, nullable=False)
    daily_unique_record_limit: Mapped[int | None] = mapped_column(default=5000)
    max_response_bytes: Mapped[int] = mapped_column(default=2_000_000, nullable=False)
    data_domains: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    constraints_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class CreditGrant(Base):
    __tablename__ = "credit_grants"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_reference"),
        CheckConstraint("granted_units > 0", name="ck_credit_grant_units"),
        CheckConstraint("expires_at IS NULL OR expires_at > granted_at", name="ck_credit_grant_window"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    granted_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    external_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
