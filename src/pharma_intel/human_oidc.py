from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.models import Tenant, User, UserRole
from pharma_intel.security import hash_password, normalize_email

OIDC_TRANSACTION_COOKIE = "pharma_oidc_transaction"
OIDC_TRANSACTION_AUDIENCE = "pharma-human-oidc-transaction"
OIDC_TRANSACTION_LIFETIME_SECONDS = 600
OIDC_ALGORITHMS = {"RS256", "ES256"}
MAX_OIDC_RESPONSE_BYTES = 1_048_576


class OidcAuthenticationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OidcAuthorization:
    url: str
    transaction_token: str
    max_age: int


class OidcIdTokenVerifier:
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
                response = await client.get(self.settings.human_oidc_jwks_url)
                response.raise_for_status()
            if len(response.content) > MAX_OIDC_RESPONSE_BYTES:
                raise OidcAuthenticationError("OIDC JWKS response is too large")
            payload = response.json()
            keys = payload.get("keys") if isinstance(payload, dict) else None
            if not isinstance(keys, list):
                raise OidcAuthenticationError("OIDC JWKS response does not contain keys")
            parsed = {
                key["kid"]: key
                for key in keys
                if isinstance(key, dict) and isinstance(key.get("kid"), str) and key.get("use", "sig") == "sig"
            }
            if not parsed:
                raise OidcAuthenticationError("OIDC JWKS response contains no signing keys")
            self._jwks = parsed
            self._cache_until = time.monotonic() + 300
            return parsed

    async def verify(self, token: str, expected_nonce: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            algorithm = header.get("alg")
            if not isinstance(kid, str) or algorithm not in OIDC_ALGORITHMS:
                raise OidcAuthenticationError("ID token uses an unsupported signing key")
            keys = await self._load_keys()
            key = keys.get(kid)
            if key is None:
                key = (await self._load_keys(force=True)).get(kid)
            if key is None or key.get("alg", algorithm) != algorithm:
                raise OidcAuthenticationError("ID token signing key is unavailable")
            signing_key = jwt.PyJWK.from_dict(key).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=[algorithm],
                issuer=self.settings.human_oidc_issuer_url,
                audience=self.settings.human_oidc_client_id,
            )
        except OidcAuthenticationError:
            raise
        except (httpx.HTTPError, jwt.PyJWTError, ValueError) as exc:
            raise OidcAuthenticationError("ID token validation failed") from exc

        required_claims = ("sub", "iss", "aud", "exp", "iat", "nonce")
        if any(claim not in claims for claim in required_claims):
            raise OidcAuthenticationError("ID token is missing a required claim")
        if not secrets.compare_digest(str(claims["nonce"]), expected_nonce):
            raise OidcAuthenticationError("ID token nonce validation failed")
        audience = claims["aud"]
        if isinstance(audience, list) and len(audience) > 1 and claims.get("azp") != self.settings.human_oidc_client_id:
            raise OidcAuthenticationError("ID token authorized-party validation failed")
        if not isinstance(claims["sub"], str) or not claims["sub"]:
            raise OidcAuthenticationError("ID token subject is invalid")
        return claims


_VERIFIER_CACHE: dict[tuple[str, str, str], OidcIdTokenVerifier] = {}


def get_oidc_id_token_verifier(settings: Settings) -> OidcIdTokenVerifier:
    key = (
        settings.human_oidc_issuer_url,
        settings.human_oidc_jwks_url,
        settings.human_oidc_client_id,
    )
    verifier = _VERIFIER_CACHE.get(key)
    if verifier is None:
        verifier = OidcIdTokenVerifier(settings)
        _VERIFIER_CACHE[key] = verifier
    return verifier


def create_oidc_authorization(settings: Settings) -> OidcAuthorization:
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode()
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=OIDC_TRANSACTION_LIFETIME_SECONDS)
    transaction = jwt.encode(
        {
            "type": "human_oidc_transaction",
            "state": state,
            "nonce": nonce,
            "code_verifier": verifier,
            "iat": now,
            "exp": expires_at,
            "aud": OIDC_TRANSACTION_AUDIENCE,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.human_oidc_client_id,
            "redirect_uri": settings.human_oidc_redirect_uri,
            "scope": "openid profile email",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    separator = "&" if "?" in settings.human_oidc_authorization_url else "?"
    return OidcAuthorization(
        url=f"{settings.human_oidc_authorization_url}{separator}{query}",
        transaction_token=transaction,
        max_age=OIDC_TRANSACTION_LIFETIME_SECONDS,
    )


def read_oidc_transaction(settings: Settings, token: str, state: str) -> dict[str, str]:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=OIDC_TRANSACTION_AUDIENCE,
        )
    except jwt.PyJWTError as exc:
        raise OidcAuthenticationError("OIDC transaction is invalid or expired") from exc
    if claims.get("type") != "human_oidc_transaction" or not secrets.compare_digest(
        str(claims.get("state", "")), state
    ):
        raise OidcAuthenticationError("OIDC state validation failed")
    nonce = claims.get("nonce")
    verifier = claims.get("code_verifier")
    if not isinstance(nonce, str) or not nonce or not isinstance(verifier, str) or not verifier:
        raise OidcAuthenticationError("OIDC transaction is incomplete")
    return {"nonce": nonce, "code_verifier": verifier}


async def exchange_oidc_code(settings: Settings, code: str, verifier: str) -> str:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.human_oidc_redirect_uri,
        "client_id": settings.human_oidc_client_id,
        "code_verifier": verifier,
    }
    auth = None
    if settings.human_oidc_client_secret:
        auth = httpx.BasicAuth(settings.human_oidc_client_id, settings.human_oidc_client_secret)
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False) as client:
            if auth is None:
                response = await client.post(settings.human_oidc_token_url, data=data)
            else:
                response = await client.post(settings.human_oidc_token_url, data=data, auth=auth)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise OidcAuthenticationError("OIDC authorization-code exchange failed") from exc
    if len(response.content) > MAX_OIDC_RESPONSE_BYTES:
        raise OidcAuthenticationError("OIDC token response is too large")
    try:
        payload = response.json()
    except ValueError as exc:
        raise OidcAuthenticationError("OIDC token response is not valid JSON") from exc
    id_token = payload.get("id_token") if isinstance(payload, dict) else None
    if not isinstance(id_token, str) or not id_token:
        raise OidcAuthenticationError("OIDC token response does not contain an ID token")
    return id_token


def resolve_oidc_user(session: Session, settings: Settings, claims: dict[str, Any]) -> User:
    issuer = str(claims["iss"])
    subject = str(claims["sub"])
    tenant_claim = claims.get(settings.human_oidc_tenant_claim)
    if not isinstance(tenant_claim, str) or not tenant_claim:
        raise OidcAuthenticationError("ID token does not identify a tenant")
    user = session.scalar(
        select(User)
        .join(Tenant)
        .where(
            User.oidc_issuer == issuer,
            User.oidc_subject == subject,
            User.active.is_(True),
            Tenant.active.is_(True),
        )
    )
    if user is not None:
        tenant = session.get(Tenant, user.tenant_id)
        if tenant is None or tenant_claim not in {tenant.id, tenant.slug}:
            raise OidcAuthenticationError("ID token tenant does not match the linked account")
        return user
    if not settings.human_oidc_auto_provision:
        raise OidcAuthenticationError("OIDC identity is not provisioned")

    tenant = session.scalar(
        select(Tenant).where(
            or_(Tenant.id == tenant_claim, Tenant.slug == tenant_claim),
            Tenant.active.is_(True),
        )
    )
    email = claims.get("email")
    if tenant is None or not isinstance(email, str) or not email or claims.get("email_verified") is not True:
        raise OidcAuthenticationError("OIDC auto-provisioning claims are incomplete")
    normalized_email = normalize_email(email)
    if len(normalized_email) > 320 or session.scalar(select(User.id).where(User.normalized_email == normalized_email)):
        raise OidcAuthenticationError("OIDC email cannot be auto-provisioned")
    display_name = str(claims.get("name") or email).strip()[:200]
    user = User(
        tenant_id=tenant.id,
        email=email.strip()[:320],
        normalized_email=normalized_email,
        display_name=display_name,
        password_hash=hash_password(secrets.token_urlsafe(48)),
        role=_provisioned_role(settings, claims),
        oidc_issuer=issuer,
        oidc_subject=subject,
    )
    session.add(user)
    session.flush()
    return user


def _provisioned_role(settings: Settings, claims: dict[str, Any]) -> UserRole:
    role = UserRole(settings.human_oidc_default_role)
    groups = claims.get(settings.human_oidc_role_claim, [])
    if isinstance(groups, str):
        groups = [groups]
    if not isinstance(groups, list):
        return role
    mapped = {settings.human_oidc_role_mapping.get(group) for group in groups if isinstance(group, str)}
    if "analyst" in mapped:
        return UserRole.ANALYST
    return role
