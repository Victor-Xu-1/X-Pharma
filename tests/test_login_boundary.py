from collections.abc import Generator

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.accounts.request_budget import AccountBudget
from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.models import Tenant, UserRole
from pharma_intel.security import CSRF_COOKIE, hash_password


@pytest.fixture
def account_client(session: Session, tenant: Tenant) -> Generator[TestClient]:
    session.add(
        create_account(
            tenant_id=tenant.id,
            email="boundary@example.test",
            normalized_email="boundary@example.test",
            password_hash=hash_password("boundary-password"),
            display_name="Boundary",
            role=UserRole.VIEWER,
        )
    )
    session.commit()

    def session_override(request: Request) -> Generator[Session]:
        request.state.db_session = session
        yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("headers", [{"Origin": "https://untrusted.example"}, {"Sec-Fetch-Site": "cross-site"}])
def test_local_login_rejects_cross_site_session_issuance(account_client: TestClient, headers: dict[str, str]) -> None:
    response = account_client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={
            "email": "boundary@example.test",
            "password": "boundary-password",
        },
    )
    assert response.status_code == 403
    assert not account_client.cookies


def test_malformed_avatar_url_is_a_safe_validation_error_not_a_server_error(account_client: TestClient) -> None:
    logged_in = account_client.post(
        "/api/v1/auth/login",
        json={
            "email": "boundary@example.test",
            "password": "boundary-password",
        },
    )
    assert logged_in.status_code == 200
    response = account_client.patch(
        "/api/v1/auth/me",
        headers={
            "X-CSRF-Token": account_client.cookies[CSRF_COOKIE],
        },
        json={"avatar_url": "https://["},
    )
    assert response.status_code == 422
    assert account_client.get("/api/v1/auth/me").json()["avatar_url"] is None


def test_rejected_password_attempts_cannot_rollback_the_login_budget(
    account_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pharma_intel.accounts.request_budget.LOGIN_IDENTITY_BUDGET",
        AccountBudget(b"login-identity-peer", 2, "登录"),
    )
    for _ in range(2):
        response = account_client.post(
            "/api/v1/auth/login",
            json={
                "email": "boundary@example.test",
                "password": "wrong-boundary-password",
            },
        )
        assert response.status_code == 401
    blocked = account_client.post(
        "/api/v1/auth/login",
        json={
            "email": "boundary@example.test",
            "password": "boundary-password",
        },
    )
    assert blocked.status_code == 429 and blocked.headers["retry-after"] == "600"
    assert blocked.headers["cache-control"] == "no-store"
    assert not account_client.cookies
