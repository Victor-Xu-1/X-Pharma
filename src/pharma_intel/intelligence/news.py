from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import String, cast, func, literal, or_, select, true
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.facets import (
    _applied_filters,
    _landscape_scalar_buckets,
    _linked_entity_facets,
    _scalar_facet_counts,
)
from pharma_intel.intelligence.scope import _published_optional_entity
from pharma_intel.intelligence.vocabulary import (
    RESEARCH_PUBLICATION_EVENT_TYPES,
    _ordered_sort_expressions,
    _sort_criteria_read,
)
from pharma_intel.models import Entity, NewsEvent, ReviewStatus
from pharma_intel.schemas import (
    NEWS_SORT_FIELDS,
    NewsEventLinkedEntityRead,
    NewsEventRead,
    NewsEventSearchItemRead,
    NewsEventSearchResult,
    NewsLandscapeBucketRead,
    NewsLandscapeRead,
    NewsSavedSearchQuery,
    NewsSortField,
    SortDirection,
)
from pharma_intel.sorting import SortClause, validate_sort_clauses


def search_news_events(
    context: QueryContext,
    query: str | None,
    event_type: str | None,
    publisher: str | None,
    language: str | None,
    venue: str | None,
    published_from: datetime | None,
    published_to: datetime | None,
    limit: int,
    offset: int,
    *,
    entity_id: str | None = None,
    research_content_only: bool = False,
    sort_by: NewsSortField = "published_at",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[NewsSortField]] | None = None,
) -> NewsEventSearchResult:
    effective_sort = validate_sort_clauses(
        sort,
        NEWS_SORT_FIELDS,
        default_field=sort_by,
        default_direction=sort_direction,
    )
    filters = _news_event_filters(
        context,
        entity_id,
        query,
        event_type,
        publisher,
        language,
        venue,
        published_from,
        published_to,
    )
    if research_content_only:
        filters.append(NewsEvent.event_type.in_(RESEARCH_PUBLICATION_EVENT_TYPES))
    items = _news_event_search_items(
        context,
        filters,
        limit,
        offset,
        sort=effective_sort,
    )
    facet_source = (
        select(
            NewsEvent.id.label("event_id"),
            NewsEvent.event_type.label("event_type"),
            NewsEvent.language.label("language"),
            NewsEvent.venue.label("venue"),
            NewsEvent.publisher_entity_id.label("publisher_entity_id"),
            NewsEvent.published_at.label("published_at"),
        )
        .where(*filters)
        .subquery()
    )
    facets = {name: _scalar_facet_counts(context, facet_source, name) for name in ("event_type", "language", "venue")}
    facets["publisher"] = _linked_entity_facets(context, facet_source, "publisher_entity_id", "event_id")
    news_total = int(context.session.scalar(select(func.count()).select_from(facet_source)) or 0)
    year_column = func.extract("year", facet_source.c.published_at)
    year_rows = context.session.execute(
        select(year_column.label("published_year"), func.count()).select_from(facet_source).group_by("published_year")
    ).all()
    published_year = sorted(
        (
            NewsLandscapeBucketRead(
                key="__missing__" if year is None else str(int(year)),
                label="未披露" if year is None else str(int(year)),
                count=int(count),
                share=(int(count) / news_total) if news_total else 0.0,
            )
            for year, count in year_rows
        ),
        key=lambda item: (item.key == "__missing__", item.key),
        reverse=True,
    )
    landscape = NewsLandscapeRead(
        total_events=news_total,
        event_type=_landscape_scalar_buckets(context, facet_source, "event_type", news_total, NewsLandscapeBucketRead),
        venue=_landscape_scalar_buckets(context, facet_source, "venue", news_total, NewsLandscapeBucketRead),
        published_year=published_year,
    )
    return NewsEventSearchResult(
        query_schema_version="pharma.news.search.v2",
        applied_filters=_applied_filters(
            ("entity_id", "eq", entity_id),
            ("q", "contains", query.strip() if query else None),
            ("event_type", "eq", event_type),
            ("publisher", "contains", publisher),
            ("language", "eq", language),
            ("venue", "contains", venue),
            ("published_from", "gte", published_from.isoformat() if published_from else None),
            ("published_to", "lte", published_to.isoformat() if published_to else None),
            ("content_scope", "eq", "research" if research_content_only else None),
        ),
        items=items,
        total=news_total,
        limit=limit,
        offset=offset,
        sort_by=effective_sort[0].field,
        sort_direction=effective_sort[0].direction,
        sort=_sort_criteria_read(effective_sort),
        facets=facets,
        landscape=landscape,
        as_of=datetime.now(UTC),
        warnings=["未观察到事件不代表事件未发生；结果受来源授权、抓取时效、实体治理和发布时间完整性限制。"],
    )


def news_event_search_items(
    context: QueryContext,
    entity_id: str | None,
    query: str | None,
    event_type: str | None,
    publisher: str | None,
    language: str | None,
    venue: str | None,
    published_from: datetime | None,
    published_to: datetime | None,
    limit: int,
    offset: int = 0,
    *,
    sort_by: NewsSortField = "published_at",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[NewsSortField]] | None = None,
) -> list[NewsEventSearchItemRead]:
    return _news_event_search_items(
        context,
        _news_event_filters(
            context,
            entity_id,
            query,
            event_type,
            publisher,
            language,
            venue,
            published_from,
            published_to,
        ),
        limit,
        offset,
        sort=validate_sort_clauses(
            sort,
            NEWS_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        ),
    )


def news_saved_search_matches_entity(context: QueryContext, entity_id: str, query: NewsSavedSearchQuery) -> bool:
    def start(value: Any) -> datetime | None:
        return datetime.combine(value, time.min, tzinfo=UTC) if value else None

    def end(value: Any) -> datetime | None:
        return datetime.combine(value, time.max, tzinfo=UTC) if value else None

    filters = _news_event_filters(
        context,
        entity_id,
        query.q,
        query.event_type,
        query.publisher,
        query.language,
        query.venue,
        start(query.published_from),
        end(query.published_to),
    )
    if query.entity_id:
        # The saved canonical-entity condition constrains in addition to the changed
        # entity relation, so replay keeps the exact saved semantics.
        filters.append(
            or_(
                NewsEvent.publisher_entity_id == query.entity_id,
                cast(NewsEvent.related_entity_ids, String).contains(f'"{query.entity_id}"', autoescape=True),
            )
        )
    if query.content_scope == "research":
        filters.append(NewsEvent.event_type.in_(RESEARCH_PUBLICATION_EVENT_TYPES))
    statement = select(NewsEvent.id).where(*filters)
    return context.session.scalar(statement.with_only_columns(literal(True)).limit(1)) is True


def news_event_detail(context: QueryContext, event_id: str) -> NewsEventSearchItemRead | None:
    items = _news_event_search_items(
        context,
        [
            NewsEvent.tenant_id == context.tenant_id,
            NewsEvent.id == event_id,
            _published_optional_entity(context, NewsEvent.publisher_entity_id),
        ],
        1,
        0,
    )
    return items[0] if items else None


def _news_event_search_items(
    context: QueryContext,
    filters: list[ColumnElement[bool]],
    limit: int,
    offset: int,
    *,
    sort_by: NewsSortField = "published_at",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[NewsSortField]] | None = None,
) -> list[NewsEventSearchItemRead]:
    effective_sort = validate_sort_clauses(
        sort,
        NEWS_SORT_FIELDS,
        default_field=sort_by,
        default_direction=sort_direction,
    )
    publisher_name = (
        select(func.lower(Entity.name))
        .where(Entity.tenant_id == context.tenant_id, Entity.id == NewsEvent.publisher_entity_id)
        .correlate(NewsEvent)
        .scalar_subquery()
    )
    sort_expressions: dict[NewsSortField, Any] = {
        "published_at": NewsEvent.published_at,
        "title": func.lower(NewsEvent.title),
        "event_type": func.lower(NewsEvent.event_type),
        "publisher": publisher_name,
        "venue": func.lower(NewsEvent.venue),
    }
    ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
    rows = context.session.scalars(
        select(NewsEvent)
        .where(*filters)
        .order_by(*ordered_sort, NewsEvent.event_identifier, NewsEvent.id)
        .limit(limit)
        .offset(offset)
    ).all()
    entity_ids = {
        entity_id
        for row in rows
        for entity_id in ([row.publisher_entity_id] if row.publisher_entity_id else []) + row.related_entity_ids
    }
    entities = (
        context.session.scalars(
            select(Entity)
            .where(Entity.tenant_id == context.tenant_id, Entity.id.in_(entity_ids))
            .order_by(Entity.entity_type, Entity.name, Entity.id)
        ).all()
        if entity_ids
        else []
    )
    linked_by_id = {
        entity.id: NewsEventLinkedEntityRead(id=entity.id, name=entity.name, entity_type=entity.entity_type)
        for entity in entities
    }
    return [
        NewsEventSearchItemRead(
            **NewsEventRead.model_validate(row).model_dump(),
            publisher_entity=linked_by_id.get(row.publisher_entity_id or ""),
            related_entities=[
                linked_by_id[entity_id] for entity_id in row.related_entity_ids if entity_id in linked_by_id
            ],
        )
        for row in rows
    ]


def _news_event_filters(
    context: QueryContext,
    entity_id: str | None,
    query: str | None,
    event_type: str | None,
    publisher: str | None,
    language: str | None,
    venue: str | None,
    published_from: datetime | None,
    published_to: datetime | None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [NewsEvent.tenant_id == context.tenant_id]
    if not context.include_unpublished:
        filters.append(_published_optional_entity(context, NewsEvent.publisher_entity_id))
    if entity_id:
        filters.append(
            or_(
                NewsEvent.publisher_entity_id == entity_id,
                cast(NewsEvent.related_entity_ids, String).contains(f'"{entity_id}"', autoescape=True),
            )
        )
    if event_type:
        filters.append(NewsEvent.event_type == event_type)
    if language:
        filters.append(NewsEvent.language == language)
    if venue:
        filters.append(NewsEvent.venue == venue)
    if published_from:
        filters.append(NewsEvent.published_at >= published_from)
    if published_to:
        filters.append(NewsEvent.published_at <= published_to)
    if publisher:
        publisher_pattern = publisher.strip()
        publisher_entity = aliased(Entity)
        filters.append(
            select(publisher_entity.id)
            .where(
                publisher_entity.tenant_id == context.tenant_id,
                publisher_entity.id == NewsEvent.publisher_entity_id,
                publisher_entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                publisher_entity.name.icontains(publisher_pattern, autoescape=True),
            )
            .exists()
        )
    if query:
        pattern = query.strip()
        publisher_entity = aliased(Entity)
        filters.append(
            or_(
                NewsEvent.event_identifier.icontains(pattern, autoescape=True),
                NewsEvent.title.icontains(pattern, autoescape=True),
                NewsEvent.summary.icontains(pattern, autoescape=True),
                NewsEvent.venue.icontains(pattern, autoescape=True),
                select(publisher_entity.id)
                .where(
                    publisher_entity.tenant_id == context.tenant_id,
                    publisher_entity.id == NewsEvent.publisher_entity_id,
                    publisher_entity.review_status == ReviewStatus.VERIFIED
                    if not context.include_unpublished
                    else true(),
                    publisher_entity.name.icontains(pattern, autoescape=True),
                )
                .exists(),
            )
        )
    return filters
