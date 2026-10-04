from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.ingest.connectors import SourceConnectorRegistry
from pharma_intel.ingest.public_sync import PublicSyncSummary, public_sync_summary
from pharma_intel.licensing import EvidenceLicensePolicy
from pharma_intel.models import DataSource, DataSourceState, TenantDataset

ALLOWED_DATA_CLASSIFICATIONS = frozenset({"public", "internal", "confidential", "restricted"})
UNASSIGNED_OWNERS = frozenset({"unassigned", "migration-unassigned", "unknown", "n/a"})
AUTHORIZATION_SCOPE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{1,119}$")
AUTHORIZATION_EXPIRY_WARNING = timedelta(days=30)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True)
class ReadinessCheck:
    code: str
    status: str
    message: str


@dataclass(frozen=True)
class DataSourceReadiness:
    source_id: str
    configuration_ready: bool
    operational_status: str
    connector_id: str | None
    incremental: bool
    replayable: bool
    delivery_channels: list[str]
    cursor_present: bool
    last_cursor_at: datetime | None
    freshness_age_seconds: int | None
    checks: list[ReadinessCheck]
    sync_status: PublicSyncSummary | None = None

    @property
    def blocking_messages(self) -> list[str]:
        return [check.message for check in self.checks if check.status == "fail"]


class SourceReadinessService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        tenant_id: str,
        connector_registry: SourceConnectorRegistry | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.tenant_id = tenant_id
        self.connector_registry = connector_registry or SourceConnectorRegistry(settings)

    def evaluate(self, source: DataSource, *, now: datetime | None = None) -> DataSourceReadiness:
        timestamp = _as_utc(now or datetime.now(UTC))
        checks: list[ReadinessCheck] = []
        owner = source.owner.strip()
        if not owner or owner.casefold() in UNASSIGNED_OWNERS:
            checks.append(ReadinessCheck("owner", "fail", "A named accountable data owner is required"))
        else:
            checks.append(ReadinessCheck("owner", "pass", f"Accountable owner: {owner}"))

        invalid_scopes = [
            scope
            for scope in source.authorization_scopes
            if not isinstance(scope, str) or not AUTHORIZATION_SCOPE_PATTERN.fullmatch(scope)
        ]
        if not source.authorization_scopes or invalid_scopes:
            checks.append(
                ReadinessCheck(
                    "authorization_scopes",
                    "fail",
                    "At least one valid source authorization scope is required",
                )
            )
        else:
            checks.append(
                ReadinessCheck(
                    "authorization_scopes",
                    "pass",
                    f"{len(source.authorization_scopes)} authorization scope(s) recorded",
                )
            )

        valid_from = source.authorization_valid_from
        valid_until = source.authorization_valid_until
        if valid_from is None:
            checks.append(
                ReadinessCheck("authorization_window", "fail", "Source authorization effective time is required")
            )
        else:
            effective_at = _as_utc(valid_from)
            expires_at = _as_utc(valid_until) if valid_until is not None else None
            if expires_at is not None and expires_at <= effective_at:
                checks.append(
                    ReadinessCheck("authorization_window", "fail", "Source authorization time window is invalid")
                )
            elif timestamp < effective_at:
                checks.append(
                    ReadinessCheck(
                        "authorization_not_yet_valid",
                        "fail",
                        f"Source authorization is not effective until {effective_at.isoformat()}",
                    )
                )
            elif expires_at is not None and timestamp >= expires_at:
                checks.append(
                    ReadinessCheck(
                        "authorization_expired",
                        "fail",
                        f"Source authorization expired at {expires_at.isoformat()}",
                    )
                )
            elif expires_at is not None and expires_at - timestamp <= AUTHORIZATION_EXPIRY_WARNING:
                checks.append(
                    ReadinessCheck(
                        "authorization_expiring",
                        "warn",
                        f"Source authorization expires at {expires_at.isoformat()}",
                    )
                )
            else:
                message = (
                    "Source authorization is effective without an end date"
                    if expires_at is None
                    else f"Source authorization is effective until {expires_at.isoformat()}"
                )
                checks.append(ReadinessCheck("authorization_window", "pass", message))

        if source.data_classification not in ALLOWED_DATA_CLASSIFICATIONS:
            checks.append(ReadinessCheck("data_classification", "fail", "Data classification is invalid"))
        else:
            checks.append(
                ReadinessCheck(
                    "data_classification",
                    "pass",
                    f"Data classification: {source.data_classification}",
                )
            )

        connector_id: str | None = None
        incremental = False
        replayable = False
        try:
            connector = self.connector_registry.get(source.source_type)
        except ValueError as exc:
            checks.append(ReadinessCheck("connector", "fail", str(exc)))
        else:
            capabilities = connector.capabilities
            connector_id = capabilities.connector_id
            incremental = capabilities.incremental
            replayable = capabilities.replayable
            configuration_errors = connector.validate_configuration(source)
            if configuration_errors:
                checks.extend(
                    ReadinessCheck("connector_configuration", "fail", error) for error in configuration_errors
                )
            else:
                checks.append(ReadinessCheck("connector", "pass", f"Connector {connector_id} is configured"))
            if capabilities.credentials_required and not source.credential_ref:
                checks.append(
                    ReadinessCheck("credential_ref", "fail", "This connector requires a credential reference")
                )
            else:
                message = (
                    "Credential reference configured"
                    if source.credential_ref
                    else "Connector uses no stored credential"
                )
                checks.append(ReadinessCheck("credential_ref", "pass", message))

        dataset = self.session.scalar(
            select(TenantDataset).where(
                TenantDataset.tenant_id == self.tenant_id,
                TenantDataset.dataset_key == source.dataset_key,
            )
        )
        delivery_channels: list[str] = []
        if dataset is None:
            checks.append(ReadinessCheck("dataset", "fail", "Target dataset is not registered for this tenant"))
        elif not dataset.active:
            checks.append(ReadinessCheck("dataset", "fail", "Target dataset is disabled"))
        else:
            checks.append(ReadinessCheck("dataset", "pass", f"Target dataset: {dataset.dataset_key}"))
            try:
                policy = EvidenceLicensePolicy.model_validate(dataset.license_policy)
            except ValidationError:
                checks.append(ReadinessCheck("license_policy", "fail", "Target dataset license policy is invalid"))
            else:
                if policy.permits("web", timestamp):
                    delivery_channels.append("web")
                if policy.permits("mcp", timestamp):
                    delivery_channels.append("mcp")
                if not delivery_channels:
                    checks.append(
                        ReadinessCheck("license_policy", "fail", "Target dataset license is not currently deliverable")
                    )
                else:
                    checks.append(
                        ReadinessCheck(
                            "license_policy",
                            "pass",
                            f"License {policy.license_id}/{policy.policy_version} is current",
                        )
                    )
                    missing_channels = sorted({"web", "mcp"} - set(delivery_channels))
                    if missing_channels:
                        checks.append(
                            ReadinessCheck(
                                "delivery_channels",
                                "warn",
                                f"License excludes delivery channel(s): {', '.join(missing_channels)}",
                            )
                        )
                    else:
                        checks.append(
                            ReadinessCheck("delivery_channels", "pass", "License permits Web and MCP delivery")
                        )

        freshness_age_seconds: int | None = None
        if source.last_success_at is None:
            checks.append(ReadinessCheck("freshness", "warn", "Source has not completed its first scan"))
        else:
            last_success = source.last_success_at
            if last_success.tzinfo is None:
                last_success = last_success.replace(tzinfo=UTC)
            freshness_age_seconds = max(0, int((timestamp - last_success).total_seconds()))
            if freshness_age_seconds > source.expected_freshness_seconds:
                checks.append(
                    ReadinessCheck(
                        "freshness",
                        "warn",
                        f"Source is stale by policy ({freshness_age_seconds}s old)",
                    )
                )
            else:
                checks.append(ReadinessCheck("freshness", "pass", "Source is within its freshness objective"))

        configuration_ready = not any(check.status == "fail" for check in checks)
        sync_status = public_sync_summary(source)
        if not configuration_ready:
            operational_status = "blocked"
        elif source.state == DataSourceState.DISABLED:
            operational_status = "disabled"
        elif source.state == DataSourceState.PAUSED:
            operational_status = "paused"
        elif source.state == DataSourceState.UNAVAILABLE:
            operational_status = "unavailable"
        elif source.last_success_at is None or (
            len(source.routing_rules) == 1
            and source.routing_rules[0].get("sync_mode") == "continuous"
            and sync_status is None
        ):
            operational_status = "pending"
        elif sync_status is not None and sync_status.pending:
            operational_status = "syncing"
        elif freshness_age_seconds is not None and freshness_age_seconds > source.expected_freshness_seconds:
            operational_status = "stale"
        else:
            operational_status = "ready"

        return DataSourceReadiness(
            source_id=source.id,
            configuration_ready=configuration_ready,
            operational_status=operational_status,
            connector_id=connector_id,
            incremental=incremental,
            replayable=replayable,
            delivery_channels=delivery_channels,
            cursor_present=bool(source.connector_cursor),
            last_cursor_at=source.last_cursor_at,
            freshness_age_seconds=freshness_age_seconds,
            checks=checks,
            sync_status=sync_status,
        )
