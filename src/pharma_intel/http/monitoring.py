from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.monitoring.service import MonitoringConflict, MonitoringNotFound, MonitoringReplay, MonitoringService
from pharma_intel.schemas import (
    MonitoringAlertRead,
    MonitoringTopicCreate,
    MonitoringTopicRead,
    MonitoringTopicUpdate,
    SavedSearchCreate,
    SavedSearchRead,
    SavedSearchUpdate,
)
from pharma_intel.security import Principal

router = APIRouter()


def _human_monitoring_service(principal: Principal, session: Session) -> MonitoringService:
    if principal.actor_type != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Human workspace session required")
    return MonitoringService(session, principal.tenant_id, principal.actor_id)


def _replay_read(replay: MonitoringReplay) -> SavedSearchRead:
    payload = SavedSearchRead.model_validate(replay.saved_search).model_dump()
    payload.update(
        query_type=replay.version.query_type,
        query_version=replay.version.version,
        query_json=replay.version.query_json,
        updated_at=replay.version.created_at,
    )
    return SavedSearchRead.model_validate(payload)


@router.get(
    "/api/v1/monitoring/topics/{topic_id}/replay",
    response_model=SavedSearchRead,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    tags=["monitoring"],
)
def replay_monitoring_topic(topic_id: str, principal: PrincipalDep, session: SessionDep) -> SavedSearchRead:
    principal.require("monitoring:read")
    try:
        return _replay_read(_human_monitoring_service(principal, session).replay_topic(topic_id))
    except MonitoringNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/api/v1/monitoring/alerts/{alert_id}/replay",
    response_model=SavedSearchRead,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    tags=["monitoring"],
)
def replay_monitoring_alert(alert_id: str, principal: PrincipalDep, session: SessionDep) -> SavedSearchRead:
    principal.require("monitoring:read")
    try:
        return _replay_read(_human_monitoring_service(principal, session).replay_alert(alert_id))
    except MonitoringNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/api/v1/monitoring/saved-searches",
    response_model=list[SavedSearchRead],
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    tags=["monitoring"],
)
def list_saved_searches(principal: PrincipalDep, session: SessionDep) -> list[SavedSearchRead]:
    principal.require("monitoring:read")
    items = _human_monitoring_service(principal, session).list_saved_searches()
    return [SavedSearchRead.model_validate(item) for item in items]


@router.get(
    "/api/v1/monitoring/saved-searches/{saved_search_id}",
    response_model=SavedSearchRead,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    tags=["monitoring"],
)
def get_saved_search(saved_search_id: str, principal: PrincipalDep, session: SessionDep) -> SavedSearchRead:
    principal.require("monitoring:read")
    try:
        item = _human_monitoring_service(principal, session).get_saved_search(saved_search_id)
    except MonitoringNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SavedSearchRead.model_validate(item)


@router.post(
    "/api/v1/monitoring/saved-searches",
    response_model=SavedSearchRead,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    status_code=status.HTTP_201_CREATED,
    tags=["monitoring"],
)
def create_saved_search(payload: SavedSearchCreate, principal: PrincipalDep, session: SessionDep) -> SavedSearchRead:
    principal.require("monitoring:write")
    try:
        item = _human_monitoring_service(principal, session).create_saved_search(payload)
    except MonitoringConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return SavedSearchRead.model_validate(item)


@router.patch(
    "/api/v1/monitoring/saved-searches/{saved_search_id}",
    response_model=SavedSearchRead,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
    tags=["monitoring"],
)
def update_saved_search(
    saved_search_id: str,
    payload: SavedSearchUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> SavedSearchRead:
    principal.require("monitoring:write")
    try:
        item = _human_monitoring_service(principal, session).update_saved_search(saved_search_id, payload)
    except MonitoringNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MonitoringConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return SavedSearchRead.model_validate(item)


@router.get(
    "/api/v1/monitoring/topics",
    response_model=list[MonitoringTopicRead],
    tags=["monitoring"],
)
def list_monitoring_topics(principal: PrincipalDep, session: SessionDep) -> list[MonitoringTopicRead]:
    principal.require("monitoring:read")
    items = _human_monitoring_service(principal, session).list_topics()
    return [MonitoringTopicRead.model_validate(item) for item in items]


@router.post(
    "/api/v1/monitoring/topics",
    response_model=MonitoringTopicRead,
    status_code=status.HTTP_201_CREATED,
    tags=["monitoring"],
)
def create_monitoring_topic(
    payload: MonitoringTopicCreate, principal: PrincipalDep, session: SessionDep
) -> MonitoringTopicRead:
    principal.require("monitoring:write")
    try:
        item = _human_monitoring_service(principal, session).create_topic(payload.name, payload.saved_search_id)
    except MonitoringNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MonitoringConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return MonitoringTopicRead.model_validate(item)


@router.patch(
    "/api/v1/monitoring/topics/{topic_id}",
    response_model=MonitoringTopicRead,
    tags=["monitoring"],
)
def update_monitoring_topic(
    topic_id: str,
    payload: MonitoringTopicUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> MonitoringTopicRead:
    principal.require("monitoring:write")
    try:
        item = _human_monitoring_service(principal, session).update_topic(
            topic_id,
            name=payload.name,
            active=payload.active,
            query_version=payload.query_version,
        )
    except MonitoringNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MonitoringConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return MonitoringTopicRead.model_validate(item)


@router.get(
    "/api/v1/monitoring/alerts",
    response_model=list[MonitoringAlertRead],
    tags=["monitoring"],
)
def list_monitoring_alerts(
    principal: PrincipalDep,
    session: SessionDep,
    unread_only: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MonitoringAlertRead]:
    principal.require("monitoring:read")
    return [
        MonitoringAlertRead.model_validate(item)
        for item in _human_monitoring_service(principal, session).list_alerts(unread_only=unread_only, limit=limit)
    ]


@router.post(
    "/api/v1/monitoring/alerts/{alert_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["monitoring"],
)
def mark_monitoring_alert_read(alert_id: str, principal: PrincipalDep, session: SessionDep) -> Response:
    principal.require("monitoring:write")
    try:
        _human_monitoring_service(principal, session).mark_alert_read(alert_id)
    except MonitoringNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
