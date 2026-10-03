from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, Query

from pharma_intel.http.agent_page import _agent_page
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _intelligence_service
from pharma_intel.http.query_contracts import _sort_reads, _validated_sort, _validated_utc_datetime_range
from pharma_intel.models import (
    RegulatoryDesignationType,
    RegulatoryLabelChangeType,
    RegulatorySafetySeverity,
    RegulatorySafetySignalType,
    RegulatorySafetyStatus,
)
from pharma_intel.schemas import (
    REGULATORY_SORT_FIELDS,
    AgentPageResult,
    RegulatoryEventSearchItemRead,
    RegulatorySortField,
    SortDirection,
    SortToken,
)

router = APIRouter()


@router.get(
    "/internal/v1/domain/regulatory-events",
    response_model=AgentPageResult[RegulatoryEventSearchItemRead],
    tags=["internal-domain"],
)
def search_regulatory_events_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    entity_id: str | None = Query(default=None, max_length=500),
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
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: RegulatorySortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[RegulatoryEventSearchItemRead]:
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
    arguments: dict[str, object] = {
        "limit": limit,
        "sort": [clause.token for clause in effective_sort],
    }
    for name, value in (
        ("entity_id", entity_id),
        ("q", q),
        ("agency", agency),
        ("jurisdiction", jurisdiction),
        ("event_type", event_type),
        ("status", status),
        ("designation_type", designation_type.value if designation_type else None),
        ("label_change_type", label_change_type.value if label_change_type else None),
        ("has_boxed_warning", has_boxed_warning),
        ("safety_signal_type", safety_signal_type.value if safety_signal_type else None),
        ("safety_severity", safety_severity.value if safety_severity else None),
        ("safety_status", safety_status.value if safety_status else None),
        ("decision_from", decision_from.isoformat() if decision_from else None),
        ("decision_to", decision_to.isoformat() if decision_to else None),
        ("source_updated_from", source_updated_from.isoformat() if source_updated_from else None),
        ("source_updated_to", source_updated_to.isoformat() if source_updated_to else None),
    ):
        if value is not None:
            arguments[name] = value
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="regulatory.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[entity_id],
        fetch=lambda offset, fetch_limit: intelligence.regulatory_search_items(
            entity_id,
            q,
            agency,
            jurisdiction,
            event_type,
            status,
            fetch_limit,
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
        ),
        sort=_sort_reads(effective_sort),
    )
