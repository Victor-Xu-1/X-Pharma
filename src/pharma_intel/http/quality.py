from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.models import DataQualityIssue, OrganizationMembership, User, UserRole
from pharma_intel.quality.service import DataQualityError, DataQualityService
from pharma_intel.schemas import (
    DataQualityCoverageRead,
    DataQualityIssueActionRequest,
    DataQualityIssueEventRead,
    DataQualityIssueRead,
    DataQualityOwnerRead,
    DataQualitySnapshotRead,
)

router = APIRouter()


def _quality_service(session: Session, tenant_id: str) -> DataQualityService:
    return DataQualityService(session, runtime.get_settings(), tenant_id)


def _quality_issue_reads(session: Session, items: list[DataQualityIssue]) -> list[DataQualityIssueRead]:
    owner_ids = {item.owner_user_id for item in items if item.owner_user_id}
    owners = {user.id: user.display_name for user in session.scalars(select(User).where(User.id.in_(owner_ids)))}
    result: list[DataQualityIssueRead] = []
    for item in items:
        payload = DataQualityIssueRead.model_validate(item).model_dump()
        payload["owner_display_name"] = owners.get(item.owner_user_id or "")
        result.append(DataQualityIssueRead.model_validate(payload))
    return result


@router.get(
    "/api/v1/governance/quality/snapshots",
    response_model=list[DataQualitySnapshotRead],
    tags=["governance"],
)
def list_data_quality_snapshots(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=30, ge=1, le=365),
) -> list[DataQualitySnapshotRead]:
    principal.require("governance:read")
    return [
        DataQualitySnapshotRead.model_validate(item)
        for item in _quality_service(session, principal.tenant_id).snapshots(limit)
    ]


@router.get(
    "/api/v1/governance/quality/coverage",
    response_model=list[DataQualityCoverageRead],
    tags=["governance"],
)
def list_data_quality_coverage(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=100),
) -> list[DataQualityCoverageRead]:
    principal.require("governance:read")
    return [
        DataQualityCoverageRead.model_validate(item)
        for item in _quality_service(session, principal.tenant_id).coverage(limit)
    ]


@router.post(
    "/api/v1/governance/quality/evaluations",
    response_model=DataQualitySnapshotRead,
    status_code=status.HTTP_201_CREATED,
    tags=["governance"],
)
def evaluate_data_quality(
    principal: PrincipalDep,
    session: SessionDep,
) -> DataQualitySnapshotRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        locked = session.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"data-quality:{principal.tenant_id}"},
        )
        if not locked:
            raise HTTPException(status_code=409, detail="A data quality evaluation is already running")
    snapshot = _quality_service(session, principal.tenant_id).evaluate(
        trigger="manual",
        actor_type="user",
        actor_id=principal.user_id,
    )
    return DataQualitySnapshotRead.model_validate(snapshot)


@router.get(
    "/api/v1/governance/quality/owners",
    response_model=list[DataQualityOwnerRead],
    tags=["governance"],
)
def list_data_quality_owners(
    principal: PrincipalDep,
    session: SessionDep,
) -> list[DataQualityOwnerRead]:
    principal.require("governance:read")
    users = session.scalars(
        select(OrganizationMembership)
        .join(User, User.id == OrganizationMembership.user_id)
        .where(
            OrganizationMembership.tenant_id == principal.tenant_id,
            OrganizationMembership.active.is_(True),
            User.active.is_(True),
            OrganizationMembership.role.in_([UserRole.ADMIN, UserRole.ANALYST]),
        )
        .order_by(User.display_name, User.id)
    )
    return [DataQualityOwnerRead(id=user.id, display_name=user.display_name, role=user.role) for user in users]


@router.get(
    "/api/v1/governance/quality/issues",
    response_model=list[DataQualityIssueRead],
    tags=["governance"],
)
def list_data_quality_issues(
    principal: PrincipalDep,
    session: SessionDep,
    issue_status: Literal["open", "acknowledged", "ready_to_resolve", "resolved", "waived"] | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[DataQualityIssueRead]:
    principal.require("governance:read")
    return _quality_issue_reads(
        session,
        _quality_service(session, principal.tenant_id).issues(issue_status, limit),
    )


@router.get(
    "/api/v1/governance/quality/issues/{issue_id}/events",
    response_model=list[DataQualityIssueEventRead],
    tags=["governance"],
)
def list_data_quality_issue_events(
    issue_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[DataQualityIssueEventRead]:
    principal.require("governance:read")
    try:
        events = _quality_service(session, principal.tenant_id).events(issue_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [DataQualityIssueEventRead.model_validate(item) for item in events]


@router.post(
    "/api/v1/governance/quality/issues/{issue_id}/actions",
    response_model=DataQualityIssueRead,
    tags=["governance"],
)
def act_on_data_quality_issue(
    issue_id: str,
    payload: DataQualityIssueActionRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataQualityIssueRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    actor = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.tenant_id == principal.tenant_id,
            OrganizationMembership.user_id == principal.user_id,
            OrganizationMembership.active.is_(True),
        )
    )
    if actor is None:
        raise HTTPException(status_code=403, detail="An active reviewer account is required")
    current_issue = session.scalar(
        select(DataQualityIssue).where(
            DataQualityIssue.tenant_id == principal.tenant_id,
            DataQualityIssue.id == issue_id,
        )
    )
    if current_issue is None:
        raise HTTPException(status_code=404, detail="Data quality issue not found")
    if payload.action == "waive" and actor.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only tenant administrators may waive quality issues")
    if payload.action == "resolve" and actor.role != UserRole.ADMIN and current_issue.owner_user_id != actor.id:
        raise HTTPException(
            status_code=403,
            detail="Only the assigned owner or an administrator may resolve this issue",
        )
    try:
        issue = _quality_service(session, principal.tenant_id).act(
            issue_id,
            action=payload.action,
            expected_version=payload.expected_version,
            actor_id=principal.user_id,
            request_id=request.state.request_id,
            owner_user_id=payload.owner_user_id,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DataQualityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _quality_issue_reads(session, [issue])[0]
