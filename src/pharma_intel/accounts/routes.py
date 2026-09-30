from __future__ import annotations

from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from pharma_intel.accounts.contracts import (
    InvitationCreate,
    InvitationIssued,
    InvitationRead,
    RegistrationPolicy,
    RegistrationRequest,
)
from pharma_intel.accounts.registration_budget import RegistrationRateExceeded, consume_registration_budget
from pharma_intel.accounts.service import (
    AccountAccessDenied,
    AccountConflict,
    AccountNotFound,
    AccountRegistrationService,
)
from pharma_intel.config import get_settings
from pharma_intel.db import get_session
from pharma_intel.schemas import UserRead
from pharma_intel.security import Principal, require_principal

router = APIRouter(tags=["authentication"])
SessionDep = Annotated[Session, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(require_principal)]


def _service(request: Request, session: Session) -> AccountRegistrationService:
    return AccountRegistrationService(session, request.state.request_id)


def _account_error(error: AccountAccessDenied | AccountConflict | AccountNotFound) -> HTTPException:
    status = 403 if isinstance(error, AccountAccessDenied) else 409 if isinstance(error, AccountConflict) else 404
    return HTTPException(status_code=status, detail=str(error))


def _registration_origin(request: Request) -> None:
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        raise HTTPException(status_code=403, detail="请从本工作台注册入口提交")
    origin = request.headers.get("origin")
    if origin:
        configured = urlsplit(get_settings().public_base_url)
        if origin != f"{configured.scheme}://{configured.netloc}":
            raise HTTPException(status_code=403, detail="请从本工作台注册入口提交")


@router.get("/api/v1/auth/registration-policy", response_model=RegistrationPolicy)
def registration_policy() -> RegistrationPolicy:
    settings = get_settings()
    local = settings.human_auth_mode == "local"
    return RegistrationPolicy(
        research="independent" if local and settings.human_self_registration_enabled else "disabled",
        internal="invitation" if local else "disabled",
    )


@router.post("/api/v1/auth/register", response_model=UserRead, status_code=201)
def register_account(
    payload: RegistrationRequest, request: Request, response: Response, session: SessionDep
) -> UserRead:
    _registration_origin(request)
    response.headers["Cache-Control"] = "no-store"
    try:
        consume_registration_budget(session, request.client.host if request.client else "unknown")
    except RegistrationRateExceeded as exc:
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
