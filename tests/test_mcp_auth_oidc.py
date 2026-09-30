from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from pharma_intel.config import Settings
from pharma_intel.mcp_auth import OidcJwksTokenVerifier


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
    return private_pem, {
        "kty": "RSA",
        "kid": "mcp-test-key",
        "use": "sig",
        "alg": "RS256",
        "n": _b64int(numbers.n),
        "e": _b64int(numbers.e),
    }


def _settings() -> Settings:
    return Settings(
        internal_service_jwt_secret="mcp-internal-test-secret-at-least-32-bytes",  # noqa: S106
        mcp_token_verifier_mode="oidc",  # noqa: S106
        mcp_auth_issuer_url="https://identity.example.test",
        mcp_resource_server_url="https://mcp.example.test/mcp",
        mcp_oidc_jwks_url="https://identity.example.test/jwks",
        mcp_oidc_audience="pharma-mcp",
    )


def _token(
    private_key: bytes,
    settings: Settings,
    *,
    include_client: bool,
    confirmation: dict[str, str] | None = None,
) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "iss": settings.mcp_auth_issuer_url,
        "sub": "agent-subject",
        "aud": settings.mcp_oidc_audience,
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "tenant_id": "tenant-1",
        "scope": "mcp:connect entities:read",
    }
    if include_client:
        claims["azp"] = "registered-client-1"
    if confirmation is not None:
        claims["cnf"] = confirmation
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "mcp-test-key"})


@pytest.mark.anyio
async def test_oidc_mcp_token_binds_verified_client_and_rejects_missing_client_claim() -> None:
    settings = _settings()
    private_key, jwk = _signing_material()
    with respx.mock:
        respx.get(settings.mcp_oidc_jwks_url).mock(return_value=httpx.Response(200, json={"keys": [jwk]}))
        verifier = OidcJwksTokenVerifier(settings)
        access = await verifier.verify_token(_token(private_key, settings, include_client=True))
        missing_client = await verifier.verify_token(_token(private_key, settings, include_client=False))

    assert access is not None
    assert access.client_id == "registered-client-1"
    claims = jwt.decode(
        access.token,
        settings.internal_service_jwt_secret,
        algorithms=["HS256"],
        issuer=settings.internal_token_issuer,
        audience=settings.internal_token_audience,
    )
    assert claims["client_id"] == "registered-client-1"
    assert missing_client is None


@pytest.mark.anyio
async def test_oidc_mcp_token_requires_and_propagates_verified_confirmation_key() -> None:
    settings = _settings().model_copy(update={"mcp_require_token_confirmation": True})
    private_key, jwk = _signing_material()
    with respx.mock:
        respx.get(settings.mcp_oidc_jwks_url).mock(return_value=httpx.Response(200, json={"keys": [jwk]}))
        verifier = OidcJwksTokenVerifier(settings)
        access = await verifier.verify_token(
            _token(private_key, settings, include_client=True, confirmation={"jkt": "a" * 43})
        )
        missing_confirmation = await verifier.verify_token(_token(private_key, settings, include_client=True))

    assert access is not None
    claims = jwt.decode(
        access.token,
        settings.internal_service_jwt_secret,
        algorithms=["HS256"],
        issuer=settings.internal_token_issuer,
        audience=settings.internal_token_audience,
    )
    assert len(claims["credential_fingerprint"]) == 64
    assert claims["credential_fingerprint"] != "a" * 43
    assert missing_confirmation is None
