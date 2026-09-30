from __future__ import annotations

import hashlib
import logging
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, cast, overload
from urllib.parse import urlsplit

import structlog
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from opentelemetry import trace
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

import pharma_intel.object_store as object_store_module
from pharma_intel import __version__
from pharma_intel.api_key_lifecycle import (
    API_KEY_MAX_TTL,
    API_KEY_MIN_TTL,
    MANAGED_API_KEY_SCOPES,
    ApiKeyLifecycleError,
    ApiKeyLifecycleNotFound,
    ApiKeyLifecycleService,
    ApiKeyView,
)
from pharma_intel.chemistry import (
    ChemistryBackendUnavailable,
    ChemistrySearchResult,
    ChemistryService,
    ChemistryValidationError,
)
from pharma_intel.commercial.accounting import (
    BillingStatementCommand,
    CommercialAccountingConflict,
    CommercialAccountingService,
    CommercialBalanceViolation,
    ReversalCommand,
    UsageAdjustmentCommand,
)
from pharma_intel.commercial.billing import BillingStatementSigner
from pharma_intel.commercial.billing_operations import BillingOperationsService
from pharma_intel.commercial.cursor import SignedCursorCodec
from pharma_intel.commercial.disputes import (
    BillingDisputeConflict,
    BillingDisputeNotFound,
    BillingDisputeService,
    CreateBillingDisputeCommand,
    TransitionBillingDisputeCommand,
)
from pharma_intel.commercial.exports import (
    CommercialExportService,
    CreateExportCommand,
    ExportStateConflict,
    ExportValidationError,
    build_export_service,
    export_job_view,
)
from pharma_intel.commercial.operations import (
    CommercialOperationsConflict,
    CommercialOperationsNotFound,
    CommercialOperationsService,
)
from pharma_intel.commercial.query import commercial_overview
from pharma_intel.commercial.risk_cursor import RiskCursorCodec, RiskCursorError
from pharma_intel.commercial.service import (
    CommercialAccessDenied,
    CommercialError,
    CommercialInvariantViolation,
    CommercialNotConfigured,
    CommercialUsageService,
    IdempotencyConflict,
    InsufficientCredits,
    ReservationConflict,
    ReservationExpired,
    ReservationOutcome,
    ReserveCommand,
    SettleCommand,
    SettlementLimitExceeded,
    SettlementOutcome,
)
from pharma_intel.comparison.exports import (
    WorkspaceComparisonExportService,
    WorkspaceExportConflict,
    WorkspaceExportDenied,
    WorkspaceExportNotConfigured,
)
from pharma_intel.comparison.service import (
    ComparisonSetConflict,
    ComparisonSetLimitExceeded,
    ComparisonSetNotFound,
    ComparisonSetService,
    ComparisonSetView,
)
from pharma_intel.config import get_settings
from pharma_intel.dataset_repository import (
    DatasetAccessDenied,
    DatasetRepository,
    DatasetSelectionError,
    ResolvedDataset,
)
from pharma_intel.db import get_session, get_session_factory, set_tenant_context
from pharma_intel.dossier import dossier_result_capacity
from pharma_intel.enterprise.admin import (
    AuditCursorCodec,
    CreateGroupCommand,
    CreateUserCommand,
    EnterpriseAdminConflict,
    EnterpriseAdminNotFound,
    EnterpriseAdminService,
    GroupView,
    UpdateDatasetStatusCommand,
    UpdateGroupCommand,
    UpdateGroupMembersCommand,
    UpdateUserRoleCommand,
    UpdateUserStatusCommand,
)
from pharma_intel.enterprise.llm_providers import (
    CreateLLMProviderCommand,
    LLMProviderCatalogService,
    LLMProviderConflict,
    LLMProviderError,
    LLMProviderNotFound,
    UpdateLLMProviderCommand,
)
from pharma_intel.governance.lifecycle import (
    DataLifecycleService,
    LifecycleConflict,
    LifecycleError,
    SourceAssetImpact,
)
from pharma_intel.governance.publication import GovernancePublicationService, PublicationError
from pharma_intel.governance.service import GovernanceError, GovernanceService, governance_policy_sha256
from pharma_intel.human_oidc import (
    OIDC_TRANSACTION_COOKIE,
    OidcAuthenticationError,
    create_oidc_authorization,
    exchange_oidc_code,
    get_oidc_id_token_verifier,
    read_oidc_transaction,
    resolve_oidc_user,
)
from pharma_intel.identity import EntityIdentityService, IdentityError, resolution_case_view, supported_namespaces
from pharma_intel.ingest.connectors import SourceConnectorRegistry
from pharma_intel.ingest.contracts import ProcessInput, ScanInput
from pharma_intel.ingest.quarantine import (
    QuarantineTransitionError,
    apply_operator_decision,
    record_rescan_failure,
)
from pharma_intel.ingest.readiness import SourceReadinessService
from pharma_intel.ingest.replay import replayable_source_version_stages
from pharma_intel.ingest.run_read_model import IngestionRunReadService
from pharma_intel.ingest.scanner import ASSET_ONLY_EXTENSIONS, PARSEABLE_EXTENSIONS
from pharma_intel.ingest.workflows import DataSourceIngestionWorkflow, SourceVersionReprocessWorkflow
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.knowledge.compiler import KnowledgeCompiler
from pharma_intel.knowledge.public import public_knowledge_markdown
from pharma_intel.knowledge.read_model import (
    KnowledgePageNotFound,
    KnowledgeReadService,
    KnowledgeVersionNotFound,
)
from pharma_intel.licensing import DeliveryChannel, EvidenceLicensePolicy, apply_evidence_license
from pharma_intel.models import (
    AuditEvent,
    BillingAdjustment,
    BillingPeriodStatement,
    CommercialReconciliationRun,
    DataExportJob,
    DataQualityIssue,
    DataSource,
    DataSourceState,
    DataSourceType,
    DealDirection,
    DealPartyRole,
    DealRightType,
    DealStatus,
    DevelopmentPhase,
    Entity,
    EntityType,
    EvidenceClaim,
    ExtractionRun,
    GovernanceStatus,
    IngestionFinding,
    IngestionRun,
    IngestionRunOperation,
    KnowledgePage,
    KnowledgePageStatus,
    KnowledgePageVersion,
    QuarantineStatus,
    RegulatoryDesignationType,
    RegulatoryLabelChangeType,
    RegulatorySafetySeverity,
    RegulatorySafetySignalType,
    RegulatorySafetyStatus,
    ResolutionStatus,
    ReviewStatus,
    ReviewTask,
    RunState,
    SourceAsset,
    SourceAssetState,
    SourceVersion,
    SourceVersionOperation,
    SourceVersionQuarantineDecision,
    StagedFact,
    Tenant,
    TenantDataset,
    TrialEntityRole,
    TrialResultEvaluation,
    UsageEvent,
    UsageSettlement,
    User,
    UserRole,
    UserSession,
    WorkspaceTablePreference,
)
from pharma_intel.monitoring.service import (
    MonitoringConflict,
    MonitoringNotFound,
    MonitoringService,
)
from pharma_intel.operational_metrics import operational_metrics
from pharma_intel.platform.operations import PlatformOperationsError, PlatformOperationsService
from pharma_intel.product import PRODUCT_NAME
from pharma_intel.provenance import ProvenanceRepository
from pharma_intel.quality.service import DataQualityError, DataQualityService
from pharma_intel.repository import DuplicateEntityError, EntityRepository
from pharma_intel.request_correlation import (
    NETWORK_FINGERPRINT_HEADER,
    CorrelationSignalError,
    validate_internal_network_fingerprint,
)
from pharma_intel.research_activity import (
    RESEARCH_ENTITY_RESOURCE_TYPE,
    RequestAuditResource,
    ResearchActivityService,
)
from pharma_intel.schemas import (
    CLINICAL_TRIAL_SORT_FIELDS,
    DEAL_SORT_FIELDS,
    ENTITY_SORT_FIELDS,
    EPIDEMIOLOGY_SORT_FIELDS,
    NEWS_SORT_FIELDS,
    PATENT_SORT_FIELDS,
    PIPELINE_SORT_FIELDS,
    REGULATORY_SORT_FIELDS,
    AgentChemistrySearchRead,
    AgentEntitySearchResult,
    AgentEvidenceSearchResult,
    AgentPageResult,
    AppliedFilterRead,
    BillingAccountRead,
    BillingCustomerMappingUpdate,
    BillingDeliveryRead,
    BillingDeliveryReplayRequest,
    BillingDisputeCreate,
    BillingDisputeRead,
    BillingDisputeTransition,
    BillingStatementCreate,
    BillingStatementRead,
    BioactivityRead,
    ChemistrySearchHitRead,
    ChemistrySearchRead,
    ChemistrySearchRequest,
    ClinicalTrialDetailRead,
    ClinicalTrialRead,
    ClinicalTrialSearchItemRead,
    ClinicalTrialSearchResult,
    ClinicalTrialSortField,
    CommercialAccessRead,
    CommercialAdjustmentRead,
    CommercialClientRead,
    CommercialClientStatusUpdate,
    CommercialEstimateRead,
    CommercialEstimateRequest,
    CommercialExpirationRead,
    CommercialExpirationRequest,
    CommercialOverviewRead,
    CommercialReconciliationCreate,
    CommercialReconciliationRead,
    CommercialReleaseRequest,
    CommercialReservationRead,
    CommercialReserveRequest,
    CommercialReversalCreate,
    CommercialRiskEventPageRead,
    CommercialRiskEventRead,
    CommercialRiskReview,
    CommercialSettlementRead,
    CommercialSettlementRequest,
    CommercialUsageAdjustmentCreate,
    CommercialUsageSummaryRead,
    CompanyDossierResponse,
    CompanyTimelineEventRead,
    CompanyTimelineResult,
    ComparisonSetCreate,
    ComparisonSetDetailRead,
    ComparisonSetMemberCreate,
    ComparisonSetMemberRead,
    ComparisonSetMemberRemove,
    ComparisonSetMembersAdd,
    ComparisonSetSummaryRead,
    ComparisonSetUpdate,
    ComparisonSetVersionRead,
    CompetitiveProgramRead,
    CompoundStructureRead,
    DataExportChunkRead,
    DataExportCreate,
    DataExportRead,
    DataLifecycleEventRead,
    DataLifecyclePurgeRead,
    DataLifecyclePurgeRequest,
    DataQualityCoverageRead,
    DataQualityIssueActionRequest,
    DataQualityIssueEventRead,
    DataQualityIssueRead,
    DataQualityOwnerRead,
    DataQualitySnapshotRead,
    DataRetentionPolicyRead,
    DataRetentionPolicyUpdate,
    DataSourceCreate,
    DataSourceDatasetRead,
    DataSourceRead,
    DataSourceReadinessRead,
    DataSourceStateUpdate,
    DataSourceUpdate,
    DealAnalysisLimit,
    DealRead,
    DealSearchItemRead,
    DealSearchResult,
    DealSortField,
    DeletedSourceAssetRead,
    DiseaseDossierResponse,
    DrugComparisonResult,
    DrugDossierResponse,
    DrugProgramSearchResult,
    EnterpriseApiKeyCatalogRead,
    EnterpriseApiKeyCreate,
    EnterpriseApiKeyRead,
    EnterpriseApiKeyRevoke,
    EnterpriseApiKeyRotate,
    EnterpriseApiKeySecretRead,
    EnterpriseAuditEventRead,
    EnterpriseAuditPageRead,
    EnterpriseDatasetRead,
    EnterpriseDatasetStatusUpdate,
    EnterpriseLLMProviderCreate,
    EnterpriseLLMProviderPrimaryUpdate,
    EnterpriseLLMProviderRead,
    EnterpriseLLMProviderUpdate,
    EnterpriseOverviewRead,
    EnterpriseSessionRead,
    EnterpriseSessionRevoke,
    EnterpriseUserCreate,
    EnterpriseUserRead,
    EnterpriseUserRoleUpdate,
    EnterpriseUserStatusUpdate,
    EntityCreate,
    EntityDossierResponse,
    EntityOntologyMappingCreate,
    EntityRead,
    EntityResolutionCaseRead,
    EntityResolutionDecisionRequest,
    EntityResolutionImpactRead,
    EntitySearchItemRead,
    EntitySortField,
    EntitySuggestionResult,
    EpidemiologyObservationSearchItemRead,
    EpidemiologyObservationSearchResult,
    EpidemiologySortField,
    EpidemiologyTrendResult,
    EvidenceChunk,
    EvidenceDatasetRead,
    EvidenceLicenseScope,
    EvidenceSearchRequest,
    EvidenceSearchResponse,
    GovernanceRunPageRead,
    GovernanceRunRead,
    IngestionCapabilitiesRead,
    IngestionFindingRead,
    IngestionRunCancelAcceptedRead,
    IngestionRunCancelRequest,
    IngestionRunRead,
    IngestionRunReplayRequest,
    IngestionScanAcceptedRead,
    KnowledgePageDetail,
    KnowledgePageSummary,
    LegalHoldCreate,
    LegalHoldRead,
    LegalHoldRelease,
    LoginRequest,
    MonitoringAlertRead,
    MonitoringTopicCreate,
    MonitoringTopicRead,
    MonitoringTopicUpdate,
    NewsEventSearchItemRead,
    NewsEventSearchResult,
    NewsSortField,
    OntologyTermRead,
    OntologyTermUpsert,
    PatentFamilyRead,
    PatentFamilySearchItemRead,
    PatentFamilySearchResult,
    PatentSortField,
    PipelineLandscapeStageScope,
    PipelineResultGrain,
    PipelineSearchResult,
    PipelineSortField,
    PipelineTargetAggregation,
    PlatformOperationsRead,
    ProjectionMaintenanceAccessRead,
    ProjectionMaintenanceJobRead,
    ProjectionMaintenanceRequest,
    ProvenanceResourceType,
    PublicationBatchCommitRequest,
    PublicationBatchItemRead,
    PublicationBatchPreviewRequest,
    PublicationBatchRead,
    PublicKnowledgePageCoverageRead,
    PublicKnowledgePageDetail,
    PublicKnowledgePageSummary,
    PublicKnowledgeVersionDiffRead,
    PublicKnowledgeVersionSummaryRead,
    RecentEntityVisitRead,
    RecordProvenanceRead,
    RecordProvenanceResponse,
    RegulatoryEventRead,
    RegulatoryEventSearchItemRead,
    RegulatoryEventSearchResult,
    RegulatorySortField,
    ReviewDecision,
    SarActivityRead,
    SarComparisonResult,
    SavedSearchCreate,
    SavedSearchRead,
    SavedSearchUpdate,
    SearchProjectionStatusRead,
    SearchResult,
    SortCriterionRead,
    SortDirection,
    SortToken,
    SourceAssetDetailRead,
    SourceAssetImpactRead,
    SourceAssetPageRead,
    SourceAssetRead,
    SourceVersionPreviewRead,
    SourceVersionQuarantineCaseRead,
    SourceVersionQuarantineDecisionAcceptedRead,
    SourceVersionQuarantineDecisionRead,
    SourceVersionQuarantineDecisionRequest,
    SourceVersionRead,
    SourceVersionReplayAcceptedRead,
    SourceVersionReplayRequest,
    StagedFactRead,
    TargetDossierResponse,
    TargetEvidenceRead,
    TargetProfileResponse,
    TrialInitiationType,
    TrialTherapyLine,
    UserGroupCreate,
    UserGroupMembershipUpdate,
    UserGroupRead,
    UserGroupUpdate,
    UserPasswordChange,
    UserProfileUpdate,
    UserRead,
    WebVitalBatchAccepted,
    WebVitalBatchCreate,
    WorkspaceDomainExportCreate,
    WorkspaceExportCreate,
    WorkspaceExportPolicyRead,
    WorkspaceExportPolicyUpsert,
    WorkspaceTableDensity,
    WorkspaceTablePreferenceKey,
    WorkspaceTablePreferenceRead,
    WorkspaceTablePreferenceUpdate,
)
from pharma_intel.search.client import SearchProjectionError, get_opensearch_gateway
from pharma_intel.search.maintenance import ProjectionMaintenanceError, ProjectionMaintenanceService
from pharma_intel.search.projector import SearchProjectionConsumer
from pharma_intel.search.service import EntitySearchResultSet, EntitySearchService
from pharma_intel.security import (
    CSRF_COOKIE,
    PLATFORM_PROJECTION_SCOPE,
    SESSION_COOKIE,
    Principal,
    authenticate_user,
    hash_password,
    issue_human_session,
    normalize_email,
    require_principal,
    verify_password,
)
from pharma_intel.sorting import SortClause, SortValidationError, resolve_sort_clauses
from pharma_intel.telemetry import instrument_fastapi
from pharma_intel.web_assets import workspace_cache_headers_for_path
from pharma_intel.web_branding import install_web_branding
from pharma_intel.workspace_preferences import (
    WorkspaceTablePreferenceConflict,
    WorkspaceTablePreferenceService,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    structlog.configure(processors=[structlog.processors.add_log_level, structlog.processors.JSONRenderer()])
    yield


app = FastAPI(
    title=PRODUCT_NAME,
    version=__version__,
    description="Structured pharmaceutical intelligence and evidence retrieval API",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json" if get_settings().api_docs_enabled else None,
)
# FastAPI defaults to 3.1.0; the release contract is pinned independently of
# whether interactive documentation is exposed in a production deployment.
app.openapi_version = "3.1.2"
install_web_branding(app, get_settings().web_root, docs_enabled=get_settings().api_docs_enabled)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().public_base_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)

request_logger = structlog.get_logger("pharma_intel.request")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
REQUEST_AUDIT_EXEMPT_PATHS = frozenset({"/api/v1/workspace/web-vitals"})
RDKIT_WORKER_ASSET_PATTERN = re.compile(r"^/assets/rdkit\.worker-[A-Za-z0-9_-]+\.js$")
INDIGO_WORKER_ASSET_PATTERN = re.compile(r"^/assets/indigoWorker-[A-Za-z0-9_-]+\.js$")
BROWSER_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "worker-src 'self'; "
        "manifest-src 'self'"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


DealAssetModalityQueryValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
DealAssetProgramTagQueryValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=240),
]
PipelineModalityQueryValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
PipelineProgramTagQueryValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=240),
]


def _validated_utc_datetime_range(
    start: datetime | None,
    end: datetime | None,
    *,
    start_field: str,
    end_field: str,
) -> tuple[datetime | None, datetime | None]:
    for field, value in ((start_field, start), (end_field, end)):
        if value is not None and value.tzinfo is None:
            raise HTTPException(status_code=422, detail=f"{field} must include a timezone offset")
    normalized_start = start.astimezone(UTC) if start else None
    normalized_end = end.astimezone(UTC) if end else None
    if normalized_start and normalized_end and normalized_start > normalized_end:
        raise HTTPException(status_code=422, detail=f"{start_field} must not be after {end_field}")
    return normalized_start, normalized_end


def _validated_trial_role_entity_filter(
    entity_id: str | None,
    entity_ids: list[str] | None,
    role: TrialEntityRole | None,
) -> tuple[str | None, list[str] | None, TrialEntityRole | None]:
    if entity_id is not None and entity_ids:
        raise HTTPException(status_code=422, detail="role_entity_id cannot be combined with role_entity_ids")
    normalized_ids = sorted(set(entity_ids or [])) or None
    if normalized_ids and any(not entity_value or len(entity_value) > 36 for entity_value in normalized_ids):
        raise HTTPException(status_code=422, detail="role_entity_ids contains an invalid entity ID")
    if role is not None and entity_id is None and normalized_ids is None:
        raise HTTPException(
            status_code=422,
            detail="role_entity_role requires role_entity_id or role_entity_ids",
        )
    return entity_id, normalized_ids, role


def _validated_trial_role_entity_ids(field: str, entity_ids: list[str] | None) -> list[str] | None:
    normalized_ids = sorted(set(entity_ids or [])) or None
    if normalized_ids and any(len(entity_id) != 36 for entity_id in normalized_ids):
        raise HTTPException(status_code=422, detail=f"{field} contains an invalid entity ID")
    return normalized_ids


def _validated_number_range(
    minimum: float | None,
    maximum: float | None,
    *,
    minimum_field: str,
    maximum_field: str,
) -> tuple[float | None, float | None]:
    if minimum is not None and maximum is not None and minimum > maximum:
        raise HTTPException(status_code=422, detail=f"{minimum_field} must not exceed {maximum_field}")
    return minimum, maximum


def _normalized_repeated_filter(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    return list(dict.fromkeys(values))


def _validated_sort[SortField: str](
    tokens: list[str] | None,
    allowed_fields: tuple[SortField, ...],
    *,
    default_field: SortField,
    default_direction: SortDirection,
    legacy_field: SortField | None,
    legacy_direction: SortDirection | None,
) -> tuple[SortClause[SortField], ...]:
    try:
        return resolve_sort_clauses(
            tokens,
            allowed_fields,
            default_field=default_field,
            default_direction=default_direction,
            legacy_field=legacy_field,
            legacy_direction=legacy_direction,
        )
    except SortValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _sort_reads[SortField: str](clauses: tuple[SortClause[SortField], ...]) -> list[SortCriterionRead]:
    return [SortCriterionRead(field=clause.field, direction=clause.direction) for clause in clauses]


def _validate_deal_amount_sort(sort: tuple[SortClause[DealSortField], ...], currency: str | None) -> None:
    if any(clause.field in {"upfront_amount", "total_potential_amount"} for clause in sort) and currency is None:
        raise HTTPException(
            status_code=422,
            detail="currency is required when sorting disclosed deal amounts",
        )


def _validated_pipeline_signal_filters(
    has_clinical_results: bool | None,
    clinical_result_evaluation: TrialResultEvaluation | None,
    has_deal: bool | None,
    deal_currency: str | None,
    deal_total_potential_amount_min: float | None,
    deal_total_potential_amount_max: float | None,
) -> tuple[float | None, float | None]:
    if has_clinical_results is False and clinical_result_evaluation is not None:
        raise HTTPException(
            status_code=422,
            detail="clinical_result_evaluation cannot be combined with has_clinical_results=false",
        )
    if has_deal is False and any(
        value is not None for value in (deal_currency, deal_total_potential_amount_min, deal_total_potential_amount_max)
    ):
        raise HTTPException(status_code=422, detail="deal detail filters cannot be combined with has_deal=false")
    if (
        deal_total_potential_amount_min is not None or deal_total_potential_amount_max is not None
    ) and deal_currency is None:
        raise HTTPException(status_code=422, detail="deal_currency is required for disclosed amount filters")
    return _validated_number_range(
        deal_total_potential_amount_min,
        deal_total_potential_amount_max,
        minimum_field="deal_total_potential_amount_min",
        maximum_field="deal_total_potential_amount_max",
    )


RDKIT_WORKER_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self' 'unsafe-eval'; connect-src 'self'; object-src 'none'"
)
INDIGO_WORKER_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; connect-src 'self'; object-src 'none'"
)


def browser_security_headers_for_path(path: str) -> dict[str, str]:
    headers = dict(BROWSER_SECURITY_HEADERS)
    if RDKIT_WORKER_ASSET_PATTERN.fullmatch(path):
        headers["Content-Security-Policy"] = RDKIT_WORKER_CONTENT_SECURITY_POLICY
    elif INDIGO_WORKER_ASSET_PATTERN.fullmatch(path):
        headers["Content-Security-Policy"] = INDIGO_WORKER_CONTENT_SECURITY_POLICY
    return headers


@app.middleware("http")
async def request_audit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    incoming = request.headers.get("X-Request-ID", "")
    request_id = incoming if REQUEST_ID_PATTERN.fullmatch(incoming) else str(uuid.uuid4())
    request.state.request_id = request_id
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute("pharma.request_id", request_id)
    response_status = 500
    try:
        response = await call_next(request)
        response_status = response.status_code
        response.headers["X-Request-ID"] = request_id
        for header, value in browser_security_headers_for_path(request.url.path).items():
            response.headers.setdefault(header, value)
        if 200 <= response_status < 400:
            for header, value in workspace_cache_headers_for_path(request.url.path).items():
                response.headers.setdefault(header, value)
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        return response
    finally:
        principal = getattr(request.state, "principal", None)
        if (
            isinstance(principal, Principal)
            and request.url.path.startswith(("/api/", "/internal/"))
            and request.url.path not in REQUEST_AUDIT_EXEMPT_PATHS
        ):
            audit_session: Session | None = None
            owns_audit_session = False
            try:
                audit_session = getattr(request.state, "db_session", None)
                if not isinstance(audit_session, Session):
                    # Dependency-owned request sessions are closed before middleware unwinds. Keep
                    # audit persistence independent so read-only routes are audited as reliably as writes.
                    audit_session = get_session_factory()()
                    owns_audit_session = True
                if audit_session.in_transaction():
                    audit_session.rollback()
                set_tenant_context(audit_session, principal.tenant_id)
                resource = getattr(request.state, "audit_resource", None)
                audit_session.add(
                    AuditEvent(
                        tenant_id=principal.tenant_id,
                        actor_type=principal.actor_type,
                        actor_id=principal.actor_id,
                        action=f"{request.method} {request.url.path}",
                        resource_type=resource.resource_type
                        if isinstance(resource, RequestAuditResource)
                        else "http_request",
                        resource_id=resource.resource_id if isinstance(resource, RequestAuditResource) else None,
                        outcome="success" if response_status < 400 else "failure",
                        request_id=request_id,
                        details={
                            "status_code": response_status,
                            **(resource.details if isinstance(resource, RequestAuditResource) else {}),
                        },
                    )
                )
                audit_session.commit()
            except Exception as exc:
                if isinstance(audit_session, Session):
                    audit_session.rollback()
                request_logger.error("audit_write_failed", request_id=request_id, error=str(exc))
            finally:
                if owns_audit_session and isinstance(audit_session, Session):
                    audit_session.close()


SessionDep = Annotated[Session, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(require_principal)]


@app.exception_handler(CommercialError)
async def commercial_error_handler(_: Request, exc: CommercialError) -> JSONResponse:
    if isinstance(exc, CommercialNotConfigured | InsufficientCredits):
        status_code = status.HTTP_402_PAYMENT_REQUIRED
        detail = str(exc)
    elif isinstance(exc, CommercialAccessDenied):
        status_code = status.HTTP_403_FORBIDDEN
        detail = str(exc)
    elif isinstance(
        exc,
        IdempotencyConflict
        | ReservationConflict
        | ReservationExpired
        | CommercialAccountingConflict
        | ExportStateConflict,
    ):
        status_code = status.HTTP_409_CONFLICT
        detail = str(exc)
    elif isinstance(exc, SettlementLimitExceeded | CommercialBalanceViolation | ExportValidationError):
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        detail = str(exc)
    elif isinstance(exc, CommercialInvariantViolation):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail = "Commercial accounting is temporarily unavailable"
        request_logger.error("commercial_invariant_violation", error=str(exc))
    else:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail = "Commercial accounting is temporarily unavailable"
    return JSONResponse(status_code=status_code, content={"detail": detail})


@app.exception_handler(CommercialOperationsNotFound)
async def commercial_operations_not_found_handler(_: Request, exc: CommercialOperationsNotFound) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


@app.exception_handler(CommercialOperationsConflict)
async def commercial_operations_conflict_handler(_: Request, exc: CommercialOperationsConflict) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@app.exception_handler(BillingDisputeNotFound)
async def billing_dispute_not_found_handler(_: Request, exc: BillingDisputeNotFound) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


@app.exception_handler(BillingDisputeConflict)
async def billing_dispute_conflict_handler(_: Request, exc: BillingDisputeConflict) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@app.exception_handler(LifecycleConflict)
async def lifecycle_conflict_handler(_: Request, exc: LifecycleConflict) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@app.exception_handler(LifecycleError)
async def lifecycle_error_handler(_: Request, exc: LifecycleError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)})


@app.exception_handler(EnterpriseAdminNotFound)
async def enterprise_admin_not_found_handler(_: Request, exc: EnterpriseAdminNotFound) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


@app.exception_handler(EnterpriseAdminConflict)
async def enterprise_admin_conflict_handler(_: Request, exc: EnterpriseAdminConflict) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@app.exception_handler(ChemistryValidationError)
async def chemistry_validation_error_handler(_: Request, exc: ChemistryValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": {"code": exc.code, "message": str(exc)}},
    )


@app.exception_handler(ChemistryBackendUnavailable)
async def chemistry_backend_error_handler(_: Request, exc: ChemistryBackendUnavailable) -> JSONResponse:
    request_logger.error("chemistry_backend_unavailable", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": {"code": "chemistry_backend_unavailable", "message": "Chemical search is unavailable"}},
    )


def _commercial_service(session: Session, principal: Principal) -> CommercialUsageService:
    principal.require(get_settings().mcp_required_scope)
    settings = get_settings()
    if not settings.mcp_commercial_enforcement_enabled:
        raise CommercialNotConfigured("Commercial MCP data access is disabled")
    return CommercialUsageService(
        session,
        principal,
        reservation_lease_seconds=settings.mcp_reservation_lease_seconds,
        max_result_bytes=settings.mcp_max_durable_result_bytes,
        max_billable_units_per_call=settings.mcp_max_billable_units_per_call,
        max_active_reservations_per_client=settings.mcp_max_active_reservations_per_client,
        cursor_codec=SignedCursorCodec(
            settings.effective_mcp_cursor_signing_secret,
            ttl_seconds=settings.mcp_cursor_ttl_seconds,
            max_token_chars=settings.mcp_cursor_max_token_chars,
        ),
    )


def _require_human_commercial(principal: Principal, scope: str) -> None:
    if principal.actor_type != "user":
        raise HTTPException(status_code=403, detail="Human workspace account required")
    principal.require(scope)


def _commercial_accounting_service(session: Session, principal: Principal) -> CommercialAccountingService:
    _require_human_commercial(principal, "commercial:write")
    tenant = session.get(Tenant, principal.tenant_id)
    if tenant is None or not tenant.active:
        raise HTTPException(status_code=403, detail="Active tenant required")
    settings = get_settings()
    return CommercialAccountingService(
        session,
        tenant,
        actor_id=principal.actor_id,
        statement_signer=BillingStatementSigner(
            settings.effective_billing_statement_signing_secret,
            key_id=settings.billing_statement_signing_key_id,
        ),
    )


def _agent_export_service(session: Session, principal: Principal) -> CommercialExportService:
    principal.require(get_settings().mcp_required_scope)
    if not get_settings().mcp_commercial_enforcement_enabled:
        raise CommercialNotConfigured("Commercial MCP data access is disabled")
    return build_export_service(session, get_settings())


def _export_read(job: DataExportJob) -> DataExportRead:
    return DataExportRead.model_validate(export_job_view(job))


def _data_lifecycle_service(session: Session, principal: Principal, scope: str) -> DataLifecycleService:
    _require_human_commercial(principal, scope)
    return DataLifecycleService(session, object_store_module.build_object_store(get_settings()))


def _enterprise_service(request: Request, session: Session, principal: Principal) -> EnterpriseAdminService:
    if principal.actor_type != "user" or principal.user_id is None:
        raise HTTPException(status_code=403, detail="Human workspace account required")
    principal.require("enterprise:admin")
    settings = get_settings()
    return EnterpriseAdminService(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request.state.request_id,
        cursor_codec=AuditCursorCodec(settings.jwt_secret),
    )


def _api_key_service(request: Request, session: Session, principal: Principal) -> ApiKeyLifecycleService:
    _enterprise_service(request, session, principal)
    tenant = session.get(Tenant, principal.tenant_id)
    if tenant is None or not tenant.active:
        raise HTTPException(status_code=403, detail="Active tenant required")
    return ApiKeyLifecycleService(
        session,
        tenant,
        actor_id=principal.actor_id,
        actor_type="user",
    )


def _llm_provider_service(request: Request, session: Session, principal: Principal) -> LLMProviderCatalogService:
    _enterprise_service(request, session, principal)
    assert principal.user_id is not None
    return LLMProviderCatalogService(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request.state.request_id,
        settings=get_settings(),
    )


def _llm_provider_http_error(session: Session, exc: LLMProviderError) -> HTTPException:
    session.rollback()
    if isinstance(exc, LLMProviderNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, LLMProviderConflict):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=503, detail=str(exc))


def _enterprise_api_key_read(view: ApiKeyView) -> EnterpriseApiKeyRead:
    key = view.key
    now = datetime.now(UTC)
    expires_at = key.expires_at
    comparable_expiry = (
        expires_at.replace(tzinfo=UTC)
        if expires_at is not None and (expires_at.tzinfo is None or expires_at.utcoffset() is None)
        else expires_at
    )
    if key.revoked_at is not None:
        key_status = "revoked"
    elif comparable_expiry is not None and comparable_expiry <= now:
        key_status = "expired"
    elif key.active:
        key_status = "active"
    else:
        key_status = "disabled"
    return EnterpriseApiKeyRead(
        id=key.id,
        name=key.name,
        prefix=key.prefix,
        scopes=list(key.scopes),
        active=key.active,
        status=key_status,
        last_used_at=key.last_used_at,
        expires_at=key.expires_at,
        revoked_at=key.revoked_at,
        commercial_client_id=view.commercial_client_id,
        commercial_client_name=view.commercial_client_name,
        created_at=key.created_at,
        updated_at=key.updated_at,
    )


def _api_key_http_error(session: Session, exc: ApiKeyLifecycleError) -> HTTPException:
    session.rollback()
    if isinstance(exc, ApiKeyLifecycleNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


def _prevent_secret_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _group_read(view: GroupView) -> UserGroupRead:
    group = view.group
    return UserGroupRead(
        id=group.id,
        tenant_id=group.tenant_id,
        name=group.name,
        description=group.description,
        active=group.active,
        version=group.version,
        member_ids=list(view.member_ids),
        member_count=len(view.member_ids),
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


def _adjustment_read(adjustment: BillingAdjustment) -> CommercialAdjustmentRead:
    return CommercialAdjustmentRead(
        id=adjustment.id,
        subscription_id=adjustment.subscription_id,
        adjustment_key=adjustment.adjustment_key,
        adjustment_kind=adjustment.adjustment_kind,
        reverses_adjustment_id=adjustment.reverses_adjustment_id,
        reverses_settlement_id=adjustment.reverses_settlement_id,
        units_delta=format(adjustment.units_delta, "f"),
        reason=adjustment.reason,
        request_id=adjustment.request_id,
        created_by=adjustment.created_by,
        created_at=adjustment.created_at,
    )


def _reconciliation_read(run: CommercialReconciliationRun) -> CommercialReconciliationRead:
    return CommercialReconciliationRead(
        id=run.id,
        subscription_id=run.subscription_id,
        run_key=run.run_key,
        status=run.status,
        issue_count=run.issue_count,
        snapshot_granted_units=format(run.snapshot_granted_units, "f"),
        snapshot_reserved_units=format(run.snapshot_reserved_units, "f"),
        snapshot_consumed_units=format(run.snapshot_consumed_units, "f"),
        ledger_granted_units=format(run.ledger_granted_units, "f"),
        ledger_reserved_units=format(run.ledger_reserved_units, "f"),
        ledger_consumed_units=format(run.ledger_consumed_units, "f"),
        source_granted_units=format(run.source_granted_units, "f"),
        source_reserved_units=format(run.source_reserved_units, "f"),
        source_consumed_units=format(run.source_consumed_units, "f"),
        issues=run.issues_json,
        requested_by=run.requested_by,
        request_id=run.request_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _statement_read(statement: BillingPeriodStatement) -> BillingStatementRead:
    return BillingStatementRead(
        id=statement.id,
        subscription_id=statement.subscription_id,
        billing_account_id=statement.billing_account_id,
        statement_key=statement.statement_key,
        revision=statement.revision,
        period_start=statement.period_start,
        period_end=statement.period_end,
        settlement_units=format(statement.settlement_units, "f"),
        adjustment_units=format(statement.adjustment_units, "f"),
        net_consumed_units=format(statement.net_consumed_units, "f"),
        settlement_count=statement.settlement_count,
        adjustment_count=statement.adjustment_count,
        result_count=statement.result_count,
        response_bytes=statement.response_bytes,
        manifest_sha256=statement.manifest_sha256,
        signature_key_id=statement.signature_key_id,
        manifest_signature=statement.manifest_signature,
        payload=statement.payload_json,
        generated_by=statement.generated_by,
        request_id=statement.request_id,
        generated_at=statement.generated_at,
    )


def _settlement_read(settlement: UsageSettlement, usage_event: UsageEvent) -> CommercialSettlementRead:
    return CommercialSettlementRead(
        settlement_id=settlement.id,
        usage_event_id=usage_event.id,
        charged_units=format(settlement.charged_units, "f"),
        result_count=usage_event.result_count,
        unique_record_count=usage_event.unique_record_count,
        new_unique_record_count=usage_event.new_unique_record_count,
        response_bytes=usage_event.response_bytes,
        price_breakdown=settlement.price_breakdown,
        result=settlement.result_json,
        created_at=settlement.created_at,
    )


def _reservation_read(
    outcome: ReservationOutcome,
    session: Session,
) -> CommercialReservationRead:
    settlement_read: CommercialSettlementRead | None = None
    if outcome.settlement is not None:
        usage_event = session.get(UsageEvent, outcome.settlement.usage_event_id)
        if usage_event is None or usage_event.tenant_id != outcome.reservation.tenant_id:
            raise CommercialInvariantViolation("Settlement usage event is unavailable")
        settlement_read = _settlement_read(outcome.settlement, usage_event)
    return CommercialReservationRead(
        reservation_id=outcome.reservation.id,
        state=outcome.reservation.state,
        billing_class=outcome.reservation.billing_class,
        estimated_units=format(outcome.reservation.estimated_units, "f"),
        reserved_units=format(outcome.reservation.reserved_units, "f"),
        requested_compute_units=format(outcome.reservation.requested_compute_units, "f"),
        lease_expires_at=outcome.reservation.lease_expires_at,
        page_depth=outcome.reservation.page_depth,
        replayed=outcome.replayed,
        settlement=settlement_read,
    )


def _chemistry_arguments(payload: ChemistrySearchRequest) -> dict[str, object]:
    arguments: dict[str, object] = {
        "mode": payload.mode,
        "query": payload.query,
        "limit": payload.limit,
    }
    if payload.mode == "similarity":
        arguments["threshold"] = payload.threshold
    return arguments


def _execute_chemistry_search(
    session: Session,
    tenant_id: str,
    payload: ChemistrySearchRequest,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> ChemistrySearchRead:
    service = ChemistryService(session, tenant_id)
    resolved_limit = limit or payload.limit
    result: ChemistrySearchResult
    if payload.mode == "exact":
        result = service.exact(payload.query, resolved_limit, offset)
    elif payload.mode == "substructure":
        result = service.substructure(payload.query, resolved_limit, offset)
    else:
        result = service.similarity(payload.query, payload.threshold, resolved_limit, offset)
    return ChemistrySearchRead(
        mode=result.mode,
        normalized_query=result.normalized_query,
        items=[ChemistrySearchHitRead.model_validate(item) for item in result.hits],
        count=len(result.hits),
        as_of=result.as_of,
        standardization_version=result.standardization_version,
        fingerprint_version=result.fingerprint_version,
        similarity_threshold=result.similarity_threshold,
    )


def _agent_page[PageRecord](
    principal: Principal,
    session: Session,
    reservation_id: str,
    *,
    billing_class: str,
    arguments: dict[str, object],
    page_size: int,
    fetch: Callable[[int, int], list[PageRecord]],
    visible_entity_ids: list[str | None] | None = None,
    visible_filter_entity_ids: list[str | None] | None = None,
    required_compute_units: str = "0",
    sort: list[SortCriterionRead] | None = None,
) -> AgentPageResult[PageRecord]:
    if visible_entity_ids is not None:
        _assert_public_entity_ids_visible(session, principal, visible_entity_ids)
    if visible_filter_entity_ids is not None:
        _assert_public_entity_ids_visible(
            session,
            principal,
            visible_filter_entity_ids,
            reject_missing=False,
        )
    service = _commercial_service(session, principal)
    reservation = service.authorize_paginated_query(
        reservation_id,
        billing_class=billing_class,
        request_arguments=arguments,
        page_size=page_size,
        required_compute_units=required_compute_units,
    )
    rows = fetch(reservation.page_offset, page_size + 1)
    items = rows[:page_size]
    next_offset = reservation.page_offset + len(items)
    next_cursor = service.issue_next_cursor(
        reservation,
        next_offset=next_offset,
        has_more=len(rows) > page_size,
    )
    return AgentPageResult(
        items=items,
        limit=page_size,
        page_depth=reservation.page_depth,
        next_cursor=next_cursor,
        sort=sort or [],
    )


def _set_human_session_cookies(request: Request, response: Response, session: Session, user: User) -> None:
    set_tenant_context(session, user.tenant_id)
    session_id = str(uuid.uuid4())
    token, csrf_token, expires_at = issue_human_session(user, session_id)
    issued_at = datetime.now(UTC)
    session.add(
        UserSession(
            id=session_id,
            tenant_id=user.tenant_id,
            user_id=user.id,
            user_agent_sha256=hashlib.sha256(request.headers.get("user-agent", "").encode()).hexdigest(),
            issued_at=issued_at,
            expires_at=expires_at,
        )
    )
    session.commit()
    secure = get_settings().app_env.lower() == "production"
    max_age = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )


@app.post("/api/v1/auth/login", response_model=UserRead, tags=["authentication"])
def login(payload: LoginRequest, request: Request, response: Response, session: SessionDep) -> UserRead:
    if get_settings().human_auth_mode != "local":
        raise HTTPException(status_code=404, detail="Local password authentication is disabled")
    user = authenticate_user(session, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user.last_login_at = datetime.now(UTC)
    session.commit()
    _set_human_session_cookies(request, response, session, user)
    request.state.principal = Principal(user.tenant_id, user.id, "user", frozenset())
    return UserRead.model_validate(user)


@app.get("/api/v1/auth/config", tags=["authentication"])
def authentication_config() -> dict[str, str]:
    return {"mode": get_settings().human_auth_mode}


@app.get("/api/v1/auth/oidc/login", tags=["authentication"])
def oidc_login() -> RedirectResponse:
    settings = get_settings()
    if settings.human_auth_mode != "oidc":
        raise HTTPException(status_code=404, detail="Enterprise authentication is not enabled")
    authorization = create_oidc_authorization(settings)
    response = RedirectResponse(authorization.url, status_code=302)
    response.set_cookie(
        OIDC_TRANSACTION_COOKIE,
        authorization.transaction_token,
        max_age=authorization.max_age,
        httponly=True,
        secure=settings.app_env.lower() == "production",
        samesite="lax",
        path="/api/v1/auth/oidc",
    )
    return response


@app.get("/api/v1/auth/oidc/callback", tags=["authentication"])
async def oidc_callback(
    request: Request,
    session: SessionDep,
    code: str = Query(min_length=1, max_length=4096),
    state: str = Query(min_length=20, max_length=500),
) -> RedirectResponse:
    settings = get_settings()
    if settings.human_auth_mode != "oidc":
        raise HTTPException(status_code=404, detail="Enterprise authentication is not enabled")
    try:
        transaction = read_oidc_transaction(
            settings,
            request.cookies.get(OIDC_TRANSACTION_COOKIE, ""),
            state,
        )
        id_token = await exchange_oidc_code(settings, code, transaction["code_verifier"])
        claims = await get_oidc_id_token_verifier(settings).verify(id_token, transaction["nonce"])
        user = resolve_oidc_user(session, settings, claims)
        user.last_login_at = datetime.now(UTC)
        session.commit()
    except (OidcAuthenticationError, ValueError) as exc:
        session.rollback()
        request_logger.warning("oidc_login_failed", request_id=request.state.request_id, reason=type(exc).__name__)
        raise HTTPException(status_code=401, detail="Enterprise authentication failed") from exc
    response = RedirectResponse(settings.public_base_url.rstrip("/") + "/", status_code=302)
    response.delete_cookie(OIDC_TRANSACTION_COOKIE, path="/api/v1/auth/oidc")
    _set_human_session_cookies(request, response, session, user)
    request.state.principal = Principal(user.tenant_id, user.id, "user", frozenset())
    return response


@app.get("/api/v1/auth/me", response_model=UserRead, tags=["authentication"])
def current_user(principal: PrincipalDep, session: SessionDep) -> UserRead:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="Human account required")
    user = session.get(User, principal.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(user)


@app.patch("/api/v1/auth/me", response_model=UserRead, tags=["authentication"])
def update_current_user(
    payload: UserProfileUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> UserRead:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="Human account required")
    user = session.scalar(select(User).where(User.id == principal.user_id, User.tenant_id == principal.tenant_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if "email" in payload.model_fields_set:
        if payload.email is None:
            raise HTTPException(status_code=422, detail="email cannot be null")
        normalized_email = normalize_email(payload.email)
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email) is None:
            raise HTTPException(status_code=422, detail="A valid email address is required")
        existing = session.scalar(select(User.id).where(User.normalized_email == normalized_email, User.id != user.id))
        if existing is not None:
            raise HTTPException(status_code=409, detail="Email address is already in use")
        user.email = payload.email
        user.normalized_email = normalized_email

    if "display_name" in payload.model_fields_set and payload.display_name is not None:
        user.display_name = payload.display_name
    if "phone" in payload.model_fields_set:
        user.phone = payload.phone or None
    if "avatar_url" in payload.model_fields_set:
        if payload.avatar_url is not None:
            parsed_avatar_url = urlsplit(payload.avatar_url)
            if parsed_avatar_url.scheme != "https" or not parsed_avatar_url.netloc:
                raise HTTPException(status_code=422, detail="头像地址必须使用有效的 HTTPS 地址")
        user.avatar_url = payload.avatar_url or None

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Email address is already in use") from exc
    session.refresh(user)
    return UserRead.model_validate(user)


@app.post("/api/v1/auth/me/password", status_code=status.HTTP_204_NO_CONTENT, tags=["authentication"])
def change_current_user_password(
    payload: UserPasswordChange,
    principal: PrincipalDep,
    session: SessionDep,
) -> Response:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="Human account required")
    user = session.scalar(select(User).where(User.id == principal.user_id, User.tenant_id == principal.tenant_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.oidc_issuer is not None:
        raise HTTPException(status_code=409, detail="OIDC accounts manage passwords through the identity provider")
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(status_code=422, detail="New password must differ from the current password")

    user.password_hash = hash_password(payload.new_password)
    now = datetime.now(UTC)
    session.execute(
        update(UserSession)
        .where(
            UserSession.tenant_id == principal.tenant_id,
            UserSession.user_id == user.id,
            UserSession.id != principal.session_id,
            UserSession.revoked_at.is_(None),
        )
        .values(
            revoked_at=now,
            revoked_by_user_id=user.id,
            revoke_reason="Password changed",
        )
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["authentication"])
def logout(response: Response, principal: PrincipalDep, session: SessionDep) -> Response:
    if principal.user_id is not None and principal.session_id is not None:
        current = session.scalar(
            select(UserSession).where(
                UserSession.tenant_id == principal.tenant_id,
                UserSession.id == principal.session_id,
                UserSession.user_id == principal.user_id,
            )
        )
        if current is not None and current.revoked_at is None:
            current.revoked_at = datetime.now(UTC)
            current.revoked_by_user_id = principal.user_id
            current.revoke_reason = "User logout"
            session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@app.get("/api/v1/enterprise/overview", response_model=EnterpriseOverviewRead, tags=["enterprise"])
def enterprise_overview(request: Request, principal: PrincipalDep, session: SessionDep) -> EnterpriseOverviewRead:
    service = _enterprise_service(request, session, principal)
    return EnterpriseOverviewRead.model_validate(service.overview())


@app.get("/api/v1/enterprise/platform", response_model=PlatformOperationsRead, tags=["enterprise"])
def enterprise_platform_operations(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> PlatformOperationsRead:
    _enterprise_service(request, session, principal)
    try:
        snapshot = PlatformOperationsService(
            session,
            tenant_id=principal.tenant_id,
            settings=get_settings(),
        ).snapshot()
    except PlatformOperationsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return PlatformOperationsRead.model_validate(snapshot)


@app.get("/api/v1/enterprise/users", response_model=list[EnterpriseUserRead], tags=["enterprise"])
def list_enterprise_users(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[EnterpriseUserRead]:
    service = _enterprise_service(request, session, principal)
    return [EnterpriseUserRead.model_validate(user) for user in service.list_users()]


@app.post(
    "/api/v1/enterprise/users",
    response_model=EnterpriseUserRead,
    status_code=status.HTTP_201_CREATED,
    tags=["enterprise"],
)
def create_enterprise_user(
    payload: EnterpriseUserCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseUserRead:
    service = _enterprise_service(request, session, principal)
    user = service.create_user(
        CreateUserCommand(
            email=payload.email,
            display_name=payload.display_name,
            role=payload.role,
            auth_mode=get_settings().human_auth_mode,
            initial_password=payload.initial_password,
            oidc_issuer=payload.oidc_issuer,
            oidc_subject=payload.oidc_subject,
        )
    )
    return EnterpriseUserRead.model_validate(user)


@app.post(
    "/api/v1/enterprise/users/{user_id}/role",
    response_model=EnterpriseUserRead,
    tags=["enterprise"],
)
def update_enterprise_user_role(
    user_id: str,
    payload: EnterpriseUserRoleUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseUserRead:
    service = _enterprise_service(request, session, principal)
    user = service.update_user_role(
        user_id,
        UpdateUserRoleCommand(
            expected_token_version=payload.expected_token_version,
            role=payload.role,
            reason=payload.reason,
        ),
    )
    return EnterpriseUserRead.model_validate(user)


@app.post(
    "/api/v1/enterprise/users/{user_id}/status",
    response_model=EnterpriseUserRead,
    tags=["enterprise"],
)
def update_enterprise_user_status(
    user_id: str,
    payload: EnterpriseUserStatusUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseUserRead:
    service = _enterprise_service(request, session, principal)
    user = service.update_user_status(
        user_id,
        UpdateUserStatusCommand(
            expected_token_version=payload.expected_token_version,
            active=payload.active,
            reason=payload.reason,
        ),
    )
    return EnterpriseUserRead.model_validate(user)


@app.get("/api/v1/enterprise/groups", response_model=list[UserGroupRead], tags=["enterprise"])
def list_enterprise_groups(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[UserGroupRead]:
    service = _enterprise_service(request, session, principal)
    return [_group_read(view) for view in service.list_groups()]


def _enterprise_dataset_read(dataset: TenantDataset) -> EnterpriseDatasetRead:
    try:
        policy = EvidenceLicensePolicy.model_validate(dataset.license_policy)
        now = datetime.now(UTC)
        available_channels: tuple[DeliveryChannel, ...] = ("web", "mcp")
        channels = [channel for channel in available_channels if policy.permits(channel, now)]
        return EnterpriseDatasetRead(
            id=dataset.id,
            dataset_key=dataset.dataset_key,
            display_name=dataset.display_name,
            active=dataset.active,
            version=dataset.version,
            required_scopes=dataset.required_scopes,
            license_id=policy.license_id,
            license_policy_version=policy.policy_version,
            permitted_channels=channels,
            license_current=bool(channels),
            attribution=policy.attribution,
        )
    except ValueError:
        return EnterpriseDatasetRead(
            id=dataset.id,
            dataset_key=dataset.dataset_key,
            display_name=dataset.display_name,
            active=dataset.active,
            version=dataset.version,
            required_scopes=dataset.required_scopes,
            license_id="invalid",
            license_policy_version="invalid",
            permitted_channels=[],
            license_current=False,
            attribution="Invalid license policy",
        )


@app.get("/api/v1/enterprise/datasets", response_model=list[EnterpriseDatasetRead], tags=["enterprise"])
def list_enterprise_datasets(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[EnterpriseDatasetRead]:
    return [_enterprise_dataset_read(item) for item in _enterprise_service(request, session, principal).list_datasets()]


@app.post(
    "/api/v1/enterprise/datasets/{dataset_id}/status",
    response_model=EnterpriseDatasetRead,
    tags=["enterprise"],
)
def update_enterprise_dataset_status(
    dataset_id: str,
    payload: EnterpriseDatasetStatusUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseDatasetRead:
    dataset = _enterprise_service(request, session, principal).update_dataset_status(
        dataset_id,
        UpdateDatasetStatusCommand(payload.expected_version, payload.active, payload.reason),
    )
    return _enterprise_dataset_read(dataset)


@app.get("/api/v1/enterprise/sessions", response_model=list[EnterpriseSessionRead], tags=["enterprise"])
def list_enterprise_sessions(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[EnterpriseSessionRead]:
    return [
        EnterpriseSessionRead(
            id=item.session.id,
            user_id=item.user.id,
            user_display_name=item.user.display_name,
            user_email=item.user.email,
            issued_at=item.session.issued_at,
            expires_at=item.session.expires_at,
            revoked_at=item.session.revoked_at,
            revoked_by_user_id=item.session.revoked_by_user_id,
            revoke_reason=item.session.revoke_reason,
            current=item.session.id == principal.session_id,
        )
        for item in _enterprise_service(request, session, principal).list_sessions(limit=limit)
    ]


@app.post(
    "/api/v1/enterprise/sessions/{session_id}/revoke",
    response_model=EnterpriseSessionRead,
    tags=["enterprise"],
)
def revoke_enterprise_session(
    session_id: str,
    payload: EnterpriseSessionRevoke,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseSessionRead:
    item = _enterprise_service(request, session, principal).revoke_session(session_id, reason=payload.reason)
    return EnterpriseSessionRead(
        id=item.session.id,
        user_id=item.user.id,
        user_display_name=item.user.display_name,
        user_email=item.user.email,
        issued_at=item.session.issued_at,
        expires_at=item.session.expires_at,
        revoked_at=item.session.revoked_at,
        revoked_by_user_id=item.session.revoked_by_user_id,
        revoke_reason=item.session.revoke_reason,
        current=item.session.id == principal.session_id,
    )


@app.get(
    "/api/v1/enterprise/api-keys",
    response_model=EnterpriseApiKeyCatalogRead,
    tags=["enterprise"],
)
def list_enterprise_api_keys(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> EnterpriseApiKeyCatalogRead:
    service = _api_key_service(request, session, principal)
    return EnterpriseApiKeyCatalogRead(
        items=[_enterprise_api_key_read(view) for view in service.list_keys(limit=limit)],
        required_scope="mcp:connect",
        allowed_scopes=list(MANAGED_API_KEY_SCOPES),
        min_ttl_hours=int(API_KEY_MIN_TTL.total_seconds() // 3600),
        max_ttl_days=API_KEY_MAX_TTL.days,
    )


@app.post(
    "/api/v1/enterprise/api-keys",
    response_model=EnterpriseApiKeySecretRead,
    status_code=status.HTTP_201_CREATED,
    tags=["enterprise"],
)
def create_enterprise_api_key(
    payload: EnterpriseApiKeyCreate,
    request: Request,
    response: Response,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseApiKeySecretRead:
    service = _api_key_service(request, session, principal)
    try:
        issued = service.create(
            name=payload.name,
            scopes=payload.scopes,
            expires_at=payload.expires_at,
            reason=payload.reason,
            request_id=request.state.request_id,
        )
        session.commit()
    except ApiKeyLifecycleError as exc:
        raise _api_key_http_error(session, exc) from exc
    _prevent_secret_caching(response)
    item = _enterprise_api_key_read(ApiKeyView(issued.key, None, None))
    return EnterpriseApiKeySecretRead(**item.model_dump(), secret=issued.secret)


@app.post(
    "/api/v1/enterprise/api-keys/{key_id}/rotate",
    response_model=EnterpriseApiKeySecretRead,
    tags=["enterprise"],
)
def rotate_enterprise_api_key(
    key_id: str,
    payload: EnterpriseApiKeyRotate,
    request: Request,
    response: Response,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseApiKeySecretRead:
    service = _api_key_service(request, session, principal)
    try:
        rotation = service.rotate(
            key_id,
            new_name=payload.name,
            expires_at=payload.expires_at,
            reason=payload.reason,
            request_id=request.state.request_id,
        )
        session.commit()
        view = service.get(rotation.new_key_id)
    except ApiKeyLifecycleError as exc:
        raise _api_key_http_error(session, exc) from exc
    _prevent_secret_caching(response)
    item = _enterprise_api_key_read(view)
    return EnterpriseApiKeySecretRead(**item.model_dump(), secret=rotation.secret)


@app.post(
    "/api/v1/enterprise/api-keys/{key_id}/revoke",
    response_model=EnterpriseApiKeyRead,
    tags=["enterprise"],
)
def revoke_enterprise_api_key(
    key_id: str,
    payload: EnterpriseApiKeyRevoke,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseApiKeyRead:
    service = _api_key_service(request, session, principal)
    try:
        service.revoke(
            key_id,
            reason=payload.reason,
            request_id=request.state.request_id,
        )
        session.commit()
        view = service.get(key_id)
    except ApiKeyLifecycleError as exc:
        raise _api_key_http_error(session, exc) from exc
    return _enterprise_api_key_read(view)


@app.get(
    "/api/v1/enterprise/llm-providers",
    response_model=list[EnterpriseLLMProviderRead],
    tags=["enterprise"],
)
def list_enterprise_llm_providers(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[EnterpriseLLMProviderRead]:
    try:
        providers = _llm_provider_service(request, session, principal).list()
    except LLMProviderError as exc:
        raise _llm_provider_http_error(session, exc) from exc
    return [EnterpriseLLMProviderRead.model_validate(provider) for provider in providers]


@app.post(
    "/api/v1/enterprise/llm-providers",
    response_model=EnterpriseLLMProviderRead,
    status_code=status.HTTP_201_CREATED,
    tags=["enterprise"],
)
def create_enterprise_llm_provider(
    payload: EnterpriseLLMProviderCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseLLMProviderRead:
    try:
        provider = _llm_provider_service(request, session, principal).create(
            CreateLLMProviderCommand(**payload.model_dump())
        )
    except LLMProviderError as exc:
        raise _llm_provider_http_error(session, exc) from exc
    return EnterpriseLLMProviderRead.model_validate(provider)


@app.put(
    "/api/v1/enterprise/llm-providers/{provider_id}",
    response_model=EnterpriseLLMProviderRead,
    tags=["enterprise"],
)
def update_enterprise_llm_provider(
    provider_id: str,
    payload: EnterpriseLLMProviderUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseLLMProviderRead:
    try:
        provider = _llm_provider_service(request, session, principal).update(
            provider_id,
            UpdateLLMProviderCommand(**payload.model_dump()),
        )
    except LLMProviderError as exc:
        raise _llm_provider_http_error(session, exc) from exc
    return EnterpriseLLMProviderRead.model_validate(provider)


@app.post(
    "/api/v1/enterprise/llm-providers/{provider_id}/make-primary",
    response_model=list[EnterpriseLLMProviderRead],
    tags=["enterprise"],
)
def make_enterprise_llm_provider_primary(
    provider_id: str,
    payload: EnterpriseLLMProviderPrimaryUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[EnterpriseLLMProviderRead]:
    try:
        providers = _llm_provider_service(request, session, principal).make_primary(
            provider_id,
            payload.expected_version,
            payload.reason,
        )
    except LLMProviderError as exc:
        raise _llm_provider_http_error(session, exc) from exc
    return [EnterpriseLLMProviderRead.model_validate(provider) for provider in providers]


@app.post(
    "/api/v1/enterprise/llm-providers/{provider_id}/test",
    response_model=EnterpriseLLMProviderRead,
    tags=["enterprise"],
)
def test_enterprise_llm_provider(
    provider_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseLLMProviderRead:
    try:
        provider = _llm_provider_service(request, session, principal).test(provider_id)
    except LLMProviderError as exc:
        raise _llm_provider_http_error(session, exc) from exc
    return EnterpriseLLMProviderRead.model_validate(provider)


@app.post(
    "/api/v1/enterprise/groups",
    response_model=UserGroupRead,
    status_code=status.HTTP_201_CREATED,
    tags=["enterprise"],
)
def create_enterprise_group(
    payload: UserGroupCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> UserGroupRead:
    service = _enterprise_service(request, session, principal)
    return _group_read(service.create_group(CreateGroupCommand(payload.name, payload.description)))


@app.put("/api/v1/enterprise/groups/{group_id}", response_model=UserGroupRead, tags=["enterprise"])
def update_enterprise_group(
    group_id: str,
    payload: UserGroupUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> UserGroupRead:
    service = _enterprise_service(request, session, principal)
    return _group_read(
        service.update_group(
            group_id,
            UpdateGroupCommand(
                expected_version=payload.expected_version,
                name=payload.name,
                description=payload.description,
                active=payload.active,
                reason=payload.reason,
            ),
        )
    )


@app.put(
    "/api/v1/enterprise/groups/{group_id}/members",
    response_model=UserGroupRead,
    tags=["enterprise"],
)
def update_enterprise_group_members(
    group_id: str,
    payload: UserGroupMembershipUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> UserGroupRead:
    service = _enterprise_service(request, session, principal)
    return _group_read(
        service.update_group_members(
            group_id,
            UpdateGroupMembersCommand(
                expected_version=payload.expected_version,
                user_ids=tuple(payload.user_ids),
                reason=payload.reason,
            ),
        )
    )


@app.get("/api/v1/enterprise/audit-events", response_model=EnterpriseAuditPageRead, tags=["enterprise"])
def list_enterprise_audit_events(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=200),
    cursor: str | None = Query(default=None, min_length=20, max_length=4096),
    action: str | None = Query(default=None, min_length=1, max_length=160),
    outcome: str | None = Query(default=None, min_length=1, max_length=40),
    actor_type: Literal["agent", "api_key", "user"] | None = Query(default=None),
) -> EnterpriseAuditPageRead:
    service = _enterprise_service(request, session, principal)
    page = service.list_audit_events(
        limit=limit,
        cursor=cursor,
        action=action,
        outcome=outcome,
        actor_type=actor_type,
    )
    return EnterpriseAuditPageRead(
        items=[EnterpriseAuditEventRead.model_validate(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready(session: SessionDep) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    settings = get_settings()
    if settings.search_backend == "opensearch":
        try:
            get_opensearch_gateway().assert_projection_ready()
        except SearchProjectionError as exc:
            raise HTTPException(status_code=503, detail="Search projection unavailable") from exc
    return {"status": "ready", "search": settings.search_backend}


def _normalize_entity_types(entity_type: EntityType | None, entity_types: list[EntityType]) -> list[EntityType]:
    selected = set(entity_types)
    if entity_type is not None:
        selected.add(entity_type)
    return sorted(selected, key=lambda item: item.value)


ENTITY_SEARCH_SCHEMA_VERSION = "pharma.entity.search.v2"

# The canonical entity attributes are intentionally open-ended because ingestion and
# governance need to retain source-specific fields.  The human research boundary is
# different: only a reviewed, business-facing subset may cross into the external Web
# API.  Internal provenance and pipeline fields must remain available to governance
# and audit services without becoming user-visible data.
_PUBLIC_ENTITY_ATTRIBUTE_KEYS = frozenset(
    {
        "biomarker",
        "cas_number",
        "chemical_name",
        "country",
        "drug_category",
        "development_phase",
        "disease_area",
        "english_name",
        "headquarters",
        "innovation_type",
        "inchi",
        "inchi_key",
        "mechanism",
        "modality",
        "organism",
        "program_tag",
        "program_tags",
        "region",
        "smiles",
        "status_detail",
        "target_class",
        "therapeutic_area",
    }
)

_PUBLIC_ENTITY_IDENTIFIER_HIDDEN_PREFIXES = (
    "pharmcube",
    "internal",
    "source",
    "ingestion",
)


def _is_public_entity_attribute_value(value: Any) -> bool:
    """Keep arbitrary nested governance payloads outside the human API."""

    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list):
        return all(item is None or isinstance(item, str | int | float | bool) for item in value)
    return False


def _is_public_entity_identifier_namespace(namespace: str) -> bool:
    normalized = namespace.strip().casefold().replace("-", "_")
    return bool(normalized) and not any(
        normalized == prefix or normalized.startswith(f"{prefix}_")
        for prefix in _PUBLIC_ENTITY_IDENTIFIER_HIDDEN_PREFIXES
    )


def _public_entity_read(entity: Any) -> EntityRead:
    """Build the external entity projection without internal provenance fields."""

    read = EntityRead.model_validate(entity)
    attributes = {
        key: value
        for key, value in read.attributes.items()
        if key in _PUBLIC_ENTITY_ATTRIBUTE_KEYS and _is_public_entity_attribute_value(value)
    }
    external_ids = {
        namespace: value
        for namespace, value in read.external_ids.items()
        if _is_public_entity_identifier_namespace(namespace)
    }
    identifiers = [
        identifier.model_copy(update={"source_document_id": None})
        for identifier in read.identity_identifiers
        if _is_public_entity_identifier_namespace(identifier.namespace)
    ]
    return read.model_copy(
        update={"attributes": attributes, "external_ids": external_ids, "identity_identifiers": identifiers}
    )


_PUBLIC_DOSSIER_HIDDEN_KEYS = frozenset(
    {
        "debug",
        "governance",
        "governed_ai_extraction",
        "ingestion",
        "internal_review_trace",
        "origin",
        "permission",
        "permissions",
        "source_asset_id",
        "source_content_sha256",
        "source_document_id",
        "source_document_ids",
        "source_file_name",
        "source_logical_path",
        "source_version_id",
        "tenant_id",
        "tenant_slug",
    }
)


@overload
def _public_dossier_projection(value: DrugDossierResponse) -> DrugDossierResponse: ...


@overload
def _public_dossier_projection(value: DrugProgramSearchResult) -> DrugProgramSearchResult: ...


@overload
def _public_dossier_projection(value: DrugComparisonResult) -> DrugComparisonResult: ...


@overload
def _public_dossier_projection(value: DiseaseDossierResponse) -> DiseaseDossierResponse: ...


@overload
def _public_dossier_projection(value: CompanyDossierResponse) -> CompanyDossierResponse: ...


@overload
def _public_dossier_projection(value: TargetDossierResponse) -> TargetDossierResponse: ...


@overload
def _public_dossier_projection(value: TargetProfileResponse) -> TargetProfileResponse: ...


@overload
def _public_dossier_projection(value: EntityDossierResponse) -> EntityDossierResponse: ...


@overload
def _public_dossier_projection(value: RecordProvenanceResponse) -> RecordProvenanceResponse: ...


def _public_dossier_projection(value: Any) -> Any:
    """Remove internal provenance from public dossier payloads while keeping evidence text."""

    if isinstance(value, EntityRead):
        return _public_entity_read(value)
    if isinstance(value, BaseModel):
        updates: dict[str, Any] = {}
        for field_name in type(value).model_fields:
            child = getattr(value, field_name)
            if field_name in _PUBLIC_DOSSIER_HIDDEN_KEYS:
                updates[field_name] = [] if isinstance(child, list) else {} if isinstance(child, dict) else None
            else:
                updates[field_name] = _public_dossier_projection(child)
        return value.model_copy(update=updates)
    if isinstance(value, list):
        return [_public_dossier_projection(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _public_dossier_projection(item)
            for key, item in value.items()
            if key not in _PUBLIC_DOSSIER_HIDDEN_KEYS
        }
    return value


def _can_view_unpublished_entities(principal: Principal) -> bool:
    """Allow unpublished records only to explicit governance principals."""

    return "*" in principal.scopes or (principal.actor_type == "user" and "governance:read" in principal.scopes)


def _intelligence_service(session: Session, principal: Principal) -> IntelligenceService:
    return IntelligenceService(
        session,
        principal.tenant_id,
        include_unpublished=_can_view_unpublished_entities(principal),
    )


def _effective_public_review_status(
    principal: Principal,
    requested: ReviewStatus | None,
) -> ReviewStatus | None:
    """Clamp public entity reads to reviewed records for ordinary callers."""

    if _can_view_unpublished_entities(principal):
        return requested
    return ReviewStatus.VERIFIED


def _assert_public_entity_visible(entity: Any, principal: Principal) -> None:
    """Make known IDs obey the same review boundary as public search."""

    if _can_view_unpublished_entities(principal):
        return
    if getattr(entity, "review_status", None) != ReviewStatus.VERIFIED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")


def _assert_public_entity_ids_visible(
    session: Session,
    principal: Principal,
    entity_ids: list[str | None],
    *,
    reject_missing: bool = True,
) -> None:
    """Apply the published-entity boundary to domain filters before reading facts.

    Domain endpoints commonly accept several linked entity IDs. Checking those IDs
    at the API boundary prevents a paid Agent query from using a draft target,
    compound, disease or organization as a side door into domain data. Optional
    multi-value filters can set ``reject_missing=False`` so an unknown filter value
    produces no matching rows instead of turning an otherwise valid search into a
    resource-not-found error; existing unpublished entities are still rejected.
    """

    if _can_view_unpublished_entities(principal):
        return
    requested_ids = {entity_id for entity_id in entity_ids if entity_id}
    if not requested_ids:
        return
    entities = session.scalars(
        select(Entity).where(
            Entity.tenant_id == principal.tenant_id,
            Entity.id.in_(requested_ids),
        )
    ).all()
    if reject_missing and len(entities) != len(requested_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    for entity in entities:
        _assert_public_entity_visible(entity, principal)


def _entity_search_applied_filters(
    q: str | None,
    selected_types: list[EntityType],
    review_status: ReviewStatus | None,
) -> list[AppliedFilterRead]:
    """Build the server-normalized applied-filter echo for entity search responses.

    Mirrors the seven professional domains: only conditions the server actually applied
    are echoed, in normalized form, so clients never present draft input as applied
    state.
    """

    return IntelligenceService._applied_filters(
        ("q", "contains", q.strip() if q else None),
        ("entity_types", "in", [item.value for item in selected_types]),
        ("review_status", "eq", review_status.value if review_status else None),
    )


def _entity_search_items(result: EntitySearchResultSet) -> list[EntitySearchItemRead]:
    items: list[EntitySearchItemRead] = []
    for entity in result.items:
        match = result.matches.get(entity.id)
        match_payload = (
            {
                "match_type": match.match_type,
                "match_relation": match.match_relation,
                "matched_value": match.matched_value,
                "namespace": match.namespace,
            }
            if match is not None
            else None
        )
        aliases: list[str] = []
        seen_aliases: set[str] = set()
        for entity_alias in sorted(
            entity.aliases,
            key=lambda item: (item.normalized_alias, item.alias.casefold(), item.id),
        ):
            alias = entity_alias.alias.strip()
            normalized_alias = alias.casefold()
            if not alias or normalized_alias in seen_aliases:
                continue
            aliases.append(alias)
            seen_aliases.add(normalized_alias)
            if len(aliases) == 20:
                break
        items.append(
            EntitySearchItemRead(
                **_public_entity_read(entity).model_dump(),
                aliases=aliases,
                match=match_payload,
            )
        )
    return items


@app.get(
    "/api/v1/admin/search/status",
    response_model=SearchProjectionStatusRead,
    tags=["data-factory"],
)
def search_projection_status(principal: PrincipalDep) -> SearchProjectionStatusRead:
    principal.require("ingestion:read")
    settings = get_settings()
    gateway = get_opensearch_gateway()
    status_snapshot = gateway.status()
    consumer = SearchProjectionConsumer(
        get_session_factory(),
        gateway,
        object_store_module.build_object_store(settings),
        settings,
    )
    return SearchProjectionStatusRead(
        available=status_snapshot.available,
        version=status_snapshot.version,
        cluster_name=status_snapshot.cluster_name,
        cluster_status=status_snapshot.cluster_status,
        aliases=status_snapshot.aliases,
        deliveries=consumer.delivery_counts(),
        error=status_snapshot.error,
    )


@app.get(
    "/internal/v1/commercial/access",
    response_model=CommercialAccessRead,
    tags=["internal-commercial"],
)
def commercial_access(principal: PrincipalDep, session: SessionDep) -> CommercialAccessRead:
    snapshot = _commercial_service(session, principal).access_snapshot()
    return CommercialAccessRead.model_validate(snapshot)


@app.post(
    "/internal/v1/commercial/estimate",
    response_model=CommercialEstimateRead,
    tags=["internal-commercial"],
)
def estimate_commercial_usage(
    payload: CommercialEstimateRequest,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialEstimateRead:
    estimate = _commercial_service(session, principal).estimate(
        payload.billing_class,
        payload.requested_result_limit,
        payload.requested_compute_units,
    )
    return CommercialEstimateRead.model_validate(estimate)


@app.get(
    "/internal/v1/commercial/usage-summary",
    response_model=CommercialUsageSummaryRead,
    tags=["internal-commercial"],
)
def commercial_usage_summary(principal: PrincipalDep, session: SessionDep) -> CommercialUsageSummaryRead:
    summary = _commercial_service(session, principal).usage_summary()
    return CommercialUsageSummaryRead.model_validate(summary)


@app.get(
    "/api/v1/commercial/overview",
    response_model=CommercialOverviewRead,
    tags=["commercial"],
)
def read_commercial_overview(principal: PrincipalDep, session: SessionDep) -> CommercialOverviewRead:
    _require_human_commercial(principal, "commercial:read")
    return CommercialOverviewRead.model_validate(commercial_overview(session, principal.tenant_id))


@app.post(
    "/api/v1/commercial/adjustments",
    response_model=CommercialAdjustmentRead,
    tags=["commercial"],
)
def create_commercial_adjustment(
    payload: CommercialUsageAdjustmentCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialAdjustmentRead:
    try:
        adjustment = _commercial_accounting_service(session, principal).adjust_usage(
            UsageAdjustmentCommand(
                subscription_key=payload.subscription_key,
                adjustment_key=payload.adjustment_key,
                units_delta=payload.units_delta,
                reason=payload.reason,
                request_id=request.state.request_id,
                metadata=payload.metadata,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _adjustment_read(adjustment)


@app.post(
    "/api/v1/commercial/settlements/{settlement_id}/reversal",
    response_model=CommercialAdjustmentRead,
    tags=["commercial"],
)
def reverse_commercial_settlement(
    settlement_id: str,
    payload: CommercialReversalCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialAdjustmentRead:
    try:
        adjustment = _commercial_accounting_service(session, principal).reverse_settlement(
            settlement_id,
            ReversalCommand(payload.adjustment_key, payload.reason, request.state.request_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _adjustment_read(adjustment)


@app.post(
    "/api/v1/commercial/adjustments/{adjustment_id}/reversal",
    response_model=CommercialAdjustmentRead,
    tags=["commercial"],
)
def reverse_commercial_adjustment(
    adjustment_id: str,
    payload: CommercialReversalCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialAdjustmentRead:
    try:
        adjustment = _commercial_accounting_service(session, principal).reverse_adjustment(
            adjustment_id,
            ReversalCommand(payload.adjustment_key, payload.reason, request.state.request_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _adjustment_read(adjustment)


@app.post(
    "/api/v1/commercial/reservations/expire",
    response_model=CommercialExpirationRead,
    tags=["commercial"],
)
def expire_commercial_reservations(
    payload: CommercialExpirationRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialExpirationRead:
    outcome = _commercial_accounting_service(session, principal).expire_stale_reservations(
        request_id=request.state.request_id,
        limit=payload.limit,
    )
    return CommercialExpirationRead(
        expired_reservations=outcome.expired_reservations,
        released_units=format(outcome.released_units, "f"),
        completed_at=outcome.completed_at,
    )


@app.post(
    "/api/v1/commercial/reconciliations",
    response_model=CommercialReconciliationRead,
    tags=["commercial"],
)
def reconcile_commercial_subscription(
    payload: CommercialReconciliationCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialReconciliationRead:
    try:
        run = _commercial_accounting_service(session, principal).reconcile(
            payload.subscription_key,
            run_key=payload.run_key,
            request_id=request.state.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _reconciliation_read(run)


@app.post(
    "/api/v1/commercial/statements",
    response_model=BillingStatementRead,
    tags=["commercial"],
)
def create_billing_statement(
    payload: BillingStatementCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> BillingStatementRead:
    try:
        statement = _commercial_accounting_service(session, principal).create_statement(
            BillingStatementCommand(
                subscription_key=payload.subscription_key,
                statement_key=payload.statement_key,
                period_start=payload.period_start,
                period_end=payload.period_end,
                revision=payload.revision,
                request_id=request.state.request_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _statement_read(statement)


@app.get(
    "/api/v1/commercial/statements/{statement_id}",
    response_model=BillingStatementRead,
    tags=["commercial"],
)
def read_billing_statement(
    statement_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> BillingStatementRead:
    _require_human_commercial(principal, "commercial:read")
    statement = session.scalar(
        select(BillingPeriodStatement).where(
            BillingPeriodStatement.tenant_id == principal.tenant_id,
            BillingPeriodStatement.id == statement_id,
        )
    )
    if statement is None:
        raise HTTPException(status_code=404, detail="Billing statement not found")
    return _statement_read(statement)


@app.post(
    "/internal/v1/commercial/reservations",
    response_model=CommercialReservationRead,
    tags=["internal-commercial"],
)
def reserve_commercial_usage(
    payload: CommercialReserveRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialReservationRead:
    settings = get_settings()
    try:
        network_fingerprint = validate_internal_network_fingerprint(
            request.headers.get(NETWORK_FINGERPRINT_HEADER),
            settings,
        )
    except CorrelationSignalError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        outcome = _commercial_service(session, principal).reserve(
            ReserveCommand(
                billing_class=payload.billing_class,
                idempotency_key=payload.idempotency_key,
                request_arguments=payload.request_arguments,
                requested_result_limit=payload.requested_result_limit,
                max_billable_units=payload.max_billable_units,
                request_id=request.state.request_id,
                requested_compute_units=payload.requested_compute_units,
                network_fingerprint=network_fingerprint,
                correlation_key_id=settings.mcp_correlation_key_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _reservation_read(outcome, session)


@app.post(
    "/internal/v1/commercial/reservations/{reservation_id}/settle",
    response_model=CommercialReservationRead,
    tags=["internal-commercial"],
)
def settle_commercial_usage(
    reservation_id: str,
    payload: CommercialSettlementRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialReservationRead:
    outcome: SettlementOutcome = _commercial_service(session, principal).settle(
        SettleCommand(
            reservation_id=reservation_id,
            result_count=payload.result_count,
            result=payload.result,
            metrics=payload.metrics,
            request_id=request.state.request_id,
        )
    )
    return CommercialReservationRead(
        reservation_id=outcome.reservation.id,
        state=outcome.reservation.state,
        billing_class=outcome.reservation.billing_class,
        estimated_units=format(outcome.reservation.estimated_units, "f"),
        reserved_units=format(outcome.reservation.reserved_units, "f"),
        requested_compute_units=format(outcome.reservation.requested_compute_units, "f"),
        lease_expires_at=outcome.reservation.lease_expires_at,
        page_depth=outcome.reservation.page_depth,
        replayed=outcome.replayed,
        settlement=_settlement_read(outcome.settlement, outcome.usage_event),
    )


@app.post(
    "/internal/v1/commercial/reservations/{reservation_id}/release",
    response_model=CommercialReservationRead,
    tags=["internal-commercial"],
)
def release_commercial_usage(
    reservation_id: str,
    payload: CommercialReleaseRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialReservationRead:
    outcome = _commercial_service(session, principal).release(
        reservation_id,
        reason=payload.reason,
        request_id=request.state.request_id,
    )
    return _reservation_read(outcome, session)


@app.post(
    "/internal/v1/exports",
    response_model=DataExportRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["internal-commercial"],
)
def create_data_export(
    payload: DataExportCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataExportRead:
    job = _agent_export_service(session, principal).create(
        principal,
        CreateExportCommand(
            dataset=payload.dataset,
            export_format=payload.export_format,
            filters=payload.filters,
            fields=payload.fields,
            max_records=payload.max_records,
            max_billable_units=payload.max_billable_units,
            idempotency_key=payload.idempotency_key,
        ),
    )
    return _export_read(job)


@app.get(
    "/internal/v1/exports/{job_id}",
    response_model=DataExportRead,
    tags=["internal-commercial"],
)
def read_data_export(
    job_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataExportRead:
    return _export_read(_agent_export_service(session, principal).get(principal, job_id))


@app.post(
    "/internal/v1/exports/{job_id}/cancel",
    response_model=DataExportRead,
    tags=["internal-commercial"],
)
def cancel_data_export(
    job_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataExportRead:
    return _export_read(_agent_export_service(session, principal).cancel(principal, job_id))


@app.get(
    "/internal/v1/exports/{job_id}/chunks",
    response_model=DataExportChunkRead,
    tags=["internal-commercial"],
)
def read_data_export_chunk(
    job_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=1000),
    cursor: str | None = Query(default=None, max_length=4096),
) -> DataExportChunkRead:
    chunk = _agent_export_service(session, principal).read_chunk(
        principal,
        job_id,
        limit=limit,
        cursor=cursor,
    )
    return DataExportChunkRead(
        items=chunk.items,
        count=chunk.count,
        next_cursor=chunk.next_cursor,
        manifest=chunk.manifest,
    )


@app.get(
    "/api/v1/commercial/exports",
    response_model=list[DataExportRead],
    tags=["commercial"],
)
def list_data_exports(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DataExportRead]:
    _require_human_commercial(principal, "commercial:read")
    jobs = build_export_service(session, get_settings()).list_for_operator(principal, limit=limit)
    return [_export_read(job) for job in jobs]


@app.post(
    "/api/v1/commercial/exports/{job_id}/approve",
    response_model=DataExportRead,
    tags=["commercial"],
)
def approve_data_export(
    job_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataExportRead:
    _require_human_commercial(principal, "commercial:write")
    return _export_read(build_export_service(session, get_settings()).approve(principal, job_id))


@app.post(
    "/api/v1/commercial/exports/{job_id}/cancel",
    response_model=DataExportRead,
    tags=["commercial"],
)
def cancel_data_export_as_operator(
    job_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataExportRead:
    _require_human_commercial(principal, "commercial:write")
    return _export_read(build_export_service(session, get_settings()).cancel_as_operator(principal, job_id))


@app.get(
    "/api/v1/commercial/data-lifecycle/retention-policies",
    response_model=list[DataRetentionPolicyRead],
    tags=["commercial"],
)
def list_data_retention_policies(
    principal: PrincipalDep,
    session: SessionDep,
) -> list[DataRetentionPolicyRead]:
    policies = _data_lifecycle_service(session, principal, "commercial:read").list_policies(principal)
    return [DataRetentionPolicyRead.model_validate(policy) for policy in policies]


@app.put(
    "/api/v1/commercial/data-lifecycle/retention-policies/export-artifacts",
    response_model=DataRetentionPolicyRead,
    tags=["commercial"],
)
def upsert_export_retention_policy(
    payload: DataRetentionPolicyUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataRetentionPolicyRead:
    policy = _data_lifecycle_service(session, principal, "commercial:write").upsert_export_policy(
        principal,
        retention_seconds=payload.retention_seconds,
        legal_basis=payload.legal_basis,
        geographic_scope=payload.geographic_scope,
        active=payload.active,
        request_id=request.state.request_id,
    )
    return DataRetentionPolicyRead.model_validate(policy)


@app.put(
    "/api/v1/commercial/data-lifecycle/retention-policies/source-assets",
    response_model=DataRetentionPolicyRead,
    tags=["commercial"],
)
def upsert_source_retention_policy(
    payload: DataRetentionPolicyUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataRetentionPolicyRead:
    policy = _data_lifecycle_service(session, principal, "commercial:write").upsert_source_policy(
        principal,
        retention_seconds=payload.retention_seconds,
        legal_basis=payload.legal_basis,
        geographic_scope=payload.geographic_scope,
        active=payload.active,
        request_id=request.state.request_id,
    )
    return DataRetentionPolicyRead.model_validate(policy)


@app.get(
    "/api/v1/commercial/data-lifecycle/legal-holds",
    response_model=list[LegalHoldRead],
    tags=["commercial"],
)
def list_legal_holds(
    principal: PrincipalDep,
    session: SessionDep,
    active_only: bool = Query(default=False),
) -> list[LegalHoldRead]:
    holds = _data_lifecycle_service(session, principal, "commercial:read").list_holds(
        principal,
        active_only=active_only,
    )
    return [LegalHoldRead.model_validate(hold) for hold in holds]


@app.post(
    "/api/v1/commercial/data-lifecycle/legal-holds",
    response_model=LegalHoldRead,
    status_code=status.HTTP_201_CREATED,
    tags=["commercial"],
)
def place_legal_hold(
    payload: LegalHoldCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> LegalHoldRead:
    hold = _data_lifecycle_service(session, principal, "commercial:write").place_hold(
        principal,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        matter_reference=payload.matter_reference,
        reason=payload.reason,
        request_id=request.state.request_id,
    )
    return LegalHoldRead.model_validate(hold)


@app.post(
    "/api/v1/commercial/data-lifecycle/legal-holds/{hold_id}/release",
    response_model=LegalHoldRead,
    tags=["commercial"],
)
def release_legal_hold(
    hold_id: str,
    payload: LegalHoldRelease,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> LegalHoldRead:
    hold = _data_lifecycle_service(session, principal, "commercial:write").release_hold(
        principal,
        hold_id,
        reason=payload.reason,
        request_id=request.state.request_id,
    )
    return LegalHoldRead.model_validate(hold)


@app.get(
    "/api/v1/commercial/data-lifecycle/export-candidates",
    response_model=list[DataExportRead],
    tags=["commercial"],
)
def list_export_purge_candidates(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DataExportRead]:
    jobs = _data_lifecycle_service(session, principal, "commercial:read").export_candidates(
        principal,
        limit=limit,
    )
    return [_export_read(job) for job in jobs]


def _source_asset_impact_read(impact: SourceAssetImpact) -> SourceAssetImpactRead:
    return SourceAssetImpactRead(
        id=impact.asset.id,
        data_source_id=impact.asset.data_source_id,
        logical_path=impact.asset.logical_path,
        file_name=impact.asset.file_name,
        state=impact.asset.state.value,
        missing_since=impact.asset.missing_since,
        retention_eligible=impact.retention_eligible,
        version_count=impact.version_count,
        raw_object_count=impact.raw_object_count,
        extracted_object_count=impact.extracted_object_count,
        extraction_run_count=impact.extraction_run_count,
        staged_fact_count=impact.staged_fact_count,
        published_fact_count=impact.published_fact_count,
        evidence_claim_count=impact.evidence_claim_count,
        knowledge_citation_count=impact.knowledge_citation_count,
        retrieval_projection_count=impact.retrieval_projection_count,
        shared_document_count=impact.shared_document_count,
        other_document_reference_count=impact.other_document_reference_count,
        blockers=impact.blockers,
    )


@app.get(
    "/api/v1/commercial/data-lifecycle/source-candidates",
    response_model=list[SourceAssetImpactRead],
    tags=["commercial"],
)
def list_source_purge_candidates(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SourceAssetImpactRead]:
    impacts = _data_lifecycle_service(session, principal, "commercial:read").source_candidates(
        principal,
        limit=limit,
    )
    return [_source_asset_impact_read(impact) for impact in impacts]


@app.get(
    "/api/v1/commercial/data-lifecycle/source-assets/deleted",
    response_model=list[DeletedSourceAssetRead],
    tags=["commercial"],
)
def list_deleted_source_assets(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DeletedSourceAssetRead]:
    assets = _data_lifecycle_service(session, principal, "commercial:read").deleted_source_assets(
        principal,
        limit=limit,
    )
    return [DeletedSourceAssetRead.model_validate(asset) for asset in assets]


@app.get(
    "/api/v1/commercial/data-lifecycle/source-assets/{asset_id}/impact",
    response_model=SourceAssetImpactRead,
    tags=["commercial"],
)
def get_source_asset_purge_impact(
    asset_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> SourceAssetImpactRead:
    impact = _data_lifecycle_service(session, principal, "commercial:read").source_asset_impact(
        principal,
        asset_id,
    )
    return _source_asset_impact_read(impact)


@app.post(
    "/api/v1/commercial/data-lifecycle/source-assets/{asset_id}/purge",
    response_model=DataLifecyclePurgeRead,
    tags=["commercial"],
)
def purge_source_asset(
    asset_id: str,
    payload: DataLifecyclePurgeRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataLifecyclePurgeRead:
    outcome = _data_lifecycle_service(session, principal, "commercial:write").purge_source_asset(
        principal,
        asset_id,
        idempotency_key=payload.idempotency_key,
        reason=payload.reason,
        request_id=request.state.request_id,
    )
    return DataLifecyclePurgeRead(
        event=DataLifecycleEventRead.model_validate(outcome.event),
        replayed=outcome.replayed,
    )


@app.post(
    "/api/v1/commercial/data-lifecycle/source-assets/{asset_id}/reauthorize",
    response_model=DataLifecyclePurgeRead,
    tags=["commercial"],
)
def reauthorize_source_asset(
    asset_id: str,
    payload: DataLifecyclePurgeRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataLifecyclePurgeRead:
    outcome = _data_lifecycle_service(session, principal, "commercial:write").reauthorize_source_asset(
        principal,
        asset_id,
        idempotency_key=payload.idempotency_key,
        reason=payload.reason,
        request_id=request.state.request_id,
    )
    return DataLifecyclePurgeRead(
        event=DataLifecycleEventRead.model_validate(outcome.event),
        replayed=outcome.replayed,
    )


@app.post(
    "/api/v1/commercial/data-lifecycle/exports/{job_id}/purge",
    response_model=DataLifecyclePurgeRead,
    tags=["commercial"],
)
def purge_export_artifacts(
    job_id: str,
    payload: DataLifecyclePurgeRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataLifecyclePurgeRead:
    outcome = _data_lifecycle_service(session, principal, "commercial:write").purge_export(
        principal,
        job_id,
        idempotency_key=payload.idempotency_key,
        reason=payload.reason,
        request_id=request.state.request_id,
    )
    return DataLifecyclePurgeRead(
        event=DataLifecycleEventRead.model_validate(outcome.event),
        replayed=outcome.replayed,
    )


@app.get(
    "/api/v1/commercial/data-lifecycle/events",
    response_model=list[DataLifecycleEventRead],
    tags=["commercial"],
)
def list_data_lifecycle_events(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DataLifecycleEventRead]:
    events = _data_lifecycle_service(session, principal, "commercial:read").list_events(
        principal,
        limit=limit,
    )
    return [DataLifecycleEventRead.model_validate(event) for event in events]


@app.get(
    "/api/v1/commercial/billing-accounts",
    response_model=list[BillingAccountRead],
    tags=["commercial"],
)
def list_billing_accounts(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[BillingAccountRead]:
    _require_human_commercial(principal, "commercial:read")
    items = BillingOperationsService(session, principal).list_accounts(limit=limit)
    return [BillingAccountRead.model_validate(item) for item in items]


@app.post(
    "/api/v1/commercial/billing-accounts/{account_id}/provider-mapping",
    response_model=BillingAccountRead,
    tags=["commercial"],
)
def update_billing_customer_mapping(
    account_id: str,
    payload: BillingCustomerMappingUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> BillingAccountRead:
    _require_human_commercial(principal, "commercial:write")
    try:
        item = BillingOperationsService(session, principal).set_customer_mapping(
            account_id,
            external_customer_reference=payload.external_customer_reference,
            reason=payload.reason,
            request_id=request.state.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BillingAccountRead.model_validate(item)


@app.get(
    "/api/v1/commercial/billing-deliveries",
    response_model=list[BillingDeliveryRead],
    tags=["commercial"],
)
def list_billing_deliveries(
    principal: PrincipalDep,
    session: SessionDep,
    delivery_state: Literal["all", "pending", "processing", "retry", "succeeded", "dead"] = "all",
    limit: int = Query(default=200, ge=1, le=500),
) -> list[BillingDeliveryRead]:
    _require_human_commercial(principal, "commercial:read")
    items = BillingOperationsService(session, principal).list_deliveries(
        state=delivery_state,
        limit=limit,
    )
    return [BillingDeliveryRead.model_validate(item) for item in items]


@app.post(
    "/api/v1/commercial/billing-deliveries/{delivery_id}/replay",
    response_model=BillingDeliveryRead,
    tags=["commercial"],
)
def replay_billing_delivery(
    delivery_id: str,
    payload: BillingDeliveryReplayRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> BillingDeliveryRead:
    _require_human_commercial(principal, "commercial:write")
    try:
        item = BillingOperationsService(session, principal).replay_delivery(
            delivery_id,
            reason=payload.reason,
            request_id=request.state.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BillingDeliveryRead.model_validate(item)


@app.get(
    "/api/v1/commercial/billing-disputes",
    response_model=list[BillingDisputeRead],
    tags=["commercial"],
)
def list_billing_disputes(
    principal: PrincipalDep,
    session: SessionDep,
    dispute_status: Literal["all", "open", "investigating", "resolved", "rejected", "cancelled"] = "all",
    limit: int = Query(default=200, ge=1, le=500),
) -> list[BillingDisputeRead]:
    _require_human_commercial(principal, "commercial:read")
    service = BillingDisputeService(
        session,
        principal,
        sla_hours=get_settings().billing_dispute_sla_hours,
    )
    return [BillingDisputeRead.model_validate(item) for item in service.list(status=dispute_status, limit=limit)]


@app.post(
    "/api/v1/commercial/billing-disputes",
    response_model=BillingDisputeRead,
    status_code=status.HTTP_201_CREATED,
    tags=["commercial"],
)
def create_billing_dispute(
    payload: BillingDisputeCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> BillingDisputeRead:
    _require_human_commercial(principal, "commercial:write")
    try:
        item = BillingDisputeService(
            session,
            principal,
            sla_hours=get_settings().billing_dispute_sla_hours,
        ).create(
            CreateBillingDisputeCommand(
                dispute_key=payload.dispute_key,
                statement_id=payload.statement_id,
                invoice_reference_id=payload.invoice_reference_id,
                category=payload.category,
                disputed_units=payload.disputed_units,
                subject=payload.subject,
                description=payload.description,
            ),
            request_id=request.state.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BillingDisputeRead.model_validate(item)


@app.post(
    "/api/v1/commercial/billing-disputes/{dispute_id}/transition",
    response_model=BillingDisputeRead,
    tags=["commercial"],
)
def transition_billing_dispute(
    dispute_id: str,
    payload: BillingDisputeTransition,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> BillingDisputeRead:
    _require_human_commercial(principal, "commercial:write")
    try:
        item = BillingDisputeService(
            session,
            principal,
            sla_hours=get_settings().billing_dispute_sla_hours,
        ).transition(
            dispute_id,
            TransitionBillingDisputeCommand(
                operation_key=payload.operation_key,
                expected_version=payload.expected_version,
                action=payload.action,
                notes=payload.notes,
                assigned_to=payload.assigned_to,
                adjustment_key=payload.adjustment_key,
                credit_units=payload.credit_units,
            ),
            request_id=request.state.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BillingDisputeRead.model_validate(item)


@app.get(
    "/api/v1/commercial/clients",
    response_model=list[CommercialClientRead],
    tags=["commercial"],
)
def list_commercial_clients(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[CommercialClientRead]:
    _require_human_commercial(principal, "commercial:read")
    items = CommercialOperationsService(session, principal).list_clients(limit=limit)
    return [CommercialClientRead.model_validate(item) for item in items]


@app.post(
    "/api/v1/commercial/clients/{client_id}/status",
    response_model=CommercialClientRead,
    tags=["commercial"],
)
def update_commercial_client_status(
    client_id: str,
    payload: CommercialClientStatusUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialClientRead:
    _require_human_commercial(principal, "commercial:write")
    try:
        item = CommercialOperationsService(session, principal).set_client_active(
            client_id,
            active=payload.active,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CommercialClientRead.model_validate(item)


@app.get(
    "/api/v1/commercial/risk-events",
    response_model=list[CommercialRiskEventRead],
    tags=["commercial"],
)
def list_commercial_risk_events(
    principal: PrincipalDep,
    session: SessionDep,
    case_status: Literal["all", "open", "acknowledged", "resolved", "dismissed"] = "all",
    limit: int = Query(default=200, ge=1, le=500),
) -> list[CommercialRiskEventRead]:
    _require_human_commercial(principal, "commercial:read")
    items = CommercialOperationsService(session, principal).list_risk_events(
        status=case_status,
        limit=limit,
    )
    return [CommercialRiskEventRead.model_validate(item) for item in items]


@app.get(
    "/api/v1/commercial/risk-events/page",
    response_model=CommercialRiskEventPageRead,
    tags=["commercial"],
)
def page_commercial_risk_events(
    principal: PrincipalDep,
    session: SessionDep,
    case_status: Literal["all", "open", "acknowledged", "resolved", "dismissed"] = "all",
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None, min_length=20, max_length=4096),
) -> CommercialRiskEventPageRead:
    _require_human_commercial(principal, "commercial:read")
    settings = get_settings()
    try:
        page = CommercialOperationsService(session, principal).list_risk_event_page(
            status=case_status,
            limit=limit,
            cursor=cursor,
            cursor_codec=RiskCursorCodec(
                settings.effective_mcp_cursor_signing_secret,
                ttl_seconds=settings.mcp_cursor_ttl_seconds,
                max_token_chars=settings.mcp_cursor_max_token_chars,
            ),
        )
    except RiskCursorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CommercialRiskEventPageRead(
        items=[CommercialRiskEventRead.model_validate(item) for item in page.items],
        total_items=page.total_items,
        next_cursor=page.next_cursor,
    )


@app.post(
    "/api/v1/commercial/risk-events/{event_id}/review",
    response_model=CommercialRiskEventRead,
    tags=["commercial"],
)
def review_commercial_risk_event(
    event_id: str,
    payload: CommercialRiskReview,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialRiskEventRead:
    _require_human_commercial(principal, "commercial:write")
    item = CommercialOperationsService(session, principal).review_risk_event(
        event_id,
        status=payload.status,
        notes=payload.notes,
    )
    return CommercialRiskEventRead.model_validate(item)


@app.get(
    "/internal/v1/domain/entities",
    response_model=AgentEntitySearchResult,
    tags=["internal-domain"],
)
def search_entities_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    billing_class: Literal["entity.search", "entity.resolve"],
    q: str = Query(min_length=1, max_length=500),
    entity_type: EntityType | None = None,
    review_status: ReviewStatus | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: EntitySortField | None = None,
    sort_direction: SortDirection | None = None,
    entity_types: Annotated[list[EntityType] | None, Query()] = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentEntitySearchResult:
    principal.require("entities:read")
    effective_review_status = _effective_public_review_status(principal, review_status)
    effective_sort = _validated_sort(
        sort,
        ENTITY_SORT_FIELDS,
        default_field="relevance",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    selected_types = _normalize_entity_types(entity_type, entity_types or [])
    arguments: dict[str, object] = {"q": q, "limit": limit}
    if len(selected_types) == 1:
        arguments["entity_type"] = selected_types[0].value
    elif selected_types:
        arguments["entity_types"] = [item.value for item in selected_types]
    if effective_review_status is not None:
        arguments["review_status"] = effective_review_status.value
    if cursor is not None:
        arguments["cursor"] = cursor
    arguments["sort"] = [clause.token for clause in effective_sort]
    service = _commercial_service(session, principal)
    reservation = service.authorize_paginated_query(
        reservation_id,
        billing_class=billing_class,
        request_arguments=arguments,
        page_size=limit,
    )
    try:
        result = EntitySearchService(session, principal.tenant_id, get_settings()).search(
            q,
            entity_type,
            limit,
            reservation.page_offset,
            effective_review_status,
            effective_sort[0].field,
            effective_sort[0].direction,
            selected_types,
            effective_sort,
            hide_unpublished_facets=not _can_view_unpublished_entities(principal),
        )
    except SearchProjectionError as exc:
        raise HTTPException(status_code=503, detail="Entity search projection unavailable") from exc
    next_offset = reservation.page_offset + len(result.items)
    next_cursor = service.issue_next_cursor(
        reservation,
        next_offset=next_offset,
        has_more=next_offset < result.total,
    )
    return AgentEntitySearchResult(
        query_schema_version=ENTITY_SEARCH_SCHEMA_VERSION,
        applied_filters=_entity_search_applied_filters(q, selected_types, effective_review_status),
        items=_entity_search_items(result),
        limit=limit,
        page_depth=reservation.page_depth,
        next_cursor=next_cursor,
        sort_by=effective_sort[0].field,
        sort_direction=effective_sort[0].direction,
        sort=_sort_reads(effective_sort),
        engine=result.engine,
        facets=result.facets,
    )


@app.get(
    "/internal/v1/domain/entities/{entity_id}/dossier",
    response_model=EntityDossierResponse,
    tags=["internal-domain"],
)
def get_entity_dossier_for_agent(
    entity_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    limit: int = Query(default=50, ge=1, le=100),
) -> EntityDossierResponse:
    principal.require("dossiers:read")
    result_limit = dossier_result_capacity(limit)
    _commercial_service(session, principal).authorize_paginated_query(
        reservation_id,
        billing_class="entity.dossier",
        request_arguments={"entity_id": entity_id, "domain_limit": limit, "limit": result_limit},
        page_size=result_limit,
    )
    dossier = _intelligence_service(session, principal).entity_dossier(entity_id, limit)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    _assert_public_entity_visible(dossier.entity, principal)
    return dossier


@app.get(
    "/internal/v1/domain/targets/{target_id}/evidence",
    response_model=AgentPageResult[TargetEvidenceRead],
    tags=["internal-domain"],
)
def search_target_evidence_for_agent(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    evidence_type: Literal[
        "genetic_association",
        "expression",
        "functional",
        "translational",
        "biomarker",
        "safety",
    ]
    | None = Query(default=None),
    direction: Literal["supports", "opposes", "neutral", "unknown"] | None = Query(default=None),
    disease_entity_id: str | None = Query(default=None, min_length=1, max_length=36),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentPageResult[TargetEvidenceRead]:
    principal.require("targets:read")
    arguments: dict[str, object] = {"target_entity_id": target_id, "limit": limit}
    for name, value in (
        ("evidence_type", evidence_type),
        ("direction", direction),
        ("disease_entity_id", disease_entity_id),
        ("cursor", cursor),
    ):
        if value is not None:
            arguments[name] = value
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="target.evidence.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[target_id, disease_entity_id],
        fetch=lambda offset, fetch_limit: intelligence.target_evidence_for_entity(
            target_id,
            fetch_limit,
            offset,
            evidence_type=evidence_type,
            direction=direction,
            disease_entity_id=disease_entity_id,
        ),
    )


@app.get(
    "/internal/v1/domain/targets/{target_id}/bioactivities",
    response_model=AgentPageResult[BioactivityRead],
    tags=["internal-domain"],
)
def search_bioactivities_for_agent(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    standard_type: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentPageResult[BioactivityRead]:
    principal.require("activities:read")
    arguments: dict[str, object] = {"target_entity_id": target_id, "limit": limit}
    if standard_type is not None:
        arguments["standard_type"] = standard_type
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="bioactivity.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[target_id],
        fetch=lambda offset, fetch_limit: intelligence.bioactivities(target_id, standard_type, fetch_limit, offset),
    )


@app.get(
    "/internal/v1/domain/targets/{target_id}/sar-comparison",
    response_model=AgentPageResult[SarActivityRead],
    tags=["internal-domain"],
)
def compare_target_sar_for_agent(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    standard_type: str | None = Query(default=None, max_length=120),
    assay_type: str | None = Query(default=None, max_length=120),
    assay_format: str | None = Query(default=None, max_length=160),
    organism: str | None = Query(default=None, max_length=160),
    cell_line: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentPageResult[SarActivityRead]:
    principal.require("activities:read")
    arguments: dict[str, object] = {"target_entity_id": target_id, "limit": limit}
    filters = {
        "standard_type": standard_type,
        "assay_type": assay_type,
        "assay_format": assay_format,
        "organism": organism,
        "cell_line": cell_line,
    }
    arguments.update({key: value for key, value in filters.items() if value is not None})
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="sar.compare",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[target_id],
        fetch=lambda offset, fetch_limit: intelligence.sar_comparison(
            target_id,
            standard_type=standard_type,
            assay_type=assay_type,
            assay_format=assay_format,
            organism=organism,
            cell_line=cell_line,
            limit=fetch_limit,
            offset=offset,
        ).items,
    )


@app.get(
    "/internal/v1/domain/targets/{target_id}/competitive-programs",
    response_model=AgentPageResult[CompetitiveProgramRead],
    tags=["internal-domain"],
)
def search_competitive_programs_for_agent(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    drug_entity_id: str | None = Query(default=None, min_length=36, max_length=36),
    disease_entity_id: str | None = Query(default=None, max_length=36),
    organization_entity_id: str | None = Query(default=None, max_length=36),
    program_status: Literal["active", "inactive", "unknown"] | None = None,
    organization_role: (
        Literal["originator", "collaborator", "licensee", "licensor", "manufacturer", "other"] | None
    ) = None,
    organization_type: str | None = Query(default=None, min_length=1, max_length=120),
    organization_country_region: str | None = Query(default=None, min_length=1, max_length=120),
    modality: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    innovation_type: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    therapeutic_area: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    drug_category: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    global_phase: DevelopmentPhase | None = None,
    china_phase: DevelopmentPhase | None = None,
    global_phase_started_from: Annotated[datetime | None, Query()] = None,
    global_phase_started_to: Annotated[datetime | None, Query()] = None,
    china_phase_started_from: Annotated[datetime | None, Query()] = None,
    china_phase_started_to: Annotated[datetime | None, Query()] = None,
    development_rights_region: str | None = Query(default=None, max_length=240),
    commercialization_rights_region: str | None = Query(default=None, max_length=240),
    program_tag: Annotated[list[PipelineProgramTagQueryValue] | None, Query(max_length=20)] = None,
    milestone_type: str | None = Query(default=None, max_length=120),
    milestone_from: Annotated[datetime | None, Query()] = None,
    milestone_to: Annotated[datetime | None, Query()] = None,
    has_clinical_results: bool | None = Query(default=None),
    clinical_result_evaluation: TrialResultEvaluation | None = None,
    has_deal: bool | None = Query(default=None),
    deal_currency: str | None = Query(default=None, pattern=r"^[A-Z]{3}$"),
    deal_total_potential_amount_min: float | None = Query(default=None, ge=0),
    deal_total_potential_amount_max: float | None = Query(default=None, ge=0),
    sort_by: PipelineSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[CompetitiveProgramRead]:
    principal.require("pipelines:read")
    effective_sort = _validated_sort(
        sort,
        PIPELINE_SORT_FIELDS,
        default_field="status_date",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    modality = _normalized_repeated_filter(modality)
    innovation_type = _normalized_repeated_filter(innovation_type)
    therapeutic_area = _normalized_repeated_filter(therapeutic_area)
    drug_category = _normalized_repeated_filter(drug_category)
    program_tag = _normalized_repeated_filter(program_tag)
    arguments: dict[str, object] = {"target_entity_id": target_id, "limit": limit}
    global_phase_started_from, global_phase_started_to = _validated_utc_datetime_range(
        global_phase_started_from,
        global_phase_started_to,
        start_field="global_phase_started_from",
        end_field="global_phase_started_to",
    )
    china_phase_started_from, china_phase_started_to = _validated_utc_datetime_range(
        china_phase_started_from,
        china_phase_started_to,
        start_field="china_phase_started_from",
        end_field="china_phase_started_to",
    )
    milestone_from, milestone_to = _validated_utc_datetime_range(
        milestone_from,
        milestone_to,
        start_field="milestone_from",
        end_field="milestone_to",
    )
    deal_total_potential_amount_min, deal_total_potential_amount_max = _validated_pipeline_signal_filters(
        has_clinical_results,
        clinical_result_evaluation,
        has_deal,
        deal_currency,
        deal_total_potential_amount_min,
        deal_total_potential_amount_max,
    )
    filters: dict[str, object | None] = {
        "drug_entity_id": drug_entity_id,
        "disease_entity_id": disease_entity_id,
        "organization_entity_id": organization_entity_id,
        "program_status": program_status,
        "organization_role": organization_role,
        "organization_type": organization_type,
        "organization_country_region": organization_country_region,
        "modality": modality,
        "innovation_type": innovation_type,
        "therapeutic_area": therapeutic_area,
        "drug_category": drug_category,
        "global_phase": global_phase.value if global_phase else None,
        "china_phase": china_phase.value if china_phase else None,
        "global_phase_started_from": global_phase_started_from,
        "global_phase_started_to": global_phase_started_to,
        "china_phase_started_from": china_phase_started_from,
        "china_phase_started_to": china_phase_started_to,
        "development_rights_region": development_rights_region,
        "commercialization_rights_region": commercialization_rights_region,
        "program_tag": program_tag,
        "milestone_type": milestone_type,
        "milestone_from": milestone_from,
        "milestone_to": milestone_to,
        "has_clinical_results": has_clinical_results,
        "clinical_result_evaluation": clinical_result_evaluation.value if clinical_result_evaluation else None,
        "has_deal": has_deal,
        "deal_currency": deal_currency,
        "deal_total_potential_amount_min": deal_total_potential_amount_min,
        "deal_total_potential_amount_max": deal_total_potential_amount_max,
        "sort": [clause.token for clause in effective_sort],
    }
    arguments.update(
        {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in filters.items()
            if value is not None
        }
    )
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="pipeline.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[target_id, drug_entity_id, disease_entity_id, organization_entity_id],
        fetch=lambda offset, fetch_limit: intelligence.search_programs(
            None,
            modality,
            None,
            None,
            fetch_limit,
            offset,
            innovation_type=innovation_type,
            therapeutic_area=therapeutic_area,
            drug_category=drug_category,
            program_status=program_status,
            organization_role=organization_role,
            organization_type=organization_type,
            organization_country_region=organization_country_region,
            drug_entity_id=drug_entity_id,
            target_entity_id=target_id,
            disease_entity_id=disease_entity_id,
            organization_entity_id=organization_entity_id,
            global_phase=global_phase.value if global_phase else None,
            china_phase=china_phase.value if china_phase else None,
            global_phase_started_from=global_phase_started_from,
            global_phase_started_to=global_phase_started_to,
            china_phase_started_from=china_phase_started_from,
            china_phase_started_to=china_phase_started_to,
            development_rights_region=development_rights_region,
            commercialization_rights_region=commercialization_rights_region,
            program_tag=program_tag,
            milestone_type=milestone_type,
            milestone_from=milestone_from,
            milestone_to=milestone_to,
            has_clinical_results=has_clinical_results,
            clinical_result_evaluation=(clinical_result_evaluation.value if clinical_result_evaluation else None),
            has_deal=has_deal,
            deal_currency=deal_currency,
            deal_total_potential_amount_min=deal_total_potential_amount_min,
            deal_total_potential_amount_max=deal_total_potential_amount_max,
            sort=effective_sort,
        ).items,
        sort=_sort_reads(effective_sort),
    )


@app.get(
    "/internal/v1/domain/structures",
    response_model=AgentPageResult[CompoundStructureRead],
    tags=["internal-domain"],
)
def search_structures_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    entity_id: str | None = Query(default=None, max_length=500),
    inchi_key: str | None = Query(default=None, max_length=27),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentPageResult[CompoundStructureRead]:
    principal.require("structures:read")
    arguments: dict[str, object] = {"limit": limit}
    if entity_id is not None:
        arguments["entity_id"] = entity_id
    if inchi_key is not None:
        arguments["inchi_key"] = inchi_key
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="structure.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[entity_id],
        fetch=lambda offset, fetch_limit: intelligence.structures(
            entity_id,
            inchi_key,
            fetch_limit,
            offset,
        ),
    )


@app.post(
    "/internal/v1/domain/chemistry/search",
    response_model=AgentChemistrySearchRead,
    tags=["internal-domain"],
)
def search_chemistry_for_agent(
    payload: ChemistrySearchRequest,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentChemistrySearchRead:
    principal.require("structures:read")
    result_cap = 20 if payload.mode == "exact" else 50
    if payload.limit > result_cap:
        raise ChemistryValidationError(
            "agent_result_limit",
            f"Agent {payload.mode} searches are limited to {result_cap} records per request",
        )
    billing_class = f"structure.{payload.mode}"
    arguments = _chemistry_arguments(payload)
    if cursor is not None:
        arguments["cursor"] = cursor
    commercial_service = _commercial_service(session, principal)
    reservation = commercial_service.authorize_paginated_query(
        reservation_id,
        billing_class=billing_class,
        request_arguments=arguments,
        page_size=payload.limit,
        required_compute_units="1",
    )
    result = _execute_chemistry_search(
        session,
        principal.tenant_id,
        payload,
        limit=payload.limit + 1,
        offset=reservation.page_offset,
    )
    items = result.items[: payload.limit]
    next_cursor = commercial_service.issue_next_cursor(
        reservation,
        next_offset=reservation.page_offset + len(items),
        has_more=len(result.items) > payload.limit,
    )
    return AgentChemistrySearchRead(
        **result.model_dump(exclude={"items", "count"}),
        items=items,
        count=len(items),
        limit=payload.limit,
        page_depth=reservation.page_depth,
        next_cursor=next_cursor,
    )


@app.get(
    "/internal/v1/domain/clinical-trials",
    response_model=AgentPageResult[ClinicalTrialSearchItemRead],
    tags=["internal-domain"],
)
def search_clinical_trials_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    entity_id: str | None = Query(default=None, max_length=500),
    q: str | None = Query(default=None, max_length=500),
    registry: str | None = Query(default=None, max_length=80),
    overall_status: str | None = Query(default=None, alias="status", max_length=100),
    phase: str | None = Query(default=None, max_length=80),
    study_type: str | None = Query(default=None, max_length=80),
    acronym: str | None = Query(default=None, max_length=240),
    initiation_type: TrialInitiationType | None = None,
    therapy_line: TrialTherapyLine | None = None,
    has_results: bool | None = Query(default=None),
    result_evaluation: TrialResultEvaluation | None = None,
    results_posted_from: Annotated[datetime | None, Query()] = None,
    results_posted_to: Annotated[datetime | None, Query()] = None,
    investigational_drug: str | None = Query(default=None, max_length=500),
    combination_drug: str | None = Query(default=None, max_length=500),
    investigational_target: str | None = Query(default=None, max_length=500),
    combination_target: str | None = Query(default=None, max_length=500),
    investigational_drug_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    combination_drug_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    investigational_target_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    combination_target_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    linked_drug_modality: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    linked_drug_innovation_type: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    linked_drug_category: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    linked_drug_program_tag: Annotated[list[PipelineProgramTagQueryValue] | None, Query(max_length=20)] = None,
    linked_drug_global_phase: DevelopmentPhase | None = None,
    linked_drug_organization_country_region: str | None = Query(default=None, min_length=1, max_length=120),
    role_entity_id: str | None = Query(default=None, max_length=36),
    role_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    role_entity_role: TrialEntityRole | None = None,
    has_key_result: bool | None = Query(default=None),
    publication_id: str | None = Query(default=None, max_length=240),
    conference: str | None = Query(default=None, max_length=500),
    disclosed_from: Annotated[datetime | None, Query()] = None,
    disclosed_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: ClinicalTrialSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[ClinicalTrialSearchItemRead]:
    principal.require("trials:read")
    effective_sort = _validated_sort(
        sort,
        CLINICAL_TRIAL_SORT_FIELDS,
        default_field="last_update_posted",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    results_posted_from, results_posted_to = _validated_utc_datetime_range(
        results_posted_from,
        results_posted_to,
        start_field="results_posted_from",
        end_field="results_posted_to",
    )
    disclosed_from, disclosed_to = _validated_utc_datetime_range(
        disclosed_from,
        disclosed_to,
        start_field="disclosed_from",
        end_field="disclosed_to",
    )
    role_entity_id, role_entity_ids, role_entity_role = _validated_trial_role_entity_filter(
        role_entity_id,
        role_entity_ids,
        role_entity_role,
    )
    investigational_drug_entity_ids = _validated_trial_role_entity_ids(
        "investigational_drug_entity_ids", investigational_drug_entity_ids
    )
    combination_drug_entity_ids = _validated_trial_role_entity_ids(
        "combination_drug_entity_ids", combination_drug_entity_ids
    )
    investigational_target_entity_ids = _validated_trial_role_entity_ids(
        "investigational_target_entity_ids", investigational_target_entity_ids
    )
    combination_target_entity_ids = _validated_trial_role_entity_ids(
        "combination_target_entity_ids", combination_target_entity_ids
    )
    linked_drug_modality = _normalized_repeated_filter(linked_drug_modality)
    linked_drug_innovation_type = _normalized_repeated_filter(linked_drug_innovation_type)
    linked_drug_category = _normalized_repeated_filter(linked_drug_category)
    linked_drug_program_tag = _normalized_repeated_filter(linked_drug_program_tag)
    arguments: dict[str, object] = {
        "limit": limit,
        "sort": [clause.token for clause in effective_sort],
    }
    if entity_id is not None:
        arguments["entity_id"] = entity_id
    if q is not None:
        arguments["q"] = q
    if registry is not None:
        arguments["registry"] = registry
    if overall_status is not None:
        arguments["status"] = overall_status
    if phase is not None:
        arguments["phase"] = phase
    if study_type is not None:
        arguments["study_type"] = study_type
    if acronym is not None:
        arguments["acronym"] = acronym
    if initiation_type is not None:
        arguments["initiation_type"] = initiation_type
    if therapy_line is not None:
        arguments["therapy_line"] = therapy_line
    if has_results is not None:
        arguments["has_results"] = has_results
    if result_evaluation is not None:
        arguments["result_evaluation"] = result_evaluation.value
    if results_posted_from is not None:
        arguments["results_posted_from"] = results_posted_from.isoformat()
    if results_posted_to is not None:
        arguments["results_posted_to"] = results_posted_to.isoformat()
    for key, value in {
        "investigational_drug": investigational_drug,
        "combination_drug": combination_drug,
        "investigational_target": investigational_target,
        "combination_target": combination_target,
        "investigational_drug_entity_ids": investigational_drug_entity_ids,
        "combination_drug_entity_ids": combination_drug_entity_ids,
        "investigational_target_entity_ids": investigational_target_entity_ids,
        "combination_target_entity_ids": combination_target_entity_ids,
        "linked_drug_modality": linked_drug_modality,
        "linked_drug_innovation_type": linked_drug_innovation_type,
        "linked_drug_category": linked_drug_category,
        "linked_drug_program_tag": linked_drug_program_tag,
        "linked_drug_global_phase": linked_drug_global_phase.value if linked_drug_global_phase else None,
        "linked_drug_organization_country_region": linked_drug_organization_country_region,
        "role_entity_id": role_entity_id,
        "role_entity_ids": role_entity_ids,
        "role_entity_role": role_entity_role.value if role_entity_role else None,
        "has_key_result": has_key_result,
        "publication_id": publication_id,
        "conference": conference,
        "disclosed_from": disclosed_from.isoformat() if disclosed_from else None,
        "disclosed_to": disclosed_to.isoformat() if disclosed_to else None,
    }.items():
        if value is not None:
            arguments[key] = value
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="trial.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[
            entity_id,
            role_entity_id,
        ],
        visible_filter_entity_ids=[
            *(role_entity_ids or []),
            *(investigational_drug_entity_ids or []),
            *(combination_drug_entity_ids or []),
            *(investigational_target_entity_ids or []),
            *(combination_target_entity_ids or []),
        ],
        fetch=lambda offset, fetch_limit: intelligence.clinical_trial_search_items(
            entity_id,
            q,
            registry,
            overall_status,
            phase,
            study_type,
            has_results,
            fetch_limit,
            offset,
            results_posted_from=results_posted_from,
            results_posted_to=results_posted_to,
            result_evaluation=result_evaluation.value if result_evaluation else None,
            acronym=acronym,
            initiation_type=initiation_type,
            therapy_line=therapy_line,
            investigational_drug=investigational_drug,
            combination_drug=combination_drug,
            investigational_target=investigational_target,
            combination_target=combination_target,
            investigational_drug_entity_ids=investigational_drug_entity_ids,
            combination_drug_entity_ids=combination_drug_entity_ids,
            investigational_target_entity_ids=investigational_target_entity_ids,
            combination_target_entity_ids=combination_target_entity_ids,
            linked_drug_modality=linked_drug_modality,
            linked_drug_innovation_type=linked_drug_innovation_type,
            linked_drug_category=linked_drug_category,
            linked_drug_program_tag=linked_drug_program_tag,
            linked_drug_global_phase=linked_drug_global_phase.value if linked_drug_global_phase else None,
            linked_drug_organization_country_region=linked_drug_organization_country_region,
            role_entity_id=role_entity_id,
            role_entity_ids=role_entity_ids,
            role_entity_role=role_entity_role.value if role_entity_role else None,
            has_key_result=has_key_result,
            publication_id=publication_id,
            conference=conference,
            disclosed_from=disclosed_from,
            disclosed_to=disclosed_to,
            sort=effective_sort,
        ),
        sort=_sort_reads(effective_sort),
    )


@app.get(
    "/internal/v1/domain/patents",
    response_model=AgentPageResult[PatentFamilySearchItemRead],
    tags=["internal-domain"],
)
def search_patents_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    entity_id: str | None = Query(default=None, max_length=500),
    q: str | None = Query(default=None, max_length=500),
    applicant: str | None = Query(default=None, max_length=300),
    legal_status: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: PatentSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[PatentFamilySearchItemRead]:
    principal.require("patents:read")
    effective_sort = _validated_sort(
        sort,
        PATENT_SORT_FIELDS,
        default_field="priority_date",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    arguments: dict[str, object] = {
        "limit": limit,
        "sort": [clause.token for clause in effective_sort],
    }
    if entity_id is not None:
        arguments["entity_id"] = entity_id
    if q is not None:
        arguments["q"] = q
    if applicant is not None:
        arguments["applicant"] = applicant
    if legal_status is not None:
        arguments["legal_status"] = legal_status
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="patent.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[entity_id],
        fetch=lambda offset, fetch_limit: intelligence.patent_search_items(
            entity_id,
            q,
            applicant,
            legal_status,
            fetch_limit,
            offset,
            sort=effective_sort,
        ),
        sort=_sort_reads(effective_sort),
    )


@app.get(
    "/internal/v1/domain/deals",
    response_model=AgentPageResult[DealSearchItemRead],
    tags=["internal-domain"],
)
def search_deals_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    entity_id: str | None = Query(default=None, max_length=500),
    q: str | None = Query(default=None, max_length=500),
    deal_type: str | None = Query(default=None, max_length=100),
    deal_status: Annotated[DealStatus | None, Query(alias="status")] = None,
    direction: DealDirection | None = None,
    direction_reference_jurisdiction: str | None = Query(default=None, max_length=120),
    territory: str | None = Query(default=None, max_length=240),
    asset_entity_id: str | None = Query(default=None, min_length=36, max_length=36),
    target_entity_id: str | None = Query(default=None, min_length=36, max_length=36),
    disease_entity_id: str | None = Query(default=None, min_length=36, max_length=36),
    asset_modality: Annotated[list[DealAssetModalityQueryValue] | None, Query(max_length=20)] = None,
    asset_program_tag: Annotated[list[DealAssetProgramTagQueryValue] | None, Query(max_length=20)] = None,
    party: str | None = Query(default=None, max_length=500),
    party_entity_id: str | None = Query(default=None, max_length=36),
    party_role: DealPartyRole | None = None,
    party_country_region: str | None = Query(default=None, max_length=120),
    party_organization_type: str | None = Query(default=None, max_length=120),
    development_phase_at_transaction: DevelopmentPhase | None = None,
    current_development_phase: DevelopmentPhase | None = None,
    right_type: DealRightType | None = None,
    rights_territory: str | None = Query(default=None, max_length=240),
    currency: str | None = Query(default=None, pattern=r"^[A-Z]{3}$"),
    announced_from: Annotated[datetime | None, Query()] = None,
    announced_to: Annotated[datetime | None, Query()] = None,
    terminated_from: Annotated[datetime | None, Query()] = None,
    terminated_to: Annotated[datetime | None, Query()] = None,
    source_updated_from: Annotated[datetime | None, Query()] = None,
    source_updated_to: Annotated[datetime | None, Query()] = None,
    upfront_amount_min: float | None = Query(default=None, ge=0),
    upfront_amount_max: float | None = Query(default=None, ge=0),
    total_potential_amount_min: float | None = Query(default=None, ge=0),
    total_potential_amount_max: float | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: DealSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[DealSearchItemRead]:
    principal.require("deals:read")
    effective_sort = _validated_sort(
        sort,
        DEAL_SORT_FIELDS,
        default_field="announced_at",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    _validate_deal_amount_sort(effective_sort, currency)
    announced_from, announced_to = _validated_utc_datetime_range(
        announced_from,
        announced_to,
        start_field="announced_from",
        end_field="announced_to",
    )
    terminated_from, terminated_to = _validated_utc_datetime_range(
        terminated_from,
        terminated_to,
        start_field="terminated_from",
        end_field="terminated_to",
    )
    source_updated_from, source_updated_to = _validated_utc_datetime_range(
        source_updated_from,
        source_updated_to,
        start_field="source_updated_from",
        end_field="source_updated_to",
    )
    upfront_amount_min, upfront_amount_max = _validated_number_range(
        upfront_amount_min,
        upfront_amount_max,
        minimum_field="upfront_amount_min",
        maximum_field="upfront_amount_max",
    )
    total_potential_amount_min, total_potential_amount_max = _validated_number_range(
        total_potential_amount_min,
        total_potential_amount_max,
        minimum_field="total_potential_amount_min",
        maximum_field="total_potential_amount_max",
    )
    asset_modality = _normalized_repeated_filter(asset_modality)
    asset_program_tag = _normalized_repeated_filter(asset_program_tag)
    arguments: dict[str, object] = {
        "limit": limit,
        "sort": [clause.token for clause in effective_sort],
    }
    if entity_id is not None:
        arguments["entity_id"] = entity_id
    if q is not None:
        arguments["q"] = q
    if deal_type is not None:
        arguments["deal_type"] = deal_type
    for key, value in {
        "status": deal_status.value if deal_status else None,
        "direction": direction.value if direction else None,
        "direction_reference_jurisdiction": direction_reference_jurisdiction,
        "territory": territory,
        "asset_entity_id": asset_entity_id,
        "target_entity_id": target_entity_id,
        "disease_entity_id": disease_entity_id,
        "asset_modality": asset_modality,
        "asset_program_tag": asset_program_tag,
        "party": party,
        "party_entity_id": party_entity_id,
        "party_role": party_role.value if party_role else None,
        "party_country_region": party_country_region,
        "party_organization_type": party_organization_type,
        "development_phase_at_transaction": (
            development_phase_at_transaction.value if development_phase_at_transaction else None
        ),
        "current_development_phase": current_development_phase.value if current_development_phase else None,
        "right_type": right_type.value if right_type else None,
        "rights_territory": rights_territory,
        "currency": currency,
        "announced_from": announced_from.isoformat() if announced_from else None,
        "announced_to": announced_to.isoformat() if announced_to else None,
        "terminated_from": terminated_from.isoformat() if terminated_from else None,
        "terminated_to": terminated_to.isoformat() if terminated_to else None,
        "source_updated_from": source_updated_from.isoformat() if source_updated_from else None,
        "source_updated_to": source_updated_to.isoformat() if source_updated_to else None,
        "upfront_amount_min": upfront_amount_min,
        "upfront_amount_max": upfront_amount_max,
        "total_potential_amount_min": total_potential_amount_min,
        "total_potential_amount_max": total_potential_amount_max,
    }.items():
        if value is not None:
            arguments[key] = value
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="deal.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[
            entity_id,
            asset_entity_id,
            target_entity_id,
            disease_entity_id,
            party_entity_id,
        ],
        fetch=lambda offset, fetch_limit: intelligence.deal_search_items(
            entity_id,
            q,
            deal_type,
            territory,
            party,
            fetch_limit,
            offset,
            status=deal_status.value if deal_status else None,
            direction=direction.value if direction else None,
            direction_reference_jurisdiction=direction_reference_jurisdiction,
            asset_entity_id=asset_entity_id,
            target_entity_id=target_entity_id,
            disease_entity_id=disease_entity_id,
            asset_modality=asset_modality,
            asset_program_tag=asset_program_tag,
            party_entity_id=party_entity_id,
            party_role=party_role.value if party_role else None,
            party_country_region=party_country_region,
            party_organization_type=party_organization_type,
            development_phase_at_transaction=(
                development_phase_at_transaction.value if development_phase_at_transaction else None
            ),
            current_development_phase=current_development_phase.value if current_development_phase else None,
            right_type=right_type.value if right_type else None,
            rights_territory=rights_territory,
            currency=currency,
            announced_from=announced_from,
            announced_to=announced_to,
            terminated_from=terminated_from,
            terminated_to=terminated_to,
            source_updated_from=source_updated_from,
            source_updated_to=source_updated_to,
            upfront_amount_min=upfront_amount_min,
            upfront_amount_max=upfront_amount_max,
            total_potential_amount_min=total_potential_amount_min,
            total_potential_amount_max=total_potential_amount_max,
            sort=effective_sort,
        ),
        sort=_sort_reads(effective_sort),
    )


@app.get(
    "/internal/v1/domain/companies/{company_id}/timeline",
    response_model=AgentPageResult[CompanyTimelineEventRead],
    tags=["internal-domain"],
)
def get_company_timeline_for_agent(
    company_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentPageResult[CompanyTimelineEventRead]:
    principal.require("pipelines:read")
    principal.require("deals:read")
    arguments: dict[str, object] = {"company_entity_id": company_id, "limit": limit}
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)

    def fetch(offset: int, fetch_limit: int) -> list[CompanyTimelineEventRead]:
        result = intelligence.company_timeline(company_id, fetch_limit, offset)
        if result is None:
            raise HTTPException(status_code=404, detail="Company not found")
        return result.items

    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="company.timeline",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[company_id],
        fetch=fetch,
    )


@app.get(
    "/internal/v1/domain/regulatory-events",
    response_model=AgentPageResult[RegulatoryEventSearchItemRead],
    tags=["internal-domain"],
)
def search_regulatory_events_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    entity_id: str | None = Query(default=None, max_length=500),
    q: str | None = Query(default=None, max_length=500),
    agency: str | None = Query(default=None, max_length=80),
    jurisdiction: str | None = Query(default=None, max_length=120),
    event_type: str | None = Query(default=None, max_length=40),
    status: str | None = Query(default=None, max_length=120),
    designation_type: RegulatoryDesignationType | None = None,
    label_change_type: RegulatoryLabelChangeType | None = None,
    has_boxed_warning: bool | None = None,
    safety_signal_type: RegulatorySafetySignalType | None = None,
    safety_severity: RegulatorySafetySeverity | None = None,
    safety_status: RegulatorySafetyStatus | None = None,
    decision_from: Annotated[datetime | None, Query()] = None,
    decision_to: Annotated[datetime | None, Query()] = None,
    source_updated_from: Annotated[datetime | None, Query()] = None,
    source_updated_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: RegulatorySortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[RegulatoryEventSearchItemRead]:
    principal.require("regulatory:read")
    effective_sort = _validated_sort(
        sort,
        REGULATORY_SORT_FIELDS,
        default_field="decision_date",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    decision_from, decision_to = _validated_utc_datetime_range(
        decision_from,
        decision_to,
        start_field="decision_from",
        end_field="decision_to",
    )
    source_updated_from, source_updated_to = _validated_utc_datetime_range(
        source_updated_from,
        source_updated_to,
        start_field="source_updated_from",
        end_field="source_updated_to",
    )
    arguments: dict[str, object] = {
        "limit": limit,
        "sort": [clause.token for clause in effective_sort],
    }
    for name, value in (
        ("entity_id", entity_id),
        ("q", q),
        ("agency", agency),
        ("jurisdiction", jurisdiction),
        ("event_type", event_type),
        ("status", status),
        ("designation_type", designation_type.value if designation_type else None),
        ("label_change_type", label_change_type.value if label_change_type else None),
        ("has_boxed_warning", has_boxed_warning),
        ("safety_signal_type", safety_signal_type.value if safety_signal_type else None),
        ("safety_severity", safety_severity.value if safety_severity else None),
        ("safety_status", safety_status.value if safety_status else None),
        ("decision_from", decision_from.isoformat() if decision_from else None),
        ("decision_to", decision_to.isoformat() if decision_to else None),
        ("source_updated_from", source_updated_from.isoformat() if source_updated_from else None),
        ("source_updated_to", source_updated_to.isoformat() if source_updated_to else None),
    ):
        if value is not None:
            arguments[name] = value
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="regulatory.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[entity_id],
        fetch=lambda offset, fetch_limit: intelligence.regulatory_search_items(
            entity_id,
            q,
            agency,
            jurisdiction,
            event_type,
            status,
            fetch_limit,
            offset,
            designation_type=designation_type.value if designation_type else None,
            label_change_type=label_change_type.value if label_change_type else None,
            has_boxed_warning=has_boxed_warning,
            safety_signal_type=safety_signal_type.value if safety_signal_type else None,
            safety_severity=safety_severity.value if safety_severity else None,
            safety_status=safety_status.value if safety_status else None,
            decision_from=decision_from,
            decision_to=decision_to,
            source_updated_from=source_updated_from,
            source_updated_to=source_updated_to,
            sort=effective_sort,
        ),
        sort=_sort_reads(effective_sort),
    )


@app.get(
    "/internal/v1/domain/epidemiology-observations",
    response_model=AgentPageResult[EpidemiologyObservationSearchItemRead],
    tags=["internal-domain"],
)
def search_epidemiology_observations_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    disease_entity_id: str | None = Query(default=None, max_length=500),
    q: str | None = Query(default=None, max_length=500),
    measure: str | None = Query(default=None, max_length=40),
    geography: str | None = Query(default=None, max_length=160),
    unit: str | None = Query(default=None, max_length=120),
    population_scope: str | None = Query(default=None, max_length=500),
    patient_population_id: str | None = Query(default=None, max_length=36),
    age_group: str | None = Query(default=None, max_length=120),
    sex: str | None = Query(default=None, max_length=80),
    period_start_from: Annotated[datetime | None, Query()] = None,
    period_end_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: EpidemiologySortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[EpidemiologyObservationSearchItemRead]:
    principal.require("epidemiology:read")
    effective_sort = _validated_sort(
        sort,
        EPIDEMIOLOGY_SORT_FIELDS,
        default_field="period_end",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    arguments: dict[str, object] = {
        "limit": limit,
        "sort": [clause.token for clause in effective_sort],
    }
    for name, value in (
        ("disease_entity_id", disease_entity_id),
        ("q", q),
        ("measure", measure),
        ("geography", geography),
        ("unit", unit),
        ("population_scope", population_scope),
        ("patient_population_id", patient_population_id),
        ("age_group", age_group),
        ("sex", sex),
        ("period_start_from", period_start_from.isoformat() if period_start_from else None),
        ("period_end_to", period_end_to.isoformat() if period_end_to else None),
        ("cursor", cursor),
    ):
        if value is not None:
            arguments[name] = value
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="epidemiology.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[disease_entity_id],
        fetch=lambda offset, fetch_limit: intelligence.epidemiology_search_items(
            disease_entity_id,
            q,
            measure,
            geography,
            unit,
            population_scope,
            age_group,
            sex,
            period_start_from,
            period_end_to,
            fetch_limit,
            offset,
            patient_population_id=patient_population_id,
            sort=effective_sort,
        ),
        sort=_sort_reads(effective_sort),
    )


@app.get(
    "/internal/v1/domain/news-events",
    response_model=AgentPageResult[NewsEventSearchItemRead],
    tags=["internal-domain"],
)
def search_news_events_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    entity_id: str | None = Query(default=None, max_length=500),
    q: str | None = Query(default=None, max_length=500),
    event_type: str | None = Query(default=None, max_length=40),
    publisher: str | None = Query(default=None, max_length=500),
    language: str | None = Query(default=None, max_length=32),
    venue: str | None = Query(default=None, max_length=240),
    published_from: Annotated[datetime | None, Query()] = None,
    published_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: NewsSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[NewsEventSearchItemRead]:
    principal.require("news:read")
    effective_sort = _validated_sort(
        sort,
        NEWS_SORT_FIELDS,
        default_field="published_at",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    arguments: dict[str, object] = {
        "limit": limit,
        "sort": [clause.token for clause in effective_sort],
    }
    for name, value in (
        ("entity_id", entity_id),
        ("q", q),
        ("event_type", event_type),
        ("publisher", publisher),
        ("language", language),
        ("venue", venue),
        ("published_from", published_from.isoformat() if published_from else None),
        ("published_to", published_to.isoformat() if published_to else None),
        ("cursor", cursor),
    ):
        if value is not None:
            arguments[name] = value
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="news.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[entity_id],
        fetch=lambda offset, fetch_limit: intelligence.news_event_search_items(
            entity_id,
            q,
            event_type,
            publisher,
            language,
            venue,
            published_from,
            published_to,
            fetch_limit,
            offset,
            sort=effective_sort,
        ),
        sort=_sort_reads(effective_sort),
    )


@app.get(
    "/internal/v1/domain/knowledge/pages",
    response_model=AgentPageResult[KnowledgePageSummary],
    tags=["internal-domain"],
)
def search_knowledge_pages_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    q: str | None = Query(default=None, max_length=500),
    page_type: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentPageResult[KnowledgePageSummary]:
    principal.require("knowledge:read")
    arguments: dict[str, object] = {"limit": limit}
    if q is not None:
        arguments["q"] = q
    if page_type is not None:
        arguments["page_type"] = page_type
    if cursor is not None:
        arguments["cursor"] = cursor

    def fetch(offset: int, fetch_limit: int) -> list[KnowledgePageSummary]:
        statement = select(KnowledgePage).where(
            KnowledgePage.tenant_id == principal.tenant_id,
            KnowledgePage.status == KnowledgePageStatus.PUBLISHED,
            KnowledgePage.current_version_id.is_not(None),
        )
        if q:
            statement = statement.where(KnowledgePage.title.ilike(f"%{q}%"))
        if page_type:
            statement = statement.where(KnowledgePage.page_type == page_type)
        pages = session.scalars(
            statement.order_by(KnowledgePage.title, KnowledgePage.id).limit(fetch_limit).offset(offset)
        )
        return [KnowledgePageSummary.model_validate(page) for page in pages]

    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="knowledge.search",
        arguments=arguments,
        page_size=limit,
        fetch=fetch,
    )


@app.get(
    "/internal/v1/domain/knowledge/pages/{page_id}",
    response_model=KnowledgePageDetail,
    tags=["internal-domain"],
)
def get_knowledge_page_for_agent(
    page_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
) -> KnowledgePageDetail:
    principal.require("knowledge:read")
    _commercial_service(session, principal).authorize_paginated_query(
        reservation_id,
        billing_class="knowledge.read",
        request_arguments={"page_id": page_id},
        page_size=1,
    )
    page = session.scalar(
        select(KnowledgePage).where(
            KnowledgePage.id == page_id,
            KnowledgePage.tenant_id == principal.tenant_id,
            KnowledgePage.status == KnowledgePageStatus.PUBLISHED,
            KnowledgePage.current_version_id.is_not(None),
        )
    )
    if page is None:
        raise HTTPException(status_code=404, detail="Knowledge page not found")
    version = session.scalar(
        select(KnowledgePageVersion).where(
            KnowledgePageVersion.id == page.current_version_id,
            KnowledgePageVersion.tenant_id == principal.tenant_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=409, detail="Knowledge page current version is unavailable")
    return KnowledgePageDetail(
        **KnowledgePageSummary.model_validate(page).model_dump(),
        version_number=version.version_number,
        compiler_version=version.compiler_version,
        content_json=version.content_json,
        rendered_markdown=version.rendered_markdown,
        content_sha256=version.content_sha256,
        source_snapshot_at=version.source_snapshot_at,
    )


@app.get("/api/v1/entities", response_model=SearchResult, tags=["entities"])
def search_entities(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    entity_type: EntityType | None = None,
    review_status: ReviewStatus | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: EntitySortField | None = None,
    sort_direction: SortDirection | None = None,
    entity_types: Annotated[list[EntityType] | None, Query()] = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> SearchResult:
    principal.require("entities:read")
    effective_review_status = _effective_public_review_status(principal, review_status)
    effective_sort = _validated_sort(
        sort,
        ENTITY_SORT_FIELDS,
        default_field="relevance",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    selected_types = _normalize_entity_types(entity_type, entity_types or [])
    try:
        result = EntitySearchService(session, principal.tenant_id, get_settings()).search(
            q,
            entity_type,
            limit,
            offset,
            effective_review_status,
            effective_sort[0].field,
            effective_sort[0].direction,
            selected_types,
            effective_sort,
            hide_unpublished_facets=not _can_view_unpublished_entities(principal),
        )
    except SearchProjectionError as exc:
        raise HTTPException(status_code=503, detail="Entity search projection unavailable") from exc
    return SearchResult(
        query_schema_version=ENTITY_SEARCH_SCHEMA_VERSION,
        applied_filters=_entity_search_applied_filters(q, selected_types, effective_review_status),
        items=_entity_search_items(result),
        total=result.total,
        limit=limit,
        offset=offset,
        sort_by=effective_sort[0].field,
        sort_direction=effective_sort[0].direction,
        sort=_sort_reads(effective_sort),
        facets=result.facets,
        suggestions=result.suggestions,
        engine=result.engine,
        took_ms=result.took_ms,
    )


@app.get("/api/v1/entities/suggestions", response_model=EntitySuggestionResult, tags=["entities"])
def suggest_entities(
    principal: PrincipalDep,
    session: SessionDep,
    q: str = Query(min_length=1, max_length=500),
    entity_type: EntityType | None = None,
    limit: int = Query(default=10, ge=1, le=25),
    entity_types: Annotated[list[EntityType] | None, Query()] = None,
) -> EntitySuggestionResult:
    principal.require("entities:read")
    effective_review_status = _effective_public_review_status(principal, None)
    selected_types = _normalize_entity_types(entity_type, entity_types or [])
    try:
        result = EntitySearchService(session, principal.tenant_id, get_settings()).search(
            q,
            entity_type,
            limit,
            0,
            effective_review_status,
            entity_types=selected_types,
        )
    except SearchProjectionError as exc:
        raise HTTPException(status_code=503, detail="Entity search projection unavailable") from exc
    suggestions = result.suggestions or [item.name for item in result.items]
    return EntitySuggestionResult(suggestions=suggestions[:limit], engine=result.engine)


def _human_monitoring_service(principal: Principal, session: Session) -> MonitoringService:
    if principal.actor_type != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Human workspace session required")
    return MonitoringService(session, principal.tenant_id, principal.actor_id)


def _human_comparison_service(principal: Principal, session: Session) -> ComparisonSetService:
    if principal.actor_type != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Human workspace session required")
    return ComparisonSetService(session, principal.tenant_id, principal.actor_id)


def _human_export_service(principal: Principal, session: Session) -> WorkspaceComparisonExportService:
    if principal.actor_type != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Human workspace session required")
    return WorkspaceComparisonExportService(session, principal.tenant_id, principal.actor_id)


def _comparison_summary(view: ComparisonSetView) -> ComparisonSetSummaryRead:
    return ComparisonSetSummaryRead(
        id=view.item.id,
        owner_user_id=view.item.owner_user_id,
        name=view.item.name,
        description=view.item.description,
        visibility=view.item.visibility,
        version=view.item.version,
        member_count=view.member_count,
        editable=view.editable,
        created_at=view.item.created_at,
        updated_at=view.item.updated_at,
    )


def _comparison_detail(view: ComparisonSetView) -> ComparisonSetDetailRead:
    summary = _comparison_summary(view)
    return ComparisonSetDetailRead(
        **summary.model_dump(),
        members=[ComparisonSetMemberRead.model_validate(member) for member in view.members],
    )


def _comparison_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ComparisonSetNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ComparisonSetLimitExceeded):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@app.get(
    "/api/v1/comparison-sets",
    response_model=list[ComparisonSetSummaryRead],
    tags=["comparison-sets"],
)
def list_comparison_sets(principal: PrincipalDep, session: SessionDep) -> list[ComparisonSetSummaryRead]:
    principal.require("collections:read")
    return [_comparison_summary(item) for item in _human_comparison_service(principal, session).list_sets()]


@app.post(
    "/api/v1/comparison-sets",
    response_model=ComparisonSetDetailRead,
    status_code=status.HTTP_201_CREATED,
    tags=["comparison-sets"],
)
def create_comparison_set(
    payload: ComparisonSetCreate, principal: PrincipalDep, session: SessionDep
) -> ComparisonSetDetailRead:
    principal.require("collections:write")
    try:
        view = _human_comparison_service(principal, session).create_set(payload)
    except ComparisonSetConflict as exc:
        raise _comparison_error(exc) from exc
    return _comparison_detail(view)


@app.get(
    "/api/v1/comparison-sets/{comparison_set_id}",
    response_model=ComparisonSetDetailRead,
    tags=["comparison-sets"],
)
def get_comparison_set(comparison_set_id: str, principal: PrincipalDep, session: SessionDep) -> ComparisonSetDetailRead:
    principal.require("collections:read")
    try:
        view = _human_comparison_service(principal, session).get_set(comparison_set_id)
    except ComparisonSetNotFound as exc:
        raise _comparison_error(exc) from exc
    return _comparison_detail(view)


@app.patch(
    "/api/v1/comparison-sets/{comparison_set_id}",
    response_model=ComparisonSetDetailRead,
    tags=["comparison-sets"],
)
def update_comparison_set(
    comparison_set_id: str,
    payload: ComparisonSetUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> ComparisonSetDetailRead:
    principal.require("collections:write")
    try:
        view = _human_comparison_service(principal, session).update_set(comparison_set_id, payload)
    except (ComparisonSetConflict, ComparisonSetNotFound) as exc:
        raise _comparison_error(exc) from exc
    return _comparison_detail(view)


@app.post(
    "/api/v1/comparison-sets/{comparison_set_id}/members",
    response_model=ComparisonSetDetailRead,
    tags=["comparison-sets"],
)
def add_comparison_set_member(
    comparison_set_id: str,
    payload: ComparisonSetMemberCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> ComparisonSetDetailRead:
    principal.require("collections:write")
    try:
        view = _human_comparison_service(principal, session).add_member(
            comparison_set_id, payload.entity_id, expected_version=payload.expected_version
        )
    except (ComparisonSetConflict, ComparisonSetLimitExceeded, ComparisonSetNotFound) as exc:
        raise _comparison_error(exc) from exc
    return _comparison_detail(view)


@app.post(
    "/api/v1/comparison-sets/{comparison_set_id}/members/batch",
    response_model=ComparisonSetDetailRead,
    tags=["comparison-sets"],
)
def add_comparison_set_members(
    comparison_set_id: str,
    payload: ComparisonSetMembersAdd,
    principal: PrincipalDep,
    session: SessionDep,
) -> ComparisonSetDetailRead:
    principal.require("collections:write")
    try:
        view = _human_comparison_service(principal, session).add_members(
            comparison_set_id,
            payload.entity_ids,
            expected_version=payload.expected_version,
        )
    except (ComparisonSetConflict, ComparisonSetLimitExceeded, ComparisonSetNotFound) as exc:
        raise _comparison_error(exc) from exc
    return _comparison_detail(view)


@app.post(
    "/api/v1/comparison-sets/{comparison_set_id}/members/{entity_id}/remove",
    response_model=ComparisonSetDetailRead,
    tags=["comparison-sets"],
)
def remove_comparison_set_member(
    comparison_set_id: str,
    entity_id: str,
    payload: ComparisonSetMemberRemove,
    principal: PrincipalDep,
    session: SessionDep,
) -> ComparisonSetDetailRead:
    principal.require("collections:write")
    try:
        view = _human_comparison_service(principal, session).remove_member(
            comparison_set_id, entity_id, expected_version=payload.expected_version
        )
    except (ComparisonSetConflict, ComparisonSetNotFound) as exc:
        raise _comparison_error(exc) from exc
    return _comparison_detail(view)


@app.get(
    "/api/v1/comparison-sets/{comparison_set_id}/versions",
    response_model=list[ComparisonSetVersionRead],
    tags=["comparison-sets"],
)
def list_comparison_set_versions(
    comparison_set_id: str, principal: PrincipalDep, session: SessionDep
) -> list[ComparisonSetVersionRead]:
    principal.require("collections:read")
    try:
        versions = _human_comparison_service(principal, session).list_versions(comparison_set_id)
    except ComparisonSetNotFound as exc:
        raise _comparison_error(exc) from exc
    return [
        ComparisonSetVersionRead(
            id=item.id,
            version=item.version,
            snapshot_json=item.snapshot_json,
            changed_by_user_id=item.changed_by_user_id,
            created_at=item.created_at,
        )
        for item in versions
    ]


@app.get(
    "/api/v1/workspace/export-policy",
    response_model=WorkspaceExportPolicyRead,
    tags=["workspace-exports"],
)
def get_workspace_export_policy(principal: PrincipalDep, session: SessionDep) -> WorkspaceExportPolicyRead:
    principal.require("workspace:export")
    try:
        service = _human_export_service(principal, session)
        return WorkspaceExportPolicyRead.model_validate(service.policy_view(service.get_policy()))
    except WorkspaceExportNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.post(
    "/api/v1/admin/workspace-export-policy",
    response_model=WorkspaceExportPolicyRead,
    tags=["workspace-exports"],
)
def configure_workspace_export_policy(
    payload: WorkspaceExportPolicyUpsert, principal: PrincipalDep, session: SessionDep
) -> WorkspaceExportPolicyRead:
    principal.require("workspace:export:manage")
    service = _human_export_service(principal, session)
    try:
        policy = service.upsert_policy(payload)
    except WorkspaceExportDenied as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except WorkspaceExportConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return WorkspaceExportPolicyRead.model_validate(service.policy_view(policy))


@app.post(
    "/api/v1/comparison-sets/{comparison_set_id}/export",
    response_class=Response,
    tags=["workspace-exports"],
)
def export_comparison_set(
    comparison_set_id: str,
    payload: WorkspaceExportCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> Response:
    principal.require("workspace:export")
    try:
        artifact = _human_export_service(principal, session).export_comparison_set(comparison_set_id, payload)
    except ComparisonSetNotFound as exc:
        raise _comparison_error(exc) from exc
    except ComparisonSetConflict as exc:
        raise _comparison_error(exc) from exc
    except WorkspaceExportNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except WorkspaceExportDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except WorkspaceExportConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "X-Export-Event-ID": artifact.event_id,
            "X-Content-SHA256": artifact.content_sha256,
            "X-Export-Policy-Version": artifact.policy_version,
            "X-Export-Replayed": str(artifact.replayed).lower(),
        },
    )


@app.post(
    "/api/v1/workspace/domain-exports",
    response_class=Response,
    tags=["workspace-exports"],
)
def export_workspace_domain_query(
    payload: WorkspaceDomainExportCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> Response:
    principal.require("workspace:export")
    try:
        artifact = _human_export_service(principal, session).export_domain_query(payload)
    except WorkspaceExportNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except WorkspaceExportDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except WorkspaceExportConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "X-Export-Event-ID": artifact.event_id,
            "X-Content-SHA256": artifact.content_sha256,
            "X-Export-Policy-Version": artifact.policy_version,
            "X-Export-Replayed": str(artifact.replayed).lower(),
        },
    )


@app.get(
    "/api/v1/monitoring/saved-searches",
    response_model=list[SavedSearchRead],
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    tags=["monitoring"],
)
def list_saved_searches(principal: PrincipalDep, session: SessionDep) -> list[SavedSearchRead]:
    principal.require("monitoring:read")
    items = _human_monitoring_service(principal, session).list_saved_searches()
    return [SavedSearchRead.model_validate(item) for item in items]


@app.get(
    "/api/v1/monitoring/saved-searches/{saved_search_id}",
    response_model=SavedSearchRead,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    tags=["monitoring"],
)
def get_saved_search(saved_search_id: str, principal: PrincipalDep, session: SessionDep) -> SavedSearchRead:
    principal.require("monitoring:read")
    try:
        item = _human_monitoring_service(principal, session).get_saved_search(saved_search_id)
    except MonitoringNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SavedSearchRead.model_validate(item)


@app.post(
    "/api/v1/monitoring/saved-searches",
    response_model=SavedSearchRead,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    status_code=status.HTTP_201_CREATED,
    tags=["monitoring"],
)
def create_saved_search(payload: SavedSearchCreate, principal: PrincipalDep, session: SessionDep) -> SavedSearchRead:
    principal.require("monitoring:write")
    try:
        item = _human_monitoring_service(principal, session).create_saved_search(payload)
    except MonitoringConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return SavedSearchRead.model_validate(item)


@app.patch(
    "/api/v1/monitoring/saved-searches/{saved_search_id}",
    response_model=SavedSearchRead,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    tags=["monitoring"],
)
def update_saved_search(
    saved_search_id: str,
    payload: SavedSearchUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> SavedSearchRead:
    principal.require("monitoring:write")
    try:
        item = _human_monitoring_service(principal, session).update_saved_search(saved_search_id, payload)
    except MonitoringNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MonitoringConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return SavedSearchRead.model_validate(item)


@app.get(
    "/api/v1/monitoring/topics",
    response_model=list[MonitoringTopicRead],
    tags=["monitoring"],
)
def list_monitoring_topics(principal: PrincipalDep, session: SessionDep) -> list[MonitoringTopicRead]:
    principal.require("monitoring:read")
    items = _human_monitoring_service(principal, session).list_topics()
    return [MonitoringTopicRead.model_validate(item) for item in items]


@app.post(
    "/api/v1/monitoring/topics",
    response_model=MonitoringTopicRead,
    status_code=status.HTTP_201_CREATED,
    tags=["monitoring"],
)
def create_monitoring_topic(
    payload: MonitoringTopicCreate, principal: PrincipalDep, session: SessionDep
) -> MonitoringTopicRead:
    principal.require("monitoring:write")
    try:
        item = _human_monitoring_service(principal, session).create_topic(payload.name, payload.saved_search_id)
    except MonitoringNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MonitoringConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return MonitoringTopicRead.model_validate(item)


@app.patch(
    "/api/v1/monitoring/topics/{topic_id}",
    response_model=MonitoringTopicRead,
    tags=["monitoring"],
)
def update_monitoring_topic(
    topic_id: str,
    payload: MonitoringTopicUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> MonitoringTopicRead:
    principal.require("monitoring:write")
    try:
        item = _human_monitoring_service(principal, session).update_topic(
            topic_id,
            name=payload.name,
            active=payload.active,
            query_version=payload.query_version,
        )
    except MonitoringNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MonitoringConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return MonitoringTopicRead.model_validate(item)


@app.get(
    "/api/v1/monitoring/alerts",
    response_model=list[MonitoringAlertRead],
    tags=["monitoring"],
)
def list_monitoring_alerts(
    principal: PrincipalDep,
    session: SessionDep,
    unread_only: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MonitoringAlertRead]:
    principal.require("monitoring:read")
    return [
        MonitoringAlertRead.model_validate(item)
        for item in _human_monitoring_service(principal, session).list_alerts(unread_only=unread_only, limit=limit)
    ]


@app.post(
    "/api/v1/monitoring/alerts/{alert_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["monitoring"],
)
def mark_monitoring_alert_read(alert_id: str, principal: PrincipalDep, session: SessionDep) -> Response:
    principal.require("monitoring:write")
    try:
        _human_monitoring_service(principal, session).mark_alert_read(alert_id)
    except MonitoringNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/v1/entities/{entity_id}", response_model=EntityRead, tags=["entities"])
def get_entity(entity_id: str, request: Request, principal: PrincipalDep, session: SessionDep) -> EntityRead:
    principal.require("entities:read")
    entity = EntityRepository(session, principal.tenant_id).get(entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    _assert_public_entity_visible(entity, principal)
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=entity.id,
        details={"entity_type": entity.entity_type.value},
    )
    return _public_entity_read(entity)


@app.get(
    "/api/v1/entities/{entity_id}/dossier",
    response_model=EntityDossierResponse,
    response_model_exclude_none=True,
    tags=["entities"],
)
def get_entity_dossier(
    entity_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> EntityDossierResponse:
    principal.require("dossiers:read")
    dossier = _intelligence_service(session, principal).entity_dossier(entity_id, limit)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    _assert_public_entity_visible(dossier.entity, principal)
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=dossier.entity.id,
        details={"entity_type": dossier.entity.entity_type.value},
    )
    return _public_dossier_projection(dossier)


@app.get(
    "/api/v1/drugs/comparison",
    response_model=DrugComparisonResult,
    response_model_exclude_none=True,
    tags=["drugs"],
)
def compare_drugs(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    drug_ids: Annotated[list[str], Query(min_length=2, max_length=4)],
) -> DrugComparisonResult:
    principal.require("dossiers:read")
    if len(set(drug_ids)) != len(drug_ids):
        raise HTTPException(status_code=422, detail="Drug comparison IDs must be unique")
    result = _intelligence_service(session, principal).drug_comparison_profiles(drug_ids)
    if len(result.items) != len(drug_ids):
        raise HTTPException(status_code=404, detail="One or more drugs were not found")
    request.state.audit_resource = RequestAuditResource(
        resource_type="research_drug_comparison",
        resource_id=hashlib.sha256("|".join(drug_ids).encode()).hexdigest(),
        details={"drug_count": len(drug_ids)},
    )
    return _public_dossier_projection(result)


@app.get(
    "/api/v1/drugs/{drug_id}/dossier",
    response_model=DrugDossierResponse,
    response_model_exclude_none=True,
    tags=["drugs"],
)
def get_drug_dossier(
    drug_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=100),
) -> DrugDossierResponse:
    principal.require("dossiers:read")
    dossier = _intelligence_service(session, principal).drug_dossier(drug_id, limit)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Drug not found")
    _assert_public_entity_visible(dossier.entity, principal)
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=dossier.entity.id,
        details={"entity_type": dossier.entity.entity_type.value, "profile": "drug"},
    )
    return _public_dossier_projection(dossier)


@app.get(
    "/api/v1/drugs/{drug_id}/programs",
    response_model=DrugProgramSearchResult,
    response_model_exclude_none=True,
    tags=["drugs"],
)
def list_drug_programs(
    drug_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DrugProgramSearchResult:
    principal.require("pipelines:read")
    _assert_public_entity_ids_visible(session, principal, [drug_id])
    result = _intelligence_service(session, principal).drug_programs(drug_id, limit, offset)
    if result is None:
        raise HTTPException(status_code=404, detail="Drug not found")
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=drug_id,
        details={"entity_type": EntityType.DRUG.value, "profile": "drug_programs", "offset": offset},
    )
    return _public_dossier_projection(result)


@app.get(
    "/api/v1/diseases/{disease_id}/dossier",
    response_model=DiseaseDossierResponse,
    response_model_exclude_none=True,
    tags=["diseases"],
)
def get_disease_dossier(
    disease_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=100),
) -> DiseaseDossierResponse:
    principal.require("dossiers:read")
    principal.require("pipelines:read")
    principal.require("epidemiology:read")
    dossier = _intelligence_service(session, principal).disease_dossier(disease_id, limit)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Disease not found")
    _assert_public_entity_visible(dossier.entity, principal)
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=dossier.entity.id,
        details={"entity_type": dossier.entity.entity_type.value, "profile": "disease"},
    )
    return _public_dossier_projection(dossier)


@app.get(
    "/api/v1/workspace/recent-entities",
    response_model=list[RecentEntityVisitRead],
    tags=["workspace"],
)
def list_recent_entities(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=8, ge=1, le=20),
) -> list[RecentEntityVisitRead]:
    principal.require("entities:read")
    if principal.user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Human user session required")
    return [
        RecentEntityVisitRead(entity=_public_entity_read(item.entity), visited_at=item.visited_at)
        for item in ResearchActivityService(session, principal.tenant_id, principal.user_id).list_recent_entities(limit)
        if _can_view_unpublished_entities(principal) or item.entity.review_status == ReviewStatus.VERIFIED
    ]


def _human_workspace_preference_service(
    principal: Principal,
    session: Session,
) -> WorkspaceTablePreferenceService:
    if principal.actor_type != "user" or principal.user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Human workspace session required")
    return WorkspaceTablePreferenceService(session, principal.tenant_id, principal.user_id)


def _workspace_table_preference_read(
    preference_key: WorkspaceTablePreferenceKey,
    item: WorkspaceTablePreference | None,
) -> WorkspaceTablePreferenceRead:
    if item is None:
        return WorkspaceTablePreferenceRead(
            preference_key=preference_key,
            version=0,
            persisted=False,
        )
    return WorkspaceTablePreferenceRead(
        preference_key=preference_key,
        schema_version=1,
        column_visibility=item.column_visibility,
        column_order=item.column_order,
        density=cast(WorkspaceTableDensity, item.density),
        version=item.version,
        persisted=True,
        updated_at=item.updated_at,
    )


@app.get(
    "/api/v1/workspace/table-preferences/{preference_key}",
    response_model=WorkspaceTablePreferenceRead,
    tags=["workspace"],
)
def get_workspace_table_preference(
    preference_key: WorkspaceTablePreferenceKey,
    principal: PrincipalDep,
    session: SessionDep,
) -> WorkspaceTablePreferenceRead:
    principal.require("entities:read")
    item = _human_workspace_preference_service(principal, session).get(preference_key)
    return _workspace_table_preference_read(preference_key, item)


@app.put(
    "/api/v1/workspace/table-preferences/{preference_key}",
    response_model=WorkspaceTablePreferenceRead,
    responses={status.HTTP_409_CONFLICT: {"description": "Preference version conflict"}},
    tags=["workspace"],
)
def update_workspace_table_preference(
    preference_key: WorkspaceTablePreferenceKey,
    payload: WorkspaceTablePreferenceUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> WorkspaceTablePreferenceRead:
    principal.require("entities:read")
    try:
        item = _human_workspace_preference_service(principal, session).upsert(preference_key, payload)
    except WorkspaceTablePreferenceConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _workspace_table_preference_read(preference_key, item)


@app.post(
    "/api/v1/workspace/web-vitals",
    response_model=WebVitalBatchAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["workspace"],
)
def report_workspace_web_vitals(
    payload: WebVitalBatchCreate,
    principal: PrincipalDep,
) -> WebVitalBatchAccepted:
    principal.require("entities:read")
    if principal.actor_type != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Human workspace session required")
    instruments = operational_metrics()
    for sample in payload.samples:
        instruments.record_web_vital(
            sample.metric_name,
            sample.route,
            sample.rating,
            sample.viewport_class,
            sample.navigation_type,
            sample.value,
        )
    return WebVitalBatchAccepted(accepted_count=len(payload.samples))


@app.post(
    "/api/v1/entities",
    response_model=EntityRead,
    status_code=status.HTTP_201_CREATED,
    tags=["entities"],
)
def create_entity(payload: EntityCreate, principal: PrincipalDep, session: SessionDep) -> EntityRead:
    principal.require("entities:write")
    try:
        entity = EntityRepository(session, principal.tenant_id).create(payload)
    except (DuplicateEntityError, IntegrityError) as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Entity already exists") from exc
    except IdentityError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _public_entity_read(entity)


def _evidence_delivery_channel(principal: Principal) -> DeliveryChannel:
    return "web" if principal.actor_type == "user" else "mcp"


def _evidence_license_scope(
    dataset: ResolvedDataset,
    channel: DeliveryChannel,
) -> EvidenceLicenseScope:
    policy = dataset.license_policy
    allowed_fields: list[str] = list(policy.allowed_fields)
    return EvidenceLicenseScope(
        dataset_key=dataset.key,
        license_id=policy.license_id,
        policy_version=policy.policy_version,
        attribution=policy.attribution,
        delivery_channel=channel,
        allowed_fields=allowed_fields,
        max_content_chars=policy.max_content_chars,
        valid_from=policy.valid_from,
        expires_at=policy.expires_at,
    )


def _public_evidence_document_id(dataset_key: str, document_id: str) -> str:
    digest = hashlib.sha256(f"{dataset_key}\0{document_id}".encode()).hexdigest()[:24]
    return f"citation-{digest}"


def _public_web_evidence_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    public: dict[str, Any] = {}
    source = metadata.get("source")
    if isinstance(source, str):
        parsed = urlsplit(source)
        if parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.username and not parsed.password:
            public["source"] = source
    license_metadata = metadata.get("license")
    if isinstance(license_metadata, dict):
        attribution = license_metadata.get("attribution")
        if isinstance(attribution, str) and attribution.strip():
            public["license"] = {"attribution": attribution.strip()}
    return public


def _licensed_evidence_chunk(
    dataset: ResolvedDataset,
    chunk: EvidenceChunk,
    channel: DeliveryChannel,
) -> tuple[EvidenceChunk, list[str]]:
    delivery = apply_evidence_license(
        dataset.license_policy,
        dataset_key=dataset.key,
        content=chunk.content,
        document_name=chunk.document_name,
        positions=chunk.positions,
        metadata=chunk.metadata,
    )
    updates: dict[str, Any] = {
        "content": delivery.content,
        "document_name": delivery.document_name,
        "dataset_id": dataset.key,
        "positions": delivery.positions,
        "metadata": delivery.metadata,
    }
    if channel == "web":
        updates.update(
            {
                "document_id": _public_evidence_document_id(dataset.key, chunk.document_id),
                "similarity": None,
                "metadata": _public_web_evidence_metadata(delivery.metadata),
            }
        )
    return chunk.model_copy(update=updates), delivery.warnings


def _search_evidence_response(
    payload: EvidenceSearchRequest,
    principal: Principal,
    session: Session,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> EvidenceSearchResponse:
    principal.require("evidence:read")
    resolved_limit = limit or payload.limit
    settings = get_settings()
    try:
        datasets = DatasetRepository(session, principal.tenant_id).resolve_for_principal(
            principal,
            payload.dataset_keys,
        )
    except DatasetAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DatasetSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    channel = _evidence_delivery_channel(principal)
    license_scopes = [_evidence_license_scope(dataset, channel) for dataset in datasets]
    warnings: list[str] = []
    try:
        matches = get_opensearch_gateway().search_evidence(
            principal.tenant_id,
            payload.query,
            [dataset.key for dataset in datasets],
            resolved_limit,
            offset,
        )
    except SearchProjectionError as exc:
        raise HTTPException(status_code=503, detail="Evidence search projection unavailable") from exc

    source_asset_ids = {
        str(match.metadata["source_asset_id"]) for match in matches if match.metadata.get("source_asset_id")
    }
    deleted_source_asset_ids = (
        set(
            session.scalars(
                select(SourceAsset.id).where(
                    SourceAsset.tenant_id == principal.tenant_id,
                    SourceAsset.id.in_(source_asset_ids),
                    SourceAsset.state == SourceAssetState.DELETED,
                )
            )
        )
        if source_asset_ids
        else set()
    )
    if deleted_source_asset_ids:
        matches = [
            match
            for match in matches
            if str(match.metadata.get("source_asset_id") or "") not in deleted_source_asset_ids
        ]
        warnings.append("Withdrawn source evidence was removed while the search projection catches up")

    dataset_by_key = {dataset.key: dataset for dataset in datasets}
    chunks: list[EvidenceChunk] = []
    for match in matches:
        dataset = dataset_by_key.get(match.dataset_key)
        if dataset is None:
            raise HTTPException(
                status_code=503,
                detail="Evidence search returned an unauthorized dataset",
            )
        chunk, chunk_warnings = _licensed_evidence_chunk(
            dataset,
            EvidenceChunk(
                content=match.content,
                document_id=match.document_id,
                document_name=match.document_name,
                dataset_id=match.dataset_key,
                similarity=match.score,
                positions=match.positions,
                metadata=match.metadata,
            ),
            channel,
        )
        chunks.append(chunk)
        warnings.extend(chunk_warnings)
    return EvidenceSearchResponse(
        query=payload.query,
        chunks=chunks,
        engine=("opensearch-hybrid" if settings.search_semantic_enabled else "opensearch")
        if channel == "mcp"
        else "evidence",
        license_scopes=license_scopes if channel == "mcp" else [],
        warnings=list(dict.fromkeys(warnings)),
    )


def _record_provenance_response(
    resource_type: ProvenanceResourceType,
    resource_id: str,
    principal: Principal,
    session: Session,
    *,
    limit: int,
) -> RecordProvenanceResponse:
    principal.require("evidence:read")
    repository = ProvenanceRepository(session, principal.tenant_id)
    dataset_keys = repository.dataset_keys_for_record(resource_type, resource_id)
    if not dataset_keys:
        return RecordProvenanceResponse(
            resource_type=resource_type,
            resource_id=resource_id,
            items=[],
            license_scopes=[],
        )
    try:
        datasets = DatasetRepository(session, principal.tenant_id).resolve_for_principal(
            principal,
            dataset_keys,
        )
    except DatasetAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DatasetSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    dataset_by_key = {dataset.key: dataset for dataset in datasets}
    channel = _evidence_delivery_channel(principal)
    warnings: list[str] = []
    withdrawn_count = repository.withdrawn_count(resource_type, resource_id)
    if withdrawn_count:
        warnings.append(f"{withdrawn_count} withdrawn source record(s) were omitted")
    items: list[RecordProvenanceRead] = []
    for record in repository.list_for_record(resource_type, resource_id, limit):
        dataset = dataset_by_key.get(record.link.dataset_key)
        if dataset is None:
            raise HTTPException(status_code=503, detail="Provenance resolved an unauthorized dataset")
        metadata = {
            "source": record.document.source_uri,
            "source_document_id": record.document.id,
            "source_version_id": record.version.id,
            "content_sha256": record.version.content_sha256,
            "evidence_claim_id": record.claim.id,
            "subject_entity_id": record.claim.subject_id,
            "review_status": record.claim.review_status.value,
        }
        delivery = apply_evidence_license(
            dataset.license_policy,
            dataset_key=dataset.key,
            content=record.staged_fact.source_quote,
            document_name=record.document.title,
            positions=[record.link.source_locator] if record.link.source_locator else [],
            metadata=metadata,
        )
        license_metadata = delivery.metadata.get("license")
        if not isinstance(license_metadata, dict):
            raise HTTPException(status_code=500, detail="Evidence license delivery metadata is invalid")
        locator = delivery.positions[0] if delivery.positions and isinstance(delivery.positions[0], str) else None
        items.append(
            RecordProvenanceRead(
                id=record.link.id,
                resource_type=resource_type,
                resource_id=resource_id,
                dataset_key=record.link.dataset_key,
                evidence_claim_id=delivery.metadata.get("evidence_claim_id"),
                source_document_id=delivery.metadata.get("source_document_id"),
                source_version_id=delivery.metadata.get("source_version_id"),
                content_sha256=delivery.metadata.get("content_sha256"),
                document_name=delivery.document_name,
                source_uri=delivery.metadata.get("source"),
                locator=locator,
                quote=delivery.content,
                subject_entity_id=delivery.metadata.get("subject_entity_id"),
                review_status=delivery.metadata.get("review_status"),
                created_at=record.link.created_at,
                license=license_metadata,
                warnings=delivery.warnings,
            )
        )
        warnings.extend(delivery.warnings)
    return RecordProvenanceResponse(
        resource_type=resource_type,
        resource_id=resource_id,
        items=items,
        license_scopes=[_evidence_license_scope(dataset, channel) for dataset in datasets],
        warnings=list(dict.fromkeys(warnings)),
    )


@app.get("/api/v1/evidence/datasets", response_model=list[EvidenceDatasetRead], tags=["evidence"])
def list_evidence_datasets(principal: PrincipalDep, session: SessionDep) -> list[EvidenceDatasetRead]:
    principal.require("evidence:read")
    try:
        resolved = DatasetRepository(session, principal.tenant_id).resolve_for_principal(
            principal,
            [],
            allow_empty=True,
        )
    except DatasetAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DatasetSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    keys = [dataset.key for dataset in resolved]
    names = {
        dataset.dataset_key: dataset.display_name
        for dataset in session.scalars(
            select(TenantDataset).where(
                TenantDataset.tenant_id == principal.tenant_id,
                TenantDataset.dataset_key.in_(keys),
            )
        )
    }
    return [
        EvidenceDatasetRead(
            dataset_key=dataset.key,
            display_name=names.get(dataset.key, dataset.key),
            attribution=dataset.license_policy.attribution,
        )
        for dataset in resolved
    ]


@app.post("/api/v1/evidence/search", response_model=EvidenceSearchResponse, tags=["evidence"])
def search_evidence(
    payload: EvidenceSearchRequest,
    principal: PrincipalDep,
    session: SessionDep,
) -> EvidenceSearchResponse:
    return _search_evidence_response(payload, principal, session)


@app.get(
    "/api/v1/provenance/{resource_type}/{resource_id}",
    response_model=RecordProvenanceResponse,
    response_model_exclude_none=True,
    tags=["evidence"],
)
def get_record_provenance(
    resource_type: ProvenanceResourceType,
    resource_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> RecordProvenanceResponse:
    return _public_dossier_projection(
        _record_provenance_response(resource_type, str(resource_id), principal, session, limit=limit)
    )


@app.post(
    "/internal/v1/domain/evidence/search",
    response_model=AgentEvidenceSearchResult,
    tags=["internal-domain"],
)
def search_evidence_for_agent(
    payload: EvidenceSearchRequest,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentEvidenceSearchResult:
    principal.require("evidence:read")
    arguments: dict[str, object] = payload.model_dump(mode="json")
    if cursor is not None:
        arguments["cursor"] = cursor
    commercial_service = _commercial_service(session, principal)
    reservation = commercial_service.authorize_paginated_query(
        reservation_id,
        billing_class="evidence.search",
        request_arguments=arguments,
        page_size=payload.limit,
    )
    result = _search_evidence_response(
        payload,
        principal,
        session,
        limit=payload.limit + 1,
        offset=reservation.page_offset,
    )
    chunks = result.chunks[: payload.limit]
    next_cursor = commercial_service.issue_next_cursor(
        reservation,
        next_offset=reservation.page_offset + len(chunks),
        has_more=len(result.chunks) > payload.limit,
    )
    return AgentEvidenceSearchResult(
        **result.model_dump(exclude={"chunks"}),
        chunks=chunks,
        limit=payload.limit,
        page_depth=reservation.page_depth,
        next_cursor=next_cursor,
    )


@app.get(
    "/internal/v1/domain/provenance/{resource_type}/{resource_id}",
    response_model=RecordProvenanceResponse,
    tags=["internal-domain"],
)
def get_record_provenance_for_agent(
    resource_type: ProvenanceResourceType,
    resource_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    limit: int = Query(default=20, ge=1, le=100),
) -> RecordProvenanceResponse:
    resource_id_string = str(resource_id)
    _commercial_service(session, principal).authorize_paginated_query(
        reservation_id,
        billing_class="provenance.read",
        request_arguments={
            "resource_type": resource_type,
            "resource_id": resource_id_string,
            "limit": limit,
        },
        page_size=limit,
    )
    return _record_provenance_response(
        resource_type,
        resource_id_string,
        principal,
        session,
        limit=limit,
    )


@app.get(
    "/api/v1/targets/{target_id}/profile",
    response_model=TargetProfileResponse,
    response_model_exclude_none=True,
    tags=["targets"],
)
def get_target_profile(target_id: str, principal: PrincipalDep, session: SessionDep) -> TargetProfileResponse:
    principal.require("targets:read")
    result = _intelligence_service(session, principal).target_profile(target_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Target not found")
    _assert_public_entity_visible(result.entity, principal)
    return _public_dossier_projection(result)


@app.get(
    "/api/v1/targets/{target_id}/dossier",
    response_model=TargetDossierResponse,
    response_model_exclude_none=True,
    tags=["targets"],
)
def get_target_dossier(
    target_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> TargetDossierResponse:
    principal.require("targets:read")
    principal.require("dossiers:read")
    result = _intelligence_service(session, principal).target_dossier(target_id, limit)
    if result is None:
        raise HTTPException(status_code=404, detail="Target not found")
    _assert_public_entity_visible(result.profile.entity, principal)
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=result.profile.entity.id,
        details={"entity_type": result.profile.entity.entity_type.value},
    )
    return _public_dossier_projection(result)


@app.get(
    "/api/v1/targets/{target_id}/bioactivities",
    response_model=list[BioactivityRead],
    tags=["activities"],
)
def get_bioactivities(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    standard_type: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=200, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> list[BioactivityRead]:
    principal.require("activities:read")
    _assert_public_entity_ids_visible(session, principal, [target_id])
    return _intelligence_service(session, principal).bioactivities(target_id, standard_type, limit, offset)


@app.get(
    "/api/v1/targets/{target_id}/sar-comparison",
    response_model=SarComparisonResult,
    tags=["activities"],
)
def compare_target_sar(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    standard_type: str | None = Query(default=None, max_length=120),
    assay_type: str | None = Query(default=None, max_length=120),
    assay_format: str | None = Query(default=None, max_length=160),
    organism: str | None = Query(default=None, max_length=160),
    cell_line: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> SarComparisonResult:
    principal.require("activities:read")
    _assert_public_entity_ids_visible(session, principal, [target_id])
    return _intelligence_service(session, principal).sar_comparison(
        target_id,
        standard_type=standard_type,
        assay_type=assay_type,
        assay_format=assay_format,
        organism=organism,
        cell_line=cell_line,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/api/v1/targets/{target_id}/competitive-programs",
    response_model=list[CompetitiveProgramRead],
    tags=["pipelines"],
)
def get_competitive_programs(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=500, ge=1, le=5000),
) -> list[CompetitiveProgramRead]:
    principal.require("pipelines:read")
    _assert_public_entity_ids_visible(session, principal, [target_id])
    return _intelligence_service(session, principal).competitive_programs(target_id, limit)


@app.get("/api/v1/pipelines", response_model=PipelineSearchResult, tags=["pipelines"])
def search_pipelines(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    modality: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    innovation_type: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    therapeutic_area: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    drug_category: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    program_status: Literal["active", "inactive", "unknown"] | None = None,
    organization_role: (
        Literal["originator", "collaborator", "licensee", "licensor", "manufacturer", "other"] | None
    ) = None,
    organization_type: str | None = Query(default=None, min_length=1, max_length=120),
    organization_country_region: str | None = Query(default=None, min_length=1, max_length=120),
    phase: DevelopmentPhase | None = None,
    geography: str | None = Query(default=None, min_length=1, max_length=120),
    status_date_from: Annotated[datetime | None, Query()] = None,
    status_date_to: Annotated[datetime | None, Query()] = None,
    drug_entity_id: str | None = Query(default=None, min_length=36, max_length=36),
    target_entity_id: str | None = Query(default=None, max_length=36),
    target_combination_key: str | None = Query(
        default=None,
        max_length=760,
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}(?:\|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}){0,19}$",
    ),
    disease_entity_id: str | None = Query(default=None, max_length=36),
    organization_entity_id: str | None = Query(default=None, max_length=36),
    global_phase: DevelopmentPhase | None = None,
    china_phase: DevelopmentPhase | None = None,
    global_phase_started_from: Annotated[datetime | None, Query()] = None,
    global_phase_started_to: Annotated[datetime | None, Query()] = None,
    china_phase_started_from: Annotated[datetime | None, Query()] = None,
    china_phase_started_to: Annotated[datetime | None, Query()] = None,
    development_rights_region: str | None = Query(default=None, max_length=240),
    commercialization_rights_region: str | None = Query(default=None, max_length=240),
    program_tag: Annotated[list[PipelineProgramTagQueryValue] | None, Query(max_length=20)] = None,
    milestone_type: str | None = Query(default=None, max_length=120),
    milestone_from: Annotated[datetime | None, Query()] = None,
    milestone_to: Annotated[datetime | None, Query()] = None,
    has_clinical_results: bool | None = Query(default=None),
    clinical_result_evaluation: TrialResultEvaluation | None = None,
    has_deal: bool | None = Query(default=None),
    deal_currency: str | None = Query(default=None, pattern=r"^[A-Z]{3}$"),
    deal_total_potential_amount_min: float | None = Query(default=None, ge=0),
    deal_total_potential_amount_max: float | None = Query(default=None, ge=0),
    sort_by: PipelineSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
    landscape_limit: int = Query(default=20, ge=5, le=200),
    landscape_stage_scope: PipelineLandscapeStageScope = "overall",
    landscape_target_aggregation: PipelineTargetAggregation = "all",
    result_grain: PipelineResultGrain = "program",
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> PipelineSearchResult:
    principal.require("pipelines:read")
    effective_sort = _validated_sort(
        sort,
        PIPELINE_SORT_FIELDS,
        default_field="status_date",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    modality = _normalized_repeated_filter(modality)
    innovation_type = _normalized_repeated_filter(innovation_type)
    therapeutic_area = _normalized_repeated_filter(therapeutic_area)
    drug_category = _normalized_repeated_filter(drug_category)
    program_tag = _normalized_repeated_filter(program_tag)
    status_date_from, status_date_to = _validated_utc_datetime_range(
        status_date_from,
        status_date_to,
        start_field="status_date_from",
        end_field="status_date_to",
    )
    global_phase_started_from, global_phase_started_to = _validated_utc_datetime_range(
        global_phase_started_from,
        global_phase_started_to,
        start_field="global_phase_started_from",
        end_field="global_phase_started_to",
    )
    china_phase_started_from, china_phase_started_to = _validated_utc_datetime_range(
        china_phase_started_from,
        china_phase_started_to,
        start_field="china_phase_started_from",
        end_field="china_phase_started_to",
    )
    milestone_from, milestone_to = _validated_utc_datetime_range(
        milestone_from,
        milestone_to,
        start_field="milestone_from",
        end_field="milestone_to",
    )
    deal_total_potential_amount_min, deal_total_potential_amount_max = _validated_pipeline_signal_filters(
        has_clinical_results,
        clinical_result_evaluation,
        has_deal,
        deal_currency,
        deal_total_potential_amount_min,
        deal_total_potential_amount_max,
    )
    _assert_public_entity_ids_visible(
        session,
        principal,
        [
            drug_entity_id,
            target_entity_id,
            disease_entity_id,
            organization_entity_id,
            *(target_combination_key.split("|") if target_combination_key else []),
        ],
    )
    return _intelligence_service(session, principal).search_programs(
        q,
        modality,
        phase.value if phase else None,
        geography,
        limit,
        offset,
        innovation_type=innovation_type,
        therapeutic_area=therapeutic_area,
        drug_category=drug_category,
        program_status=program_status,
        organization_role=organization_role,
        organization_type=organization_type,
        organization_country_region=organization_country_region,
        status_date_from=status_date_from,
        status_date_to=status_date_to,
        drug_entity_id=drug_entity_id,
        target_entity_id=target_entity_id,
        target_combination_key=target_combination_key.lower() if target_combination_key else None,
        disease_entity_id=disease_entity_id,
        organization_entity_id=organization_entity_id,
        global_phase=global_phase.value if global_phase else None,
        china_phase=china_phase.value if china_phase else None,
        global_phase_started_from=global_phase_started_from,
        global_phase_started_to=global_phase_started_to,
        china_phase_started_from=china_phase_started_from,
        china_phase_started_to=china_phase_started_to,
        development_rights_region=development_rights_region,
        commercialization_rights_region=commercialization_rights_region,
        program_tag=program_tag,
        milestone_type=milestone_type,
        milestone_from=milestone_from,
        milestone_to=milestone_to,
        has_clinical_results=has_clinical_results,
        clinical_result_evaluation=(clinical_result_evaluation.value if clinical_result_evaluation else None),
        has_deal=has_deal,
        deal_currency=deal_currency,
        deal_total_potential_amount_min=deal_total_potential_amount_min,
        deal_total_potential_amount_max=deal_total_potential_amount_max,
        sort=effective_sort,
        landscape_limit=landscape_limit,
        landscape_stage_scope=landscape_stage_scope,
        landscape_target_aggregation=landscape_target_aggregation,
        result_grain=result_grain,
    )


@app.get("/api/v1/structures", response_model=list[CompoundStructureRead], tags=["structures"])
def search_structures(
    principal: PrincipalDep,
    session: SessionDep,
    entity_id: str | None = None,
    inchi_key: str | None = Query(default=None, max_length=27),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[CompoundStructureRead]:
    principal.require("structures:read")
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    return _intelligence_service(session, principal).structures(entity_id, inchi_key, limit)


@app.post(
    "/api/v1/chemistry/search",
    response_model=ChemistrySearchRead,
    tags=["structures"],
)
def search_chemistry(
    payload: ChemistrySearchRequest,
    principal: PrincipalDep,
    session: SessionDep,
) -> ChemistrySearchRead:
    principal.require("structures:read")
    return _execute_chemistry_search(session, principal.tenant_id, payload)


@app.get("/api/v1/clinical-trials", response_model=list[ClinicalTrialRead], tags=["clinical-trials"])
def search_clinical_trials(
    principal: PrincipalDep,
    session: SessionDep,
    entity_id: str | None = None,
    q: str | None = Query(default=None, max_length=500),
    has_results: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[ClinicalTrialRead]:
    principal.require("trials:read")
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    return _intelligence_service(session, principal).clinical_trials(
        entity_id,
        q,
        limit,
        has_results=has_results,
    )


@app.get("/api/v1/trials", response_model=ClinicalTrialSearchResult, tags=["trials"])
def search_trials(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    registry: str | None = Query(default=None, max_length=80),
    overall_status: str | None = Query(default=None, alias="status", max_length=100),
    phase: str | None = Query(default=None, max_length=80),
    study_type: str | None = Query(default=None, max_length=80),
    acronym: str | None = Query(default=None, max_length=240),
    initiation_type: TrialInitiationType | None = None,
    therapy_line: TrialTherapyLine | None = None,
    has_results: bool | None = Query(default=None),
    result_evaluation: TrialResultEvaluation | None = None,
    results_posted_from: Annotated[datetime | None, Query()] = None,
    results_posted_to: Annotated[datetime | None, Query()] = None,
    investigational_drug: str | None = Query(default=None, max_length=500),
    combination_drug: str | None = Query(default=None, max_length=500),
    investigational_target: str | None = Query(default=None, max_length=500),
    combination_target: str | None = Query(default=None, max_length=500),
    investigational_drug_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    combination_drug_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    investigational_target_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    combination_target_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    linked_drug_modality: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    linked_drug_innovation_type: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    linked_drug_category: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    linked_drug_program_tag: Annotated[list[PipelineProgramTagQueryValue] | None, Query(max_length=20)] = None,
    linked_drug_global_phase: DevelopmentPhase | None = None,
    linked_drug_organization_country_region: str | None = Query(default=None, min_length=1, max_length=120),
    role_entity_id: str | None = Query(default=None, max_length=36),
    role_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    role_entity_role: TrialEntityRole | None = None,
    has_key_result: bool | None = Query(default=None),
    publication_id: str | None = Query(default=None, max_length=240),
    conference: str | None = Query(default=None, max_length=500),
    disclosed_from: Annotated[datetime | None, Query()] = None,
    disclosed_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    sort_by: ClinicalTrialSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> ClinicalTrialSearchResult:
    principal.require("trials:read")
    effective_sort = _validated_sort(
        sort,
        CLINICAL_TRIAL_SORT_FIELDS,
        default_field="last_update_posted",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    results_posted_from, results_posted_to = _validated_utc_datetime_range(
        results_posted_from,
        results_posted_to,
        start_field="results_posted_from",
        end_field="results_posted_to",
    )
    disclosed_from, disclosed_to = _validated_utc_datetime_range(
        disclosed_from,
        disclosed_to,
        start_field="disclosed_from",
        end_field="disclosed_to",
    )
    role_entity_id, role_entity_ids, role_entity_role = _validated_trial_role_entity_filter(
        role_entity_id,
        role_entity_ids,
        role_entity_role,
    )
    investigational_drug_entity_ids = _validated_trial_role_entity_ids(
        "investigational_drug_entity_ids", investigational_drug_entity_ids
    )
    combination_drug_entity_ids = _validated_trial_role_entity_ids(
        "combination_drug_entity_ids", combination_drug_entity_ids
    )
    investigational_target_entity_ids = _validated_trial_role_entity_ids(
        "investigational_target_entity_ids", investigational_target_entity_ids
    )
    combination_target_entity_ids = _validated_trial_role_entity_ids(
        "combination_target_entity_ids", combination_target_entity_ids
    )
    linked_drug_modality = _normalized_repeated_filter(linked_drug_modality)
    linked_drug_innovation_type = _normalized_repeated_filter(linked_drug_innovation_type)
    linked_drug_category = _normalized_repeated_filter(linked_drug_category)
    linked_drug_program_tag = _normalized_repeated_filter(linked_drug_program_tag)
    _assert_public_entity_ids_visible(
        session,
        principal,
        [role_entity_id],
    )
    _assert_public_entity_ids_visible(
        session,
        principal,
        [
            *(role_entity_ids or []),
            *(investigational_drug_entity_ids or []),
            *(combination_drug_entity_ids or []),
            *(investigational_target_entity_ids or []),
            *(combination_target_entity_ids or []),
        ],
        reject_missing=False,
    )
    return _intelligence_service(session, principal).search_clinical_trials(
        q,
        registry,
        overall_status,
        phase,
        study_type,
        has_results,
        limit,
        offset,
        results_posted_from=results_posted_from,
        results_posted_to=results_posted_to,
        result_evaluation=result_evaluation.value if result_evaluation else None,
        acronym=acronym,
        initiation_type=initiation_type,
        therapy_line=therapy_line,
        investigational_drug=investigational_drug,
        combination_drug=combination_drug,
        investigational_target=investigational_target,
        combination_target=combination_target,
        investigational_drug_entity_ids=investigational_drug_entity_ids,
        combination_drug_entity_ids=combination_drug_entity_ids,
        investigational_target_entity_ids=investigational_target_entity_ids,
        combination_target_entity_ids=combination_target_entity_ids,
        linked_drug_modality=linked_drug_modality,
        linked_drug_innovation_type=linked_drug_innovation_type,
        linked_drug_category=linked_drug_category,
        linked_drug_program_tag=linked_drug_program_tag,
        linked_drug_global_phase=linked_drug_global_phase.value if linked_drug_global_phase else None,
        linked_drug_organization_country_region=linked_drug_organization_country_region,
        role_entity_id=role_entity_id,
        role_entity_ids=role_entity_ids,
        role_entity_role=role_entity_role.value if role_entity_role else None,
        has_key_result=has_key_result,
        publication_id=publication_id,
        conference=conference,
        disclosed_from=disclosed_from,
        disclosed_to=disclosed_to,
        sort=effective_sort,
    )


@app.get("/api/v1/trials/{trial_id}", response_model=ClinicalTrialDetailRead, tags=["trials"])
def get_trial_detail(
    trial_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> ClinicalTrialDetailRead:
    principal.require("trials:read")
    result = _intelligence_service(session, principal).clinical_trial_detail(trial_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Clinical trial not found")
    return result


@app.get("/api/v1/patents", response_model=list[PatentFamilyRead], tags=["patents"])
def search_patents(
    principal: PrincipalDep,
    session: SessionDep,
    entity_id: str | None = None,
    q: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[PatentFamilyRead]:
    principal.require("patents:read")
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    return _intelligence_service(session, principal).patents(entity_id, q, limit)


@app.get("/api/v1/patent-families", response_model=PatentFamilySearchResult, tags=["patents"])
def search_patent_families(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    entity_id: str | None = Query(default=None, max_length=36),
    applicant: str | None = Query(default=None, max_length=300),
    legal_status: str | None = Query(default=None, max_length=120),
    priority_from: Annotated[datetime | None, Query()] = None,
    priority_to: Annotated[datetime | None, Query()] = None,
    expiration_from: Annotated[datetime | None, Query()] = None,
    expiration_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    sort_by: PatentSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> PatentFamilySearchResult:
    principal.require("patents:read")
    effective_sort = _validated_sort(
        sort,
        PATENT_SORT_FIELDS,
        default_field="priority_date",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    priority_from, priority_to = _validated_utc_datetime_range(
        priority_from, priority_to, start_field="priority_from", end_field="priority_to"
    )
    expiration_from, expiration_to = _validated_utc_datetime_range(
        expiration_from, expiration_to, start_field="expiration_from", end_field="expiration_to"
    )
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    return _intelligence_service(session, principal).search_patent_families(
        q,
        applicant,
        legal_status,
        limit,
        offset,
        entity_id=entity_id,
        priority_from=priority_from,
        priority_to=priority_to,
        expiration_from=expiration_from,
        expiration_to=expiration_to,
        sort=effective_sort,
    )


@app.get(
    "/api/v1/patent-families/{family_id}",
    response_model=PatentFamilySearchItemRead,
    tags=["patents"],
)
def get_patent_family(
    family_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> PatentFamilySearchItemRead:
    principal.require("patents:read")
    family = _intelligence_service(session, principal).patent_family_detail(family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Patent family not found")
    return family


@app.get("/api/v1/deals", response_model=list[DealRead], tags=["deals"])
def search_deals(
    principal: PrincipalDep,
    session: SessionDep,
    entity_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[DealRead]:
    principal.require("deals:read")
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    return _intelligence_service(session, principal).deals(entity_id, limit)


@app.get("/api/v1/deal-transactions", response_model=DealSearchResult, tags=["deals"])
def search_deal_transactions(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    deal_type: str | None = Query(default=None, max_length=100),
    deal_status: Annotated[DealStatus | None, Query(alias="status")] = None,
    direction: DealDirection | None = None,
    direction_reference_jurisdiction: str | None = Query(default=None, max_length=120),
    territory: str | None = Query(default=None, max_length=240),
    asset_entity_id: str | None = Query(default=None, min_length=36, max_length=36),
    target_entity_id: str | None = Query(default=None, min_length=36, max_length=36),
    disease_entity_id: str | None = Query(default=None, min_length=36, max_length=36),
    asset_modality: Annotated[list[DealAssetModalityQueryValue] | None, Query(max_length=20)] = None,
    asset_program_tag: Annotated[list[DealAssetProgramTagQueryValue] | None, Query(max_length=20)] = None,
    party: str | None = Query(default=None, max_length=500),
    party_entity_id: str | None = Query(default=None, max_length=36),
    party_role: DealPartyRole | None = None,
    party_country_region: str | None = Query(default=None, max_length=120),
    party_organization_type: str | None = Query(default=None, max_length=120),
    development_phase_at_transaction: DevelopmentPhase | None = None,
    current_development_phase: DevelopmentPhase | None = None,
    right_type: DealRightType | None = None,
    rights_territory: str | None = Query(default=None, max_length=240),
    currency: str | None = Query(default=None, pattern=r"^[A-Z]{3}$"),
    announced_from: Annotated[datetime | None, Query()] = None,
    announced_to: Annotated[datetime | None, Query()] = None,
    terminated_from: Annotated[datetime | None, Query()] = None,
    terminated_to: Annotated[datetime | None, Query()] = None,
    source_updated_from: Annotated[datetime | None, Query()] = None,
    source_updated_to: Annotated[datetime | None, Query()] = None,
    upfront_amount_min: float | None = Query(default=None, ge=0),
    upfront_amount_max: float | None = Query(default=None, ge=0),
    total_potential_amount_min: float | None = Query(default=None, ge=0),
    total_potential_amount_max: float | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    sort_by: DealSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
    analysis_top: int = Query(default=8, ge=5, le=50),
) -> DealSearchResult:
    principal.require("deals:read")
    if analysis_top not in {5, 8, 20, 50}:
        raise HTTPException(status_code=422, detail="analysis_top must be one of 5, 8, 20 or 50")
    effective_sort = _validated_sort(
        sort,
        DEAL_SORT_FIELDS,
        default_field="announced_at",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    _validate_deal_amount_sort(effective_sort, currency)
    announced_from, announced_to = _validated_utc_datetime_range(
        announced_from,
        announced_to,
        start_field="announced_from",
        end_field="announced_to",
    )
    terminated_from, terminated_to = _validated_utc_datetime_range(
        terminated_from,
        terminated_to,
        start_field="terminated_from",
        end_field="terminated_to",
    )
    source_updated_from, source_updated_to = _validated_utc_datetime_range(
        source_updated_from,
        source_updated_to,
        start_field="source_updated_from",
        end_field="source_updated_to",
    )
    upfront_amount_min, upfront_amount_max = _validated_number_range(
        upfront_amount_min,
        upfront_amount_max,
        minimum_field="upfront_amount_min",
        maximum_field="upfront_amount_max",
    )
    total_potential_amount_min, total_potential_amount_max = _validated_number_range(
        total_potential_amount_min,
        total_potential_amount_max,
        minimum_field="total_potential_amount_min",
        maximum_field="total_potential_amount_max",
    )
    asset_modality = _normalized_repeated_filter(asset_modality)
    asset_program_tag = _normalized_repeated_filter(asset_program_tag)
    _assert_public_entity_ids_visible(
        session,
        principal,
        [asset_entity_id, target_entity_id, disease_entity_id, party_entity_id],
    )
    return _intelligence_service(session, principal).search_deals(
        q,
        deal_type,
        territory,
        party,
        limit,
        offset,
        status=deal_status.value if deal_status else None,
        direction=direction.value if direction else None,
        direction_reference_jurisdiction=direction_reference_jurisdiction,
        asset_entity_id=asset_entity_id,
        target_entity_id=target_entity_id,
        disease_entity_id=disease_entity_id,
        asset_modality=asset_modality,
        asset_program_tag=asset_program_tag,
        party_entity_id=party_entity_id,
        party_role=party_role.value if party_role else None,
        party_country_region=party_country_region,
        party_organization_type=party_organization_type,
        development_phase_at_transaction=(
            development_phase_at_transaction.value if development_phase_at_transaction else None
        ),
        current_development_phase=current_development_phase.value if current_development_phase else None,
        right_type=right_type.value if right_type else None,
        rights_territory=rights_territory,
        currency=currency,
        announced_from=announced_from,
        announced_to=announced_to,
        terminated_from=terminated_from,
        terminated_to=terminated_to,
        source_updated_from=source_updated_from,
        source_updated_to=source_updated_to,
        upfront_amount_min=upfront_amount_min,
        upfront_amount_max=upfront_amount_max,
        total_potential_amount_min=total_potential_amount_min,
        total_potential_amount_max=total_potential_amount_max,
        sort=effective_sort,
        landscape_limit=cast(DealAnalysisLimit, analysis_top),
    )


@app.get("/api/v1/deal-transactions/{deal_id}", response_model=DealSearchItemRead, tags=["deals"])
def get_deal_transaction(
    deal_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> DealSearchItemRead:
    principal.require("deals:read")
    deal = _intelligence_service(session, principal).deal_detail(deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal transaction not found")
    return deal


@app.get(
    "/api/v1/companies/{company_id}/dossier",
    response_model=CompanyDossierResponse,
    response_model_exclude_none=True,
    tags=["companies"],
)
def get_company_dossier(
    company_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=100),
) -> CompanyDossierResponse:
    principal.require("dossiers:read")
    principal.require("pipelines:read")
    principal.require("deals:read")
    dossier = _intelligence_service(session, principal).company_dossier(company_id, limit)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Company not found")
    _assert_public_entity_visible(dossier.entity, principal)
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=dossier.entity.id,
        details={"entity_type": dossier.entity.entity_type.value, "profile": "company"},
    )
    return _public_dossier_projection(dossier)


@app.get(
    "/api/v1/companies/{company_id}/timeline",
    response_model=CompanyTimelineResult,
    tags=["companies"],
)
def get_company_timeline(
    company_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> CompanyTimelineResult:
    principal.require("pipelines:read")
    principal.require("deals:read")
    _assert_public_entity_ids_visible(session, principal, [company_id])
    result = _intelligence_service(session, principal).company_timeline(company_id, limit, offset)
    if result is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return result


@app.get("/api/v1/regulatory-events", response_model=list[RegulatoryEventRead], tags=["regulatory"])
def search_regulatory_events(
    principal: PrincipalDep,
    session: SessionDep,
    entity_id: str | None = None,
    q: str | None = Query(default=None, max_length=500),
    agency: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[RegulatoryEventRead]:
    principal.require("regulatory:read")
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    return _intelligence_service(session, principal).regulatory_events(entity_id, q, agency, limit)


@app.get(
    "/api/v1/regulatory-event-timeline",
    response_model=RegulatoryEventSearchResult,
    tags=["regulatory"],
)
def search_regulatory_event_timeline(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    agency: str | None = Query(default=None, max_length=80),
    jurisdiction: str | None = Query(default=None, max_length=120),
    event_type: str | None = Query(default=None, max_length=40),
    status: str | None = Query(default=None, max_length=120),
    designation_type: RegulatoryDesignationType | None = None,
    label_change_type: RegulatoryLabelChangeType | None = None,
    has_boxed_warning: bool | None = None,
    safety_signal_type: RegulatorySafetySignalType | None = None,
    safety_severity: RegulatorySafetySeverity | None = None,
    safety_status: RegulatorySafetyStatus | None = None,
    decision_from: Annotated[datetime | None, Query()] = None,
    decision_to: Annotated[datetime | None, Query()] = None,
    source_updated_from: Annotated[datetime | None, Query()] = None,
    source_updated_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    sort_by: RegulatorySortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> RegulatoryEventSearchResult:
    principal.require("regulatory:read")
    effective_sort = _validated_sort(
        sort,
        REGULATORY_SORT_FIELDS,
        default_field="decision_date",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    decision_from, decision_to = _validated_utc_datetime_range(
        decision_from,
        decision_to,
        start_field="decision_from",
        end_field="decision_to",
    )
    source_updated_from, source_updated_to = _validated_utc_datetime_range(
        source_updated_from,
        source_updated_to,
        start_field="source_updated_from",
        end_field="source_updated_to",
    )
    return _intelligence_service(session, principal).search_regulatory_events(
        q,
        agency,
        jurisdiction,
        event_type,
        status,
        limit,
        offset,
        designation_type=designation_type.value if designation_type else None,
        label_change_type=label_change_type.value if label_change_type else None,
        has_boxed_warning=has_boxed_warning,
        safety_signal_type=safety_signal_type.value if safety_signal_type else None,
        safety_severity=safety_severity.value if safety_severity else None,
        safety_status=safety_status.value if safety_status else None,
        decision_from=decision_from,
        decision_to=decision_to,
        source_updated_from=source_updated_from,
        source_updated_to=source_updated_to,
        sort=effective_sort,
    )


@app.get(
    "/api/v1/regulatory-event-timeline/{event_id}",
    response_model=RegulatoryEventSearchItemRead,
    tags=["regulatory"],
)
def get_regulatory_event_timeline_item(
    event_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> RegulatoryEventSearchItemRead:
    principal.require("regulatory:read")
    event = _intelligence_service(session, principal).regulatory_event_detail(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Regulatory event not found")
    return event


@app.get(
    "/api/v1/epidemiology-observations",
    response_model=EpidemiologyObservationSearchResult,
    tags=["epidemiology"],
)
def search_epidemiology_observations(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    disease_entity_id: str | None = Query(default=None, max_length=36),
    measure: str | None = Query(default=None, max_length=40),
    geography: str | None = Query(default=None, max_length=160),
    unit: str | None = Query(default=None, max_length=120),
    population_scope: str | None = Query(default=None, max_length=500),
    patient_population_id: str | None = Query(default=None, max_length=36),
    age_group: str | None = Query(default=None, max_length=120),
    sex: str | None = Query(default=None, max_length=80),
    period_start_from: Annotated[datetime | None, Query()] = None,
    period_end_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    sort_by: EpidemiologySortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> EpidemiologyObservationSearchResult:
    principal.require("epidemiology:read")
    _assert_public_entity_ids_visible(session, principal, [disease_entity_id])
    effective_sort = _validated_sort(
        sort,
        EPIDEMIOLOGY_SORT_FIELDS,
        default_field="period_end",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    return _intelligence_service(session, principal).search_epidemiology_observations(
        q,
        measure,
        geography,
        unit,
        population_scope,
        age_group,
        sex,
        period_start_from,
        period_end_to,
        limit,
        offset,
        disease_entity_id=disease_entity_id,
        patient_population_id=patient_population_id,
        sort=effective_sort,
    )


@app.get(
    "/api/v1/epidemiology-trends/{disease_entity_id}",
    response_model=EpidemiologyTrendResult,
    tags=["epidemiology"],
)
def get_epidemiology_trend(
    disease_entity_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    measure: str | None = Query(default=None, max_length=40),
    geography: str | None = Query(default=None, max_length=160),
    unit: str | None = Query(default=None, max_length=120),
    population_scope: str | None = Query(default=None, max_length=500),
    patient_population_id: str | None = Query(default=None, max_length=36),
    age_group: str | None = Query(default=None, max_length=120),
    sex: str | None = Query(default=None, max_length=80),
    anchor_observation_id: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=200, ge=1, le=500),
) -> EpidemiologyTrendResult:
    principal.require("epidemiology:read")
    _assert_public_entity_ids_visible(session, principal, [disease_entity_id])
    result = _intelligence_service(session, principal).epidemiology_trend(
        disease_entity_id,
        measure,
        geography,
        unit,
        population_scope,
        age_group,
        sex,
        limit,
        patient_population_id=patient_population_id,
        anchor_observation_id=anchor_observation_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Disease not found")
    return result


@app.get("/api/v1/news-events", response_model=NewsEventSearchResult, tags=["news"])
def search_news_events(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    entity_id: str | None = Query(default=None, max_length=36),
    event_type: str | None = Query(default=None, max_length=40),
    publisher: str | None = Query(default=None, max_length=500),
    language: str | None = Query(default=None, max_length=32),
    venue: str | None = Query(default=None, max_length=240),
    content_scope: Literal["research"] | None = Query(default=None),
    published_from: Annotated[datetime | None, Query()] = None,
    published_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    sort_by: NewsSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> NewsEventSearchResult:
    principal.require("news:read")
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    effective_sort = _validated_sort(
        sort,
        NEWS_SORT_FIELDS,
        default_field="published_at",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    return _intelligence_service(session, principal).search_news_events(
        q,
        event_type,
        publisher,
        language,
        venue,
        published_from,
        published_to,
        limit,
        offset,
        research_content_only=content_scope == "research",
        entity_id=entity_id,
        sort=effective_sort,
    )


@app.get(
    "/api/v1/news-events/{event_id}",
    response_model=NewsEventSearchItemRead,
    tags=["news"],
)
def get_news_event(
    event_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> NewsEventSearchItemRead:
    principal.require("news:read")
    event = _intelligence_service(session, principal).news_event_detail(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="News event not found")
    return event


@app.get("/api/v1/admin/data-sources", response_model=list[DataSourceRead], tags=["data-factory"])
def list_data_sources(principal: PrincipalDep, session: SessionDep) -> list[DataSourceRead]:
    principal.require("ingestion:read")
    sources = session.scalars(
        select(DataSource).where(DataSource.tenant_id == principal.tenant_id).order_by(DataSource.name)
    )
    return [DataSourceRead.model_validate(source) for source in sources]


@app.get(
    "/api/v1/admin/ingestion-capabilities",
    response_model=IngestionCapabilitiesRead,
    tags=["data-factory"],
)
def get_ingestion_capabilities(principal: PrincipalDep) -> IngestionCapabilitiesRead:
    principal.require("ingestion:read")
    settings = get_settings()
    return IngestionCapabilitiesRead(
        automatic_scheduling_enabled=settings.temporal_enabled and settings.temporal_scheduler_enabled,
        durable_workflows_enabled=settings.temporal_enabled and settings.temporal_worker_enabled,
        isolated_parser_enabled=settings.parser_backend == "service",
        malware_scanning_enabled=settings.malware_scan_enabled,
        ai_governance_enabled=settings.ai_governance_enabled,
        ai_model_configured=bool(settings.ai_base_url and settings.ai_api_key and settings.ai_model),
        ai_model=settings.ai_model or None,
        ai_auto_publish_threshold=settings.ai_auto_publish_threshold,
        allowed_folder_roots=sorted(str(root) for root in settings.source_roots),
        parseable_extensions=sorted(PARSEABLE_EXTENSIONS),
        asset_only_extensions=sorted(ASSET_ONLY_EXTENSIONS),
    )


@app.get(
    "/api/v1/admin/data-source-datasets",
    response_model=list[DataSourceDatasetRead],
    tags=["data-factory"],
)
def list_data_source_datasets(principal: PrincipalDep, session: SessionDep) -> list[DataSourceDatasetRead]:
    principal.require("ingestion:read")
    now = datetime.now(UTC)
    datasets = session.scalars(
        select(TenantDataset).where(TenantDataset.tenant_id == principal.tenant_id).order_by(TenantDataset.display_name)
    )
    result: list[DataSourceDatasetRead] = []
    for dataset in datasets:
        try:
            policy = EvidenceLicensePolicy.model_validate(dataset.license_policy)
        except ValueError:
            result.append(
                DataSourceDatasetRead(
                    dataset_key=dataset.dataset_key,
                    display_name=dataset.display_name,
                    active=dataset.active,
                    license_id="invalid",
                    license_policy_version="invalid",
                    permitted_channels=[],
                    license_current=False,
                    attribution="Invalid license policy",
                )
            )
            continue
        channels: list[DeliveryChannel] = []
        if policy.permits("web", now):
            channels.append("web")
        if policy.permits("mcp", now):
            channels.append("mcp")
        result.append(
            DataSourceDatasetRead(
                dataset_key=dataset.dataset_key,
                display_name=dataset.display_name,
                active=dataset.active,
                license_id=policy.license_id,
                license_policy_version=policy.policy_version,
                permitted_channels=channels,
                license_current=bool(channels),
                attribution=policy.attribution,
            )
        )
    return result


@app.get(
    "/api/v1/admin/data-source-readiness",
    response_model=list[DataSourceReadinessRead],
    tags=["data-factory"],
)
def list_data_source_readiness(principal: PrincipalDep, session: SessionDep) -> list[DataSourceReadinessRead]:
    principal.require("ingestion:read")
    settings = get_settings()
    service = SourceReadinessService(session, settings, principal.tenant_id)
    sources = session.scalars(
        select(DataSource).where(DataSource.tenant_id == principal.tenant_id).order_by(DataSource.name)
    )
    return [DataSourceReadinessRead.model_validate(service.evaluate(source)) for source in sources]


def _normalized_source_root(source_type: DataSourceType, root_uri: str) -> str:
    try:
        connector = SourceConnectorRegistry(get_settings()).get(source_type)
        return connector.normalize_root_uri(root_uri)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _validate_source_connector(source: DataSource) -> None:
    try:
        connector = SourceConnectorRegistry(get_settings()).get(source.source_type)
        errors = connector.validate_configuration(source)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if errors:
        raise HTTPException(status_code=422, detail=errors[0])


def _validate_source_authorization_window(source: DataSource) -> None:
    valid_from = source.authorization_valid_from
    if valid_from is None:
        raise HTTPException(status_code=422, detail="Source authorization effective time is required")
    valid_until = source.authorization_valid_until
    effective_at = valid_from.replace(tzinfo=UTC) if valid_from.tzinfo is None else valid_from.astimezone(UTC)
    expires_at = (
        valid_until.replace(tzinfo=UTC)
        if valid_until is not None and valid_until.tzinfo is None
        else valid_until.astimezone(UTC)
        if valid_until is not None
        else None
    )
    if expires_at is not None and expires_at <= effective_at:
        raise HTTPException(status_code=422, detail="Authorization end must be later than its effective time")


def _add_data_source_audit(
    session: Session,
    request: Request,
    principal: Principal,
    source: DataSource,
    *,
    action: str,
    details: dict[str, Any],
) -> None:
    session.add(
        AuditEvent(
            tenant_id=principal.tenant_id,
            actor_type=principal.actor_type,
            actor_id=principal.actor_id,
            action=action,
            resource_type="data_source",
            resource_id=source.id,
            outcome="success",
            request_id=request.state.request_id,
            details=details,
        )
    )


def _prospective_source(source: DataSource, values: dict[str, object]) -> DataSource:
    def updated(field: str, current: Any) -> Any:
        return values[field] if field in values else current

    reset_cursor = any(field in values for field in ("root_uri", "include_globs", "exclude_globs", "routing_rules"))
    return DataSource(
        tenant_id=source.tenant_id,
        name=str(updated("name", source.name)),
        source_type=source.source_type,
        root_uri=str(updated("root_uri", source.root_uri)),
        credential_ref=updated("credential_ref", source.credential_ref),
        owner=str(updated("owner", source.owner)),
        data_classification=str(updated("data_classification", source.data_classification)),
        authorization_scopes=updated("authorization_scopes", source.authorization_scopes),
        authorization_valid_from=updated("authorization_valid_from", source.authorization_valid_from),
        authorization_valid_until=updated("authorization_valid_until", source.authorization_valid_until),
        dataset_key=str(updated("dataset_key", source.dataset_key)),
        include_globs=updated("include_globs", source.include_globs),
        exclude_globs=updated("exclude_globs", source.exclude_globs),
        routing_rules=updated("routing_rules", source.routing_rules),
        stable_seconds=int(updated("stable_seconds", source.stable_seconds)),
        max_file_bytes=int(updated("max_file_bytes", source.max_file_bytes)),
        scan_interval_seconds=int(updated("scan_interval_seconds", source.scan_interval_seconds)),
        expected_freshness_seconds=int(updated("expected_freshness_seconds", source.expected_freshness_seconds)),
        rate_limit_per_minute=int(updated("rate_limit_per_minute", source.rate_limit_per_minute)),
        connector_cursor={} if reset_cursor else source.connector_cursor,
    )


def _validate_globs(include_globs: list[str], exclude_globs: list[str]) -> None:
    if any(not pattern.strip() or "\x00" in pattern for pattern in include_globs + exclude_globs):
        raise HTTPException(status_code=422, detail="Glob patterns cannot be empty or contain NUL bytes")


def _require_ingestion_dataset(session: Session, tenant_id: str, dataset_key: str) -> TenantDataset:
    dataset = session.scalar(
        select(TenantDataset).where(
            TenantDataset.tenant_id == tenant_id,
            TenantDataset.dataset_key == dataset_key,
        )
    )
    if dataset is None:
        raise HTTPException(status_code=422, detail="Target dataset is not registered for this tenant")
    if not dataset.active:
        raise HTTPException(status_code=422, detail="Target dataset is disabled")
    try:
        policy = EvidenceLicensePolicy.model_validate(dataset.license_policy)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Target dataset license policy is invalid") from exc
    now = datetime.now(UTC)
    if not policy.permits("web", now) and not policy.permits("mcp", now):
        raise HTTPException(status_code=422, detail="Target dataset license is not currently deliverable")
    return dataset


@app.post(
    "/api/v1/admin/data-sources",
    response_model=DataSourceRead,
    status_code=status.HTTP_201_CREATED,
    tags=["data-factory"],
)
def create_data_source(
    payload: DataSourceCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataSourceRead:
    principal.require("ingestion:manage")
    root = _normalized_source_root(payload.source_type, payload.root_uri)
    _validate_globs(payload.include_globs, payload.exclude_globs)
    _require_ingestion_dataset(session, principal.tenant_id, payload.dataset_key)
    source = DataSource(
        tenant_id=principal.tenant_id,
        name=payload.name.strip(),
        source_type=payload.source_type,
        root_uri=root,
        credential_ref=payload.credential_ref,
        owner=payload.owner,
        data_classification=payload.data_classification,
        authorization_scopes=payload.authorization_scopes,
        authorization_valid_from=payload.authorization_valid_from,
        authorization_valid_until=payload.authorization_valid_until,
        dataset_key=payload.dataset_key,
        include_globs=payload.include_globs,
        exclude_globs=payload.exclude_globs,
        routing_rules=[rule.document() for rule in payload.routing_rules],
        stable_seconds=payload.stable_seconds,
        max_file_bytes=payload.max_file_bytes,
        scan_interval_seconds=payload.scan_interval_seconds,
        expected_freshness_seconds=payload.expected_freshness_seconds,
        rate_limit_per_minute=payload.rate_limit_per_minute,
    )
    _validate_source_connector(source)
    _validate_source_authorization_window(source)
    session.add(source)
    try:
        session.flush()
        _add_data_source_audit(
            session,
            request,
            principal,
            source,
            action="data_source.create",
            details={"config_version": source.config_version},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="A data source with this name or root already exists") from exc
    return DataSourceRead.model_validate(source)


@app.patch(
    "/api/v1/admin/data-sources/{data_source_id}",
    response_model=DataSourceRead,
    tags=["data-factory"],
)
def update_data_source(
    data_source_id: str,
    payload: DataSourceUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataSourceRead:
    principal.require("ingestion:manage")
    source = session.scalar(
        select(DataSource).where(
            DataSource.id == data_source_id,
            DataSource.tenant_id == principal.tenant_id,
        )
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Data source not found")

    values = payload.model_dump(exclude_unset=True)
    if "routing_rules" in payload.model_fields_set:
        values["routing_rules"] = [rule.document() for rule in payload.routing_rules or []]
    if "root_uri" in values and values["root_uri"] is not None:
        values["root_uri"] = _normalized_source_root(source.source_type, str(values["root_uri"]))
    if "dataset_key" in values and values["dataset_key"] is not None:
        _require_ingestion_dataset(session, principal.tenant_id, str(values["dataset_key"]))
    include_globs = values.get("include_globs", source.include_globs)
    exclude_globs = values.get("exclude_globs", source.exclude_globs)
    _validate_globs(include_globs, exclude_globs)
    prospective_source = _prospective_source(source, values)
    _validate_source_connector(prospective_source)
    _validate_source_authorization_window(prospective_source)

    identity_changed = any(
        key in values and values[key] != getattr(source, key) for key in ("root_uri", "dataset_key", "routing_rules")
    )
    if identity_changed:
        asset_exists = session.scalar(
            select(SourceAsset.id)
            .where(
                SourceAsset.tenant_id == principal.tenant_id,
                SourceAsset.data_source_id == source.id,
            )
            .limit(1)
        )
        if asset_exists is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Root, dataset, or routing-rule changes require a governed source migration "
                    "after assets have been discovered"
                ),
            )

    changed_fields = sorted(field for field, value in values.items() if value != getattr(source, field))
    for field, value in values.items():
        setattr(source, field, value)
    if any(field in values for field in ("root_uri", "include_globs", "exclude_globs", "routing_rules")):
        source.connector_cursor = {}
        source.last_cursor_at = None
    if source.state == DataSourceState.UNAVAILABLE:
        source.state = DataSourceState.ACTIVE
        source.unavailable_since = None
        source.last_error = None
    source.config_version += 1
    authorization_fields = {"authorization_scopes", "authorization_valid_from", "authorization_valid_until"}
    audit_action = (
        "data_source.authorization.update"
        if authorization_fields.intersection(changed_fields)
        else "data_source.update"
    )
    _add_data_source_audit(
        session,
        request,
        principal,
        source,
        action=audit_action,
        details={"changed_fields": changed_fields, "config_version": source.config_version},
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="A data source with this name or root already exists") from exc
    return DataSourceRead.model_validate(source)


@app.patch(
    "/api/v1/admin/data-sources/{data_source_id}/state",
    response_model=DataSourceRead,
    tags=["data-factory"],
)
def update_data_source_state(
    data_source_id: str,
    payload: DataSourceStateUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataSourceRead:
    principal.require("ingestion:manage")
    source = session.scalar(
        select(DataSource).where(
            DataSource.id == data_source_id,
            DataSource.tenant_id == principal.tenant_id,
        )
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Data source not found")
    previous_state = source.state
    source.state = payload.state
    source.config_version += 1
    _add_data_source_audit(
        session,
        request,
        principal,
        source,
        action="data_source.state.update",
        details={
            "previous_state": previous_state.value,
            "state": source.state.value,
            "config_version": source.config_version,
        },
    )
    session.commit()
    return DataSourceRead.model_validate(source)


async def _start_data_source_scan(
    source: DataSource,
    principal: Principal,
    session: Session,
    *,
    replayed_from_run_id: str | None = None,
    run_correlation_id: str | None = None,
) -> IngestionScanAcceptedRead:
    if source.state in {DataSourceState.PAUSED, DataSourceState.DISABLED}:
        raise HTTPException(status_code=409, detail=f"Data source is {source.state.value}")
    settings = get_settings()
    readiness = SourceReadinessService(session, settings, principal.tenant_id).evaluate(source)
    if not readiness.configuration_ready:
        raise HTTPException(
            status_code=409,
            detail={"code": "source_governance_blocked", "checks": readiness.blocking_messages},
        )
    if not settings.temporal_enabled:
        raise HTTPException(status_code=503, detail="Durable workflow service is not enabled")
    workflow_id = f"source-ingest-{source.id}"
    run_correlation_id = run_correlation_id or f"{workflow_id}-{uuid.uuid4()}"
    try:
        client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
        await client.start_workflow(
            DataSourceIngestionWorkflow.run,
            ScanInput(principal.tenant_id, source.id, run_correlation_id),
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        )
    except WorkflowAlreadyStartedError as exc:
        raise HTTPException(status_code=409, detail="A scan is already running for this data source") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Durable workflow service is unavailable") from exc
    return IngestionScanAcceptedRead(
        workflow_id=workflow_id,
        ingestion_run_id=run_correlation_id,
        status="accepted",
        replayed_from_run_id=replayed_from_run_id,
    )


@app.post(
    "/api/v1/admin/data-sources/{data_source_id}/scan",
    response_model=IngestionScanAcceptedRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["data-factory"],
)
async def trigger_data_source_scan(
    data_source_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> IngestionScanAcceptedRead:
    principal.require("ingestion:manage")
    source = session.scalar(
        select(DataSource).where(
            DataSource.id == data_source_id,
            DataSource.tenant_id == principal.tenant_id,
        )
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Data source not found")
    return await _start_data_source_scan(source, principal, session)


@app.get("/api/v1/admin/ingestion-runs", response_model=list[IngestionRunRead], tags=["data-factory"])
def list_ingestion_runs(
    principal: PrincipalDep,
    session: SessionDep,
    data_source_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[IngestionRunRead]:
    principal.require("ingestion:read")
    statement = select(IngestionRun).where(IngestionRun.tenant_id == principal.tenant_id)
    if data_source_id:
        statement = statement.where(IngestionRun.data_source_id == data_source_id)
    runs = list(session.scalars(statement.order_by(IngestionRun.created_at.desc()).limit(limit)))
    return IngestionRunReadService(session, principal.tenant_id).build_many(runs)


@app.post(
    "/api/v1/admin/ingestion-runs/{run_id}/cancel",
    response_model=IngestionRunCancelAcceptedRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["data-factory"],
)
async def cancel_ingestion_run(
    run_id: str,
    payload: IngestionRunCancelRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> IngestionRunCancelAcceptedRead:
    principal.require("ingestion:manage")
    run = session.scalar(
        select(IngestionRun).where(
            IngestionRun.id == run_id,
            IngestionRun.tenant_id == principal.tenant_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    operation = session.scalar(
        select(IngestionRunOperation).where(
            IngestionRunOperation.tenant_id == principal.tenant_id,
            IngestionRunOperation.operation_key == payload.operation_key,
        )
    )
    if operation is not None:
        same_command = (
            operation.ingestion_run_id == run.id
            and operation.operation_type == "cancel"
            and operation.expected_state == payload.expected_state
            and operation.reason == payload.reason
            and operation.requested_by_actor_type == principal.actor_type
            and operation.requested_by_actor_id == principal.actor_id
        )
        if not same_command:
            raise HTTPException(status_code=409, detail="Operation key was already used with different arguments")
        if operation.state == "accepted":
            return IngestionRunCancelAcceptedRead.model_validate(operation.response)
        if operation.state == "pending":
            raise HTTPException(status_code=409, detail="Ingestion cancel operation is already in progress")
        claimed = session.execute(
            update(IngestionRunOperation)
            .where(
                IngestionRunOperation.id == operation.id,
                IngestionRunOperation.state == "failed",
            )
            .values(state="pending", last_error=None)
        )
        if claimed.rowcount != 1:
            session.rollback()
            raise HTTPException(status_code=409, detail="Ingestion cancel operation is already in progress")

    run_read = IngestionRunReadService(session, principal.tenant_id).build(run)
    if run_read.effective_state.value != payload.expected_state:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ingestion_run_state_conflict",
                "expected_state": payload.expected_state,
                "current_state": run_read.effective_state.value,
            },
        )
    if not run.temporal_workflow_id or not run.temporal_run_id:
        raise HTTPException(status_code=409, detail="Ingestion run does not have a bound Temporal execution")
    if run.cancel_requested_at is not None and operation is None:
        raise HTTPException(status_code=409, detail="Ingestion cancellation was already requested")

    accepted = IngestionRunCancelAcceptedRead(
        run_id=run.id,
        workflow_id=run.workflow_id,
        temporal_workflow_id=run.temporal_workflow_id,
        temporal_run_id=run.temporal_run_id,
        status="cancel_requested",
    )
    if operation is None:
        operation = IngestionRunOperation(
            tenant_id=principal.tenant_id,
            ingestion_run_id=run.id,
            operation_key=payload.operation_key,
            operation_type="cancel",
            expected_state=payload.expected_state,
            reason=payload.reason,
            requested_by_actor_type=principal.actor_type,
            requested_by_actor_id=principal.actor_id,
            response=accepted.model_dump(mode="json"),
        )
        session.add(operation)
    else:
        operation.response = accepted.model_dump(mode="json")
    run.cancel_requested_at = datetime.now(UTC)
    run.cancel_reason = payload.reason
    run.cancel_requested_by_actor_type = principal.actor_type
    run.cancel_requested_by_actor_id = principal.actor_id
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Ingestion cancel operation is already in progress") from exc

    temporal_workflow_id = run.temporal_workflow_id
    temporal_run_id = run.temporal_run_id
    try:
        settings = get_settings()
        if not settings.temporal_enabled:
            raise HTTPException(status_code=503, detail="Durable workflow service is not enabled")
        client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
        handle = client.get_workflow_handle(temporal_workflow_id, run_id=temporal_run_id)
        await handle.cancel(reason=payload.reason)
    except HTTPException as exc:
        operation.state = "failed"
        operation.last_error = str(exc.detail)[:4000]
        run.cancel_requested_at = None
        run.cancel_reason = None
        run.cancel_requested_by_actor_type = None
        run.cancel_requested_by_actor_id = None
        session.commit()
        raise
    except Exception as exc:
        operation.state = "failed"
        operation.last_error = str(exc)[:4000]
        run.cancel_requested_at = None
        run.cancel_reason = None
        run.cancel_requested_by_actor_type = None
        run.cancel_requested_by_actor_id = None
        session.commit()
        raise HTTPException(status_code=503, detail="Durable workflow cancellation is unavailable") from exc

    now = datetime.now(UTC)
    run.state = RunState.CANCELED
    run.completed_at = now
    run.heartbeat_at = now
    run.error_summary = f"Canceled by operator: {payload.reason}"[:4000]
    run.result = {**run.result, "cancellation": {"status": "requested", "operation_id": operation.id}}
    operation.state = "accepted"
    operation.response = accepted.model_dump(mode="json")
    operation.last_error = None
    session.add(
        AuditEvent(
            tenant_id=principal.tenant_id,
            actor_type=principal.actor_type,
            actor_id=principal.actor_id,
            action="ingestion_run.cancel",
            resource_type="ingestion_run",
            resource_id=run.id,
            outcome="success",
            request_id=request.state.request_id,
            details={
                "reason": payload.reason,
                "operation_key": payload.operation_key,
                "expected_state": payload.expected_state,
                "data_source_id": run.data_source_id,
                "workflow_id": run.workflow_id,
                "temporal_workflow_id": temporal_workflow_id,
                "temporal_run_id": temporal_run_id,
            },
        )
    )
    session.commit()
    return accepted


@app.post(
    "/api/v1/admin/ingestion-runs/{run_id}/replay",
    response_model=IngestionScanAcceptedRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["data-factory"],
)
async def replay_ingestion_run(
    run_id: str,
    payload: IngestionRunReplayRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> IngestionScanAcceptedRead:
    principal.require("ingestion:manage")
    run = session.scalar(
        select(IngestionRun).where(
            IngestionRun.id == run_id,
            IngestionRun.tenant_id == principal.tenant_id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    if run.state.value != payload.expected_state:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ingestion_run_state_conflict",
                "expected_state": payload.expected_state,
                "current_state": run.state.value,
            },
        )
    if run.state not in {RunState.FAILED, RunState.PARTIAL, RunState.CANCELED}:
        raise HTTPException(status_code=409, detail=f"Ingestion run in {run.state.value} state cannot be replayed")
    source = session.scalar(
        select(DataSource).where(
            DataSource.id == run.data_source_id,
            DataSource.tenant_id == principal.tenant_id,
        )
    )
    if source is None:
        raise HTTPException(status_code=409, detail="The ingestion run data source is no longer available")
    operation = session.scalar(
        select(IngestionRunOperation).where(
            IngestionRunOperation.tenant_id == principal.tenant_id,
            IngestionRunOperation.operation_key == payload.operation_key,
        )
    )
    if operation is not None:
        same_command = (
            operation.ingestion_run_id == run.id
            and operation.operation_type == "replay"
            and operation.expected_state == payload.expected_state
            and operation.reason == payload.reason
            and operation.requested_by_actor_type == principal.actor_type
            and operation.requested_by_actor_id == principal.actor_id
        )
        if not same_command:
            raise HTTPException(status_code=409, detail="Operation key was already used with different arguments")
        if operation.state == "accepted":
            return IngestionScanAcceptedRead.model_validate(operation.response)
        if operation.state == "pending":
            raise HTTPException(status_code=409, detail="Ingestion replay operation is already in progress")
        claimed = session.execute(
            update(IngestionRunOperation)
            .where(
                IngestionRunOperation.id == operation.id,
                IngestionRunOperation.state == "failed",
            )
            .values(state="pending", last_error=None)
        )
        session.commit()
        if claimed.rowcount != 1:
            raise HTTPException(status_code=409, detail="Ingestion replay operation is already in progress")
        session.refresh(operation)
    else:
        workflow_id = f"source-ingest-{source.id}"
        accepted = IngestionScanAcceptedRead(
            workflow_id=workflow_id,
            ingestion_run_id=f"{workflow_id}-{uuid.uuid4()}",
            status="accepted",
            replayed_from_run_id=run.id,
        )
        operation = IngestionRunOperation(
            tenant_id=principal.tenant_id,
            ingestion_run_id=run.id,
            operation_key=payload.operation_key,
            operation_type="replay",
            expected_state=payload.expected_state,
            reason=payload.reason,
            requested_by_actor_type=principal.actor_type,
            requested_by_actor_id=principal.actor_id,
            response=accepted.model_dump(mode="json"),
        )
        session.add(operation)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail="Ingestion replay operation is already in progress") from exc

    accepted = IngestionScanAcceptedRead.model_validate(operation.response)
    try:
        accepted = await _start_data_source_scan(
            source,
            principal,
            session,
            replayed_from_run_id=run.id,
            run_correlation_id=accepted.ingestion_run_id,
        )
    except HTTPException as exc:
        operation.state = "failed"
        operation.last_error = str(exc.detail)[:4000]
        session.commit()
        raise
    operation.state = "accepted"
    operation.response = accepted.model_dump(mode="json")
    operation.last_error = None
    session.add(
        AuditEvent(
            tenant_id=principal.tenant_id,
            actor_type=principal.actor_type,
            actor_id=principal.actor_id,
            action="ingestion_run.replay",
            resource_type="ingestion_run",
            resource_id=run.id,
            outcome="success",
            request_id=request.state.request_id,
            details={
                "reason": payload.reason,
                "operation_key": payload.operation_key,
                "expected_state": payload.expected_state,
                "data_source_id": source.id,
                "workflow_id": accepted.workflow_id,
                "ingestion_run_id": accepted.ingestion_run_id,
            },
        )
    )
    session.commit()
    return accepted


@app.get(
    "/api/v1/admin/ingestion-runs/{run_id}/findings",
    response_model=list[IngestionFindingRead],
    tags=["data-factory"],
)
def list_ingestion_findings(
    run_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[IngestionFindingRead]:
    principal.require("ingestion:read")
    findings = session.scalars(
        select(IngestionFinding)
        .where(
            IngestionFinding.tenant_id == principal.tenant_id,
            IngestionFinding.ingestion_run_id == run_id,
        )
        .order_by(IngestionFinding.occurred_at)
    )
    return [IngestionFindingRead.model_validate(item) for item in findings]


@app.get("/api/v1/admin/source-assets", response_model=SourceAssetPageRead, tags=["data-factory"])
def list_source_assets(
    principal: PrincipalDep,
    session: SessionDep,
    data_source_id: str | None = None,
    state_filter: Annotated[SourceAssetState | None, Query(alias="state")] = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> SourceAssetPageRead:
    principal.require("ingestion:read")
    filters = [SourceAsset.tenant_id == principal.tenant_id]
    if data_source_id:
        filters.append(SourceAsset.data_source_id == data_source_id)
    if state_filter is not None:
        filters.append(SourceAsset.state == state_filter)
    total = int(session.scalar(select(func.count()).select_from(SourceAsset).where(*filters)) or 0)
    statement = select(SourceAsset).where(*filters)
    assets = session.scalars(
        statement.order_by(SourceAsset.last_seen_at.desc(), SourceAsset.id).offset(offset).limit(limit)
    )
    return SourceAssetPageRead(
        items=[SourceAssetRead.model_validate(asset) for asset in assets],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/api/v1/admin/source-assets/{asset_id}",
    response_model=SourceAssetDetailRead,
    tags=["data-factory"],
)
def get_source_asset_detail(
    asset_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> SourceAssetDetailRead:
    principal.require("ingestion:read")
    asset = session.scalar(
        select(SourceAsset).where(
            SourceAsset.id == asset_id,
            SourceAsset.tenant_id == principal.tenant_id,
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Source asset not found")
    versions = list(
        session.scalars(
            select(SourceVersion)
            .where(
                SourceVersion.source_asset_id == asset.id,
                SourceVersion.tenant_id == principal.tenant_id,
            )
            .order_by(SourceVersion.version_number.desc())
        )
    )
    settings = get_settings()
    return SourceAssetDetailRead(
        **SourceAssetRead.model_validate(asset).model_dump(),
        versions=[
            SourceVersionRead(
                **SourceVersionRead.model_validate(version).model_dump(exclude={"replayable_stages"}),
                replayable_stages=replayable_source_version_stages(
                    version,
                    ai_governance_enabled=settings.ai_governance_enabled,
                ),
            )
            for version in versions
        ],
    )


def _quarantine_case_read(
    version: SourceVersion,
    asset: SourceAsset,
    decisions: list[SourceVersionQuarantineDecision],
) -> SourceVersionQuarantineCaseRead:
    malware = version.metadata_json.get("malware_scan")
    threat_name = malware.get("threat_name") if isinstance(malware, dict) else None
    return SourceVersionQuarantineCaseRead(
        source_version_id=version.id,
        source_asset_id=asset.id,
        file_name=asset.file_name,
        logical_path=asset.logical_path,
        quarantine_status=version.quarantine_status,
        quarantine_version=version.quarantine_version,
        threat_name=str(threat_name)[:240] if threat_name else None,
        error_code=version.error_code,
        error_message=version.error_message,
        updated_at=version.quarantine_updated_at or version.malware_scanned_at or version.discovered_at,
        decisions=[SourceVersionQuarantineDecisionRead.model_validate(item) for item in decisions],
    )


@app.get(
    "/api/v1/admin/quarantine-cases",
    response_model=list[SourceVersionQuarantineCaseRead],
    tags=["data-factory"],
)
def list_source_version_quarantine_cases(
    principal: PrincipalDep,
    session: SessionDep,
    status_filter: Annotated[QuarantineStatus | None, Query(alias="status")] = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SourceVersionQuarantineCaseRead]:
    principal.require("ingestion:read")
    filters = [
        SourceVersion.tenant_id == principal.tenant_id,
        SourceVersion.quarantine_status != QuarantineStatus.NOT_APPLICABLE,
    ]
    if status_filter is not None:
        filters.append(SourceVersion.quarantine_status == status_filter)
    rows = list(
        session.execute(
            select(SourceVersion, SourceAsset)
            .join(SourceAsset, SourceAsset.id == SourceVersion.source_asset_id)
            .where(*filters)
            .order_by(SourceVersion.quarantine_updated_at.desc(), SourceVersion.id)
            .limit(limit)
        )
    )
    # Queue reads stay bounded; immutable history is loaded only from the case detail endpoint.
    return [_quarantine_case_read(version, asset, []) for version, asset in rows]


@app.get(
    "/api/v1/admin/quarantine-cases/{version_id}",
    response_model=SourceVersionQuarantineCaseRead,
    tags=["data-factory"],
)
def get_source_version_quarantine_case(
    version_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> SourceVersionQuarantineCaseRead:
    principal.require("ingestion:read")
    row = session.execute(
        select(SourceVersion, SourceAsset)
        .join(SourceAsset, SourceAsset.id == SourceVersion.source_asset_id)
        .where(
            SourceVersion.id == version_id,
            SourceVersion.tenant_id == principal.tenant_id,
            SourceVersion.quarantine_status != QuarantineStatus.NOT_APPLICABLE,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Quarantine case not found")
    version, asset = row
    decisions = list(
        session.scalars(
            select(SourceVersionQuarantineDecision)
            .where(
                SourceVersionQuarantineDecision.tenant_id == principal.tenant_id,
                SourceVersionQuarantineDecision.source_version_id == version.id,
            )
            .order_by(SourceVersionQuarantineDecision.resulting_version)
        )
    )
    return _quarantine_case_read(version, asset, decisions)


def _quarantine_decision_response(
    decision: SourceVersionQuarantineDecision,
) -> SourceVersionQuarantineDecisionAcceptedRead:
    return SourceVersionQuarantineDecisionAcceptedRead(
        decision_id=decision.id,
        source_version_id=decision.source_version_id,
        action=cast(Literal["hold", "reject", "rescan"], decision.action),
        quarantine_status=decision.resulting_status,
        quarantine_version=decision.resulting_version,
        workflow_id=decision.workflow_id,
        status="accepted",
    )


@app.post(
    "/api/v1/admin/quarantine-cases/{version_id}/decisions",
    response_model=SourceVersionQuarantineDecisionAcceptedRead,
    tags=["data-factory"],
)
async def decide_source_version_quarantine_case(
    version_id: str,
    payload: SourceVersionQuarantineDecisionRequest,
    request: Request,
    response: Response,
    principal: PrincipalDep,
    session: SessionDep,
) -> SourceVersionQuarantineDecisionAcceptedRead:
    principal.require("ingestion:manage")
    version = session.scalar(
        select(SourceVersion)
        .where(
            SourceVersion.id == version_id,
            SourceVersion.tenant_id == principal.tenant_id,
        )
        .with_for_update()
    )
    if version is None or version.quarantine_status == QuarantineStatus.NOT_APPLICABLE:
        raise HTTPException(status_code=404, detail="Quarantine case not found")

    operation_type = f"quarantine_{payload.action}"
    operation = session.scalar(
        select(SourceVersionOperation).where(
            SourceVersionOperation.tenant_id == principal.tenant_id,
            SourceVersionOperation.operation_key == payload.operation_key,
        )
    )
    decision: SourceVersionQuarantineDecision | None = None
    if operation is not None:
        same_command = (
            operation.source_version_id == version.id
            and operation.operation_type == operation_type
            and operation.expected_quarantine_version == payload.expected_version
            and operation.reason == payload.reason
            and operation.requested_by_actor_type == principal.actor_type
            and operation.requested_by_actor_id == principal.actor_id
        )
        if not same_command:
            raise HTTPException(status_code=409, detail="Operation key was already used with different arguments")
        decision = session.scalar(
            select(SourceVersionQuarantineDecision).where(
                SourceVersionQuarantineDecision.tenant_id == principal.tenant_id,
                SourceVersionQuarantineDecision.operation_key == payload.operation_key,
            )
        )
        if decision is None:
            raise HTTPException(status_code=409, detail="Quarantine operation is missing its decision record")
        accepted = SourceVersionQuarantineDecisionAcceptedRead.model_validate(operation.response)
        if operation.state == "accepted":
            response.status_code = status.HTTP_202_ACCEPTED if payload.action == "rescan" else status.HTTP_200_OK
            return accepted
        if operation.state == "failed":
            raise HTTPException(
                status_code=409,
                detail="Previous quarantine operation failed; refresh and submit a new operation key",
            )
        if payload.action != "rescan":
            raise HTTPException(status_code=409, detail="Quarantine operation is already in progress")
        if version.quarantine_status != QuarantineStatus.RESCAN_REQUESTED:
            operation.state = "accepted"
            operation.response = accepted.model_dump(mode="json")
            session.commit()
            response.status_code = status.HTTP_202_ACCEPTED
            return accepted
    else:
        workflow_id = f"source-version-reprocess-{version.id}" if payload.action == "rescan" else None
        try:
            outcome = apply_operator_decision(
                session,
                version,
                operation_key=payload.operation_key,
                expected_version=payload.expected_version,
                action=payload.action,
                reason=payload.reason,
                actor_type=principal.actor_type,
                actor_id=principal.actor_id,
                workflow_id=workflow_id,
            )
        except QuarantineTransitionError as exc:
            raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
        decision = outcome.decision
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail="Quarantine operation already exists") from exc
        accepted = _quarantine_decision_response(decision)
        operation = SourceVersionOperation(
            tenant_id=principal.tenant_id,
            source_version_id=version.id,
            operation_key=payload.operation_key,
            operation_type=operation_type,
            from_stage="malware_scan" if payload.action == "rescan" else "quarantine",
            expected_state=version.state.value,
            expected_error_code=version.error_code,
            expected_quarantine_version=payload.expected_version,
            reason=payload.reason,
            requested_by_actor_type=principal.actor_type,
            requested_by_actor_id=principal.actor_id,
            state="pending" if payload.action == "rescan" else "accepted",
            response=accepted.model_dump(mode="json"),
        )
        session.add(operation)
        if payload.action != "rescan":
            session.add(
                AuditEvent(
                    tenant_id=principal.tenant_id,
                    actor_type=principal.actor_type,
                    actor_id=principal.actor_id,
                    action=f"source_version.quarantine.{payload.action}",
                    resource_type="source_version",
                    resource_id=version.id,
                    outcome="success",
                    request_id=request.state.request_id,
                    details={
                        "operation_key": payload.operation_key,
                        "reason": payload.reason,
                        "expected_version": payload.expected_version,
                        "resulting_version": decision.resulting_version,
                        "previous_status": decision.previous_status.value,
                        "resulting_status": decision.resulting_status.value,
                    },
                )
            )
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail="Quarantine operation already exists") from exc
        if payload.action != "rescan":
            return accepted

    assert decision is not None
    settings = get_settings()
    if not settings.temporal_enabled:
        operation.state = "failed"
        operation.last_error = "Durable workflow service is not enabled"
        record_rescan_failure(
            session,
            version,
            reason=operation.last_error,
            actor_id="api",
        )
        session.commit()
        raise HTTPException(status_code=503, detail=operation.last_error)
    try:
        client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
        await client.start_workflow(
            SourceVersionReprocessWorkflow.run,
            ProcessInput(principal.tenant_id, version.id, from_stage="malware_scan"),
            id=decision.workflow_id or f"source-version-reprocess-{version.id}",
            task_queue=settings.temporal_task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        )
    except WorkflowAlreadyStartedError:
        pass
    except Exception as exc:
        operation.state = "failed"
        operation.last_error = "Durable quarantine rescan workflow is unavailable"
        record_rescan_failure(
            session,
            version,
            reason=operation.last_error,
            actor_id="api",
        )
        session.add(
            AuditEvent(
                tenant_id=principal.tenant_id,
                actor_type=principal.actor_type,
                actor_id=principal.actor_id,
                action="source_version.quarantine.rescan",
                resource_type="source_version",
                resource_id=version.id,
                outcome="failure",
                request_id=request.state.request_id,
                details={"operation_key": payload.operation_key, "reason": payload.reason},
            )
        )
        session.commit()
        raise HTTPException(status_code=503, detail=operation.last_error) from exc

    operation.state = "accepted"
    operation.last_error = None
    session.add(
        AuditEvent(
            tenant_id=principal.tenant_id,
            actor_type=principal.actor_type,
            actor_id=principal.actor_id,
            action="source_version.quarantine.rescan",
            resource_type="source_version",
            resource_id=version.id,
            outcome="success",
            request_id=request.state.request_id,
            details={
                "operation_key": payload.operation_key,
                "reason": payload.reason,
                "expected_version": payload.expected_version,
                "workflow_id": decision.workflow_id,
                "from_stage": "malware_scan",
            },
        )
    )
    session.commit()
    response.status_code = status.HTTP_202_ACCEPTED
    return SourceVersionQuarantineDecisionAcceptedRead.model_validate(operation.response)


@app.get(
    "/api/v1/admin/source-versions/{version_id}/preview",
    response_model=SourceVersionPreviewRead,
    tags=["data-factory"],
)
def get_source_version_preview(
    version_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    max_chars: int = Query(default=20_000, ge=100, le=100_000),
) -> SourceVersionPreviewRead:
    principal.require("ingestion:read")
    version = session.scalar(
        select(SourceVersion).where(
            SourceVersion.id == version_id,
            SourceVersion.tenant_id == principal.tenant_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Source version not found")
    if version.error_code == "malware_detected":
        raise HTTPException(status_code=409, detail="Quarantined malware content cannot be previewed")
    if not version.extracted_text_object_uri or not version.extracted_text_sha256:
        raise HTTPException(status_code=409, detail="Parsed text is not available for this source version")
    try:
        payload = object_store_module.build_object_store(get_settings()).read_bytes(
            version.extracted_text_object_uri,
            max_bytes=8_000_000,
        )
        text_content = payload.decode("utf-8")
    except (object_store_module.ObjectStoreError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Parsed text preview is unavailable or exceeds the safe limit",
        ) from exc
    preview = text_content[:max_chars]
    return SourceVersionPreviewRead(
        source_version_id=version.id,
        text=preview,
        truncated=len(text_content) > len(preview),
        returned_chars=len(preview),
        extracted_text_sha256=version.extracted_text_sha256,
    )


@app.post(
    "/api/v1/admin/source-versions/{version_id}/replay",
    response_model=SourceVersionReplayAcceptedRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["data-factory"],
)
async def replay_source_version(
    version_id: str,
    payload: SourceVersionReplayRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> SourceVersionReplayAcceptedRead:
    principal.require("ingestion:manage")
    version = session.scalar(
        select(SourceVersion).where(
            SourceVersion.id == version_id,
            SourceVersion.tenant_id == principal.tenant_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Source version not found")
    operation = session.scalar(
        select(SourceVersionOperation).where(
            SourceVersionOperation.tenant_id == principal.tenant_id,
            SourceVersionOperation.operation_key == payload.operation_key,
        )
    )
    if operation is not None:
        same_command = (
            operation.source_version_id == version.id
            and operation.operation_type == "replay"
            and operation.from_stage == payload.from_stage
            and operation.expected_state == payload.expected_state.value
            and operation.expected_error_code == payload.expected_error_code
            and operation.reason == payload.reason
            and operation.requested_by_actor_type == principal.actor_type
            and operation.requested_by_actor_id == principal.actor_id
        )
        if not same_command:
            raise HTTPException(status_code=409, detail="Operation key was already used with different arguments")
        if operation.state == "accepted":
            return SourceVersionReplayAcceptedRead.model_validate(operation.response)
        if operation.state == "pending":
            raise HTTPException(status_code=409, detail="Source version replay operation is already in progress")

    if version.error_code == "malware_detected" and version.quarantine_status not in {
        QuarantineStatus.NOT_APPLICABLE,
        QuarantineStatus.CLEARED,
    }:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "quarantine_decision_required",
                "quarantine_status": version.quarantine_status.value,
                "quarantine_version": version.quarantine_version,
            },
        )

    if version.state != payload.expected_state or version.error_code != payload.expected_error_code:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "source_version_state_conflict",
                "expected_state": payload.expected_state.value,
                "current_state": version.state.value,
                "expected_error_code": payload.expected_error_code,
                "current_error_code": version.error_code,
            },
        )
    settings = get_settings()
    replayable_stages = replayable_source_version_stages(
        version,
        ai_governance_enabled=settings.ai_governance_enabled,
    )
    if payload.from_stage not in replayable_stages:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "source_version_stage_not_replayable",
                "requested_stage": payload.from_stage,
                "replayable_stages": replayable_stages,
            },
        )

    if operation is not None:
        claimed = session.execute(
            update(SourceVersionOperation)
            .where(
                SourceVersionOperation.id == operation.id,
                SourceVersionOperation.state == "failed",
            )
            .values(state="pending", last_error=None)
        )
        session.commit()
        if claimed.rowcount != 1:
            raise HTTPException(status_code=409, detail="Source version replay operation is already in progress")
        session.refresh(operation)
    else:
        accepted = SourceVersionReplayAcceptedRead(
            workflow_id=f"source-version-reprocess-{version.id}",
            source_version_id=version.id,
            from_stage=payload.from_stage,
            status="accepted",
        )
        operation = SourceVersionOperation(
            tenant_id=principal.tenant_id,
            source_version_id=version.id,
            operation_key=payload.operation_key,
            operation_type="replay",
            from_stage=payload.from_stage,
            expected_state=payload.expected_state.value,
            expected_error_code=payload.expected_error_code,
            reason=payload.reason,
            requested_by_actor_type=principal.actor_type,
            requested_by_actor_id=principal.actor_id,
            response=accepted.model_dump(mode="json"),
        )
        session.add(operation)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Source version replay operation is already in progress",
            ) from exc

    accepted = SourceVersionReplayAcceptedRead.model_validate(operation.response)
    if not settings.temporal_enabled:
        operation.state = "failed"
        operation.last_error = "Durable workflow service is not enabled"
        session.commit()
        raise HTTPException(status_code=503, detail=operation.last_error)
    try:
        client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
        await client.start_workflow(
            SourceVersionReprocessWorkflow.run,
            ProcessInput(principal.tenant_id, version.id, from_stage=payload.from_stage),
            id=accepted.workflow_id,
            task_queue=settings.temporal_task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        )
    except WorkflowAlreadyStartedError as exc:
        operation.state = "failed"
        operation.last_error = "A replay is already running for this source version"
        session.commit()
        raise HTTPException(status_code=409, detail=operation.last_error) from exc
    except Exception as exc:
        operation.state = "failed"
        operation.last_error = "Durable workflow service is unavailable"
        session.commit()
        raise HTTPException(status_code=503, detail=operation.last_error) from exc
    operation.state = "accepted"
    operation.last_error = None
    session.add(
        AuditEvent(
            tenant_id=principal.tenant_id,
            actor_type=principal.actor_type,
            actor_id=principal.actor_id,
            action="source_version.replay",
            resource_type="source_version",
            resource_id=version.id,
            outcome="success",
            request_id=request.state.request_id,
            details={
                "reason": payload.reason,
                "operation_key": payload.operation_key,
                "from_stage": payload.from_stage,
                "expected_state": payload.expected_state.value,
                "expected_error_code": payload.expected_error_code,
                "workflow_id": accepted.workflow_id,
            },
        )
    )
    session.commit()
    return accepted


@app.get(
    "/api/v1/governance/runs",
    response_model=GovernanceRunPageRead,
    tags=["governance"],
)
def list_governance_runs(
    principal: PrincipalDep,
    session: SessionDep,
    run_status: Annotated[RunState | None, Query(alias="status")] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> GovernanceRunPageRead:
    principal.require("governance:read")
    filters = [ExtractionRun.tenant_id == principal.tenant_id]
    if run_status is not None:
        filters.append(ExtractionRun.status == run_status)
    total = int(session.scalar(select(func.count()).select_from(ExtractionRun).where(*filters)) or 0)
    rows = session.execute(
        select(ExtractionRun, SourceVersion, SourceAsset)
        .join(
            SourceVersion,
            (SourceVersion.id == ExtractionRun.source_version_id)
            & (SourceVersion.tenant_id == ExtractionRun.tenant_id),
        )
        .join(
            SourceAsset,
            (SourceAsset.id == SourceVersion.source_asset_id) & (SourceAsset.tenant_id == ExtractionRun.tenant_id),
        )
        .where(*filters)
        .order_by(ExtractionRun.created_at.desc(), ExtractionRun.id.desc())
        .limit(limit)
        .offset(offset)
    )
    current_policy = governance_policy_sha256(get_settings())
    items = [
        GovernanceRunRead(
            id=run.id,
            source_version_id=version.id,
            source_asset_id=asset.id,
            source_logical_path=asset.logical_path,
            source_file_name=asset.file_name,
            source_content_sha256=version.content_sha256,
            schema_name=run.schema_name,
            schema_version=run.schema_version,
            model_provider=run.model_provider,
            model_name=run.model_name,
            prompt_sha256=run.prompt_sha256,
            policy_sha256=run.policy_sha256,
            input_sha256=run.input_sha256,
            policy_current=run.policy_sha256 == current_policy,
            status=run.status,
            validation_errors=run.validation_errors[:20],
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            estimated_cost=run.estimated_cost,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
        )
        for run, version, asset in rows
    ]
    return GovernanceRunPageRead(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        current_policy_sha256=current_policy,
    )


@app.get("/api/v1/governance/review-queue", response_model=list[StagedFactRead], tags=["governance"])
def list_review_queue(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[StagedFactRead]:
    principal.require("governance:read")
    facts = session.scalars(
        select(StagedFact)
        .join(ReviewTask, ReviewTask.staged_fact_id == StagedFact.id)
        .where(
            StagedFact.tenant_id == principal.tenant_id,
            ReviewTask.tenant_id == principal.tenant_id,
            ReviewTask.status == GovernanceStatus.REVIEW_PENDING,
        )
        .order_by(ReviewTask.priority.desc(), ReviewTask.created_at)
        .limit(limit)
    )
    return [StagedFactRead.model_validate(fact) for fact in facts]


@app.get("/api/v1/governance/identity/namespaces", tags=["governance"])
def list_identifier_namespaces(principal: PrincipalDep) -> list[dict[str, Any]]:
    principal.require("governance:read")
    return supported_namespaces()


@app.get(
    "/api/v1/governance/ontology/terms",
    response_model=list[OntologyTermRead],
    tags=["governance"],
)
def list_ontology_terms(
    principal: PrincipalDep,
    session: SessionDep,
    ontology_name: str | None = Query(default=None, max_length=100),
    entity_type: EntityType | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[OntologyTermRead]:
    principal.require("governance:read")
    terms = EntityIdentityService(session, principal.tenant_id).list_ontology_terms(
        ontology_name=ontology_name,
        entity_type=entity_type,
        limit=limit,
    )
    return [OntologyTermRead.model_validate(item) for item in terms]


@app.post(
    "/api/v1/governance/ontology/terms",
    response_model=OntologyTermRead,
    status_code=status.HTTP_201_CREATED,
    tags=["governance"],
)
def register_ontology_term(
    payload: OntologyTermUpsert,
    principal: PrincipalDep,
    session: SessionDep,
) -> OntologyTermRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    try:
        term = EntityIdentityService(session, principal.tenant_id).register_ontology_term(payload.model_dump())
    except IdentityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return OntologyTermRead.model_validate(term)


@app.post(
    "/api/v1/governance/entities/{entity_id}/ontology-mappings",
    status_code=status.HTTP_201_CREATED,
    tags=["governance"],
)
def create_entity_ontology_mapping(
    entity_id: str,
    payload: EntityOntologyMappingCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> dict[str, Any]:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    try:
        mapping = EntityIdentityService(session, principal.tenant_id).map_ontology_term(
            entity_id=entity_id,
            ontology_term_id=payload.ontology_term_id,
            mapping_type=payload.mapping_type,
            confidence=payload.confidence,
            source_document_id=payload.source_document_id,
            evidence=payload.evidence,
            review_status=ReviewStatus.VERIFIED,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IdentityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": mapping.id,
        "entity_id": mapping.entity_id,
        "ontology_term_id": mapping.ontology_term_id,
        "mapping_type": mapping.mapping_type,
        "confidence": mapping.confidence,
        "review_status": mapping.review_status,
    }


@app.get(
    "/api/v1/governance/entity-resolution-cases",
    response_model=list[EntityResolutionCaseRead],
    tags=["governance"],
)
def list_entity_resolution_cases(
    principal: PrincipalDep,
    session: SessionDep,
    case_status: Annotated[ResolutionStatus, Query(alias="status")] = ResolutionStatus.PENDING,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[EntityResolutionCaseRead]:
    principal.require("governance:read")
    cases = EntityIdentityService(session, principal.tenant_id).list_cases(status=case_status, limit=limit)
    return [EntityResolutionCaseRead.model_validate(resolution_case_view(session, item)) for item in cases]


@app.get(
    "/api/v1/governance/entity-resolution-cases/{case_id}/impact",
    response_model=EntityResolutionImpactRead,
    tags=["governance"],
)
def get_entity_resolution_case_impact(
    case_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> EntityResolutionImpactRead:
    principal.require("governance:read")
    try:
        impact = EntityIdentityService(session, principal.tenant_id).resolution_impact(case_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IdentityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return EntityResolutionImpactRead.model_validate(impact)


@app.post(
    "/api/v1/governance/entity-resolution-cases/{case_id}/decision",
    response_model=EntityResolutionCaseRead,
    tags=["governance"],
)
def decide_entity_resolution_case(
    case_id: str,
    payload: EntityResolutionDecisionRequest,
    principal: PrincipalDep,
    session: SessionDep,
) -> EntityResolutionCaseRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    try:
        item = EntityIdentityService(session, principal.tenant_id).decide(
            case_id,
            action=payload.action,
            expected_status=payload.expected_status,
            canonical_entity_id=payload.canonical_entity_id,
            user_id=principal.user_id,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IdentityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return EntityResolutionCaseRead.model_validate(resolution_case_view(session, item))


def _publication_service(session: Session, tenant_id: str) -> GovernancePublicationService:
    settings = get_settings()
    return GovernancePublicationService(
        session,
        settings,
        object_store_module.build_object_store(settings),
        tenant_id,
    )


def _projection_maintenance_service(session: Session, tenant_id: str) -> ProjectionMaintenanceService:
    return ProjectionMaintenanceService(session, get_settings(), tenant_id)


def _require_projection_admin(principal: Principal, session: Session) -> str:
    principal.require("governance:review")
    principal.require_exact(PLATFORM_PROJECTION_SCOPE)
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human administrator account is required")
    user = session.scalar(
        select(User).where(
            User.id == principal.user_id,
            User.tenant_id == principal.tenant_id,
            User.role == UserRole.ADMIN,
            User.active.is_(True),
        )
    )
    if user is None:
        raise HTTPException(status_code=403, detail="An active tenant administrator is required")
    return user.id


@app.get(
    "/api/v1/governance/projection-maintenance-access",
    response_model=ProjectionMaintenanceAccessRead,
    tags=["governance"],
)
def get_projection_maintenance_access(
    principal: PrincipalDep,
    session: SessionDep,
) -> ProjectionMaintenanceAccessRead:
    if principal.user_id is None or PLATFORM_PROJECTION_SCOPE not in principal.scopes:
        return ProjectionMaintenanceAccessRead(allowed=False)
    user = session.scalar(
        select(User).where(
            User.id == principal.user_id,
            User.tenant_id == principal.tenant_id,
            User.role == UserRole.ADMIN,
            User.active.is_(True),
        )
    )
    return ProjectionMaintenanceAccessRead(allowed=user is not None)


@app.get(
    "/api/v1/governance/projection-maintenance-jobs",
    response_model=list[ProjectionMaintenanceJobRead],
    tags=["governance"],
)
def list_projection_maintenance_jobs(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ProjectionMaintenanceJobRead]:
    _require_projection_admin(principal, session)
    return [
        ProjectionMaintenanceJobRead.model_validate(job)
        for job in _projection_maintenance_service(session, principal.tenant_id).list(limit)
    ]


@app.get(
    "/api/v1/governance/projection-maintenance-jobs/{job_id}",
    response_model=ProjectionMaintenanceJobRead,
    tags=["governance"],
)
def get_projection_maintenance_job(
    job_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> ProjectionMaintenanceJobRead:
    _require_projection_admin(principal, session)
    try:
        job = _projection_maintenance_service(session, principal.tenant_id).get(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProjectionMaintenanceJobRead.model_validate(job)


@app.post(
    "/api/v1/governance/projection-maintenance-jobs",
    response_model=ProjectionMaintenanceJobRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["governance"],
)
def request_projection_maintenance_job(
    payload: ProjectionMaintenanceRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> ProjectionMaintenanceJobRead:
    user_id = _require_projection_admin(principal, session)
    try:
        job = _projection_maintenance_service(session, principal.tenant_id).request(
            payload.operation,
            user_id,
            request.state.request_id,
        )
    except ProjectionMaintenanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ProjectionMaintenanceJobRead.model_validate(job)


def _quality_service(session: Session, tenant_id: str) -> DataQualityService:
    return DataQualityService(session, get_settings(), tenant_id)


def _quality_issue_reads(session: Session, items: list[DataQualityIssue]) -> list[DataQualityIssueRead]:
    owner_ids = {item.owner_user_id for item in items if item.owner_user_id}
    owners = {user.id: user.display_name for user in session.scalars(select(User).where(User.id.in_(owner_ids)))}
    result: list[DataQualityIssueRead] = []
    for item in items:
        payload = DataQualityIssueRead.model_validate(item).model_dump()
        payload["owner_display_name"] = owners.get(item.owner_user_id or "")
        result.append(DataQualityIssueRead.model_validate(payload))
    return result


@app.get(
    "/api/v1/governance/quality/snapshots",
    response_model=list[DataQualitySnapshotRead],
    tags=["governance"],
)
def list_data_quality_snapshots(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=30, ge=1, le=365),
) -> list[DataQualitySnapshotRead]:
    principal.require("governance:read")
    return [
        DataQualitySnapshotRead.model_validate(item)
        for item in _quality_service(session, principal.tenant_id).snapshots(limit)
    ]


@app.get(
    "/api/v1/governance/quality/coverage",
    response_model=list[DataQualityCoverageRead],
    tags=["governance"],
)
def list_data_quality_coverage(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=100),
) -> list[DataQualityCoverageRead]:
    principal.require("governance:read")
    return [
        DataQualityCoverageRead.model_validate(item)
        for item in _quality_service(session, principal.tenant_id).coverage(limit)
    ]


@app.post(
    "/api/v1/governance/quality/evaluations",
    response_model=DataQualitySnapshotRead,
    status_code=status.HTTP_201_CREATED,
    tags=["governance"],
)
def evaluate_data_quality(
    principal: PrincipalDep,
    session: SessionDep,
) -> DataQualitySnapshotRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        locked = session.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"data-quality:{principal.tenant_id}"},
        )
        if not locked:
            raise HTTPException(status_code=409, detail="A data quality evaluation is already running")
    snapshot = _quality_service(session, principal.tenant_id).evaluate(
        trigger="manual",
        actor_type="user",
        actor_id=principal.user_id,
    )
    return DataQualitySnapshotRead.model_validate(snapshot)


@app.get(
    "/api/v1/governance/quality/owners",
    response_model=list[DataQualityOwnerRead],
    tags=["governance"],
)
def list_data_quality_owners(
    principal: PrincipalDep,
    session: SessionDep,
) -> list[DataQualityOwnerRead]:
    principal.require("governance:read")
    users = session.scalars(
        select(User)
        .where(
            User.tenant_id == principal.tenant_id,
            User.active.is_(True),
            User.role.in_([UserRole.ADMIN, UserRole.ANALYST]),
        )
        .order_by(User.display_name, User.id)
    )
    return [DataQualityOwnerRead(id=user.id, display_name=user.display_name, role=user.role) for user in users]


@app.get(
    "/api/v1/governance/quality/issues",
    response_model=list[DataQualityIssueRead],
    tags=["governance"],
)
def list_data_quality_issues(
    principal: PrincipalDep,
    session: SessionDep,
    issue_status: Literal["open", "acknowledged", "ready_to_resolve", "resolved", "waived"] | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[DataQualityIssueRead]:
    principal.require("governance:read")
    return _quality_issue_reads(
        session,
        _quality_service(session, principal.tenant_id).issues(issue_status, limit),
    )


@app.get(
    "/api/v1/governance/quality/issues/{issue_id}/events",
    response_model=list[DataQualityIssueEventRead],
    tags=["governance"],
)
def list_data_quality_issue_events(
    issue_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[DataQualityIssueEventRead]:
    principal.require("governance:read")
    try:
        events = _quality_service(session, principal.tenant_id).events(issue_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [DataQualityIssueEventRead.model_validate(item) for item in events]


@app.post(
    "/api/v1/governance/quality/issues/{issue_id}/actions",
    response_model=DataQualityIssueRead,
    tags=["governance"],
)
def act_on_data_quality_issue(
    issue_id: str,
    payload: DataQualityIssueActionRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataQualityIssueRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    actor = session.scalar(
        select(User).where(
            User.tenant_id == principal.tenant_id,
            User.id == principal.user_id,
            User.active.is_(True),
        )
    )
    if actor is None:
        raise HTTPException(status_code=403, detail="An active reviewer account is required")
    current_issue = session.scalar(
        select(DataQualityIssue).where(
            DataQualityIssue.tenant_id == principal.tenant_id,
            DataQualityIssue.id == issue_id,
        )
    )
    if current_issue is None:
        raise HTTPException(status_code=404, detail="Data quality issue not found")
    if payload.action == "waive" and actor.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only tenant administrators may waive quality issues")
    if payload.action == "resolve" and actor.role != UserRole.ADMIN and current_issue.owner_user_id != actor.id:
        raise HTTPException(
            status_code=403,
            detail="Only the assigned owner or an administrator may resolve this issue",
        )
    try:
        issue = _quality_service(session, principal.tenant_id).act(
            issue_id,
            action=payload.action,
            expected_version=payload.expected_version,
            actor_id=principal.user_id,
            request_id=request.state.request_id,
            owner_user_id=payload.owner_user_id,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DataQualityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _quality_issue_reads(session, [issue])[0]


def _publication_batch_read(
    service: GovernancePublicationService,
    batch_id: str,
) -> PublicationBatchRead:
    batch = service.get(batch_id)
    return PublicationBatchRead(
        **PublicationBatchRead.model_validate(batch).model_dump(exclude={"items"}),
        items=[PublicationBatchItemRead.model_validate(item) for item in service.items(batch.id)],
    )


@app.get(
    "/api/v1/governance/publication-batches",
    response_model=list[PublicationBatchRead],
    tags=["governance"],
)
def list_publication_batches(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[PublicationBatchRead]:
    principal.require("governance:review")
    service = _publication_service(session, principal.tenant_id)
    return [
        PublicationBatchRead(
            **PublicationBatchRead.model_validate(batch).model_dump(exclude={"items"}),
            items=[],
        )
        for batch in service.list_batches(limit)
    ]


@app.get(
    "/api/v1/governance/publication-batches/{batch_id}",
    response_model=PublicationBatchRead,
    tags=["governance"],
)
def get_publication_batch(
    batch_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> PublicationBatchRead:
    principal.require("governance:review")
    try:
        return _publication_batch_read(_publication_service(session, principal.tenant_id), batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/api/v1/governance/publication-batches/preview",
    response_model=PublicationBatchRead,
    status_code=status.HTTP_201_CREATED,
    tags=["governance"],
)
def preview_publication_batch(
    payload: PublicationBatchPreviewRequest,
    principal: PrincipalDep,
    session: SessionDep,
) -> PublicationBatchRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    service = _publication_service(session, principal.tenant_id)
    try:
        batch = service.preview(
            operation=payload.operation,
            staged_fact_ids=payload.staged_fact_ids,
            idempotency_key=payload.idempotency_key,
            user_id=principal.user_id,
            reason=payload.reason,
        )
        return _publication_batch_read(service, batch.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PublicationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/api/v1/governance/publication-batches/{batch_id}/commit",
    response_model=PublicationBatchRead,
    tags=["governance"],
)
def commit_publication_batch(
    batch_id: str,
    payload: PublicationBatchCommitRequest,
    principal: PrincipalDep,
    session: SessionDep,
) -> PublicationBatchRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    service = _publication_service(session, principal.tenant_id)
    try:
        batch = service.commit(batch_id, payload.preview_sha256, principal.user_id)
        return _publication_batch_read(service, batch.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PublicationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _export_published_knowledge_page(compiler: KnowledgeCompiler, page_id: str) -> None:
    try:
        compiler.export_page(page_id, get_settings().markdown_export_root)
    except (OSError, ValueError) as exc:
        request_logger.error(
            "knowledge_markdown_export_failed_after_publish",
            page_id=page_id,
            error_type=type(exc).__name__,
        )


@app.post(
    "/api/v1/governance/staged-facts/{staged_fact_id}/decision",
    response_model=StagedFactRead,
    tags=["governance"],
)
def decide_staged_fact(
    staged_fact_id: str,
    payload: ReviewDecision,
    principal: PrincipalDep,
    session: SessionDep,
) -> StagedFactRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    if payload.decision == "reject" and not payload.notes:
        raise HTTPException(status_code=422, detail="A rejection reason is required")
    service = GovernanceService(
        session,
        get_settings(),
        object_store_module.build_object_store(get_settings()),
        principal.tenant_id,
    )
    try:
        if payload.decision == "approve":
            staged = service.approve_fact(staged_fact_id, principal.user_id, payload.notes)
            if staged.published_resource_type == "evidence_claim" and staged.published_resource_id:
                claim = session.get(EvidenceClaim, staged.published_resource_id)
                if claim is not None:
                    compiler = KnowledgeCompiler(session, principal.tenant_id)
                    result = compiler.compile_entity(claim.subject_id, run_id=f"review:{staged.id}")
                    _export_published_knowledge_page(compiler, result.page_id)
        else:
            staged = service.reject_fact(staged_fact_id, principal.user_id, payload.notes or "")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return StagedFactRead.model_validate(staged)


def _public_knowledge_page_or_404(session: Session, principal: Principal, page_id: str) -> KnowledgePage:
    page = session.scalar(
        select(KnowledgePage).where(
            KnowledgePage.id == page_id,
            KnowledgePage.tenant_id == principal.tenant_id,
            KnowledgePage.status == KnowledgePageStatus.PUBLISHED,
            KnowledgePage.current_version_id.is_not(None),
        )
    )
    if page is None:
        raise HTTPException(status_code=404, detail="Knowledge page not found")
    return page


@app.get("/api/v1/knowledge/pages", response_model=list[PublicKnowledgePageSummary], tags=["knowledge"])
def list_knowledge_pages(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    page_type: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[PublicKnowledgePageSummary]:
    principal.require("knowledge:read")
    statement = select(KnowledgePage).where(
        KnowledgePage.tenant_id == principal.tenant_id,
        KnowledgePage.status == KnowledgePageStatus.PUBLISHED,
        KnowledgePage.current_version_id.is_not(None),
    )
    if q:
        statement = statement.where(KnowledgePage.title.ilike(f"%{q}%"))
    if page_type:
        statement = statement.where(KnowledgePage.page_type == page_type)
    pages = session.scalars(statement.order_by(KnowledgePage.title).limit(limit))
    return [PublicKnowledgePageSummary.model_validate(page) for page in pages]


@app.get("/api/v1/knowledge/pages/{page_id}", response_model=PublicKnowledgePageDetail, tags=["knowledge"])
def get_knowledge_page(page_id: str, principal: PrincipalDep, session: SessionDep) -> PublicKnowledgePageDetail:
    principal.require("knowledge:read")
    page = _public_knowledge_page_or_404(session, principal, page_id)
    version = session.scalar(
        select(KnowledgePageVersion).where(
            KnowledgePageVersion.id == page.current_version_id,
            KnowledgePageVersion.tenant_id == principal.tenant_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=409, detail="Knowledge page current version is unavailable")
    return PublicKnowledgePageDetail(
        **PublicKnowledgePageSummary.model_validate(page).model_dump(),
        version_number=version.version_number,
        rendered_markdown=public_knowledge_markdown(version.rendered_markdown),
        source_snapshot_at=version.source_snapshot_at,
    )


@app.get(
    "/api/v1/knowledge/pages/{page_id}/coverage",
    response_model=PublicKnowledgePageCoverageRead,
    tags=["knowledge"],
)
def get_knowledge_page_coverage(
    page_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> PublicKnowledgePageCoverageRead:
    principal.require("knowledge:read")
    _public_knowledge_page_or_404(session, principal, page_id)
    service = KnowledgeReadService(session, principal.tenant_id)
    try:
        coverage = service.coverage(page_id)
        return PublicKnowledgePageCoverageRead.model_validate(coverage.model_dump())
    except KnowledgePageNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KnowledgeVersionNotFound as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get(
    "/api/v1/knowledge/pages/{page_id}/versions",
    response_model=list[PublicKnowledgeVersionSummaryRead],
    tags=["knowledge"],
)
def list_knowledge_page_versions(
    page_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PublicKnowledgeVersionSummaryRead]:
    principal.require("knowledge:read")
    _public_knowledge_page_or_404(session, principal, page_id)
    try:
        history = KnowledgeReadService(session, principal.tenant_id).version_history(page_id, limit)
        return [PublicKnowledgeVersionSummaryRead.model_validate(item.model_dump()) for item in history]
    except KnowledgePageNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/api/v1/knowledge/pages/{page_id}/versions/{version_number}/diff",
    response_model=PublicKnowledgeVersionDiffRead,
    tags=["knowledge"],
)
def get_knowledge_page_version_diff(
    page_id: str,
    version_number: int,
    principal: PrincipalDep,
    session: SessionDep,
    compare_to: int | None = Query(default=None, ge=1),
) -> PublicKnowledgeVersionDiffRead:
    principal.require("knowledge:read")
    if version_number < 1:
        raise HTTPException(status_code=422, detail="version_number must be at least 1")
    _public_knowledge_page_or_404(session, principal, page_id)
    try:
        diff = KnowledgeReadService(session, principal.tenant_id).version_diff(
            page_id,
            version_number,
            compare_to,
        )
        return PublicKnowledgeVersionDiffRead.model_validate(diff.model_dump())
    except (KnowledgePageNotFound, KnowledgeVersionNotFound) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


web_root = get_settings().web_root
if web_root.is_dir():

    @app.api_route("/workspace/research", methods=["GET", "HEAD"], include_in_schema=False)
    def research_workspace_entry() -> FileResponse:
        return FileResponse(web_root / "research.html")

    @app.api_route("/workspace/internal", methods=["GET", "HEAD"], include_in_schema=False)
    def internal_workspace_entry() -> FileResponse:
        return FileResponse(web_root / "internal.html")

    app.mount("/", StaticFiles(directory=web_root, html=True), name="workspace")


def run() -> None:
    settings = get_settings()
    instrument_fastapi(app, "pharma-api")
    uvicorn.run("pharma_intel.api:app", host=settings.app_host, port=settings.app_port)
