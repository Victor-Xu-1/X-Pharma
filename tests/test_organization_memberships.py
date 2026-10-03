from __future__ import annotations

import secrets
from collections.abc import Generator

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.models import Entity, EntityType, OrganizationMembership, ReviewStatus, Tenant, User, UserRole
from pharma_intel.security import CSRF_COOKIE, SESSION_COOKIE, hash_password


@pytest.fixture
def membership_client(session: Session) -> Generator[TestClient]:
    def override(request: Request) -> Generator[Session]:
        request.state.db_session = session
        yield session

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


def _account(session: Session, tenant: Tenant, name: str, password: str) -> User:
    account = create_account(
        tenant_id=tenant.id,
        email=f"{name}@example.test",
        normalized_email=f"{name}@example.test",
        display_name=name,
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
    )
    session.add(account)
    session.commit()
    return account


def _login(client: TestClient, account: User, password: str, tenant_id: str | None = None) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": account.email,
            "password": password,
            "organization_id": tenant_id,
        },
    )
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": client.cookies[CSRF_COOKIE]}


def _invitation(client: TestClient, headers: dict[str, str], account: User) -> str:
    response = client.post("/api/v1/enterprise/account-invitations", headers=headers, json={"email": account.email})
    assert response.status_code == 201, response.text
    return str(response.json()["code"])


def test_explicit_join_switch_and_org_status_preserve_identity_and_isolate_permissions(
    session: Session,
    tenant: Tenant,
    membership_client: TestClient,
) -> None:
    second = Tenant(slug="membership-second", name="Second organization")
    session.add(second)
    session.commit()
    password = secrets.token_urlsafe(24)
    account = _account(session, tenant, "shared-identity", password)
    sponsor = _account(session, second, "second-sponsor", password)
    for organization in (tenant, second):
        session.add(
            Entity(
                tenant_id=organization.id,
                entity_type=EntityType.TARGET,
                name=f"Isolated target {organization.slug}",
                normalized_name=organization.slug,
                review_status=ReviewStatus.VERIFIED,
            )
        )
    session.commit()
    client = membership_client
    with TestClient(app) as admin_client:
        admin_headers = _login(admin_client, sponsor, password)
        code = _invitation(admin_client, admin_headers, account)
        headers = _login(client, account, password)
        assert len(client.get("/api/v1/auth/organizations").json()) == 1
        assert session.get(OrganizationMembership, (second.id, account.id)) is None
        refused = client.post(
            "/api/v1/auth/organizations/join", headers=headers, json={"invitation_code": code, "confirmed": False}
        )
        assert refused.status_code == 422
        assert session.get(OrganizationMembership, (second.id, account.id)) is None
        joined = client.post(
            "/api/v1/auth/organizations/join", headers=headers, json={"invitation_code": code, "confirmed": True}
        )
        assert joined.status_code == 201 and joined.json()["role"] == "analyst"
        assert client.get("/api/v1/auth/me").json()["tenant_id"] == tenant.id
        assert len(client.get("/api/v1/auth/organizations").json()) == 2
        old_cookie = client.cookies[SESSION_COOKIE]
        switched = client.post(
            "/api/v1/auth/organizations/switch", headers=headers, json={"organization_id": second.id}
        )
        assert switched.status_code == 200
        assert switched.json()["id"] == account.id and switched.json()["role"] == "analyst"
        assert switched.json()["tenant_id"] == second.id
        stale = client.get("/api/v1/enterprise/users", headers={"X-Organization-ID": tenant.id})
        assert stale.status_code == 409 and stale.headers["X-Session-Context"] == "changed"
        assert client.get("/api/v1/enterprise/users").status_code == 403
        entities = client.get("/api/v1/entities").json()["items"]
        assert {item["name"] for item in entities} == {f"Isolated target {second.slug}"}
        new_cookie = client.cookies[SESSION_COOKIE]
        client.cookies.set(SESSION_COOKIE, old_cookie, domain="testserver.local", path="/")
        assert client.get("/api/v1/auth/me").status_code == 401
        client.cookies.set(SESSION_COOKIE, new_cookie, domain="testserver.local", path="/")
        assert client.get("/api/v1/auth/me").status_code == 200
        member = session.get(OrganizationMembership, (second.id, account.id))
        assert member is not None
        changed = admin_client.post(
            f"/api/v1/enterprise/users/{account.id}/status",
            headers=admin_headers,
            json={
                "active": False,
                "expected_token_version": member.token_version,
                "reason": "Organization membership suspended",
            },
        )
        assert changed.status_code == 200, changed.text
        assert client.get("/api/v1/auth/me").status_code == 401
        _login(client, account, password, tenant.id)
        assert client.get("/api/v1/auth/me").json()["role"] == "admin"
        assert client.get("/api/v1/enterprise/users").status_code == 200
        assert session.get(User, account.id) is not None and account.home_tenant_id == tenant.id
        assert session.scalar(select(Entity.id).where(Entity.tenant_id == tenant.id)) is not None


def test_password_change_invalidates_other_organization_sessions_but_renews_current_session(
    session: Session,
    tenant: Tenant,
    membership_client: TestClient,
) -> None:
    second = Tenant(slug="password-second", name="Password second organization")
    session.add(second)
    session.commit()
    password = secrets.token_urlsafe(24)
    account = _account(session, tenant, "password-member", password)
    session.add(OrganizationMembership(tenant_id=second.id, account=account, role=UserRole.VIEWER))
    session.commit()
    client = membership_client
    headers = _login(client, account, password, tenant.id)
    with TestClient(app) as other:
        _login(other, account, password, second.id)
        changed = client.post(
            "/api/v1/auth/me/password",
            headers=headers,
            json={"current_password": password, "new_password": secrets.token_urlsafe(32)},
        )
        assert changed.status_code == 204, changed.text
        assert client.get("/api/v1/auth/me").status_code == 200
        assert other.get("/api/v1/auth/me").status_code == 401


def test_verified_existing_account_without_active_membership_can_accept_email_bound_invitation(
    session: Session,
    tenant: Tenant,
    membership_client: TestClient,
) -> None:
    second = Tenant(slug="recovery-second", name="Recovery second organization")
    session.add(second)
    session.commit()
    password = secrets.token_urlsafe(24)
    account = _account(session, tenant, "recovery-member", password)
    account.memberships[0].active = False
    sponsor = _account(session, second, "recovery-sponsor", password)
    session.commit()
    client = membership_client
    headers = _login(client, sponsor, password)
    code = _invitation(client, headers, account)
    client.cookies.clear()
    assert client.post("/api/v1/auth/login", json={"email": account.email, "password": password}).status_code == 403
    command = {"email": account.email, "password": password, "invitation_code": code, "confirmed": True}
    assert client.post("/api/v1/auth/invitations/accept", json={**command, "confirmed": False}).status_code == 422
    assert (
        client.post(
            "/api/v1/auth/invitations/accept", json={**command, "password": secrets.token_urlsafe(24)}
        ).status_code
        == 401
    )
    joined = client.post("/api/v1/auth/invitations/accept", json=command)
    assert joined.status_code == 200 and joined.json()["id"] == account.id
    assert joined.json()["tenant_id"] == second.id and joined.json()["role"] == "analyst"
    assert client.get("/api/v1/auth/me").status_code == 200
    assert account.home_tenant_id == tenant.id and not account.memberships[0].active
    assert session.get(OrganizationMembership, (tenant.id, account.id)) is not None
