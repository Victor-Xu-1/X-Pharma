from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, cast
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pharma_intel.api_key_lifecycle import MANAGED_API_KEY_SCOPES
from pharma_intel.ingest.readiness import AUTHORIZATION_SCOPE_PATTERN
from pharma_intel.models import (
    DataSourceState,
    DataSourceType,
    DealDirection,
    DealPartyRole,
    DealRightType,
    DealStatus,
    DevelopmentPhase,
    EntityType,
    GovernanceStatus,
    KnowledgePageStatus,
    QuarantineStatus,
    RegulatoryDesignationType,
    RegulatoryLabelChangeType,
    RegulatorySafetySeverity,
    RegulatorySafetySignalType,
    RegulatorySafetyStatus,
    ReviewStatus,
    RunState,
    SavedSearchVisibility,
    SourceAssetState,
    SourceVersionState,
    StageStatus,
    TrialEntityRole,
    TrialResultDisclosureType,
    TrialResultEvaluation,
    UsageReservationState,
    UserRole,
)
from pharma_intel.sorting import (
    MAX_SORT_CRITERIA,
    SORT_TOKEN_PATTERN,
    parse_sort_tokens,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


def _validate_human_display_name(value: str) -> str:
    if not any(character.isalnum() for character in value):
        raise ValueError("display_name must include at least one letter or number")
    return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    email: str
    display_name: str
    phone: str | None
    avatar_url: str | None
    role: UserRole


class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    avatar_url: str | None = Field(default=None, max_length=2048)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return _validate_human_display_name(value) if value is not None else None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> UserProfileUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one profile field must be supplied")
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("display_name cannot be null")
        return self


class UserPasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


class EnterpriseTenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    slug: str
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime


class EnterpriseOverviewRead(BaseModel):
    tenant: EnterpriseTenantRead
    user_count: int
    active_user_count: int
    admin_count: int
    group_count: int
    active_group_count: int
    dataset_count: int
    active_source_count: int
    audit_event_count_24h: int


class EnterpriseLLMProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    base_url: str
    model: str
    priority: int
    version: int
    active: bool
    api_key_configured: bool = True
    api_key_fingerprint: str
    response_format_mode: Literal["json_schema", "json_object", "prompt_only"]
    thinking_mode: Literal["provider_default", "enabled", "disabled"]
    include_schema_in_prompt: bool
    max_output_tokens_per_segment: int
    request_timeout_seconds: float
    request_attempts: int
    last_tested_at: datetime | None
    last_test_status: Literal["passed", "failed"] | None
    last_test_message: str | None
    created_at: datetime
    updated_at: datetime


class _EnterpriseLLMProviderInputBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,119}$")
    base_url: str = Field(min_length=10, max_length=2048)
    model: str = Field(min_length=1, max_length=500)
    response_format_mode: Literal["json_schema", "json_object", "prompt_only"] = "prompt_only"
    thinking_mode: Literal["provider_default", "enabled", "disabled"] = "disabled"
    include_schema_in_prompt: bool = True
    max_output_tokens_per_segment: int = Field(default=16_384, ge=256, le=131_072)
    request_timeout_seconds: float = Field(default=120, ge=1, le=600)
    request_attempts: int = Field(default=2, ge=1, le=8)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("base_url must be a credential-free HTTPS API root")
        return value.rstrip("/")


class EnterpriseLLMProviderCreate(_EnterpriseLLMProviderInputBase):
    api_key: str = Field(min_length=8, max_length=8192, repr=False)


class EnterpriseLLMProviderUpdate(_EnterpriseLLMProviderInputBase):
    expected_version: int = Field(ge=1)
    api_key: str | None = Field(default=None, min_length=8, max_length=8192, repr=False)
    active: bool


class EnterpriseLLMProviderPrimaryUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    email: str
    display_name: str
    role: UserRole
    active: bool
    token_version: int
    last_login_at: datetime | None
    oidc_issuer: str | None
    created_at: datetime
    updated_at: datetime


class EnterpriseUserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    role: UserRole = UserRole.VIEWER
    initial_password: str | None = Field(default=None, min_length=12, max_length=200)
    oidc_issuer: str | None = Field(default=None, min_length=8, max_length=500)
    oidc_subject: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _validate_human_display_name(value)

    @model_validator(mode="after")
    def validate_identity_shape(self) -> EnterpriseUserCreate:
        if bool(self.oidc_issuer) != bool(self.oidc_subject):
            raise ValueError("oidc_issuer and oidc_subject must be supplied together")
        if self.initial_password is not None and self.oidc_issuer is not None:
            raise ValueError("initial_password and OIDC identity are mutually exclusive")
        return self


class EnterpriseUserRoleUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_token_version: int = Field(ge=1)
    role: UserRole
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseUserStatusUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_token_version: int = Field(ge=1)
    active: bool
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseDatasetRead(BaseModel):
    id: str
    dataset_key: str
    display_name: str
    active: bool
    version: int
    required_scopes: list[str]
    license_id: str
    license_policy_version: str
    permitted_channels: list[Literal["web", "mcp"]]
    license_current: bool
    attribution: str


class EnterpriseDatasetStatusUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    active: bool
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseSessionRead(BaseModel):
    id: str
    user_id: str
    user_display_name: str
    user_email: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    revoked_by_user_id: str | None
    revoke_reason: str | None
    current: bool


class EnterpriseSessionRevoke(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseApiKeyRead(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: list[str]
    active: bool
    status: Literal["active", "expired", "revoked", "disabled"]
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    commercial_client_id: str | None
    commercial_client_name: str | None
    created_at: datetime
    updated_at: datetime


class EnterpriseApiKeyCatalogRead(BaseModel):
    items: list[EnterpriseApiKeyRead]
    required_scope: str
    allowed_scopes: list[str]
    min_ttl_hours: int
    max_ttl_days: int


def _managed_api_key_scopes(values: list[str]) -> list[str]:
    normalized = sorted({value.strip() for value in values if value.strip()})
    unknown = sorted(set(normalized) - set(MANAGED_API_KEY_SCOPES))
    if unknown:
        raise ValueError(f"Unmanaged API key scopes: {', '.join(unknown)}")
    if "mcp:connect" not in normalized:
        raise ValueError("Managed API keys must include mcp:connect")
    if len(normalized) < 2:
        raise ValueError("Managed API keys must include at least one data-access scope")
    return normalized


class EnterpriseApiKeyCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(min_length=2, max_length=len(MANAGED_API_KEY_SCOPES))
    expires_at: datetime
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        return _managed_api_key_scopes(value)


class EnterpriseApiKeyRotate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    expires_at: datetime
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseApiKeyRevoke(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseApiKeySecretRead(EnterpriseApiKeyRead):
    secret: str


class PlatformServiceRead(BaseModel):
    service_id: str
    owner: str
    escalation_policy: str
    status: Literal["ready", "degraded", "blocked", "external"]
    detail: str


class PlatformWorkflowRead(BaseModel):
    engine: Literal["temporal"]
    enabled: bool
    namespace: str
    task_queue: str
    max_concurrent_activities: int


class PlatformModelBudgetRead(BaseModel):
    window: Literal["24h"]
    run_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost: str
    failed_runs: int
    max_document_cost: str
    provider: str
    model: str


class PlatformSloRead(BaseModel):
    id: str
    service: str
    metric: str
    measurement: str
    target: float
    window: str
    evaluation_status: Literal["external_evidence_required"]
    error_budget_policy: str


class PlatformAlertRead(BaseModel):
    id: str
    objective: str
    severity: Literal["warning", "critical"]
    threshold: float
    lookback: str
    runbook: str


class PlatformMigrationRead(BaseModel):
    current_revision: str | None
    expected_revision: str | None
    status: Literal["current", "behind", "unknown"]


class PlatformEvidenceRead(BaseModel):
    category: Literal["backup_restore", "release_candidate", "production_topology"]
    status: Literal["not_configured", "missing", "passed", "failed", "invalid"]
    artifact: str
    sha256: str | None
    observed_at: str | None
    detail: str


class PlatformEventRead(BaseModel):
    id: str
    action: str
    outcome: str
    resource_type: str
    occurred_at: datetime
    request_id: str


class PlatformOperationsRead(BaseModel):
    generated_at: datetime
    environment: str
    services: list[PlatformServiceRead]
    queues: dict[str, Any]
    workflow: PlatformWorkflowRead
    model_budget: PlatformModelBudgetRead
    slos: list[PlatformSloRead]
    alerts: list[PlatformAlertRead]
    migration: PlatformMigrationRead
    evidence: list[PlatformEvidenceRead]
    recent_events: list[PlatformEventRead]


class UserGroupCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=500)


class UserGroupUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=500)
    active: bool
    reason: str = Field(min_length=3, max_length=500)


class UserGroupMembershipUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    user_ids: list[str] = Field(default_factory=list, max_length=500)
    reason: str = Field(min_length=3, max_length=500)


class UserGroupRead(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str
    active: bool
    version: int
    member_ids: list[str]
    member_count: int
    created_at: datetime
    updated_at: datetime


class EnterpriseAuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    actor_type: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    request_id: str
    details: dict[str, Any]
    occurred_at: datetime


class EnterpriseAuditPageRead(BaseModel):
    items: list[EnterpriseAuditEventRead]
    next_cursor: str | None


class EntityCreate(BaseModel):
    entity_type: EntityType
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    aliases: list[str] = Field(default_factory=list, max_length=100)
    external_ids: dict[str, str] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)


class EntityIdentifierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    namespace: str
    value: str
    normalized_value: str
    trusted_namespace: bool
    review_status: ReviewStatus
    source_document_id: str | None


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_type: EntityType
    name: str
    description: str | None
    external_ids: dict[str, str]
    attributes: dict[str, Any]
    review_status: ReviewStatus
    canonical_entity_id: str
    identity_identifiers: list[EntityIdentifierRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RecentEntityVisitRead(BaseModel):
    entity: EntityRead
    visited_at: datetime


WorkspaceTablePreferenceKey = Literal[
    "clinical-trials",
    "deals",
    "entity-search",
    "epidemiology",
    "news-events",
    "patent-families",
    "pipeline",
    "regulatory-events",
]
WorkspaceTableDensity = Literal["comfortable", "compact"]
_WORKSPACE_COLUMN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")


class WorkspaceTablePreferenceUpdate(BaseModel):
    schema_version: Literal[1] = 1
    expected_version: int = Field(ge=0)
    column_visibility: dict[str, bool] = Field(default_factory=dict, max_length=64)
    column_order: list[str] = Field(default_factory=list, max_length=64)
    density: WorkspaceTableDensity = "comfortable"

    @field_validator("column_visibility")
    @classmethod
    def validate_column_visibility(cls, value: dict[str, bool]) -> dict[str, bool]:
        if any(_WORKSPACE_COLUMN_ID_PATTERN.fullmatch(column_id) is None for column_id in value):
            raise ValueError("Column visibility contains an invalid column ID")
        return value

    @field_validator("column_order")
    @classmethod
    def validate_column_order(cls, value: list[str]) -> list[str]:
        if any(_WORKSPACE_COLUMN_ID_PATTERN.fullmatch(column_id) is None for column_id in value):
            raise ValueError("Column order contains an invalid column ID")
        if len(value) != len(set(value)):
            raise ValueError("Column order IDs must be unique")
        return value


class WorkspaceTablePreferenceRead(BaseModel):
    preference_key: WorkspaceTablePreferenceKey
    schema_version: Literal[1] = 1
    column_visibility: dict[str, bool] = Field(default_factory=dict)
    column_order: list[str] = Field(default_factory=list)
    density: WorkspaceTableDensity = "comfortable"
    version: int = Field(ge=0)
    persisted: bool
    updated_at: datetime | None = None


WebVitalMetricName = Literal["CLS", "INP", "LCP", "TTFB"]
WebVitalRating = Literal["good", "needs-improvement", "poor"]
WebVitalNavigationType = Literal[
    "navigate",
    "reload",
    "back-forward",
    "back-forward-cache",
    "prerender",
    "restore",
    "soft-navigation",
]
WebVitalViewportClass = Literal["desktop", "tablet", "mobile"]
ResearchWebVitalRoute = Literal[
    "overview",
    "explorer",
    "chemistry",
    "pipeline",
    "trials",
    "patents",
    "deals",
    "regulatory",
    "epidemiology",
    "news",
    "target",
    "drug",
    "company",
    "disease",
    "entity",
    "evidence",
    "knowledge",
    "monitoring",
    "collections",
    "unknown",
]
_WEB_VITAL_THRESHOLDS: dict[str, tuple[float, float]] = {
    "CLS": (0.1, 0.25),
    "INP": (200, 500),
    "LCP": (2500, 4000),
    "TTFB": (800, 1800),
}


class WebVitalSampleCreate(BaseModel):
    metric_name: WebVitalMetricName
    value: float = Field(ge=0, le=120_000, allow_inf_nan=False)
    rating: WebVitalRating
    route: ResearchWebVitalRoute
    navigation_type: WebVitalNavigationType
    navigation_sequence: int = Field(ge=0, le=10_000)
    viewport_class: WebVitalViewportClass

    @model_validator(mode="after")
    def validate_metric_integrity(self) -> WebVitalSampleCreate:
        if self.metric_name == "CLS" and self.value > 10:
            raise ValueError("CLS value exceeds the accepted telemetry boundary")
        good_threshold, poor_threshold = _WEB_VITAL_THRESHOLDS[self.metric_name]
        expected_rating: WebVitalRating
        if self.value <= good_threshold:
            expected_rating = "good"
        elif self.value <= poor_threshold:
            expected_rating = "needs-improvement"
        else:
            expected_rating = "poor"
        if self.rating != expected_rating:
            raise ValueError("Web Vital rating does not match the measured value")
        return self


class WebVitalBatchCreate(BaseModel):
    schema_version: Literal[1] = 1
    samples: list[WebVitalSampleCreate] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_unique_navigation_metrics(self) -> WebVitalBatchCreate:
        identities = [(sample.navigation_sequence, sample.metric_name) for sample in self.samples]
        if len(identities) != len(set(identities)):
            raise ValueError("Web Vital navigation metrics must be unique within a batch")
        return self


class WebVitalBatchAccepted(BaseModel):
    schema_version: Literal[1] = 1
    accepted_count: int = Field(ge=1, le=8)


class EntitySearchMatchRead(BaseModel):
    match_type: Literal["canonical_name", "alias", "external_id", "description", "semantic"]
    match_relation: Literal["exact", "partial", "semantic"]
    matched_value: str | None = None
    namespace: str | None = None


class EntitySearchItemRead(EntityRead):
    aliases: list[str] = Field(default_factory=list, max_length=20)
    match: EntitySearchMatchRead | None = None


class EntityResolutionCaseRead(BaseModel):
    id: str
    source_entity_id: str
    source_entity_name: str
    candidate_entity_id: str
    candidate_entity_name: str
    entity_type: EntityType
    score: float
    risk_tier: Literal["low", "medium", "high"]
    reasons: list[dict[str, Any]]
    status: Literal["pending", "approved", "rejected", "reverted"]
    proposed_by: str
    reviewed_by_user_id: str | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime
    updated_at: datetime


class EntityResolutionDecisionRequest(BaseModel):
    action: Literal["approve", "reject", "revert"]
    expected_status: Literal["pending", "approved", "rejected", "reverted"]
    canonical_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    notes: str | None = Field(default=None, max_length=4000)


class EntityReferenceImpactRead(BaseModel):
    domain: str
    table: str
    column: str
    source_count: int
    candidate_count: int


class EntityResolutionDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    action: str
    decided_by_user_id: str
    notes: str | None
    snapshot: dict[str, Any]
    created_at: datetime


class EntityResolutionImpactRead(BaseModel):
    case: EntityResolutionCaseRead
    source_reference_count: int
    candidate_reference_count: int
    source_trusted_identifier_count: int
    candidate_trusted_identifier_count: int
    recommended_canonical_entity_id: str
    recommendation_reasons: list[str]
    active_alias_entity_id: str | None
    active_canonical_entity_id: str | None
    rollback_available: bool
    references: list[EntityReferenceImpactRead]
    decisions: list[EntityResolutionDecisionRead]


class PublicationBatchPreviewRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    operation: Literal["publish", "withdraw"]
    staged_fact_ids: list[str] = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=128)
    reason: str | None = Field(default=None, max_length=4000)


class PublicationBatchCommitRequest(BaseModel):
    preview_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PublicationBatchItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    staged_fact_id: str
    position: int
    expected_status: str
    outcome: str
    blockers: list[dict[str, Any]]
    snapshot: dict[str, Any]
    created_at: datetime


class PublicationBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    idempotency_key: str
    operation: Literal["publish", "withdraw"]
    status: Literal["previewed", "committed", "failed"]
    preview_sha256: str
    expected_count: int
    blocked_count: int
    reason: str | None
    requested_by_user_id: str
    committed_by_user_id: str | None
    committed_at: datetime | None
    result: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    items: list[PublicationBatchItemRead] = Field(default_factory=list)


class ProjectionMaintenanceRequest(BaseModel):
    operation: Literal["consistency_check", "rebuild"]


class ProjectionMaintenanceAccessRead(BaseModel):
    allowed: bool


class ProjectionMaintenanceJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation: Literal["consistency_check", "rebuild"]
    status: Literal["queued", "running", "succeeded", "failed"]
    build_id: str | None
    requested_by_user_id: str
    attempts: int
    worker_id: str | None
    lease_expires_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    result: dict[str, Any]
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class DataQualitySnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trigger: Literal["scheduled", "manual"]
    definitions_version: str
    window_start: datetime
    window_end: datetime
    measured_at: datetime
    metrics: dict[str, dict[str, Any]]
    created_at: datetime


class DataQualityCoverageRead(BaseModel):
    source_id: str
    name: str
    source_type: str
    dataset_key: str
    owner: str
    state: str
    data_classification: str
    authorization_scopes: list[str]
    authorization_valid_until: datetime | None
    authorization_status: Literal["valid", "expiring", "expired", "missing_scope", "not_yet_valid"]
    asset_count: int
    active_asset_count: int
    parsed_asset_count: int
    parse_missing_count: int
    parse_coverage: float
    fact_count: int
    published_fact_count: int
    review_pending_fact_count: int
    conflict_fact_count: int
    rejected_fact_count: int
    published_fact_coverage: float
    conflict_rate: float
    window_start: datetime
    measured_at: datetime
    run_count: int
    successful_run_count: int
    failed_run_count: int
    ingestion_success_rate: float
    last_scanned_at: datetime | None
    last_success_at: datetime | None
    expected_freshness_seconds: int
    freshness_age_seconds: int | None
    freshness_status: Literal["fresh", "stale", "never_succeeded"]
    consecutive_failures: int
    failure_sla_age_seconds: int | None
    failure_sla_status: Literal["healthy", "at_risk", "breached"]
    last_error_present: bool


class DataQualityOwnerRead(BaseModel):
    id: str
    display_name: str
    role: UserRole


class DataQualityIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    metric_key: str
    scope_type: str
    scope_id: str | None
    status: Literal["open", "acknowledged", "ready_to_resolve", "resolved", "waived"]
    severity: Literal["critical", "high", "medium", "low"]
    title: str
    description: str
    actual_value: float
    threshold_value: float
    comparison: Literal["gte", "lte"]
    owner_user_id: str | None
    owner_display_name: str | None = None
    sla_due_at: datetime
    detected_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    resolution_notes: str | None
    version: int
    last_snapshot_id: str
    created_at: datetime
    updated_at: datetime


class DataQualityIssueEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    action: str
    actor_type: str
    actor_id: str
    previous_status: str | None
    resulting_status: str
    details: dict[str, Any]
    occurred_at: datetime


class DataQualityIssueActionRequest(BaseModel):
    action: Literal["assign", "acknowledge", "resolve", "waive"]
    expected_version: int = Field(ge=1)
    owner_user_id: str | None = Field(default=None, max_length=36)
    notes: str | None = Field(default=None, max_length=4000)


class OntologyTermUpsert(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    ontology_name: str = Field(min_length=1, max_length=100)
    ontology_version: str = Field(min_length=1, max_length=100)
    term_id: str = Field(min_length=1, max_length=200)
    entity_type: EntityType
    preferred_label: str = Field(min_length=1, max_length=500)
    definition: str | None = None
    synonyms: list[str] = Field(default_factory=list, max_length=500)
    parent_term_ids: list[str] = Field(default_factory=list, max_length=100)
    source_uri: str | None = Field(default=None, max_length=2000)


class OntologyTermRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    ontology_name: str
    ontology_version: str
    term_id: str
    entity_type: EntityType
    preferred_label: str
    definition: str | None
    synonyms: list[str]
    parent_term_ids: list[str]
    source_uri: str | None
    content_sha256: str
    active: bool
    created_at: datetime
    updated_at: datetime


class EntityOntologyMappingCreate(BaseModel):
    ontology_term_id: str = Field(min_length=36, max_length=36)
    mapping_type: Literal["exact", "broad", "narrow", "related"]
    confidence: float = Field(ge=0, le=1)
    source_document_id: str | None = Field(default=None, min_length=36, max_length=36)
    evidence: dict[str, Any] = Field(default_factory=dict)


EntitySortField = Literal["relevance", "name", "entity_type", "updated_at"]
ENTITY_SORT_FIELDS: tuple[EntitySortField, ...] = ("relevance", "name", "entity_type", "updated_at")
SortToken = Annotated[str, Field(pattern=SORT_TOKEN_PATTERN.pattern)]


class SortCriterionRead(BaseModel):
    field: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    direction: SortDirection


def _synchronize_saved_sort(model: Any, allowed_fields: tuple[str, ...]) -> None:
    clauses = parse_sort_tokens(model.sort, allowed_fields)
    if not clauses:
        return
    primary = clauses[0]
    fields_set = model.model_fields_set
    if "sort_by" in fields_set and model.sort_by != primary.field:
        raise ValueError("sort_by must match the first sort criterion")
    if "sort_direction" in fields_set and model.sort_direction != primary.direction:
        raise ValueError("sort_direction must match the first sort criterion")
    model.sort_by = primary.field
    model.sort_direction = primary.direction


class AppliedFilterRead(BaseModel):
    field: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    operator: Literal["contains", "eq", "in", "gte", "lte"]
    value: str | bool | int | float | list[str]


class QueryResultMetadata(BaseModel):
    query_schema_version: str = Field(pattern=r"^pharma\.[a-z][a-z0-9_.-]+\.v[1-9][0-9]*$")
    applied_filters: list[AppliedFilterRead] = Field(default_factory=list)


class SearchResult(QueryResultMetadata):
    items: list[EntitySearchItemRead]
    total: int
    limit: int
    offset: int
    sort_by: EntitySortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)
    suggestions: list[str] = Field(default_factory=list)
    engine: str = "database"
    took_ms: int | None = None


class EntitySearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    entity_type: EntityType | None = None
    entity_types: list[EntityType] = Field(default_factory=list, max_length=10)
    review_status: ReviewStatus | None = None
    # Presentation state is versioned with the saved query so replay returns the same research view.
    # Defaults are omitted from persisted JSON to keep legacy entity-search records compact.
    display_mode: Literal["list", "landscape"] = Field(default="list", exclude_if=lambda value: value == "list")
    analysis_view: Literal["chart", "table"] = Field(default="chart", exclude_if=lambda value: value == "chart")
    # Presentation-stable server sorting for replay; defaults keep legacy saved JSON valid.
    sort_by: EntitySortField = "relevance"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(
        default_factory=list,
        max_length=MAX_SORT_CRITERIA,
        exclude_if=lambda value: not value,
    )

    @model_validator(mode="after")
    def require_filter(self) -> EntitySearchQuery:
        _synchronize_saved_sort(self, ENTITY_SORT_FIELDS)
        self.entity_types = list(dict.fromkeys(self.entity_types))
        if self.entity_type is not None and self.entity_types and self.entity_type not in self.entity_types:
            raise ValueError("entity_type must be included in entity_types when both are provided")
        if self.q is None and self.entity_type is None and not self.entity_types and self.review_status is None:
            raise ValueError("At least one entity search filter is required")
        return self


class PipelineSavedSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    modality: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None,
        max_length=20,
    )
    innovation_type: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None,
        max_length=20,
    )
    therapeutic_area: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None,
        max_length=20,
    )
    drug_category: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None,
        max_length=20,
    )
    program_status: Literal["active", "inactive", "unknown"] | None = None
    organization_role: Literal["originator", "collaborator", "licensee", "licensor", "manufacturer", "other"] | None = (
        None
    )
    organization_type: str | None = Field(default=None, min_length=1, max_length=120)
    organization_country_region: str | None = Field(default=None, min_length=1, max_length=120)
    phase: DevelopmentPhase | None = None
    geography: str | None = Field(default=None, min_length=1, max_length=120)
    status_date_from: date | None = None
    status_date_to: date | None = None
    drug_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    target_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    target_combination_key: str | None = Field(default=None, min_length=36, max_length=760)
    disease_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    organization_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    global_phase: DevelopmentPhase | None = None
    china_phase: DevelopmentPhase | None = None
    global_phase_started_from: date | None = None
    global_phase_started_to: date | None = None
    china_phase_started_from: date | None = None
    china_phase_started_to: date | None = None
    development_rights_region: str | None = Field(default=None, min_length=1, max_length=240)
    commercialization_rights_region: str | None = Field(default=None, min_length=1, max_length=240)
    program_tag: list[Annotated[str, Field(min_length=1, max_length=240)]] | None = Field(
        default=None,
        max_length=20,
    )
    milestone_type: str | None = Field(default=None, min_length=1, max_length=120)
    milestone_from: date | None = None
    milestone_to: date | None = None
    has_clinical_results: bool | None = None
    clinical_result_evaluation: TrialResultEvaluation | None = None
    has_deal: bool | None = None
    deal_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    deal_total_potential_amount_min: float | None = Field(default=None, ge=0)
    deal_total_potential_amount_max: float | None = Field(default=None, ge=0)
    sort_by: Literal[
        "status_date",
        "drug_name",
        "target_name",
        "disease_name",
        "organization_name",
        "modality",
        "mechanism_of_action",
        "phase",
        "status_detail",
        "geography",
        "global_phase",
        "china_phase",
        "global_phase_started_at",
        "china_phase_started_at",
    ] = "status_date"
    sort_direction: Literal["asc", "desc"] = "desc"
    sort: list[SortToken] = Field(
        default_factory=list,
        max_length=MAX_SORT_CRITERIA,
        exclude_if=lambda value: not value,
    )
    display_mode: Literal["list", "landscape"] = "list"
    analysis_dimension: Literal[
        "all",
        "global_phase",
        "china_phase",
        "targets",
        "target_combinations",
        "diseases",
        "organizations",
        "modality",
        "geography",
    ] = "all"
    analysis_view: Literal["chart", "table"] = "chart"
    analysis_limit: Literal[5, 8, 20, 50, 100, 200] = 8
    analysis_stage_scope: Literal["overall", "global", "china"] = "overall"
    target_aggregation: Literal["all", "primary"] = "all"

    @field_validator("modality", "innovation_type", "therapeutic_area", "drug_category", "program_tag", mode="before")
    @classmethod
    def normalize_repeated_pipeline_filters(cls, value: Any) -> Any:
        # Legacy saved queries and single-value URL parameters stored these as plain
        # strings; normalize to single-element lists so replay keeps the same semantics.
        # Empty collections normalize to None so they can never satisfy the
        # at-least-one-filter rule while applying no actual condition.
        if value is None:
            return None
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list):
            return values
        normalized: list[Any] = []
        for item in values:
            candidate = item.strip() if isinstance(item, str) else item
            if candidate not in normalized:
                normalized.append(candidate)
        return normalized or None

    @model_validator(mode="after")
    def validate_pipeline_query(self) -> PipelineSavedSearchQuery:
        _synchronize_saved_sort(self, PIPELINE_SORT_FIELDS)
        filter_fields = (
            self.q,
            self.modality,
            self.innovation_type,
            self.therapeutic_area,
            self.drug_category,
            self.program_status,
            self.organization_role,
            self.organization_type,
            self.organization_country_region,
            self.phase,
            self.geography,
            self.status_date_from,
            self.status_date_to,
            self.drug_entity_id,
            self.target_entity_id,
            self.target_combination_key,
            self.disease_entity_id,
            self.organization_entity_id,
            self.global_phase,
            self.china_phase,
            self.global_phase_started_from,
            self.global_phase_started_to,
            self.china_phase_started_from,
            self.china_phase_started_to,
            self.development_rights_region,
            self.commercialization_rights_region,
            self.program_tag,
            self.milestone_type,
            self.milestone_from,
            self.milestone_to,
            self.has_clinical_results,
            self.clinical_result_evaluation,
            self.has_deal,
            self.deal_currency,
            self.deal_total_potential_amount_min,
            self.deal_total_potential_amount_max,
        )
        if not any(value is not None for value in filter_fields):
            raise ValueError("At least one pipeline search filter is required")
        for start, end, label in (
            (self.status_date_from, self.status_date_to, "status_date"),
            (self.global_phase_started_from, self.global_phase_started_to, "global_phase_started"),
            (self.china_phase_started_from, self.china_phase_started_to, "china_phase_started"),
            (self.milestone_from, self.milestone_to, "milestone"),
        ):
            if start and end and start > end:
                raise ValueError(f"{label}_from must not be after {label}_to")
        if self.has_clinical_results is False and self.clinical_result_evaluation is not None:
            raise ValueError("clinical_result_evaluation cannot be combined with has_clinical_results=false")
        if self.has_deal is False and any(
            value is not None
            for value in (
                self.deal_currency,
                self.deal_total_potential_amount_min,
                self.deal_total_potential_amount_max,
            )
        ):
            raise ValueError("deal detail filters cannot be combined with has_deal=false")
        if (
            self.deal_total_potential_amount_min is not None or self.deal_total_potential_amount_max is not None
        ) and self.deal_currency is None:
            raise ValueError("deal_currency is required for disclosed amount filters")
        if (
            self.deal_total_potential_amount_min is not None
            and self.deal_total_potential_amount_max is not None
            and self.deal_total_potential_amount_min > self.deal_total_potential_amount_max
        ):
            raise ValueError("deal_total_potential_amount_min must not exceed maximum")
        return self


class ClinicalTrialSavedSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    registry: str | None = Field(default=None, min_length=1, max_length=80)
    status: str | None = Field(default=None, min_length=1, max_length=100)
    phase: str | None = Field(default=None, min_length=1, max_length=80)
    study_type: str | None = Field(default=None, min_length=1, max_length=80)
    acronym: str | None = Field(default=None, min_length=1, max_length=240)
    initiation_type: Literal["iit", "ist"] | None = None
    therapy_line: (
        Literal[
            "first_line",
            "second_line",
            "third_or_later",
            "prevention",
            "treatment_naive",
            "add_on",
            "adjuvant",
            "neoadjuvant",
            "maintenance",
            "consolidation",
            "induction",
            "conversion",
        ]
        | None
    ) = None
    has_results: bool | None = None
    result_evaluation: TrialResultEvaluation | None = None
    results_posted_from: date | None = None
    results_posted_to: date | None = None
    investigational_drug: str | None = Field(default=None, min_length=1, max_length=500)
    combination_drug: str | None = Field(default=None, min_length=1, max_length=500)
    investigational_target: str | None = Field(default=None, min_length=1, max_length=500)
    combination_target: str | None = Field(default=None, min_length=1, max_length=500)
    investigational_drug_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    combination_drug_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    investigational_target_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    combination_target_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    linked_drug_modality: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None, min_length=1, max_length=20
    )
    linked_drug_innovation_type: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None, min_length=1, max_length=20
    )
    linked_drug_category: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None, min_length=1, max_length=20
    )
    linked_drug_program_tag: list[Annotated[str, Field(min_length=1, max_length=240)]] | None = Field(
        default=None, min_length=1, max_length=20
    )
    linked_drug_global_phase: str | None = Field(default=None, min_length=1, max_length=40)
    linked_drug_organization_country_region: str | None = Field(default=None, min_length=1, max_length=120)
    role_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    role_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    role_entity_role: TrialEntityRole | None = None
    has_key_result: bool | None = None
    publication_id: str | None = Field(default=None, min_length=1, max_length=240)
    conference: str | None = Field(default=None, min_length=1, max_length=500)
    disclosed_from: date | None = None
    disclosed_to: date | None = None
    sort_by: Literal[
        "last_update_posted",
        "registry_id",
        "has_results",
        "result_evaluation",
        "overall_status",
        "enrollment",
        "study_type",
        "acronym",
        "initiation_type",
    ] = "last_update_posted"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(
        default_factory=list,
        max_length=MAX_SORT_CRITERIA,
        exclude_if=lambda value: not value,
    )
    # Presentation state travels with the saved contract so monitoring replay restores
    # the exact list/landscape and chart/table view; it never changes the fact query.
    display_mode: Literal["list", "landscape"] = "list"
    analysis_view: Literal["chart", "table"] = "chart"

    @model_validator(mode="after")
    def validate_clinical_trial_query(self) -> ClinicalTrialSavedSearchQuery:
        _synchronize_saved_sort(self, CLINICAL_TRIAL_SORT_FIELDS)
        filter_fields = (
            self.q,
            self.registry,
            self.status,
            self.phase,
            self.study_type,
            self.acronym,
            self.initiation_type,
            self.therapy_line,
            self.has_results,
            self.result_evaluation,
            self.results_posted_from,
            self.results_posted_to,
            self.investigational_drug,
            self.combination_drug,
            self.investigational_target,
            self.combination_target,
            self.investigational_drug_entity_ids,
            self.combination_drug_entity_ids,
            self.investigational_target_entity_ids,
            self.combination_target_entity_ids,
            self.linked_drug_modality,
            self.linked_drug_innovation_type,
            self.linked_drug_category,
            self.linked_drug_program_tag,
            self.linked_drug_global_phase,
            self.linked_drug_organization_country_region,
            self.role_entity_id,
            self.role_entity_ids,
            self.has_key_result,
            self.publication_id,
            self.conference,
            self.disclosed_from,
            self.disclosed_to,
        )
        if not any(value is not None for value in filter_fields):
            raise ValueError("At least one clinical trial search filter is required")
        if self.role_entity_id is not None and self.role_entity_ids is not None:
            raise ValueError("role_entity_id cannot be combined with role_entity_ids")
        if self.role_entity_role is not None and self.role_entity_id is None and self.role_entity_ids is None:
            raise ValueError("role_entity_role requires role_entity_id or role_entity_ids")
        for start, end, label in (
            (self.results_posted_from, self.results_posted_to, "results_posted"),
            (self.disclosed_from, self.disclosed_to, "disclosed"),
        ):
            if start and end and start > end:
                raise ValueError(f"{label}_from must not be after {label}_to")
        return self

    @field_validator(
        "investigational_drug_entity_ids",
        "combination_drug_entity_ids",
        "investigational_target_entity_ids",
        "combination_target_entity_ids",
        "role_entity_ids",
    )
    @classmethod
    def validate_role_entity_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if any(len(entity_id) != 36 for entity_id in value):
            raise ValueError("Clinical trial role entity IDs must be UUID strings")
        if len(value) != len(set(value)):
            raise ValueError("Clinical trial role entity IDs must be unique")
        return sorted(value)

    @field_validator(
        "linked_drug_modality",
        "linked_drug_innovation_type",
        "linked_drug_category",
        "linked_drug_program_tag",
        mode="before",
    )
    @classmethod
    def normalize_linked_drug_values(cls, value: list[str] | str | None) -> list[str] | None:
        if value is None:
            return None
        values = [value] if isinstance(value, str) else value
        normalized = sorted({item.strip() for item in values if item.strip()})
        return normalized or None


class PatentSavedSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    applicant: str | None = Field(default=None, min_length=1, max_length=300)
    legal_status: str | None = Field(default=None, min_length=1, max_length=120)
    priority_from: date | None = None
    priority_to: date | None = None
    expiration_from: date | None = None
    expiration_to: date | None = None
    sort_by: Literal["priority_date", "family_identifier", "legal_status", "expiration_date"] = "priority_date"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(
        default_factory=list,
        max_length=MAX_SORT_CRITERIA,
        exclude_if=lambda value: not value,
    )
    # Presentation state for monitoring replay; never counts as a fact filter.
    display_mode: Literal["list", "landscape"] = "list"
    analysis_view: Literal["chart", "table"] = "chart"

    @model_validator(mode="after")
    def validate_patent_query(self) -> PatentSavedSearchQuery:
        _synchronize_saved_sort(self, PATENT_SORT_FIELDS)
        filter_fields = (
            self.q,
            self.entity_id,
            self.applicant,
            self.legal_status,
            self.priority_from,
            self.priority_to,
            self.expiration_from,
            self.expiration_to,
        )
        if not any(value is not None for value in filter_fields):
            raise ValueError("At least one patent search filter is required")
        for start, end, label in (
            (self.priority_from, self.priority_to, "priority"),
            (self.expiration_from, self.expiration_to, "expiration"),
        ):
            if start and end and start > end:
                raise ValueError(f"{label}_from must not be after {label}_to")
        return self


DealAnalysisDimension = Literal[
    "all",
    "deal_type",
    "status",
    "direction",
    "territory",
    "currency",
    "asset_modality",
    "transaction_phase",
    "current_phase",
    "party_country",
    "rights_territory",
]
DealAnalysisView = Literal["chart", "table"]
DealAnalysisLimit = Literal[5, 8, 20, 50]


class DealSavedSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    deal_type: str | None = Field(default=None, min_length=1, max_length=100)
    status: DealStatus | None = None
    direction: DealDirection | None = None
    direction_reference_jurisdiction: str | None = Field(default=None, min_length=1, max_length=120)
    territory: str | None = Field(default=None, min_length=1, max_length=240)
    asset_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    target_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    disease_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    asset_modality: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None,
        max_length=20,
    )
    asset_program_tag: list[Annotated[str, Field(min_length=1, max_length=240)]] | None = Field(
        default=None,
        max_length=20,
    )
    party: str | None = Field(default=None, min_length=1, max_length=500)
    party_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    party_role: DealPartyRole | None = None
    party_country_region: str | None = Field(default=None, min_length=1, max_length=120)
    party_organization_type: str | None = Field(default=None, min_length=1, max_length=120)
    development_phase_at_transaction: DevelopmentPhase | None = None
    current_development_phase: DevelopmentPhase | None = None
    right_type: DealRightType | None = None
    rights_territory: str | None = Field(default=None, min_length=1, max_length=240)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    announced_from: date | None = None
    announced_to: date | None = None
    terminated_from: date | None = None
    terminated_to: date | None = None
    source_updated_from: date | None = None
    source_updated_to: date | None = None
    upfront_amount_min: float | None = Field(default=None, ge=0)
    upfront_amount_max: float | None = Field(default=None, ge=0)
    total_potential_amount_min: float | None = Field(default=None, ge=0)
    total_potential_amount_max: float | None = Field(default=None, ge=0)
    sort_by: Literal[
        "announced_at",
        "name",
        "deal_type",
        "status",
        "direction",
        "territory",
        "upfront_amount",
        "total_potential_amount",
    ] = "announced_at"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(
        default_factory=list,
        max_length=MAX_SORT_CRITERIA,
        exclude_if=lambda value: not value,
    )
    display_mode: Literal["list", "landscape"] = "list"
    analysis_dimension: DealAnalysisDimension = "all"
    analysis_view: DealAnalysisView = "chart"
    analysis_limit: DealAnalysisLimit = 8

    @field_validator("asset_modality", "asset_program_tag", mode="before")
    @classmethod
    def normalize_repeated_asset_filters(cls, value: Any) -> Any:
        # Empty collections normalize to None: an empty multi-select must never count as
        # a filter, or it would pass the at-least-one-filter rule as a full-library
        # subscription while applying no condition.
        if value is None:
            return None
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list):
            return values
        normalized: list[Any] = []
        for item in values:
            candidate = item.strip() if isinstance(item, str) else item
            if candidate not in normalized:
                normalized.append(candidate)
        return normalized or None

    @model_validator(mode="after")
    def validate_deal_query(self) -> DealSavedSearchQuery:
        _synchronize_saved_sort(self, DEAL_SORT_FIELDS)
        filter_fields = (
            self.q,
            self.deal_type,
            self.status,
            self.direction,
            self.direction_reference_jurisdiction,
            self.territory,
            self.asset_entity_id,
            self.target_entity_id,
            self.disease_entity_id,
            self.asset_modality,
            self.asset_program_tag,
            self.party,
            self.party_entity_id,
            self.party_role,
            self.party_country_region,
            self.party_organization_type,
            self.development_phase_at_transaction,
            self.current_development_phase,
            self.right_type,
            self.rights_territory,
            self.currency,
            self.announced_from,
            self.announced_to,
            self.terminated_from,
            self.terminated_to,
            self.source_updated_from,
            self.source_updated_to,
            self.upfront_amount_min,
            self.upfront_amount_max,
            self.total_potential_amount_min,
            self.total_potential_amount_max,
        )
        if not any(value is not None for value in filter_fields):
            raise ValueError("At least one deal search filter is required")
        if self.party is not None and self.party_entity_id is not None:
            raise ValueError("party and party_entity_id are mutually exclusive")
        for start, end, label in (
            (self.announced_from, self.announced_to, "announced"),
            (self.terminated_from, self.terminated_to, "terminated"),
            (self.source_updated_from, self.source_updated_to, "source_updated"),
        ):
            if start and end and start > end:
                raise ValueError(f"{label}_from must not be after {label}_to")
        for minimum, maximum, label in (
            (self.upfront_amount_min, self.upfront_amount_max, "upfront_amount"),
            (self.total_potential_amount_min, self.total_potential_amount_max, "total_potential_amount"),
        ):
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"{label}_min must not be greater than {label}_max")
        if (
            self.sort_by in {"upfront_amount", "total_potential_amount"}
            or any(token.startswith(("upfront_amount:", "total_potential_amount:")) for token in self.sort)
        ) and self.currency is None:
            raise ValueError("currency is required when sorting disclosed deal amounts")
        return self


class RegulatorySavedSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    agency: str | None = Field(default=None, min_length=1, max_length=80)
    jurisdiction: str | None = Field(default=None, min_length=1, max_length=120)
    event_type: str | None = Field(default=None, min_length=1, max_length=40)
    status: str | None = Field(default=None, min_length=1, max_length=120)
    designation_type: RegulatoryDesignationType | None = None
    label_change_type: RegulatoryLabelChangeType | None = None
    has_boxed_warning: bool | None = None
    safety_signal_type: RegulatorySafetySignalType | None = None
    safety_severity: RegulatorySafetySeverity | None = None
    safety_status: RegulatorySafetyStatus | None = None
    decision_from: date | None = None
    decision_to: date | None = None
    source_updated_from: date | None = None
    source_updated_to: date | None = None
    sort_by: Literal[
        "decision_date",
        "title",
        "agency",
        "jurisdiction",
        "event_type",
        "status",
        "subject",
        "source_updated_at",
    ] = "decision_date"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(
        default_factory=list,
        max_length=MAX_SORT_CRITERIA,
        exclude_if=lambda value: not value,
    )
    # Presentation state for monitoring replay; never counts as a fact filter.
    display_mode: Literal["list", "landscape"] = "list"
    analysis_view: Literal["chart", "table"] = "chart"

    @model_validator(mode="after")
    def validate_regulatory_query(self) -> RegulatorySavedSearchQuery:
        _synchronize_saved_sort(self, REGULATORY_SORT_FIELDS)
        filter_fields = (
            self.q,
            self.agency,
            self.jurisdiction,
            self.event_type,
            self.status,
            self.designation_type,
            self.label_change_type,
            self.has_boxed_warning,
            self.safety_signal_type,
            self.safety_severity,
            self.safety_status,
            self.decision_from,
            self.decision_to,
            self.source_updated_from,
            self.source_updated_to,
        )
        if not any(value is not None for value in filter_fields):
            raise ValueError("At least one regulatory search filter is required")
        for start, end, label in (
            (self.decision_from, self.decision_to, "decision"),
            (self.source_updated_from, self.source_updated_to, "source_updated"),
        ):
            if start and end and start > end:
                raise ValueError(f"{label}_from must not be after {label}_to")
        return self


class EpidemiologySavedSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    disease_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    measure: (
        Literal[
            "prevalence",
            "incidence",
            "mortality",
            "patient_count",
            "diagnosed_count",
            "treated_count",
            "survival_rate",
            "daly",
            "other",
        ]
        | None
    ) = None
    geography: str | None = Field(default=None, min_length=1, max_length=160)
    unit: str | None = Field(default=None, min_length=1, max_length=120)
    patient_population_id: str | None = Field(default=None, min_length=36, max_length=36)
    population_scope: str | None = Field(default=None, min_length=1, max_length=500)
    age_group: str | None = Field(default=None, min_length=1, max_length=120)
    sex: str | None = Field(default=None, min_length=1, max_length=80)
    period_start_from: date | None = None
    period_end_to: date | None = None
    sort_by: Literal[
        "period_end",
        "period_start",
        "disease",
        "measure",
        "value",
        "geography",
        "unit",
        "publisher",
        "sample_size",
    ] = "period_end"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(
        default_factory=list,
        max_length=MAX_SORT_CRITERIA,
        exclude_if=lambda value: not value,
    )
    # Presentation state for monitoring replay; never counts as a fact filter.
    display_mode: Literal["list", "landscape"] = "list"
    analysis_view: Literal["chart", "table"] = "chart"

    @model_validator(mode="after")
    def validate_epidemiology_query(self) -> EpidemiologySavedSearchQuery:
        _synchronize_saved_sort(self, EPIDEMIOLOGY_SORT_FIELDS)
        filter_fields = (
            self.q,
            self.disease_entity_id,
            self.measure,
            self.geography,
            self.unit,
            self.patient_population_id,
            self.population_scope,
            self.age_group,
            self.sex,
            self.period_start_from,
            self.period_end_to,
        )
        if not any(value is not None for value in filter_fields):
            raise ValueError("At least one epidemiology search filter is required")
        if self.period_start_from and self.period_end_to and self.period_start_from > self.period_end_to:
            raise ValueError("period_start_from must not be after period_end_to")
        return self


class NewsSavedSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    event_type: (
        Literal[
            "news",
            "press_release",
            "corporate_announcement",
            "publication",
            "conference_abstract",
            "poster",
            "presentation",
            "other",
        ]
        | None
    ) = None
    publisher: str | None = Field(default=None, min_length=1, max_length=500)
    language: str | None = Field(default=None, min_length=1, max_length=32)
    venue: str | None = Field(default=None, min_length=1, max_length=240)
    published_from: date | None = None
    published_to: date | None = None
    content_scope: Literal["research"] | None = None
    display_mode: Literal["list", "timeline", "landscape"] = "list"
    analysis_view: Literal["chart", "table"] = "chart"
    sort_by: Literal["published_at", "title", "event_type", "publisher", "venue"] = "published_at"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(
        default_factory=list,
        max_length=MAX_SORT_CRITERIA,
        exclude_if=lambda value: not value,
    )

    @model_validator(mode="after")
    def validate_news_query(self) -> NewsSavedSearchQuery:
        _synchronize_saved_sort(self, NEWS_SORT_FIELDS)
        filter_fields = (
            self.q,
            self.entity_id,
            self.event_type,
            self.publisher,
            self.language,
            self.venue,
            self.published_from,
            self.published_to,
            self.content_scope,
        )
        if not any(value is not None for value in filter_fields):
            raise ValueError("At least one news search filter is required")
        if self.published_from and self.published_to and self.published_from > self.published_to:
            raise ValueError("published_from must not be after published_to")
        if self.display_mode == "timeline" and self.content_scope != "research":
            raise ValueError("timeline display requires research content_scope")
        if self.content_scope == "research" and self.event_type not in {
            None,
            "publication",
            "conference_abstract",
            "poster",
            "presentation",
        }:
            raise ValueError("research content_scope requires a research event_type")
        return self


class ChemistrySavedSearchQuery(BaseModel):
    """Versioned saved-search payload; the structure stays server-side, not in a URL."""

    mode: Literal["exact", "substructure", "similarity"]
    query: str = Field(min_length=1, max_length=20_000)
    threshold: float = Field(default=0.5, ge=0, le=1)
    limit: int = Field(default=20, ge=1, le=100)


SavedSearchQueryType = Literal[
    "entity_search",
    "chemistry_search",
    "pipeline_search",
    "clinical_trial_search",
    "patent_search",
    "deal_search",
    "regulatory_search",
    "epidemiology_search",
    "news_search",
]
SavedSearchQuery = (
    EntitySearchQuery
    | ChemistrySavedSearchQuery
    | PipelineSavedSearchQuery
    | ClinicalTrialSavedSearchQuery
    | PatentSavedSearchQuery
    | DealSavedSearchQuery
    | RegulatorySavedSearchQuery
    | EpidemiologySavedSearchQuery
    | NewsSavedSearchQuery
)
_SAVED_SEARCH_QUERY_MODELS: dict[str, type[BaseModel]] = {
    "entity_search": EntitySearchQuery,
    "chemistry_search": ChemistrySavedSearchQuery,
    "pipeline_search": PipelineSavedSearchQuery,
    "clinical_trial_search": ClinicalTrialSavedSearchQuery,
    "patent_search": PatentSavedSearchQuery,
    "deal_search": DealSavedSearchQuery,
    "regulatory_search": RegulatorySavedSearchQuery,
    "epidemiology_search": EpidemiologySavedSearchQuery,
    "news_search": NewsSavedSearchQuery,
}


def _saved_search_query_model(query_type: Any) -> type[BaseModel]:
    model = _SAVED_SEARCH_QUERY_MODELS.get(str(query_type or "entity_search"))
    if model is None:
        raise ValueError("Unsupported saved search query type")
    return model


class SavedSearchCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    query_type: SavedSearchQueryType = "entity_search"
    query: SavedSearchQuery
    visibility: SavedSearchVisibility = SavedSearchVisibility.PRIVATE

    @model_validator(mode="before")
    @classmethod
    def parse_typed_query(cls, value: Any) -> Any:
        if not isinstance(value, dict) or not isinstance(value.get("query"), dict):
            return value
        parsed = dict(value)
        model = _saved_search_query_model(value.get("query_type", "entity_search"))
        parsed["query"] = model.model_validate(value["query"])
        return parsed


class SavedSearchUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    query_type: SavedSearchQueryType | None = None
    query: SavedSearchQuery | None = None
    visibility: SavedSearchVisibility | None = None

    @model_validator(mode="before")
    @classmethod
    def parse_typed_query(cls, value: Any) -> Any:
        if not isinstance(value, dict) or not isinstance(value.get("query"), dict):
            return value
        parsed = dict(value)
        model = _saved_search_query_model(value.get("query_type", "entity_search"))
        parsed["query"] = model.model_validate(value["query"])
        return parsed

    @model_validator(mode="after")
    def require_change(self) -> SavedSearchUpdate:
        if all(value is None for value in (self.name, self.description, self.query, self.visibility)):
            raise ValueError("At least one saved search field must change")
        if self.query_type is not None and self.query is None:
            raise ValueError("query_type can only be supplied with query")
        return self


class SavedSearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    owner_user_id: str
    name: str
    description: str
    query_type: SavedSearchQueryType
    query_version: int
    query_json: SavedSearchQuery
    visibility: SavedSearchVisibility
    created_at: datetime
    updated_at: datetime

    @field_validator("query_json", mode="before")
    @classmethod
    def parse_query_json(cls, value: Any, info: Any) -> SavedSearchQuery:
        model = _saved_search_query_model(info.data.get("query_type"))
        return cast(SavedSearchQuery, model.model_validate(value))


class MonitoringTopicCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    saved_search_id: str = Field(min_length=36, max_length=36)


class MonitoringTopicUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    active: bool | None = None
    query_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_change(self) -> MonitoringTopicUpdate:
        if self.name is None and self.active is None and self.query_version is None:
            raise ValueError("At least one monitoring topic field must change")
        return self


class MonitoringTopicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    owner_user_id: str
    saved_search_id: str
    query_version: int
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime


class MonitoringAlertRead(BaseModel):
    id: str
    topic_id: str
    topic_name: str
    entity_id: str
    entity_name: str
    event_type: str
    title: str
    summary: str
    payload_json: dict[str, Any]
    occurred_at: datetime
    read_at: datetime | None


class ComparisonSetCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    visibility: SavedSearchVisibility = SavedSearchVisibility.PRIVATE


class ComparisonSetUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    visibility: SavedSearchVisibility | None = None

    @model_validator(mode="after")
    def require_change(self) -> ComparisonSetUpdate:
        if self.name is None and self.description is None and self.visibility is None:
            raise ValueError("At least one comparison set field must change")
        return self


class ComparisonSetMemberCreate(BaseModel):
    entity_id: str = Field(min_length=36, max_length=36)
    expected_version: int = Field(ge=1)


class ComparisonSetMembersAdd(BaseModel):
    entity_ids: list[str] = Field(min_length=1, max_length=20)
    expected_version: int = Field(ge=1)

    @field_validator("entity_ids")
    @classmethod
    def validate_entity_ids(cls, value: list[str]) -> list[str]:
        if any(len(entity_id) != 36 for entity_id in value):
            raise ValueError("Comparison set entity IDs must be UUID strings")
        if len(value) != len(set(value)):
            raise ValueError("Comparison set entity IDs must be unique")
        return value


class ComparisonSetMemberRemove(BaseModel):
    expected_version: int = Field(ge=1)


class ComparisonSetSummaryRead(BaseModel):
    id: str
    owner_user_id: str
    name: str
    description: str
    visibility: SavedSearchVisibility
    version: int
    member_count: int
    editable: bool
    created_at: datetime
    updated_at: datetime


class ComparisonSetMemberRead(BaseModel):
    id: str
    position: int
    added_by_user_id: str
    created_at: datetime
    entity: EntityRead


class ComparisonSetDetailRead(ComparisonSetSummaryRead):
    members: list[ComparisonSetMemberRead]


class ComparisonSetVersionRead(BaseModel):
    id: str
    version: int
    snapshot_json: dict[str, Any]
    changed_by_user_id: str
    created_at: datetime


class WorkspaceExportPolicyUpsert(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    policy_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")
    enabled: bool
    allowed_formats: list[Literal["csv", "json", "xlsx"]] = Field(min_length=1, max_length=3)
    allowed_fields: list[str] = Field(min_length=1, max_length=500)
    max_records_per_export: int = Field(ge=1, le=100)
    attribution: str = Field(min_length=1, max_length=500)

    @field_validator("allowed_formats", "allowed_fields")
    @classmethod
    def unique_values(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Workspace export policy lists must not contain duplicates")
        return sorted(value)


class WorkspaceExportPolicyRead(BaseModel):
    id: str
    policy_version: str
    enabled: bool
    allowed_formats: list[str]
    allowed_fields: list[str]
    max_records_per_export: int
    attribution: str
    configured_by_user_id: str
    policy_sha256: str
    created_at: datetime
    updated_at: datetime


class WorkspaceExportCreate(BaseModel):
    expected_version: int = Field(ge=1)
    export_format: Literal["csv", "json", "xlsx"]
    fields: list[str] = Field(min_length=1, max_length=20)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")

    @field_validator("fields")
    @classmethod
    def unique_fields(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Workspace export fields must not contain duplicates")
        return value


WorkspaceDomainExportDataset = Literal[
    "entities",
    "pipelines",
    "trials",
    "patents",
    "deals",
    "regulatory",
    "epidemiology",
    "news",
]


class WorkspaceDomainExportCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    dataset: WorkspaceDomainExportDataset
    query: dict[str, str | int | float | bool | list[str]] = Field(default_factory=dict, max_length=50)
    export_format: Literal["csv", "json", "xlsx"]
    fields: list[str] = Field(min_length=1, max_length=100)
    max_records: int = Field(ge=1, le=100)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")

    @field_validator("fields")
    @classmethod
    def unique_domain_fields(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Workspace domain export fields must not contain duplicates")
        if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", field) for field in value):
            raise ValueError("Workspace domain export fields are invalid")
        return value

    @field_validator("query")
    @classmethod
    def validate_query_shape(
        cls,
        value: dict[str, str | int | float | bool | list[str]],
    ) -> dict[str, str | int | float | bool | list[str]]:
        reserved = {"limit", "offset", "view", "display"}
        if set(value) & reserved:
            raise ValueError("Workspace domain export query contains reserved pagination or presentation fields")
        if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", field) for field in value):
            raise ValueError("Workspace domain export query fields are invalid")
        if any(len(item) > 10 or len(item) != len(set(item)) for item in value.values() if isinstance(item, list)):
            raise ValueError("Workspace domain export query list values are invalid")
        return value


class AgentEntitySearchResult(QueryResultMetadata):
    items: list[EntitySearchItemRead]
    limit: int
    page_depth: int
    next_cursor: str | None
    sort_by: EntitySortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    engine: str = "database"
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)


class AgentPageResult[PageItem](BaseModel):
    items: list[PageItem]
    limit: int
    page_depth: int
    next_cursor: str | None
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)


class EntitySuggestionResult(BaseModel):
    suggestions: list[str]
    engine: str


class SearchProjectionStatusRead(BaseModel):
    available: bool
    version: str | None
    cluster_name: str | None
    cluster_status: str | None
    aliases: dict[str, list[str]]
    deliveries: dict[str, int]
    error: str | None = None


class EvidenceSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    dataset_keys: list[str] = Field(default_factory=list, max_length=20)
    entity_types: list[EntityType] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=50)


class EvidenceDatasetRead(BaseModel):
    dataset_key: str
    display_name: str
    attribution: str


class EvidenceChunk(BaseModel):
    content: str
    document_id: str
    document_name: str
    dataset_id: str
    similarity: float | None = Field(
        default=None,
        description="Retriever ranking score; it is not normalized and is not a probability.",
    )
    positions: list[Any] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceLicenseScope(BaseModel):
    dataset_key: str
    license_id: str
    policy_version: str
    attribution: str
    delivery_channel: Literal["web", "mcp"]
    allowed_fields: list[str]
    max_content_chars: int
    valid_from: datetime | None = None
    expires_at: datetime | None = None


class EvidenceSearchResponse(BaseModel):
    query: str
    chunks: list[EvidenceChunk]
    engine: str
    license_scopes: list[EvidenceLicenseScope]
    warnings: list[str] = Field(default_factory=list)


class AgentEvidenceSearchResult(EvidenceSearchResponse):
    limit: int
    page_depth: int
    next_cursor: str | None


ProvenanceResourceType = Literal[
    "activity_measurement",
    "assay",
    "clinical_trial",
    "compound_structure",
    "deal",
    "development_program",
    "epidemiology_observation",
    "evidence_claim",
    "news_event",
    "patient_population",
    "patent_family",
    "regulatory_event",
    "target_profile",
    "target_evidence",
]


class RecordProvenanceRead(BaseModel):
    id: str
    resource_type: ProvenanceResourceType
    resource_id: str
    dataset_key: str
    evidence_claim_id: str | None = None
    source_document_id: str | None = None
    source_version_id: str | None = None
    content_sha256: str | None = None
    document_name: str
    source_uri: str | None = None
    locator: str | None = None
    quote: str
    subject_entity_id: str | None = None
    review_status: str | None = None
    created_at: datetime
    license: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class RecordProvenanceResponse(BaseModel):
    resource_type: ProvenanceResourceType
    resource_id: str
    items: list[RecordProvenanceRead]
    license_scopes: list[EvidenceLicenseScope]
    warnings: list[str] = Field(default_factory=list)


class BioactivityRead(BaseModel):
    id: str
    compound_entity_id: str
    target_entity_id: str | None
    assay_id: str
    standard_type: str | None
    standard_relation: str | None
    standard_value: float | None
    standard_units: str | None
    pchembl_value: float | None
    reported_type: str
    reported_relation: str
    reported_value: str
    reported_units: str | None
    source_system: str
    source_activity_id: str
    source_document_id: str | None = None


class SarActivityRead(BaseModel):
    id: str
    compound_entity_id: str
    compound_name: str
    target_entity_id: str
    assay_id: str
    assay_type: str | None
    assay_format: str | None
    organism: str | None
    cell_line: str | None
    standard_type: str | None
    standard_relation: str | None
    standard_value: float | None
    standard_units: str | None
    pchembl_value: float | None
    comparison_group: str
    comparable: bool
    comparability_reasons: list[str] = Field(default_factory=list)
    potency_rank: int | None = None
    delta_pchembl: float | None = None
    canonical_smiles: str | None = None
    standard_inchi_key: str | None = None
    validity_comment: str | None = None
    source_system: str
    source_activity_id: str
    source_document_id: str | None = None


class SarComparisonResult(BaseModel):
    items: list[SarActivityRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)
    as_of: datetime | None = None
    warnings: list[str] = Field(default_factory=list)


class ProgramStatusHistoryRead(BaseModel):
    phase: str
    status: str | None = None
    effective_at: datetime
    geography: str | None = None
    reason: str | None = None
    source_document_id: str | None = None


class ProgramMilestoneRead(BaseModel):
    milestone_type: str
    title: str
    occurred_at: datetime
    geography: str | None = None
    description: str | None = None
    source_document_id: str | None = None


class ProgramTargetRead(BaseModel):
    entity_id: str
    name: str
    role: Literal["primary", "combination"]
    position: int = Field(ge=0, lt=20)


class ProgramOrganizationRead(BaseModel):
    entity_id: str
    name: str
    role: Literal["originator", "collaborator", "licensee", "licensor", "manufacturer", "other"]
    country_region: str | None = None
    organization_type: str | None = None
    position: int = Field(ge=0, lt=20)


class ProgramIndicationRead(BaseModel):
    program_id: str
    disease_entity_id: str | None = None
    disease_name: str | None = None
    phase: str
    global_phase: str | None = None
    china_phase: str | None = None
    global_phase_started_at: datetime | None = None
    china_phase_started_at: datetime | None = None
    program_status: Literal["active", "inactive", "unknown"] | None = None
    status_date: datetime | None = None
    geography: str | None = None


class CompetitiveProgramRead(BaseModel):
    id: str
    drug_entity_id: str
    drug_name: str
    target_entity_id: str | None
    target_name: str | None
    targets: list[ProgramTargetRead] = Field(default_factory=list, max_length=20)
    target_combination_key: str | None = Field(default=None, max_length=760)
    disease_entity_id: str | None
    disease_name: str | None
    organization_entity_id: str | None
    organization_name: str | None
    organizations: list[ProgramOrganizationRead] = Field(default_factory=list, max_length=20)
    modality: str | None
    innovation_type: str | None = None
    therapeutic_area: str | None = None
    drug_category: str | None = None
    mechanism_of_action: str | None
    phase: str
    status_detail: str | None
    program_status: Literal["active", "inactive", "unknown"] | None = None
    status_date: datetime | None
    geography: str | None
    global_phase: str | None = None
    china_phase: str | None = None
    global_phase_started_at: datetime | None = None
    china_phase_started_at: datetime | None = None
    development_rights_regions: list[str] = Field(default_factory=list)
    commercialization_rights_regions: list[str] = Field(default_factory=list)
    program_tags: list[str] = Field(default_factory=list)
    status_history: list[ProgramStatusHistoryRead] = Field(default_factory=list)
    milestones: list[ProgramMilestoneRead] = Field(default_factory=list)
    clinical_trial_count: int = Field(default=0, ge=0)
    has_clinical_results: bool = False
    clinical_result_evaluations: list[TrialResultEvaluation] = Field(default_factory=list)
    deal_count: int = Field(default=0, ge=0)
    deal_currencies: list[str] = Field(default_factory=list)
    source_document_id: str | None
    project_count: int = Field(default=1, ge=1)
    indications: list[ProgramIndicationRead] = Field(default_factory=list)
    modalities: list[str] = Field(default_factory=list)
    mechanisms_of_action: list[str] = Field(default_factory=list)
    innovation_types: list[str] = Field(default_factory=list)
    therapeutic_areas: list[str] = Field(default_factory=list)
    drug_categories: list[str] = Field(default_factory=list)
    program_status_counts: dict[str, int] = Field(default_factory=dict)


class PipelineLandscapeBucketRead(BaseModel):
    key: str = Field(min_length=1, max_length=760)
    label: str = Field(min_length=1, max_length=500)
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)
    entity_id: str | None = None
    phase_counts: dict[str, int] = Field(default_factory=dict)


PipelineLandscapeStageScope = Literal["overall", "global", "china"]
PipelineTargetAggregation = Literal["all", "primary"]
PipelineResultGrain = Literal["program", "drug"]


class PipelineLandscapeRead(BaseModel):
    total_programs: int = Field(ge=0)
    distinct_drugs: int = Field(ge=0)
    distinct_targets: int = Field(ge=0)
    distinct_diseases: int = Field(ge=0)
    distinct_organizations: int = Field(ge=0)
    limit: int = Field(ge=5, le=200)
    stage_scope: PipelineLandscapeStageScope
    target_aggregation: PipelineTargetAggregation
    overall_phase: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    global_phase: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    china_phase: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    targets: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    diseases: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    target_combinations: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    modality: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    geography: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    organizations: list[PipelineLandscapeBucketRead] = Field(default_factory=list)


PipelineSortField = Literal[
    "status_date",
    "drug_name",
    "target_name",
    "disease_name",
    "organization_name",
    "modality",
    "mechanism_of_action",
    "phase",
    "status_detail",
    "geography",
    "global_phase",
    "china_phase",
    "global_phase_started_at",
    "china_phase_started_at",
]
PIPELINE_SORT_FIELDS: tuple[PipelineSortField, ...] = (
    "status_date",
    "drug_name",
    "target_name",
    "disease_name",
    "organization_name",
    "modality",
    "mechanism_of_action",
    "phase",
    "status_detail",
    "geography",
    "global_phase",
    "china_phase",
    "global_phase_started_at",
    "china_phase_started_at",
)
ClinicalTrialSortField = Literal[
    "last_update_posted",
    "registry_id",
    "has_results",
    "result_evaluation",
    "overall_status",
    "enrollment",
    "study_type",
    "acronym",
    "initiation_type",
]
CLINICAL_TRIAL_SORT_FIELDS: tuple[ClinicalTrialSortField, ...] = (
    "last_update_posted",
    "registry_id",
    "has_results",
    "result_evaluation",
    "overall_status",
    "enrollment",
    "study_type",
    "acronym",
    "initiation_type",
)
TrialInitiationType = Literal["iit", "ist"]
TrialTherapyLine = Literal[
    "first_line",
    "second_line",
    "third_or_later",
    "prevention",
    "treatment_naive",
    "add_on",
    "adjuvant",
    "neoadjuvant",
    "maintenance",
    "consolidation",
    "induction",
    "conversion",
]
PatentSortField = Literal["priority_date", "family_identifier", "legal_status", "expiration_date"]
PATENT_SORT_FIELDS: tuple[PatentSortField, ...] = (
    "priority_date",
    "family_identifier",
    "legal_status",
    "expiration_date",
)
NewsSortField = Literal["published_at", "title", "event_type", "publisher", "venue"]
NEWS_SORT_FIELDS: tuple[NewsSortField, ...] = ("published_at", "title", "event_type", "publisher", "venue")
DealSortField = Literal[
    "announced_at",
    "name",
    "deal_type",
    "status",
    "direction",
    "territory",
    "upfront_amount",
    "total_potential_amount",
]
DEAL_SORT_FIELDS: tuple[DealSortField, ...] = (
    "announced_at",
    "name",
    "deal_type",
    "status",
    "direction",
    "territory",
    "upfront_amount",
    "total_potential_amount",
)
RegulatorySortField = Literal[
    "decision_date",
    "title",
    "agency",
    "jurisdiction",
    "event_type",
    "status",
    "subject",
    "source_updated_at",
]
REGULATORY_SORT_FIELDS: tuple[RegulatorySortField, ...] = (
    "decision_date",
    "title",
    "agency",
    "jurisdiction",
    "event_type",
    "status",
    "subject",
    "source_updated_at",
)
EpidemiologySortField = Literal[
    "period_end",
    "period_start",
    "disease",
    "measure",
    "value",
    "geography",
    "unit",
    "publisher",
    "sample_size",
]
EPIDEMIOLOGY_SORT_FIELDS: tuple[EpidemiologySortField, ...] = (
    "period_end",
    "period_start",
    "disease",
    "measure",
    "value",
    "geography",
    "unit",
    "publisher",
    "sample_size",
)


class PipelineSearchResult(QueryResultMetadata):
    items: list[CompetitiveProgramRead]
    total: int
    limit: int
    offset: int
    sort_by: PipelineSortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)
    landscape: PipelineLandscapeRead
    result_grain: PipelineResultGrain = "program"
    project_total: int = Field(default=0, ge=0)
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class CompoundStructureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_id: str
    canonical_smiles: str
    isomeric_smiles: str | None
    standard_inchi: str | None
    standard_inchi_key: str
    molecular_formula: str | None
    molecular_weight: float | None
    exact_mass: float | None
    structure_version: str
    standardization_version: str
    fingerprint_version: str


class ChemistrySearchRequest(BaseModel):
    mode: Literal["exact", "substructure", "similarity"]
    query: str = Field(min_length=1, max_length=20_000)
    threshold: float = Field(default=0.5, ge=0, le=1)
    limit: int = Field(default=20, ge=1, le=100)


class ChemistrySearchHitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_id: str
    entity_name: str
    canonical_smiles: str
    isomeric_smiles: str | None
    standard_inchi: str | None
    standard_inchi_key: str
    molecular_formula: str | None
    molecular_weight: float | None
    exact_mass: float | None
    structure_version: str
    standardization_version: str
    fingerprint_version: str
    updated_at: datetime
    similarity: float | None


class ChemistrySearchRead(BaseModel):
    mode: Literal["exact", "substructure", "similarity"]
    normalized_query: str
    items: list[ChemistrySearchHitRead]
    count: int
    as_of: datetime
    standardization_version: str | None
    fingerprint_version: str | None
    similarity_threshold: float | None


class AgentChemistrySearchRead(ChemistrySearchRead):
    limit: int
    page_depth: int
    next_cursor: str | None


class ClinicalTrialInterventionRead(BaseModel):
    name: str
    type: str | None = None
    description: str | None = None
    arm_labels: list[str] = Field(default_factory=list)
    other_names: list[str] = Field(default_factory=list)


class ClinicalTrialSponsorRead(BaseModel):
    name: str
    sponsor_class: str | None = None


class ClinicalTrialLocationRead(BaseModel):
    facility: str | None = None
    city: str | None = None
    state: str | None = None
    country: str
    status: str | None = None


class ClinicalTrialDesignRead(BaseModel):
    allocation: str | None = None
    intervention_model: str | None = None
    intervention_model_description: str | None = None
    primary_purpose: str | None = None
    observational_model: str | None = None
    time_perspective: str | None = None
    masking: str | None = None
    masking_description: str | None = None
    who_masked: list[str] = Field(default_factory=list)


class ClinicalTrialEligibilityRead(BaseModel):
    minimum_age: str | None = None
    maximum_age: str | None = None
    sex: str | None = None
    gender_based: bool | None = None
    healthy_volunteers: bool | None = None
    sampling_method: str | None = None
    criteria: str | None = None


class ClinicalTrialArmRead(BaseModel):
    label: str
    type: str | None = None
    description: str | None = None
    intervention_names: list[str] = Field(default_factory=list)


class ClinicalTrialOutcomeResultRead(BaseModel):
    group_label: str
    value: str
    unit: str | None = None
    participants: int | None = None
    dispersion: str | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None


class ClinicalTrialStatisticalAnalysisRead(BaseModel):
    method: str | None = None
    p_value: str | None = None
    parameter_type: str | None = None
    parameter_value: float | None = None
    confidence_interval_percent: float | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None
    notes: str | None = None


class ClinicalTrialOutcomeRead(BaseModel):
    outcome_type: str | None = None
    measure: str
    description: str | None = None
    time_frame: str | None = None
    results: list[ClinicalTrialOutcomeResultRead] = Field(default_factory=list)
    statistical_analyses: list[ClinicalTrialStatisticalAnalysisRead] = Field(default_factory=list)


class ClinicalTrialStatusHistoryRead(BaseModel):
    status: str
    effective_at: datetime
    effective_at_precision: Literal["day", "month", "year"] | None = None
    reason: str | None = None
    source_document_id: str | None = None


class ClinicalTrialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_id: str
    registry_name: str
    registry_id: str
    official_title: str
    acronym: str | None
    initiation_type: TrialInitiationType | None
    therapy_lines: list[TrialTherapyLine]
    overall_status: str | None
    phases: list[str]
    study_type: str | None
    enrollment: int | None
    start_date: datetime | None
    start_date_precision: Literal["day", "month", "year"] | None
    completion_date: datetime | None
    completion_date_precision: Literal["day", "month", "year"] | None
    interventions: list[ClinicalTrialInterventionRead]
    conditions: list[str]
    sponsors: list[ClinicalTrialSponsorRead]
    outcomes: list[ClinicalTrialOutcomeRead]
    locations: list[ClinicalTrialLocationRead]
    study_design: ClinicalTrialDesignRead
    eligibility: ClinicalTrialEligibilityRead
    arms: list[ClinicalTrialArmRead]
    status_history: list[ClinicalTrialStatusHistoryRead]
    has_results: bool
    result_evaluation: TrialResultEvaluation | None
    results_first_posted: datetime | None
    last_update_posted: datetime | None
    source_document_id: str | None


class ClinicalTrialLinkedEntityRead(BaseModel):
    id: str
    name: str
    entity_type: EntityType


class ClinicalTrialEntityRoleRead(BaseModel):
    entity_id: str
    name: str
    entity_type: EntityType
    role: TrialEntityRole


class ClinicalTrialResultDisclosureRead(BaseModel):
    id: str
    disclosure_key: str
    version: int
    disclosure_type: TrialResultDisclosureType
    external_id: str | None
    title: str
    disclosed_at: datetime
    conference_name: str | None
    is_key_result: bool
    result_evaluation: TrialResultEvaluation | None
    source_locator: str | None
    source_quote: str | None
    source_document_id: str | None


class ClinicalTrialSearchItemRead(ClinicalTrialRead):
    linked_entities: list[ClinicalTrialLinkedEntityRead]
    entity_roles: list[ClinicalTrialEntityRoleRead] = Field(default_factory=list)
    key_result_count: int = 0
    latest_result_disclosure: ClinicalTrialResultDisclosureRead | None = None


class ClinicalTrialDetailRead(ClinicalTrialSearchItemRead):
    result_disclosures: list[ClinicalTrialResultDisclosureRead] = Field(default_factory=list)


class ClinicalTrialLandscapeMatrixRowRead(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    total: int = Field(ge=0)
    values: dict[str, int] = Field(default_factory=dict)


class ClinicalTrialLandscapeRead(BaseModel):
    total_trials: int = Field(ge=0)
    publication_year_phase: list[ClinicalTrialLandscapeMatrixRowRead] = Field(default_factory=list)
    phase_evaluation: list[ClinicalTrialLandscapeMatrixRowRead] = Field(default_factory=list)


class ClinicalTrialSearchResult(QueryResultMetadata):
    items: list[ClinicalTrialSearchItemRead]
    total: int
    limit: int
    offset: int
    sort_by: ClinicalTrialSortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]]
    landscape: ClinicalTrialLandscapeRead
    as_of: datetime
    warnings: list[str]


class PatentPublicationRead(BaseModel):
    publication_number: str
    application_number: str | None = None
    jurisdiction: str | None = None
    publication_date: datetime | None = None
    grant_date: datetime | None = None


class PatentLegalEventRead(BaseModel):
    event_type: str
    status: str | None = None
    occurred_at: datetime
    jurisdiction: str | None = None
    publication_number: str | None = None
    description: str | None = None
    source_document_id: str | None = None


class PatentClaimRead(BaseModel):
    claim_number: str
    claim_type: Literal["composition", "method", "use", "formulation", "sequence", "other"]
    summary: str
    scope: str | None = None
    source_document_id: str | None = None


class PatentFamilyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_id: str
    family_identifier: str
    title: str
    priority_date: datetime | None
    applicants: list[str]
    inventors: list[str]
    publications: list[PatentPublicationRead]
    legal_status: str | None
    legal_status_at: datetime | None
    legal_events: list[PatentLegalEventRead] = Field(default_factory=list)
    independent_claims: list[PatentClaimRead] = Field(default_factory=list)
    expiration_date: datetime | None
    linked_entity_ids: list[str]
    source_document_id: str | None


class PatentFamilyLinkedEntityRead(BaseModel):
    id: str
    name: str
    entity_type: EntityType


class PatentFamilySearchItemRead(PatentFamilyRead):
    linked_entities: list[PatentFamilyLinkedEntityRead]


class PatentLandscapeBucketRead(BaseModel):
    key: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=500)
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)


class PatentLandscapeRead(BaseModel):
    """Full-hit-set patent statistics computed by the database for the applied query.

    Buckets always cover the complete authorized result set, never the current page;
    missing values are reported as explicit `__missing__` buckets instead of being
    silently dropped.
    """

    total_families: int = Field(ge=0)
    legal_status: list[PatentLandscapeBucketRead] = Field(default_factory=list)
    top_applicants: list[PatentLandscapeBucketRead] = Field(default_factory=list)
    priority_year: list[PatentLandscapeBucketRead] = Field(default_factory=list)


class PatentFamilySearchResult(QueryResultMetadata):
    items: list[PatentFamilySearchItemRead]
    total: int
    limit: int
    offset: int
    sort_by: PatentSortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]]
    landscape: PatentLandscapeRead
    as_of: datetime
    warnings: list[str]


class DealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_id: str
    deal_type: str
    status: DealStatus
    direction: DealDirection
    direction_reference_jurisdiction: str | None
    announced_at: datetime | None
    terminated_at: datetime | None
    source_updated_at: datetime | None
    parties: list[dict[str, Any]]
    asset_entity_ids: list[str]
    territory: str | None
    upfront_amount: float | None
    total_potential_amount: float | None
    currency: str | None
    terms: dict[str, Any]
    source_document_id: str | None


class DealLinkedEntityRead(BaseModel):
    id: str
    name: str
    entity_type: EntityType


class DealPartyAssociationRead(DealLinkedEntityRead):
    role: DealPartyRole
    country_region: str | None
    organization_type: str | None


class DealAssetAssociationRead(DealLinkedEntityRead):
    development_phase_at_transaction: str | None
    current_development_phase: str | None
    current_phase_as_of: datetime | None


class DealRightRead(BaseModel):
    id: str
    holder_entity_id: str
    holder_name: str
    right_type: DealRightType
    territory: str
    exclusive: bool | None
    scope_description: str | None
    source_document_id: str | None


class DealSearchItemRead(DealRead):
    name: str
    party_entities: list[DealLinkedEntityRead]
    asset_entities: list[DealLinkedEntityRead]
    party_roles: list[DealPartyAssociationRead]
    asset_stages: list[DealAssetAssociationRead]
    rights: list[DealRightRead]


class DealLandscapeBucketRead(BaseModel):
    key: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=500)
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)


class DealLandscapeRead(BaseModel):
    total_deals: int = Field(ge=0)
    limit: DealAnalysisLimit
    deal_type: list[DealLandscapeBucketRead] = Field(default_factory=list)
    status: list[DealLandscapeBucketRead] = Field(default_factory=list)
    direction: list[DealLandscapeBucketRead] = Field(default_factory=list)
    territory: list[DealLandscapeBucketRead] = Field(default_factory=list)
    currency: list[DealLandscapeBucketRead] = Field(default_factory=list)
    asset_modality: list[DealLandscapeBucketRead] = Field(default_factory=list)
    transaction_phase: list[DealLandscapeBucketRead] = Field(default_factory=list)
    current_phase: list[DealLandscapeBucketRead] = Field(default_factory=list)
    party_country: list[DealLandscapeBucketRead] = Field(default_factory=list)
    rights_territory: list[DealLandscapeBucketRead] = Field(default_factory=list)


class DealSearchResult(QueryResultMetadata):
    items: list[DealSearchItemRead]
    total: int
    limit: int
    offset: int
    sort_by: DealSortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]]
    landscape: DealLandscapeRead
    as_of: datetime
    warnings: list[str]


class CompanyTimelineEventRead(BaseModel):
    id: str
    event_type: Literal["program_status", "deal_announced"]
    occurred_at: datetime
    title: str
    program: CompetitiveProgramRead | None = None
    deal: DealSearchItemRead | None = None

    @model_validator(mode="after")
    def validate_event_payload(self) -> CompanyTimelineEventRead:
        if (self.program is None) == (self.deal is None):
            raise ValueError("Company timeline event must contain exactly one domain record")
        if self.event_type == "program_status" and self.program is None:
            raise ValueError("Program status event must contain a program")
        if self.event_type == "deal_announced" and self.deal is None:
            raise ValueError("Deal announcement event must contain a deal")
        return self


class CompanyTimelineResult(BaseModel):
    company: EntityRead
    items: list[CompanyTimelineEventRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class CompanyDossierSummaryRead(BaseModel):
    program_count: int = Field(ge=0)
    drug_count: int = Field(ge=0)
    target_count: int = Field(ge=0)
    indication_count: int = Field(ge=0)
    deal_count: int = Field(ge=0)
    timeline_event_count: int = Field(ge=0)
    modalities: list[str] = Field(default_factory=list)
    phase_distribution: dict[str, int] = Field(default_factory=dict)
    highest_phase: DevelopmentPhase | None = None
    latest_activity_at: datetime | None = None


class DiseaseDossierSummaryRead(BaseModel):
    program_count: int = Field(ge=0)
    drug_count: int = Field(ge=0)
    target_count: int = Field(ge=0)
    organization_count: int = Field(ge=0)
    clinical_trial_count: int = Field(ge=0)
    patent_count: int = Field(ge=0)
    epidemiology_observation_count: int = Field(ge=0)
    patient_population_count: int = Field(ge=0)
    modalities: list[str] = Field(default_factory=list)
    phase_distribution: dict[str, int] = Field(default_factory=dict)
    highest_phase: DevelopmentPhase | None = None
    measures: list[str] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)
    latest_activity_at: datetime | None = None


class RegulatoryEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    subject_entity_id: str
    agency: str
    jurisdiction: str
    event_identifier: str
    application_number: str | None
    event_type: str
    status: str | None
    title: str
    decision_date: datetime | None
    designation_type: RegulatoryDesignationType | None
    label_change_type: RegulatoryLabelChangeType | None
    label_version: str | None
    label_effective_at: datetime | None
    approved_population: str | None
    line_of_therapy: str | None
    biomarker: str | None
    route_of_administration: str | None
    dosage_form: str | None
    has_boxed_warning: bool | None
    safety_signal_type: RegulatorySafetySignalType | None
    safety_term: str | None
    safety_severity: RegulatorySafetySeverity | None
    safety_status: RegulatorySafetyStatus | None
    safety_identified_at: datetime | None
    safety_confirmed_at: datetime | None
    safety_resolved_at: datetime | None
    affected_population: str | None
    risk_actions: list[str]
    source_updated_at: datetime | None
    indication_entity_id: str | None
    organization_entity_id: str | None
    details: dict[str, Any]
    source_document_id: str | None


class RegulatoryEventLinkedEntityRead(BaseModel):
    id: str
    name: str
    entity_type: EntityType


class RegulatoryEventSearchItemRead(RegulatoryEventRead):
    subject_entity: RegulatoryEventLinkedEntityRead
    indication_entity: RegulatoryEventLinkedEntityRead | None
    organization_entity: RegulatoryEventLinkedEntityRead | None


class RegulatoryLandscapeBucketRead(BaseModel):
    key: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=500)
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)


class RegulatoryLandscapeRead(BaseModel):
    """Full-hit-set regulatory statistics for the applied query; missing values are
    explicit `__missing__` buckets and counts never come from the current page."""

    total_events: int = Field(ge=0)
    event_type: list[RegulatoryLandscapeBucketRead] = Field(default_factory=list)
    agency: list[RegulatoryLandscapeBucketRead] = Field(default_factory=list)
    decision_year: list[RegulatoryLandscapeBucketRead] = Field(default_factory=list)


class RegulatoryEventSearchResult(QueryResultMetadata):
    items: list[RegulatoryEventSearchItemRead]
    total: int
    limit: int
    offset: int
    sort_by: RegulatorySortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]]
    landscape: RegulatoryLandscapeRead
    as_of: datetime
    warnings: list[str]


class EpidemiologyLinkedEntityRead(BaseModel):
    id: str
    name: str
    entity_type: EntityType


class PatientPopulationRead(BaseModel):
    id: str
    population_key: str
    name: str
    description: str | None
    attributes: dict[str, Any]
    disease_entities: list[EpidemiologyLinkedEntityRead]
    target_entities: list[EpidemiologyLinkedEntityRead]


class PatientPopulationOptionRead(BaseModel):
    id: str
    name: str
    count: int


class EpidemiologyObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    observation_identifier: str
    disease_entity_id: str
    patient_population_id: str | None
    measure: str
    value: float
    lower_bound: float | None
    upper_bound: float | None
    unit: str
    geography: str
    population_scope: str
    age_group: str | None
    sex: str | None
    period_start: datetime | None
    period_end: datetime | None
    sample_size: float | None
    methodology: str | None
    publisher_entity_id: str | None
    source_document_id: str | None


class EpidemiologyObservationSearchItemRead(EpidemiologyObservationRead):
    disease_entity: EpidemiologyLinkedEntityRead
    publisher_entity: EpidemiologyLinkedEntityRead | None
    patient_population: PatientPopulationRead | None


class EpidemiologyLandscapeBucketRead(BaseModel):
    key: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=500)
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)


class EpidemiologyLandscapeRead(BaseModel):
    """Full-hit-set epidemiology statistics; missing values are explicit buckets."""

    total_observations: int = Field(ge=0)
    measure: list[EpidemiologyLandscapeBucketRead] = Field(default_factory=list)
    geography: list[EpidemiologyLandscapeBucketRead] = Field(default_factory=list)
    population_scope: list[EpidemiologyLandscapeBucketRead] = Field(default_factory=list)


class EpidemiologyObservationSearchResult(QueryResultMetadata):
    items: list[EpidemiologyObservationSearchItemRead]
    total: int
    limit: int
    offset: int
    sort_by: EpidemiologySortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]]
    landscape: EpidemiologyLandscapeRead
    patient_populations: list[PatientPopulationOptionRead]
    as_of: datetime
    warnings: list[str]


class EpidemiologyTrendResult(BaseModel):
    disease: EpidemiologyLinkedEntityRead
    anchor_observation_id: str | None = None
    items: list[EpidemiologyObservationSearchItemRead]
    total: int
    truncated: bool
    as_of: datetime
    warnings: list[str]


class NewsEventLinkedEntityRead(BaseModel):
    id: str
    name: str
    entity_type: EntityType


class NewsEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    event_identifier: str
    event_type: str
    title: str
    summary: str | None
    published_at: datetime | None
    language: str | None
    publisher_entity_id: str | None
    related_entity_ids: list[str]
    canonical_url: str | None
    venue: str | None
    details: dict[str, Any]
    source_document_id: str | None


class NewsEventSearchItemRead(NewsEventRead):
    publisher_entity: NewsEventLinkedEntityRead | None
    related_entities: list[NewsEventLinkedEntityRead]


class NewsLandscapeBucketRead(BaseModel):
    key: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=500)
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)


class NewsLandscapeRead(BaseModel):
    """Full-hit-set news statistics; missing values are explicit buckets."""

    total_events: int = Field(ge=0)
    event_type: list[NewsLandscapeBucketRead] = Field(default_factory=list)
    venue: list[NewsLandscapeBucketRead] = Field(default_factory=list)
    published_year: list[NewsLandscapeBucketRead] = Field(default_factory=list)


class NewsEventSearchResult(QueryResultMetadata):
    items: list[NewsEventSearchItemRead]
    total: int
    limit: int
    offset: int
    sort_by: NewsSortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]]
    landscape: NewsLandscapeRead
    as_of: datetime
    warnings: list[str]


class EntityRelationshipRead(BaseModel):
    id: str
    predicate: str
    direction: Literal["outgoing", "incoming"]
    related_entity: EntityRead
    attributes: dict[str, Any]
    review_status: ReviewStatus
    valid_from: datetime | None
    valid_to: datetime | None


EntityDossierDomain = Literal[
    "relationships",
    "evidence",
    "activities",
    "programs",
    "clinical_trials",
    "patents",
    "deals",
    "regulatory_events",
    "news_events",
    "structures",
    "target_evidence",
]


class EntityDossierCoverageRead(BaseModel):
    domain: EntityDossierDomain
    total: int = Field(ge=0)
    returned: int = Field(ge=0)
    status: Literal["available", "not_observed", "truncated"]
    note: str


class TargetEvidenceRead(BaseModel):
    id: str
    source_system: str
    source_record_id: str
    target_entity_id: str
    target_name: str
    disease_entity_id: str | None = None
    disease_name: str | None = None
    evidence_type: Literal[
        "genetic_association",
        "expression",
        "functional",
        "translational",
        "biomarker",
        "safety",
    ]
    direction: Literal["supports", "opposes", "neutral", "unknown"]
    study_name: str | None = None
    population: str | None = None
    tissue: str | None = None
    variant: str | None = None
    effect_size: float | None = None
    effect_unit: str | None = None
    p_value: float | None = None
    sample_size: int | None = None
    summary: str
    observed_at: datetime | None = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    source_document_id: str | None = None


class EntityDossierResponse(BaseModel):
    entity: EntityRead
    relationships: list[EntityRelationshipRead]
    activities: list[BioactivityRead]
    programs: list[CompetitiveProgramRead]
    clinical_trials: list[ClinicalTrialSearchItemRead]
    patents: list[PatentFamilyRead]
    deals: list[DealSearchItemRead]
    regulatory_events: list[RegulatoryEventSearchItemRead]
    news_events: list[NewsEventSearchItemRead]
    structures: list[CompoundStructureRead]
    target_evidence: list[TargetEvidenceRead]
    coverage: list[EntityDossierCoverageRead]
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class CompanyDossierResponse(EntityDossierResponse):
    summary: CompanyDossierSummaryRead
    timeline: CompanyTimelineResult


class DiseaseDossierResponse(EntityDossierResponse):
    summary: DiseaseDossierSummaryRead
    epidemiology: EpidemiologyObservationSearchResult


class DrugDossierSummaryRead(BaseModel):
    program_count: int = Field(ge=0)
    target_count: int = Field(ge=0)
    indication_count: int = Field(ge=0)
    organization_count: int = Field(ge=0)
    modalities: list[str]
    highest_phase: DevelopmentPhase | None = None
    highest_global_phase: DevelopmentPhase | None = None
    highest_china_phase: DevelopmentPhase | None = None
    latest_status_date: datetime | None = None


class DrugDossierResponse(EntityDossierResponse):
    deals: list[DealSearchItemRead]
    summary: DrugDossierSummaryRead


class DrugProgramSearchResult(QueryResultMetadata):
    """A paged, human-readable view of one drug's complete development set."""

    items: list[CompetitiveProgramRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class DrugComparisonProfileRead(BaseModel):
    """Complete, server-computed development profile for one compared drug."""

    entity: EntityRead
    summary: DrugDossierSummaryRead
    target_names: list[str]
    indication_names: list[str]
    organization_names: list[str]
    program_status_counts: dict[str, int]
    as_of: datetime


class DrugComparisonResult(BaseModel):
    """Bounded batch response used by the human drug comparison workspace."""

    query_schema_version: Literal["pharma.drug.comparison.v1"] = "pharma.drug.comparison.v1"
    items: list[DrugComparisonProfileRead]
    as_of: datetime


class TargetProfileResponse(BaseModel):
    profile_id: str | None = None
    entity: EntityRead
    gene_symbol: str | None = None
    uniprot_accession: str | None = None
    organism: str | None = None
    target_class: str | None = None
    sequence: str | None = None
    function_summary: str | None = None
    activity_count: int
    program_count: int
    target_evidence_count: int = 0
    source_document_id: str | None = None
    as_of: datetime


class TargetDossierSummaryRead(BaseModel):
    """Server-computed target landscape counts over the complete authorized result set.

    Counts are never derived from the truncated record collections returned alongside
    them. Free-text source statuses are classified by an explicit versioned vocabulary
    and anything outside it is reported as unclassified instead of being silently
    bucketed.
    """

    program_count: int = Field(ge=0)
    phase_distribution: dict[str, int] = Field(default_factory=dict)
    highest_phase: DevelopmentPhase | None = None
    clinical_trial_count: int = Field(ge=0)
    recruiting_trial_count: int = Field(ge=0)
    unclassified_trial_status_count: int = Field(ge=0)
    patent_count: int = Field(ge=0)
    active_patent_count: int = Field(ge=0)
    unclassified_patent_status_count: int = Field(ge=0)
    regulatory_event_count: int = Field(ge=0)
    approval_event_count: int = Field(ge=0)
    status_vocabulary_version: str


class TargetDossierResponse(EntityDossierResponse):
    profile: TargetProfileResponse
    summary: TargetDossierSummaryRead


class _DataSourceRoutingRuleBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_term: str = Field(min_length=1, max_length=2000)
    max_records: int = Field(default=100, ge=1, le=1000)
    page_size: int = Field(default=100, ge=1, le=1000)

    def document(self) -> dict[str, Any]:
        return self.model_dump()


class PubMedDataSourceRoutingRule(_DataSourceRoutingRuleBase):
    include_abstract: bool


class ClinicalTrialsGovDataSourceRoutingRule(_DataSourceRoutingRuleBase):
    sort: Literal[
        "LastUpdatePostDate:asc",
        "LastUpdatePostDate:desc",
        "StudyFirstPostDate:asc",
        "StudyFirstPostDate:desc",
    ]


class ChemblDataSourceRoutingRule(BaseModel):
    """Routing rule retained for the public ChEMBL connector.

    ChEMBL sources were registered before PubMed and ClinicalTrials.gov routing
    rules became a tagged union. Keep the persisted target identifier explicit so
    existing sources remain readable and new registrations use the same contract.
    """

    model_config = ConfigDict(extra="forbid")

    target_chembl_id: str = Field(min_length=7, max_length=32)
    max_records: int = Field(default=100, ge=1, le=1000)
    page_size: int = Field(default=100, ge=1, le=100)

    def document(self) -> dict[str, Any]:
        return self.model_dump()

    @field_validator("target_chembl_id")
    @classmethod
    def normalize_target_chembl_id(cls, value: str) -> str:
        normalized = value.strip().upper()
        if re.fullmatch(r"CHEMBL[0-9]+", normalized) is None:
            raise ValueError("target_chembl_id must be a valid ChEMBL identifier")
        return normalized


DataSourceRoutingRule = (
    PubMedDataSourceRoutingRule | ClinicalTrialsGovDataSourceRoutingRule | ChemblDataSourceRoutingRule
)


class DataSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    source_type: DataSourceType = DataSourceType.FOLDER
    root_uri: str = Field(min_length=1, max_length=4000)
    credential_ref: str | None = Field(default=None, max_length=500)
    owner: str = Field(min_length=1, max_length=200)
    data_classification: Literal["public", "internal", "confidential", "restricted"] = "internal"
    authorization_scopes: list[str] = Field(min_length=1, max_length=100)
    authorization_valid_from: datetime = Field(default_factory=lambda: datetime.now(UTC))
    authorization_valid_until: datetime | None = None
    dataset_key: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,79}$")
    include_globs: list[str] = Field(default_factory=lambda: ["*", "**/*"], max_length=100)
    exclude_globs: list[str] = Field(default_factory=list, max_length=500)
    routing_rules: list[DataSourceRoutingRule] = Field(default_factory=list, max_length=1)
    stable_seconds: int = Field(default=30, ge=0, le=86_400)
    max_file_bytes: int = Field(default=1_073_741_824, gt=0, le=10_737_418_240)
    scan_interval_seconds: int = Field(default=300, ge=10, le=86_400)
    expected_freshness_seconds: int = Field(default=86_400, ge=60, le=31_536_000)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=100_000)

    @field_validator("name", "owner")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("credential_ref")
    @classmethod
    def validate_credential_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if "\x00" in stripped or "\n" in stripped or "\r" in stripped:
            raise ValueError("Credential reference contains invalid characters")
        return stripped

    @field_validator("authorization_scopes")
    @classmethod
    def validate_authorization_scopes(cls, value: list[str]) -> list[str]:
        normalized = sorted({scope.strip() for scope in value})
        if len(normalized) != len(value):
            raise ValueError("Authorization scopes must be unique")
        if any(not AUTHORIZATION_SCOPE_PATTERN.fullmatch(scope) for scope in normalized):
            raise ValueError("Authorization scope is invalid")
        return normalized

    @field_validator("authorization_valid_from", "authorization_valid_until")
    @classmethod
    def validate_authorization_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Authorization datetimes must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_authorization_window(self) -> DataSourceCreate:
        if (
            self.authorization_valid_until is not None
            and self.authorization_valid_until <= self.authorization_valid_from
        ):
            raise ValueError("Authorization end must be later than its effective time")
        return self


class DataSourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    root_uri: str | None = Field(default=None, min_length=1, max_length=4000)
    credential_ref: str | None = Field(default=None, max_length=500)
    owner: str | None = Field(default=None, min_length=1, max_length=200)
    data_classification: Literal["public", "internal", "confidential", "restricted"] | None = None
    authorization_scopes: list[str] | None = Field(default=None, min_length=1, max_length=100)
    authorization_valid_from: datetime | None = None
    authorization_valid_until: datetime | None = None
    dataset_key: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_-]{1,79}$")
    include_globs: list[str] | None = Field(default=None, max_length=100)
    exclude_globs: list[str] | None = Field(default=None, max_length=500)
    routing_rules: list[DataSourceRoutingRule] = Field(default_factory=list, max_length=1)
    stable_seconds: int | None = Field(default=None, ge=0, le=86_400)
    max_file_bytes: int | None = Field(default=None, gt=0, le=10_737_418_240)
    scan_interval_seconds: int | None = Field(default=None, ge=10, le=86_400)
    expected_freshness_seconds: int | None = Field(default=None, ge=60, le=31_536_000)
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=100_000)

    @field_validator("name", "owner")
    @classmethod
    def strip_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped

    @field_validator("credential_ref")
    @classmethod
    def validate_optional_credential_ref(cls, value: str | None) -> str | None:
        return DataSourceCreate.validate_credential_ref(value)

    @field_validator("authorization_scopes")
    @classmethod
    def validate_optional_authorization_scopes(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else DataSourceCreate.validate_authorization_scopes(value)

    @field_validator("authorization_valid_from", "authorization_valid_until")
    @classmethod
    def validate_optional_authorization_datetime(cls, value: datetime | None) -> datetime | None:
        return DataSourceCreate.validate_authorization_datetime(value)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> DataSourceUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one data-source field must be supplied")
        if "authorization_valid_from" in self.model_fields_set and self.authorization_valid_from is None:
            raise ValueError("Authorization effective time cannot be null")
        if (
            self.authorization_valid_from is not None
            and self.authorization_valid_until is not None
            and self.authorization_valid_until <= self.authorization_valid_from
        ):
            raise ValueError("Authorization end must be later than its effective time")
        return self


class DataSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    source_type: DataSourceType
    root_uri: str
    credential_configured: bool
    owner: str
    data_classification: Literal["public", "internal", "confidential", "restricted"]
    authorization_scopes: list[str]
    authorization_valid_from: datetime
    authorization_valid_until: datetime | None
    dataset_key: str
    include_globs: list[str]
    exclude_globs: list[str]
    routing_rules: list[DataSourceRoutingRule]
    stable_seconds: int
    max_file_bytes: int
    scan_interval_seconds: int
    expected_freshness_seconds: int
    rate_limit_per_minute: int
    config_version: int
    state: DataSourceState
    last_scanned_at: datetime | None
    last_success_at: datetime | None
    unavailable_since: datetime | None
    consecutive_failures: int
    last_error: str | None
    last_cursor_at: datetime | None


class DataSourceDatasetRead(BaseModel):
    dataset_key: str
    display_name: str
    active: bool
    license_id: str
    license_policy_version: str
    permitted_channels: list[Literal["web", "mcp"]]
    license_current: bool
    attribution: str


class DataSourceReadinessCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    status: Literal["pass", "warn", "fail"]
    message: str


class DataSourceReadinessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    source_id: str
    configuration_ready: bool
    operational_status: Literal["blocked", "disabled", "paused", "unavailable", "pending", "stale", "ready"]
    connector_id: str | None
    incremental: bool
    replayable: bool
    delivery_channels: list[Literal["web", "mcp"]]
    cursor_present: bool
    last_cursor_at: datetime | None
    freshness_age_seconds: int | None
    checks: list[DataSourceReadinessCheckRead]


class IngestionCapabilitiesRead(BaseModel):
    automatic_scheduling_enabled: bool
    durable_workflows_enabled: bool
    isolated_parser_enabled: bool
    malware_scanning_enabled: bool
    ai_governance_enabled: bool
    ai_model_configured: bool
    ai_model: str | None
    ai_auto_publish_threshold: float
    allowed_folder_roots: list[str]
    parseable_extensions: list[str]
    asset_only_extensions: list[str]


class DataSourceStateUpdate(BaseModel):
    state: Literal[DataSourceState.ACTIVE, DataSourceState.PAUSED, DataSourceState.DISABLED]


class IngestionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    data_source_id: str
    workflow_id: str
    temporal_workflow_id: str | None
    temporal_run_id: str | None
    state: RunState
    effective_state: RunState
    started_at: datetime | None
    completed_at: datetime | None
    heartbeat_at: datetime | None
    counters: dict[str, int]
    result: dict[str, Any]
    error_summary: str | None
    cancel_requested_at: datetime | None
    cancelable: bool
    progress_percent: int = Field(ge=0, le=100)
    total_versions: int = Field(ge=0)
    completed_versions: int = Field(ge=0)
    stages: list[IngestionRunStageRead]
    created_at: datetime


class IngestionRunStageRead(BaseModel):
    stage: Literal["discovery", "snapshot", "malware_scan", "parse", "retrieval", "governance"]
    status: Literal["not_started", "running", "succeeded", "failed", "skipped", "canceled"]
    completed_items: int = Field(ge=0)
    failed_items: int = Field(ge=0)
    total_items: int = Field(ge=0)


class IngestionRunReplayRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    expected_state: Literal[RunState.FAILED, RunState.PARTIAL, RunState.CANCELED]
    reason: str = Field(min_length=3, max_length=500)


class IngestionRunCancelRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    expected_state: Literal[RunState.RUNNING]
    reason: str = Field(min_length=3, max_length=500)


class IngestionRunCancelAcceptedRead(BaseModel):
    run_id: str
    workflow_id: str
    temporal_workflow_id: str
    temporal_run_id: str
    status: Literal["cancel_requested"]


class IngestionScanAcceptedRead(BaseModel):
    workflow_id: str
    ingestion_run_id: str
    status: Literal["accepted"]
    replayed_from_run_id: str | None = None


class IngestionFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    ingestion_run_id: str
    source_path: str
    stage: str
    code: str
    message: str
    retryable: bool
    occurred_at: datetime


class SourceAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    data_source_id: str
    logical_path: str
    source_uri: str
    file_name: str
    extension: str
    media_type: str | None
    processing_mode: str
    state: SourceAssetState
    current_version_id: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    missing_since: datetime | None


class SourceVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_asset_id: str
    version_number: int
    content_sha256: str
    size_bytes: int
    source_modified_at: datetime | None
    discovered_at: datetime
    state: SourceVersionState
    snapshot_status: StageStatus
    malware_scan_status: StageStatus
    parse_status: StageStatus
    retrieval_status: StageStatus
    governance_status: StageStatus
    malware_scanner: str | None
    malware_signature_version: str | None
    malware_scanned_at: datetime | None
    extracted_text_sha256: str | None
    parser_name: str | None
    parser_version: str | None
    metadata_json: dict[str, Any]
    error_code: str | None
    error_message: str | None
    quarantine_status: QuarantineStatus
    quarantine_version: int = Field(ge=0)
    quarantine_updated_at: datetime | None
    replayable_stages: list[Literal["malware_scan", "parse", "governance", "retrieval"]] = Field(default_factory=list)


class SourceAssetDetailRead(SourceAssetRead):
    versions: list[SourceVersionRead]


class SourceAssetPageRead(BaseModel):
    items: list[SourceAssetRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class SourceVersionPreviewRead(BaseModel):
    source_version_id: str
    text: str
    truncated: bool
    returned_chars: int
    extracted_text_sha256: str


class SourceVersionReplayRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    expected_state: SourceVersionState
    expected_error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{2,119}$")
    from_stage: Literal["malware_scan", "parse", "governance", "retrieval"] = "malware_scan"
    reason: str = Field(min_length=3, max_length=500)


class SourceVersionReplayAcceptedRead(BaseModel):
    workflow_id: str
    source_version_id: str
    from_stage: Literal["malware_scan", "parse", "governance", "retrieval"]
    status: Literal["accepted"]


class SourceVersionQuarantineDecisionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    expected_version: int = Field(ge=1)
    action: Literal["hold", "reject", "rescan"]
    reason: str = Field(min_length=3, max_length=500)


class SourceVersionQuarantineDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_version_id: str
    action: str
    expected_version: int
    resulting_version: int
    previous_status: QuarantineStatus
    resulting_status: QuarantineStatus
    reason: str
    actor_type: str
    actor_id: str
    workflow_id: str | None
    details: dict[str, Any]
    created_at: datetime


class SourceVersionQuarantineCaseRead(BaseModel):
    source_version_id: str
    source_asset_id: str
    file_name: str
    logical_path: str
    quarantine_status: QuarantineStatus
    quarantine_version: int = Field(ge=1)
    threat_name: str | None
    error_code: str | None
    error_message: str | None
    updated_at: datetime
    decisions: list[SourceVersionQuarantineDecisionRead] = Field(default_factory=list)


class SourceVersionQuarantineDecisionAcceptedRead(BaseModel):
    decision_id: str
    source_version_id: str
    action: Literal["hold", "reject", "rescan"]
    quarantine_status: QuarantineStatus
    quarantine_version: int = Field(ge=1)
    workflow_id: str | None
    status: Literal["accepted"]


class StagedFactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    fact_kind: str
    raw_payload: dict[str, Any]
    payload: dict[str, Any]
    normalization_version: str | None
    source_document_id: str | None
    source_locator: str | None
    source_quote: str
    confidence: float
    status: GovernanceStatus
    quality_findings: list[dict[str, Any]]
    conflict_with_ids: list[str]
    created_at: datetime


class GovernanceRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_version_id: str
    source_asset_id: str
    source_logical_path: str
    source_file_name: str
    source_content_sha256: str
    schema_name: str
    schema_version: str
    model_provider: str
    model_name: str
    prompt_sha256: str
    policy_sha256: str
    input_sha256: str
    policy_current: bool
    status: RunState
    validation_errors: list[dict[str, Any]]
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: Decimal | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class GovernanceRunPageRead(BaseModel):
    items: list[GovernanceRunRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    current_policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReviewDecision(BaseModel):
    decision: Literal["approve", "reject"]
    notes: str | None = Field(default=None, max_length=4000)


class KnowledgePageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    page_key: str
    page_type: str
    title: str
    subject_entity_id: str | None
    status: KnowledgePageStatus
    current_version_id: str | None
    updated_at: datetime


class KnowledgePageDetail(KnowledgePageSummary):
    version_number: int
    compiler_version: str
    content_json: dict[str, Any]
    rendered_markdown: str
    content_sha256: str
    source_snapshot_at: datetime


class PublicKnowledgePageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    page_type: str
    title: str
    updated_at: datetime


class PublicKnowledgePageDetail(PublicKnowledgePageSummary):
    version_number: int
    rendered_markdown: str
    source_snapshot_at: datetime


class KnowledgePredicateCoverageRead(BaseModel):
    predicate: str
    fact_count: int
    cited_fact_count: int


class KnowledgePageCoverageRead(BaseModel):
    page_id: str
    version_id: str
    version_number: int
    fact_count: int
    cited_fact_count: int
    uncited_fact_count: int
    source_count: int
    linked_entity_count: int
    predicates: list[KnowledgePredicateCoverageRead]
    source_snapshot_at: datetime


class PublicKnowledgePageCoverageRead(BaseModel):
    version_number: int
    fact_count: int
    cited_fact_count: int
    uncited_fact_count: int
    source_count: int
    linked_entity_count: int
    predicates: list[KnowledgePredicateCoverageRead]
    source_snapshot_at: datetime


class KnowledgeVersionSummaryRead(BaseModel):
    version_id: str
    version_number: int
    compiler_version: str
    content_sha256: str
    source_snapshot_at: datetime
    created_at: datetime
    created_by_run_id: str | None
    is_current: bool
    previous_version_number: int | None
    fact_count: int
    source_count: int
    added_fact_count: int
    removed_fact_count: int
    added_source_count: int
    removed_source_count: int


class PublicKnowledgeVersionSummaryRead(BaseModel):
    version_number: int
    source_snapshot_at: datetime
    is_current: bool
    previous_version_number: int | None
    added_fact_count: int
    removed_fact_count: int
    added_source_count: int
    removed_source_count: int


class KnowledgeFactChangeRead(BaseModel):
    change_key: str
    fact_id: str | None
    predicate: str
    object_entity_name: str | None
    value: Any
    confidence: float | None
    citation_number: int | None
    source_document_id: str | None
    source_title: str | None
    source_locator: str | None


class KnowledgeSourceChangeRead(BaseModel):
    source_document_id: str
    title: str
    source_uri: str | None
    locator: str | None


class PublicKnowledgeFactChangeRead(BaseModel):
    change_key: str
    predicate: str
    object_entity_name: str | None
    value: Any
    source_title: str | None
    source_locator: str | None


class PublicKnowledgeSourceChangeRead(BaseModel):
    title: str
    locator: str | None


class KnowledgeVersionDiffRead(BaseModel):
    page_id: str
    from_version_number: int | None
    to_version_number: int
    added_fact_count: int
    removed_fact_count: int
    added_source_count: int
    removed_source_count: int
    added_facts: list[KnowledgeFactChangeRead]
    removed_facts: list[KnowledgeFactChangeRead]
    added_sources: list[KnowledgeSourceChangeRead]
    removed_sources: list[KnowledgeSourceChangeRead]
    truncated: bool


class PublicKnowledgeVersionDiffRead(BaseModel):
    from_version_number: int | None
    to_version_number: int
    added_fact_count: int
    removed_fact_count: int
    added_source_count: int
    removed_source_count: int
    added_facts: list[PublicKnowledgeFactChangeRead]
    removed_facts: list[PublicKnowledgeFactChangeRead]
    added_sources: list[PublicKnowledgeSourceChangeRead]
    removed_sources: list[PublicKnowledgeSourceChangeRead]
    truncated: bool


class CommercialEntitlementRead(BaseModel):
    key: str
    max_result_rows: int
    daily_unit_limit: str | None
    max_page_depth: int
    daily_unique_record_limit: int | None
    max_response_bytes: int
    data_domains: list[str]


class CommercialAccessRead(BaseModel):
    client_id: str
    subscription_id: str
    status: str
    available_units: str
    consumed_units: str
    reserved_units: str
    entitlements: list[CommercialEntitlementRead]
    as_of: datetime


class CommercialEstimateRequest(BaseModel):
    billing_class: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    requested_result_limit: int = Field(gt=0, le=5000)
    requested_compute_units: Decimal = Field(default=Decimal("0"), ge=0, max_digits=28, decimal_places=8)


class CommercialEstimateRead(BaseModel):
    billing_class: str
    entitlement_key: str
    requested_result_limit: int
    requested_compute_units: str
    estimated_units_before_response_bytes: str
    base_units: str
    per_result_units: str
    per_kib_units: str
    per_compute_unit: str
    maximum_licensed_result_rows: int
    available_units: str
    rate_card_key: str
    rate_card_revision: int
    currency: str
    as_of: datetime


class CommercialUsageSummaryRead(BaseModel):
    client_id: str
    subscription_id: str
    rate_card_key: str
    rate_card_revision: int
    currency: str
    period_start: datetime
    as_of: datetime
    settlement_count: int
    charged_units: str
    result_count: int
    response_bytes: int
    active_reservations: int
    granted_units: str
    consumed_units: str
    reserved_units: str
    available_units: str
    latest_statement_id: str | None
    latest_statement_period_end: datetime | None


class CommercialDailyUsageRead(BaseModel):
    settlement_count: int
    result_count: int
    unique_record_count: int
    new_unique_record_count: int
    response_bytes: int


class CommercialSubscriptionOverviewRead(BaseModel):
    subscription_id: str
    subscription_key: str
    status: str
    client_key: str
    client_name: str
    billing_account_key: str
    billing_account_name: str
    rate_card_key: str
    rate_card_revision: int
    starts_at: datetime
    ends_at: datetime | None
    granted_units: str
    consumed_units: str
    reserved_units: str
    available_units: str
    active_reservations: int
    daily_unique_records: int
    daily_usage: CommercialDailyUsageRead
    entitlements: list[CommercialEntitlementRead]


class CommercialOverviewRead(BaseModel):
    as_of: datetime
    period_start: datetime
    open_risk_count: int = Field(ge=0)
    subscriptions: list[CommercialSubscriptionOverviewRead]


class CommercialUsageAdjustmentCreate(BaseModel):
    subscription_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")
    adjustment_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")
    units_delta: Decimal = Field(max_digits=28, decimal_places=8)
    reason: str = Field(min_length=1, max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommercialReversalCreate(BaseModel):
    adjustment_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")
    reason: str = Field(min_length=1, max_length=1000)


class CommercialAdjustmentRead(BaseModel):
    id: str
    subscription_id: str
    adjustment_key: str
    adjustment_kind: str
    reverses_adjustment_id: str | None
    reverses_settlement_id: str | None
    units_delta: str
    reason: str
    request_id: str
    created_by: str
    created_at: datetime


class CommercialExpirationRequest(BaseModel):
    limit: int = Field(default=1000, ge=1, le=10_000)


class CommercialExpirationRead(BaseModel):
    expired_reservations: int
    released_units: str
    completed_at: datetime


class CommercialReconciliationCreate(BaseModel):
    subscription_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,119}$")
    run_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")


class CommercialReconciliationRead(BaseModel):
    id: str
    subscription_id: str
    run_key: str
    status: str
    issue_count: int
    snapshot_granted_units: str
    snapshot_reserved_units: str
    snapshot_consumed_units: str
    ledger_granted_units: str
    ledger_reserved_units: str
    ledger_consumed_units: str
    source_granted_units: str
    source_reserved_units: str
    source_consumed_units: str
    issues: list[dict[str, Any]]
    requested_by: str
    request_id: str
    started_at: datetime
    completed_at: datetime


class BillingStatementCreate(BaseModel):
    subscription_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,119}$")
    statement_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")
    period_start: datetime
    period_end: datetime
    revision: int = Field(default=1, ge=1)


class BillingStatementRead(BaseModel):
    id: str
    subscription_id: str
    billing_account_id: str
    statement_key: str
    revision: int
    period_start: datetime
    period_end: datetime
    settlement_units: str
    adjustment_units: str
    net_consumed_units: str
    settlement_count: int
    adjustment_count: int
    result_count: int
    response_bytes: int
    manifest_sha256: str
    signature_key_id: str
    manifest_signature: str
    payload: dict[str, Any]
    generated_by: str
    request_id: str
    generated_at: datetime


class BillingAccountRead(BaseModel):
    id: str
    account_key: str
    display_name: str
    currency: str
    status: Literal["active", "suspended", "closed"]
    mapping_configured: bool
    external_customer_reference_masked: str | None
    statement_count: int
    unresolved_statement_count: int
    invoice_count: int
    updated_at: datetime


class BillingCustomerMappingUpdate(BaseModel):
    external_customer_reference: str = Field(
        min_length=1,
        max_length=500,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,499}$",
    )
    reason: str = Field(min_length=3, max_length=500)


class BillingDeliveryRead(BaseModel):
    delivery_id: str | None
    event_id: str
    statement_id: str
    statement_key: str
    billing_account_id: str
    billing_account_key: str
    billing_account_name: str
    state: Literal["pending", "processing", "retry", "succeeded", "dead"]
    attempts: int
    available_at: datetime
    lease_expires_at: datetime | None
    processed_at: datetime | None
    last_error: str | None
    invoice_provider: str | None
    external_invoice_id: str | None
    invoice_status: str | None
    created_at: datetime


class BillingDeliveryReplayRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class BillingDisputeCreate(BaseModel):
    dispute_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,119}$")
    statement_id: str = Field(min_length=1, max_length=36)
    invoice_reference_id: str | None = Field(default=None, min_length=1, max_length=36)
    category: Literal["usage", "pricing", "duplicate", "authorization", "service", "other"]
    disputed_units: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=4000)


class BillingDisputeTransition(BaseModel):
    operation_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,119}$")
    expected_version: int = Field(ge=1)
    action: Literal["investigate", "resolve_credit", "resolve_no_credit", "reject", "cancel"]
    notes: str = Field(min_length=3, max_length=4000)
    assigned_to: str | None = Field(default=None, min_length=1, max_length=500)
    adjustment_key: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")
    credit_units: Decimal | None = Field(default=None, gt=0, max_digits=28, decimal_places=8)

    @model_validator(mode="after")
    def validate_credit_fields(self) -> BillingDisputeTransition:
        if self.action == "resolve_credit":
            if self.adjustment_key is None or self.credit_units is None:
                raise ValueError("Credit resolution requires adjustment_key and credit_units")
        elif self.adjustment_key is not None or self.credit_units is not None:
            raise ValueError("Adjustment fields are only accepted for credit resolution")
        return self


class BillingDisputeRead(BaseModel):
    id: str
    dispute_key: str
    billing_account_id: str
    billing_account_key: str
    billing_account_name: str
    subscription_id: str
    statement_id: str
    statement_key: str
    invoice_reference_id: str | None
    external_invoice_id: str | None
    status: Literal["open", "investigating", "resolved", "rejected", "cancelled"]
    category: Literal["usage", "pricing", "duplicate", "authorization", "service", "other"]
    disputed_units: str
    subject: str
    description: str
    opened_by: str
    opened_at: datetime
    assigned_to: str | None
    due_at: datetime
    overdue: bool
    resolution_code: str | None
    resolution_notes: str
    resolved_by: str | None
    resolved_at: datetime | None
    resolution_adjustment_key: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class CommercialReserveRequest(BaseModel):
    billing_class: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    request_arguments: dict[str, Any]
    requested_result_limit: int = Field(gt=0, le=5000)
    max_billable_units: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    requested_compute_units: Decimal = Field(default=Decimal("0"), ge=0, max_digits=28, decimal_places=8)


class CommercialSettlementRequest(BaseModel):
    result_count: int = Field(ge=0, le=5000)
    result: dict[str, Any] | list[Any]
    metrics: dict[str, Any] = Field(default_factory=dict)


class CommercialReleaseRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class CommercialSettlementRead(BaseModel):
    settlement_id: str
    usage_event_id: str
    charged_units: str
    result_count: int
    unique_record_count: int
    new_unique_record_count: int
    response_bytes: int
    price_breakdown: dict[str, Any]
    result: dict[str, Any] | list[Any]
    created_at: datetime


class CommercialReservationRead(BaseModel):
    reservation_id: str
    state: UsageReservationState
    billing_class: str
    estimated_units: str
    reserved_units: str
    requested_compute_units: str
    lease_expires_at: datetime
    page_depth: int
    replayed: bool
    settlement: CommercialSettlementRead | None = None


class DataExportCreate(BaseModel):
    dataset: Literal[
        "entities",
        "structures",
        "bioactivities",
        "competitive_programs",
        "clinical_trials",
        "patents",
        "deals",
        "regulatory_events",
        "fact_provenance",
    ]
    export_format: Literal["jsonl", "csv"] = "jsonl"
    filters: dict[str, Any] = Field(default_factory=dict)
    fields: list[str] = Field(default_factory=list, max_length=50)
    max_records: int = Field(default=1000, ge=1, le=5000)
    max_billable_units: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


class DataExportRead(BaseModel):
    id: str
    dataset: str
    format: str
    fields: list[str]
    filters: dict[str, Any]
    max_records: int
    license_policy_version: str
    license_policy_sha256: str
    license_attribution: str
    record_count: int
    state: str
    approval_required: bool
    approved_by: str | None
    approved_at: datetime | None
    artifact_bytes: int
    artifact_sha256: str | None
    manifest_sha256: str | None
    manifest_signature: str | None
    manifest_key_id: str | None
    failure_code: str | None
    failure_message: str | None
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None


class DataExportChunkRead(BaseModel):
    items: list[dict[str, Any]]
    count: int
    next_cursor: str | None
    manifest: dict[str, Any]


class DataRetentionPolicyUpdate(BaseModel):
    retention_seconds: int = Field(ge=300, le=315_360_000)
    legal_basis: str = Field(min_length=3, max_length=500)
    geographic_scope: list[str] = Field(default_factory=list, max_length=50)
    active: bool = True


class DataRetentionPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    data_class: Literal["commercial_export_artifact", "source_asset_snapshot"]
    policy_version: int
    retention_seconds: int
    legal_basis: str
    geographic_scope: list[str]
    active: bool
    configured_by_user_id: str
    created_at: datetime
    updated_at: datetime


class LegalHoldCreate(BaseModel):
    scope_type: Literal["tenant", "billing_account", "data_export_job", "data_source", "source_asset"]
    scope_id: str | None = Field(default=None, max_length=36)
    matter_reference: str = Field(min_length=3, max_length=200)
    reason: str = Field(min_length=3, max_length=2000)


class LegalHoldRelease(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class LegalHoldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    scope_type: str
    scope_id: str | None
    matter_reference: str
    reason: str
    status: Literal["active", "released"]
    placed_by_user_id: str
    placed_at: datetime
    released_by_user_id: str | None
    released_at: datetime | None
    release_reason: str | None


class DataLifecyclePurgeRequest(BaseModel):
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    reason: str = Field(min_length=3, max_length=2000)


class DataLifecycleEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    data_class: str
    target_type: str
    target_id: str
    action: Literal["purge", "blocked", "reauthorize"]
    outcome: Literal["succeeded", "blocked"]
    idempotency_key: str
    policy_id: str
    policy_version: int
    legal_hold_ids: list[str]
    actor_user_id: str
    reason: str
    details: dict[str, Any]
    created_at: datetime


class DataLifecyclePurgeRead(BaseModel):
    event: DataLifecycleEventRead
    replayed: bool


class SourceAssetImpactRead(BaseModel):
    id: str
    data_source_id: str
    logical_path: str
    file_name: str
    state: str
    missing_since: datetime | None
    retention_eligible: bool
    version_count: int
    raw_object_count: int
    extracted_object_count: int
    extraction_run_count: int
    staged_fact_count: int
    published_fact_count: int
    evidence_claim_count: int
    knowledge_citation_count: int
    retrieval_projection_count: int
    shared_document_count: int
    other_document_reference_count: int
    blockers: list[str]


class DeletedSourceAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    data_source_id: str
    logical_path: str
    file_name: str
    state: Literal["deleted"]
    updated_at: datetime


class CommercialClientSubjectRead(BaseModel):
    actor_type: str
    subject_id: str
    active: bool


class CommercialClientRead(BaseModel):
    id: str
    client_key: str
    display_name: str
    active: bool
    subjects: list[CommercialClientSubjectRead]
    subscription_key: str | None
    subscription_status: str | None
    billing_account_key: str | None
    available_units: str | None
    active_reservations: int
    denial_count_24h: int
    last_policy_event_at: datetime | None
    created_at: datetime


class CommercialClientStatusUpdate(BaseModel):
    active: bool
    reason: str = Field(min_length=3, max_length=500)


class CommercialRiskEventRead(BaseModel):
    id: str
    client_id: str
    client_key: str
    client_name: str
    actor_type: str
    subject_id: str
    entitlement_key: str
    phase: str
    reason_code: str
    query_sha256: str
    page_depth: int
    requested_records: int
    existing_unique_records: int
    projected_unique_records: int
    request_id: str
    details: dict[str, Any]
    occurred_at: datetime
    case_status: Literal["open", "acknowledged", "resolved", "dismissed"]
    case_notes: str
    reviewed_by: str | None
    reviewed_at: datetime | None


class CommercialRiskEventPageRead(BaseModel):
    items: list[CommercialRiskEventRead]
    total_items: int = Field(ge=0)
    next_cursor: str | None


class CommercialRiskReview(BaseModel):
    status: Literal["acknowledged", "resolved", "dismissed"]
    notes: str = Field(default="", max_length=2000)
