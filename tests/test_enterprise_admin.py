from __future__ import annotations

import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.enterprise.admin import (
    AuditCursorCodec,
    CreateGroupCommand,
    CreateUserCommand,
    EnterpriseAdminAccessDenied,
    EnterpriseAdminConflict,
    EnterpriseAdminNotFound,
    EnterpriseAdminService,
    UpdateDatasetStatusCommand,
    UpdateGroupCommand,
    UpdateGroupMembersCommand,
    UpdateUserRoleCommand,
    UpdateUserStatusCommand,
)
from pharma_intel.licensing import internal_evidence_license_policy
from pharma_intel.models import ApiKey, AuditEvent, Tenant, TenantDataset, User, UserGroup, UserRole, UserSession
from pharma_intel.security import (
    Principal,
    authenticate_api_key,
    hash_api_key,
    hash_password,
    issue_api_key,
    require_principal,
)

CURSOR_SECRET = "enterprise-audit-cursor-test-secret-32-bytes"  # noqa: S105


def _user(tenant_id: str, email: str, role: UserRole, *, active: bool = True) -> User:
    return create_account(
        tenant_id=tenant_id,
        email=email,
        normalized_email=email.casefold(),
        display_name=email.split("@", 1)[0],
        password_hash=hash_password("correct-horse-battery-staple"),
        role=role,
        active=active,
    )


def _service(session: Session, tenant_id: str, actor_id: str) -> EnterpriseAdminService:
    return EnterpriseAdminService(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_id="enterprise-test-request",
        cursor_codec=AuditCursorCodec(CURSOR_SECRET),
    )


def test_enterprise_admin_user_group_and_audit_lifecycle(session: Session, tenant: Tenant) -> None:
    actor = _user(tenant.id, "admin@example.test", UserRole.ADMIN)
    analyst = _user(tenant.id, "analyst@example.test", UserRole.ANALYST)
    other_tenant = Tenant(slug="other", name="Other Tenant")
    session.add_all([actor, analyst, other_tenant])
    session.flush()
    outsider = _user(other_tenant.id, "outside@example.test", UserRole.VIEWER)
    session.add(outsider)
    session.commit()

    service = _service(session, tenant.id, actor.id)
    overview = service.overview()
    assert overview["tenant"] == tenant
    assert overview["user_count"] == 2
    assert overview["admin_count"] == 1

    created = service.create_user(
        CreateUserCommand(
            email="Viewer@Example.Test",
            display_name="Viewer",
            role=UserRole.VIEWER,
            auth_mode="local",
            initial_password="new-user-initial-password",  # noqa: S106
        )
    )
    assert created.normalized_email == "viewer@example.test"
    changed = service.update_user_role(
        created.id,
        UpdateUserRoleCommand(created.token_version, UserRole.ANALYST, "Assigned to research operations"),
    )
    assert changed.role == UserRole.ANALYST
    assert changed.token_version == 2
    with pytest.raises(EnterpriseAdminConflict, match="refresh"):
        service.update_user_status(
            created.id,
            UpdateUserStatusCommand(1, False, "Stale administrative action"),
        )

    group = service.create_group(CreateGroupCommand("Research Operations", "Internal research analysts"))
    assert group.member_ids == ()
    populated = service.update_group_members(
        group.group.id,
        UpdateGroupMembersCommand(group.group.version, (analyst.id, created.id), "Initial team assignment"),
    )
    assert populated.member_ids == tuple(sorted((analyst.id, created.id)))
    assert populated.group.version == 2
    renamed = service.update_group(
        populated.group.id,
        UpdateGroupCommand(
            populated.group.version,
            "Research Intelligence",
            "Curated intelligence team",
            True,
            "Operating model update",
        ),
    )
    assert renamed.group.name == "Research Intelligence"
    assert renamed.group.version == 3

    with pytest.raises(EnterpriseAdminConflict, match="active users in this tenant"):
        service.update_group_members(
            renamed.group.id,
            UpdateGroupMembersCommand(renamed.group.version, (outsider.id,), "Cross tenant attempt"),
        )
    assert {item.id for item in service.list_users()} == {actor.id, analyst.id, created.id}
    assert session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant.id).count() == 5

    first_page = service.list_audit_events(
        limit=2,
        cursor=None,
        action=None,
        outcome="success",
        actor_type="user",
    )
    assert len(first_page.items) == 2
    assert first_page.next_cursor is not None
    second_page = service.list_audit_events(
        limit=2,
        cursor=first_page.next_cursor,
        action=None,
        outcome="success",
        actor_type="user",
    )
    assert {item.id for item in first_page.items}.isdisjoint(item.id for item in second_page.items)
    with pytest.raises(EnterpriseAdminConflict, match="invalid or expired"):
        service.list_audit_events(
            limit=2,
            cursor=f"{first_page.next_cursor}x",
            action=None,
            outcome="success",
            actor_type="user",
        )
    with pytest.raises(EnterpriseAdminConflict, match="invalid or expired"):
        service.list_audit_events(
            limit=2,
            cursor=first_page.next_cursor,
            action="enterprise.group.updated",
            outcome="success",
            actor_type="user",
        )


def test_enterprise_admin_protects_self_last_admin_and_tenant_boundaries(
    session: Session,
    tenant: Tenant,
) -> None:
    actor = _user(tenant.id, "admin@example.test", UserRole.ADMIN)
    session.add(actor)
    session.commit()
    service = _service(session, tenant.id, actor.id)

    with pytest.raises(EnterpriseAdminConflict, match="own role"):
        service.update_user_role(
            actor.id,
            UpdateUserRoleCommand(actor.token_version, UserRole.ANALYST, "Unsafe self demotion"),
        )
    operator = _user(tenant.id, "operator@example.test", UserRole.ANALYST)
    session.add(operator)
    session.commit()
    operator_service = _service(session, tenant.id, operator.id)
    with pytest.raises(EnterpriseAdminAccessDenied, match="active organization administrator"):
        operator_service.update_user_status(
            actor.id,
            UpdateUserStatusCommand(actor.token_version, False, "Attempt to remove final administrator"),
        )
    with pytest.raises(EnterpriseAdminNotFound):
        service.update_group(
            "missing-group",
            UpdateGroupCommand(1, "Missing", "", True, "Missing resource check"),
        )


def test_enterprise_admin_governs_datasets_and_individual_sessions(session: Session, tenant: Tenant) -> None:
    actor = _user(tenant.id, "session-admin@example.test", UserRole.ADMIN)
    analyst = _user(tenant.id, "session-analyst@example.test", UserRole.ANALYST)
    dataset = TenantDataset(
        tenant_id=tenant.id,
        dataset_key="session_test",
        display_name="Session test dataset",
        license_policy=internal_evidence_license_policy(source="enterprise-test"),
        required_scopes=["evidence:read"],
    )
    session.add_all([actor, analyst, dataset])
    session.flush()
    now = datetime.now(UTC)
    active_session = UserSession(
        tenant_id=tenant.id,
        user_id=analyst.id,
        user_agent_sha256="a" * 64,
        issued_at=now,
        expires_at=now + timedelta(hours=8),
    )
    session.add(active_session)
    session.commit()
    service = _service(session, tenant.id, actor.id)

    disabled = service.update_dataset_status(
        dataset.id,
        UpdateDatasetStatusCommand(dataset.version, False, "License delivery paused by administrator"),
    )
    assert disabled.active is False
    assert disabled.version == 2
    with pytest.raises(EnterpriseAdminConflict, match="refresh"):
        service.update_dataset_status(
            dataset.id,
            UpdateDatasetStatusCommand(1, True, "Stale dataset update"),
        )
    enabled = service.update_dataset_status(
        dataset.id,
        UpdateDatasetStatusCommand(2, True, "Current license was revalidated"),
    )
    assert enabled.active is True
    assert enabled.version == 3

    assert [item.session.id for item in service.list_sessions()] == [active_session.id]
    revoked = service.revoke_session(active_session.id, reason="Analyst device access ended")
    assert revoked.session.revoked_at is not None
    assert revoked.session.revoked_by_user_id == actor.id
    assert service.revoke_session(active_session.id, reason="Idempotent retry").session.revoked_at is not None


def test_enterprise_api_requires_human_admin_and_enforces_tenant_scope(
    session: Session,
    tenant: Tenant,
) -> None:
    actor = _user(tenant.id, "admin@example.test", UserRole.ADMIN)
    other_tenant = Tenant(slug="other-api", name="Other API Tenant")
    session.add_all([actor, other_tenant])
    session.flush()
    outside_group = UserGroup(tenant_id=other_tenant.id, name="Outside", normalized_name="outside")
    dataset = TenantDataset(
        tenant_id=tenant.id,
        dataset_key="api_dataset",
        display_name="API dataset",
        license_policy=internal_evidence_license_policy(source="enterprise-api-test"),
        required_scopes=["evidence:read"],
    )
    session.add_all([outside_group, dataset])
    session.flush()
    now = datetime.now(UTC)
    current_session = UserSession(
        tenant_id=tenant.id,
        user_id=actor.id,
        user_agent_sha256="b" * 64,
        issued_at=now,
        expires_at=now + timedelta(hours=8),
    )
    other_session = UserSession(
        tenant_id=tenant.id,
        user_id=actor.id,
        user_agent_sha256="c" * 64,
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(hours=7),
    )
    session.add_all([current_session, other_session])
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def admin_override() -> Principal:
        return Principal(tenant.id, actor.id, "user", frozenset({"*"}), session_id=current_session.id)

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = admin_override
    try:
        with TestClient(app) as client:
            overview = client.get("/api/v1/enterprise/overview")
            assert overview.status_code == 200
            assert overview.json()["tenant"]["id"] == tenant.id
            platform = client.get("/api/v1/enterprise/platform")
            assert platform.status_code == 200
            assert {item["service_id"] for item in platform.json()["services"]} >= {"api", "mcp"}
            assert platform.json()["workflow"]["engine"] == "temporal"
            datasets = client.get("/api/v1/enterprise/datasets")
            assert datasets.status_code == 200
            assert datasets.json()[0]["license_current"] is True
            disabled_dataset = client.post(
                f"/api/v1/enterprise/datasets/{dataset.id}/status",
                json={
                    "expected_version": 1,
                    "active": False,
                    "reason": "API dataset delivery pause",
                },
            )
            assert disabled_dataset.status_code == 200
            assert disabled_dataset.json()["version"] == 2
            sessions = client.get("/api/v1/enterprise/sessions")
            assert sessions.status_code == 200
            assert next(item for item in sessions.json() if item["id"] == current_session.id)["current"] is True
            revoked_session = client.post(
                f"/api/v1/enterprise/sessions/{other_session.id}/revoke",
                json={"reason": "Remote administrator session revocation"},
            )
            assert revoked_session.status_code == 200
            assert revoked_session.json()["revoked_at"] is not None
            created = client.post(
                "/api/v1/enterprise/groups",
                json={"name": "Clinical Intelligence", "description": "Clinical evidence team"},
            )
            assert created.status_code == 201
            assert created.json()["version"] == 1
            created_user = client.post(
                "/api/v1/enterprise/users",
                json={
                    "email": "api-viewer@example.test",
                    "display_name": "API Viewer",
                    "role": "viewer",
                    "initial_password": "api-viewer-initial-password",
                },
            )
            assert created_user.status_code == 201
            assert created_user.json()["email"] == "api-viewer@example.test"
            assert "initial_password" not in created_user.json()
            invalid_user = client.post(
                "/api/v1/enterprise/users",
                json={
                    "email": "invalid-name@example.test",
                    "display_name": "???????????",
                    "role": "viewer",
                    "initial_password": "invalid-name-initial-password",
                },
            )
            assert invalid_user.status_code == 422
            users = client.get("/api/v1/enterprise/users")
            assert users.status_code == 200
            assert {item["email"] for item in users.json()} == {actor.email, "api-viewer@example.test"}
            audit = client.get(
                "/api/v1/enterprise/audit-events",
                params={"action": "enterprise.user.created", "actor_type": "user"},
            )
            assert audit.status_code == 200
            assert len(audit.json()["items"]) == 1
            assert audit.json()["items"][0]["resource_id"] == created_user.json()["id"]
            assert (
                client.put(
                    f"/api/v1/enterprise/groups/{outside_group.id}",
                    json={
                        "expected_version": 1,
                        "name": "Outside",
                        "description": "",
                        "active": True,
                        "reason": "Cross tenant boundary check",
                    },
                ).status_code
                == 404
            )

            app.dependency_overrides[require_principal] = lambda: Principal(
                tenant.id,
                actor.id,
                "user",
                frozenset({"entities:read"}),
            )
            assert client.get("/api/v1/enterprise/overview").status_code == 403
            app.dependency_overrides[require_principal] = lambda: Principal(
                tenant.id,
                "agent-key",
                "api_key",
                frozenset({"*"}),
            )
            assert client.get("/api/v1/enterprise/overview").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_enterprise_api_key_lifecycle_is_tenant_scoped_and_secret_is_one_time(
    session: Session,
    tenant: Tenant,
) -> None:
    actor = _user(tenant.id, "key-admin@example.test", UserRole.ADMIN)
    other_tenant = Tenant(slug="other-key-api", name="Other Key API Tenant")
    session.add_all([actor, other_tenant])
    session.flush()
    other_secret, other_hash = issue_api_key()
    other_key = ApiKey(
        tenant_id=other_tenant.id,
        name="outside-agent",
        prefix=other_secret[:12],
        secret_hash=other_hash,
        scopes=["mcp:connect", "entities:read"],
        expires_at=datetime.now(UTC) + timedelta(days=90),
    )
    session.add(other_key)
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def admin_override() -> Principal:
        return Principal(tenant.id, actor.id, "user", frozenset({"*"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = admin_override
    try:
        with TestClient(app) as client:
            policy = client.get("/api/v1/enterprise/api-keys")
            assert policy.status_code == 200
            assert policy.json()["items"] == []
            assert policy.json()["required_scope"] == "mcp:connect"
            assert "*" not in policy.json()["allowed_scopes"]

            expires_at = datetime.now(UTC) + timedelta(days=90)
            created = client.post(
                "/api/v1/enterprise/api-keys",
                json={
                    "name": "research-agent",
                    "scopes": ["mcp:connect", "entities:read", "targets:read"],
                    "expires_at": expires_at.isoformat(),
                    "reason": "Provision approved research integration",
                },
            )
            assert created.status_code == 201
            assert created.headers["cache-control"] == "no-store"
            created_payload = created.json()
            secret = created_payload.pop("secret")
            assert secret.startswith("phk_")
            assert "secret_hash" not in created_payload
            persisted = session.get(ApiKey, created_payload["id"])
            assert persisted is not None
            assert persisted.secret_hash == hash_api_key(secret)

            listed = client.get("/api/v1/enterprise/api-keys")
            assert listed.status_code == 200
            assert listed.json()["items"][0]["id"] == created_payload["id"]
            assert secret not in listed.text

            rotated = client.post(
                f"/api/v1/enterprise/api-keys/{created_payload['id']}/rotate",
                json={
                    "name": "research-agent-rotated",
                    "expires_at": (datetime.now(UTC) + timedelta(days=120)).isoformat(),
                    "reason": "Scheduled credential rotation",
                },
            )
            assert rotated.status_code == 200
            assert rotated.headers["cache-control"] == "no-store"
            rotated_secret = rotated.json()["secret"]
            rotated_id = rotated.json()["id"]
            assert rotated_secret != secret
            assert authenticate_api_key(session, secret) is None
            assert authenticate_api_key(session, rotated_secret) is not None

            cross_tenant = client.post(
                f"/api/v1/enterprise/api-keys/{other_key.id}/revoke",
                json={"reason": "Cross tenant attempt"},
            )
            assert cross_tenant.status_code == 404

            revoked = client.post(
                f"/api/v1/enterprise/api-keys/{rotated_id}/revoke",
                json={"reason": "Retire research integration"},
            )
            assert revoked.status_code == 200
            assert revoked.json()["active"] is False
            assert authenticate_api_key(session, rotated_secret) is None

            invalid_scope = client.post(
                "/api/v1/enterprise/api-keys",
                json={
                    "name": "unsafe-key",
                    "scopes": ["mcp:connect", "*"],
                    "expires_at": expires_at.isoformat(),
                    "reason": "Reject wildcard scope",
                },
            )
            assert invalid_scope.status_code == 422

            audit_details = [
                event.details
                for event in session.query(AuditEvent)
                .filter(AuditEvent.tenant_id == tenant.id, AuditEvent.action.like("security.api_key.%"))
                .all()
            ]
            assert {event.action for event in session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant.id)} >= {
                "security.api_key.create",
                "security.api_key.rotate",
                "security.api_key.revoke",
            }
            assert secret not in json.dumps(audit_details)
            assert rotated_secret not in json.dumps(audit_details)

            app.dependency_overrides[require_principal] = lambda: Principal(
                tenant.id,
                actor.id,
                "user",
                frozenset({"entities:read"}),
            )
            assert client.get("/api/v1/enterprise/api-keys").status_code == 403
    finally:
        app.dependency_overrides.clear()
