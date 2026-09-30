from __future__ import annotations

import base64
import hashlib
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.config import Settings
from pharma_intel.db import get_session
from pharma_intel.human_oidc import (
    OIDC_TRANSACTION_COOKIE,
    OidcAuthenticationError,
    OidcIdTokenVerifier,
    create_oidc_authorization,
    read_oidc_transaction,
)
from pharma_intel.models import Tenant, User, UserRole
from pharma_intel.security import SESSION_COOKIE, hash_password


def _b64int(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _signing_material() -> tuple[bytes, dict[str, str]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private_key.public_key().public_numbers()
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    jwk = {
        "kty": "RSA",
        "kid": "human-test-key",
        "use": "sig",
        "alg": "RS256",
        "n": _b64int(numbers.n),
        "e": _b64int(numbers.e),
    }
    return private_pem, jwk


def _settings() -> Settings:
    return Settings(
        jwt_secret="human-oidc-transaction-test-secret",  # noqa: S106
        human_auth_mode="oidc",
        human_oidc_issuer_url="https://identity.example.test",
        human_oidc_authorization_url="https://identity.example.test/authorize",
        human_oidc_token_url="https://identity.example.test/token",  # noqa: S106
        human_oidc_jwks_url="https://identity.example.test/jwks",
        human_oidc_client_id="pharma-human-client",
        human_oidc_client_secret="oidc-client-test-secret",  # noqa: S106
        human_oidc_redirect_uri="https://workspace.example.test/api/v1/auth/oidc/callback",
        public_base_url="https://workspace.example.test",
    )


def _id_token(private_key: bytes, settings: Settings, tenant_id: str, nonce: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "iss": settings.human_oidc_issuer_url,
            "sub": "subject-123",
            "aud": settings.human_oidc_client_id,
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "nonce": nonce,
            "tenant_id": tenant_id,
            "email": "oidc.user@example.test",
            "email_verified": True,
            "name": "OIDC User",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "human-test-key"},
    )


def test_authorization_uses_state_nonce_and_s256_pkce() -> None:
    settings = _settings()
    authorization = create_oidc_authorization(settings)
    query = parse_qs(urlparse(authorization.url).query)
    transaction = read_oidc_transaction(settings, authorization.transaction_token, query["state"][0])
    expected_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(transaction["code_verifier"].encode("ascii")).digest())
        .rstrip(b"=")
        .decode()
    )

    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == [expected_challenge]
    assert query["nonce"] == [transaction["nonce"]]
    with pytest.raises(OidcAuthenticationError, match="state"):
        read_oidc_transaction(settings, authorization.transaction_token, "wrong-state-value-for-test")


@pytest.mark.anyio
async def test_id_token_verifier_checks_signature_issuer_audience_and_nonce() -> None:
    settings = _settings()
    private_key, jwk = _signing_material()
    token = _id_token(private_key, settings, "tenant-1", "expected-nonce")
    with respx.mock:
        respx.get(settings.human_oidc_jwks_url).mock(return_value=httpx.Response(200, json={"keys": [jwk]}))
        verifier = OidcIdTokenVerifier(settings)
        claims = await verifier.verify(token, "expected-nonce")
        assert claims["sub"] == "subject-123"
        with pytest.raises(OidcAuthenticationError, match="nonce"):
            await verifier.verify(token, "different-nonce")


def test_oidc_authorization_code_callback_creates_application_session(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    private_key, jwk = _signing_material()
    user = User(
        tenant_id=tenant.id,
        email="oidc.user@example.test",
        normalized_email="oidc.user@example.test",
        display_name="OIDC User",
        password_hash=hash_password("unusable-local-password"),
        role=UserRole.ANALYST,
        oidc_issuer=settings.human_oidc_issuer_url,
        oidc_subject="subject-123",
    )
    session.add(user)
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    monkeypatch.setattr("pharma_intel.api.get_settings", lambda: settings)
    monkeypatch.setattr("pharma_intel.security.get_settings", lambda: settings)
    monkeypatch.setattr("pharma_intel.human_oidc._VERIFIER_CACHE", {})
    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as client, respx.mock:
            start = client.get("/api/v1/auth/oidc/login", follow_redirects=False)
            assert start.status_code == 302
            query = parse_qs(urlparse(start.headers["location"]).query)
            transaction_cookie = client.cookies.get(OIDC_TRANSACTION_COOKIE)
            assert transaction_cookie
            transaction = read_oidc_transaction(settings, transaction_cookie, query["state"][0])
            token = _id_token(private_key, settings, tenant.id, transaction["nonce"])
            token_route = respx.post(settings.human_oidc_token_url).mock(
                return_value=httpx.Response(200, json={"id_token": token, "token_type": "Bearer"})
            )
            respx.get(settings.human_oidc_jwks_url).mock(return_value=httpx.Response(200, json={"keys": [jwk]}))

            callback = client.get(
                "/api/v1/auth/oidc/callback",
                params={"code": "authorization-code", "state": query["state"][0]},
                follow_redirects=False,
            )
            assert callback.status_code == 302
            assert callback.headers["location"] == "https://workspace.example.test/"
            assert client.cookies.get(SESSION_COOKIE)
            assert client.get("/api/v1/auth/me").json()["email"] == user.email
            request_form = parse_qs(token_route.calls[0].request.content.decode())
            assert request_form["code_verifier"] == [transaction["code_verifier"]]
    finally:
        app.dependency_overrides.clear()
