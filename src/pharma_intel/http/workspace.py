from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _can_view_unpublished_entities, _public_entity_read
from pharma_intel.models import ReviewStatus, WorkspaceTablePreference
from pharma_intel.operational_metrics import operational_metrics
from pharma_intel.research_activity import ResearchActivityService
from pharma_intel.schemas import (
    RecentEntityVisitRead,
    WebVitalBatchAccepted,
    WebVitalBatchCreate,
    WorkspaceTableDensity,
    WorkspaceTablePreferenceKey,
    WorkspaceTablePreferenceRead,
    WorkspaceTablePreferenceUpdate,
)
from pharma_intel.security import Principal
from pharma_intel.workspace_preferences import WorkspaceTablePreferenceConflict, WorkspaceTablePreferenceService

router = APIRouter()


@router.get(
    "/api/v1/workspace/recent-entities",
    response_model=list[RecentEntityVisitRead],
    tags=["workspace"],
)
def list_recent_entities(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=8, ge=1, le=20),
) -> list[RecentEntityVisitRead]:
    principal.require("entities:read")
    if principal.user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Human user session required")
    return [
        RecentEntityVisitRead(entity=_public_entity_read(item.entity), visited_at=item.visited_at)
        for item in ResearchActivityService(session, principal.tenant_id, principal.user_id).list_recent_entities(limit)
        if _can_view_unpublished_entities(principal) or item.entity.review_status == ReviewStatus.VERIFIED
    ]


def _human_workspace_preference_service(
    principal: Principal,
    session: Session,
) -> WorkspaceTablePreferenceService:
    if principal.actor_type != "user" or principal.user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Human workspace session required")
    return WorkspaceTablePreferenceService(session, principal.tenant_id, principal.user_id)


def _workspace_table_preference_read(
    preference_key: WorkspaceTablePreferenceKey,
    item: WorkspaceTablePreference | None,
) -> WorkspaceTablePreferenceRead:
    if item is None:
        return WorkspaceTablePreferenceRead(
            preference_key=preference_key,
            version=0,
            persisted=False,
        )
    return WorkspaceTablePreferenceRead(
        preference_key=preference_key,
        schema_version=1,
        column_visibility=item.column_visibility,
        column_order=item.column_order,
        density=cast(WorkspaceTableDensity, item.density),
        version=item.version,
        persisted=True,
        updated_at=item.updated_at,
    )


@router.get(
    "/api/v1/workspace/table-preferences/{preference_key}",
    response_model=WorkspaceTablePreferenceRead,
    tags=["workspace"],
)
def get_workspace_table_preference(
    preference_key: WorkspaceTablePreferenceKey,
    principal: PrincipalDep,
    session: SessionDep,
) -> WorkspaceTablePreferenceRead:
    principal.require("entities:read")
    item = _human_workspace_preference_service(principal, session).get(preference_key)
    return _workspace_table_preference_read(preference_key, item)


@router.put(
    "/api/v1/workspace/table-preferences/{preference_key}",
    response_model=WorkspaceTablePreferenceRead,
    responses={status.HTTP_409_CONFLICT: {"description": "Preference version conflict"}},
    tags=["workspace"],
)
def update_workspace_table_preference(
    preference_key: WorkspaceTablePreferenceKey,
    payload: WorkspaceTablePreferenceUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> WorkspaceTablePreferenceRead:
    principal.require("entities:read")
    try:
        item = _human_workspace_preference_service(principal, session).upsert(preference_key, payload)
    except WorkspaceTablePreferenceConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _workspace_table_preference_read(preference_key, item)


@router.post(
    "/api/v1/workspace/web-vitals",
    response_model=WebVitalBatchAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["workspace"],
)
def report_workspace_web_vitals(
    payload: WebVitalBatchCreate,
    principal: PrincipalDep,
) -> WebVitalBatchAccepted:
    principal.require("entities:read")
    if principal.actor_type != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Human workspace session required")
    instruments = operational_metrics()
    for sample in payload.samples:
        instruments.record_web_vital(
            sample.metric_name,
            sample.route,
            sample.rating,
            sample.viewport_class,
            sample.navigation_type,
            sample.value,
        )
    return WebVitalBatchAccepted(accepted_count=len(payload.samples))
