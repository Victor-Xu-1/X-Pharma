from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from pharma_intel.runtime_heartbeat import (
    HEARTBEAT_DIRECTORY_ENV,
    HEARTBEAT_SCHEMA,
    HEARTBEAT_SERVICE_ENV,
    RuntimeHeartbeat,
    RuntimeHeartbeatError,
    verify_runtime_heartbeat,
)


@pytest.fixture(autouse=True)
def _clear_heartbeat_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(HEARTBEAT_DIRECTORY_ENV, raising=False)
    monkeypatch.delenv(HEARTBEAT_SERVICE_ENV, raising=False)


def test_runtime_heartbeat_is_private_atomic_verifiable_and_removed(tmp_path: Path) -> None:
    observed: list[tuple[int, int]] = []
    heartbeat = RuntimeHeartbeat("ingest-worker", directory=tmp_path, pid=321, clock=lambda: 1000.0)

    with heartbeat:
        status = verify_runtime_heartbeat(
            "ingest-worker",
            directory=tmp_path,
            max_age_seconds=30,
            clock=lambda: 1010.0,
            process_probe=lambda pid, signal: observed.append((pid, signal)),
        )
        assert status.service == "ingest-worker"
        assert status.pid == 321
        assert status.observed_at_epoch_ms == 1_000_000
        document = json.loads(heartbeat.path.read_text(encoding="utf-8"))
        assert document == {
            "observed_at_epoch_ms": 1_000_000,
            "pid": 321,
            "schema": HEARTBEAT_SCHEMA,
            "service": "ingest-worker",
            "status": "ready",
        }
        assert heartbeat.path.stat().st_mode & 0o777 == 0o600
        assert list(tmp_path.glob(".ingest-worker.*")) == []

    assert observed == [(321, 0)]
    assert not heartbeat.path.exists()


@pytest.mark.parametrize(
    ("clock", "process_probe", "message"),
    [
        (lambda: 1100.0, lambda _pid, _signal: None, "stale"),
        (lambda: 990.0, lambda _pid, _signal: None, "future"),
        (lambda: 1001.0, lambda _pid, _signal: (_ for _ in ()).throw(ProcessLookupError()), "unavailable"),
    ],
)
def test_runtime_heartbeat_rejects_stale_future_or_dead_process(
    tmp_path: Path,
    clock: object,
    process_probe: object,
    message: str,
) -> None:
    heartbeat = RuntimeHeartbeat("search-projector", directory=tmp_path, pid=45, clock=lambda: 1000.0)
    heartbeat.beat()

    with pytest.raises(RuntimeHeartbeatError, match=message):
        verify_runtime_heartbeat(
            "search-projector",
            directory=tmp_path,
            max_age_seconds=30,
            clock=clock,  # type: ignore[arg-type]
            process_probe=process_probe,  # type: ignore[arg-type]
        )


def test_runtime_heartbeat_rejects_symlink_and_contract_tampering(tmp_path: Path) -> None:
    heartbeat = RuntimeHeartbeat("monitoring-worker", directory=tmp_path, clock=lambda: 1000.0)
    heartbeat.beat()
    target = tmp_path / "target.json"
    heartbeat.path.replace(target)
    heartbeat.path.symlink_to(target)

    with pytest.raises(RuntimeHeartbeatError, match="regular file"):
        verify_runtime_heartbeat("monitoring-worker", directory=tmp_path, clock=lambda: 1001.0)

    heartbeat.path.unlink()
    heartbeat.path.write_text("{}", encoding="utf-8")
    heartbeat.path.chmod(0o600)
    with pytest.raises(RuntimeHeartbeatError, match="invalid contract"):
        verify_runtime_heartbeat("monitoring-worker", directory=tmp_path, clock=lambda: 1001.0)


def test_runtime_heartbeat_rejects_invalid_service_relative_directory_and_age(tmp_path: Path) -> None:
    with pytest.raises(RuntimeHeartbeatError, match="service name"):
        RuntimeHeartbeat("../worker", directory=tmp_path)
    with pytest.raises(RuntimeHeartbeatError, match="must be absolute"):
        RuntimeHeartbeat("worker", directory=Path("relative"))
    with pytest.raises(RuntimeHeartbeatError, match="PID must be positive"):
        RuntimeHeartbeat("worker", directory=tmp_path, pid=0)
    with pytest.raises(RuntimeHeartbeatError, match="maximum age"):
        verify_runtime_heartbeat("worker", directory=tmp_path, max_age_seconds=0)


def test_runtime_heartbeat_rejects_shared_writable_directory(tmp_path: Path) -> None:
    tmp_path.chmod(0o777)

    with pytest.raises(RuntimeHeartbeatError, match="private and process-owned"):
        RuntimeHeartbeat("worker", directory=tmp_path).beat()


def test_runtime_heartbeat_environment_service_binding_cannot_be_bypassed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(HEARTBEAT_SERVICE_ENV, "ingest-scheduler")
    heartbeat = RuntimeHeartbeat("ingest-worker", directory=tmp_path, pid=os.getpid())
    heartbeat.beat()

    assert heartbeat.service == "ingest-scheduler"
    with pytest.raises(RuntimeHeartbeatError, match="unavailable"):
        verify_runtime_heartbeat("ingest-worker", directory=tmp_path)
