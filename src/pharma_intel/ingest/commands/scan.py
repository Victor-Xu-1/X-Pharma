from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from pharma_intel.config import Settings
from pharma_intel.ingest.commands.errors import IngestionCommandError
from pharma_intel.ingest.contracts import ScanInput
from pharma_intel.ingest.readiness import SourceReadinessService
from pharma_intel.ingest.workflows import DataSourceIngestionWorkflow
from pharma_intel.models import DataSource, DataSourceState
from pharma_intel.schemas import IngestionScanAcceptedRead
from pharma_intel.security import Principal


async def _start_data_source_scan(
    source: DataSource,
    principal: Principal,
    session: Session,
    *,
    replayed_from_run_id: str | None = None,
    run_correlation_id: str | None = None,
    settings: Settings,
) -> IngestionScanAcceptedRead:
    if source.state in {DataSourceState.PAUSED, DataSourceState.DISABLED}:
        raise IngestionCommandError(status_code=409, detail=f"Data source is {source.state.value}")
    readiness = SourceReadinessService(session, settings, principal.tenant_id).evaluate(source)
    if not readiness.configuration_ready:
        raise IngestionCommandError(
            status_code=409,
            detail={"code": "source_governance_blocked", "checks": readiness.blocking_messages},
        )
    if not settings.temporal_enabled:
        raise IngestionCommandError(status_code=503, detail="Durable workflow service is not enabled")
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
        raise IngestionCommandError(status_code=409, detail="A scan is already running for this data source") from exc
    except Exception as exc:
        raise IngestionCommandError(status_code=503, detail="Durable workflow service is unavailable") from exc
    return IngestionScanAcceptedRead(
        workflow_id=workflow_id,
        ingestion_run_id=run_correlation_id,
        status="accepted",
        replayed_from_run_id=replayed_from_run_id,
    )


async def trigger_data_source_scan(
    data_source_id: str, principal: Principal, session: Session, *, settings: Settings
) -> IngestionScanAcceptedRead:
    principal.require("ingestion:manage")
    source = session.scalar(
        select(DataSource).where(
            DataSource.id == data_source_id,
            DataSource.tenant_id == principal.tenant_id,
        )
    )
    if source is None:
        raise IngestionCommandError(status_code=404, detail="Data source not found")
    return await _start_data_source_scan(source, principal, session, settings=settings)
