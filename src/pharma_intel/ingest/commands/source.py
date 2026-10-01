from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.ingest.commands.errors import IngestionCommandError
from pharma_intel.ingest.connectors import SourceConnectorRegistry
from pharma_intel.licensing import EvidenceLicensePolicy
from pharma_intel.models import AuditEvent, DataSource, DataSourceState, DataSourceType, SourceAsset, TenantDataset
from pharma_intel.schemas import DataSourceCreate, DataSourceRead, DataSourceStateUpdate, DataSourceUpdate
from pharma_intel.security import Principal


def _normalized_source_root(source_type: DataSourceType, root_uri: str, *, settings: Settings) -> str:
    try:
        connector = SourceConnectorRegistry(settings).get(source_type)
        return connector.normalize_root_uri(root_uri)
    except ValueError as exc:
        raise IngestionCommandError(status_code=422, detail=str(exc)) from exc


def _validate_source_connector(source: DataSource, *, settings: Settings) -> None:
    try:
        connector = SourceConnectorRegistry(settings).get(source.source_type)
        errors = connector.validate_configuration(source)
    except ValueError as exc:
        raise IngestionCommandError(status_code=422, detail=str(exc)) from exc
    if errors:
        raise IngestionCommandError(status_code=422, detail=errors[0])


def _validate_source_authorization_window(source: DataSource) -> None:
    valid_from = source.authorization_valid_from
    if valid_from is None:
        raise IngestionCommandError(status_code=422, detail="Source authorization effective time is required")
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
        raise IngestionCommandError(status_code=422, detail="Authorization end must be later than its effective time")


def _add_data_source_audit(
    session: Session, request_id: str, principal: Principal, source: DataSource, *, action: str, details: dict[str, Any]
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
            request_id=request_id,
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
        raise IngestionCommandError(status_code=422, detail="Glob patterns cannot be empty or contain NUL bytes")


def _require_ingestion_dataset(session: Session, tenant_id: str, dataset_key: str) -> TenantDataset:
    dataset = session.scalar(
        select(TenantDataset).where(
            TenantDataset.tenant_id == tenant_id,
            TenantDataset.dataset_key == dataset_key,
        )
    )
    if dataset is None:
        raise IngestionCommandError(status_code=422, detail="Target dataset is not registered for this tenant")
    if not dataset.active:
        raise IngestionCommandError(status_code=422, detail="Target dataset is disabled")
    try:
        policy = EvidenceLicensePolicy.model_validate(dataset.license_policy)
    except ValueError as exc:
        raise IngestionCommandError(status_code=422, detail="Target dataset license policy is invalid") from exc
    now = datetime.now(UTC)
    if not policy.permits("web", now) and not policy.permits("mcp", now):
        raise IngestionCommandError(status_code=422, detail="Target dataset license is not currently deliverable")
    return dataset


def create_data_source(
    payload: DataSourceCreate, request_id: str, principal: Principal, session: Session, *, settings: Settings
) -> DataSourceRead:
    principal.require("ingestion:manage")
    root = _normalized_source_root(payload.source_type, payload.root_uri, settings=settings)
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
    _validate_source_connector(source, settings=settings)
    _validate_source_authorization_window(source)
    session.add(source)
    try:
        session.flush()
        _add_data_source_audit(
            session,
            request_id,
            principal,
            source,
            action="data_source.create",
            details={"config_version": source.config_version},
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise IngestionCommandError(
            status_code=409, detail="A data source with this name or root already exists"
        ) from exc
    return DataSourceRead.model_validate(source)


def update_data_source(
    data_source_id: str,
    payload: DataSourceUpdate,
    request_id: str,
    principal: Principal,
    session: Session,
    *,
    settings: Settings,
) -> DataSourceRead:
    principal.require("ingestion:manage")
    source = session.scalar(
        select(DataSource).where(
            DataSource.id == data_source_id,
            DataSource.tenant_id == principal.tenant_id,
        )
    )
    if source is None:
        raise IngestionCommandError(status_code=404, detail="Data source not found")

    values = payload.model_dump(exclude_unset=True)
    if "routing_rules" in payload.model_fields_set:
        values["routing_rules"] = [rule.document() for rule in payload.routing_rules or []]
    if "root_uri" in values and values["root_uri"] is not None:
        values["root_uri"] = _normalized_source_root(source.source_type, str(values["root_uri"]), settings=settings)
    if "dataset_key" in values and values["dataset_key"] is not None:
        _require_ingestion_dataset(session, principal.tenant_id, str(values["dataset_key"]))
    include_globs = values.get("include_globs", source.include_globs)
    exclude_globs = values.get("exclude_globs", source.exclude_globs)
    _validate_globs(include_globs, exclude_globs)
    prospective_source = _prospective_source(source, values)
    _validate_source_connector(prospective_source, settings=settings)
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
            raise IngestionCommandError(
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
        request_id,
        principal,
        source,
        action=audit_action,
        details={"changed_fields": changed_fields, "config_version": source.config_version},
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise IngestionCommandError(
            status_code=409, detail="A data source with this name or root already exists"
        ) from exc
    return DataSourceRead.model_validate(source)


def update_data_source_state(
    data_source_id: str, payload: DataSourceStateUpdate, request_id: str, principal: Principal, session: Session
) -> DataSourceRead:
    principal.require("ingestion:manage")
    source = session.scalar(
        select(DataSource).where(
            DataSource.id == data_source_id,
            DataSource.tenant_id == principal.tenant_id,
        )
    )
    if source is None:
        raise IngestionCommandError(status_code=404, detail="Data source not found")
    previous_state = source.state
    source.state = payload.state
    source.config_version += 1
    _add_data_source_audit(
        session,
        request_id,
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
