from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.identity import normalize_name
from pharma_intel.models import Entity, EntityAlias, EntityIdentifier


def entity_keyword_predicate(tenant_id: str, query: str, additional_ids: Sequence[str] = ()) -> ColumnElement[bool]:
    normalized = normalize_name(query)
    alias = (
        select(EntityAlias.id)
        .where(
            EntityAlias.tenant_id == tenant_id,
            EntityAlias.entity_id == Entity.id,
            EntityAlias.normalized_alias.contains(normalized, autoescape=True),
        )
        .exists()
    )
    identifier = (
        select(EntityIdentifier.id)
        .where(
            EntityIdentifier.tenant_id == tenant_id,
            EntityIdentifier.entity_id == Entity.id,
            func.lower(EntityIdentifier.normalized_value).contains(normalized, autoescape=True),
        )
        .exists()
    )
    return or_(
        Entity.normalized_name.contains(normalized, autoescape=True),
        alias,
        identifier,
        func.lower(func.coalesce(Entity.description, "")).contains(normalized, autoescape=True),
        Entity.id.in_(additional_ids),
    )
