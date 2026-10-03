from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pharma_intel.models.enums import (
    DealDirection,
    DealPartyRole,
    DealRightType,
    DealStatus,
    DevelopmentPhase,
    EntityType,
)
from pharma_intel.sorting import (
    MAX_SORT_CRITERIA,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)

from .identity import (
    EntityRead,
)
from .programs import (
    CompetitiveProgramRead,
)
from .query import (
    QueryResultMetadata,
    SortCriterionRead,
    _synchronize_saved_sort,
)
from .types import (
    DEAL_SORT_FIELDS,
    DealSortField,
    SortToken,
)

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
