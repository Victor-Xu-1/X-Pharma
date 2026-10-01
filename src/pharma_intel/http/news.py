from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _assert_public_entity_ids_visible, _intelligence_service
from pharma_intel.http.query_contracts import _validated_sort
from pharma_intel.schemas import (
    NEWS_SORT_FIELDS,
    NewsEventSearchItemRead,
    NewsEventSearchResult,
    NewsSortField,
    SortDirection,
    SortToken,
)

router = APIRouter()


@router.get("/api/v1/news-events", response_model=NewsEventSearchResult, tags=["news"])
def search_news_events(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    entity_id: str | None = Query(default=None, max_length=36),
    event_type: str | None = Query(default=None, max_length=40),
    publisher: str | None = Query(default=None, max_length=500),
    language: str | None = Query(default=None, max_length=32),
    venue: str | None = Query(default=None, max_length=240),
    content_scope: Literal["research"] | None = Query(default=None),
    published_from: Annotated[datetime | None, Query()] = None,
    published_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    sort_by: NewsSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> NewsEventSearchResult:
    principal.require("news:read")
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    effective_sort = _validated_sort(
        sort,
        NEWS_SORT_FIELDS,
        default_field="published_at",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    return _intelligence_service(session, principal).search_news_events(
        q,
        event_type,
        publisher,
        language,
        venue,
        published_from,
        published_to,
        limit,
        offset,
        research_content_only=content_scope == "research",
        entity_id=entity_id,
        sort=effective_sort,
    )


@router.get(
    "/api/v1/news-events/{event_id}",
    response_model=NewsEventSearchItemRead,
    tags=["news"],
)
def get_news_event(
    event_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> NewsEventSearchItemRead:
    principal.require("news:read")
    event = _intelligence_service(session, principal).news_event_detail(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="News event not found")
    return event
