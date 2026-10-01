from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from pharma_intel.commercial.operations import CommercialOperationsService
from pharma_intel.commercial.risk_cursor import RiskCursorCodec, RiskCursorError
from pharma_intel.http import runtime
from pharma_intel.http.commercial_policy import _require_human_commercial
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.schemas import (
    CommercialClientRead,
    CommercialClientStatusUpdate,
    CommercialRiskEventPageRead,
    CommercialRiskEventRead,
    CommercialRiskReview,
)

router = APIRouter()


@router.get(
    "/api/v1/commercial/clients",
    response_model=list[CommercialClientRead],
    tags=["commercial"],
)
def list_commercial_clients(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[CommercialClientRead]:
    _require_human_commercial(principal, "commercial:read")
    items = CommercialOperationsService(session, principal).list_clients(limit=limit)
    return [CommercialClientRead.model_validate(item) for item in items]


@router.post(
    "/api/v1/commercial/clients/{client_id}/status",
    response_model=CommercialClientRead,
    tags=["commercial"],
)
def update_commercial_client_status(
    client_id: str,
    payload: CommercialClientStatusUpdate,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialClientRead:
    _require_human_commercial(principal, "commercial:write")
    try:
        item = CommercialOperationsService(session, principal).set_client_active(
            client_id,
            active=payload.active,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CommercialClientRead.model_validate(item)


@router.get(
    "/api/v1/commercial/risk-events",
    response_model=list[CommercialRiskEventRead],
    tags=["commercial"],
)
def list_commercial_risk_events(
    principal: PrincipalDep,
    session: SessionDep,
    case_status: Literal["all", "open", "acknowledged", "resolved", "dismissed"] = "all",
    limit: int = Query(default=200, ge=1, le=500),
) -> list[CommercialRiskEventRead]:
    _require_human_commercial(principal, "commercial:read")
    items = CommercialOperationsService(session, principal).list_risk_events(
        status=case_status,
        limit=limit,
    )
    return [CommercialRiskEventRead.model_validate(item) for item in items]


@router.get(
    "/api/v1/commercial/risk-events/page",
    response_model=CommercialRiskEventPageRead,
    tags=["commercial"],
)
def page_commercial_risk_events(
    principal: PrincipalDep,
    session: SessionDep,
    case_status: Literal["all", "open", "acknowledged", "resolved", "dismissed"] = "all",
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None, min_length=20, max_length=4096),
) -> CommercialRiskEventPageRead:
    _require_human_commercial(principal, "commercial:read")
    settings = runtime.get_settings()
    try:
        page = CommercialOperationsService(session, principal).list_risk_event_page(
            status=case_status,
            limit=limit,
            cursor=cursor,
            cursor_codec=RiskCursorCodec(
                settings.effective_mcp_cursor_signing_secret,
                ttl_seconds=settings.mcp_cursor_ttl_seconds,
                max_token_chars=settings.mcp_cursor_max_token_chars,
            ),
        )
    except RiskCursorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CommercialRiskEventPageRead(
        items=[CommercialRiskEventRead.model_validate(item) for item in page.items],
        total_items=page.total_items,
        next_cursor=page.next_cursor,
    )


@router.post(
    "/api/v1/commercial/risk-events/{event_id}/review",
    response_model=CommercialRiskEventRead,
    tags=["commercial"],
)
def review_commercial_risk_event(
    event_id: str,
    payload: CommercialRiskReview,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialRiskEventRead:
    _require_human_commercial(principal, "commercial:write")
    item = CommercialOperationsService(session, principal).review_risk_event(
        event_id,
        status=payload.status,
        notes=payload.notes,
    )
    return CommercialRiskEventRead.model_validate(item)
