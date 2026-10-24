from __future__ import annotations

import importlib.metadata
import ssl

import certifi
import pytest
from packaging.requirements import Requirement
from packaging.version import Version


@pytest.mark.parametrize(
    ("distribution", "minimum"),
    [
        ("certifi", "2026.10.19"),
        ("opentelemetry-api", "1.45.1"),
        ("opentelemetry-sdk", "1.45.1"),
        ("Pillow", "13.0.0"),
        ("pypdf", "6.21.2"),
    ],
)
def test_audited_dependencies_meet_the_october_security_floor(distribution: str, minimum: str) -> None:
    assert Version(importlib.metadata.version(distribution)) >= Version(minimum)


def test_telemetry_instrumentation_and_its_declared_dependencies_are_coherent() -> None:
    distributions = (
        "opentelemetry-api",
        "opentelemetry-sdk",
        "opentelemetry-exporter-otlp-proto-grpc",
        "opentelemetry-instrumentation-fastapi",
        "opentelemetry-instrumentation-httpx",
        "opentelemetry-instrumentation-logging",
        "opentelemetry-instrumentation-sqlalchemy",
    )
    for distribution in distributions:
        for declaration in importlib.metadata.requires(distribution) or []:
            requirement = Requirement(declaration)
            if not requirement.name.startswith("opentelemetry-"):
                continue
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            installed = Version(importlib.metadata.version(requirement.name))
            assert installed in requirement.specifier, (distribution, declaration, installed)


def test_updated_certificate_bundle_remains_a_real_tls_trust_store() -> None:
    context = ssl.create_default_context(cafile=certifi.where())
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    assert context.cert_store_stats()["x509_ca"] > 0
