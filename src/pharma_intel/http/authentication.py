from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_intel.accounts.organizations import select_membership
from pharma_intel.accounts.request_budget import AccountRateExceeded, consume_login_budget
from pharma_intel.accounts.service import AccountAccessDenied, AccountConflict, AccountRegistrationService
from pharma_intel.db import set_tenant_context
from pharma_intel.http import runtime
from pharma_intel.http.account_boundary import require_account_origin
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.human_oidc import (
    OIDC_TRANSACTION_COOKIE,
    OidcAuthenticationError,
    create_oidc_authorization,
    exchange_oidc_code,
    get_oidc_id_token_verifier,
    read_oidc_transaction,
    resolve_oidc_user,
)
from pharma_intel.models import (
    OrganizationMembership,
    User,
    UserSession,
)
from pharma_intel.schemas import (
    LoginRequest,
    UserPasswordChange,
    UserProfileUpdate,
    UserRead,
)
from pharma_intel.security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    Principal,
    authenticate_user,
    hash_password,
    issue_human_session,
    normalize_email,
    verify_password,
)

router = APIRouter()
request_logger = structlog.get_logger("pharma_intel.request")


def set_human_session_cookies(
    request: Request, response: Response, session: Session, member: OrganizationMembership
) -> None:
    set_tenant_context(session, member.tenant_id)
    session_id = str(uuid.uuid4())
    token, csrf_token, expires_at = issue_human_session(member, session_id)
    issued_at = datetime.now(UTC)
    session.add(
        UserSession(
            id=session_id,
            tenant_id=member.tenant_id,
            user_id=member.user_id,
            user_agent_sha256=hashlib.sha256(request.headers.get("user-agent", "").encode()).hexdigest(),
            issued_at=issued_at,
            expires_at=expires_at,
        )
    )
    session.commit()
    secure = runtime.get_settings().app_env.lower() == "production"
    max_age = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )


@router.post("/api/v1/auth/login", response_model=UserRead, tags=["authentication"])
def login(payload: LoginRequest, request: Request, response: Response, session: SessionDep) -> UserRead:
    if runtime.get_settings().human_auth_mode != "local":
        raise HTTPException(status_code=404, detail="Local password authentication is disabled")
    require_account_origin(request)
    try:
        consume_login_budget(session, request.client.host if request.client else "unknown", payload.email)
    except AccountRateExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": "600"}) from exc
    user = authenticate_user(session, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    member = select_membership(session, user, payload.organization_id)
    if member is None:
        raise HTTPException(status_code=403, detail="没有可用的组织成员资格；请使用管理员邀请码加入组织")
    user.last_login_at = member.last_login_at = datetime.now(UTC)
    set_human_session_cookies(request, response, session, member)
    request.state.principal = Principal(member.tenant_id, user.id, "user", frozenset())
    return UserRead.model_validate(member)


@router.get("/api/v1/auth/config", tags=["authentication"])
def authentication_config() -> dict[str, str]:
    return {"mode": runtime.get_settings().human_auth_mode}


@router.get("/api/v1/auth/oidc/login", tags=["authentication"])
def oidc_login() -> RedirectResponse:
    settings = runtime.get_settings()
    if settings.human_auth_mode != "oidc":
        raise HTTPException(status_code=404, detail="Enterprise authentication is not enabled")
    authorization = create_oidc_authorization(settings)
    response = RedirectResponse(authorization.url, status_code=302)
    response.set_cookie(
        OIDC_TRANSACTION_COOKIE,
        authorization.transaction_token,
        max_age=authorization.max_age,
        httponly=True,
        secure=settings.app_env.lower() == "production",
        samesite="lax",
        path="/api/v1/auth/oidc",
    )
    return response


@router.get("/api/v1/auth/oidc/callback", tags=["authentication"])
async def oidc_callback(
    request: Request,
    session: SessionDep,
    code: str = Query(min_length=1, max_length=4096),
    state: str = Query(min_length=20, max_length=500),
) -> RedirectResponse:
    settings = runtime.get_settings()
    if settings.human_auth_mode != "oidc":
        raise HTTPException(status_code=404, detail="Enterprise authentication is not enabled")
    try:
        transaction = read_oidc_transaction(
            settings,
            request.cookies.get(OIDC_TRANSACTION_COOKIE, ""),
            state,
        )
        id_token = await exchange_oidc_code(settings, code, transaction["code_verifier"])
        claims = await get_oidc_id_token_verifier(settings).verify(id_token, transaction["nonce"])
        invitation_code = transaction.get("invitation_code")
        user = resolve_oidc_user(session, settings, claims, allow_provision=invitation_code is None)
        member: OrganizationMembership | None
        if invitation_code is not None:
            if (
                claims.get("email_verified") is not True
                or normalize_email(str(claims.get("email", ""))) != user.normalized_email
            ):
                raise OidcAuthenticationError("Invitation requires the linked verified enterprise email")
            member = AccountRegistrationService(session, request.state.request_id).accept_invitation(
                user, invitation_code
            )
        else:
            member = select_membership(session, user)
        if member is None:
            raise OidcAuthenticationError("No active organization membership")
        user.last_login_at = member.last_login_at = datetime.now(UTC)
    except (OidcAuthenticationError, ValueError, AccountAccessDenied, AccountConflict) as exc:
        session.rollback()
        request_logger.warning("oidc_login_failed", request_id=request.state.request_id, reason=type(exc).__name__)
        raise HTTPException(status_code=401, detail="Enterprise authentication failed") from exc
    response = RedirectResponse(settings.public_base_url.rstrip("/") + "/", status_code=302)
    response.delete_cookie(OIDC_TRANSACTION_COOKIE, path="/api/v1/auth/oidc")
    set_human_session_cookies(request, response, session, member)
    request.state.principal = Principal(member.tenant_id, user.id, "user", frozenset())
    return response


@router.get("/api/v1/auth/me", response_model=UserRead, tags=["authentication"])
def current_user(principal: PrincipalDep, session: SessionDep) -> UserRead:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="Human account required")
    member = session.get(OrganizationMembership, (principal.tenant_id, principal.user_id))
    if member is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(member)


@router.patch("/api/v1/auth/me", response_model=UserRead, tags=["authentication"])
def update_current_user(
    payload: UserProfileUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> UserRead:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="Human account required")
    user = session.get(User, principal.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if "email" in payload.model_fields_set:
        if payload.email is None:
            raise HTTPException(status_code=422, detail="email cannot be null")
        normalized_email = normalize_email(payload.email)
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized_email) is None:
            raise HTTPException(status_code=422, detail="A valid email address is required")
        existing = session.scalar(select(User.id).where(User.normalized_email == normalized_email, User.id != user.id))
        if existing is not None:
            raise HTTPException(status_code=409, detail="Email address is already in use")
        user.email = payload.email
        user.normalized_email = normalized_email

    if "display_name" in payload.model_fields_set and payload.display_name is not None:
        user.display_name = payload.display_name
    if "phone" in payload.model_fields_set:
        user.phone = payload.phone or None
    if "avatar_url" in payload.model_fields_set:
        user.avatar_url = payload.avatar_url or None

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Email address is already in use") from exc
    session.refresh(user)
    member = session.get(OrganizationMembership, (principal.tenant_id, user.id))
    if member is None:
        raise HTTPException(status_code=404, detail="Organization membership not found")
    return UserRead.model_validate(member)


@router.post("/api/v1/auth/me/password", status_code=status.HTTP_204_NO_CONTENT, tags=["authentication"])
def change_current_user_password(
    payload: UserPasswordChange,
    principal: PrincipalDep,
    session: SessionDep,
    request: Request,
) -> Response:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="Human account required")
    user = session.get(User, principal.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.oidc_issuer is not None:
        raise HTTPException(status_code=409, detail="OIDC accounts manage passwords through the identity provider")
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(status_code=422, detail="New password must differ from the current password")

    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    now = datetime.now(UTC)
    session.execute(
        update(UserSession)
        .where(
            UserSession.tenant_id == principal.tenant_id,
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
        )
        .values(
            revoked_at=now,
            revoked_by_user_id=user.id,
            revoke_reason="Password changed",
        )
    )
    member = session.get(OrganizationMembership, (principal.tenant_id, user.id))
    if member is None:
        raise HTTPException(status_code=404, detail="Organization membership not found")
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_human_session_cookies(request, response, session, member)
    return response


@router.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["authentication"])
def logout(response: Response, principal: PrincipalDep, session: SessionDep) -> Response:
    if principal.user_id is not None and principal.session_id is not None:
        current = session.scalar(
            select(UserSession).where(
                UserSession.tenant_id == principal.tenant_id,
                UserSession.id == principal.session_id,
                UserSession.user_id == principal.user_id,
            )
        )
        if current is not None and current.revoked_at is None:
            current.revoked_at = datetime.now(UTC)
            current.revoked_by_user_id = principal.user_id
            current.revoke_reason = "User logout"
            session.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
