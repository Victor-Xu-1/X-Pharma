from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pharma_intel.ingest.readiness import AUTHORIZATION_SCOPE_PATTERN
from pharma_intel.models.enums import (
    DataSourceState,
    DataSourceType,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


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


class DataSourceStateUpdate(BaseModel):
    state: Literal[DataSourceState.ACTIVE, DataSourceState.PAUSED, DataSourceState.DISABLED]
