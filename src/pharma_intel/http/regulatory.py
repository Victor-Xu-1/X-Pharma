from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _assert_public_entity_ids_visible, _intelligence_service
from pharma_intel.http.query_contracts import _validated_sort, _validated_utc_datetime_range
from pharma_intel.models import (
    RegulatoryDesignationType,
    RegulatoryLabelChangeType,
    RegulatorySafetySeverity,
    RegulatorySafetySignalType,
    RegulatorySafetyStatus,
)
from pharma_intel.schemas import (
    REGULATORY_SORT_FIELDS,
    RegulatoryEventRead,
    RegulatoryEventSearchItemRead,
    RegulatoryEventSearchResult,
    RegulatorySortField,
    SortDirection,
    SortToken,
)

router = APIRouter()


@router.get("/api/v1/regulatory-events", response_model=list[RegulatoryEventRead], tags=["regulatory"])
def search_regulatory_events(
    principal: PrincipalDep,
    session: SessionDep,
    entity_id: str | None = None,
    q: str | None = Query(default=None, max_length=500),
    agency: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[RegulatoryEventRead]:
    principal.require("regulatory:read")
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    return _intelligence_service(session, principal).regulatory_events(entity_id, q, agency, limit)


@router.get(
    "/api/v1/regulatory-event-timeline",
    response_model=RegulatoryEventSearchResult,
    tags=["regulatory"],
)
def search_regulatory_event_timeline(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    agency: str | None = Query(default=None, max_length=80),
    jurisdiction: str | None = Query(default=None, max_length=120),
    event_type: str | None = Query(default=None, max_length=40),
    status: str | None = Query(default=None, max_length=120),
    designation_type: RegulatoryDesignationType | None = None,
    label_change_type: RegulatoryLabelChangeType | None = None,
    has_boxed_warning: bool | None = None,
    safety_signal_type: RegulatorySafetySignalType | None = None,
    safety_severity: RegulatorySafetySeverity | None = None,
    safety_status: RegulatorySafetyStatus | None = None,
    decision_from: Annotated[datetime | None, Query()] = None,
    decision_to: Annotated[datetime | None, Query()] = None,
    source_updated_from: Annotated[datetime | None, Query()] = None,
    source_updated_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    sort_by: RegulatorySortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> RegulatoryEventSearchResult:
    principal.require("regulatory:read")
    effective_sort = _validated_sort(
        sort,
        REGULATORY_SORT_FIELDS,
        default_field="decision_date",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    decision_from, decision_to = _validated_utc_datetime_range(
        decision_from,
        decision_to,
        start_field="decision_from",
        end_field="decision_to",
    )
    source_updated_from, source_updated_to = _validated_utc_datetime_range(
        source_updated_from,
        source_updated_to,
        start_field="source_updated_from",
        end_field="source_updated_to",
    )
    return _intelligence_service(session, principal).search_regulatory_events(
        q,
        agency,
        jurisdiction,
        event_type,
        status,
        limit,
        offset,
        designation_type=designation_type.value if designation_type else None,
        label_change_type=label_change_type.value if label_change_type else None,
        has_boxed_warning=has_boxed_warning,
        safety_signal_type=safety_signal_type.value if safety_signal_type else None,
        safety_severity=safety_severity.value if safety_severity else None,
        safety_status=safety_status.value if safety_status else None,
        decision_from=decision_from,
        decision_to=decision_to,
        source_updated_from=source_updated_from,
        source_updated_to=source_updated_to,
        sort=effective_sort,
    )


@router.get(
    "/api/v1/regulatory-event-timeline/{event_id}",
    response_model=RegulatoryEventSearchItemRead,
    tags=["regulatory"],
)
def get_regulatory_event_timeline_item(
    event_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> RegulatoryEventSearchItemRead:
    principal.require("regulatory:read")
    event = _intelligence_service(session, principal).regulatory_event_detail(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Regulatory event not found")
    return event
