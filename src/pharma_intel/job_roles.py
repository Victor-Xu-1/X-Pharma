from __future__ import annotations

from dataclasses import dataclass

from pharma_intel.config import Settings


@dataclass(frozen=True)
class JobRoleSpec:
    name: str
    heartbeat_service: str
    heartbeat_max_age_seconds: float


def ingestion_heartbeat_service(settings: Settings) -> str:
    if settings.temporal_worker_enabled and settings.temporal_scheduler_enabled:
        return "data-factory"
    if settings.temporal_worker_enabled:
        return "ingest-worker"
    return "ingest-scheduler"


def enabled_job_role_specs(settings: Settings) -> tuple[JobRoleSpec, ...]:
    roles: list[JobRoleSpec] = []
    if settings.temporal_enabled and (settings.temporal_worker_enabled or settings.temporal_scheduler_enabled):
        roles.append(JobRoleSpec("ingestion", ingestion_heartbeat_service(settings), 30))
    if settings.search_projection_enabled:
        roles.extend(
            (
                JobRoleSpec("search-projector", "search-projector", 150),
                JobRoleSpec("search-maintenance", "search-maintenance", 150),
            )
        )
    if settings.monitoring_enabled:
        roles.append(JobRoleSpec("monitoring", "monitoring-worker", 150))
    if settings.billing_provider_enabled:
        roles.append(JobRoleSpec("billing", "billing-provider", 660))
    return tuple(roles)
