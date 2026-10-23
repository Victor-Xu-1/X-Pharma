from __future__ import annotations

from typing import Any

import pytest
from opentelemetry.sdk.resources import Resource

from pharma_intel import telemetry
from pharma_intel.config import Settings


def test_telemetry_version_follows_product_metadata_after_a_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, Any] = {}

    class ResourceRecorded(Exception):
        pass

    def record_resource(attributes: dict[str, Any]) -> None:
        observed.update(attributes)
        raise ResourceRecorded

    monkeypatch.setattr(telemetry, "_runtime", None)
    monkeypatch.setattr(telemetry, "PRODUCT_VERSION", "0.2.0", raising=False)
    monkeypatch.setattr(Resource, "create", record_resource)
    with pytest.raises(ResourceRecorded):
        telemetry.initialize_telemetry("pharma-gateway", settings=Settings(otel_enabled=True))
    assert observed["service.version"] == "0.2.0"
