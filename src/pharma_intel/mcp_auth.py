from __future__ import annotations

import asyncio
import time
from typing import Any

import anyio
import httpx
import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier

from pharma_intel.config import Settings
from pharma_intel.db import get_session_factory
from pharma_intel.request_correlation import CorrelationSignalError, credential_confirmation_fingerprint
from pharma_intel.security import Principal, authenticate_api_key, issue_internal_service_token

OIDC_ALGORITHMS = {"RS256", "ES256"}


def _to_access_token(principal: Principal, settings: Settings) -> AccessToken:
    token, expires_at = issue_internal_service_token(principal, settings)
    advertised_scopes = set(principal.scopes)
    if "*" in advertised_scopes:
        advertised_scopes.add(settings.mcp_required_scope)
    return AccessToken(
        token=token,
        client_id=principal.commercial_client_id or principal.actor_id,
        scopes=sorted(advertised_scopes),
        expires_at=int(expires_at.timestamp()),
        resource=settings.mcp_resource_server_url,
    )


class DatabaseApiKeyTokenVerifier(TokenVerifier):
    """Development adapter. Production uses the OIDC verifier below."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _verify(self, token: str) -> AccessToken | None:
        with get_session_factory()() as session:
            principal = authenticate_api_key(session, token)
            if principal is None or not _has_scope(principal.scopes, self.settings.mcp_required_scope):
                return None
            return _to_access_token(principal, self.settings)

    async def verify_token(self, token: str) -> AccessToken | None:
        return await anyio.to_thread.run_sync(self._verify, token)


class OidcJwksTokenVerifier(TokenVerifier):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jwks: dict[str, dict[str, Any]] = {}
        self._cache_until = 0.0
        self._lock = asyncio.Lock()

    async def _load_keys(self, force: bool = False) -> dict[str, dict[str, Any]]:
        async with self._lock:
            if not force and self._jwks and time.monotonic() < self._cache_until:
                return self._jwks
            async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
                response = await client.get(self.settings.mcp_oidc_jwks_url)
                response.raise_for_status()
            payload = response.json()
            keys = payload.get("keys") if isinstance(payload, dict) else None
            if not isinstance(keys, list):
                raise ValueError("OIDC JWKS response does not contain a keys array")
            parsed = {key["kid"]: key for key in keys if isinstance(key, dict) and isinstance(key.get("kid"), str)}
            if not parsed:
                raise ValueError("OIDC JWKS response contains no usable signing keys")
            self._jwks = parsed
            self._cache_until = time.monotonic() + self.settings.mcp_oidc_jwks_cache_seconds
            return parsed

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            algorithm = header.get("alg")
            if not isinstance(kid, str) or algorithm not in OIDC_ALGORITHMS:
                return None
            keys = await self._load_keys()
            key = keys.get(kid)
            if key is None:
                key = (await self._load_keys(force=True)).get(kid)
            if key is None:
                return None
            signing_key = jwt.PyJWK.from_dict(key).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=[algorithm],
                audience=self.settings.mcp_oidc_audience,
                issuer=self.settings.mcp_auth_issuer_url,
            )
        except (httpx.HTTPError, jwt.PyJWTError, ValueError):
            return None

        subject = claims.get("sub")
        tenant_id = claims.get(self.settings.mcp_oidc_tenant_claim)
        client_id = claims.get(self.settings.mcp_oidc_client_id_claim)
        scopes = _read_scopes(claims)
        if (
            not isinstance(subject, str)
            or not subject
            or not isinstance(tenant_id, str)
            or not tenant_id
            or not isinstance(client_id, str)
            or not client_id
            or not _has_scope(scopes, self.settings.mcp_required_scope)
        ):
            return None
        try:
            credential_fingerprint = credential_confirmation_fingerprint(
                self.settings,
                issuer=self.settings.mcp_auth_issuer_url,
                client_id=client_id,
                confirmation=claims.get("cnf"),
            )
        except CorrelationSignalError:
            return None
        return _to_access_token(
            Principal(tenant_id, subject, "agent", scopes, client_id, credential_fingerprint),
            self.settings,
        )


def _read_scopes(claims: dict[str, Any]) -> frozenset[str]:
    scope = claims.get("scope")
    if isinstance(scope, str):
        return frozenset(scope.split())
    scp = claims.get("scp")
    if isinstance(scp, list) and all(isinstance(value, str) for value in scp):
        return frozenset(scp)
    return frozenset()


def _has_scope(scopes: frozenset[str], required: str) -> bool:
    return "*" in scopes or required in scopes


def build_token_verifier(settings: Settings) -> TokenVerifier:
    if settings.mcp_token_verifier_mode == "oidc":  # noqa: S105
        return OidcJwksTokenVerifier(settings)
    return DatabaseApiKeyTokenVerifier(settings)
