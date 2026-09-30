from __future__ import annotations

from datetime import UTC, datetime

import jwt
import pytest
from sqlalchemy.orm import Session

from pharma_intel.config import get_settings
from pharma_intel.dataset_repository import DatasetAccessDenied, DatasetRepository, DatasetSelectionError
from pharma_intel.licensing import internal_evidence_license_policy
from pharma_intel.mcp_auth import DatabaseApiKeyTokenVerifier
from pharma_intel.models import ApiKey, Tenant, TenantDataset
from pharma_intel.security import Principal, issue_api_key


def test_pyjwt_preverification_deep_payload_is_a_controlled_decode_failure() -> None:
    header = jwt.utils.base64url_encode(b'{"alg":"HS256","typ":"JWT"}')
    payload = jwt.utils.base64url_encode(b"[" * 20_000 + b"0" + b"]" * 20_000)
    signature = jwt.utils.base64url_encode(b"unused pre-verification signature")
    token = b".".join((header, payload, signature)).decode("ascii")
    with pytest.raises(jwt.DecodeError):
        jwt.decode(token, options={"verify_signature": False})


@pytest.mark.anyio
async def test_mcp_api_key_is_exchanged_for_short_lived_internal_token(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret, secret_hash = issue_api_key()
    key = ApiKey(
        tenant_id=tenant.id,
        name="agent",
        prefix=secret[:12],
        secret_hash=secret_hash,
        scopes=["mcp:connect", "entities:read"],
    )
    session.add(key)
    session.commit()

    class SessionContext:
        def __enter__(self) -> Session:
            return session

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr("pharma_intel.mcp_auth.get_session_factory", lambda: lambda: SessionContext())
    access = await DatabaseApiKeyTokenVerifier(get_settings()).verify_token(secret)

    assert access is not None
    assert access.token != secret
    claims = jwt.decode(
        access.token,
        get_settings().effective_internal_service_jwt_secret,
        algorithms=["HS256"],
        issuer=get_settings().internal_token_issuer,
        audience=get_settings().internal_token_audience,
    )
    assert claims["tenant_id"] == tenant.id
    assert claims["sub"] == key.id
    assert claims["client_id"] == key.id
    assert claims["type"] == "internal_service"
    assert access.client_id == key.id
    assert get_settings().mcp_required_scope in access.scopes
    assert access.expires_at is not None and access.expires_at > int(datetime.now(UTC).timestamp())

    key.revoked_at = datetime.now(UTC)
    session.commit()
    assert await DatabaseApiKeyTokenVerifier(get_settings()).verify_token(secret) is None


@pytest.mark.anyio
async def test_wildcard_api_key_advertises_required_mcp_scope(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret, secret_hash = issue_api_key()
    session.add(
        ApiKey(
            tenant_id=tenant.id,
            name="admin-agent",
            prefix=secret[:12],
            secret_hash=secret_hash,
            scopes=["*"],
        )
    )
    session.commit()

    class SessionContext:
        def __enter__(self) -> Session:
            return session

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr("pharma_intel.mcp_auth.get_session_factory", lambda: lambda: SessionContext())
    access = await DatabaseApiKeyTokenVerifier(get_settings()).verify_token(secret)

    assert access is not None
    assert get_settings().mcp_required_scope in access.scopes


def test_dataset_ids_are_resolved_server_side_and_scope_checked(session: Session, tenant: Tenant) -> None:
    session.add_all(
        [
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key="literature",
                display_name="Literature",
                ragflow_dataset_id="private-ragflow-id",
                required_scopes=["evidence:read"],
                license_policy=internal_evidence_license_policy(source="test"),
            ),
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key="licensed",
                display_name="Licensed",
                ragflow_dataset_id="licensed-private-id",
                required_scopes=["licensed:read"],
                license_policy=internal_evidence_license_policy(source="test"),
            ),
        ]
    )
    session.commit()
    principal = Principal(tenant.id, "agent", "agent", frozenset({"evidence:read"}))
    repository = DatasetRepository(session, tenant.id)

    resolved = repository.resolve_for_principal(principal, ["literature"])

    assert [item.key for item in resolved] == ["literature"]
    with pytest.raises(DatasetAccessDenied):
        repository.resolve_for_principal(principal, ["licensed"])
    with pytest.raises(DatasetSelectionError):
        repository.resolve_for_principal(principal, ["unknown"])

    all_authorized = repository.resolve_for_principal(principal, [])
    assert [item.key for item in all_authorized] == ["literature"]


def test_dataset_license_policy_fails_closed_for_invalid_or_disallowed_channels(
    session: Session,
    tenant: Tenant,
) -> None:
    web_only_policy = internal_evidence_license_policy(source="test")
    web_only_policy["permitted_channels"] = ["web"]
    session.add_all(
        [
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key="web-only",
                display_name="Web Only",
                required_scopes=["evidence:read"],
                license_policy=web_only_policy,
            ),
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key="invalid-policy",
                display_name="Invalid Policy",
                required_scopes=["evidence:read"],
                license_policy={},
            ),
        ]
    )
    session.commit()
    repository = DatasetRepository(session, tenant.id)
    agent = Principal(
        tenant.id,
        "agent",
        "agent",
        frozenset({"evidence:read"}),
    )
    human = Principal(
        tenant.id,
        "user",
        "user",
        frozenset({"evidence:read"}),
    )

    with pytest.raises(DatasetAccessDenied):
        repository.resolve_for_principal(agent, ["web-only"])
    assert repository.resolve_for_principal(human, ["web-only"])[0].key == "web-only"
    with pytest.raises(DatasetSelectionError, match="invalid license policy"):
        repository.resolve_for_principal(agent, ["invalid-policy"])
