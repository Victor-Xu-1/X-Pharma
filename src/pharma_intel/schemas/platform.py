from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class PlatformServiceRead(BaseModel):
    service_id: str
    owner: str
    escalation_policy: str
    status: Literal["ready", "degraded", "blocked", "external"]
    enabled: bool | None
    liveness: Literal["observed", "unverified", "not_applicable"]
    queue_status: Literal["healthy", "degraded", "not_applicable"]
    detail: str


class PlatformWorkflowRead(BaseModel):
    engine: Literal["temporal"]
    enabled: bool
    namespace: str
    task_queue: str
    max_concurrent_activities: int


class PlatformModelBudgetRead(BaseModel):
    window: Literal["24h"]
    run_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost: str
    failed_runs: int
    max_document_cost: str
    provider: str
    model: str


class PlatformSloRead(BaseModel):
    id: str
    service: str
    metric: str
    measurement: str
    target: float
    window: str
    evaluation_status: Literal["external_evidence_required"]
    error_budget_policy: str


class PlatformAlertRead(BaseModel):
    id: str
    objective: str
    severity: Literal["warning", "critical"]
    threshold: float
    lookback: str
    runbook: str


class PlatformMigrationRead(BaseModel):
    current_revision: str | None
    expected_revision: str | None
    status: Literal["current", "behind", "unknown"]


class PlatformEvidenceRead(BaseModel):
    category: Literal["backup_restore", "release_candidate", "production_topology"]
    status: Literal["not_configured", "missing", "passed", "failed", "invalid"]
    artifact: str
    sha256: str | None
    observed_at: str | None
    detail: str


class PlatformEventRead(BaseModel):
    id: str
    action: str
    outcome: str
    resource_type: str
    occurred_at: datetime
    request_id: str


class PlatformOperationsRead(BaseModel):
    generated_at: datetime
    environment: str
    services: list[PlatformServiceRead]
    queues: dict[str, Any]
    workflow: PlatformWorkflowRead
    model_budget: PlatformModelBudgetRead
    slos: list[PlatformSloRead]
    alerts: list[PlatformAlertRead]
    migration: PlatformMigrationRead
    evidence: list[PlatformEvidenceRead]
    recent_events: list[PlatformEventRead]
