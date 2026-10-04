from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request, status
from sqlalchemy import select

from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.ingest.commands.scan import trigger_data_source_scan as command_trigger_data_source_scan
from pharma_intel.ingest.commands.source import create_data_source as command_create_data_source
from pharma_intel.ingest.commands.source import update_data_source as command_update_data_source
from pharma_intel.ingest.commands.source import update_data_source_state as command_update_data_source_state
from pharma_intel.ingest.readiness import SourceReadinessService
from pharma_intel.ingest.scanner import ASSET_ONLY_EXTENSIONS, PARSEABLE_EXTENSIONS
from pharma_intel.licensing import DeliveryChannel, EvidenceLicensePolicy
from pharma_intel.models import DataSource, TenantDataset
from pharma_intel.schemas import (
    DataSourceCreate,
    DataSourceDatasetRead,
    DataSourceRead,
    DataSourceReadinessRead,
    DataSourceStateUpdate,
    DataSourceUpdate,
    IngestionCapabilitiesRead,
    IngestionScanAcceptedRead,
)

router = APIRouter()


@router.get("/api/v1/admin/data-sources", response_model=list[DataSourceRead], tags=["data-factory"])
def list_data_sources(principal: PrincipalDep, session: SessionDep) -> list[DataSourceRead]:
    principal.require("ingestion:read")
    sources = session.scalars(
        select(DataSource).where(DataSource.tenant_id == principal.tenant_id).order_by(DataSource.name)
    )
    return [DataSourceRead.model_validate(source) for source in sources]


@router.get(
    "/api/v1/admin/ingestion-capabilities",
    response_model=IngestionCapabilitiesRead,
    tags=["data-factory"],
)
def get_ingestion_capabilities(principal: PrincipalDep) -> IngestionCapabilitiesRead:
    principal.require("ingestion:read")
    settings = runtime.get_settings()
    return IngestionCapabilitiesRead(
        automatic_scheduling_enabled=settings.temporal_enabled and settings.temporal_scheduler_enabled,
        durable_workflows_enabled=settings.temporal_enabled and settings.temporal_worker_enabled,
        isolated_parser_enabled=settings.parser_backend == "service",
        malware_scanning_enabled=settings.malware_scan_enabled,
        ai_governance_enabled=settings.ai_governance_enabled,
        deterministic_governance_enabled=settings.deterministic_governance_enabled,
        ai_model_configured=bool(settings.ai_base_url and settings.ai_api_key and settings.ai_model),
        ai_model=settings.ai_model or None,
        ai_auto_publish_threshold=settings.ai_auto_publish_threshold,
        allowed_folder_roots=sorted(str(root) for root in settings.source_roots),
        parseable_extensions=sorted(PARSEABLE_EXTENSIONS),
        asset_only_extensions=sorted(ASSET_ONLY_EXTENSIONS),
    )


@router.get(
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


@router.get(
    "/api/v1/admin/data-source-readiness",
    response_model=list[DataSourceReadinessRead],
    tags=["data-factory"],
)
def list_data_source_readiness(principal: PrincipalDep, session: SessionDep) -> list[DataSourceReadinessRead]:
    principal.require("ingestion:read")
    settings = runtime.get_settings()
    service = SourceReadinessService(session, settings, principal.tenant_id)
    sources = session.scalars(
        select(DataSource).where(DataSource.tenant_id == principal.tenant_id).order_by(DataSource.name)
    )
    return [DataSourceReadinessRead.model_validate(service.evaluate(source)) for source in sources]


@router.post(
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
    return command_create_data_source(
        payload, request.state.request_id, principal, session, settings=runtime.get_settings()
    )


@router.patch(
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
    return command_update_data_source(
        data_source_id, payload, request.state.request_id, principal, session, settings=runtime.get_settings()
    )


@router.patch(
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
    return command_update_data_source_state(data_source_id, payload, request.state.request_id, principal, session)


@router.post(
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
    return await command_trigger_data_source_scan(data_source_id, principal, session, settings=runtime.get_settings())
