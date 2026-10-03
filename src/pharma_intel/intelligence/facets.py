from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import DateTime, and_, cast, func, literal, select, true
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.models import Entity
from pharma_intel.program_semantics import public_program_tags
from pharma_intel.schemas import AppliedFilterRead


def _applied_filters(
    *filters: tuple[
        str,
        Literal["contains", "eq", "in", "gte", "lte"],
        str | bool | int | float | list[str] | None,
    ],
) -> list[AppliedFilterRead]:
    applied: list[AppliedFilterRead] = []
    for field, operator, value in filters:
        if isinstance(value, str):
            normalized: str | bool | int | float | list[str] | None = value.strip()
        elif isinstance(value, list):
            normalized = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        else:
            normalized = value
        if normalized is None or normalized == "" or normalized == []:
            continue
        applied.append(AppliedFilterRead(field=field, operator=operator, value=normalized))
    return applied


def _scalar_facet_counts(context: QueryContext, source: Any, name: str) -> dict[str, int]:
    column = source.c[name]
    counts = context.session.execute(
        select(column, func.count())
        .select_from(source)
        .where(column.is_not(None))
        .group_by(column)
        .order_by(func.count().desc(), column)
    ).all()
    return {
        str(value).lower() if isinstance(value, bool) else str(value): count
        for value, count in counts
        if value is not None and str(value) != ""
    }


def _json_array_facets(
    context: QueryContext,
    source: Any,
    column_name: str,
    id_name: str,
    *,
    public_program_tags_only: bool = False,
) -> dict[str, int]:
    if context.session.get_bind().dialect.name == "postgresql":
        values = func.json_array_elements_text(source.c[column_name]).table_valued("value").alias("array_value")
    else:
        values = func.json_each(source.c[column_name]).table_valued("key", "value").alias("array_value")
    value = values.c.value
    counts = context.session.execute(
        select(value, func.count(func.distinct(source.c[id_name])))
        .select_from(source.join(values, true()))
        .where(value.is_not(None), value != "")
        .group_by(value)
        .order_by(func.count(func.distinct(source.c[id_name])).desc(), value)
    ).all()
    return {
        str(item): count
        for item, count in counts
        if item and (not public_program_tags_only or public_program_tags([str(item)]))
    }


def _json_array_value_exists(context: QueryContext, column: Any, value: str) -> ColumnElement[bool]:
    if context.session.get_bind().dialect.name == "postgresql":
        values = func.json_array_elements_text(column).table_valued("value").alias("array_filter_value")
    else:
        values = func.json_each(column).table_valued("key", "value").alias("array_filter_value")
    return select(literal(1)).select_from(values).where(values.c.value == value).exists()


def _json_object_array_facets(
    context: QueryContext,
    source: Any,
    column_name: str,
    field_name: str,
    id_name: str,
) -> dict[str, int]:
    value: ColumnElement[Any]
    if context.session.get_bind().dialect.name == "postgresql":
        values = func.json_array_elements(source.c[column_name]).table_valued("value").alias("object_value")
        value = values.c.value.op("->>")(field_name)
    else:
        values = func.json_each(source.c[column_name]).table_valued("key", "value").alias("object_value")
        value = func.json_extract(values.c.value, f"$.{field_name}")
    counts = context.session.execute(
        select(value, func.count(func.distinct(source.c[id_name])))
        .select_from(source.join(values, true()))
        .where(value.is_not(None), value != "")
        .group_by(value)
        .order_by(func.count(func.distinct(source.c[id_name])).desc(), value)
    ).all()
    return {str(item): count for item, count in counts if item}


def _json_object_array_exists(
    context: QueryContext,
    column: Any,
    *,
    text_field: str,
    text_value: str | None,
    datetime_field: str,
    datetime_from: datetime | None,
    datetime_to: datetime | None,
) -> ColumnElement[bool]:
    text_expression: ColumnElement[Any]
    datetime_expression: ColumnElement[Any]
    if context.session.get_bind().dialect.name == "postgresql":
        values = func.json_array_elements(column).table_valued("value").alias("object_filter_value")
        text_expression = values.c.value.op("->>")(text_field)
        datetime_expression = cast(
            values.c.value.op("->>")(datetime_field),
            DateTime(timezone=True),
        )
    else:
        values = func.json_each(column).table_valued("key", "value").alias("object_filter_value")
        text_expression = func.json_extract(values.c.value, f"$.{text_field}")
        datetime_expression = func.datetime(func.json_extract(values.c.value, f"$.{datetime_field}"))
    predicates: list[ColumnElement[bool]] = []
    if text_value:
        predicates.append(text_expression == text_value)
    if datetime_from:
        predicates.append(datetime_expression >= datetime_from)
    if datetime_to:
        predicates.append(datetime_expression <= datetime_to)
    return select(literal(1)).select_from(values).where(*predicates).exists()


def _landscape_scalar_buckets(
    context: QueryContext,
    source: Any,
    column_name: str,
    total: int,
    bucket_type: Any,
) -> list[Any]:
    column = func.coalesce(getattr(source.c, column_name), "__missing__")
    rows = context.session.execute(
        select(column.label("value"), func.count())
        .select_from(source)
        .group_by("value")
        .order_by(func.count().desc(), column)
    ).all()
    return [
        bucket_type(
            key=str(value),
            label="未披露" if str(value) == "__missing__" else str(value),
            count=int(count),
            share=(int(count) / total) if total else 0.0,
        )
        for value, count in rows
    ]


def _linked_entity_facets(
    context: QueryContext, source: Any, entity_id_name: str, observation_id_name: str
) -> dict[str, int]:
    entity = aliased(Entity)
    entity_id = source.c[entity_id_name]
    observation_id = source.c[observation_id_name]
    counts = context.session.execute(
        select(entity.name, func.count(func.distinct(observation_id)))
        .select_from(source)
        .join(entity, and_(entity.tenant_id == context.tenant_id, entity.id == entity_id))
        .group_by(entity.name)
        .order_by(func.count(func.distinct(observation_id)).desc(), entity.name)
    ).all()
    return {name: count for name, count in counts if name}
