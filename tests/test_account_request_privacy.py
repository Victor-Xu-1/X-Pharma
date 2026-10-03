from __future__ import annotations

import secrets

import pytest
from fastapi.testclient import TestClient

from pharma_intel.api import app


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/v1/auth/login", {"email": "fixture@example.test"}),
        ("/api/v1/auth/invitations/accept", {"email": "fixture@example.test", "confirmed": True}),
        ("/api/v1/auth/oidc/invitation", {"confirmed": False}),
    ],
)
def test_authentication_validation_never_echoes_raw_credentials_or_invitation_input(
    path: str,
    payload: dict[str, object],
) -> None:
    marker = secrets.token_urlsafe(24)
    with TestClient(app) as client:
        response = client.post(path, json={**payload, "password": marker * 9, "invitation_code": marker * 100})
        assert response.status_code == 422
        assert marker not in response.text
        assert all(set(item) <= {"type", "loc", "msg"} for item in response.json()["detail"])


@pytest.mark.parametrize(
    "path", ["/api/v1/auth/login", "/api/v1/auth/invitations/accept", "/api/v1/auth/oidc/invitation"]
)
def test_anonymous_account_requests_are_bounded_before_json_parsing(path: str) -> None:
    with TestClient(app) as client:
        response = client.post(path, content=b"x" * 16_385, headers={"Content-Type": "application/json"})
        assert response.status_code == 413
