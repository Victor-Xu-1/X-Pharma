from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.models import OrganizationMembership, UserRole
from pharma_intel.schemas import (
    ProjectionMaintenanceAccessRead,
    ProjectionMaintenanceJobRead,
    ProjectionMaintenanceRequest,
)
from pharma_intel.search.maintenance import ProjectionMaintenanceError, ProjectionMaintenanceService
from pharma_intel.security import PLATFORM_PROJECTION_SCOPE, Principal

router = APIRouter()


def _projection_maintenance_service(session: Session, tenant_id: str) -> ProjectionMaintenanceService:
    return ProjectionMaintenanceService(session, runtime.get_settings(), tenant_id)


def _require_projection_admin(principal: Principal, session: Session) -> str:
    principal.require("governance:review")
    principal.require_exact(PLATFORM_PROJECTION_SCOPE)
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human administrator account is required")
    user = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == principal.user_id,
            OrganizationMembership.tenant_id == principal.tenant_id,
            OrganizationMembership.role == UserRole.ADMIN,
            OrganizationMembership.active.is_(True),
        )
    )
    if user is None:
        raise HTTPException(status_code=403, detail="An active tenant administrator is required")
    return user.id


@router.get(
    "/api/v1/governance/projection-maintenance-access",
    response_model=ProjectionMaintenanceAccessRead,
    tags=["governance"],
)
def get_projection_maintenance_access(
    principal: PrincipalDep,
    session: SessionDep,
) -> ProjectionMaintenanceAccessRead:
    if principal.user_id is None or PLATFORM_PROJECTION_SCOPE not in principal.scopes:
        return ProjectionMaintenanceAccessRead(allowed=False)
    user = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == principal.user_id,
            OrganizationMembership.tenant_id == principal.tenant_id,
            OrganizationMembership.role == UserRole.ADMIN,
            OrganizationMembership.active.is_(True),
        )
    )
    return ProjectionMaintenanceAccessRead(allowed=user is not None)


@router.get(
    "/api/v1/governance/projection-maintenance-jobs",
    response_model=list[ProjectionMaintenanceJobRead],
    tags=["governance"],
)
def list_projection_maintenance_jobs(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ProjectionMaintenanceJobRead]:
    _require_projection_admin(principal, session)
    return [
        ProjectionMaintenanceJobRead.model_validate(job)
        for job in _projection_maintenance_service(session, principal.tenant_id).list(limit)
    ]


@router.get(
    "/api/v1/governance/projection-maintenance-jobs/{job_id}",
    response_model=ProjectionMaintenanceJobRead,
    tags=["governance"],
)
def get_projection_maintenance_job(
    job_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> ProjectionMaintenanceJobRead:
    _require_projection_admin(principal, session)
    try:
        job = _projection_maintenance_service(session, principal.tenant_id).get(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProjectionMaintenanceJobRead.model_validate(job)


@router.post(
    "/api/v1/governance/projection-maintenance-jobs",
    response_model=ProjectionMaintenanceJobRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["governance"],
)
def request_projection_maintenance_job(
    payload: ProjectionMaintenanceRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> ProjectionMaintenanceJobRead:
    user_id = _require_projection_admin(principal, session)
    try:
        job = _projection_maintenance_service(session, principal.tenant_id).request(
            payload.operation,
            user_id,
            request.state.request_id,
        )
    except ProjectionMaintenanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ProjectionMaintenanceJobRead.model_validate(job)
