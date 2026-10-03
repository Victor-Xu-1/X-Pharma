from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class WorkspaceTablePreference(Base, TimestampMixin):
    __tablename__ = "workspace_table_preferences"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["organization_memberships.tenant_id", "organization_memberships.user_id"],
            name="fk_workspace_table_preferences_tenant_user",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "preference_key",
            name="uq_workspace_table_preferences_owner_key",
        ),
        CheckConstraint("schema_version = 1", name="ck_workspace_table_preferences_schema_version"),
        CheckConstraint("version > 0", name="ck_workspace_table_preferences_version"),
        CheckConstraint(
            "density IN ('comfortable', 'compact')",
            name="ck_workspace_table_preferences_density",
        ),
        CheckConstraint(
            "preference_key IN ('clinical-trials','deals','entity-search','epidemiology','news-events',"
            "'patent-families','pipeline','regulatory-events')",
            name="ck_workspace_table_preferences_key",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    preference_key: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_version: Mapped[int] = mapped_column(default=1, nullable=False)
    column_visibility: Mapped[dict[str, bool]] = mapped_column(JSON, default=dict, nullable=False)
    column_order: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    density: Mapped[str] = mapped_column(String(20), default="comfortable", nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)


class WorkspaceExportPolicy(Base, TimestampMixin):
    __tablename__ = "workspace_export_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id"),
        CheckConstraint("max_records_per_export > 0", name="ck_workspace_export_policy_records_positive"),
        CheckConstraint("max_records_per_export <= 100", name="ck_workspace_export_policy_records_bounded"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    allowed_formats: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allowed_fields: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    max_records_per_export: Mapped[int] = mapped_column(default=20, nullable=False)
    attribution: Mapped[str] = mapped_column(String(500), nullable=False)
    configured_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)


class WorkspaceExportEvent(Base):
    __tablename__ = "workspace_export_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "requested_by_user_id", "idempotency_key"),
        CheckConstraint("export_kind IN ('comparison', 'domain')", name="ck_workspace_export_event_kind"),
        CheckConstraint(
            "(export_kind = 'comparison' AND comparison_set_id IS NOT NULL "
            "AND comparison_set_version > 0 AND dataset IS NULL) OR "
            "(export_kind = 'domain' AND comparison_set_id IS NULL "
            "AND comparison_set_version IS NULL AND dataset IS NOT NULL)",
            name="ck_workspace_export_event_subject",
        ),
        CheckConstraint("record_count > 0", name="ck_workspace_export_event_records_positive"),
        CheckConstraint("content_bytes > 0", name="ck_workspace_export_event_bytes_positive"),
        CheckConstraint("export_format IN ('csv', 'json', 'xlsx')", name="ck_workspace_export_event_format"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    export_kind: Mapped[str] = mapped_column(String(20), default="comparison", index=True, nullable=False)
    comparison_set_id: Mapped[str | None] = mapped_column(ForeignKey("comparison_sets.id"), index=True)
    comparison_set_version: Mapped[int | None] = mapped_column()
    dataset: Mapped[str | None] = mapped_column(String(80), index=True)
    query_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    export_format: Mapped[str] = mapped_column(String(20), nullable=False)
    fields_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    records_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    record_count: Mapped[int] = mapped_column(nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    attribution: Mapped[str] = mapped_column(String(500), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_bytes: Mapped[int] = mapped_column(nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
