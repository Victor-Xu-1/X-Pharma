from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import func, literal, or_, select, true
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.deal_filters import _target_asset_ids
from pharma_intel.intelligence.facets import _applied_filters, _scalar_facet_counts
from pharma_intel.intelligence.scope import _published_entity_exists, _published_optional_entity
from pharma_intel.intelligence.vocabulary import _ordered_sort_expressions, _sort_criteria_read
from pharma_intel.models import Entity, RegulatoryEvent, ReviewStatus
from pharma_intel.schemas import (
    REGULATORY_SORT_FIELDS,
    RegulatoryEventLinkedEntityRead,
    RegulatoryEventRead,
    RegulatoryEventSearchItemRead,
    RegulatoryEventSearchResult,
    RegulatoryLandscapeBucketRead,
    RegulatoryLandscapeRead,
    RegulatorySavedSearchQuery,
    RegulatorySortField,
    SortDirection,
)
from pharma_intel.sorting import SortClause, validate_sort_clauses


def _regulatory_landscape(context: QueryContext, source: Any, total: int) -> RegulatoryLandscapeRead:
    """Aggregate the complete filtered regulatory set for the same-query statistics view."""

    def bucket(key: str, count: int) -> RegulatoryLandscapeBucketRead:
        return RegulatoryLandscapeBucketRead(
            key=key,
            label="未披露" if key == "__missing__" else key,
            count=count,
            share=(count / total) if total else 0.0,
        )

    def scalar_buckets(column_name: str) -> list[RegulatoryLandscapeBucketRead]:
        column = func.coalesce(getattr(source.c, column_name), "__missing__")
        rows = context.session.execute(
            select(column.label("value"), func.count())
            .select_from(source)
            .group_by("value")
            .order_by(func.count().desc(), column)
        ).all()
        return [bucket(str(value), int(count)) for value, count in rows]

    year_column = func.extract("year", source.c.decision_date)
    year_rows = context.session.execute(
        select(year_column.label("decision_year"), func.count()).select_from(source).group_by("decision_year")
    ).all()
    decision_year = sorted(
        (bucket("__missing__" if year is None else str(int(year)), int(count)) for year, count in year_rows),
        key=lambda item: (item.key == "__missing__", item.key),
        reverse=True,
    )

    return RegulatoryLandscapeRead(
        total_events=total,
        event_type=scalar_buckets("event_type"),
        agency=scalar_buckets("agency"),
        decision_year=decision_year,
    )


def regulatory_events(
    context: QueryContext,
    entity_id: str | None,
    query: str | None,
    agency: str | None,
    limit: int,
    offset: int = 0,
    jurisdiction: str | None = None,
    event_type: str | None = None,
    status: str | None = None,
) -> list[RegulatoryEventRead]:
    filters = _regulatory_filters(
        context,
        entity_id,
        query,
        agency,
        jurisdiction=jurisdiction,
        event_type=event_type,
        status=status,
    )
    rows = context.session.scalars(
        select(RegulatoryEvent)
        .where(*filters)
        .order_by(RegulatoryEvent.decision_date.desc().nullslast(), RegulatoryEvent.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [RegulatoryEventRead.model_validate(row) for row in rows]


def search_regulatory_events(
    context: QueryContext,
    query: str | None,
    agency: str | None,
    jurisdiction: str | None,
    event_type: str | None,
    status: str | None,
    limit: int,
    offset: int,
    *,
    entity_id: str | None = None,
    designation_type: str | None = None,
    label_change_type: str | None = None,
    has_boxed_warning: bool | None = None,
    safety_signal_type: str | None = None,
    safety_severity: str | None = None,
    safety_status: str | None = None,
    decision_from: datetime | None = None,
    decision_to: datetime | None = None,
    source_updated_from: datetime | None = None,
    source_updated_to: datetime | None = None,
    sort_by: RegulatorySortField = "decision_date",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[RegulatorySortField]] | None = None,
) -> RegulatoryEventSearchResult:
    effective_sort = validate_sort_clauses(
        sort,
        REGULATORY_SORT_FIELDS,
        default_field=sort_by,
        default_direction=sort_direction,
    )
    filters = _regulatory_filters(
        context,
        entity_id,
        query,
        agency,
        jurisdiction=jurisdiction,
        event_type=event_type,
        status=status,
        designation_type=designation_type,
        label_change_type=label_change_type,
        has_boxed_warning=has_boxed_warning,
        safety_signal_type=safety_signal_type,
        safety_severity=safety_severity,
        safety_status=safety_status,
        decision_from=decision_from,
        decision_to=decision_to,
        source_updated_from=source_updated_from,
        source_updated_to=source_updated_to,
    )
    items = _regulatory_search_items(
        context,
        filters,
        limit,
        offset,
        sort=effective_sort,
    )
    facet_source = (
        select(
            RegulatoryEvent.id.label("event_id"),
            RegulatoryEvent.agency.label("agency"),
            RegulatoryEvent.jurisdiction.label("jurisdiction"),
            RegulatoryEvent.event_type.label("event_type"),
            RegulatoryEvent.status.label("status"),
            RegulatoryEvent.designation_type.label("designation_type"),
            RegulatoryEvent.label_change_type.label("label_change_type"),
            RegulatoryEvent.has_boxed_warning.label("has_boxed_warning"),
            RegulatoryEvent.safety_signal_type.label("safety_signal_type"),
            RegulatoryEvent.safety_severity.label("safety_severity"),
            RegulatoryEvent.safety_status.label("safety_status"),
            RegulatoryEvent.decision_date.label("decision_date"),
        )
        .where(*filters)
        .subquery()
    )
    total = context.session.scalar(select(func.count()).select_from(facet_source)) or 0
    facets = {
        name: _scalar_facet_counts(context, facet_source, name)
        for name in (
            "agency",
            "jurisdiction",
            "event_type",
            "status",
            "designation_type",
            "label_change_type",
            "has_boxed_warning",
            "safety_signal_type",
            "safety_severity",
            "safety_status",
        )
    }
    landscape = _regulatory_landscape(context, facet_source, total)
    return RegulatoryEventSearchResult(
        query_schema_version="pharma.regulatory.search.v4",
        applied_filters=_applied_filters(
            ("entity_id", "eq", entity_id),
            ("q", "contains", query.strip() if query else None),
            ("agency", "eq", agency),
            ("jurisdiction", "eq", jurisdiction),
            ("event_type", "eq", event_type),
            ("status", "eq", status),
            ("designation_type", "eq", designation_type),
            ("label_change_type", "eq", label_change_type),
            ("has_boxed_warning", "eq", has_boxed_warning),
            ("safety_signal_type", "eq", safety_signal_type),
            ("safety_severity", "eq", safety_severity),
            ("safety_status", "eq", safety_status),
            ("decision_from", "gte", decision_from.isoformat() if decision_from else None),
            ("decision_to", "lte", decision_to.isoformat() if decision_to else None),
            ("source_updated_from", "gte", source_updated_from.isoformat() if source_updated_from else None),
            ("source_updated_to", "lte", source_updated_to.isoformat() if source_updated_to else None),
        ),
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=effective_sort[0].field,
        sort_direction=effective_sort[0].direction,
        sort=_sort_criteria_read(effective_sort),
        facets=facets,
        landscape=landscape,
        as_of=datetime.now(UTC),
        warnings=["未观察到监管事件不代表不存在；结果受监管辖区、数据授权、更新时效和治理状态限制。"],
    )


def regulatory_saved_search_matches_entity(
    context: QueryContext,
    entity_id: str,
    query: RegulatorySavedSearchQuery,
) -> bool:
    def start(value: Any) -> datetime | None:
        return datetime.combine(value, time.min, tzinfo=UTC) if value else None

    def end(value: Any) -> datetime | None:
        return datetime.combine(value, time.max, tzinfo=UTC) if value else None

    filters = _regulatory_filters(
        context,
        entity_id,
        query.q,
        query.agency,
        jurisdiction=query.jurisdiction,
        event_type=query.event_type,
        status=query.status,
        designation_type=query.designation_type.value if query.designation_type else None,
        label_change_type=query.label_change_type.value if query.label_change_type else None,
        has_boxed_warning=query.has_boxed_warning,
        safety_signal_type=query.safety_signal_type.value if query.safety_signal_type else None,
        safety_severity=query.safety_severity.value if query.safety_severity else None,
        safety_status=query.safety_status.value if query.safety_status else None,
        decision_from=start(query.decision_from),
        decision_to=end(query.decision_to),
        source_updated_from=start(query.source_updated_from),
        source_updated_to=end(query.source_updated_to),
    )
    statement = select(RegulatoryEvent.id).where(*filters)
    return context.session.scalar(statement.with_only_columns(literal(True)).limit(1)) is True


def regulatory_search_items(
    context: QueryContext,
    entity_id: str | None,
    query: str | None,
    agency: str | None,
    jurisdiction: str | None,
    event_type: str | None,
    status: str | None,
    limit: int,
    offset: int = 0,
    *,
    designation_type: str | None = None,
    label_change_type: str | None = None,
    has_boxed_warning: bool | None = None,
    safety_signal_type: str | None = None,
    safety_severity: str | None = None,
    safety_status: str | None = None,
    decision_from: datetime | None = None,
    decision_to: datetime | None = None,
    source_updated_from: datetime | None = None,
    source_updated_to: datetime | None = None,
    sort_by: RegulatorySortField = "decision_date",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[RegulatorySortField]] | None = None,
) -> list[RegulatoryEventSearchItemRead]:
    filters = _regulatory_filters(
        context,
        entity_id,
        query,
        agency,
        jurisdiction=jurisdiction,
        event_type=event_type,
        status=status,
        designation_type=designation_type,
        label_change_type=label_change_type,
        has_boxed_warning=has_boxed_warning,
        safety_signal_type=safety_signal_type,
        safety_severity=safety_severity,
        safety_status=safety_status,
        decision_from=decision_from,
        decision_to=decision_to,
        source_updated_from=source_updated_from,
        source_updated_to=source_updated_to,
    )
    return _regulatory_search_items(
        context,
        filters,
        limit,
        offset,
        sort=validate_sort_clauses(
            sort,
            REGULATORY_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        ),
    )


def regulatory_event_detail(context: QueryContext, event_id: str) -> RegulatoryEventSearchItemRead | None:
    items = _regulatory_search_items(
        context,
        [
            RegulatoryEvent.tenant_id == context.tenant_id,
            RegulatoryEvent.id == event_id,
            _published_entity_exists(context, RegulatoryEvent.subject_entity_id),
        ],
        1,
        0,
    )
    return items[0] if items else None


def _regulatory_search_items(
    context: QueryContext,
    filters: list[ColumnElement[bool]],
    limit: int,
    offset: int,
    *,
    sort_by: RegulatorySortField = "decision_date",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[RegulatorySortField]] | None = None,
) -> list[RegulatoryEventSearchItemRead]:
    effective_sort = validate_sort_clauses(
        sort,
        REGULATORY_SORT_FIELDS,
        default_field=sort_by,
        default_direction=sort_direction,
    )
    subject_name = (
        select(func.lower(Entity.name))
        .where(
            Entity.tenant_id == context.tenant_id,
            Entity.id == RegulatoryEvent.subject_entity_id,
        )
        .correlate(RegulatoryEvent)
        .scalar_subquery()
    )
    sort_expressions: dict[RegulatorySortField, Any] = {
        "decision_date": RegulatoryEvent.decision_date,
        "title": func.lower(RegulatoryEvent.title),
        "agency": func.lower(RegulatoryEvent.agency),
        "jurisdiction": func.lower(RegulatoryEvent.jurisdiction),
        "event_type": func.lower(RegulatoryEvent.event_type),
        "status": func.lower(RegulatoryEvent.status),
        "subject": subject_name,
        "source_updated_at": RegulatoryEvent.source_updated_at,
    }
    ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
    rows = context.session.scalars(
        select(RegulatoryEvent)
        .where(*filters)
        .order_by(
            *ordered_sort,
            RegulatoryEvent.event_identifier,
            RegulatoryEvent.id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    entity_ids = {
        entity_id
        for row in rows
        for entity_id in (row.subject_entity_id, row.indication_entity_id, row.organization_entity_id)
        if entity_id
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
        entity.id: RegulatoryEventLinkedEntityRead(
            id=entity.id,
            name=entity.name,
            entity_type=entity.entity_type,
        )
        for entity in entities
    }
    return [
        RegulatoryEventSearchItemRead(
            **RegulatoryEventRead.model_validate(row).model_dump(),
            subject_entity=linked_by_id[row.subject_entity_id],
            indication_entity=linked_by_id.get(row.indication_entity_id or ""),
            organization_entity=linked_by_id.get(row.organization_entity_id or ""),
        )
        for row in rows
    ]


def _regulatory_filters(
    context: QueryContext,
    entity_id: str | None,
    query: str | None,
    agency: str | None,
    *,
    jurisdiction: str | None = None,
    event_type: str | None = None,
    status: str | None = None,
    designation_type: str | None = None,
    label_change_type: str | None = None,
    has_boxed_warning: bool | None = None,
    safety_signal_type: str | None = None,
    safety_severity: str | None = None,
    safety_status: str | None = None,
    decision_from: datetime | None = None,
    decision_to: datetime | None = None,
    source_updated_from: datetime | None = None,
    source_updated_to: datetime | None = None,
) -> list[ColumnElement[bool]]:
    subject_guard = aliased(Entity)
    filters = [
        RegulatoryEvent.tenant_id == context.tenant_id,
        select(subject_guard.id)
        .where(
            subject_guard.tenant_id == context.tenant_id,
            subject_guard.id == RegulatoryEvent.subject_entity_id,
            subject_guard.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
        )
        .exists(),
    ]
    if not context.include_unpublished:
        filters.extend(
            [
                _published_optional_entity(context, RegulatoryEvent.indication_entity_id),
                _published_optional_entity(context, RegulatoryEvent.organization_entity_id),
            ]
        )
    if entity_id:
        filters.append(
            or_(
                RegulatoryEvent.subject_entity_id == entity_id,
                RegulatoryEvent.indication_entity_id == entity_id,
                RegulatoryEvent.organization_entity_id == entity_id,
                RegulatoryEvent.subject_entity_id.in_(_target_asset_ids(context, entity_id)),
            )
        )
    if agency:
        filters.append(RegulatoryEvent.agency == agency)
    if jurisdiction:
        filters.append(RegulatoryEvent.jurisdiction == jurisdiction)
    if event_type:
        filters.append(RegulatoryEvent.event_type == event_type)
    if status:
        filters.append(RegulatoryEvent.status == status)
    if designation_type:
        filters.append(RegulatoryEvent.designation_type == designation_type)
    if label_change_type:
        filters.append(RegulatoryEvent.label_change_type == label_change_type)
    if has_boxed_warning is not None:
        filters.append(RegulatoryEvent.has_boxed_warning == has_boxed_warning)
    if safety_signal_type:
        filters.append(RegulatoryEvent.safety_signal_type == safety_signal_type)
    if safety_severity:
        filters.append(RegulatoryEvent.safety_severity == safety_severity)
    if safety_status:
        filters.append(RegulatoryEvent.safety_status == safety_status)
    if decision_from:
        filters.append(RegulatoryEvent.decision_date >= decision_from)
    if decision_to:
        filters.append(RegulatoryEvent.decision_date <= decision_to)
    if source_updated_from:
        filters.append(RegulatoryEvent.source_updated_at >= source_updated_from)
    if source_updated_to:
        filters.append(RegulatoryEvent.source_updated_at <= source_updated_to)
    if query:
        pattern = query.strip()
        subject = aliased(Entity)
        indication = aliased(Entity)
        organization = aliased(Entity)
        filters.append(
            or_(
                RegulatoryEvent.title.icontains(pattern, autoescape=True),
                RegulatoryEvent.event_identifier.icontains(pattern, autoescape=True),
                RegulatoryEvent.application_number.icontains(pattern, autoescape=True),
                RegulatoryEvent.event_type.icontains(pattern, autoescape=True),
                RegulatoryEvent.status.icontains(pattern, autoescape=True),
                RegulatoryEvent.jurisdiction.icontains(pattern, autoescape=True),
                RegulatoryEvent.agency.icontains(pattern, autoescape=True),
                RegulatoryEvent.designation_type.icontains(pattern, autoescape=True),
                RegulatoryEvent.label_change_type.icontains(pattern, autoescape=True),
                RegulatoryEvent.label_version.icontains(pattern, autoescape=True),
                RegulatoryEvent.approved_population.icontains(pattern, autoescape=True),
                RegulatoryEvent.line_of_therapy.icontains(pattern, autoescape=True),
                RegulatoryEvent.biomarker.icontains(pattern, autoescape=True),
                RegulatoryEvent.route_of_administration.icontains(pattern, autoescape=True),
                RegulatoryEvent.dosage_form.icontains(pattern, autoescape=True),
                RegulatoryEvent.safety_signal_type.icontains(pattern, autoescape=True),
                RegulatoryEvent.safety_term.icontains(pattern, autoescape=True),
                RegulatoryEvent.safety_severity.icontains(pattern, autoescape=True),
                RegulatoryEvent.safety_status.icontains(pattern, autoescape=True),
                RegulatoryEvent.affected_population.icontains(pattern, autoescape=True),
                select(subject.id)
                .where(
                    subject.tenant_id == context.tenant_id,
                    subject.id == RegulatoryEvent.subject_entity_id,
                    subject.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                    subject.name.icontains(pattern, autoescape=True),
                )
                .exists(),
                select(indication.id)
                .where(
                    indication.tenant_id == context.tenant_id,
                    indication.id == RegulatoryEvent.indication_entity_id,
                    indication.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                    indication.name.icontains(pattern, autoescape=True),
                )
                .exists(),
                select(organization.id)
                .where(
                    organization.tenant_id == context.tenant_id,
                    organization.id == RegulatoryEvent.organization_entity_id,
                    organization.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                    organization.name.icontains(pattern, autoescape=True),
                )
                .exists(),
            )
        )
    return filters
