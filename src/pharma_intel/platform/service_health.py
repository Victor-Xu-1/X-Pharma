"""Report only the configuration and observations available to the API process."""

from __future__ import annotations

from typing import Any

from pharma_intel.config import Settings
from pharma_intel.job_roles import enabled_job_role_specs
from pharma_intel.models import ProjectionDeliveryState
from pharma_intel.operations_contract import OperationsContract


def service_statuses(
    contract: OperationsContract,
    *,
    stale_ingestion_runs: int,
    delivery_counts: dict[str, dict[str, int]],
    settings: Settings,
) -> list[dict[str, Any]]:
    # Share the jobs supervisor's configuration authority. A process-local PID or
    # heartbeat file cannot prove that a worker in another container is alive.
    roles = enabled_job_role_specs(settings)
    enabled_services = {role.heartbeat_service for role in roles}
    if any(role.name == "ingestion" for role in roles):
        enabled_services.add("data-factory")
    worker_queues: dict[str, int | None] = {
        "data-factory": stale_ingestion_runs,
        "search-projector": delivery_counts.get("opensearch", {}).get(ProjectionDeliveryState.DEAD.value, 0),
        "search-maintenance": None,
        "monitoring-worker": delivery_counts.get("monitoring", {}).get(ProjectionDeliveryState.DEAD.value, 0),
        "billing-provider": delivery_counts.get("billing_provider", {}).get(ProjectionDeliveryState.DEAD.value, 0),
    }
    external_details = {
        "workspace": "Web rendering and navigation require a browser probe; an API request is not Web liveness",
        "mcp": "MCP liveness and OAuth require a probe at the dedicated Agent entry",
        "parser": "Parser liveness requires a probe inside the isolated parser network",
        "clamav": "Scanner liveness requires a probe at the ingestion safety gate",
    }
    services: list[dict[str, Any]] = []
    for item in contract.services:
        observation: dict[str, Any] = {
            "service_id": item.id,
            "owner": item.owner,
            "escalation_policy": item.escalation_policy,
            "status": "external",
            "enabled": None,
            "liveness": "unverified",
            "queue_status": "not_applicable",
            "detail": external_details.get(item.id, "External telemetry evidence required"),
        }
        if item.id == "api":
            observation.update(
                status="ready",
                enabled=True,
                liveness="observed",
                detail="Authenticated platform snapshot query completed; not a platform-wide readiness check",
            )
        elif item.id in worker_queues:
            enabled = item.id in enabled_services
            problems = worker_queues[item.id]
            configuration = "enabled" if enabled else "disabled"
            queue_detail = (
                "queue state is not measured here"
                if problems is None
                else f"{problems} stale ingestion runs"
                if item.id == "data-factory"
                else f"{problems} dead deliveries"
            )
            observation.update(
                status="degraded" if problems else "external" if enabled else "blocked",
                enabled=enabled,
                liveness="unverified" if enabled else "not_applicable",
                queue_status="not_applicable" if problems is None else "degraded" if problems else "healthy",
                detail=f"Job role is {configuration}; {queue_detail}; deployment health probe required",
            )
        services.append(observation)
    return services
