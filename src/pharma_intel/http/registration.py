from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy.orm import Session

from pharma_intel.accounts.contracts import (
    InvitationCreate,
    InvitationIssued,
    InvitationRead,
    RegistrationPolicy,
    RegistrationRequest,
)
from pharma_intel.accounts.request_budget import AccountRateExceeded, consume_account_budget
from pharma_intel.accounts.service import (
    AccountAccessDenied,
    AccountConflict,
    AccountNotFound,
    AccountRegistrationService,
)
from pharma_intel.http import runtime
from pharma_intel.http.account_boundary import _account_error, require_account_origin
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.schemas import UserRead

router = APIRouter(tags=["authentication"])


def _service(request: Request, session: Session) -> AccountRegistrationService:
    return AccountRegistrationService(session, request.state.request_id)


@router.get("/api/v1/auth/registration-policy", response_model=RegistrationPolicy)
def registration_policy() -> RegistrationPolicy:
    settings = runtime.get_settings()
    local = settings.human_auth_mode == "local"
    return RegistrationPolicy(
        research="independent" if local and settings.human_self_registration_enabled else "disabled",
        internal="invitation" if local else "disabled",
    )


@router.post("/api/v1/auth/register", response_model=UserRead, status_code=201)
def register_account(
    payload: RegistrationRequest, request: Request, response: Response, session: SessionDep
) -> UserRead:
    require_account_origin(request)
    response.headers["Cache-Control"] = "no-store"
    try:
        consume_account_budget(session, request.client.host if request.client else "unknown")
    except AccountRateExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": "600"}) from exc
    try:
        return UserRead.model_validate(_service(request, session).register(payload))
    except (AccountAccessDenied, AccountConflict, AccountNotFound) as exc:
        raise _account_error(exc) from exc


@router.get("/api/v1/enterprise/account-invitations", response_model=list[InvitationRead], tags=["enterprise"])
def list_account_invitations(request: Request, principal: PrincipalDep, session: SessionDep) -> list[InvitationRead]:
    try:
        return _service(request, session).list_invitations(principal)
    except (AccountAccessDenied, AccountConflict, AccountNotFound) as exc:
        raise _account_error(exc) from exc


@router.post(
    "/api/v1/enterprise/account-invitations", response_model=InvitationIssued, status_code=201, tags=["enterprise"]
)
def create_account_invitation(
    payload: InvitationCreate, request: Request, response: Response, principal: PrincipalDep, session: SessionDep
) -> InvitationIssued:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        return _service(request, session).issue_invitation(principal, payload)
    except (AccountAccessDenied, AccountConflict, AccountNotFound) as exc:
        raise _account_error(exc) from exc


@router.delete("/api/v1/enterprise/account-invitations/{invitation_id}", status_code=204, tags=["enterprise"])
def revoke_account_invitation(
    invitation_id: UUID, request: Request, principal: PrincipalDep, session: SessionDep
) -> Response:
    try:
        _service(request, session).revoke_invitation(principal, str(invitation_id))
    except (AccountAccessDenied, AccountConflict, AccountNotFound) as exc:
        raise _account_error(exc) from exc
    return Response(status_code=204)
