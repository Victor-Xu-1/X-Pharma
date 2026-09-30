from __future__ import annotations

import threading
import time
from collections.abc import Callable

import pytest

from pharma_intel.config import Settings
from pharma_intel.jobs import JobRole, enabled_job_roles, ingestion_heartbeat_service, supervise_jobs


def test_enabled_roles_collapse_background_capabilities_into_one_process_contract() -> None:
    settings = Settings(
        temporal_enabled=True,
        temporal_worker_enabled=True,
        temporal_scheduler_enabled=True,
        search_projection_enabled=True,
        monitoring_enabled=True,
        billing_provider_enabled=False,
    )

    roles = enabled_job_roles(settings)

    assert [role.name for role in roles] == ["ingestion", "search-projector", "search-maintenance", "monitoring"]
    assert [role.heartbeat_service for role in roles] == [
        "data-factory",
        "search-projector",
        "search-maintenance",
        "monitoring-worker",
    ]
    assert ingestion_heartbeat_service(settings) == "data-factory"


def test_supervisor_starts_roles_and_stops_them_from_one_event() -> None:
    stopping = threading.Event()
    started = {"one": threading.Event(), "two": threading.Event()}

    def role(name: str) -> Callable[[threading.Event], None]:
        def target(stop: threading.Event) -> None:
            started[name].set()
            stop.wait()

        return target

    roles = (
        JobRole("one", "one", 30, role("one")),
        JobRole("two", "two", 30, role("two")),
    )
    failure: list[BaseException] = []

    def supervise() -> None:
        try:
            supervise_jobs(roles, stopping, poll_seconds=0.01, shutdown_timeout_seconds=1)
        except BaseException as exc:
            failure.append(exc)

    thread = threading.Thread(target=supervise)
    thread.start()
    assert started["one"].wait(1)
    assert started["two"].wait(1)
    stopping.set()
    thread.join(2)

    assert not thread.is_alive()
    assert failure == []


def test_supervisor_propagates_role_failure_and_stops_siblings() -> None:
    stopping = threading.Event()
    sibling_stopped = threading.Event()

    def failing(_stop: threading.Event) -> None:
        raise ValueError("projection failed")

    def sibling(stop: threading.Event) -> None:
        stop.wait()
        sibling_stopped.set()

    roles = (
        JobRole("projector", "search-projector", 30, failing),
        JobRole("monitoring", "monitoring-worker", 30, sibling),
    )

    with pytest.raises(RuntimeError, match="Unified jobs role failed: projector") as caught:
        supervise_jobs(roles, stopping, poll_seconds=0.01, shutdown_timeout_seconds=1)

    assert isinstance(caught.value.__cause__, ValueError)
    assert sibling_stopped.wait(1)


def test_supervisor_rejects_empty_and_duplicate_role_contracts() -> None:
    with pytest.raises(RuntimeError, match="At least one"):
        supervise_jobs((), threading.Event(), poll_seconds=0.01, shutdown_timeout_seconds=1)

    role = JobRole("duplicate", "one", 30, lambda stop: time.sleep(0))
    with pytest.raises(RuntimeError, match="unique"):
        supervise_jobs((role, role), threading.Event(), poll_seconds=0.01, shutdown_timeout_seconds=1)
