from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
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
from .enums import GovernanceStatus, RunState


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source_version_id",
            "schema_name",
            "schema_version",
            "input_sha256",
            "policy_sha256",
            name="uq_extraction_runs_policy_identity",
        ),
        Index("ix_extraction_runs_version_status", "source_version_id", "status"),
        Index("ix_extraction_runs_version_policy_status", "source_version_id", "policy_sha256", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_version_id: Mapped[str] = mapped_column(ForeignKey("source_versions.id"), index=True, nullable=False)
    schema_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[RunState] = mapped_column(Enum(RunState), default=RunState.PENDING, index=True, nullable=False)
    structured_output: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    validation_errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(18, 6))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class StagedFact(Base, TimestampMixin):
    __tablename__ = "staged_facts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "extraction_run_id", "fact_key"),
        Index("ix_staged_facts_tenant_kind_status", "tenant_id", "fact_kind", "status"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_staged_fact_confidence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    extraction_run_id: Mapped[str] = mapped_column(ForeignKey("extraction_runs.id"), index=True, nullable=False)
    fact_kind: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    fact_key: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    normalization_version: Mapped[str | None] = mapped_column(String(100))
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)
    source_locator: Mapped[str | None] = mapped_column(String(500))
    source_quote: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[GovernanceStatus] = mapped_column(
        Enum(GovernanceStatus), default=GovernanceStatus.PROPOSED, index=True, nullable=False
    )
    quality_findings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    conflict_with_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    published_resource_type: Mapped[str | None] = mapped_column(String(80))
    published_resource_id: Mapped[str | None] = mapped_column(String(36), index=True)


class FactProvenanceLink(Base):
    __tablename__ = "fact_provenance_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "resource_type", "resource_id", "staged_fact_id"),
        Index("ix_fact_provenance_resource", "tenant_id", "resource_type", "resource_id"),
        Index("ix_fact_provenance_dataset_created", "tenant_id", "dataset_key", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    resource_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    staged_fact_id: Mapped[str] = mapped_column(ForeignKey("staged_facts.id"), index=True, nullable=False)
    evidence_claim_id: Mapped[str] = mapped_column(ForeignKey("evidence_claims.id"), index=True, nullable=False)
    source_asset_id: Mapped[str] = mapped_column(ForeignKey("source_assets.id"), index=True, nullable=False)
    source_version_id: Mapped[str] = mapped_column(ForeignKey("source_versions.id"), index=True, nullable=False)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True, nullable=False)
    dataset_key: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    source_locator: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class ReviewTask(Base, TimestampMixin):
    __tablename__ = "review_tasks"
    __table_args__ = (Index("ix_review_tasks_tenant_status_priority", "tenant_id", "status", "priority"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    staged_fact_id: Mapped[str] = mapped_column(ForeignKey("staged_facts.id"), unique=True, index=True, nullable=False)
    status: Mapped[GovernanceStatus] = mapped_column(
        Enum(GovernanceStatus), default=GovernanceStatus.REVIEW_PENDING, index=True, nullable=False
    )
    priority: Mapped[int] = mapped_column(default=50, index=True, nullable=False)
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    assigned_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    decision_notes: Mapped[str | None] = mapped_column(Text)
    decided_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GovernancePublicationBatch(Base, TimestampMixin):
    __tablename__ = "governance_publication_batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        CheckConstraint("operation IN ('publish','withdraw')", name="ck_publication_batch_operation"),
        CheckConstraint(
            "status IN ('previewed','committed','failed')",
            name="ck_publication_batch_status",
        ),
        CheckConstraint("expected_count > 0", name="ck_publication_batch_expected_count"),
        CheckConstraint("blocked_count >= 0", name="ck_publication_batch_blocked_count"),
        Index("ix_publication_batches_tenant_status_created", "tenant_id", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    operation: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    preview_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_count: Mapped[int] = mapped_column(nullable=False)
    blocked_count: Mapped[int] = mapped_column(default=0, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(4000))
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    committed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class GovernancePublicationBatchItem(Base):
    __tablename__ = "governance_publication_batch_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "publication_batch_id", "staged_fact_id"),
        Index("ix_publication_batch_items_batch_position", "publication_batch_id", "position"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    publication_batch_id: Mapped[str] = mapped_column(
        ForeignKey("governance_publication_batches.id"), index=True, nullable=False
    )
    staged_fact_id: Mapped[str] = mapped_column(ForeignKey("staged_facts.id"), index=True, nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    expected_status: Mapped[str] = mapped_column(String(40), nullable=False)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    blockers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class FactWithdrawalTombstone(Base):
    __tablename__ = "fact_withdrawal_tombstones"
    __table_args__ = (
        UniqueConstraint("tenant_id", "staged_fact_id"),
        Index("ix_fact_withdrawal_tombstones_batch_created", "publication_batch_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    staged_fact_id: Mapped[str] = mapped_column(ForeignKey("staged_facts.id"), index=True, nullable=False)
    publication_batch_id: Mapped[str] = mapped_column(
        ForeignKey("governance_publication_batches.id"), index=True, nullable=False
    )
    withdrawn_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(4000), nullable=False)
    resource_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
