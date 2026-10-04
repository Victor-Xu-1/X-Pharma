from __future__ import annotations

import asyncio
import signal
import threading
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.worker import Worker

from pharma_intel.commercial.export_activities import execute_export_activity, fail_export_activity
from pharma_intel.commercial.export_contracts import ExportInput
from pharma_intel.commercial.export_workflows import GovernedDataExportWorkflow
from pharma_intel.config import Settings, get_settings
from pharma_intel.db import get_session_factory, set_tenant_context
from pharma_intel.governance.service import recover_stale_extraction_runs
from pharma_intel.ingest.activities import (
    process_version_activity,
    scan_source_activity,
)
from pharma_intel.ingest.contracts import ScanInput
from pharma_intel.ingest.public_sync import public_sync_pending
from pharma_intel.ingest.readiness import SourceReadinessService
from pharma_intel.ingest.run_reconciliation import reconcile_stale_ingestion_runs
from pharma_intel.ingest.workflows import DataSourceIngestionWorkflow, SourceVersionReprocessWorkflow
from pharma_intel.models import DataExportJob, DataSource, Tenant
from pharma_intel.models import DataSourceState as DataSourceState
from pharma_intel.runtime_heartbeat import RuntimeHeartbeat
from pharma_intel.telemetry import initialize_telemetry

logger = structlog.get_logger(__name__)


async def _connect_temporal(settings: Settings) -> Client:
    for attempt in range(1, settings.temporal_connect_attempts + 1):
        try:
            client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
        except Exception as exc:
            if attempt == settings.temporal_connect_attempts:
                logger.error(
                    "temporal_connect_exhausted",
                    address=settings.temporal_address,
                    attempts=attempt,
                    error=str(exc),
                )
                raise
            delay = min(
                settings.temporal_connect_backoff_seconds * (2 ** (attempt - 1)),
                settings.temporal_connect_max_backoff_seconds,
            )
            logger.warning(
                "temporal_connect_retry",
                address=settings.temporal_address,
                attempt=attempt,
                next_attempt=attempt + 1,
                delay_seconds=delay,
                error=str(exc),
            )
            await asyncio.sleep(delay)
        else:
            if attempt > 1:
                logger.info("temporal_connect_recovered", address=settings.temporal_address, attempt=attempt)
            return client
    raise RuntimeError("Temporal connection attempts exhausted")


def _recover_stale_runs(settings: Settings, now: datetime) -> int:
    recovered_runs = 0
    with get_session_factory()() as identity_session:
        tenant_ids = list(identity_session.scalars(select(Tenant.id).where(Tenant.active.is_(True))))
    for tenant_id in tenant_ids:
        with get_session_factory()() as session:
            recovered_runs += recover_stale_extraction_runs(session, settings, tenant_id, now=now)
    return recovered_runs


def _source_scan_interval(settings: Settings, source: DataSource) -> int:
    """Return the next automatic scan delay for a source.

    A source that has failed upstream should be retried with a bounded backoff,
    rather than waiting for its normal freshness interval (which can be a day)
    or being retried on every scheduler poll. Successful sources retain their
    configured cadence.
    """
    scan_interval = int(source.scan_interval_seconds)
    failure_count = int(source.consecutive_failures)
    if source.state != DataSourceState.UNAVAILABLE or failure_count <= 0:
        if public_sync_pending(source):
            return min(scan_interval, settings.public_sync_catchup_interval_seconds)
        return scan_interval
    exponent = min(failure_count - 1, 20)
    backoff_seconds = int(settings.source_retry_base_seconds) * (2**exponent)
    return int(min(scan_interval, int(settings.source_retry_max_seconds), backoff_seconds))


def _collect_due_work(settings: Settings, now: datetime) -> tuple[list[tuple[str, str]], list[tuple[str, str, str]]]:
    due: list[tuple[str, str]] = []
    export_due: list[tuple[str, str, str]] = []
    with get_session_factory()() as identity_session:
        tenant_ids = list(identity_session.scalars(select(Tenant.id).where(Tenant.active.is_(True))))
    for tenant_id in tenant_ids:
        with get_session_factory()() as session:
            set_tenant_context(session, tenant_id)
            sources = session.scalars(
                select(DataSource).where(
                    DataSource.tenant_id == tenant_id,
                    DataSource.state.in_([DataSourceState.ACTIVE, DataSourceState.UNAVAILABLE]),
                )
            )
            readiness_service = SourceReadinessService(session, settings, tenant_id)
            for source in sources:
                readiness = readiness_service.evaluate(source, now=now)
                if not readiness.configuration_ready:
                    logger.debug(
                        "source_schedule_blocked",
                        source_id=source.id,
                        checks=readiness.blocking_messages,
                    )
                    continue
                if source.last_scanned_at is None or (
                    now - source.last_scanned_at
                ).total_seconds() >= _source_scan_interval(settings, source):
                    due.append((tenant_id, source.id))
            exports = session.scalars(
                select(DataExportJob).where(
                    DataExportJob.tenant_id == tenant_id,
                    DataExportJob.state == "queued",
                    DataExportJob.reservation_id.is_not(None),
                )
            )
            export_due.extend((tenant_id, job.id, job.workflow_id) for job in exports)
    return due, export_due


async def _run_reconciliation_iteration(client: Client, settings: Settings, now: datetime) -> None:
    recovered_runs = _recover_stale_runs(settings, now)
    if recovered_runs:
        logger.warning("stale_extraction_runs_recovered", count=recovered_runs)
    reconciliation = await reconcile_stale_ingestion_runs(client, get_session_factory(), now=now)
    if reconciliation.reconciled or reconciliation.failed:
        logger.warning(
            "stale_ingestion_runs_reconciled",
            scanned=reconciliation.scanned,
            reconciled=reconciliation.reconciled,
            still_running=reconciliation.still_running,
            failed=reconciliation.failed,
        )


async def _reconciliation_maintenance(client: Client, settings: Settings) -> None:
    while True:
        await _run_reconciliation_iteration(client, settings, datetime.now(UTC))
        await asyncio.sleep(settings.temporal_scheduler_poll_seconds)


async def _run_scheduler_iteration(client: Client, settings: Settings, now: datetime) -> None:
    await _run_reconciliation_iteration(client, settings, now)
    due, export_due = _collect_due_work(settings, now)
    for tenant_id, source_id in due:
        execution_id = f"source-ingest-{source_id}"
        run_correlation_id = f"{execution_id}-{uuid.uuid4()}"
        try:
            await client.start_workflow(
                DataSourceIngestionWorkflow.run,
                ScanInput(tenant_id, source_id, run_correlation_id),
                id=execution_id,
                task_queue=settings.temporal_task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
            )
        except WorkflowAlreadyStartedError:
            continue
        except Exception as exc:
            logger.warning("workflow_schedule_failed", source_id=source_id, error=str(exc))
    for tenant_id, job_id, workflow_id in export_due:
        try:
            await client.start_workflow(
                GovernedDataExportWorkflow.run,
                ExportInput(tenant_id, job_id),
                id=workflow_id,
                task_queue=settings.temporal_task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            )
        except WorkflowAlreadyStartedError:
            continue
        except Exception as exc:
            logger.warning("export_workflow_schedule_failed", job_id=job_id, error=str(exc))


async def _scheduler(client: Client) -> None:
    settings = get_settings()
    while True:
        await _run_scheduler_iteration(client, settings, datetime.now(UTC))
        await asyncio.sleep(settings.temporal_scheduler_poll_seconds)


async def _maintain_heartbeat(heartbeat: RuntimeHeartbeat) -> None:
    while True:
        heartbeat.beat()
        await asyncio.sleep(5)


async def _run(stopping: threading.Event | None = None) -> None:
    settings = get_settings()
    if not settings.temporal_enabled:
        raise RuntimeError("TEMPORAL_ENABLED must be true to start the durable ingestion worker")
    if not settings.temporal_worker_enabled and not settings.temporal_scheduler_enabled:
        raise RuntimeError("At least one Temporal process role must be enabled")
    client = await _connect_temporal(settings)
    role_tasks: list[asyncio.Task[None]] = []
    if settings.temporal_worker_enabled:
        worker = Worker(
            client,
            task_queue=settings.temporal_task_queue,
            workflows=[DataSourceIngestionWorkflow, SourceVersionReprocessWorkflow, GovernedDataExportWorkflow],
            activities=[
                scan_source_activity,
                process_version_activity,
                execute_export_activity,
                fail_export_activity,
            ],
            max_concurrent_activities=settings.temporal_max_concurrent_activities,
        )
        role_tasks.append(asyncio.create_task(worker.run(), name="temporal-worker"))
        if not settings.temporal_scheduler_enabled:
            role_tasks.append(
                asyncio.create_task(
                    _reconciliation_maintenance(client, settings),
                    name="ingestion-run-reconciliation",
                )
            )
    if settings.temporal_scheduler_enabled:
        role_tasks.append(asyncio.create_task(_scheduler(client), name="source-scheduler"))
    default_service = (
        "data-factory"
        if settings.temporal_worker_enabled and settings.temporal_scheduler_enabled
        else "ingest-worker"
        if settings.temporal_worker_enabled
        else "ingest-scheduler"
    )
    heartbeat = RuntimeHeartbeat(default_service)
    heartbeat_task: asyncio.Task[None] | None = None
    stopping_task: asyncio.Task[bool] | None = None
    try:
        with heartbeat:
            heartbeat_task = asyncio.create_task(_maintain_heartbeat(heartbeat), name="runtime-heartbeat")
            if stopping is not None:
                stopping_task = asyncio.create_task(asyncio.to_thread(stopping.wait), name="shutdown-request")
            done, _pending = await asyncio.wait(
                [*role_tasks, heartbeat_task, *([stopping_task] if stopping_task is not None else [])],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                if task is stopping_task and stopping is not None and stopping.is_set():
                    return
                if task.cancelled():
                    raise RuntimeError(f"Temporal process role was cancelled unexpectedly: {task.get_name()}")
                error = task.exception()
                if error is not None:
                    raise error
                raise RuntimeError(f"Temporal process role exited unexpectedly: {task.get_name()}")
    finally:
        if stopping is not None:
            stopping.set()
        tasks = [
            *role_tasks,
            *([heartbeat_task] if heartbeat_task is not None else []),
            *([stopping_task] if stopping_task is not None else []),
        ]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def serve(stopping: threading.Event) -> None:
    asyncio.run(_run(stopping))


def run() -> None:
    initialize_telemetry("pharma-data-factory")
    stopping = threading.Event()

    def stop(_signum: int, _frame: object) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    serve(stopping)
