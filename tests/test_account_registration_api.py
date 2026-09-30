from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from pharma_intel.accounts.request_limits import REGISTRATION_BODY_LIMIT
from pharma_intel.api import app
from pharma_intel.config import get_settings
from pharma_intel.db import get_engine, get_session_factory
from pharma_intel.models import AccountInvitation, Base, Tenant, User, UserRole
from pharma_intel.security import CSRF_COOKIE, SESSION_COOKIE, hash_password

PASSWORD = "registration-api-test-password"  # noqa: S105


@pytest.fixture
def registration_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'accounts.db'}")
    monkeypatch.setenv("HUMAN_AUTH_MODE", "local")
    monkeypatch.setenv("HUMAN_SELF_REGISTRATION_ENABLED", "true")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://testserver")
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    get_settings.cache_clear()
    engine = get_engine()
    Base.metadata.create_all(engine)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        engine.dispose()
        get_session_factory.cache_clear()
        get_engine.cache_clear()
        get_settings.cache_clear()


def _registration(email: str = "new@example.test") -> dict[str, object]:
    return {"email": email, "display_name": "Registered", "password": PASSWORD, "workbench": "research"}


def _bootstrap_admin() -> None:
    with get_session_factory()() as session:
        tenant = Tenant(slug="managed", name="Managed")
        session.add(tenant)
        session.flush()
        session.add(
            User(
                tenant_id=tenant.id,
                email="admin@example.test",
                normalized_email="admin@example.test",
                display_name="Admin",
                password_hash=hash_password(PASSWORD),
                role=UserRole.ADMIN,
            )
        )
        session.commit()


def test_real_registration_login_and_server_side_logout_revocation(registration_client: TestClient) -> None:
    client = registration_client
    created = client.post("/api/v1/auth/register", json=_registration())
    assert created.status_code == 201
    assert created.headers["Cache-Control"] == "no-store"
    assert created.json()["role"] == "viewer"
    assert PASSWORD not in created.text
    assert (
        client.post("/api/v1/auth/login", json={"email": "new@example.test", "password": PASSWORD}).status_code == 200
    )
    old_cookie = client.cookies.get(SESSION_COOKIE)
    assert old_cookie
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.get("/api/v1/enterprise/account-invitations").status_code == 403
    csrf = client.cookies.get(CSRF_COOKIE)
    assert csrf
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Cookie": f"{SESSION_COOKIE}={old_cookie}"}).status_code == 401


def test_invitation_issuance_redemption_and_secret_free_list(registration_client: TestClient) -> None:
    client = registration_client
    _bootstrap_admin()
    assert (
        client.post("/api/v1/auth/login", json={"email": "admin@example.test", "password": PASSWORD}).status_code == 200
    )
    csrf = client.cookies.get(CSRF_COOKIE)
    assert csrf
    issued = client.post(
        "/api/v1/enterprise/account-invitations",
        json={"email": "employee@example.test"},
        headers={"X-CSRF-Token": csrf},
    )
    assert issued.status_code == 201
    assert issued.headers["Cache-Control"] == "no-store"
    code = issued.json()["code"]
    listed = client.get("/api/v1/enterprise/account-invitations")
    assert listed.status_code == 200 and listed.json()[0]["status"] == "active"
    assert code not in listed.text and "token_digest" not in listed.text
    payload = _registration("employee@example.test") | {"workbench": "internal", "invitation_code": code}
    registered = client.post("/api/v1/auth/register", json=payload)
    assert registered.status_code == 201 and registered.json()["role"] == "analyst"
    assert registered.json()["tenant_id"] == issued.json()["invitation"]["tenant_id"]
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert (
        client.post("/api/v1/auth/login", json={"email": "employee@example.test", "password": PASSWORD}).status_code
        == 200
    )
    assert client.get("/api/v1/enterprise/account-invitations").status_code == 403
    member_csrf = client.cookies.get(CSRF_COOKIE)
    assert member_csrf
    assert (
        client.post(
            "/api/v1/enterprise/account-invitations",
            json={"email": "other@example.test"},
            headers={"X-CSRF-Token": member_csrf},
        ).status_code
        == 403
    )
    with get_session_factory()() as session:
        item = session.scalar(select(AccountInvitation))
        assert item is not None and item.claimed_at is not None


def test_registration_rejects_privilege_injection_and_redacts_sensitive_validation(
    registration_client: TestClient,
) -> None:
    client = registration_client
    malformed = client.post(
        "/api/v1/auth/register", json=_registration() | {"role": "admin", "password": "short-secret"}
    )
    assert malformed.status_code == 422
    assert "short-secret" not in malformed.text and '"input"' not in malformed.text
    assert client.post("/api/v1/auth/register", json=_registration() | {"workbench": "internal"}).status_code == 422
    with get_session_factory()() as session:
        assert session.scalar(select(User.id)) is None


def test_registration_blocks_cross_origin_and_repeated_anonymous_attempts(registration_client: TestClient) -> None:
    client = registration_client
    assert (
        client.post(
            "/api/v1/auth/register", json=_registration(), headers={"Origin": "https://other.example"}
        ).status_code
        == 403
    )
    for index in range(10):
        assert (
            client.post("/api/v1/auth/register", json=_registration(f"fixture-{index}@example.test")).status_code == 201
        )
    limited = client.post("/api/v1/auth/register", json=_registration("another@example.test"))
    assert limited.status_code == 429 and limited.headers["Retry-After"] == "600"


@pytest.mark.parametrize("chunked", [False, True])
def test_registration_bounds_anonymous_bodies_before_parsing_or_persistence(
    registration_client: TestClient, chunked: bool
) -> None:
    content = json.dumps(_registration() | {"display_name": "x" * REGISTRATION_BODY_LIMIT}).encode()
    response = registration_client.post(
        "/api/v1/auth/register",
        content=iter([content[:100], content[100:]]) if chunked else content,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert PASSWORD not in response.text
    with get_session_factory()() as session:
        assert session.scalar(select(User.id)) is None
