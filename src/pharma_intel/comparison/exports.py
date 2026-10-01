from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

import xlsxwriter  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_intel.comparison.service import ComparisonSetConflict, ComparisonSetService
from pharma_intel.config import get_settings
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.licensing import canonical_policy_sha256
from pharma_intel.models import (
    AuditEvent,
    DealDirection,
    DealPartyRole,
    DealRightType,
    DealStatus,
    DevelopmentPhase,
    EntityType,
    RegulatoryDesignationType,
    RegulatoryLabelChangeType,
    RegulatorySafetySeverity,
    RegulatorySafetySignalType,
    RegulatorySafetyStatus,
    ReviewStatus,
    TrialEntityRole,
    TrialResultEvaluation,
    WorkspaceExportEvent,
    WorkspaceExportPolicy,
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
    ClinicalTrialSearchItemRead,
    ClinicalTrialSortField,
    CompetitiveProgramRead,
    DealSearchItemRead,
    DealSortField,
    EntityRead,
    EntitySortField,
    EpidemiologyObservationSearchItemRead,
    EpidemiologySortField,
    NewsEventSearchItemRead,
    NewsSortField,
    PatentFamilySearchItemRead,
    PatentSortField,
    PipelineSortField,
    RegulatoryEventSearchItemRead,
    RegulatorySortField,
    SortDirection,
    SortToken,
    WorkspaceDomainExportCreate,
    WorkspaceExportCreate,
    WorkspaceExportPolicyUpsert,
)
from pharma_intel.search.client import SearchProjectionError
from pharma_intel.search.service import EntitySearchService
from pharma_intel.sorting import MAX_SORT_CRITERIA, SortClause, parse_sort_tokens, validate_sort_clauses

WORKSPACE_EXPORT_FIELDS = frozenset(
    {
        "position",
        "id",
        "entity_type",
        "name",
        "description",
        "external_ids",
        "review_status",
        "created_at",
        "updated_at",
    }
)
REQUIRED_WORKSPACE_EXPORT_FIELDS = frozenset({"id", "entity_type", "name"})
WORKSPACE_EXPORT_FORMATS = frozenset({"csv", "json", "xlsx"})
DOMAIN_EXPORT_FIELDS: dict[str, tuple[str, ...]] = {
    "entities": tuple(EntityRead.model_fields),
    "pipelines": tuple(CompetitiveProgramRead.model_fields),
    "trials": tuple(ClinicalTrialSearchItemRead.model_fields),
    "patents": tuple(PatentFamilySearchItemRead.model_fields),
    "deals": tuple(DealSearchItemRead.model_fields),
    "regulatory": tuple(RegulatoryEventSearchItemRead.model_fields),
    "epidemiology": tuple(EpidemiologyObservationSearchItemRead.model_fields),
    "news": tuple(NewsEventSearchItemRead.model_fields),
}
WORKSPACE_EXPORT_POLICY_FIELDS = WORKSPACE_EXPORT_FIELDS | frozenset(
    f"{dataset}.{field}" for dataset, fields in DOMAIN_EXPORT_FIELDS.items() for field in fields
)
MAX_WORKSPACE_EXPORT_BYTES = 10_000_000


def _synchronize_export_sort(model: Any, allowed_fields: tuple[str, ...]) -> None:
    clauses = parse_sort_tokens(model.sort, allowed_fields)
    if not clauses:
        return
    primary = clauses[0]
    if "sort_by" in model.model_fields_set and model.sort_by != primary.field:
        raise ValueError("sort_by must match the first sort criterion")
    if "sort_direction" in model.model_fields_set and model.sort_direction != primary.direction:
        raise ValueError("sort_direction must match the first sort criterion")
    model.sort_by = primary.field
    model.sort_direction = primary.direction


def _export_sort[SortField: str](
    tokens: list[str],
    allowed_fields: tuple[SortField, ...],
    default_field: SortField,
    default_direction: SortDirection,
) -> tuple[SortClause[SortField], ...]:
    return validate_sort_clauses(
        parse_sort_tokens(tokens, allowed_fields),
        allowed_fields,
        default_field=default_field,
        default_direction=default_direction,
    )


class _BoundedExportQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_bounded_values(self) -> _BoundedExportQuery:
        values = self.model_dump(exclude_none=True)
        if any(
            isinstance(value, str) and len(value) > (760 if field_name == "target_combination_key" else 500)
            for field_name, value in values.items()
        ):
            raise ValueError("Workspace domain export query values are too long")
        range_pairs = (
            ("status_date_from", "status_date_to"),
            ("global_phase_started_from", "global_phase_started_to"),
            ("china_phase_started_from", "china_phase_started_to"),
            ("milestone_from", "milestone_to"),
            ("results_posted_from", "results_posted_to"),
            ("disclosed_from", "disclosed_to"),
            ("announced_from", "announced_to"),
            ("terminated_from", "terminated_to"),
            ("source_updated_from", "source_updated_to"),
            ("decision_from", "decision_to"),
            ("priority_from", "priority_to"),
            ("expiration_from", "expiration_to"),
            ("period_start_from", "period_end_to"),
            ("published_from", "published_to"),
            ("upfront_amount_min", "upfront_amount_max"),
            ("total_potential_amount_min", "total_potential_amount_max"),
        )
        for start_field, end_field in range_pairs:
            start = values.get(start_field)
            end = values.get(end_field)
            if start is not None and end is not None and start > end:
                raise ValueError(f"{start_field} must not exceed {end_field}")
        return self


class _EntityExportQuery(_BoundedExportQuery):
    q: str | None = Field(default=None, max_length=500)
    entity_type: EntityType | None = None
    entity_types: list[EntityType] = Field(default_factory=list, max_length=10)
    review_status: ReviewStatus | None = None
    sort_by: EntitySortField = "relevance"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)

    @model_validator(mode="after")
    def validate_sort(self) -> _EntityExportQuery:
        _synchronize_export_sort(self, ENTITY_SORT_FIELDS)
        return self


class _PipelineExportQuery(_BoundedExportQuery):
    q: str | None = None
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
    geography: str | None = None
    status_date_from: datetime | None = None
    status_date_to: datetime | None = None
    drug_entity_id: str | None = None
    target_entity_id: str | None = None
    target_combination_key: str | None = Field(
        default=None,
        max_length=760,
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}(?:\|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}){0,19}$",
    )
    disease_entity_id: str | None = None
    organization_entity_id: str | None = None
    global_phase: DevelopmentPhase | None = None
    china_phase: DevelopmentPhase | None = None
    global_phase_started_from: datetime | None = None
    global_phase_started_to: datetime | None = None
    china_phase_started_from: datetime | None = None
    china_phase_started_to: datetime | None = None
    development_rights_region: str | None = None
    commercialization_rights_region: str | None = None
    program_tag: list[Annotated[str, Field(min_length=1, max_length=240)]] | None = Field(
        default=None,
        max_length=20,
    )
    milestone_type: str | None = None
    milestone_from: datetime | None = None
    milestone_to: datetime | None = None
    has_clinical_results: bool | None = None
    clinical_result_evaluation: TrialResultEvaluation | None = None
    has_deal: bool | None = None
    deal_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    deal_total_potential_amount_min: float | None = Field(default=None, ge=0)
    deal_total_potential_amount_max: float | None = Field(default=None, ge=0)
    sort_by: PipelineSortField = "status_date"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)

    @field_validator("modality", "innovation_type", "therapeutic_area", "drug_category", "program_tag", mode="before")
    @classmethod
    def normalize_repeated_pipeline_filters(cls, value: Any) -> Any:
        # Single-value exports from legacy saved URLs arrive as plain strings; empty
        # collections normalize to None so they never widen the export beyond the list.
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
    def validate_signal_filters(self) -> _PipelineExportQuery:
        _synchronize_export_sort(self, PIPELINE_SORT_FIELDS)
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


class _TrialExportQuery(_BoundedExportQuery):
    q: str | None = None
    registry: str | None = None
    status: str | None = None
    phase: str | None = None
    study_type: str | None = None
    acronym: str | None = None
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
    results_posted_from: datetime | None = None
    results_posted_to: datetime | None = None
    investigational_drug: str | None = None
    combination_drug: str | None = None
    investigational_target: str | None = None
    combination_target: str | None = None
    investigational_drug_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    combination_drug_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    investigational_target_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    combination_target_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    linked_drug_modality: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None, max_length=20
    )
    linked_drug_innovation_type: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None, max_length=20
    )
    linked_drug_category: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None, max_length=20
    )
    linked_drug_program_tag: list[Annotated[str, Field(min_length=1, max_length=240)]] | None = Field(
        default=None, max_length=20
    )
    linked_drug_global_phase: DevelopmentPhase | None = None
    linked_drug_organization_country_region: str | None = Field(default=None, min_length=1, max_length=120)
    role_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    role_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    role_entity_role: TrialEntityRole | None = None
    has_key_result: bool | None = None
    publication_id: str | None = None
    conference: str | None = None
    disclosed_from: datetime | None = None
    disclosed_to: datetime | None = None
    sort_by: ClinicalTrialSortField = "last_update_posted"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)

    @model_validator(mode="after")
    def require_entity_for_role(self) -> _TrialExportQuery:
        _synchronize_export_sort(self, CLINICAL_TRIAL_SORT_FIELDS)
        if self.role_entity_id is not None and self.role_entity_ids is not None:
            raise ValueError("role_entity_id cannot be combined with role_entity_ids")
        if self.role_entity_role is not None and self.role_entity_id is None and self.role_entity_ids is None:
            raise ValueError("role_entity_role requires role_entity_id or role_entity_ids")
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
    def normalize_linked_drug_values(cls, value: Any) -> Any:
        if value is None:
            return None
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list):
            return values
        normalized = sorted({item.strip() for item in values if isinstance(item, str) and item.strip()})
        return normalized or None


class _PatentExportQuery(_BoundedExportQuery):
    q: str | None = None
    entity_id: str | None = None
    applicant: str | None = None
    legal_status: str | None = None
    priority_from: datetime | None = None
    priority_to: datetime | None = None
    expiration_from: datetime | None = None
    expiration_to: datetime | None = None
    sort_by: PatentSortField = "priority_date"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)

    @model_validator(mode="after")
    def validate_sort(self) -> _PatentExportQuery:
        _synchronize_export_sort(self, PATENT_SORT_FIELDS)
        return self


class _DealExportQuery(_BoundedExportQuery):
    q: str | None = None
    deal_type: str | None = None
    status: DealStatus | None = None
    direction: DealDirection | None = None
    direction_reference_jurisdiction: str | None = None
    territory: str | None = None
    asset_entity_id: str | None = None
    target_entity_id: str | None = None
    disease_entity_id: str | None = None
    asset_modality: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None,
        max_length=20,
    )
    asset_program_tag: list[Annotated[str, Field(min_length=1, max_length=240)]] | None = Field(
        default=None,
        max_length=20,
    )
    party: str | None = None
    party_entity_id: str | None = None
    party_role: DealPartyRole | None = None
    party_country_region: str | None = None
    party_organization_type: str | None = None
    development_phase_at_transaction: DevelopmentPhase | None = None
    current_development_phase: DevelopmentPhase | None = None
    right_type: DealRightType | None = None
    rights_territory: str | None = None
    currency: str | None = None
    announced_from: datetime | None = None
    announced_to: datetime | None = None
    terminated_from: datetime | None = None
    terminated_to: datetime | None = None
    source_updated_from: datetime | None = None
    source_updated_to: datetime | None = None
    upfront_amount_min: float | None = Field(default=None, ge=0)
    upfront_amount_max: float | None = Field(default=None, ge=0)
    total_potential_amount_min: float | None = Field(default=None, ge=0)
    total_potential_amount_max: float | None = Field(default=None, ge=0)
    sort_by: DealSortField = "announced_at"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)

    @field_validator("asset_modality", "asset_program_tag", mode="before")
    @classmethod
    def normalize_repeated_asset_filters(cls, value: Any) -> Any:
        if value is None:
            return None
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list):
            return values
        return list(dict.fromkeys(item.strip() if isinstance(item, str) else item for item in values))

    @model_validator(mode="after")
    def require_currency_for_amount_sort(self) -> _DealExportQuery:
        _synchronize_export_sort(self, DEAL_SORT_FIELDS)
        if (
            any(token.startswith(("upfront_amount:", "total_potential_amount:")) for token in self.sort)
            and not self.currency
        ):
            raise ValueError("currency is required when sorting disclosed deal amounts")
        if not self.sort and self.sort_by in {"upfront_amount", "total_potential_amount"} and not self.currency:
            raise ValueError("currency is required when sorting disclosed deal amounts")
        return self


class _RegulatoryExportQuery(_BoundedExportQuery):
    q: str | None = None
    agency: str | None = None
    jurisdiction: str | None = None
    event_type: str | None = None
    status: str | None = None
    designation_type: RegulatoryDesignationType | None = None
    label_change_type: RegulatoryLabelChangeType | None = None
    has_boxed_warning: bool | None = None
    safety_signal_type: RegulatorySafetySignalType | None = None
    safety_severity: RegulatorySafetySeverity | None = None
    safety_status: RegulatorySafetyStatus | None = None
    decision_from: datetime | None = None
    decision_to: datetime | None = None
    source_updated_from: datetime | None = None
    source_updated_to: datetime | None = None
    sort_by: RegulatorySortField = "decision_date"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)

    @model_validator(mode="after")
    def validate_sort(self) -> _RegulatoryExportQuery:
        _synchronize_export_sort(self, REGULATORY_SORT_FIELDS)
        return self


class _EpidemiologyExportQuery(_BoundedExportQuery):
    q: str | None = None
    disease_entity_id: str | None = None
    measure: str | None = None
    geography: str | None = None
    unit: str | None = None
    population_scope: str | None = None
    patient_population_id: str | None = None
    age_group: str | None = None
    sex: str | None = None
    period_start_from: datetime | None = None
    period_end_to: datetime | None = None
    sort_by: EpidemiologySortField = "period_end"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)

    @model_validator(mode="after")
    def validate_sort(self) -> _EpidemiologyExportQuery:
        _synchronize_export_sort(self, EPIDEMIOLOGY_SORT_FIELDS)
        return self


class _NewsExportQuery(_BoundedExportQuery):
    q: str | None = None
    entity_id: str | None = None
    event_type: str | None = None
    publisher: str | None = None
    language: str | None = None
    venue: str | None = None
    content_scope: Literal["research"] | None = None
    published_from: datetime | None = None
    published_to: datetime | None = None
    sort_by: NewsSortField = "published_at"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)

    @model_validator(mode="after")
    def validate_sort(self) -> _NewsExportQuery:
        _synchronize_export_sort(self, NEWS_SORT_FIELDS)
        return self


class WorkspaceExportError(Exception):
    pass


class WorkspaceExportNotConfigured(WorkspaceExportError):
    pass


class WorkspaceExportDenied(WorkspaceExportError):
    pass


class WorkspaceExportConflict(WorkspaceExportError):
    pass


@dataclass(frozen=True)
class WorkspaceExportArtifact:
    event_id: str
    filename: str
    media_type: str
    content: bytes
    content_sha256: str
    policy_version: str
    attribution: str
    replayed: bool


class WorkspaceComparisonExportService:
    def __init__(self, session: Session, tenant_id: str, user_id: str, *, include_unpublished: bool = False) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.include_unpublished = include_unpublished

    def get_policy(self) -> WorkspaceExportPolicy:
        policy = self.session.scalar(
            select(WorkspaceExportPolicy).where(WorkspaceExportPolicy.tenant_id == self.tenant_id)
        )
        if policy is None:
            raise WorkspaceExportNotConfigured("Workspace export policy is not configured")
        return policy

    def policy_view(self, policy: WorkspaceExportPolicy) -> dict[str, object]:
        return {
            "id": policy.id,
            "policy_version": policy.policy_version,
            "enabled": policy.enabled,
            "allowed_formats": policy.allowed_formats,
            "allowed_fields": policy.allowed_fields,
            "max_records_per_export": policy.max_records_per_export,
            "attribution": policy.attribution,
            "configured_by_user_id": policy.configured_by_user_id,
            "policy_sha256": canonical_policy_sha256(self._policy_document(policy)),
            "created_at": policy.created_at,
            "updated_at": policy.updated_at,
        }

    def upsert_policy(self, command: WorkspaceExportPolicyUpsert) -> WorkspaceExportPolicy:
        requested = self._validated_policy_document(command)
        current = self.session.scalar(
            select(WorkspaceExportPolicy).where(WorkspaceExportPolicy.tenant_id == self.tenant_id).with_for_update()
        )
        if current is not None and current.policy_version == command.policy_version:
            if self._policy_document(current) != requested:
                raise WorkspaceExportConflict("A policy version cannot be reused for different export rights")
            return current
        if current is None:
            current = WorkspaceExportPolicy(
                tenant_id=self.tenant_id,
                policy_version=command.policy_version,
                enabled=command.enabled,
                allowed_formats=command.allowed_formats,
                allowed_fields=command.allowed_fields,
                max_records_per_export=command.max_records_per_export,
                attribution=command.attribution,
                configured_by_user_id=self.user_id,
            )
            self.session.add(current)
        else:
            current.policy_version = command.policy_version
            current.enabled = command.enabled
            current.allowed_formats = list(command.allowed_formats)
            current.allowed_fields = command.allowed_fields
            current.max_records_per_export = command.max_records_per_export
            current.attribution = command.attribution
            current.configured_by_user_id = self.user_id
        self.session.flush()
        self._audit(
            current.id,
            "workspace.export_policy.configure",
            {"policy_version": current.policy_version, "policy_sha256": canonical_policy_sha256(requested)},
        )
        self.session.commit()
        self.session.refresh(current)
        return current

    def export_comparison_set(self, item_id: str, command: WorkspaceExportCreate) -> WorkspaceExportArtifact:
        policy = self.get_policy()
        policy_document = self._policy_document(policy)
        policy_sha256 = canonical_policy_sha256(policy_document)
        if not policy.enabled:
            raise WorkspaceExportDenied("Workspace exports are disabled by policy")
        fields = list(command.fields)
        if not REQUIRED_WORKSPACE_EXPORT_FIELDS.issubset(fields):
            raise WorkspaceExportDenied("Workspace exports must include stable ID, entity type and name")
        if not set(fields).issubset(WORKSPACE_EXPORT_FIELDS) or not set(fields).issubset(policy.allowed_fields):
            raise WorkspaceExportDenied("Requested export fields are not allowed by policy")
        if command.export_format not in WORKSPACE_EXPORT_FORMATS or command.export_format not in policy.allowed_formats:
            raise WorkspaceExportDenied("Requested export format is not allowed by policy")
        comparison = ComparisonSetService(
            self.session, self.tenant_id, self.user_id, include_unpublished=self.include_unpublished
        ).get_set(item_id)
        if comparison.item.version != command.expected_version:
            raise ComparisonSetConflict(f"Comparison set version changed; current version is {comparison.item.version}")
        if comparison.member_count < 1:
            raise WorkspaceExportDenied("Empty comparison sets cannot be exported")
        if comparison.member_count > policy.max_records_per_export:
            raise WorkspaceExportDenied("Comparison set exceeds the workspace export record limit")
        request_document = {
            "comparison_set_id": comparison.item.id,
            "publication_scope": "review" if self.include_unpublished else "published",
            "comparison_set_version": comparison.item.version,
            "export_format": command.export_format,
            "fields": fields,
            "policy_sha256": policy_sha256,
        }
        request_sha256 = _canonical_sha256(request_document)
        existing = self._event_for_key(command.idempotency_key)
        if existing is not None:
            return self._replay(existing, request_sha256, comparison.item.name)
        records = [
            {field: _record_value(field, member, index) for field in fields}
            for index, member in enumerate(comparison.members)
        ]
        event_id = str(uuid.uuid4())
        generated_at = datetime.now(UTC)
        content = self._encode(
            command.export_format,
            fields,
            records,
            event_id=event_id,
            set_id=comparison.item.id,
            set_name=comparison.item.name,
            set_version=comparison.item.version,
            generated_at=generated_at,
            policy_version=policy.policy_version,
            attribution=policy.attribution,
        )
        if not content or len(content) > MAX_WORKSPACE_EXPORT_BYTES:
            raise WorkspaceExportDenied("Workspace export artifact exceeds the bounded size limit")
        content_sha256 = hashlib.sha256(content).hexdigest()
        event = WorkspaceExportEvent(
            id=event_id,
            tenant_id=self.tenant_id,
            comparison_set_id=comparison.item.id,
            comparison_set_version=comparison.item.version,
            requested_by_user_id=self.user_id,
            idempotency_key=command.idempotency_key,
            request_sha256=request_sha256,
            export_format=command.export_format,
            fields_json=fields,
            records_json=records,
            record_count=len(records),
            policy_version=policy.policy_version,
            policy_sha256=policy_sha256,
            attribution=policy.attribution,
            content_sha256=content_sha256,
            content_bytes=len(content),
            generated_at=generated_at,
        )
        self.session.add(event)
        self._audit(
            event.id,
            "workspace.comparison_export.generate",
            {
                "comparison_set_id": comparison.item.id,
                "comparison_set_version": comparison.item.version,
                "record_count": len(records),
                "format": command.export_format,
                "policy_version": policy.policy_version,
                "content_sha256": content_sha256,
            },
        )
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raced = self._event_for_key(command.idempotency_key)
            if raced is None:
                raise
            return self._replay(raced, request_sha256, comparison.item.name)
        return self._artifact(event, content, replayed=False)

    def export_domain_query(self, command: WorkspaceDomainExportCreate) -> WorkspaceExportArtifact:
        policy = self.get_policy()
        policy_document = self._policy_document(policy)
        policy_sha256 = canonical_policy_sha256(policy_document)
        if not policy.enabled:
            raise WorkspaceExportDenied("Workspace exports are disabled by policy")
        if command.dataset not in DOMAIN_EXPORT_FIELDS:
            raise WorkspaceExportDenied("Workspace domain export dataset is unsupported")
        if command.export_format not in WORKSPACE_EXPORT_FORMATS or command.export_format not in policy.allowed_formats:
            raise WorkspaceExportDenied("Requested export format is not allowed by policy")
        if command.max_records > policy.max_records_per_export:
            raise WorkspaceExportDenied("Requested export record limit exceeds the workspace policy")
        fields = list(command.fields)
        supported_fields = set(DOMAIN_EXPORT_FIELDS[command.dataset])
        licensed_fields = {
            field.removeprefix(f"{command.dataset}.")
            for field in policy.allowed_fields
            if field.startswith(f"{command.dataset}.")
        }
        if "id" not in fields:
            raise WorkspaceExportDenied("Workspace domain export fields must include id")
        if set(fields) - supported_fields or set(fields) - licensed_fields:
            raise WorkspaceExportDenied("Requested workspace domain export fields are not allowed by policy")
        request_document = {
            "dataset": command.dataset,
            "query": command.query,
            "publication_scope": "review" if self.include_unpublished else "published",
            "export_format": command.export_format,
            "fields": fields,
            "max_records": command.max_records,
            "policy_sha256": policy_sha256,
        }
        request_sha256 = _canonical_sha256(request_document)
        existing = self._event_for_key(command.idempotency_key)
        if existing is not None:
            return self._replay_domain(existing, request_sha256)
        try:
            records, query_schema_version = self._domain_records(command)
        except (ValidationError, ValueError, SearchProjectionError) as exc:
            raise WorkspaceExportDenied("Workspace domain export query is invalid or unavailable") from exc
        if not records:
            raise WorkspaceExportDenied("Empty workspace domain query results cannot be exported")
        event_id = str(uuid.uuid4())
        generated_at = datetime.now(UTC)
        metadata = {
            "schema": "pharma.workspace-domain-export.v1",
            "export_event_id": event_id,
            "dataset": command.dataset,
            "query_schema_version": query_schema_version,
            "query": command.query,
            "generated_at": generated_at.isoformat(),
            "as_of": generated_at.isoformat(),
            "policy_version": policy.policy_version,
            "attribution": policy.attribution,
            "warnings": self._query_warnings(command.dataset),
        }
        content = self._encode_domain(command.export_format, fields, records, metadata)
        if not content or len(content) > MAX_WORKSPACE_EXPORT_BYTES:
            raise WorkspaceExportDenied("Workspace domain export artifact exceeds the bounded size limit")
        content_sha256 = hashlib.sha256(content).hexdigest()
        event = WorkspaceExportEvent(
            id=event_id,
            tenant_id=self.tenant_id,
            export_kind="domain",
            comparison_set_id=None,
            comparison_set_version=None,
            dataset=command.dataset,
            query_json=command.query,
            requested_by_user_id=self.user_id,
            idempotency_key=command.idempotency_key,
            request_sha256=request_sha256,
            export_format=command.export_format,
            fields_json=fields,
            records_json=records,
            record_count=len(records),
            policy_version=policy.policy_version,
            policy_sha256=policy_sha256,
            attribution=policy.attribution,
            content_sha256=content_sha256,
            content_bytes=len(content),
            generated_at=generated_at,
        )
        self.session.add(event)
        self._audit(
            event.id,
            "workspace.domain_export.generate",
            {
                "dataset": command.dataset,
                "record_count": len(records),
                "format": command.export_format,
                "policy_version": policy.policy_version,
                "policy_sha256": policy_sha256,
                "request_sha256": request_sha256,
                "content_sha256": content_sha256,
            },
        )
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raced = self._event_for_key(command.idempotency_key)
            if raced is None:
                raise
            return self._replay_domain(raced, request_sha256)
        return self._domain_artifact(event, content, replayed=False)

    def _domain_records(self, command: WorkspaceDomainExportCreate) -> tuple[list[dict[str, Any]], str]:
        intelligence = IntelligenceService(self.session, self.tenant_id, include_unpublished=self.include_unpublished)
        if command.dataset == "entities":
            entity_query = _EntityExportQuery.model_validate(command.query)
            if not self.include_unpublished and entity_query.review_status not in {None, ReviewStatus.VERIFIED}:
                raise WorkspaceExportDenied("Unpublished records require governance access")
            entity_result = EntitySearchService(self.session, self.tenant_id, get_settings()).search(
                entity_query.q,
                entity_query.entity_type,
                command.max_records,
                0,
                entity_query.review_status if self.include_unpublished else ReviewStatus.VERIFIED,
                entity_query.sort_by,
                entity_query.sort_direction,
                entity_query.entity_types,
                _export_sort(
                    entity_query.sort,
                    ENTITY_SORT_FIELDS,
                    entity_query.sort_by,
                    entity_query.sort_direction,
                ),
            )
            return self._selected_records(entity_result.items, command.fields, EntityRead), self._query_schema_version(
                command.dataset
            )
        if command.dataset == "pipelines":
            pipeline_query = _PipelineExportQuery.model_validate(command.query)
            pipeline_result = intelligence.search_programs(
                pipeline_query.q,
                pipeline_query.modality,
                pipeline_query.phase.value if pipeline_query.phase else None,
                pipeline_query.geography,
                command.max_records,
                0,
                program_status=pipeline_query.program_status,
                organization_role=pipeline_query.organization_role,
                organization_type=pipeline_query.organization_type,
                organization_country_region=pipeline_query.organization_country_region,
                innovation_type=pipeline_query.innovation_type,
                therapeutic_area=pipeline_query.therapeutic_area,
                drug_category=pipeline_query.drug_category,
                status_date_from=pipeline_query.status_date_from,
                status_date_to=pipeline_query.status_date_to,
                drug_entity_id=pipeline_query.drug_entity_id,
                target_entity_id=pipeline_query.target_entity_id,
                target_combination_key=(
                    pipeline_query.target_combination_key.lower() if pipeline_query.target_combination_key else None
                ),
                disease_entity_id=pipeline_query.disease_entity_id,
                organization_entity_id=pipeline_query.organization_entity_id,
                global_phase=pipeline_query.global_phase.value if pipeline_query.global_phase else None,
                china_phase=pipeline_query.china_phase.value if pipeline_query.china_phase else None,
                global_phase_started_from=pipeline_query.global_phase_started_from,
                global_phase_started_to=pipeline_query.global_phase_started_to,
                china_phase_started_from=pipeline_query.china_phase_started_from,
                china_phase_started_to=pipeline_query.china_phase_started_to,
                development_rights_region=pipeline_query.development_rights_region,
                commercialization_rights_region=pipeline_query.commercialization_rights_region,
                program_tag=pipeline_query.program_tag,
                milestone_type=pipeline_query.milestone_type,
                milestone_from=pipeline_query.milestone_from,
                milestone_to=pipeline_query.milestone_to,
                has_clinical_results=pipeline_query.has_clinical_results,
                clinical_result_evaluation=(
                    pipeline_query.clinical_result_evaluation.value
                    if pipeline_query.clinical_result_evaluation
                    else None
                ),
                has_deal=pipeline_query.has_deal,
                deal_currency=pipeline_query.deal_currency,
                deal_total_potential_amount_min=pipeline_query.deal_total_potential_amount_min,
                deal_total_potential_amount_max=pipeline_query.deal_total_potential_amount_max,
                sort_by=pipeline_query.sort_by,
                sort_direction=pipeline_query.sort_direction,
                sort=_export_sort(
                    pipeline_query.sort,
                    PIPELINE_SORT_FIELDS,
                    pipeline_query.sort_by,
                    pipeline_query.sort_direction,
                ),
            )
            return self._selected_records(
                pipeline_result.items, command.fields, CompetitiveProgramRead
            ), pipeline_result.query_schema_version
        if command.dataset == "trials":
            trial_query = _TrialExportQuery.model_validate(command.query)
            trial_result = intelligence.search_clinical_trials(
                trial_query.q,
                trial_query.registry,
                trial_query.status,
                trial_query.phase,
                trial_query.study_type,
                trial_query.has_results,
                command.max_records,
                0,
                results_posted_from=trial_query.results_posted_from,
                results_posted_to=trial_query.results_posted_to,
                result_evaluation=trial_query.result_evaluation.value if trial_query.result_evaluation else None,
                acronym=trial_query.acronym,
                initiation_type=trial_query.initiation_type,
                therapy_line=trial_query.therapy_line,
                investigational_drug=trial_query.investigational_drug,
                combination_drug=trial_query.combination_drug,
                investigational_target=trial_query.investigational_target,
                combination_target=trial_query.combination_target,
                investigational_drug_entity_ids=trial_query.investigational_drug_entity_ids,
                combination_drug_entity_ids=trial_query.combination_drug_entity_ids,
                investigational_target_entity_ids=trial_query.investigational_target_entity_ids,
                combination_target_entity_ids=trial_query.combination_target_entity_ids,
                linked_drug_modality=trial_query.linked_drug_modality,
                linked_drug_innovation_type=trial_query.linked_drug_innovation_type,
                linked_drug_category=trial_query.linked_drug_category,
                linked_drug_program_tag=trial_query.linked_drug_program_tag,
                linked_drug_global_phase=(
                    trial_query.linked_drug_global_phase.value if trial_query.linked_drug_global_phase else None
                ),
                linked_drug_organization_country_region=trial_query.linked_drug_organization_country_region,
                role_entity_id=trial_query.role_entity_id,
                role_entity_ids=trial_query.role_entity_ids,
                role_entity_role=trial_query.role_entity_role.value if trial_query.role_entity_role else None,
                has_key_result=trial_query.has_key_result,
                publication_id=trial_query.publication_id,
                conference=trial_query.conference,
                disclosed_from=trial_query.disclosed_from,
                disclosed_to=trial_query.disclosed_to,
                sort_by=trial_query.sort_by,
                sort_direction=trial_query.sort_direction,
                sort=_export_sort(
                    trial_query.sort,
                    CLINICAL_TRIAL_SORT_FIELDS,
                    trial_query.sort_by,
                    trial_query.sort_direction,
                ),
            )
            return self._selected_records(
                trial_result.items, command.fields, ClinicalTrialSearchItemRead
            ), trial_result.query_schema_version
        if command.dataset == "patents":
            patent_query = _PatentExportQuery.model_validate(command.query)
            patent_result = intelligence.search_patent_families(
                patent_query.q,
                patent_query.applicant,
                patent_query.legal_status,
                command.max_records,
                0,
                entity_id=patent_query.entity_id,
                priority_from=patent_query.priority_from,
                priority_to=patent_query.priority_to,
                expiration_from=patent_query.expiration_from,
                expiration_to=patent_query.expiration_to,
                sort_by=patent_query.sort_by,
                sort_direction=patent_query.sort_direction,
                sort=_export_sort(
                    patent_query.sort,
                    PATENT_SORT_FIELDS,
                    patent_query.sort_by,
                    patent_query.sort_direction,
                ),
            )
            return self._selected_records(
                patent_result.items, command.fields, PatentFamilySearchItemRead
            ), patent_result.query_schema_version
        if command.dataset == "deals":
            deal_query = _DealExportQuery.model_validate(command.query)
            deal_result = intelligence.search_deals(
                deal_query.q,
                deal_query.deal_type,
                deal_query.territory,
                deal_query.party,
                command.max_records,
                0,
                status=deal_query.status.value if deal_query.status else None,
                direction=deal_query.direction.value if deal_query.direction else None,
                direction_reference_jurisdiction=deal_query.direction_reference_jurisdiction,
                asset_entity_id=deal_query.asset_entity_id,
                target_entity_id=deal_query.target_entity_id,
                disease_entity_id=deal_query.disease_entity_id,
                asset_modality=deal_query.asset_modality,
                asset_program_tag=deal_query.asset_program_tag,
                party_entity_id=deal_query.party_entity_id,
                party_role=deal_query.party_role.value if deal_query.party_role else None,
                party_country_region=deal_query.party_country_region,
                party_organization_type=deal_query.party_organization_type,
                development_phase_at_transaction=(
                    deal_query.development_phase_at_transaction.value
                    if deal_query.development_phase_at_transaction
                    else None
                ),
                current_development_phase=(
                    deal_query.current_development_phase.value if deal_query.current_development_phase else None
                ),
                right_type=deal_query.right_type.value if deal_query.right_type else None,
                rights_territory=deal_query.rights_territory,
                currency=deal_query.currency,
                announced_from=deal_query.announced_from,
                announced_to=deal_query.announced_to,
                terminated_from=deal_query.terminated_from,
                terminated_to=deal_query.terminated_to,
                source_updated_from=deal_query.source_updated_from,
                source_updated_to=deal_query.source_updated_to,
                upfront_amount_min=deal_query.upfront_amount_min,
                upfront_amount_max=deal_query.upfront_amount_max,
                total_potential_amount_min=deal_query.total_potential_amount_min,
                total_potential_amount_max=deal_query.total_potential_amount_max,
                sort_by=deal_query.sort_by,
                sort_direction=deal_query.sort_direction,
                sort=_export_sort(
                    deal_query.sort,
                    DEAL_SORT_FIELDS,
                    deal_query.sort_by,
                    deal_query.sort_direction,
                ),
            )
            return self._selected_records(
                deal_result.items, command.fields, DealSearchItemRead
            ), deal_result.query_schema_version
        if command.dataset == "regulatory":
            regulatory_query = _RegulatoryExportQuery.model_validate(command.query)
            regulatory_result = intelligence.search_regulatory_events(
                regulatory_query.q,
                regulatory_query.agency,
                regulatory_query.jurisdiction,
                regulatory_query.event_type,
                regulatory_query.status,
                command.max_records,
                0,
                designation_type=(
                    regulatory_query.designation_type.value if regulatory_query.designation_type else None
                ),
                label_change_type=(
                    regulatory_query.label_change_type.value if regulatory_query.label_change_type else None
                ),
                has_boxed_warning=regulatory_query.has_boxed_warning,
                safety_signal_type=(
                    regulatory_query.safety_signal_type.value if regulatory_query.safety_signal_type else None
                ),
                safety_severity=(regulatory_query.safety_severity.value if regulatory_query.safety_severity else None),
                safety_status=regulatory_query.safety_status.value if regulatory_query.safety_status else None,
                decision_from=regulatory_query.decision_from,
                decision_to=regulatory_query.decision_to,
                source_updated_from=regulatory_query.source_updated_from,
                source_updated_to=regulatory_query.source_updated_to,
                sort_by=regulatory_query.sort_by,
                sort_direction=regulatory_query.sort_direction,
                sort=_export_sort(
                    regulatory_query.sort,
                    REGULATORY_SORT_FIELDS,
                    regulatory_query.sort_by,
                    regulatory_query.sort_direction,
                ),
            )
            return self._selected_records(
                regulatory_result.items, command.fields, RegulatoryEventSearchItemRead
            ), regulatory_result.query_schema_version
        if command.dataset == "epidemiology":
            epidemiology_query = _EpidemiologyExportQuery.model_validate(command.query)
            epidemiology_result = intelligence.search_epidemiology_observations(
                epidemiology_query.q,
                epidemiology_query.measure,
                epidemiology_query.geography,
                epidemiology_query.unit,
                epidemiology_query.population_scope,
                epidemiology_query.age_group,
                epidemiology_query.sex,
                epidemiology_query.period_start_from,
                epidemiology_query.period_end_to,
                command.max_records,
                0,
                disease_entity_id=epidemiology_query.disease_entity_id,
                patient_population_id=epidemiology_query.patient_population_id,
                sort_by=epidemiology_query.sort_by,
                sort_direction=epidemiology_query.sort_direction,
                sort=_export_sort(
                    epidemiology_query.sort,
                    EPIDEMIOLOGY_SORT_FIELDS,
                    epidemiology_query.sort_by,
                    epidemiology_query.sort_direction,
                ),
            )
            return self._selected_records(
                epidemiology_result.items, command.fields, EpidemiologyObservationSearchItemRead
            ), epidemiology_result.query_schema_version
        if command.dataset == "news":
            news_query = _NewsExportQuery.model_validate(command.query)
            news_result = intelligence.search_news_events(
                news_query.q,
                news_query.event_type,
                news_query.publisher,
                news_query.language,
                news_query.venue,
                news_query.published_from,
                news_query.published_to,
                command.max_records,
                0,
                research_content_only=news_query.content_scope == "research",
                sort_by=news_query.sort_by,
                entity_id=news_query.entity_id,
                sort_direction=news_query.sort_direction,
                sort=_export_sort(
                    news_query.sort,
                    NEWS_SORT_FIELDS,
                    news_query.sort_by,
                    news_query.sort_direction,
                ),
            )
            return self._selected_records(
                news_result.items, command.fields, NewsEventSearchItemRead
            ), news_result.query_schema_version
        raise WorkspaceExportDenied("Workspace domain export dataset is unsupported")

    @staticmethod
    def _selected_records(
        items: list[Any],
        fields: list[str],
        model: type[BaseModel],
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in items:
            document = model.model_validate(item).model_dump(mode="json")
            records.append({field: document.get(field) for field in fields})
        return records

    def _replay(self, event: WorkspaceExportEvent, request_sha256: str, set_name: str) -> WorkspaceExportArtifact:
        if event.export_kind != "comparison" or event.request_sha256 != request_sha256:
            raise WorkspaceExportConflict("Idempotency key was already used for a different workspace export")
        if event.comparison_set_id is None or event.comparison_set_version is None:
            raise WorkspaceExportConflict("Comparison export subject is missing")
        content = self._encode(
            event.export_format,
            event.fields_json,
            event.records_json,
            event_id=event.id,
            set_id=event.comparison_set_id,
            set_name=set_name,
            set_version=event.comparison_set_version,
            generated_at=event.generated_at,
            policy_version=event.policy_version,
            attribution=event.attribution,
        )
        if len(content) != event.content_bytes or hashlib.sha256(content).hexdigest() != event.content_sha256:
            raise WorkspaceExportConflict("Immutable workspace export snapshot cannot be reproduced")
        return self._artifact(event, content, replayed=True)

    def _replay_domain(self, event: WorkspaceExportEvent, request_sha256: str) -> WorkspaceExportArtifact:
        if (
            event.export_kind != "domain"
            or event.request_sha256 != request_sha256
            or event.dataset is None
            or event.query_json is None
        ):
            raise WorkspaceExportConflict("Idempotency key was already used for a different workspace export")
        metadata = {
            "schema": "pharma.workspace-domain-export.v1",
            "export_event_id": event.id,
            "dataset": event.dataset,
            "query_schema_version": self._query_schema_version(event.dataset),
            "query": event.query_json,
            "generated_at": _utc_datetime(event.generated_at).isoformat(),
            "as_of": _utc_datetime(event.generated_at).isoformat(),
            "policy_version": event.policy_version,
            "attribution": event.attribution,
            "warnings": self._query_warnings(event.dataset),
        }
        content = self._encode_domain(event.export_format, event.fields_json, event.records_json, metadata)
        if len(content) != event.content_bytes or hashlib.sha256(content).hexdigest() != event.content_sha256:
            raise WorkspaceExportConflict("Immutable workspace domain export snapshot cannot be reproduced")
        return self._domain_artifact(event, content, replayed=True)

    @staticmethod
    def _query_schema_version(dataset: str) -> str:
        versions = {
            "entities": "pharma.entity.search.v2",
            "pipelines": "pharma.pipeline.search.v13",
            "trials": "pharma.clinical_trial.search.v10",
            "patents": "pharma.patent.search.v2",
            "deals": "pharma.deal.search.v8",
            "regulatory": "pharma.regulatory.search.v4",
            "epidemiology": "pharma.epidemiology.search.v3",
            "news": "pharma.news.search.v2",
        }
        try:
            return versions[dataset]
        except KeyError as exc:
            raise WorkspaceExportConflict("Workspace domain export dataset is invalid") from exc

    @staticmethod
    def _query_warnings(dataset: str) -> list[str]:
        warnings = {
            "entities": [],
            "pipelines": ["未观察到研发项目不代表不存在；结果受授权范围、时点和治理状态限制。"],
            "trials": ["未观察到临床试验不代表不存在；结果受注册平台、更新时间、数据授权和治理状态限制。"],
            "patents": ["未观察到专利族不代表不存在；结果受司法辖区、法律状态时效、数据授权和治理状态限制。"],
            "deals": ["未观察到交易不代表不存在；未披露金额、权益范围、数据授权和治理状态可能限制结果。"],
            "regulatory": ["未观察到监管事件不代表不存在；结果受监管机构、司法辖区、更新时间和数据授权限制。"],
            "epidemiology": ["流行病学估计受研究设计、口径、地区、时间、数据授权和治理状态限制。"],
            "news": ["未观察到事件不代表不存在；结果受来源覆盖、发布时间、数据授权和治理状态限制。"],
        }
        try:
            return warnings[dataset]
        except KeyError as exc:
            raise WorkspaceExportConflict("Workspace domain export dataset is invalid") from exc

    @staticmethod
    def _domain_artifact(event: WorkspaceExportEvent, content: bytes, *, replayed: bool) -> WorkspaceExportArtifact:
        if event.dataset is None:
            raise WorkspaceExportConflict("Workspace domain export dataset is missing")
        media_types = {
            "csv": "text/csv; charset=utf-8",
            "json": "application/json",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        return WorkspaceExportArtifact(
            event_id=event.id,
            filename=f"{event.dataset}-{event.id}.{event.export_format}",
            media_type=media_types[event.export_format],
            content=content,
            content_sha256=event.content_sha256,
            policy_version=event.policy_version,
            attribution=event.attribution,
            replayed=replayed,
        )

    @staticmethod
    def _artifact(event: WorkspaceExportEvent, content: bytes, *, replayed: bool) -> WorkspaceExportArtifact:
        media_types = {
            "csv": "text/csv; charset=utf-8",
            "json": "application/json",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        return WorkspaceExportArtifact(
            event_id=event.id,
            filename=f"comparison-{event.comparison_set_id}-v{event.comparison_set_version}.{event.export_format}",
            media_type=media_types[event.export_format],
            content=content,
            content_sha256=event.content_sha256,
            policy_version=event.policy_version,
            attribution=event.attribution,
            replayed=replayed,
        )

    @staticmethod
    def _encode(
        export_format: str,
        fields: list[str],
        records: list[dict[str, Any]],
        *,
        event_id: str,
        set_id: str,
        set_name: str,
        set_version: int,
        generated_at: datetime,
        policy_version: str,
        attribution: str,
    ) -> bytes:
        generated_at = _utc_datetime(generated_at)
        metadata = {
            "schema": "pharma.workspace-comparison-export.v1",
            "export_event_id": event_id,
            "comparison_set_id": set_id,
            "comparison_set_name": set_name,
            "comparison_set_version": set_version,
            "generated_at": generated_at.isoformat(),
            "policy_version": policy_version,
            "attribution": attribution,
        }
        if export_format == "json":
            return _canonical_bytes({**metadata, "records": records}) + b"\n"
        if export_format == "csv":
            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for record in records:
                writer.writerow({field: _tabular_value(record.get(field)) for field in fields})
            return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")
        if export_format != "xlsx":
            raise WorkspaceExportDenied("Unsupported workspace export format")
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True, "constant_memory": False})
        workbook.set_properties({"created": generated_at, "modified": generated_at, "comments": attribution})
        data_sheet = workbook.add_worksheet("Comparison")
        for column, field in enumerate(fields):
            data_sheet.write_string(0, column, field)
        for row_index, record in enumerate(records, start=1):
            for column, field in enumerate(fields):
                value = record.get(field)
                if isinstance(value, int | float) and not isinstance(value, bool):
                    data_sheet.write_number(row_index, column, value)
                else:
                    data_sheet.write_string(row_index, column, _tabular_value(value))
        metadata_sheet = workbook.add_worksheet("Metadata")
        for row_index, (key, value) in enumerate(metadata.items()):
            metadata_sheet.write_string(row_index, 0, key)
            metadata_sheet.write_string(row_index, 1, str(value))
        workbook.close()
        return output.getvalue()

    @staticmethod
    def _encode_domain(
        export_format: str,
        fields: list[str],
        records: list[dict[str, Any]],
        metadata: dict[str, Any],
    ) -> bytes:
        if export_format == "json":
            return _canonical_bytes({**metadata, "records": records}) + b"\n"
        if export_format == "csv":
            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for record in records:
                writer.writerow({field: _tabular_value(record.get(field)) for field in fields})
            return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")
        if export_format != "xlsx":
            raise WorkspaceExportDenied("Unsupported workspace export format")
        generated_at = datetime.fromisoformat(str(metadata["generated_at"]))
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True, "constant_memory": False})
        workbook.set_properties(
            {"created": generated_at, "modified": generated_at, "comments": str(metadata["attribution"])}
        )
        data_sheet = workbook.add_worksheet("Results")
        for column, field in enumerate(fields):
            data_sheet.write_string(0, column, field)
        for row_index, record in enumerate(records, start=1):
            for column, field in enumerate(fields):
                value = record.get(field)
                if isinstance(value, int | float) and not isinstance(value, bool):
                    data_sheet.write_number(row_index, column, value)
                else:
                    data_sheet.write_string(row_index, column, _tabular_value(value))
        metadata_sheet = workbook.add_worksheet("Metadata")
        for row_index, (key, value) in enumerate(metadata.items()):
            metadata_sheet.write_string(row_index, 0, key)
            metadata_sheet.write_string(row_index, 1, _tabular_value(value))
        workbook.close()
        return output.getvalue()

    def _event_for_key(self, idempotency_key: str) -> WorkspaceExportEvent | None:
        return self.session.scalar(
            select(WorkspaceExportEvent).where(
                WorkspaceExportEvent.tenant_id == self.tenant_id,
                WorkspaceExportEvent.requested_by_user_id == self.user_id,
                WorkspaceExportEvent.idempotency_key == idempotency_key,
            )
        )

    @staticmethod
    def _validated_policy_document(command: WorkspaceExportPolicyUpsert) -> dict[str, Any]:
        fields = set(command.allowed_fields)
        if not REQUIRED_WORKSPACE_EXPORT_FIELDS.issubset(fields):
            raise WorkspaceExportDenied("Workspace export policy must include stable ID, entity type and name")
        if not fields.issubset(WORKSPACE_EXPORT_POLICY_FIELDS):
            raise WorkspaceExportDenied("Workspace export policy contains unsupported fields")
        if not set(command.allowed_formats).issubset(WORKSPACE_EXPORT_FORMATS):
            raise WorkspaceExportDenied("Workspace export policy contains unsupported formats")
        return {
            "schema_version": "1.0",
            "policy_version": command.policy_version,
            "enabled": command.enabled,
            "allowed_formats": command.allowed_formats,
            "allowed_fields": command.allowed_fields,
            "max_records_per_export": command.max_records_per_export,
            "attribution": command.attribution,
        }

    @staticmethod
    def _policy_document(policy: WorkspaceExportPolicy) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "policy_version": policy.policy_version,
            "enabled": policy.enabled,
            "allowed_formats": policy.allowed_formats,
            "allowed_fields": policy.allowed_fields,
            "max_records_per_export": policy.max_records_per_export,
            "attribution": policy.attribution,
        }

    def _audit(self, resource_id: str, action: str, details: dict[str, object]) -> None:
        self.session.add(
            AuditEvent(
                tenant_id=self.tenant_id,
                actor_type="user",
                actor_id=self.user_id,
                action=action,
                resource_type="workspace_export",
                resource_id=resource_id,
                outcome="success",
                request_id=str(uuid.uuid4()),
                details=details,
            )
        )


def _record_value(field: str, member: dict[str, object], index: int) -> Any:
    if field == "position":
        return index + 1
    entity = member.get("entity")
    if not isinstance(entity, dict):
        raise WorkspaceExportConflict("Comparison member has an invalid entity snapshot")
    return entity.get(field)


def _tabular_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    rendered = str(value)
    if rendered.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{rendered}"
    return rendered


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _utc_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
