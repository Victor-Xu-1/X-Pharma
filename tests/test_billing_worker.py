from __future__ import annotations

import json

import pytest

from pharma_intel.commercial import billing_worker
from pharma_intel.commercial.billing_consumer import BillingDeliveryBatchResult
from pharma_intel.config import Settings


class _Consumer:
    result = BillingDeliveryBatchResult(1, 1, 0, 0)
    retry_tenant: str | None = None

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def delivery_counts(self) -> dict[str, int]:
        return {"pending": 0, "processing": 0, "retry": 2, "succeeded": 5, "dead": 1}

    def retry_dead(self, tenant_id: str | None = None) -> int:
        type(self).retry_tenant = tenant_id
        return 3

    def drain_once(self) -> BillingDeliveryBatchResult:
        return self.result


class _Engine:
    disposed = False

    def dispose(self) -> None:
        type(self).disposed = True


def _enabled_settings() -> Settings:
    return Settings(
        _env_file=None,
        billing_provider_enabled=True,
        billing_provider_name="approved-erp",
        billing_provider_base_url="https://billing.example.test",
        billing_provider_api_token="billing-provider-test-token-with-32-bytes",  # noqa: S106
    )


def _install_runtime(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    _Engine.disposed = False
    monkeypatch.setattr(billing_worker, "initialize_telemetry", lambda _name, **_kwargs: None)
    monkeypatch.setattr(billing_worker, "get_billing_worker_settings", lambda: settings)
    monkeypatch.setattr(billing_worker, "create_engine_from_settings", lambda _settings: _Engine())
    monkeypatch.setattr(billing_worker, "sessionmaker", lambda **_kwargs: object())
    monkeypatch.setattr(billing_worker, "HttpBillingProviderAdapter", lambda **_kwargs: object())
    monkeypatch.setattr(billing_worker, "BillingProviderConsumer", _Consumer)


def test_billing_worker_reports_status_as_machine_readable_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_runtime(monkeypatch, _enabled_settings())

    assert billing_worker.main(["--status"]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "dead": 1,
        "pending": 0,
        "processing": 0,
        "retry": 2,
        "succeeded": 5,
    }
    assert _Engine.disposed is True


def test_billing_worker_replays_dead_deliveries_for_one_tenant(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_runtime(monkeypatch, _enabled_settings())
    _Consumer.retry_tenant = None

    assert billing_worker.main(["--retry-dead", "--tenant-id", "tenant-1"]) == 0

    assert _Consumer.retry_tenant == "tenant-1"
    assert json.loads(capsys.readouterr().out) == {"requeued": 3}


def test_billing_worker_once_returns_failure_when_a_delivery_is_dead(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_runtime(monkeypatch, _enabled_settings())
    _Consumer.result = BillingDeliveryBatchResult(1, 0, 0, 1)

    assert billing_worker.main(["--once"]) == 1

    assert json.loads(capsys.readouterr().out) == {
        "dead": 1,
        "processed": 1,
        "retried": 0,
        "succeeded": 0,
    }
    _Consumer.result = BillingDeliveryBatchResult(1, 1, 0, 0)


def test_billing_worker_refuses_disabled_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_runtime(monkeypatch, Settings(_env_file=None, billing_provider_enabled=False))

    with pytest.raises(RuntimeError, match="BILLING_PROVIDER_ENABLED"):
        billing_worker.main(["--status"])


def test_billing_worker_rejects_tenant_without_replay_action() -> None:
    with pytest.raises(SystemExit, match="requires --retry-dead"):
        billing_worker.main(["--tenant-id", "tenant-1"])
