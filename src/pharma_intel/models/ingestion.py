from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid
from .enums import (
    AssetStatus,
    DataSourceState,
    DataSourceType,
    QuarantineStatus,
    RunState,
    SourceAssetState,
    SourceVersionState,
    StageStatus,
)


class IngestionAsset(Base, TimestampMixin):
    __tablename__ = "ingestion_assets"
    __table_args__ = (UniqueConstraint("tenant_id", "source_path"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(default=0, nullable=False)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    dataset_key: Mapped[str | None] = mapped_column(String(80), index=True)
    status: Mapped[AssetStatus] = mapped_column(
        Enum(AssetStatus), default=AssetStatus.DISCOVERED, index=True, nullable=False
    )
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"))


class DataSource(Base, TimestampMixin):
    __tablename__ = "data_sources"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name"),
        UniqueConstraint("tenant_id", "root_uri", "scope_digest", name="uq_data_source_scope"),
        CheckConstraint("stable_seconds >= 0", name="ck_data_source_stable_seconds"),
        CheckConstraint("max_file_bytes > 0", name="ck_data_source_max_file_bytes"),
        CheckConstraint("scan_interval_seconds >= 10", name="ck_data_source_scan_interval"),
        CheckConstraint("expected_freshness_seconds >= 60", name="ck_data_source_expected_freshness"),
        CheckConstraint("rate_limit_per_minute > 0", name="ck_data_source_rate_limit"),
        CheckConstraint(
            "authorization_valid_until IS NULL OR authorization_valid_until > authorization_valid_from",
            name="ck_data_source_authorization_window",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[DataSourceType] = mapped_column(Enum(DataSourceType), index=True, nullable=False)
    root_uri: Mapped[str] = mapped_column(Text, nullable=False)
    scope_digest: Mapped[str] = mapped_column(String(64), default="root", server_default="root", nullable=False)
    credential_ref: Mapped[str | None] = mapped_column(String(500))
    owner: Mapped[str] = mapped_column(String(200), default="migration-unassigned", nullable=False)
    data_classification: Mapped[str] = mapped_column(String(32), default="internal", nullable=False)
    authorization_scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    authorization_valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    authorization_valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dataset_key: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    include_globs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    exclude_globs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    routing_rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    stable_seconds: Mapped[int] = mapped_column(default=30, nullable=False)
    max_file_bytes: Mapped[int] = mapped_column(default=1_073_741_824, nullable=False)
    scan_interval_seconds: Mapped[int] = mapped_column(default=300, nullable=False)
    expected_freshness_seconds: Mapped[int] = mapped_column(default=86_400, nullable=False)
    rate_limit_per_minute: Mapped[int] = mapped_column(default=60, nullable=False)
    state: Mapped[DataSourceState] = mapped_column(
        Enum(DataSourceState), default=DataSourceState.ACTIVE, index=True, nullable=False
    )
    config_version: Mapped[int] = mapped_column(default=1, nullable=False)
    connector_cursor: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_cursor_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unavailable_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)

    @property
    def credential_configured(self) -> bool:
        return bool(self.credential_ref)


class SourceAsset(Base, TimestampMixin):
    __tablename__ = "source_assets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "data_source_id", "logical_path"),
        Index("ix_source_assets_source_seen", "tenant_id", "data_source_id", "last_seen_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    data_source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"), index=True, nullable=False)
    logical_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    extension: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(200))
    processing_mode: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    source_fingerprint: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[SourceAssetState] = mapped_column(
        Enum(SourceAssetState), default=SourceAssetState.ACTIVE, index=True, nullable=False
    )
    current_version_id: Mapped[str | None] = mapped_column(String(36), index=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
    missing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceVersion(Base):
    __tablename__ = "source_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_asset_id", "version_number"),
        Index("ix_source_versions_tenant_state", "tenant_id", "state", "discovered_at"),
        CheckConstraint("version_number > 0", name="ck_source_version_number"),
        CheckConstraint("size_bytes >= 0", name="ck_source_version_size"),
        CheckConstraint("quarantine_version >= 0", name="ck_source_version_quarantine_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_asset_id: Mapped[str] = mapped_column(ForeignKey("source_assets.id"), index=True, nullable=False)
    version_number: Mapped[int] = mapped_column(nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    source_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
    state: Mapped[SourceVersionState] = mapped_column(
        Enum(SourceVersionState), default=SourceVersionState.DISCOVERED, index=True, nullable=False
    )
    snapshot_status: Mapped[StageStatus] = mapped_column(
        Enum(StageStatus), default=StageStatus.NOT_STARTED, index=True, nullable=False
    )
    malware_scan_status: Mapped[StageStatus] = mapped_column(
        Enum(StageStatus), default=StageStatus.NOT_STARTED, index=True, nullable=False
    )
    parse_status: Mapped[StageStatus] = mapped_column(
        Enum(StageStatus), default=StageStatus.NOT_STARTED, index=True, nullable=False
    )
    retrieval_status: Mapped[StageStatus] = mapped_column(
        Enum(StageStatus), default=StageStatus.NOT_STARTED, index=True, nullable=False
    )
    governance_status: Mapped[StageStatus] = mapped_column(
        Enum(StageStatus), default=StageStatus.NOT_STARTED, index=True, nullable=False
    )
    raw_object_uri: Mapped[str | None] = mapped_column(Text)
    malware_scanner: Mapped[str | None] = mapped_column(String(120))
    malware_signature_version: Mapped[str | None] = mapped_column(String(240))
    malware_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extracted_text_object_uri: Mapped[str | None] = mapped_column(Text)
    extracted_text_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    parser_name: Mapped[str | None] = mapped_column(String(120))
    parser_version: Mapped[str | None] = mapped_column(String(80))
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)
    retrieval_projection_id: Mapped[str | None] = mapped_column(ForeignKey("retrieval_projections.id"), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    quarantine_status: Mapped[QuarantineStatus] = mapped_column(
        Enum(QuarantineStatus),
        default=QuarantineStatus.NOT_APPLICABLE,
        index=True,
        nullable=False,
    )
    quarantine_version: Mapped[int] = mapped_column(default=0, nullable=False)
    quarantine_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("ix_ingestion_runs_source_started", "data_source_id", "started_at"),
        Index("ix_ingestion_runs_temporal_execution", "temporal_workflow_id", "temporal_run_id", unique=True),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    data_source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"), index=True, nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    temporal_workflow_id: Mapped[str | None] = mapped_column(String(200), index=True)
    temporal_run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    state: Mapped[RunState] = mapped_column(Enum(RunState), default=RunState.PENDING, index=True, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    counters: Mapped[dict[str, int]] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(500))
    cancel_requested_by_actor_type: Mapped[str | None] = mapped_column(String(40))
    cancel_requested_by_actor_id: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class IngestionRunOperation(Base, TimestampMixin):
    __tablename__ = "ingestion_run_operations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "operation_key", name="uq_ingestion_run_operation_key"),
        Index("ix_ingestion_run_operations_run_created", "ingestion_run_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    ingestion_run_id: Mapped[str] = mapped_column(ForeignKey("ingestion_runs.id"), index=True, nullable=False)
    operation_key: Mapped[str] = mapped_column(String(128), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    expected_state: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    requested_by_actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_by_actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(40), default="pending", index=True, nullable=False)
    response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)


class SourceVersionOperation(Base, TimestampMixin):
    __tablename__ = "source_version_operations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "operation_key", name="uq_source_version_operation_key"),
        Index("ix_source_version_operations_version_created", "source_version_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_version_id: Mapped[str] = mapped_column(ForeignKey("source_versions.id"), index=True, nullable=False)
    operation_key: Mapped[str] = mapped_column(String(128), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    from_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    expected_state: Mapped[str] = mapped_column(String(40), nullable=False)
    expected_error_code: Mapped[str | None] = mapped_column(String(120))
    expected_quarantine_version: Mapped[int | None]
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    requested_by_actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_by_actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(40), default="pending", index=True, nullable=False)
    response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)


class SourceVersionQuarantineDecision(Base):
    __tablename__ = "source_version_quarantine_decisions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "operation_key", name="uq_source_version_quarantine_decision_key"),
        UniqueConstraint(
            "tenant_id",
            "source_version_id",
            "resulting_version",
            name="uq_source_version_quarantine_decision_version",
        ),
        Index(
            "ix_source_version_quarantine_decisions_version_created",
            "source_version_id",
            "created_at",
        ),
        CheckConstraint("expected_version >= 0", name="ck_quarantine_decision_expected_version"),
        CheckConstraint(
            "resulting_version = expected_version + 1",
            name="ck_quarantine_decision_resulting_version",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_version_id: Mapped[str] = mapped_column(ForeignKey("source_versions.id"), index=True, nullable=False)
    operation_key: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    expected_version: Mapped[int] = mapped_column(nullable=False)
    resulting_version: Mapped[int] = mapped_column(nullable=False)
    previous_status: Mapped[QuarantineStatus] = mapped_column(Enum(QuarantineStatus), nullable=False)
    resulting_status: Mapped[QuarantineStatus] = mapped_column(Enum(QuarantineStatus), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    workflow_id: Mapped[str | None] = mapped_column(String(200))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class RetrievalProjection(Base, TimestampMixin):
    __tablename__ = "retrieval_projections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_document_id", "tenant_dataset_id", "engine"),
        Index("ix_retrieval_projection_status", "tenant_id", "engine", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True, nullable=False)
    tenant_dataset_id: Mapped[str] = mapped_column(ForeignKey("tenant_datasets.id"), index=True, nullable=False)
    engine: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    external_dataset_id: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    external_document_id: Mapped[str | None] = mapped_column(String(160), index=True)
    status: Mapped[StageStatus] = mapped_column(
        Enum(StageStatus), default=StageStatus.NOT_STARTED, index=True, nullable=False
    )
    progress: Mapped[float | None] = mapped_column(Float)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class IngestionFinding(Base):
    __tablename__ = "ingestion_findings"
    __table_args__ = (Index("ix_ingestion_findings_run_stage", "ingestion_run_id", "stage"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    ingestion_run_id: Mapped[str] = mapped_column(ForeignKey("ingestion_runs.id"), index=True, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
