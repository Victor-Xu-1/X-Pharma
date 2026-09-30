from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class EntityType(str, enum.Enum):
    DRUG = "drug"
    TARGET = "target"
    DISEASE = "disease"
    ORGANIZATION = "organization"
    CLINICAL_TRIAL = "clinical_trial"
    PATENT = "patent"
    TRANSACTION = "transaction"
    PRODUCT = "product"
    TECHNOLOGY = "technology"
    PERSON = "person"


class ReviewStatus(str, enum.Enum):
    DRAFT = "draft"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ResolutionStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVERTED = "reverted"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class AssetStatus(str, enum.Enum):
    DISCOVERED = "discovered"
    REGISTERED = "registered"
    UPLOADED = "uploaded"
    PARSING = "parsing"
    READY = "ready"
    FAILED = "failed"
    SOURCE_UNAVAILABLE = "source_unavailable"
    EXCLUDED = "excluded"


class DevelopmentPhase(str, enum.Enum):
    DISCOVERY = "discovery"
    PRECLINICAL = "preclinical"
    IND = "ind"
    PHASE_1 = "phase_1"
    PHASE_1_2 = "phase_1_2"
    PHASE_2 = "phase_2"
    PHASE_2_3 = "phase_2_3"
    PHASE_3 = "phase_3"
    FILED = "filed"
    APPROVED = "approved"
    DISCONTINUED = "discontinued"


class ProgramOrganizationRole(str, enum.Enum):
    ORIGINATOR = "originator"
    COLLABORATOR = "collaborator"
    LICENSEE = "licensee"
    LICENSOR = "licensor"
    MANUFACTURER = "manufacturer"
    OTHER = "other"


class ProgramTargetRole(str, enum.Enum):
    PRIMARY = "primary"
    COMBINATION = "combination"


class TrialResultEvaluation(str, enum.Enum):
    UNFAVORABLE = "unfavorable"
    NOT_SUPERIOR = "not_superior"
    NON_INFERIOR = "non_inferior"
    SIMILAR = "similar"
    POSITIVE = "positive"
    SUPERIOR = "superior"
    TERMINATED = "terminated"


class TrialEntityRole(str, enum.Enum):
    INVESTIGATIONAL_DRUG = "investigational_drug"
    COMBINATION_DRUG = "combination_drug"
    INVESTIGATIONAL_TARGET = "investigational_target"
    COMBINATION_TARGET = "combination_target"


class TrialResultDisclosureType(str, enum.Enum):
    JOURNAL_ARTICLE = "journal_article"
    CONFERENCE_ABSTRACT = "conference_abstract"
    CONFERENCE_PRESENTATION = "conference_presentation"
    REGISTRY_RESULT = "registry_result"
    PRESS_RELEASE = "press_release"
    POSTER = "poster"
    OTHER = "other"


class DealStatus(str, enum.Enum):
    ANNOUNCED = "announced"
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    WITHDRAWN = "withdrawn"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"


class DealDirection(str, enum.Enum):
    DOMESTIC = "domestic"
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    CROSS_BORDER = "cross_border"
    GLOBAL = "global"
    UNDISCLOSED = "undisclosed"


class DealPartyRole(str, enum.Enum):
    LICENSOR = "licensor"
    LICENSEE = "licensee"
    SELLER = "seller"
    BUYER = "buyer"
    ACQUIRER = "acquirer"
    TARGET = "target"
    PARTNER = "partner"
    INVESTOR = "investor"
    INVESTEE = "investee"
    OTHER = "other"


class DealRightType(str, enum.Enum):
    RESEARCH = "research"
    DEVELOPMENT = "development"
    MANUFACTURING = "manufacturing"
    COMMERCIALIZATION = "commercialization"
    CO_DEVELOPMENT = "co_development"
    CO_PROMOTION = "co_promotion"
    DISTRIBUTION = "distribution"
    OPTION = "option"
    OTHER = "other"


class RegulatoryDesignationType(str, enum.Enum):
    BREAKTHROUGH_THERAPY = "breakthrough_therapy"
    FAST_TRACK = "fast_track"
    PRIORITY_REVIEW = "priority_review"
    ACCELERATED_APPROVAL = "accelerated_approval"
    ORPHAN_DRUG = "orphan_drug"
    PRIME = "prime"
    SAKIGAKE = "sakigake"
    CONDITIONAL_MARKETING_AUTHORISATION = "conditional_marketing_authorisation"
    OTHER = "other"


class RegulatoryLabelChangeType(str, enum.Enum):
    INITIAL_LABEL = "initial_label"
    INDICATION_EXPANSION = "indication_expansion"
    POPULATION_EXPANSION = "population_expansion"
    RESTRICTION = "restriction"
    DOSING_UPDATE = "dosing_update"
    ADMINISTRATION_UPDATE = "administration_update"
    SAFETY_UPDATE = "safety_update"
    BOXED_WARNING = "boxed_warning"
    CONTRAINDICATION = "contraindication"
    OTHER = "other"


class RegulatorySafetySignalType(str, enum.Enum):
    ADVERSE_EVENT = "adverse_event"
    BOXED_WARNING = "boxed_warning"
    CONTRAINDICATION = "contraindication"
    RISK_MANAGEMENT = "risk_management"
    RECALL = "recall"
    CLINICAL_HOLD = "clinical_hold"
    POSTMARKETING_REQUIREMENT = "postmarketing_requirement"
    OTHER = "other"


class RegulatorySafetySeverity(str, enum.Enum):
    INFORMATIONAL = "informational"
    MODERATE = "moderate"
    SERIOUS = "serious"
    SEVERE = "severe"
    LIFE_THREATENING = "life_threatening"
    FATAL = "fatal"
    UNKNOWN = "unknown"


class RegulatorySafetyStatus(str, enum.Enum):
    DETECTED = "detected"
    UNDER_EVALUATION = "under_evaluation"
    CONFIRMED = "confirmed"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    WITHDRAWN = "withdrawn"
    UNKNOWN = "unknown"


class MeasurementRelation(str, enum.Enum):
    EQUAL = "="
    LESS_THAN = "<"
    LESS_OR_EQUAL = "<="
    GREATER_THAN = ">"
    GREATER_OR_EQUAL = ">="
    APPROXIMATE = "~"


class DataSourceType(str, enum.Enum):
    FOLDER = "folder"
    HTTP_MANIFEST = "http_manifest"
    CLINICALTRIALS_GOV = "clinicaltrials_gov"
    PUBMED = "pubmed"
    CHEMBL = "chembl"
    S3_SNAPSHOT = "s3_snapshot"
    SFTP_SNAPSHOT = "sftp_snapshot"
    SMB_SNAPSHOT = "smb_snapshot"


class DataSourceState(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class SourceAssetState(str, enum.Enum):
    ACTIVE = "active"
    MISSING = "missing"
    SOURCE_UNAVAILABLE = "source_unavailable"
    DELETED = "deleted"


class SourceVersionState(str, enum.Enum):
    DISCOVERED = "discovered"
    SNAPSHOTTED = "snapshotted"
    PARSED = "parsed"
    INDEXED = "indexed"
    GOVERNANCE_PENDING = "governance_pending"
    REVIEW_PENDING = "review_pending"
    PUBLISHED = "published"
    ASSET_ONLY = "asset_only"
    FAILED = "failed"


class QuarantineStatus(str, enum.Enum):
    NOT_APPLICABLE = "not_applicable"
    PENDING_REVIEW = "pending_review"
    HELD = "held"
    RESCAN_REQUESTED = "rescan_requested"
    REJECTED = "rejected"
    CLEARED = "cleared"


class RunState(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    PARTIAL = "partial"


class StageStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class GovernanceStatus(str, enum.Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    CONFLICT = "conflict"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    WITHDRAWN = "withdrawn"


class KnowledgePageStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class OutboxState(str, enum.Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


class ProjectionDeliveryState(str, enum.Enum):
    PROCESSING = "processing"
    RETRY = "retry"
    SUCCEEDED = "succeeded"
    DEAD = "dead"


class SavedSearchVisibility(str, enum.Enum):
    PRIVATE = "private"
    TENANT = "tenant"


class BillingAccountStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELED = "canceled"
    EXPIRED = "expired"


class UsageReservationState(str, enum.Enum):
    RESERVED = "reserved"
    SETTLED = "settled"
    RELEASED = "released"
    EXPIRED = "expired"


class CommercialLedgerEventType(str, enum.Enum):
    CREDIT_GRANTED = "credit_granted"
    USAGE_RESERVED = "usage_reserved"
    USAGE_SETTLED = "usage_settled"
    RESERVATION_RELEASED = "reservation_released"
    RESERVATION_EXPIRED = "reservation_expired"
    ADJUSTMENT = "adjustment"
    REVERSAL = "reversal"


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


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


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    prefix: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


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


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_tenant_occurred", "tenant_id", "occurred_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(200), index=True)
    outcome: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("oidc_issuer", "oidc_subject", name="uq_users_oidc_identity"),
        UniqueConstraint("tenant_id", "id", name="uq_users_tenant_id_id"),
        CheckConstraint(
            "(oidc_issuer IS NULL) = (oidc_subject IS NULL)",
            name="ck_users_oidc_identity_complete",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.VIEWER, index=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    token_version: Mapped[int] = mapped_column(default=1, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    oidc_issuer: Mapped[str | None] = mapped_column(String(500), index=True)
    oidc_subject: Mapped[str | None] = mapped_column(String(500), index=True)


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        CheckConstraint("expires_at > issued_at", name="ck_user_session_expiry"),
        Index("ix_user_sessions_tenant_user_expiry", "tenant_id", "user_id", "expires_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    user_agent_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revoked_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(500))


class AccountInvitation(Base, TimestampMixin):
    """Tenant-scoped invitations; signed codes establish the pre-auth tenant context."""

    __tablename__ = "account_invitations"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]),
        ForeignKeyConstraint(["tenant_id", "claimed_user_id"], ["users.tenant_id", "users.id"]),
        CheckConstraint("expires_at > created_at", name="ck_account_invitation_expiry"),
        CheckConstraint(
            "(claimed_at IS NULL) = (claimed_user_id IS NULL)", name="ck_account_invitation_claim_complete"
        ),
        Index("ix_account_invitation_tenant_created", "tenant_id", "created_at"),
        Index(
            "uq_account_invitation_pending",
            "tenant_id",
            "normalized_email",
            unique=True,
            postgresql_where=text("claimed_at IS NULL AND revoked_at IS NULL"),
            sqlite_where=text("claimed_at IS NULL AND revoked_at IS NULL"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    created_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_user_id: Mapped[str | None] = mapped_column(String(36))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountRegistrationBudget(Base):
    __tablename__ = "account_registration_budgets"
    __table_args__ = (CheckConstraint("attempts > 0", name="ck_account_registration_attempts"),)
    peer_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(nullable=False)


class WorkspaceTablePreference(Base, TimestampMixin):
    __tablename__ = "workspace_table_preferences"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
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


class UserGroup(Base, TimestampMixin):
    __tablename__ = "user_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_user_groups_tenant_id_id"),
        UniqueConstraint("tenant_id", "normalized_name", name="uq_user_groups_tenant_name"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)


class UserGroupMembership(Base):
    __tablename__ = "user_group_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "group_id"],
            ["user_groups.tenant_id", "user_groups.id"],
            name="fk_user_group_memberships_tenant_group",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_user_group_memberships_tenant_user",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "group_id", "user_id", name="uq_user_group_membership"),
        Index("ix_user_group_memberships_tenant_group", "tenant_id", "group_id"),
        Index("ix_user_group_memberships_tenant_user", "tenant_id", "user_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    group_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class Entity(Base, TimestampMixin):
    __tablename__ = "entities"
    __table_args__ = (
        Index("ix_entities_tenant_type_normalized_name", "tenant_id", "entity_type", "normalized_name"),
        Index("ix_entities_tenant_type_name", "tenant_id", "entity_type", "name"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    external_ids: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.DRAFT, index=True, nullable=False
    )
    aliases: Mapped[list[EntityAlias]] = relationship(back_populates="entity", cascade="all, delete-orphan")
    identity_identifiers: Mapped[list[EntityIdentifier]] = relationship(
        cascade="all, delete-orphan",
        foreign_keys="EntityIdentifier.entity_id",
        order_by="(EntityIdentifier.namespace, EntityIdentifier.normalized_value)",
    )
    canonical_link: Mapped[EntityCanonicalLink | None] = relationship(
        foreign_keys="EntityCanonicalLink.alias_entity_id", uselist=False
    )

    @property
    def canonical_entity_id(self) -> str:
        if self.canonical_link is not None and self.canonical_link.active:
            return self.canonical_link.canonical_entity_id
        return self.id


class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (UniqueConstraint("tenant_id", "entity_id", "normalized_alias"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    alias: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16))
    entity: Mapped[Entity] = relationship(back_populates="aliases")


class EntityIdentifier(Base, TimestampMixin):
    __tablename__ = "entity_identifiers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_id", "namespace", "normalized_value"),
        Index(
            "ix_entity_identifiers_lookup",
            "tenant_id",
            "entity_type",
            "namespace",
            "normalized_value",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType), index=True, nullable=False)
    namespace: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(500), nullable=False)
    trusted_namespace: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.DRAFT, index=True, nullable=False
    )


class OntologyTerm(Base, TimestampMixin):
    __tablename__ = "ontology_terms"
    __table_args__ = (
        UniqueConstraint("tenant_id", "ontology_name", "ontology_version", "term_id"),
        Index("ix_ontology_terms_lookup", "tenant_id", "ontology_name", "term_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    ontology_name: Mapped[str] = mapped_column(String(100), nullable=False)
    ontology_version: Mapped[str] = mapped_column(String(100), nullable=False)
    term_id: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType), index=True, nullable=False)
    preferred_label: Mapped[str] = mapped_column(String(500), nullable=False)
    definition: Mapped[str | None] = mapped_column(Text)
    synonyms: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    parent_term_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_uri: Mapped[str | None] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)


class EntityOntologyMapping(Base, TimestampMixin):
    __tablename__ = "entity_ontology_mappings"
    __table_args__ = (UniqueConstraint("tenant_id", "entity_id", "ontology_term_id", "mapping_type"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    ontology_term_id: Mapped[str] = mapped_column(ForeignKey("ontology_terms.id"), index=True, nullable=False)
    mapping_type: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.DRAFT, index=True, nullable=False
    )


class EntityResolutionCase(Base, TimestampMixin):
    __tablename__ = "entity_resolution_cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_entity_id", "candidate_entity_id"),
        CheckConstraint("source_entity_id <> candidate_entity_id", name="ck_resolution_distinct_entities"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    candidate_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[ResolutionStatus] = mapped_column(
        Enum(ResolutionStatus), default=ResolutionStatus.PENDING, index=True, nullable=False
    )
    proposed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(String(4000))


class EntityCanonicalLink(Base, TimestampMixin):
    __tablename__ = "entity_canonical_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "alias_entity_id"),
        CheckConstraint("alias_entity_id <> canonical_entity_id", name="ck_canonical_link_distinct_entities"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    alias_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    canonical_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    resolution_case_id: Mapped[str] = mapped_column(
        ForeignKey("entity_resolution_cases.id"), index=True, nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)


class EntityResolutionDecision(Base):
    __tablename__ = "entity_resolution_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    resolution_case_id: Mapped[str] = mapped_column(
        ForeignKey("entity_resolution_cases.id"), index=True, nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    decided_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(4000))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class SourceDocument(Base, TimestampMixin):
    __tablename__ = "source_documents"
    __table_args__ = (UniqueConstraint("tenant_id", "content_sha256"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_uri: Mapped[str | None] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    # Legacy upgrade data only; retained until customers approve the destructive column-removal migration.
    ragflow_dataset_id: Mapped[str | None] = mapped_column(String(64), index=True)
    ragflow_document_id: Mapped[str | None] = mapped_column(String(64), index=True)


class Relationship(Base, TimestampMixin):
    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "subject_id", "predicate", "object_id", "valid_from"),
        Index("ix_relationships_subject_predicate", "tenant_id", "subject_id", "predicate"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subject_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    predicate: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    object_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.DRAFT, nullable=False)


class EvidenceClaim(Base, TimestampMixin):
    __tablename__ = "evidence_claims"
    __table_args__ = (Index("ix_claims_entity_predicate", "tenant_id", "subject_id", "predicate"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subject_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    predicate: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    object_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True, nullable=False)
    page_number: Mapped[int | None]
    source_locator: Mapped[str | None] = mapped_column(String(500))
    quote: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.DRAFT, index=True, nullable=False
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


class TargetProfile(Base, TimestampMixin):
    __tablename__ = "target_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "entity_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    gene_symbol: Mapped[str | None] = mapped_column(String(80), index=True)
    uniprot_accession: Mapped[str | None] = mapped_column(String(20), index=True)
    organism: Mapped[str] = mapped_column(String(120), default="Homo sapiens", nullable=False)
    target_class: Mapped[str | None] = mapped_column(String(160), index=True)
    sequence: Mapped[str | None] = mapped_column(Text)
    function_summary: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)


class TargetEvidenceObservation(Base, TimestampMixin):
    __tablename__ = "target_evidence_observations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_system", "source_record_id"),
        Index("ix_target_evidence_target_type", "tenant_id", "target_entity_id", "evidence_type"),
        Index("ix_target_evidence_disease_type", "tenant_id", "disease_entity_id", "evidence_type"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(240), index=True, nullable=False)
    target_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    disease_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    study_name: Mapped[str | None] = mapped_column(String(500))
    population: Mapped[str | None] = mapped_column(String(500))
    tissue: Mapped[str | None] = mapped_column(String(240), index=True)
    variant: Mapped[str | None] = mapped_column(String(240), index=True)
    effect_size: Mapped[float | None] = mapped_column(Float)
    effect_unit: Mapped[str | None] = mapped_column(String(80))
    p_value: Mapped[float | None] = mapped_column(Float)
    sample_size: Mapped[int | None]
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    qualifiers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)


class CompoundStructure(Base, TimestampMixin):
    __tablename__ = "compound_structures"
    __table_args__ = (
        UniqueConstraint("tenant_id", "standard_inchi_key"),
        Index("ix_compound_structure_entity", "tenant_id", "entity_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    canonical_smiles: Mapped[str] = mapped_column(Text, nullable=False)
    isomeric_smiles: Mapped[str | None] = mapped_column(Text)
    standard_inchi: Mapped[str | None] = mapped_column(Text)
    standard_inchi_key: Mapped[str] = mapped_column(String(27), index=True, nullable=False)
    molecular_formula: Mapped[str | None] = mapped_column(String(120))
    molecular_weight: Mapped[float | None] = mapped_column(Float)
    exact_mass: Mapped[float | None] = mapped_column(Float)
    structure_version: Mapped[str] = mapped_column(String(40), default="source", nullable=False)
    standardization_version: Mapped[str] = mapped_column(
        String(100),
        default="legacy-source/v1",
        server_default="legacy-source/v1",
        nullable=False,
    )
    fingerprint_version: Mapped[str] = mapped_column(
        String(100),
        default="morganbv-radius2-2048/rdkit-2026.03.3",
        server_default="morganbv-radius2-2048/rdkit-2026.03.3",
        nullable=False,
    )


class Assay(Base, TimestampMixin):
    __tablename__ = "assays"
    __table_args__ = (UniqueConstraint("tenant_id", "source_system", "source_assay_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    source_assay_id: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    target_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    assay_type: Mapped[str | None] = mapped_column(String(80), index=True)
    assay_format: Mapped[str | None] = mapped_column(String(120), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    organism: Mapped[str | None] = mapped_column(String(160))
    cell_line: Mapped[str | None] = mapped_column(String(160))
    confidence_score: Mapped[int | None]
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"))


class ActivityMeasurement(Base, TimestampMixin):
    __tablename__ = "activity_measurements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_system", "source_activity_id"),
        Index(
            "ix_activity_target_type_value",
            "tenant_id",
            "target_entity_id",
            "standard_type",
            "standard_value",
        ),
        Index("ix_activity_compound", "tenant_id", "compound_entity_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    source_activity_id: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    assay_id: Mapped[str] = mapped_column(ForeignKey("assays.id"), index=True, nullable=False)
    compound_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    target_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    reported_type: Mapped[str] = mapped_column(String(80), nullable=False)
    reported_relation: Mapped[MeasurementRelation] = mapped_column(Enum(MeasurementRelation), nullable=False)
    reported_value: Mapped[str] = mapped_column(String(120), nullable=False)
    reported_units: Mapped[str | None] = mapped_column(String(40))
    standard_type: Mapped[str | None] = mapped_column(String(80), index=True)
    standard_relation: Mapped[MeasurementRelation | None] = mapped_column(Enum(MeasurementRelation))
    standard_value: Mapped[float | None] = mapped_column(Numeric(24, 8))
    standard_units: Mapped[str | None] = mapped_column(String(40))
    pchembl_value: Mapped[float | None] = mapped_column(Float, index=True)
    qualifiers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    validity_comment: Mapped[str | None] = mapped_column(String(500))


class DevelopmentProgram(Base, TimestampMixin):
    __tablename__ = "development_programs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "drug_entity_id", "disease_entity_id", "organization_entity_id"),
        Index("ix_program_target_phase", "tenant_id", "target_entity_id", "phase"),
        Index("ix_program_target_combination_lookup", "tenant_id", "target_combination_key"),
        Index("ix_program_regional_phase", "tenant_id", "global_phase", "china_phase"),
        CheckConstraint(
            "global_phase IS NULL OR global_phase IN "
            "('discovery','preclinical','ind','phase_1','phase_1_2','phase_2','phase_2_3','phase_3',"
            "'filed','approved','discontinued')",
            name="ck_program_global_phase",
        ),
        CheckConstraint(
            "china_phase IS NULL OR china_phase IN "
            "('discovery','preclinical','ind','phase_1','phase_1_2','phase_2','phase_2_3','phase_3',"
            "'filed','approved','discontinued')",
            name="ck_program_china_phase",
        ),
        CheckConstraint(
            "program_status IS NULL OR program_status IN ('active', 'inactive', 'unknown')",
            name="ck_program_status",
        ),
        CheckConstraint(
            "global_phase_started_at IS NULL OR global_phase IS NOT NULL",
            name="ck_program_global_phase_date_requires_phase",
        ),
        CheckConstraint(
            "china_phase_started_at IS NULL OR china_phase IS NOT NULL",
            name="ck_program_china_phase_date_requires_phase",
        ),
        CheckConstraint("target_set_version > 0", name="ck_development_program_target_set_version"),
        CheckConstraint("organization_set_version > 0", name="ck_development_program_org_set_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    drug_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    target_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    disease_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    organization_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    modality: Mapped[str | None] = mapped_column(String(120), index=True)
    innovation_type: Mapped[str | None] = mapped_column(String(120), index=True)
    therapeutic_area: Mapped[str | None] = mapped_column(String(120), index=True)
    drug_category: Mapped[str | None] = mapped_column(String(120), index=True)
    mechanism_of_action: Mapped[str | None] = mapped_column(String(240))
    phase: Mapped[DevelopmentPhase] = mapped_column(Enum(DevelopmentPhase), index=True, nullable=False)
    status_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    geography: Mapped[str | None] = mapped_column(String(120), index=True)
    status_detail: Mapped[str | None] = mapped_column(Text)
    program_status: Mapped[str | None] = mapped_column(String(20), index=True)
    organization_set_version: Mapped[int] = mapped_column(default=1, nullable=False)
    status_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    milestones: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    global_phase: Mapped[str | None] = mapped_column(String(40), index=True)
    china_phase: Mapped[str | None] = mapped_column(String(40), index=True)
    global_phase_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    china_phase_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    development_rights_regions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    commercialization_rights_regions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    program_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    target_set_version: Mapped[int] = mapped_column(default=1, nullable=False)
    target_combination_key: Mapped[str | None] = mapped_column(String(760), index=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"))


class DevelopmentProgramTarget(Base, TimestampMixin):
    __tablename__ = "development_program_targets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "program_id", "target_set_version", "target_entity_id"),
        UniqueConstraint("tenant_id", "program_id", "target_set_version", "position"),
        Index(
            "ix_program_targets_current_lookup",
            "tenant_id",
            "program_id",
            "target_set_version",
            "position",
        ),
        Index(
            "ix_program_targets_target_lookup",
            "tenant_id",
            "target_entity_id",
            "program_id",
            "target_set_version",
        ),
        CheckConstraint("target_set_version > 0", name="ck_program_target_set_version"),
        CheckConstraint("position >= 0 AND position < 20", name="ck_program_target_position"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    program_id: Mapped[str] = mapped_column(ForeignKey("development_programs.id"), index=True, nullable=False)
    target_set_version: Mapped[int] = mapped_column(index=True, nullable=False)
    target_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    role: Mapped[ProgramTargetRole] = mapped_column(
        Enum(ProgramTargetRole, values_callable=lambda members: [member.value for member in members]),
        index=True,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)


class DevelopmentProgramOrganization(Base, TimestampMixin):
    """Versioned organization roles for one development program.

    Mirrors `DevelopmentProgramTarget` for set versioning and `DealPartyAssociation`
    for per-association governed attributes, so originator and collaborator are
    distinguishable instead of collapsing into one nullable column.
    """

    __tablename__ = "development_program_organizations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "program_id",
            "organization_set_version",
            "organization_entity_id",
            name="uq_program_org_entity",
        ),
        UniqueConstraint(
            "tenant_id",
            "program_id",
            "organization_set_version",
            "position",
            name="uq_program_org_position",
        ),
        Index(
            "ix_program_orgs_current_lookup",
            "tenant_id",
            "program_id",
            "organization_set_version",
            "position",
        ),
        Index(
            "ix_program_orgs_entity_lookup",
            "tenant_id",
            "organization_entity_id",
            "program_id",
            "organization_set_version",
        ),
        CheckConstraint("organization_set_version > 0", name="ck_program_org_set_version"),
        CheckConstraint("position >= 0 AND position < 20", name="ck_program_org_position"),
        CheckConstraint(
            "role IN ('originator','collaborator','licensee','licensor','manufacturer','other')",
            name="ck_program_org_role",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    program_id: Mapped[str] = mapped_column(ForeignKey("development_programs.id"), index=True, nullable=False)
    organization_set_version: Mapped[int] = mapped_column(index=True, nullable=False)
    organization_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    country_region: Mapped[str | None] = mapped_column(String(120), index=True)
    organization_type: Mapped[str | None] = mapped_column(String(120), index=True)
    position: Mapped[int] = mapped_column(nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)


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


class PatentFamily(Base, TimestampMixin):
    __tablename__ = "patent_families"
    __table_args__ = (UniqueConstraint("tenant_id", "family_identifier"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    family_identifier: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    priority_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    applicants: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    inventors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    publications: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    legal_status: Mapped[str | None] = mapped_column(String(120), index=True)
    legal_status_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    legal_events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    independent_claims: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    expiration_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    linked_entity_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"))


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
        CheckConstraint(
            "development_phase_at_transaction IS NULL OR development_phase_at_transaction IN "
            "('discovery','preclinical','ind','phase_1','phase_1_2','phase_2','phase_2_3','phase_3',"
            "'filed','approved','discontinued')",
            name="ck_deal_asset_transaction_phase",
        ),
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


class NewsEvent(Base, TimestampMixin):
    __tablename__ = "news_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_identifier"),
        CheckConstraint(
            "event_type IN ('news', 'press_release', 'corporate_announcement', 'publication', "
            "'conference_abstract', 'poster', 'presentation', 'other')",
            name="ck_news_event_type",
        ),
        Index("ix_news_event_published", "tenant_id", "published_at"),
        Index("ix_news_event_publisher", "tenant_id", "publisher_entity_id", "published_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    event_identifier: Mapped[str] = mapped_column(String(240), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    language: Mapped[str | None] = mapped_column(String(32), index=True)
    publisher_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    related_entity_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    venue: Mapped[str | None] = mapped_column(String(240), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("source_documents.id"), index=True)


class DataSource(Base, TimestampMixin):
    __tablename__ = "data_sources"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name"),
        UniqueConstraint("tenant_id", "root_uri"),
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


class ProjectionMaintenanceJob(Base, TimestampMixin):
    __tablename__ = "projection_maintenance_jobs"
    __table_args__ = (
        UniqueConstraint("active_key"),
        CheckConstraint(
            "operation IN ('consistency_check','rebuild')",
            name="ck_projection_maintenance_operation",
        ),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed')",
            name="ck_projection_maintenance_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_projection_maintenance_attempts"),
        Index("ix_projection_maintenance_jobs_status_created", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    operation: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    active_key: Mapped[str | None] = mapped_column(String(40))
    build_id: Mapped[str | None] = mapped_column(String(80), index=True)
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(200), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)


class DataQualitySnapshot(Base):
    __tablename__ = "data_quality_snapshots"
    __table_args__ = (
        CheckConstraint("trigger IN ('scheduled','manual')", name="ck_data_quality_snapshot_trigger"),
        Index("ix_quality_snapshots_tenant_measured", "tenant_id", "measured_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    trigger: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    definitions_version: Mapped[str] = mapped_column(String(40), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class DataQualityIssue(Base, TimestampMixin):
    __tablename__ = "data_quality_issues"
    __table_args__ = (
        UniqueConstraint("tenant_id", "active_key"),
        CheckConstraint(
            "status IN ('open','acknowledged','ready_to_resolve','resolved','waived')",
            name="ck_data_quality_issue_status",
        ),
        CheckConstraint("severity IN ('critical','high','medium','low')", name="ck_data_quality_issue_severity"),
        CheckConstraint("comparison IN ('gte','lte')", name="ck_data_quality_issue_comparison"),
        CheckConstraint("version > 0", name="ck_data_quality_issue_version"),
        Index("ix_quality_issues_tenant_status_due", "tenant_id", "status", "sla_due_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    active_key: Mapped[str | None] = mapped_column(String(160))
    metric_key: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    scope_id: Mapped[str | None] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    comparison: Mapped[str] = mapped_column(String(8), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    sla_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    last_snapshot_id: Mapped[str] = mapped_column(ForeignKey("data_quality_snapshots.id"), index=True, nullable=False)


class DataQualityIssueEvent(Base):
    __tablename__ = "data_quality_issue_events"
    __table_args__ = (Index("ix_quality_issue_events_issue_occurred", "issue_id", "occurred_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    issue_id: Mapped[str] = mapped_column(ForeignKey("data_quality_issues.id"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(24))
    resulting_status: Mapped[str] = mapped_column(String(24), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class KnowledgePage(Base, TimestampMixin):
    __tablename__ = "knowledge_pages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "page_key"),
        Index("ix_knowledge_pages_tenant_type_title", "tenant_id", "page_type", "title"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    page_key: Mapped[str] = mapped_column(String(240), nullable=False)
    page_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    subject_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    status: Mapped[KnowledgePageStatus] = mapped_column(
        Enum(KnowledgePageStatus), default=KnowledgePageStatus.DRAFT, index=True, nullable=False
    )
    current_version_id: Mapped[str | None] = mapped_column(String(36), index=True)


class KnowledgePageVersion(Base):
    __tablename__ = "knowledge_page_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "knowledge_page_id", "version_number"),
        UniqueConstraint("tenant_id", "knowledge_page_id", "content_sha256"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    knowledge_page_id: Mapped[str] = mapped_column(ForeignKey("knowledge_pages.id"), index=True, nullable=False)
    version_number: Mapped[int] = mapped_column(nullable=False)
    compiler_version: Mapped[str] = mapped_column(String(80), nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rendered_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_run_id: Mapped[str | None] = mapped_column(String(200), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class KnowledgeCitation(Base):
    __tablename__ = "knowledge_citations"
    __table_args__ = (UniqueConstraint("tenant_id", "page_version_id", "ordinal"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    page_version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_page_versions.id"), index=True, nullable=False)
    ordinal: Mapped[int] = mapped_column(nullable=False)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True, nullable=False)
    evidence_claim_id: Mapped[str | None] = mapped_column(ForeignKey("evidence_claims.id"), index=True)
    source_locator: Mapped[str | None] = mapped_column(String(500))
    quote: Mapped[str | None] = mapped_column(Text)


class KnowledgeLink(Base):
    __tablename__ = "knowledge_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "page_version_id", "relationship", "target_key"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_knowledge_link_confidence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    page_version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_page_versions.id"), index=True, nullable=False)
    relationship: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    target_key: Mapped[str] = mapped_column(String(240), index=True, nullable=False)
    target_page_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_pages.id"), index=True)
    target_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_state_available", "state", "available_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    state: Mapped[OutboxState] = mapped_column(
        Enum(OutboxState), default=OutboxState.PENDING, index=True, nullable=False
    )
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class ProjectionDelivery(Base):
    __tablename__ = "projection_deliveries"
    __table_args__ = (
        UniqueConstraint("consumer_name", "outbox_event_id"),
        Index("ix_projection_delivery_due", "consumer_name", "state", "available_at"),
        CheckConstraint("attempts > 0", name="ck_projection_delivery_attempts"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    consumer_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    outbox_event_id: Mapped[str] = mapped_column(ForeignKey("outbox_events.id"), index=True, nullable=False)
    state: Mapped[ProjectionDeliveryState] = mapped_column(Enum(ProjectionDeliveryState), index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(default=1, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    worker_id: Mapped[str | None] = mapped_column(String(200), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class SavedSearch(Base, TimestampMixin):
    __tablename__ = "saved_searches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "owner_user_id", "name"),
        CheckConstraint("query_version > 0", name="ck_saved_search_query_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    query_type: Mapped[str] = mapped_column(String(80), default="entity_search", index=True, nullable=False)
    query_version: Mapped[int] = mapped_column(default=1, nullable=False)
    query_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    visibility: Mapped[SavedSearchVisibility] = mapped_column(
        String(20), default=SavedSearchVisibility.PRIVATE, index=True, nullable=False
    )


class SavedSearchVersion(Base):
    __tablename__ = "saved_search_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "saved_search_id", "version"),
        CheckConstraint("version > 0", name="ck_saved_search_version_positive"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    saved_search_id: Mapped[str] = mapped_column(ForeignKey("saved_searches.id"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    query_type: Mapped[str] = mapped_column(String(80), nullable=False)
    query_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class MonitoringTopic(Base, TimestampMixin):
    __tablename__ = "monitoring_topics"
    __table_args__ = (
        UniqueConstraint("tenant_id", "owner_user_id", "name"),
        CheckConstraint("query_version > 0", name="ck_monitoring_topic_query_version_positive"),
        ForeignKeyConstraint(
            ["tenant_id", "saved_search_id", "query_version"],
            [
                "saved_search_versions.tenant_id",
                "saved_search_versions.saved_search_id",
                "saved_search_versions.version",
            ],
            name="fk_monitoring_topic_saved_search_version",
        ),
        Index("ix_monitoring_topic_saved_search_version", "tenant_id", "saved_search_id", "query_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    saved_search_id: Mapped[str] = mapped_column(ForeignKey("saved_searches.id"), index=True, nullable=False)
    query_version: Mapped[int] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)


class MonitoringAlert(Base):
    __tablename__ = "monitoring_alerts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "topic_id", "source_outbox_event_id"),
        Index("ix_monitoring_alerts_inbox", "tenant_id", "recipient_user_id", "occurred_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    topic_id: Mapped[str] = mapped_column(ForeignKey("monitoring_topics.id"), index=True, nullable=False)
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    source_outbox_event_id: Mapped[str] = mapped_column(ForeignKey("outbox_events.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class MonitoringAlertReceipt(Base):
    __tablename__ = "monitoring_alert_receipts"
    __table_args__ = (UniqueConstraint("tenant_id", "alert_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    alert_id: Mapped[str] = mapped_column(ForeignKey("monitoring_alerts.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class ComparisonSet(Base, TimestampMixin):
    __tablename__ = "comparison_sets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "owner_user_id", "name"),
        CheckConstraint("version > 0", name="ck_comparison_set_version_positive"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    visibility: Mapped[SavedSearchVisibility] = mapped_column(
        String(20), default=SavedSearchVisibility.PRIVATE, index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(default=1, nullable=False)


class ComparisonSetMember(Base):
    __tablename__ = "comparison_set_members"
    __table_args__ = (
        UniqueConstraint("tenant_id", "comparison_set_id", "entity_id"),
        UniqueConstraint("tenant_id", "comparison_set_id", "position"),
        CheckConstraint("position >= 0", name="ck_comparison_set_member_position"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    comparison_set_id: Mapped[str] = mapped_column(ForeignKey("comparison_sets.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    added_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class ComparisonSetVersion(Base):
    __tablename__ = "comparison_set_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "comparison_set_id", "version"),
        CheckConstraint("version > 0", name="ck_comparison_set_history_version_positive"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    comparison_set_id: Mapped[str] = mapped_column(ForeignKey("comparison_sets.id"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


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


class DataExportJob(Base):
    __tablename__ = "data_export_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "agent_client_id", "idempotency_key"),
        UniqueConstraint("reservation_id"),
        Index("ix_data_export_jobs_state_created", "tenant_id", "state", "created_at"),
        CheckConstraint("actor_type IN ('agent', 'api_key')", name="ck_export_job_actor_type"),
        CheckConstraint("export_format IN ('jsonl', 'csv')", name="ck_export_job_format"),
        CheckConstraint(
            "state IN ('pending_approval', 'queued', 'running', 'completed', 'failed', 'cancel_requested', "
            "'cancelled', 'expired')",
            name="ck_export_job_state",
        ),
        CheckConstraint("max_records > 0", name="ck_export_job_max_records"),
        CheckConstraint("record_count >= 0", name="ck_export_job_record_count"),
        CheckConstraint("artifact_bytes >= 0", name="ck_export_job_artifact_bytes"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    billing_account_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    agent_client_id: Mapped[str] = mapped_column(ForeignKey("agent_clients.id"), index=True, nullable=False)
    reservation_id: Mapped[str | None] = mapped_column(ForeignKey("usage_reservations.id"), index=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    license_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    license_policy_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    license_attribution: Mapped[str] = mapped_column(String(500), nullable=False)
    export_format: Mapped[str] = mapped_column(String(20), nullable=False)
    filters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    fields_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    max_records: Mapped[int] = mapped_column(nullable=False)
    max_billable_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="pending_approval", index=True, nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(500))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    workflow_id: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    record_count: Mapped[int] = mapped_column(default=0, nullable=False)
    artifact_uri: Mapped[str | None] = mapped_column(Text)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    artifact_bytes: Mapped[int] = mapped_column(default=0, nullable=False)
    manifest_uri: Mapped[str | None] = mapped_column(Text)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    manifest_signature: Mapped[str | None] = mapped_column(String(128))
    manifest_key_id: Mapped[str | None] = mapped_column(String(120))
    failure_code: Mapped[str | None] = mapped_column(String(120))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class DataRetentionPolicy(Base, TimestampMixin):
    __tablename__ = "data_retention_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "data_class"),
        CheckConstraint("retention_seconds >= 300", name="ck_retention_policy_minimum"),
        CheckConstraint(
            "data_class IN ('commercial_export_artifact', 'source_asset_snapshot')",
            name="ck_retention_policy_data_class",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    data_class: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    policy_version: Mapped[int] = mapped_column(default=1, nullable=False)
    retention_seconds: Mapped[int] = mapped_column(nullable=False)
    legal_basis: Mapped[str] = mapped_column(String(500), nullable=False)
    geographic_scope: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    configured_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class LegalHold(Base):
    __tablename__ = "legal_holds"
    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('tenant', 'billing_account', 'data_export_job', 'data_source', 'source_asset')",
            name="ck_legal_hold_scope_type",
        ),
        CheckConstraint("status IN ('active', 'released')", name="ck_legal_hold_status"),
        CheckConstraint(
            "(scope_type = 'tenant' AND scope_id IS NULL) OR (scope_type <> 'tenant' AND scope_id IS NOT NULL)",
            name="ck_legal_hold_scope_id",
        ),
        Index("ix_legal_holds_active_scope", "tenant_id", "status", "scope_type", "scope_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    scope_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    scope_id: Mapped[str | None] = mapped_column(String(36), index=True)
    matter_reference: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True, nullable=False)
    placed_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    released_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(String(2000))


class DataLifecycleEvent(Base):
    __tablename__ = "data_lifecycle_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key"),
        CheckConstraint(
            "action IN ('purge', 'blocked', 'reauthorize')",
            name="ck_data_lifecycle_event_action",
        ),
        CheckConstraint(
            "outcome IN ('succeeded', 'blocked')",
            name="ck_data_lifecycle_event_outcome",
        ),
        Index("ix_data_lifecycle_target", "tenant_id", "target_type", "target_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    data_class: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_id: Mapped[str] = mapped_column(ForeignKey("data_retention_policies.id"), nullable=False)
    policy_version: Mapped[int] = mapped_column(nullable=False)
    legal_hold_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


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


class UsageReservation(Base):
    __tablename__ = "usage_reservations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "agent_client_id", "actor_type", "subject_id", "idempotency_key"),
        Index("ix_usage_reservation_expiry", "tenant_id", "state", "lease_expires_at"),
        CheckConstraint("actor_type IN ('agent', 'api_key')", name="ck_usage_reservation_actor_type"),
        CheckConstraint("requested_result_limit > 0", name="ck_usage_reservation_result_limit"),
        CheckConstraint("client_max_units > 0", name="ck_usage_reservation_client_max"),
        CheckConstraint("estimated_units >= 0", name="ck_usage_reservation_estimated"),
        CheckConstraint("requested_compute_units >= 0", name="ck_usage_reservation_compute_units"),
        CheckConstraint("reserved_units > 0", name="ck_usage_reservation_reserved"),
        CheckConstraint("page_offset >= 0", name="ck_usage_reservation_page_offset"),
        CheckConstraint("page_depth > 0", name="ck_usage_reservation_page_depth"),
        CheckConstraint(
            "network_fingerprint IS NULL OR length(network_fingerprint) = 64",
            name="ck_usage_reservation_network_fingerprint",
        ),
        CheckConstraint(
            "credential_fingerprint IS NULL OR length(credential_fingerprint) = 64",
            name="ck_usage_reservation_credential_fingerprint",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    agent_client_id: Mapped[str] = mapped_column(ForeignKey("agent_clients.id"), index=True, nullable=False)
    rate_card_item_id: Mapped[str] = mapped_column(ForeignKey("rate_card_items.id"), index=True, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    network_fingerprint: Mapped[str | None] = mapped_column(String(64))
    credential_fingerprint: Mapped[str | None] = mapped_column(String(64))
    correlation_key_id: Mapped[str] = mapped_column(String(120), nullable=False)
    billing_class: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    query_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    cursor_chain_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    page_offset: Mapped[int] = mapped_column(default=0, nullable=False)
    page_depth: Mapped[int] = mapped_column(default=1, nullable=False)
    requested_result_limit: Mapped[int] = mapped_column(nullable=False)
    requested_compute_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"), nullable=False)
    client_max_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    estimated_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    reserved_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    state: Mapped[UsageReservationState] = mapped_column(
        Enum(UsageReservationState), default=UsageReservationState.RESERVED, index=True, nullable=False
    )
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    execution_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(String(500))


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_key"),
        CheckConstraint("result_count >= 0", name="ck_usage_event_result_count"),
        CheckConstraint("unique_record_count >= 0", name="ck_usage_event_unique_record_count"),
        CheckConstraint("new_unique_record_count >= 0", name="ck_usage_event_new_unique_record_count"),
        CheckConstraint(
            "new_unique_record_count <= unique_record_count",
            name="ck_usage_event_new_unique_within_total",
        ),
        CheckConstraint("response_bytes >= 0", name="ck_usage_event_response_bytes"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    reservation_id: Mapped[str] = mapped_column(ForeignKey("usage_reservations.id"), unique=True, index=True)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    billing_class: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    result_count: Mapped[int] = mapped_column(nullable=False)
    unique_record_count: Mapped[int] = mapped_column(default=0, nullable=False)
    new_unique_record_count: Mapped[int] = mapped_column(default=0, nullable=False)
    response_bytes: Mapped[int] = mapped_column(nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class CommercialCoverageRecord(Base):
    __tablename__ = "commercial_coverage_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "subscription_id",
            "agent_client_id",
            "entitlement_key",
            "period_start",
            "record_type",
            "record_identifier_sha256",
            name="uq_commercial_coverage_exact_record",
        ),
        Index(
            "ix_commercial_coverage_budget",
            "tenant_id",
            "subscription_id",
            "entitlement_key",
            "period_start",
        ),
        CheckConstraint("actor_type IN ('agent', 'api_key')", name="ck_coverage_actor_type"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    agent_client_id: Mapped[str] = mapped_column(ForeignKey("agent_clients.id"), index=True, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    entitlement_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    record_type: Mapped[str] = mapped_column(String(160), nullable=False)
    record_identifier_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    first_usage_event_id: Mapped[str] = mapped_column(ForeignKey("usage_events.id"), index=True, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CommercialPolicyEvent(Base):
    __tablename__ = "commercial_policy_events"
    __table_args__ = (
        Index(
            "ix_commercial_policy_scope",
            "tenant_id",
            "subscription_id",
            "occurred_at",
        ),
        Index(
            "ix_commercial_policy_risk_queue",
            "tenant_id",
            "decision",
            "occurred_at",
            "id",
        ),
        CheckConstraint("actor_type IN ('agent', 'api_key')", name="ck_policy_actor_type"),
        CheckConstraint("phase IN ('reserve', 'settle')", name="ck_policy_phase"),
        CheckConstraint("decision IN ('allow', 'deny')", name="ck_policy_decision"),
        CheckConstraint("requested_records >= 0", name="ck_policy_requested_records"),
        CheckConstraint("existing_unique_records >= 0", name="ck_policy_existing_records"),
        CheckConstraint("projected_unique_records >= 0", name="ck_policy_projected_records"),
        CheckConstraint("page_depth > 0", name="ck_policy_page_depth"),
        CheckConstraint(
            "projected_unique_records >= existing_unique_records",
            name="ck_policy_projected_after_existing",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    agent_client_id: Mapped[str] = mapped_column(ForeignKey("agent_clients.id"), index=True, nullable=False)
    reservation_id: Mapped[str | None] = mapped_column(ForeignKey("usage_reservations.id"), index=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    entitlement_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    phase: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    query_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    cursor_chain_id: Mapped[str] = mapped_column(String(36), nullable=False)
    page_depth: Mapped[int] = mapped_column(nullable=False)
    requested_records: Mapped[int] = mapped_column(nullable=False)
    existing_unique_records: Mapped[int] = mapped_column(nullable=False)
    projected_unique_records: Mapped[int] = mapped_column(nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class CommercialRiskCase(Base, TimestampMixin):
    __tablename__ = "commercial_risk_cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "policy_event_id"),
        CheckConstraint(
            "status IN ('acknowledged', 'resolved', 'dismissed')",
            name="ck_commercial_risk_case_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    policy_event_id: Mapped[str] = mapped_column(ForeignKey("commercial_policy_events.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    notes: Mapped[str] = mapped_column(String(2000), default="", nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(500), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class UsageSettlement(Base):
    __tablename__ = "usage_settlements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "settlement_key"),
        CheckConstraint("charged_units >= 0", name="ck_usage_settlement_charged"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    settlement_key: Mapped[str] = mapped_column(String(200), nullable=False)
    reservation_id: Mapped[str] = mapped_column(
        ForeignKey("usage_reservations.id"), unique=True, index=True, nullable=False
    )
    usage_event_id: Mapped[str] = mapped_column(ForeignKey("usage_events.id"), unique=True, index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    rate_card_version_id: Mapped[str] = mapped_column(ForeignKey("rate_card_versions.id"), index=True, nullable=False)
    charged_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    price_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class CommercialLedgerEntry(Base):
    __tablename__ = "commercial_ledger_entries"
    __table_args__ = (UniqueConstraint("tenant_id", "event_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    reservation_id: Mapped[str | None] = mapped_column(ForeignKey("usage_reservations.id"), index=True)
    settlement_id: Mapped[str | None] = mapped_column(ForeignKey("usage_settlements.id"), index=True)
    adjustment_id: Mapped[str | None] = mapped_column(ForeignKey("billing_adjustments.id"), index=True)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[CommercialLedgerEventType] = mapped_column(
        Enum(CommercialLedgerEventType), index=True, nullable=False
    )
    granted_delta: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"), nullable=False)
    reserved_delta: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"), nullable=False)
    consumed_delta: Mapped[Decimal] = mapped_column(Numeric(28, 8), default=Decimal("0"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class BillingAdjustment(Base):
    __tablename__ = "billing_adjustments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "adjustment_key"),
        UniqueConstraint(
            "tenant_id",
            "reverses_adjustment_id",
            name="uq_billing_adjustment_single_reversal",
        ),
        UniqueConstraint(
            "tenant_id",
            "reverses_settlement_id",
            name="uq_billing_settlement_single_reversal",
        ),
        CheckConstraint("units_delta != 0", name="ck_billing_adjustment_nonzero"),
        CheckConstraint(
            "adjustment_kind IN ('usage_adjustment', 'settlement_reversal', 'adjustment_reversal')",
            name="ck_billing_adjustment_kind",
        ),
        CheckConstraint(
            "(adjustment_kind = 'usage_adjustment' "
            "AND reverses_adjustment_id IS NULL AND reverses_settlement_id IS NULL) "
            "OR (adjustment_kind = 'settlement_reversal' "
            "AND reverses_adjustment_id IS NULL AND reverses_settlement_id IS NOT NULL AND units_delta < 0) "
            "OR (adjustment_kind = 'adjustment_reversal' "
            "AND reverses_adjustment_id IS NOT NULL AND reverses_settlement_id IS NULL)",
            name="ck_billing_adjustment_reference",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    adjustment_key: Mapped[str] = mapped_column(String(200), nullable=False)
    adjustment_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    reverses_adjustment_id: Mapped[str | None] = mapped_column(ForeignKey("billing_adjustments.id"), index=True)
    reverses_settlement_id: Mapped[str | None] = mapped_column(ForeignKey("usage_settlements.id"), index=True)
    units_delta: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_by: Mapped[str] = mapped_column(String(500), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class CommercialReconciliationRun(Base):
    __tablename__ = "commercial_reconciliation_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_key"),
        CheckConstraint("status IN ('clean', 'drift')", name="ck_commercial_reconciliation_status"),
        CheckConstraint("issue_count >= 0", name="ck_commercial_reconciliation_issue_count"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    run_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    issue_count: Mapped[int] = mapped_column(nullable=False)
    snapshot_granted_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    snapshot_reserved_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    snapshot_consumed_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    ledger_granted_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    ledger_reserved_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    ledger_consumed_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    source_granted_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    source_reserved_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    source_consumed_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    issues_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(500), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class BillingPeriodStatement(Base):
    __tablename__ = "billing_period_statements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "statement_key"),
        UniqueConstraint(
            "tenant_id",
            "subscription_id",
            "period_start",
            "period_end",
            "revision",
            name="uq_billing_statement_period_revision",
        ),
        UniqueConstraint("tenant_id", "manifest_sha256", name="uq_billing_statement_manifest"),
        CheckConstraint("period_end > period_start", name="ck_billing_statement_period"),
        CheckConstraint("revision > 0", name="ck_billing_statement_revision"),
        CheckConstraint("settlement_count >= 0", name="ck_billing_statement_settlement_count"),
        CheckConstraint("adjustment_count >= 0", name="ck_billing_statement_adjustment_count"),
        CheckConstraint("result_count >= 0", name="ck_billing_statement_result_count"),
        CheckConstraint("response_bytes >= 0", name="ck_billing_statement_response_bytes"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    billing_account_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.id"), index=True, nullable=False)
    statement_key: Mapped[str] = mapped_column(String(200), nullable=False)
    revision: Mapped[int] = mapped_column(nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    settlement_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    adjustment_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    net_consumed_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    settlement_count: Mapped[int] = mapped_column(nullable=False)
    adjustment_count: Mapped[int] = mapped_column(nullable=False)
    result_count: Mapped[int] = mapped_column(nullable=False)
    response_bytes: Mapped[int] = mapped_column(nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_key_id: Mapped[str] = mapped_column(String(120), nullable=False)
    manifest_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    generated_by: Mapped[str] = mapped_column(String(500), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class InvoiceReference(Base, TimestampMixin):
    __tablename__ = "invoice_references"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_invoice_id"),
        UniqueConstraint("statement_id", name="uq_invoice_reference_statement"),
        CheckConstraint("period_end > period_start", name="ck_invoice_period"),
        CheckConstraint("total_units >= 0", name="ck_invoice_total_units"),
        CheckConstraint("amount_due >= 0", name="ck_invoice_amount_due"),
        CheckConstraint("length(currency) = 3", name="ck_invoice_currency"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    billing_account_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.id"), index=True, nullable=False)
    statement_id: Mapped[str | None] = mapped_column(ForeignKey("billing_period_statements.id"), index=True)
    external_invoice_id: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    amount_due: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(100), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class BillingDispute(Base, TimestampMixin):
    __tablename__ = "billing_disputes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dispute_key"),
        CheckConstraint(
            "status IN ('open', 'investigating', 'resolved', 'rejected', 'cancelled')",
            name="ck_billing_dispute_status",
        ),
        CheckConstraint(
            "category IN ('usage', 'pricing', 'duplicate', 'authorization', 'service', 'other')",
            name="ck_billing_dispute_category",
        ),
        CheckConstraint("disputed_units > 0", name="ck_billing_dispute_positive_units"),
        CheckConstraint("version > 0", name="ck_billing_dispute_version"),
        CheckConstraint(
            "(status IN ('open', 'investigating') AND resolved_at IS NULL AND resolved_by IS NULL "
            "AND resolution_code IS NULL) OR "
            "(status = 'resolved' AND resolved_at IS NOT NULL AND resolved_by IS NOT NULL "
            "AND resolution_code IN ('credit', 'no_credit')) OR "
            "(status = 'rejected' AND resolved_at IS NOT NULL AND resolved_by IS NOT NULL "
            "AND resolution_code = 'rejected') OR "
            "(status = 'cancelled' AND resolved_at IS NOT NULL AND resolved_by IS NOT NULL "
            "AND resolution_code = 'cancelled')",
            name="ck_billing_dispute_resolution_state",
        ),
        CheckConstraint(
            "resolution_adjustment_key IS NULL OR (status = 'resolved' AND resolution_code = 'credit')",
            name="ck_billing_dispute_adjustment_state",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    dispute_key: Mapped[str] = mapped_column(String(120), nullable=False)
    billing_account_id: Mapped[str] = mapped_column(ForeignKey("billing_accounts.id"), index=True, nullable=False)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("commercial_subscriptions.id"), index=True, nullable=False)
    statement_id: Mapped[str] = mapped_column(ForeignKey("billing_period_statements.id"), index=True, nullable=False)
    invoice_reference_id: Mapped[str | None] = mapped_column(ForeignKey("invoice_references.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    disputed_units: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(4000), nullable=False)
    opened_by: Mapped[str] = mapped_column(String(500), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(500), index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    resolution_code: Mapped[str | None] = mapped_column(String(40))
    resolution_notes: Mapped[str] = mapped_column(String(4000), default="", nullable=False)
    resolved_by: Mapped[str | None] = mapped_column(String(500))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    resolution_adjustment_key: Mapped[str | None] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(default=1, nullable=False)


class BillingDisputeEvent(Base):
    __tablename__ = "billing_dispute_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dispute_id", "operation_key", name="uq_billing_dispute_operation"),
        CheckConstraint(
            "event_type IN ('opened', 'investigating', 'resolved', 'rejected', 'cancelled')",
            name="ck_billing_dispute_event_type",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    dispute_id: Mapped[str] = mapped_column(ForeignKey("billing_disputes.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(500), nullable=False)
    operation_key: Mapped[str] = mapped_column(String(120), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    note: Mapped[str] = mapped_column(String(4000), default="", nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
