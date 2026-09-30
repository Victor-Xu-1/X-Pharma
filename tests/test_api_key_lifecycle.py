from __future__ import annotations

import json
import stat
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel import api_key_cli
from pharma_intel.api_key_lifecycle import (
    ApiKeyLifecycleError,
    ApiKeyLifecycleNotFound,
    ApiKeyLifecycleService,
)
from pharma_intel.models import AgentClient, AgentClientSubject, ApiKey, AuditEvent, Tenant
from pharma_intel.security import hash_api_key, issue_api_key


class SessionContext:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> Session:
        return self.session

    def __exit__(self, *_args: object) -> None:
        return None


def _api_key(session: Session, tenant: Tenant, *, name: str = "agent-gateway") -> tuple[ApiKey, str]:
    secret, secret_hash = issue_api_key()
    key = ApiKey(
        tenant_id=tenant.id,
        name=name,
        prefix=secret[:12],
        secret_hash=secret_hash,
        scopes=["mcp:connect", "entities:read"],
    )
    session.add(key)
    session.flush()
    return key, secret


def test_rotate_revokes_old_key_and_preserves_commercial_binding(session: Session, tenant: Tenant) -> None:
    old_key, old_secret = _api_key(session, tenant)
    client = AgentClient(
        tenant_id=tenant.id,
        client_key="agent-gateway",
        oauth_client_id=old_key.id,
        display_name="Agent Gateway",
    )
    session.add(client)
    session.flush()
    subject = AgentClientSubject(
        tenant_id=tenant.id,
        agent_client_id=client.id,
        actor_type="api_key",
        subject_id=old_key.id,
    )
    session.add(subject)
    session.commit()

    rotation = ApiKeyLifecycleService(session, tenant, actor_id="SEC-42").rotate(old_key.id)
    session.commit()

    replacement = session.get(ApiKey, rotation.new_key_id)
    assert replacement is not None
    assert replacement.active is True
    assert replacement.revoked_at is None
    assert replacement.scopes == old_key.scopes
    assert hash_api_key(rotation.secret) == replacement.secret_hash
    assert hash_api_key(old_secret) == old_key.secret_hash
    assert old_key.active is False
    assert old_key.revoked_at is not None
    assert client.oauth_client_id == replacement.id
    assert subject.subject_id == replacement.id
    assert rotation.commercial_client_id == client.id

    audit = session.scalar(
        select(AuditEvent).where(
            AuditEvent.tenant_id == tenant.id,
            AuditEvent.action == "security.api_key.rotate",
        )
    )
    assert audit is not None
    assert audit.actor_id == "SEC-42"
    assert audit.details["old_key_id"] == old_key.id
    assert rotation.secret not in json.dumps(audit.details)


def test_rotate_fails_closed_for_broken_commercial_subject_binding(session: Session, tenant: Tenant) -> None:
    old_key, _ = _api_key(session, tenant)
    session.add(
        AgentClient(
            tenant_id=tenant.id,
            client_key="broken-client",
            oauth_client_id=old_key.id,
            display_name="Broken Client",
        )
    )
    session.commit()

    with pytest.raises(ApiKeyLifecycleError, match="exactly one active"):
        ApiKeyLifecycleService(session, tenant, actor_id="SEC-43").rotate(old_key.id)
    session.rollback()

    assert old_key.active is True
    assert old_key.revoked_at is None
    assert session.scalar(select(func.count(ApiKey.id)).where(ApiKey.tenant_id == tenant.id)) == 1


def test_create_list_and_revoke_api_key_without_persisting_secret(session: Session, tenant: Tenant) -> None:
    expires_at = datetime.now(UTC) + timedelta(days=90)
    service = ApiKeyLifecycleService(session, tenant, actor_id="admin-user")

    issued = service.create(
        name="research-agent",
        scopes=["mcp:connect", "entities:read", "targets:read"],
        expires_at=expires_at,
        reason="Provision research agent access",
        request_id="request-create",
    )
    session.commit()

    assert issued.secret.startswith("phk_")
    assert issued.key.secret_hash == hash_api_key(issued.secret)
    assert issued.secret not in json.dumps(issued.key.scopes)
    listed = service.list_keys()
    assert [view.key.id for view in listed] == [issued.key.id]
    assert listed[0].commercial_client_id is None

    revoke = service.revoke(
        issued.key.id,
        reason="Agent integration retired",
        request_id="request-revoke",
    )
    session.commit()

    assert revoke.key.active is False
    assert revoke.key.revoked_at is not None
    audits = list(
        session.scalars(
            select(AuditEvent).where(AuditEvent.tenant_id == tenant.id).order_by(AuditEvent.occurred_at, AuditEvent.id)
        ).all()
    )
    assert [audit.action for audit in audits] == ["security.api_key.create", "security.api_key.revoke"]
    assert issued.secret not in json.dumps([audit.details for audit in audits])


def test_api_key_lifecycle_rejects_unsafe_scopes_expiry_and_cross_tenant_access(
    session: Session,
    tenant: Tenant,
) -> None:
    service = ApiKeyLifecycleService(session, tenant, actor_id="admin-user")
    expires_at = datetime.now(UTC) + timedelta(days=90)

    with pytest.raises(ApiKeyLifecycleError, match="mcp:connect"):
        service.create(
            name="missing-mcp",
            scopes=["entities:read"],
            expires_at=expires_at,
            reason="Invalid test request",
        )
    with pytest.raises(ApiKeyLifecycleError, match="not managed"):
        service.create(
            name="wildcard",
            scopes=["mcp:connect", "*"],
            expires_at=expires_at,
            reason="Invalid test request",
        )
    with pytest.raises(ApiKeyLifecycleError, match="future"):
        service.create(
            name="expired",
            scopes=["mcp:connect", "entities:read"],
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
            reason="Invalid test request",
        )

    other_tenant = Tenant(slug="api-key-other", name="API Key Other")
    session.add(other_tenant)
    session.flush()
    other_key, _ = _api_key(session, other_tenant)
    session.commit()
    with pytest.raises(ApiKeyLifecycleNotFound):
        service.revoke(other_key.id, reason="Cross tenant attempt")


def test_revoke_deactivates_commercial_subject_binding(session: Session, tenant: Tenant) -> None:
    key, _ = _api_key(session, tenant)
    client = AgentClient(
        tenant_id=tenant.id,
        client_key="revoked-agent",
        oauth_client_id=key.id,
        display_name="Revoked Agent",
    )
    session.add(client)
    session.flush()
    subject = AgentClientSubject(
        tenant_id=tenant.id,
        agent_client_id=client.id,
        actor_type="api_key",
        subject_id=key.id,
    )
    session.add(subject)
    session.commit()

    result = ApiKeyLifecycleService(session, tenant, actor_id="admin-user").revoke(
        key.id,
        reason="Credential compromise response",
    )
    session.commit()

    assert result.commercial_client_id == client.id
    assert subject.active is False
    assert key.active is False


def test_rotation_cli_writes_secret_once_with_restricted_mode(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    old_key, _ = _api_key(session, tenant)
    session.commit()
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(mode=0o700)
    secret_output = secret_dir / "agent-gateway.key"
    monkeypatch.setattr(api_key_cli, "get_session_factory", lambda: lambda: SessionContext(session))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pharma-api-key",
            "--tenant-slug",
            tenant.slug,
            "--actor",
            "SEC-44",
            "rotate",
            "--key-id",
            old_key.id,
            "--secret-output",
            str(secret_output.resolve()),
        ],
    )

    api_key_cli.run()

    secret = secret_output.read_text(encoding="utf-8").strip()
    assert secret.startswith("phk_")
    if sys.platform != "win32":
        assert stat.S_IMODE(secret_output.stat().st_mode) == 0o600
    output = json.loads(capsys.readouterr().out)
    assert output["old_key_id"] == old_key.id
    assert output["new_key_id"] != old_key.id
    assert output["secret_output"] == str(secret_output.resolve())
    assert secret not in json.dumps(output)


def test_rotation_cli_preserves_write_error_when_cleanup_also_fails(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    old_key, _ = _api_key(session, tenant)
    session.commit()
    secret_dir = tmp_path / "secrets"
    secret_dir.mkdir(mode=0o700)
    secret_output = secret_dir / "agent-gateway.key"
    monkeypatch.setattr(api_key_cli, "get_session_factory", lambda: lambda: SessionContext(session))
    monkeypatch.setattr(
        api_key_cli,
        "_write_secret",
        lambda _path, _secret: (_ for _ in ()).throw(OSError("primary write failure")),
    )
    monkeypatch.setattr(Path, "unlink", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("cleanup failure")))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pharma-api-key",
            "--tenant-slug",
            tenant.slug,
            "--actor",
            "SEC-45",
            "rotate",
            "--key-id",
            old_key.id,
            "--secret-output",
            str(secret_output.resolve()),
        ],
    )

    with pytest.raises(SystemExit):
        api_key_cli.run()

    assert "primary write failure" in capsys.readouterr().err
    session.expire_all()
    persisted_key = session.get(ApiKey, old_key.id)
    assert persisted_key is not None
    assert persisted_key.active is True
