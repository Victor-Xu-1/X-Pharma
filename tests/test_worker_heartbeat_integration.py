from __future__ import annotations

import argparse
from types import SimpleNamespace
from typing import Any, cast

import pytest

from pharma_intel.commercial import billing_worker
from pharma_intel.config import Settings
from pharma_intel.monitoring import worker as monitoring_worker
from pharma_intel.search import worker as search_worker


class _OneIterationEvent:
    def __init__(self) -> None:
        self.stopped = False

    def is_set(self) -> bool:
        return self.stopped

    def set(self) -> None:
        self.stopped = True

    def wait(self, _timeout: float) -> bool:
        self.stopped = True
        return True


class _RecordingHeartbeat:
    instances: list[_RecordingHeartbeat] = []

    def __init__(self, service: str) -> None:
        self.service = service
        self.beats = 0
        self.closed = False
        type(self).instances.append(self)

    def beat(self) -> None:
        self.beats += 1

    def __enter__(self) -> _RecordingHeartbeat:
        self.beat()
        return self

    def __exit__(self, *_args: object) -> None:
        self.closed = True


class _IdleConsumer:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def drain_once(self) -> SimpleNamespace:
        return SimpleNamespace(processed=0, succeeded=0, retried=0, dead=0)


class _IdleQualityWorker:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def process_once(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _reset_heartbeats() -> None:
    _RecordingHeartbeat.instances = []


def _assert_single_heartbeat(service: str) -> None:
    assert len(_RecordingHeartbeat.instances) == 1
    heartbeat = _RecordingHeartbeat.instances[0]
    assert heartbeat.service == service
    assert heartbeat.beats == 2
    assert heartbeat.closed is True


def test_search_projector_refreshes_heartbeat_after_a_bounded_drain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, search_projection_enabled=True, search_projection_poll_seconds=0.1)
    gateway = SimpleNamespace(ensure_indices=lambda: {"entities": "index-1"})
    monkeypatch.setattr(search_worker, "initialize_telemetry", lambda _name: None)
    monkeypatch.setattr(search_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(search_worker, "get_opensearch_gateway", lambda: gateway)
    monkeypatch.setattr(search_worker, "get_session_factory", lambda: object())
    monkeypatch.setattr(search_worker, "build_object_store", lambda _settings: object())
    monkeypatch.setattr(search_worker, "SearchProjectionConsumer", _IdleConsumer)
    monkeypatch.setattr(search_worker, "RuntimeHeartbeat", _RecordingHeartbeat)
    monkeypatch.setattr("pharma_intel.search.worker.threading.Event", _OneIterationEvent)
    monkeypatch.setattr("pharma_intel.search.worker.signal.signal", lambda *_args: None)

    search_worker.run()

    _assert_single_heartbeat("search-projector")


def test_monitoring_worker_refreshes_heartbeat_after_a_bounded_drain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, monitoring_enabled=True, monitoring_poll_seconds=0.1)
    monkeypatch.setattr(monitoring_worker, "initialize_telemetry", lambda _name: None)
    monkeypatch.setattr(monitoring_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(monitoring_worker, "get_session_factory", lambda: object())
    monkeypatch.setattr(monitoring_worker, "MonitoringConsumer", _IdleConsumer)
    monkeypatch.setattr(monitoring_worker, "DataQualityWorker", _IdleQualityWorker)
    monkeypatch.setattr(monitoring_worker, "RuntimeHeartbeat", _RecordingHeartbeat)
    monkeypatch.setattr("pharma_intel.monitoring.worker.threading.Event", _OneIterationEvent)
    monkeypatch.setattr("pharma_intel.monitoring.worker.signal.signal", lambda *_args: None)

    monitoring_worker.run()

    _assert_single_heartbeat("monitoring-worker")


def test_billing_provider_refreshes_heartbeat_after_a_bounded_drain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(_env_file=None, billing_provider_poll_seconds=0.1)
    args = argparse.Namespace(status=False, retry_dead=False, once=False, tenant_id=None)
    monkeypatch.setattr(billing_worker, "RuntimeHeartbeat", _RecordingHeartbeat)
    monkeypatch.setattr("pharma_intel.commercial.billing_worker.threading.Event", _OneIterationEvent)
    monkeypatch.setattr("pharma_intel.commercial.billing_worker.signal.signal", lambda *_args: None)

    assert billing_worker._execute(args, cast(Any, _IdleConsumer()), settings) == 0

    _assert_single_heartbeat("billing-provider")


def test_heartbeat_context_is_closed_when_a_worker_drain_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingConsumer(_IdleConsumer):
        def drain_once(self) -> Any:
            raise RuntimeError("database unavailable")

    settings = Settings(_env_file=None, monitoring_enabled=True)
    monkeypatch.setattr(monitoring_worker, "initialize_telemetry", lambda _name: None)
    monkeypatch.setattr(monitoring_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(monitoring_worker, "get_session_factory", lambda: object())
    monkeypatch.setattr(monitoring_worker, "MonitoringConsumer", FailingConsumer)
    monkeypatch.setattr(monitoring_worker, "RuntimeHeartbeat", _RecordingHeartbeat)
    monkeypatch.setattr("pharma_intel.monitoring.worker.threading.Event", _OneIterationEvent)
    monkeypatch.setattr("pharma_intel.monitoring.worker.signal.signal", lambda *_args: None)

    with pytest.raises(RuntimeError, match="database unavailable"):
        monitoring_worker.run()

    assert _RecordingHeartbeat.instances[0].closed is True
