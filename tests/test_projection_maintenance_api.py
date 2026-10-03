from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.api import app
from pharma_intel.config import get_settings
from pharma_intel.db import get_session
from pharma_intel.models import AuditEvent, Tenant, UserRole
from pharma_intel.security import PLATFORM_PROJECTION_SCOPE, Principal, hash_password, require_principal


def test_projection_maintenance_requires_explicit_platform_operator_scope(
    session: Session,
    tenant: Tenant,
) -> None:
    administrator = create_account(
        tenant_id=tenant.id,
        email="operator@example.test",
        normalized_email="operator@example.test",
        display_name="Projection operator",
        password_hash=hash_password("projection-operator-test-password"),
        role=UserRole.ADMIN,
    )
    session.add(administrator)
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    principal = Principal(tenant.id, administrator.id, "user", frozenset({"*"}))

    def principal_override() -> Principal:
        return principal

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            access = client.get("/api/v1/governance/projection-maintenance-access")
            assert access.status_code == 200
            assert access.json() == {"allowed": False}
            denied = client.post(
                "/api/v1/governance/projection-maintenance-jobs",
                json={"operation": "consistency_check"},
            )
            assert denied.status_code == 403
            assert denied.json()["detail"] == "Insufficient platform scope"

            principal = Principal(
                tenant.id,
                administrator.id,
                "user",
                frozenset({"*", PLATFORM_PROJECTION_SCOPE}),
            )
            access = client.get("/api/v1/governance/projection-maintenance-access")
            assert access.status_code == 200
            assert access.json() == {"allowed": True}
            accepted = client.post(
                "/api/v1/governance/projection-maintenance-jobs",
                json={"operation": "consistency_check"},
            )
            assert accepted.status_code == 202
            body = accepted.json()
            assert body["operation"] == "consistency_check"
            assert body["status"] == "queued"

            listed = client.get("/api/v1/governance/projection-maintenance-jobs")
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()] == [body["id"]]
    finally:
        app.dependency_overrides.clear()

    audit = session.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "search.projection_maintenance.requested",
            AuditEvent.resource_id == body["id"],
        )
    )
    assert audit is not None
    assert audit.actor_id == administrator.id
    assert audit.details == {"operation": "consistency_check", "global": True}


def test_projection_maintenance_rejects_non_human_platform_credentials(
    session: Session,
    tenant: Tenant,
) -> None:
    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(
            tenant.id,
            "automation-key",
            "api_key",
            frozenset({"*", PLATFORM_PROJECTION_SCOPE}),
        )

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/governance/projection-maintenance-jobs",
                json={"operation": "consistency_check"},
            )
        assert response.status_code == 403
        assert response.json()["detail"] == "A human administrator account is required"
    finally:
        app.dependency_overrides.clear()


def test_configured_platform_operator_receives_exact_scope_through_human_session(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    password = "configured-platform-operator-password"  # noqa: S105
    administrator = create_account(
        tenant_id=tenant.id,
        email="configured-operator@example.test",
        normalized_email="configured-operator@example.test",
        display_name="Configured projection operator",
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
    )
    session.add(administrator)
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    monkeypatch.setenv("PLATFORM_OPERATOR_USER_IDS", administrator.id)
    get_settings.cache_clear()
    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/auth/login",
                json={"email": administrator.email, "password": password},
            )
            assert login.status_code == 200
            csrf = client.cookies.get("pharma_csrf")
            assert csrf
            accepted = client.post(
                "/api/v1/governance/projection-maintenance-jobs",
                json={"operation": "consistency_check"},
                headers={"X-CSRF-Token": csrf},
            )
            assert accepted.status_code == 202
            access = client.get("/api/v1/governance/projection-maintenance-access")
            assert access.status_code == 200
            assert access.json() == {"allowed": True}
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
