from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from pharma_intel.comparison.exports import (
    WorkspaceComparisonExportService,
    WorkspaceExportConflict,
    WorkspaceExportDenied,
    WorkspaceExportNotConfigured,
)
from pharma_intel.comparison.service import (
    ComparisonSetConflict,
    ComparisonSetLimitExceeded,
    ComparisonSetNotFound,
    ComparisonSetService,
    ComparisonSetView,
)
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _can_view_unpublished_entities
from pharma_intel.schemas import (
    ComparisonSetCreate,
    ComparisonSetDetailRead,
    ComparisonSetMemberCreate,
    ComparisonSetMemberRead,
    ComparisonSetMemberRemove,
    ComparisonSetMembersAdd,
    ComparisonSetSummaryRead,
    ComparisonSetUpdate,
    ComparisonSetVersionRead,
    WorkspaceDomainExportCreate,
    WorkspaceExportCreate,
    WorkspaceExportPolicyRead,
    WorkspaceExportPolicyUpsert,
)
from pharma_intel.security import Principal

router = APIRouter()


def _human_comparison_service(principal: Principal, session: Session) -> ComparisonSetService:
    if principal.actor_type != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Human workspace session required")
    return ComparisonSetService(
        session, principal.tenant_id, principal.actor_id, include_unpublished=_can_view_unpublished_entities(principal)
    )


def _human_export_service(principal: Principal, session: Session) -> WorkspaceComparisonExportService:
    if principal.actor_type != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Human workspace session required")
    return WorkspaceComparisonExportService(
        session, principal.tenant_id, principal.actor_id, include_unpublished=_can_view_unpublished_entities(principal)
    )


def _comparison_summary(view: ComparisonSetView) -> ComparisonSetSummaryRead:
    return ComparisonSetSummaryRead(
        id=view.item.id,
        owner_user_id=view.item.owner_user_id,
        name=view.item.name,
        description=view.item.description,
        visibility=view.item.visibility,
        version=view.item.version,
        member_count=view.member_count,
        editable=view.editable,
        created_at=view.item.created_at,
        updated_at=view.item.updated_at,
    )


def _comparison_detail(view: ComparisonSetView) -> ComparisonSetDetailRead:
    summary = _comparison_summary(view)
    return ComparisonSetDetailRead(
        **summary.model_dump(),
        members=[ComparisonSetMemberRead.model_validate(member) for member in view.members],
    )


def _comparison_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ComparisonSetNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ComparisonSetLimitExceeded):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get(
    "/api/v1/comparison-sets",
    response_model=list[ComparisonSetSummaryRead],
    tags=["comparison-sets"],
)
def list_comparison_sets(principal: PrincipalDep, session: SessionDep) -> list[ComparisonSetSummaryRead]:
    principal.require("collections:read")
    return [_comparison_summary(item) for item in _human_comparison_service(principal, session).list_sets()]


@router.post(
    "/api/v1/comparison-sets",
    response_model=ComparisonSetDetailRead,
    status_code=status.HTTP_201_CREATED,
    tags=["comparison-sets"],
)
def create_comparison_set(
    payload: ComparisonSetCreate, principal: PrincipalDep, session: SessionDep
) -> ComparisonSetDetailRead:
    principal.require("collections:write")
    try:
        view = _human_comparison_service(principal, session).create_set(payload)
    except ComparisonSetConflict as exc:
        raise _comparison_error(exc) from exc
    return _comparison_detail(view)


@router.get(
    "/api/v1/comparison-sets/{comparison_set_id}",
    response_model=ComparisonSetDetailRead,
    tags=["comparison-sets"],
)
def get_comparison_set(comparison_set_id: str, principal: PrincipalDep, session: SessionDep) -> ComparisonSetDetailRead:
    principal.require("collections:read")
    try:
        view = _human_comparison_service(principal, session).get_set(comparison_set_id)
    except ComparisonSetNotFound as exc:
        raise _comparison_error(exc) from exc
    return _comparison_detail(view)


@router.patch(
    "/api/v1/comparison-sets/{comparison_set_id}",
    response_model=ComparisonSetDetailRead,
    tags=["comparison-sets"],
)
def update_comparison_set(
    comparison_set_id: str,
    payload: ComparisonSetUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> ComparisonSetDetailRead:
    principal.require("collections:write")
    try:
        view = _human_comparison_service(principal, session).update_set(comparison_set_id, payload)
    except (ComparisonSetConflict, ComparisonSetNotFound) as exc:
        raise _comparison_error(exc) from exc
    return _comparison_detail(view)


@router.post(
    "/api/v1/comparison-sets/{comparison_set_id}/members",
    response_model=ComparisonSetDetailRead,
    tags=["comparison-sets"],
)
def add_comparison_set_member(
    comparison_set_id: str,
    payload: ComparisonSetMemberCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> ComparisonSetDetailRead:
    principal.require("collections:write")
    try:
        view = _human_comparison_service(principal, session).add_member(
            comparison_set_id, payload.entity_id, expected_version=payload.expected_version
        )
    except (ComparisonSetConflict, ComparisonSetLimitExceeded, ComparisonSetNotFound) as exc:
        raise _comparison_error(exc) from exc
    return _comparison_detail(view)


@router.post(
    "/api/v1/comparison-sets/{comparison_set_id}/members/batch",
    response_model=ComparisonSetDetailRead,
    tags=["comparison-sets"],
)
def add_comparison_set_members(
    comparison_set_id: str,
    payload: ComparisonSetMembersAdd,
    principal: PrincipalDep,
    session: SessionDep,
) -> ComparisonSetDetailRead:
    principal.require("collections:write")
    try:
        view = _human_comparison_service(principal, session).add_members(
            comparison_set_id,
            payload.entity_ids,
            expected_version=payload.expected_version,
        )
    except (ComparisonSetConflict, ComparisonSetLimitExceeded, ComparisonSetNotFound) as exc:
        raise _comparison_error(exc) from exc
    return _comparison_detail(view)


@router.post(
    "/api/v1/comparison-sets/{comparison_set_id}/members/{entity_id}/remove",
    response_model=ComparisonSetDetailRead,
    tags=["comparison-sets"],
)
def remove_comparison_set_member(
    comparison_set_id: str,
    entity_id: str,
    payload: ComparisonSetMemberRemove,
    principal: PrincipalDep,
    session: SessionDep,
) -> ComparisonSetDetailRead:
    principal.require("collections:write")
    try:
        view = _human_comparison_service(principal, session).remove_member(
            comparison_set_id, entity_id, expected_version=payload.expected_version
        )
    except (ComparisonSetConflict, ComparisonSetNotFound) as exc:
        raise _comparison_error(exc) from exc
    return _comparison_detail(view)


@router.get(
    "/api/v1/comparison-sets/{comparison_set_id}/versions",
    response_model=list[ComparisonSetVersionRead],
    tags=["comparison-sets"],
)
def list_comparison_set_versions(
    comparison_set_id: str, principal: PrincipalDep, session: SessionDep
) -> list[ComparisonSetVersionRead]:
    principal.require("collections:read")
    try:
        versions = _human_comparison_service(principal, session).list_versions(comparison_set_id)
    except ComparisonSetNotFound as exc:
        raise _comparison_error(exc) from exc
    return [
        ComparisonSetVersionRead(
            id=item.id,
            version=item.version,
            snapshot_json=item.snapshot_json,
            changed_by_user_id=item.changed_by_user_id,
            created_at=item.created_at,
        )
        for item in versions
    ]


@router.get(
    "/api/v1/workspace/export-policy",
    response_model=WorkspaceExportPolicyRead,
    tags=["workspace-exports"],
)
def get_workspace_export_policy(principal: PrincipalDep, session: SessionDep) -> WorkspaceExportPolicyRead:
    principal.require("workspace:export")
    try:
        service = _human_export_service(principal, session)
        return WorkspaceExportPolicyRead.model_validate(service.policy_view(service.get_policy()))
    except WorkspaceExportNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/api/v1/admin/workspace-export-policy",
    response_model=WorkspaceExportPolicyRead,
    tags=["workspace-exports"],
)
def configure_workspace_export_policy(
    payload: WorkspaceExportPolicyUpsert, principal: PrincipalDep, session: SessionDep
) -> WorkspaceExportPolicyRead:
    principal.require("workspace:export:manage")
    service = _human_export_service(principal, session)
    try:
        policy = service.upsert_policy(payload)
    except WorkspaceExportDenied as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except WorkspaceExportConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return WorkspaceExportPolicyRead.model_validate(service.policy_view(policy))


@router.post(
    "/api/v1/comparison-sets/{comparison_set_id}/export",
    response_class=Response,
    tags=["workspace-exports"],
)
def export_comparison_set(
    comparison_set_id: str,
    payload: WorkspaceExportCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> Response:
    principal.require("workspace:export")
    try:
        artifact = _human_export_service(principal, session).export_comparison_set(comparison_set_id, payload)
    except ComparisonSetNotFound as exc:
        raise _comparison_error(exc) from exc
    except ComparisonSetConflict as exc:
        raise _comparison_error(exc) from exc
    except WorkspaceExportNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except WorkspaceExportDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except WorkspaceExportConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "X-Export-Event-ID": artifact.event_id,
            "X-Content-SHA256": artifact.content_sha256,
            "X-Export-Policy-Version": artifact.policy_version,
            "X-Export-Replayed": str(artifact.replayed).lower(),
        },
    )


@router.post(
    "/api/v1/workspace/domain-exports",
    response_class=Response,
    tags=["workspace-exports"],
)
def export_workspace_domain_query(
    payload: WorkspaceDomainExportCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> Response:
    principal.require("workspace:export")
    try:
        artifact = _human_export_service(principal, session).export_domain_query(payload)
    except WorkspaceExportNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except WorkspaceExportDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except WorkspaceExportConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "X-Export-Event-ID": artifact.event_id,
            "X-Content-SHA256": artifact.content_sha256,
            "X-Export-Policy-Version": artifact.policy_version,
            "X-Export-Replayed": str(artifact.replayed).lower(),
        },
    )
