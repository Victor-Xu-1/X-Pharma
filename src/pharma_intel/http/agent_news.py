from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, Query

from pharma_intel.http.agent_page import _agent_page
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _intelligence_service
from pharma_intel.http.query_contracts import _sort_reads, _validated_sort
from pharma_intel.schemas import (
    NEWS_SORT_FIELDS,
    AgentPageResult,
    NewsEventSearchItemRead,
    NewsSortField,
    SortDirection,
    SortToken,
)

router = APIRouter()


@router.get(
    "/internal/v1/domain/news-events",
    response_model=AgentPageResult[NewsEventSearchItemRead],
    tags=["internal-domain"],
)
def search_news_events_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    entity_id: str | None = Query(default=None, max_length=500),
    q: str | None = Query(default=None, max_length=500),
    event_type: str | None = Query(default=None, max_length=40),
    publisher: str | None = Query(default=None, max_length=500),
    language: str | None = Query(default=None, max_length=32),
    venue: str | None = Query(default=None, max_length=240),
    published_from: Annotated[datetime | None, Query()] = None,
    published_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: NewsSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[NewsEventSearchItemRead]:
    principal.require("news:read")
    effective_sort = _validated_sort(
        sort,
        NEWS_SORT_FIELDS,
        default_field="published_at",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    arguments: dict[str, object] = {
        "limit": limit,
        "sort": [clause.token for clause in effective_sort],
    }
    for name, value in (
        ("entity_id", entity_id),
        ("q", q),
        ("event_type", event_type),
        ("publisher", publisher),
        ("language", language),
        ("venue", venue),
        ("published_from", published_from.isoformat() if published_from else None),
        ("published_to", published_to.isoformat() if published_to else None),
        ("cursor", cursor),
    ):
        if value is not None:
            arguments[name] = value
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="news.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[entity_id],
        fetch=lambda offset, fetch_limit: intelligence.news_event_search_items(
            entity_id,
            q,
            event_type,
            publisher,
            language,
            venue,
            published_from,
            published_to,
            fetch_limit,
            offset,
            sort=effective_sort,
        ),
        sort=_sort_reads(effective_sort),
    )
