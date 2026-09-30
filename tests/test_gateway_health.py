from __future__ import annotations

from types import SimpleNamespace

import pytest

from pharma_intel.gateway_health import verify_api_readiness, verify_gateway_health


class _Response:
    status = 200

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_gateway_health_checks_api_and_mcp_on_the_same_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[str, str, str | None, float]] = []

    def record_metadata(
        url: str,
        *,
        expected_resource_url: str,
        expected_authorization_server_url: str,
        timeout_seconds: float,
    ) -> tuple[str, ...]:
        observed.append(("metadata", url, expected_resource_url, timeout_seconds))
        observed.append(("issuer", expected_authorization_server_url, None, timeout_seconds))
        return ("http://127.0.0.1:8080/",)

    monkeypatch.setattr(
        "pharma_intel.gateway_health.verify_api_readiness",
        lambda url, *, timeout_seconds: observed.append(("api", url, None, timeout_seconds)),
    )
    monkeypatch.setattr(
        "pharma_intel.gateway_health.verify_unauthenticated_rejection",
        lambda url, *, expected_resource_url, timeout_seconds: observed.append(
            ("mcp", url, expected_resource_url, timeout_seconds)
        ),
    )
    monkeypatch.setattr(
        "pharma_intel.gateway_health.verify_protected_resource_metadata",
        record_metadata,
    )

    verify_gateway_health(timeout_seconds=2)

    assert observed == [
        ("api", "http://127.0.0.1:8080/health/ready", None, 2),
        ("mcp", "http://127.0.0.1:8080/mcp", "http://127.0.0.1:8090/mcp", 2),
        ("metadata", "http://127.0.0.1:8080/mcp", "http://127.0.0.1:8090/mcp", 2),
        ("issuer", "http://127.0.0.1:8080", None, 2),
    ]


def test_gateway_health_verifies_oidc_discovery_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[str, float]] = []
    monkeypatch.setattr(
        "pharma_intel.gateway_health.verify_api_readiness",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "pharma_intel.gateway_health.verify_unauthenticated_rejection",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "pharma_intel.gateway_health.verify_protected_resource_metadata",
        lambda *_args, **_kwargs: ("https://IDENTITY.EXAMPLE.TEST/",),
    )
    monkeypatch.setattr(
        "pharma_intel.gateway_health.verify_authorization_server_metadata",
        lambda url, *, timeout_seconds: observed.append((url, timeout_seconds)),
    )

    verify_gateway_health(
        expected_mcp_authorization_server_url="https://identity.example.test",
        verify_mcp_authorization_server=True,
        timeout_seconds=2,
    )

    assert observed == [("https://IDENTITY.EXAMPLE.TEST/", 2)]


def test_api_readiness_disables_proxies_and_accepts_only_bounded_loopback_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = SimpleNamespace(open=lambda request, timeout: _Response())
    monkeypatch.setattr("pharma_intel.gateway_health.urllib.request.build_opener", lambda *_args: opener)

    verify_api_readiness("http://127.0.0.1:8080/health/ready", timeout_seconds=2)

    with pytest.raises(ValueError, match="loopback"):
        verify_api_readiness("https://example.com/health/ready")
