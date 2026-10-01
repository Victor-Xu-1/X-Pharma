from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select, update

from pharma_intel.accounts.organization_contracts import (
    InvitationAcceptance,
    OidcInvitationStart,
    OrganizationJoin,
    OrganizationRead,
    OrganizationSwitch,
)
from pharma_intel.accounts.organizations import select_membership
from pharma_intel.accounts.request_budget import AccountRateExceeded, consume_account_budget
from pharma_intel.accounts.service import (
    AccountAccessDenied,
    AccountConflict,
    AccountNotFound,
    AccountRegistrationService,
)
from pharma_intel.db import set_tenant_context
from pharma_intel.http import runtime
from pharma_intel.http.account_boundary import _account_error, require_account_origin
from pharma_intel.http.authentication import set_human_session_cookies
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.human_oidc import OIDC_TRANSACTION_COOKIE, create_oidc_authorization
from pharma_intel.models import OrganizationMembership, Tenant, User, UserSession
from pharma_intel.schemas import UserRead
from pharma_intel.security import Principal, authenticate_user

router = APIRouter(tags=["authentication"])


@router.post("/api/v1/auth/oidc/invitation", response_model=OidcInvitationStart)
def start_oidc_invitation(
    payload: OrganizationJoin,
    request: Request,
    response: Response,
    session: SessionDep,
) -> OidcInvitationStart:
    require_account_origin(request)
    settings = runtime.get_settings()
    if settings.human_auth_mode != "oidc":
        raise HTTPException(status_code=404, detail="Enterprise authentication is not enabled")
    try:
        consume_account_budget(session, request.client.host if request.client else "unknown")
        code = payload.invitation_code.get_secret_value()
        AccountRegistrationService(session, request.state.request_id).prepare_oidc_invitation(code)
    except AccountRateExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": "600"}) from exc
    except (AccountAccessDenied, AccountConflict, AccountNotFound) as exc:
        raise _account_error(exc) from exc
    authorization = create_oidc_authorization(settings, invitation_code=code)
    response.set_cookie(
        OIDC_TRANSACTION_COOKIE,
        authorization.transaction_token,
        max_age=authorization.max_age,
        httponly=True,
        secure=settings.app_env.lower() == "production",
        samesite="lax",
        path="/api/v1/auth/oidc",
    )
    response.headers["Cache-Control"] = "no-store"
    return OidcInvitationStart(authorization_url=authorization.url)


@router.get("/api/v1/auth/organizations", response_model=list[OrganizationRead])
def list_organizations(principal: PrincipalDep, session: SessionDep, response: Response) -> list[OrganizationRead]:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="Human account required")
    response.headers["Cache-Control"] = "no-store"
    rows = session.execute(
        select(OrganizationMembership, Tenant)
        .join(Tenant, Tenant.id == OrganizationMembership.tenant_id)
        .where(OrganizationMembership.user_id == principal.user_id)
        .order_by(Tenant.name, Tenant.id)
    )
    return [
        OrganizationRead(
            tenant_id=member.tenant_id,
            name=tenant.name,
            slug=tenant.slug,
            role=member.role,
            active=member.active and tenant.active,
            selected=member.tenant_id == principal.tenant_id,
        )
        for member, tenant in rows
    ]


@router.post("/api/v1/auth/organizations/switch", response_model=UserRead)
def switch_organization(
    payload: OrganizationSwitch,
    request: Request,
    response: Response,
    principal: PrincipalDep,
    session: SessionDep,
) -> UserRead:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="Human account required")
    account = session.get(User, principal.user_id)
    member = select_membership(session, account, str(payload.organization_id)) if account is not None else None
    if member is None:
        raise HTTPException(status_code=403, detail="该组织不可用或你没有有效成员资格")
    # Revoke only the switching session. Other devices retain their chosen org.
    session.execute(
        update(UserSession)
        .where(
            UserSession.tenant_id == principal.tenant_id,
            UserSession.id == principal.session_id,
            UserSession.user_id == principal.user_id,
            UserSession.revoked_at.is_(None),
        )
        .values(
            revoked_at=datetime.now(UTC), revoked_by_user_id=principal.user_id, revoke_reason="Organization switched"
        )
    )
    set_tenant_context(session, member.tenant_id)
    member.last_login_at = datetime.now(UTC)
    set_human_session_cookies(request, response, session, member)
    request.state.principal = Principal(member.tenant_id, member.user_id, "user", frozenset())
    response.headers["Cache-Control"] = "no-store"
    return UserRead.model_validate(member)


@router.post("/api/v1/auth/organizations/join", response_model=OrganizationRead, status_code=201)
def join_organization(
    payload: OrganizationJoin,
    request: Request,
    response: Response,
    principal: PrincipalDep,
    session: SessionDep,
) -> OrganizationRead:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="Human account required")
    account = session.get(User, principal.user_id)
    if account is None:
        raise HTTPException(status_code=401, detail="Account not found")
    try:
        member = AccountRegistrationService(session, request.state.request_id).accept_invitation(
            account,
            payload.invitation_code.get_secret_value(),
        )
    except (AccountAccessDenied, AccountConflict, AccountNotFound) as exc:
        raise _account_error(exc) from exc
    tenant = session.get(Tenant, member.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    result = OrganizationRead(
        tenant_id=tenant.id, name=tenant.name, slug=tenant.slug, role=member.role, active=True, selected=False
    )
    set_tenant_context(session, principal.tenant_id)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/api/v1/auth/invitations/accept", response_model=UserRead)
def accept_invitation_with_credentials(
    payload: InvitationAcceptance,
    request: Request,
    response: Response,
    session: SessionDep,
) -> UserRead:
    """Permit a locally verified identity with no active org to accept an invitation."""
    require_account_origin(request)
    if runtime.get_settings().human_auth_mode != "local":
        raise HTTPException(status_code=404, detail="Local password authentication is disabled")
    try:
        consume_account_budget(session, request.client.host if request.client else "unknown")
    except AccountRateExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": "600"}) from exc
    account = authenticate_user(session, payload.email, payload.password.get_secret_value())
    if account is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    try:
        member = AccountRegistrationService(session, request.state.request_id).accept_invitation(
            account,
            payload.invitation_code.get_secret_value(),
        )
    except (AccountAccessDenied, AccountConflict, AccountNotFound) as exc:
        raise _account_error(exc) from exc
    member.last_login_at = datetime.now(UTC)
    set_human_session_cookies(request, response, session, member)
    request.state.principal = Principal(member.tenant_id, member.user_id, "user", frozenset())
    response.headers["Cache-Control"] = "no-store"
    return UserRead.model_validate(member)
