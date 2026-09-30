from __future__ import annotations

import os
import queue
import signal
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import structlog

from pharma_intel.commercial.billing_worker import serve as serve_billing
from pharma_intel.config import Settings, get_settings
from pharma_intel.ingest.temporal_worker import serve as serve_ingestion
from pharma_intel.job_roles import (
    enabled_job_role_specs,
)
from pharma_intel.job_roles import (
    ingestion_heartbeat_service as ingestion_heartbeat_service,
)
from pharma_intel.monitoring.worker import serve as serve_monitoring
from pharma_intel.runtime_heartbeat import HEARTBEAT_SERVICE_ENV
from pharma_intel.search.maintenance_worker import serve as serve_search_maintenance
from pharma_intel.search.worker import serve as serve_search_projector
from pharma_intel.telemetry import initialize_telemetry

logger = structlog.get_logger(__name__)
JobTarget = Callable[[threading.Event], None]


@dataclass(frozen=True)
class JobRole:
    name: str
    heartbeat_service: str
    heartbeat_max_age_seconds: float
    target: JobTarget


@dataclass(frozen=True)
class JobRoleExit:
    name: str
    error: BaseException | None


def enabled_job_roles(settings: Settings) -> tuple[JobRole, ...]:
    targets = {
        "ingestion": serve_ingestion,
        "search-projector": serve_search_projector,
        "search-maintenance": serve_search_maintenance,
        "monitoring": serve_monitoring,
        "billing": serve_billing,
    }
    return tuple(
        JobRole(
            spec.name,
            spec.heartbeat_service,
            spec.heartbeat_max_age_seconds,
            targets[spec.name],
        )
        for spec in enabled_job_role_specs(settings)
    )


def _run_role(role: JobRole, stopping: threading.Event, exits: queue.Queue[JobRoleExit]) -> None:
    try:
        role.target(stopping)
    except BaseException as exc:
        exits.put(JobRoleExit(role.name, exc))
    else:
        exits.put(JobRoleExit(role.name, None))


def supervise_jobs(
    roles: Sequence[JobRole],
    stopping: threading.Event,
    *,
    poll_seconds: float,
    shutdown_timeout_seconds: float,
) -> None:
    if not roles:
        raise RuntimeError("At least one unified jobs role must be enabled")
    names = [role.name for role in roles]
    if len(names) != len(set(names)):
        raise RuntimeError("Unified jobs role names must be unique")

    exits: queue.Queue[JobRoleExit] = queue.Queue()
    threads = [
        threading.Thread(
            target=_run_role,
            args=(role, stopping, exits),
            name=f"pharma-jobs-{role.name}",
            daemon=True,
        )
        for role in roles
    ]
    for thread in threads:
        thread.start()
    logger.info("unified_jobs_started", roles=names, process_id=os.getpid())

    unexpected_exit: JobRoleExit | None = None
    try:
        while not stopping.is_set():
            try:
                role_exit = exits.get(timeout=poll_seconds)
            except queue.Empty:
                continue
            if stopping.is_set() and role_exit.error is None:
                break
            unexpected_exit = role_exit
            stopping.set()
            break
    finally:
        stopping.set()
        deadline = time.monotonic() + shutdown_timeout_seconds
        for thread in threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))

    still_running = [thread.name for thread in threads if thread.is_alive()]
    if still_running:
        raise RuntimeError(f"Unified jobs roles did not stop within the deadline: {', '.join(still_running)}")
    if unexpected_exit is not None and unexpected_exit.error is not None:
        raise RuntimeError(f"Unified jobs role failed: {unexpected_exit.name}") from unexpected_exit.error
    if unexpected_exit is not None:
        raise RuntimeError(f"Unified jobs role exited unexpectedly: {unexpected_exit.name}")
    logger.info("unified_jobs_stopped", roles=names, process_id=os.getpid())


def run() -> None:
    if os.environ.get(HEARTBEAT_SERVICE_ENV):
        raise RuntimeError(f"{HEARTBEAT_SERVICE_ENV} cannot be set for the unified jobs process")
    settings = get_settings()
    roles = enabled_job_roles(settings)
    initialize_telemetry("pharma-jobs")
    stopping = threading.Event()

    def stop(_signum: int, _frame: object) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    supervise_jobs(
        roles,
        stopping,
        poll_seconds=settings.jobs_supervisor_poll_seconds,
        shutdown_timeout_seconds=settings.jobs_shutdown_timeout_seconds,
    )
