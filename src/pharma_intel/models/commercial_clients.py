from __future__ import annotations

from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid
from .enums import BillingAccountStatus


class AgentClient(Base, TimestampMixin):
    __tablename__ = "agent_clients"
    __table_args__ = (
        UniqueConstraint("tenant_id", "oauth_client_id"),
        UniqueConstraint("tenant_id", "client_key"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    client_key: Mapped[str] = mapped_column(String(120), nullable=False)
    oauth_client_id: Mapped[str] = mapped_column(String(500), nullable=False)
    display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class AgentClientSubject(Base, TimestampMixin):
    __tablename__ = "agent_client_subjects"
    __table_args__ = (
        UniqueConstraint("tenant_id", "agent_client_id", "actor_type", "subject_id"),
        CheckConstraint("actor_type IN ('agent', 'api_key')", name="ck_agent_client_subject_actor_type"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    agent_client_id: Mapped[str] = mapped_column(ForeignKey("agent_clients.id"), index=True, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)


class BillingAccount(Base, TimestampMixin):
    __tablename__ = "billing_accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_key"),
        CheckConstraint("length(currency) = 3", name="ck_billing_account_currency"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    account_key: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[BillingAccountStatus] = mapped_column(
        Enum(BillingAccountStatus), default=BillingAccountStatus.ACTIVE, index=True, nullable=False
    )
    external_customer_reference: Mapped[str | None] = mapped_column(String(500), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class CommercialRiskPolicy(Base, TimestampMixin):
    __tablename__ = "commercial_risk_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "billing_account_id"),
        UniqueConstraint("billing_account_id"),
        CheckConstraint("account_daily_unique_record_limit > 0", name="ck_risk_account_daily_coverage"),
        CheckConstraint("partition_window_seconds > 0", name="ck_risk_partition_window"),
        CheckConstraint("max_requests_per_window > 0", name="ck_risk_requests_per_window"),
        CheckConstraint("max_partition_queries_per_window > 0", name="ck_risk_partition_queries"),
        CheckConstraint(
            "max_cross_client_partition_queries_per_window > 0",
            name="ck_risk_cross_client_partition_queries",
        ),
        CheckConstraint(
            "max_cross_client_partition_queries_per_window <= max_partition_queries_per_window",
            name="ck_risk_cross_client_within_partition_limit",
        ),
        CheckConstraint("max_distinct_clients_per_window > 0", name="ck_risk_distinct_clients"),
        CheckConstraint("max_distinct_networks_per_window > 0", name="ck_risk_distinct_networks"),
        CheckConstraint("max_distinct_credentials_per_window > 0", name="ck_risk_distinct_credentials"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    billing_account_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.id"), index=True, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), default="risk-v2", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    account_daily_unique_record_limit: Mapped[int] = mapped_column(default=20_000, nullable=False)
    partition_window_seconds: Mapped[int] = mapped_column(default=900, nullable=False)
    max_requests_per_window: Mapped[int] = mapped_column(default=50_000, nullable=False)
    max_partition_queries_per_window: Mapped[int] = mapped_column(default=8, nullable=False)
    max_cross_client_partition_queries_per_window: Mapped[int] = mapped_column(default=4, nullable=False)
    max_distinct_clients_per_window: Mapped[int] = mapped_column(default=20, nullable=False)
    max_distinct_networks_per_window: Mapped[int] = mapped_column(default=8, nullable=False)
    max_distinct_credentials_per_window: Mapped[int] = mapped_column(default=4, nullable=False)


class CommercialExportPolicy(Base, TimestampMixin):
    __tablename__ = "commercial_export_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "billing_account_id"),
        UniqueConstraint("billing_account_id"),
        CheckConstraint("max_records_per_job > 0", name="ck_export_policy_records_per_job"),
        CheckConstraint("daily_record_limit > 0", name="ck_export_policy_daily_records"),
        CheckConstraint("approval_required_above >= 0", name="ck_export_policy_approval_threshold"),
        CheckConstraint(
            "approval_required_above <= max_records_per_job",
            name="ck_export_policy_approval_within_job_limit",
        ),
        CheckConstraint("max_artifact_bytes > 0", name="ck_export_policy_artifact_bytes"),
        CheckConstraint("artifact_ttl_seconds > 0", name="ck_export_policy_artifact_ttl"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    billing_account_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.id"), index=True, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), default="export-v1", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    allowed_datasets: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: [
            "entities",
            "structures",
            "bioactivities",
            "competitive_programs",
            "clinical_trials",
            "patents",
            "deals",
            "regulatory_events",
            "fact_provenance",
        ],
        nullable=False,
    )
    allowed_formats: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["jsonl", "csv"], nullable=False)
    field_policy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    max_records_per_job: Mapped[int] = mapped_column(default=5_000, nullable=False)
    daily_record_limit: Mapped[int] = mapped_column(default=20_000, nullable=False)
    approval_required_above: Mapped[int] = mapped_column(default=1_000, nullable=False)
    max_artifact_bytes: Mapped[int] = mapped_column(default=100_000_000, nullable=False)
    artifact_ttl_seconds: Mapped[int] = mapped_column(default=86_400, nullable=False)
