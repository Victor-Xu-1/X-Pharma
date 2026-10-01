from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TenantDataset(Base, TimestampMixin):
    __tablename__ = "tenant_datasets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dataset_key"),
        UniqueConstraint("tenant_id", "ragflow_dataset_id"),
        CheckConstraint("version > 0", name="ck_tenant_dataset_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    dataset_key: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Legacy upgrade data only. Online runtime code must not read or write this migration mapping.
    ragflow_dataset_id: Mapped[str | None] = mapped_column(String(64), index=True)
    license_policy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    required_scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)


class LLMProviderConfig(Base, TimestampMixin):
    __tablename__ = "llm_provider_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_llm_provider_tenant_name"),
        UniqueConstraint("tenant_id", "priority", name="uq_llm_provider_tenant_priority"),
        CheckConstraint("priority >= 0", name="ck_llm_provider_priority_nonnegative"),
        CheckConstraint("version > 0", name="ck_llm_provider_version_positive"),
        CheckConstraint("request_timeout_seconds BETWEEN 1 AND 600", name="ck_llm_provider_timeout"),
        CheckConstraint("request_attempts BETWEEN 1 AND 8", name="ck_llm_provider_attempts"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    model: Mapped[str] = mapped_column(String(500), nullable=False)
    priority: Mapped[int] = mapped_column(nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    api_key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_fingerprint: Mapped[str] = mapped_column(String(16), nullable=False)
    response_format_mode: Mapped[str] = mapped_column(String(32), default="prompt_only", nullable=False)
    thinking_mode: Mapped[str] = mapped_column(String(32), default="disabled", nullable=False)
    include_schema_in_prompt: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_output_tokens_per_segment: Mapped[int] = mapped_column(default=16_384, nullable=False)
    request_timeout_seconds: Mapped[float] = mapped_column(Float, default=120, nullable=False)
    request_attempts: Mapped[int] = mapped_column(default=2, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[str | None] = mapped_column(String(32))
    last_test_message: Mapped[str | None] = mapped_column(String(500))
