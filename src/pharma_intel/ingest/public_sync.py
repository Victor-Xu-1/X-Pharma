from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pharma_intel.ingest.connectors import ConnectorConfigurationError
from pharma_intel.models import DataSource, DataSourceType


class SourceRoutingRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def document(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ContinuousSyncRule(SourceRoutingRule):
    sync_mode: Literal["snapshot", "continuous"] = "snapshot"


class DateWindowSyncRule(ContinuousSyncRule):
    start_date: date | None = None
    window_days: int = Field(default=31, ge=1, le=366)
    overlap_days: int = Field(default=2, ge=1, le=30)
    reconcile_interval_days: int = Field(default=30, ge=1, le=365)

    @model_validator(mode="after")
    def validate_sync_start(self) -> DateWindowSyncRule:
        if self.sync_mode == "continuous" and self.start_date is None:
            raise ValueError("Continuous date-window synchronization requires an explicit start_date")
        if self.start_date is not None and self.start_date > datetime.now(UTC).date():
            raise ValueError("Synchronization start_date cannot be in the future")
        return self


class PublicSyncState(BaseModel):
    """Durable source checkpoint; never returned to browsers with its page token."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["public-source-sync.v1"] = "public-source-sync.v1"
    configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_kind: Literal["clinicaltrials_gov", "chembl_mechanism"]
    phase: Literal["backfill", "incremental", "reconcile", "full_scan"]
    pending: bool = Field(strict=True)
    cycle_started_at: datetime
    last_completed_at: datetime | None = None
    last_reconciled_at: datetime | None = None
    cycle_processed: int = Field(default=0, ge=0, strict=True)
    after_id: int = Field(default=0, ge=0, le=9_223_372_036_854_775_807, strict=True)
    window_start: date | None = None
    window_end: date | None = None
    cycle_cutoff: date | None = None
    completed_through: date | None = None
    page_token: str | None = Field(default=None, min_length=1, max_length=4096)

    @field_validator("cycle_started_at", "last_completed_at", "last_reconciled_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Public-source checkpoint timestamps require a timezone")
            return value.astimezone(UTC)
        return value

    @field_validator("page_token")
    @classmethod
    def validate_token(cls, value: str | None) -> str | None:
        if value is not None and any(character in value for character in ("\x00", "\r", "\n")):
            raise ValueError("Public-source page token contains invalid characters")
        return value

    @model_validator(mode="after")
    def validate_boundaries(self) -> PublicSyncState:
        if self.source_kind == "clinicaltrials_gov":
            if self.phase == "full_scan" or None in (self.window_start, self.window_end, self.cycle_cutoff):
                raise ValueError("ClinicalTrials.gov checkpoint requires a date window")
            assert self.window_start is not None and self.window_end is not None and self.cycle_cutoff is not None
            if not self.window_start <= self.window_end <= self.cycle_cutoff:
                raise ValueError("Public-source checkpoint has reversed window boundaries")
            if self.after_id:
                raise ValueError("ClinicalTrials.gov checkpoint cannot contain a mechanism key")
        elif self.phase != "full_scan" or any(
            value is not None for value in (self.window_start, self.window_end, self.cycle_cutoff, self.page_token)
        ):
            raise ValueError("ChEMBL checkpoint cannot contain a date window or page token")
        if not self.pending and self.page_token is not None:
            raise ValueError("Completed checkpoint cannot contain a next-page token")
        return self


def sync_configuration_sha256(rule: SourceRoutingRule) -> str:
    return hashlib.sha256(
        json.dumps(rule.document(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def read_sync_state(cursor: dict[str, object], rule: SourceRoutingRule, source_kind: str) -> PublicSyncState | None:
    payload = cursor.get("sync_state")
    if payload is None:
        return None
    try:
        state = PublicSyncState.model_validate(payload)
    except ValueError as exc:
        raise ConnectorConfigurationError("Public-source synchronization checkpoint is invalid") from exc
    if state.source_kind != source_kind or state.configuration_sha256 != sync_configuration_sha256(rule):
        raise ConnectorConfigurationError("Public-source checkpoint does not match source configuration")
    return state


def public_sync_pending(source: DataSource) -> bool:
    if source.source_type not in {DataSourceType.CLINICALTRIALS_GOV, DataSourceType.CHEMBL}:
        return False
    if len(source.routing_rules) != 1 or source.routing_rules[0].get("sync_mode") != "continuous":
        return False
    try:
        state = PublicSyncState.model_validate((source.connector_cursor or {}).get("sync_state"))
    except ValueError:
        return False  # Connector readiness reports the malformed checkpoint and blocks scheduling.
    return state.pending


@dataclass(frozen=True)
class PublicSyncSummary:
    phase: str
    pending: bool
    processed_records: int
    cycle_started_at: datetime
    last_completed_at: datetime | None
    window_start: date | None
    window_end: date | None
    completed_through: date | None


def public_sync_summary(source: DataSource) -> PublicSyncSummary | None:
    if source.source_type not in {DataSourceType.CLINICALTRIALS_GOV, DataSourceType.CHEMBL}:
        return None
    if len(source.routing_rules) != 1 or source.routing_rules[0].get("sync_mode") != "continuous":
        return None
    try:
        state = PublicSyncState.model_validate((source.connector_cursor or {}).get("sync_state"))
    except ValueError:
        return None  # Missing/invalid state is reported by source readiness, never asserted as complete.
    return PublicSyncSummary(
        phase=state.phase,
        pending=state.pending,
        processed_records=state.cycle_processed,
        cycle_started_at=state.cycle_started_at,
        last_completed_at=state.last_completed_at,
        window_start=state.window_start,
        window_end=state.window_end,
        completed_through=state.completed_through,
    )
