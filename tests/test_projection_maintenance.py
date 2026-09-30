from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.config import Settings
from pharma_intel.models import ProjectionMaintenanceJob, Tenant, User, UserRole
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.search.maintenance import (
    ProjectionMaintenanceError,
    ProjectionMaintenanceService,
    ProjectionMaintenanceWorker,
)


class MaintenanceGateway:
    def __init__(self, *, fail_counts: bool = False) -> None:
        self.fail_counts = fail_counts
        self.swapped: list[dict[str, str]] = []

    def count(self, kind: str, *, target: str | None = None) -> int:
        del kind, target
        if self.fail_counts:
            raise RuntimeError("controlled OpenSearch count failure")
        return 0

    @staticmethod
    def create_rebuild_indices(build_id: str | None = None) -> dict[str, str]:
        suffix = build_id or "test"
        return {kind: f"test-{kind}-{suffix}" for kind in ("entities", "evidence", "knowledge")}

    @staticmethod
    def bulk_index(documents, *, targets=None, refresh=False) -> int:  # type: ignore[no-untyped-def]
        del targets, refresh
        return len(documents)

    @staticmethod
    def refresh(targets=None) -> None:  # type: ignore[no-untyped-def]
        del targets

    def swap_rebuild_indices(self, targets: dict[str, str]) -> None:
        self.swapped.append(targets)


def _reviewer(session: Session, tenant: Tenant) -> User:
    reviewer = User(
        tenant_id=tenant.id,
        email="projection-operator@example.test",
        normalized_email="projection-operator@example.test",
        display_name="Projection Operator",
        password_hash="not-used",  # noqa: S106
        role=UserRole.ADMIN,
    )
    session.add(reviewer)
    session.commit()
    return reviewer


def _factory(session: Session) -> sessionmaker[Session]:
    return sessionmaker(bind=session.get_bind(), expire_on_commit=False)


def test_projection_maintenance_is_durable_exclusive_and_policy_gated(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    reviewer = _reviewer(session, tenant)
    settings = Settings(
        object_store_root=tmp_path / "objects",
        search_allow_global_rebuild=False,
        search_projection_batch_size=10,
    )
    service = ProjectionMaintenanceService(session, settings, tenant.id)
    check = service.request("consistency_check", reviewer.id, "req-check")
    assert check.status == "queued"
    assert check.active_key == "global"
    with pytest.raises(ProjectionMaintenanceError, match="already active"):
        service.request("consistency_check", reviewer.id, "req-conflict")
    with pytest.raises(ProjectionMaintenanceError, match="disabled"):
        service.request("rebuild", reviewer.id, "req-disabled")

    gateway = MaintenanceGateway()
    worker = ProjectionMaintenanceWorker(
        _factory(session),
        gateway,  # type: ignore[arg-type]
        FileSystemObjectStore(settings.object_store_root),
        settings,
        worker_id="maintenance-test-worker",
    )
    completed = worker.process_once()
    assert completed is not None
    assert completed.status == "succeeded"
    assert completed.result == {
        "consistent": True,
        "expected_counts": {"entities": 0, "evidence": 0, "knowledge": 0},
        "actual_counts": {"entities": 0, "evidence": 0, "knowledge": 0},
        "delta": {"entities": 0, "evidence": 0, "knowledge": 0},
    }
    assert completed.active_key is None

    enabled = Settings(
        object_store_root=tmp_path / "objects",
        search_allow_global_rebuild=True,
        search_projection_batch_size=10,
    )
    rebuild = ProjectionMaintenanceService(session, enabled, tenant.id).request("rebuild", reviewer.id, "req-rebuild")
    rebuilt = ProjectionMaintenanceWorker(
        _factory(session),
        gateway,  # type: ignore[arg-type]
        FileSystemObjectStore(enabled.object_store_root),
        enabled,
        worker_id="maintenance-rebuild-worker",
    ).process_once()
    assert rebuilt is not None and rebuilt.id == rebuild.id
    assert rebuilt.status == "succeeded", rebuilt.last_error
    assert rebuilt.result["actual_counts_after"] == {"entities": 0, "evidence": 0, "knowledge": 0}
    assert len(gateway.swapped) == 1


def test_projection_maintenance_failure_releases_the_global_slot(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    reviewer = _reviewer(session, tenant)
    settings = Settings(object_store_root=tmp_path / "objects")
    job = ProjectionMaintenanceService(session, settings, tenant.id).request(
        "consistency_check", reviewer.id, "req-failure"
    )
    failed = ProjectionMaintenanceWorker(
        _factory(session),
        MaintenanceGateway(fail_counts=True),  # type: ignore[arg-type]
        FileSystemObjectStore(settings.object_store_root),
        settings,
        worker_id="maintenance-failure-worker",
    ).process_once()

    assert failed is not None and failed.id == job.id
    assert failed.status == "failed"
    assert failed.active_key is None
    assert "controlled OpenSearch count failure" in (failed.last_error or "")
    assert session.get(ProjectionMaintenanceJob, job.id) is not None
