from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace

import pytest

from pharma_intel.job_roles import JobRoleSpec
from pharma_intel.jobs_health import verify_jobs_health
from pharma_intel.runtime_heartbeat import RuntimeHeartbeatError


def test_jobs_health_import_does_not_load_unified_worker_graph() -> None:
    completed = subprocess.run(  # noqa: S603 - the interpreter and inline probe are fixed
        [
            sys.executable,
            "-c",
            "import sys; import pharma_intel.jobs_health; assert 'pharma_intel.jobs' not in sys.modules",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_jobs_health_requires_every_role_to_share_one_process(monkeypatch: pytest.MonkeyPatch) -> None:
    roles = (
        JobRoleSpec("ingestion", "data-factory", 30),
        JobRoleSpec("projector", "search-projector", 150),
    )
    monkeypatch.setattr("pharma_intel.jobs_health.get_settings", lambda: object())
    monkeypatch.setattr("pharma_intel.jobs_health.enabled_job_role_specs", lambda _settings: roles)
    monkeypatch.setattr(
        "pharma_intel.jobs_health.verify_runtime_heartbeat",
        lambda service, **_kwargs: SimpleNamespace(service=service, pid=41),
    )

    verify_jobs_health()


def test_jobs_health_rejects_role_heartbeats_from_multiple_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    roles = (
        JobRoleSpec("ingestion", "data-factory", 30),
        JobRoleSpec("projector", "search-projector", 150),
    )
    process_ids = iter((41, 42))
    monkeypatch.setattr("pharma_intel.jobs_health.get_settings", lambda: object())
    monkeypatch.setattr("pharma_intel.jobs_health.enabled_job_role_specs", lambda _settings: roles)
    monkeypatch.setattr(
        "pharma_intel.jobs_health.verify_runtime_heartbeat",
        lambda service, **_kwargs: SimpleNamespace(service=service, pid=next(process_ids)),
    )

    with pytest.raises(RuntimeHeartbeatError, match="one process"):
        verify_jobs_health()
