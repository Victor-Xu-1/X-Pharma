from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings, get_settings
from pharma_intel.db import get_session, set_tenant_context
from pharma_intel.models import ApiKey, Tenant, User, UserRole, UserSession
from pharma_intel.request_correlation import api_key_credential_fingerprint

SESSION_COOKIE = "pharma_session"
CSRF_COOKIE = "pharma_csrf"
JWT_ALGORITHM = "HS256"
PLATFORM_PROJECTION_SCOPE = "platform:projection:operate"
_password_hasher = PasswordHasher()
_dummy_password_hash = _password_hasher.hash("not-a-real-password")

ROLE_SCOPES: dict[UserRole, frozenset[str]] = {
    UserRole.ADMIN: frozenset({"*"}),
    UserRole.ANALYST: frozenset(
        {
            "activities:read",
            "collections:read",
            "collections:write",
            "deals:read",
            "dossiers:read",
            "entities:read",
            "evidence:read",
            "governance:read",
            "governance:review",
            "ingestion:read",
            "knowledge:read",
            "monitoring:read",
            "monitoring:write",
            "patents:read",
            "pipelines:read",
            "regulatory:read",
            "epidemiology:read",
            "news:read",
            "structures:read",
            "targets:read",
            "trials:read",
            "workspace:export",
        }
    ),
    UserRole.VIEWER: frozenset(
        {
            "activities:read",
            "collections:read",
            "collections:write",
            "deals:read",
            "dossiers:read",
            "entities:read",
            "evidence:read",
            "knowledge:read",
            "monitoring:read",
            "monitoring:write",
            "patents:read",
            "pipelines:read",
            "regulatory:read",
            "epidemiology:read",
            "news:read",
            "structures:read",
            "targets:read",
            "trials:read",
            "workspace:export",
        }
    ),
}


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    actor_id: str
    actor_type: Literal["agent", "api_key", "user"]
    scopes: frozenset[str]
    client_id: str | None = None
    credential_fingerprint: str | None = None
    session_id: str | None = None

    @property
    def api_key_id(self) -> str | None:
        return self.actor_id if self.actor_type == "api_key" else None

    @property
    def user_id(self) -> str | None:
        return self.actor_id if self.actor_type == "user" else None

    @property
    def commercial_client_id(self) -> str | None:
        if self.actor_type == "user":
            return None
        return self.client_id or (self.actor_id if self.actor_type == "api_key" else None)

    def require(self, scope: str) -> None:
        if "*" not in self.scopes and scope not in self.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient scope")

    def require_exact(self, scope: str) -> None:
        """Require an explicitly granted platform scope, never a tenant-role wildcard."""
        if scope not in self.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient platform scope")


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _password_hasher.verify(password_hash or _dummy_password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def hash_api_key(secret: str) -> str:
    salt = get_settings().api_key_hash_salt.encode()
    return hmac.new(salt, secret.encode(), hashlib.sha256).hexdigest()


def issue_api_key() -> tuple[str, str]:
    secret = f"phk_{secrets.token_urlsafe(32)}"
    return secret, hash_api_key(secret)


def issue_human_session(user: User, session_id: str) -> tuple[str, str, datetime]:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.session_lifetime_minutes)
    csrf_token = secrets.token_urlsafe(32)
    claims = {
        "sub": user.id,
        "tenant_id": user.tenant_id,
        "role": user.role.value,
        "token_version": user.token_version,
        "sid": session_id,
        "type": "human",
        "iat": datetime.now(UTC),
        "exp": expires_at,
    }
    token = jwt.encode(claims, settings.jwt_secret, algorithm=JWT_ALGORITHM)
    return token, csrf_token, expires_at


def issue_internal_service_token(principal: Principal, settings: Settings | None = None) -> tuple[str, datetime]:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.internal_token_lifetime_seconds)
    claims = {
        "sub": principal.actor_id,
        "tenant_id": principal.tenant_id,
        "actor_type": principal.actor_type,
        "client_id": principal.client_id,
        "credential_fingerprint": principal.credential_fingerprint,
        "scopes": sorted(principal.scopes),
        "type": "internal_service",
        "iss": settings.internal_token_issuer,
        "aud": settings.internal_token_audience,
        "iat": now,
        "exp": expires_at,
        "jti": secrets.token_urlsafe(16),
    }
    token = jwt.encode(claims, settings.effective_internal_service_jwt_secret, algorithm=JWT_ALGORITHM)
    return token, expires_at


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    user = session.scalar(
        select(User)
        .join(Tenant)
        .where(
            User.normalized_email == normalize_email(email),
            User.active.is_(True),
            Tenant.active.is_(True),
        )
    )
    if user is None:
        verify_password(password, None)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def authenticate_api_key(session: Session, secret: str) -> Principal | None:
    now = datetime.now(UTC)
    api_key = session.scalar(
        select(ApiKey)
        .join(Tenant)
        .where(
            ApiKey.secret_hash == hash_api_key(secret),
            ApiKey.active.is_(True),
            ApiKey.revoked_at.is_(None),
            (ApiKey.expires_at.is_(None) | (ApiKey.expires_at > now)),
            Tenant.active.is_(True),
        )
    )
    if api_key is None:
        return None
    api_key.last_used_at = now
    session.commit()
    principal = Principal(
        api_key.tenant_id,
        api_key.id,
        "api_key",
        frozenset(api_key.scopes),
        api_key.id,
        api_key_credential_fingerprint(get_settings(), api_key.id),
    )
    set_tenant_context(session, principal.tenant_id)
    return principal


def _principal_from_internal_token(token: str) -> Principal | None:
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.effective_internal_service_jwt_secret,
            algorithms=[JWT_ALGORITHM],
            issuer=settings.internal_token_issuer,
            audience=settings.internal_token_audience,
        )
    except jwt.PyJWTError:
        return None
    actor_type = claims.get("actor_type")
    scopes = claims.get("scopes")
    if (
        claims.get("type") != "internal_service"
        or actor_type not in {"agent", "api_key", "user"}
        or not isinstance(claims.get("sub"), str)
        or not isinstance(claims.get("tenant_id"), str)
        or not isinstance(scopes, list)
        or not all(isinstance(scope, str) for scope in scopes)
    ):
        return None
    client_id = claims.get("client_id")
    if client_id is not None and not isinstance(client_id, str):
        return None
    credential_fingerprint = claims.get("credential_fingerprint")
    if credential_fingerprint is not None and (
        not isinstance(credential_fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", credential_fingerprint) is None
    ):
        return None
    return Principal(
        claims["tenant_id"],
        claims["sub"],
        actor_type,
        frozenset(scopes),
        client_id,
        credential_fingerprint,
    )


def _principal_from_session(session: Session, request: Request, token: str) -> Principal | None:
    try:
        claims = jwt.decode(token, get_settings().jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if (
        claims.get("type") != "human"
        or not isinstance(claims.get("sub"), str)
        or not isinstance(claims.get("sid"), str)
        or not isinstance(claims.get("tenant_id"), str)
    ):
        return None
    # user_sessions is tenant-RLS protected. The tenant claim is safe to use as
    # the query boundary only after the session JWT signature has been verified.
    set_tenant_context(session, claims["tenant_id"])
    now = datetime.now(UTC)
    user = session.scalar(
        select(User)
        .join(Tenant)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            User.id == claims["sub"],
            User.active.is_(True),
            Tenant.active.is_(True),
            UserSession.id == claims["sid"],
            UserSession.tenant_id == User.tenant_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    )
    if user is None or claims.get("token_version") != user.token_version or claims.get("tenant_id") != user.tenant_id:
        return None
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
        csrf_header = request.headers.get("X-CSRF-Token", "")
        if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    scopes = ROLE_SCOPES[user.role]
    if user.id in get_settings().platform_operator_user_ids:
        scopes = scopes | {PLATFORM_PROJECTION_SCOPE}
    principal = Principal(user.tenant_id, user.id, "user", scopes, session_id=claims["sid"])
    set_tenant_context(session, principal.tenant_id)
    return principal


def require_principal(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> Principal:
    authorization = request.headers.get("Authorization", "")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.casefold() != "bearer" or not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
        principal = _principal_from_internal_token(token)
        if principal is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal access token")
        set_tenant_context(session, principal.tenant_id)
        request.state.principal = principal
        return principal
    session_token = request.cookies.get(SESSION_COOKIE)
    if session_token:
        principal = _principal_from_session(session, request, session_token)
        if principal is not None:
            request.state.principal = principal
            return principal
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
