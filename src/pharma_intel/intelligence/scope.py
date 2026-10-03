from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import and_, func, literal, or_, select, true
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.vocabulary import _MISSING_ENTITY_LABELS
from pharma_intel.models import Entity, EntityCanonicalLink, EntityIdentifier, EntityType, ReviewStatus
from pharma_intel.schemas import ProgramTargetRead


def _placeholder_target_ids(context: QueryContext) -> tuple[str, ...]:
    if context._placeholder_target_ids_cache is None:
        context._placeholder_target_ids_cache = tuple(
            context.session.scalars(
                select(Entity.id).where(
                    Entity.tenant_id == context.tenant_id,
                    Entity.entity_type == EntityType.TARGET,
                    func.lower(func.trim(Entity.name)).in_(tuple(sorted(_MISSING_ENTITY_LABELS))),
                )
            )
        )
    return context._placeholder_target_ids_cache


def _clean_target_combination_expression(context: QueryContext, expression: Any) -> Any:
    cleaned = expression
    for target_id in _placeholder_target_ids(context):
        cleaned = func.replace(
            func.replace(func.replace(cleaned, f"{target_id}|", ""), f"|{target_id}", ""), target_id, ""
        )
    return func.nullif(cleaned, "")


def _published_entity_exists(context: QueryContext, entity_id: Any) -> ColumnElement[bool]:
    """Return the public entity boundary for a linked domain identifier."""

    if context.include_unpublished:
        return true()
    published_entity = aliased(Entity)
    return (
        select(literal(1))
        .select_from(published_entity)
        .where(
            published_entity.tenant_id == context.tenant_id,
            published_entity.id == entity_id,
            published_entity.review_status == ReviewStatus.VERIFIED,
        )
        .correlate_except(published_entity)
        .exists()
    )


def _published_optional_entity(context: QueryContext, entity_id: Any) -> ColumnElement[bool]:
    if context.include_unpublished:
        return true()
    return or_(entity_id.is_(None), _published_entity_exists(context, entity_id))


def _entity_identity_ids(context: QueryContext, entity_id: str, entity_type: EntityType) -> Select[Any]:
    """Return the tenant-scoped identity family for one governed entity.

    Imports can create a verified canonical row and a same-name draft row before
    entity resolution finishes. Domain records linked to either row must remain
    discoverable from the verified identity, while the type and tenant boundaries
    prevent accidental cross-domain or cross-tenant matches.
    """

    source = Entity.__table__.alias()
    family = Entity.__table__.alias()
    normalized_name = (
        select(source.c.normalized_name)
        .where(
            source.c.tenant_id == context.tenant_id,
            source.c.id == entity_id,
            source.c.entity_type == entity_type,
        )
        .scalar_subquery()
    )
    return select(family.c.id).where(
        family.c.tenant_id == context.tenant_id,
        family.c.entity_type == entity_type,
        family.c.normalized_name == normalized_name,
    )


def _entity_identity_member_ids(context: QueryContext, entity_id: str, entity_type: EntityType) -> set[str]:
    """Materialize one bounded identity family for aggregate read models.

    The SQL identity expression is preferable for large scans. Bounded comparison
    requests also need a Python mapping from every raw row back to its requested
    entity, so this helper expands the same normalized-name family and active
    canonical links without widening the tenant or entity-type boundary.
    """

    normalized_name = context.session.scalar(
        select(Entity.normalized_name).where(
            Entity.tenant_id == context.tenant_id,
            Entity.id == entity_id,
            Entity.entity_type == entity_type,
        )
    )
    if normalized_name is None:
        return {entity_id}
    members = set(
        context.session.scalars(
            select(Entity.id).where(
                Entity.tenant_id == context.tenant_id,
                Entity.entity_type == entity_type,
                Entity.normalized_name == normalized_name,
            )
        )
    )
    changed = True
    while changed:
        changed = False
        link_rows = context.session.execute(
            select(EntityCanonicalLink.alias_entity_id, EntityCanonicalLink.canonical_entity_id).where(
                EntityCanonicalLink.tenant_id == context.tenant_id,
                EntityCanonicalLink.active.is_(True),
                or_(
                    EntityCanonicalLink.alias_entity_id.in_(members),
                    EntityCanonicalLink.canonical_entity_id.in_(members),
                ),
            )
        ).all()
        for alias_id, canonical_id in link_rows:
            if alias_id not in members:
                members.add(alias_id)
                changed = True
            if canonical_id not in members:
                members.add(canonical_id)
                changed = True
    return members


def _published_identity_exists(
    context: QueryContext,
    entity_id: Any,
    entity_type: EntityType,
    *,
    correlate_from: Any | None = None,
) -> ColumnElement[bool]:
    """Check visibility through any verified member of an identity family."""

    if context.include_unpublished:
        return true()
    source = Entity.__table__.alias()
    family = Entity.__table__.alias()
    normalized_name_query = select(source.c.normalized_name).where(
        source.c.tenant_id == context.tenant_id,
        source.c.id == entity_id,
        source.c.entity_type == entity_type,
    )
    if correlate_from is not None:
        normalized_name_query = normalized_name_query.correlate(correlate_from)
    normalized_name = normalized_name_query.scalar_subquery()
    return (
        select(literal(1))
        .select_from(family)
        .where(
            family.c.tenant_id == context.tenant_id,
            family.c.entity_type == entity_type,
            family.c.normalized_name == normalized_name,
            family.c.review_status == ReviewStatus.VERIFIED,
        )
        .correlate_except(source, family)
        .exists()
    )


def _published_optional_identity_entity(
    context: QueryContext,
    entity_id: Any,
    entity_type: EntityType,
    *,
    correlate_from: Any | None = None,
) -> ColumnElement[bool]:
    if context.include_unpublished:
        return true()
    return or_(
        entity_id.is_(None),
        _published_identity_exists(context, entity_id, entity_type, correlate_from=correlate_from),
    )


def _canonical_entity_identity_ids(
    context: QueryContext, entity_ids: set[str], entity_type: EntityType
) -> dict[str, str]:
    if not entity_ids:
        return {}
    identity_rows = context.session.execute(
        select(
            Entity.id,
            Entity.normalized_name,
            Entity.review_status,
            EntityCanonicalLink.canonical_entity_id,
        )
        .outerjoin(
            EntityCanonicalLink,
            and_(
                EntityCanonicalLink.tenant_id == context.tenant_id,
                EntityCanonicalLink.alias_entity_id == Entity.id,
                EntityCanonicalLink.active.is_(True),
            ),
        )
        .where(
            Entity.tenant_id == context.tenant_id,
            Entity.entity_type == entity_type,
            or_(
                Entity.id.in_(entity_ids),
                Entity.normalized_name.in_(
                    select(Entity.normalized_name).where(
                        Entity.tenant_id == context.tenant_id,
                        Entity.id.in_(entity_ids),
                        Entity.entity_type == entity_type,
                    )
                ),
            ),
        )
    ).all()
    verified_by_name: dict[str, str] = {}
    canonical_by_id: dict[str, str] = {}
    for entity_id, normalized_name, review_status, canonical_entity_id in identity_rows:
        if review_status == ReviewStatus.VERIFIED:
            verified_by_name[normalized_name] = min(verified_by_name.get(normalized_name, entity_id), entity_id)
        if canonical_entity_id:
            canonical_by_id[entity_id] = canonical_entity_id
    return {
        entity_id: canonical_by_id.get(entity_id, verified_by_name.get(normalized_name, entity_id))
        for entity_id, normalized_name, _, _ in identity_rows
        if entity_id in entity_ids
    }


def _canonical_entity_identity_labels(
    context: QueryContext,
    entity_ids: set[str],
    entity_type: EntityType,
) -> dict[str, tuple[str, str]]:
    identity_ids = _canonical_entity_identity_ids(context, entity_ids, entity_type)
    display_ids = set(identity_ids.values()) | entity_ids
    name_rows = context.session.execute(
        select(Entity.id, Entity.name).where(
            Entity.tenant_id == context.tenant_id,
            Entity.entity_type == entity_type,
            Entity.id.in_(display_ids),
        )
    ).all()
    names_by_id = {entity_id: name for entity_id, name in name_rows}
    return {
        raw_id: (identity_id, names_by_id.get(identity_id, names_by_id[raw_id]))
        for raw_id, identity_id in identity_ids.items()
        if raw_id in names_by_id
    }


def _published_entity_identity_labels(
    context: QueryContext,
    entity_ids: set[str],
    entity_type: EntityType,
) -> dict[str, tuple[str, str]]:
    """Resolve raw links to stable, publicly readable entity identities.

    Ingestion can attach a program to a draft alias before entity governance has
    reconciled it. Public read models must never emit that draft UUID as a link:
    the entity endpoint correctly rejects it and the user lands on a guaranteed
    404. An explicit verified canonical link wins; otherwise choose the strongest
    verified same-name representative deterministically. Internal reads keep the
    raw relationship and therefore do not call this projection.
    """

    if not entity_ids:
        return {}
    raw_rows = context.session.execute(
        select(Entity.id, Entity.normalized_name).where(
            Entity.tenant_id == context.tenant_id,
            Entity.entity_type == entity_type,
            Entity.id.in_(entity_ids),
        )
    ).all()
    normalized_by_id = {str(entity_id): normalized_name for entity_id, normalized_name in raw_rows}
    if not normalized_by_id:
        return {}

    published_canonical = Entity.__table__.alias("published_identity_canonical")
    canonical_rows = context.session.execute(
        select(
            EntityCanonicalLink.alias_entity_id,
            published_canonical.c.id,
            published_canonical.c.name,
        )
        .select_from(
            EntityCanonicalLink.__table__.join(
                published_canonical,
                and_(
                    published_canonical.c.id == EntityCanonicalLink.canonical_entity_id,
                    published_canonical.c.tenant_id == context.tenant_id,
                    published_canonical.c.entity_type == entity_type,
                    published_canonical.c.review_status == ReviewStatus.VERIFIED,
                ),
            )
        )
        .where(
            EntityCanonicalLink.tenant_id == context.tenant_id,
            EntityCanonicalLink.alias_entity_id.in_(normalized_by_id),
            EntityCanonicalLink.active.is_(True),
        )
        .order_by(EntityCanonicalLink.alias_entity_id, published_canonical.c.id)
    ).all()
    canonical_by_id: dict[str, tuple[str, str]] = {}
    for raw_id, canonical_id, canonical_name in canonical_rows:
        canonical_by_id.setdefault(str(raw_id), (str(canonical_id), str(canonical_name)))

    verified_rows = context.session.execute(
        select(Entity.id, Entity.name, Entity.normalized_name, Entity.external_ids).where(
            Entity.tenant_id == context.tenant_id,
            Entity.entity_type == entity_type,
            Entity.normalized_name.in_(set(normalized_by_id.values())),
            Entity.review_status == ReviewStatus.VERIFIED,
        )
    ).all()
    verified_ids = {str(entity_id) for entity_id, *_ in verified_rows}
    trusted_identifier_counts = {
        str(entity_id): int(count)
        for entity_id, count in context.session.execute(
            select(EntityIdentifier.entity_id, func.count(EntityIdentifier.id))
            .where(
                EntityIdentifier.tenant_id == context.tenant_id,
                EntityIdentifier.entity_type == entity_type,
                EntityIdentifier.entity_id.in_(verified_ids),
                EntityIdentifier.trusted_namespace.is_(True),
                EntityIdentifier.review_status == ReviewStatus.VERIFIED,
            )
            .group_by(EntityIdentifier.entity_id)
        ).all()
    }
    best_verified_by_name: dict[str, tuple[str, str]] = {}
    for entity_id, name, normalized_name, _external_ids in sorted(
        verified_rows,
        key=lambda row: (
            -trusted_identifier_counts.get(str(row[0]), 0),
            -len(row[3] or {}),
            str(row[0]),
        ),
    ):
        best_verified_by_name.setdefault(normalized_name, (str(entity_id), str(name)))

    return {
        raw_id: canonical_by_id.get(raw_id, best_verified_by_name[normalized_name])
        for raw_id, normalized_name in normalized_by_id.items()
        if raw_id in canonical_by_id or normalized_name in best_verified_by_name
    }


def _canonical_target_identity_ids(context: QueryContext, target_ids: set[str]) -> dict[str, str]:
    return _canonical_entity_identity_ids(context, target_ids, EntityType.TARGET)


def _canonical_target_combination_keys(
    context: QueryContext,
    target_map: Mapping[str, Sequence[ProgramTargetRead]],
) -> dict[str, str]:
    target_ids = {target.entity_id for targets in target_map.values() for target in targets}
    identity_ids = _canonical_target_identity_ids(context, target_ids)
    return {
        program_id: "|".join(sorted({identity_ids.get(target.entity_id, target.entity_id) for target in targets}))
        for program_id, targets in target_map.items()
        if targets
    }


def _count(context: QueryContext, model: type[Any], filters: list[ColumnElement[bool]]) -> int:
    return int(context.session.scalar(select(func.count()).select_from(model).where(*filters)) or 0)
