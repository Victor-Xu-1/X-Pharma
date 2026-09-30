from __future__ import annotations

import socket
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.models import AuditEvent, ProjectionMaintenanceJob, Tenant, new_uuid
from pharma_intel.object_store import ObjectStore
from pharma_intel.search.client import OpenSearchGateway
from pharma_intel.search.rebuild import SearchRebuilder

MAINTENANCE_LEASE = timedelta(hours=6)


class ProjectionMaintenanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClaimedMaintenanceJob:
    id: str
    tenant_id: str
    operation: str
    attempt: int


class ProjectionMaintenanceService:
    def __init__(self, session: Session, settings: Settings, tenant_id: str):
        self.session = session
        self.settings = settings
        self.tenant_id = tenant_id
        set_tenant_context(session, tenant_id)

    def request(self, operation: str, user_id: str, request_id: str) -> ProjectionMaintenanceJob:
        if operation not in {"consistency_check", "rebuild"}:
            raise ProjectionMaintenanceError("Unsupported projection maintenance operation")
        if operation == "rebuild" and not self.settings.search_allow_global_rebuild:
            raise ProjectionMaintenanceError("Global projection rebuild is disabled by deployment policy")
        job = ProjectionMaintenanceJob(
            id=new_uuid(),
            tenant_id=self.tenant_id,
            operation=operation,
            status="queued",
            active_key="global",
            build_id=f"job-{uuid.uuid4().hex[:16]}" if operation == "rebuild" else None,
            requested_by_user_id=user_id,
            result={},
        )
        self.session.add(job)
        self.session.add(
            AuditEvent(
                tenant_id=self.tenant_id,
                actor_type="user",
                actor_id=user_id,
                action="search.projection_maintenance.requested",
                resource_type="projection_maintenance_job",
                resource_id=job.id,
                outcome="success",
                request_id=request_id,
                details={"operation": operation, "global": True},
            )
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ProjectionMaintenanceError("Another projection maintenance job is already active") from exc
        return job

    def get(self, job_id: str) -> ProjectionMaintenanceJob:
        job = self.session.scalar(
            select(ProjectionMaintenanceJob).where(
                ProjectionMaintenanceJob.tenant_id == self.tenant_id,
                ProjectionMaintenanceJob.id == job_id,
            )
        )
        if job is None:
            raise LookupError("Projection maintenance job not found")
        return job

    def list(self, limit: int = 100) -> list[ProjectionMaintenanceJob]:
        return list(
            self.session.scalars(
                select(ProjectionMaintenanceJob)
                .where(ProjectionMaintenanceJob.tenant_id == self.tenant_id)
                .order_by(ProjectionMaintenanceJob.created_at.desc(), ProjectionMaintenanceJob.id.desc())
                .limit(limit)
            )
        )


class ProjectionMaintenanceWorker:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        gateway: OpenSearchGateway,
        object_store: ObjectStore,
        settings: Settings,
        *,
        worker_id: str | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.gateway = gateway
        self.object_store = object_store
        self.settings = settings
        self.worker_id = worker_id or f"{socket.gethostname()}:{uuid.uuid4()}"

    def process_once(self) -> ProjectionMaintenanceJob | None:
        claimed = self._claim()
        if claimed is None:
            return None
        try:
            rebuilder = SearchRebuilder(
                self.session_factory,
                self.gateway,
                self.object_store,
                self.settings,
            )
            expected = rebuilder.expected_counts()
            before = rebuilder.current_counts()
            if claimed.operation == "consistency_check":
                result = {
                    "consistent": expected == before,
                    "expected_counts": expected,
                    "actual_counts": before,
                    "delta": {kind: before[kind] - expected[kind] for kind in expected},
                }
            else:
                build_id = f"{self._job_build_id(claimed)}-a{claimed.attempt}"
                rebuilt = rebuilder.rebuild(build_id)
                result = {
                    "consistent_before": expected == before,
                    "expected_counts_before": expected,
                    "actual_counts_before": before,
                    "rebuild": {
                        "targets": rebuilt.targets,
                        "counts": rebuilt.counts,
                        "started_at": rebuilt.started_at.isoformat(),
                        "completed_at": rebuilt.completed_at.isoformat(),
                    },
                    "actual_counts_after": rebuilder.current_counts(),
                }
            return self._finish(claimed, result)
        except Exception as exc:
            return self._fail(claimed, exc)

    def _tenant_ids(self) -> list[str]:
        with self.session_factory() as session:
            return list(session.scalars(select(Tenant.id).where(Tenant.active.is_(True)).order_by(Tenant.id)))

    def _claim(self) -> ClaimedMaintenanceJob | None:
        now = datetime.now(UTC)
        for tenant_id in self._tenant_ids():
            with self.session_factory() as session:
                set_tenant_context(session, tenant_id)
                job = session.scalar(
                    select(ProjectionMaintenanceJob)
                    .where(
                        ProjectionMaintenanceJob.tenant_id == tenant_id,
                        or_(
                            ProjectionMaintenanceJob.status == "queued",
                            (
                                (ProjectionMaintenanceJob.status == "running")
                                & (ProjectionMaintenanceJob.lease_expires_at.is_not(None))
                                & (ProjectionMaintenanceJob.lease_expires_at <= now)
                            ),
                        ),
                    )
                    .order_by(ProjectionMaintenanceJob.created_at, ProjectionMaintenanceJob.id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                if job is None:
                    continue
                job.status = "running"
                job.attempts += 1
                job.worker_id = self.worker_id
                job.lease_expires_at = now + MAINTENANCE_LEASE
                job.started_at = job.started_at or now
                job.last_error = None
                session.commit()
                return ClaimedMaintenanceJob(job.id, tenant_id, job.operation, job.attempts)
        return None

    def _job_build_id(self, claimed: ClaimedMaintenanceJob) -> str:
        with self.session_factory() as session:
            set_tenant_context(session, claimed.tenant_id)
            job = session.get(ProjectionMaintenanceJob, claimed.id)
            if job is None or not job.build_id:
                raise ProjectionMaintenanceError("Projection rebuild job lost its build identifier")
            return str(job.build_id)

    def _finish(self, claimed: ClaimedMaintenanceJob, result: dict[str, Any]) -> ProjectionMaintenanceJob:
        with self.session_factory() as session:
            set_tenant_context(session, claimed.tenant_id)
            job = session.scalar(
                select(ProjectionMaintenanceJob)
                .where(
                    ProjectionMaintenanceJob.id == claimed.id,
                    ProjectionMaintenanceJob.tenant_id == claimed.tenant_id,
                    ProjectionMaintenanceJob.status == "running",
                    ProjectionMaintenanceJob.worker_id == self.worker_id,
                )
                .with_for_update()
            )
            if job is None:
                raise ProjectionMaintenanceError("Projection maintenance lease was lost")
            job.status = "succeeded"
            job.result = result
            job.completed_at = datetime.now(UTC)
            job.lease_expires_at = None
            job.active_key = None
            session.add(
                AuditEvent(
                    tenant_id=claimed.tenant_id,
                    actor_type="system",
                    actor_id=self.worker_id,
                    action="search.projection_maintenance.completed",
                    resource_type="projection_maintenance_job",
                    resource_id=job.id,
                    outcome="success",
                    request_id=job.id,
                    details={"operation": job.operation, "attempts": job.attempts},
                )
            )
            session.commit()
            return job

    def _fail(self, claimed: ClaimedMaintenanceJob, exc: Exception) -> ProjectionMaintenanceJob:
        with self.session_factory() as session:
            set_tenant_context(session, claimed.tenant_id)
            job = session.get(ProjectionMaintenanceJob, claimed.id)
            if job is None:
                raise ProjectionMaintenanceError("Projection maintenance job disappeared") from exc
            job.status = "failed"
            job.last_error = str(exc)[:4000]
            job.completed_at = datetime.now(UTC)
            job.lease_expires_at = None
            job.active_key = None
            session.add(
                AuditEvent(
                    tenant_id=claimed.tenant_id,
                    actor_type="system",
                    actor_id=self.worker_id,
                    action="search.projection_maintenance.completed",
                    resource_type="projection_maintenance_job",
                    resource_id=job.id,
                    outcome="failed",
                    request_id=job.id,
                    details={"operation": job.operation, "attempts": job.attempts},
                )
            )
            session.commit()
            return job
