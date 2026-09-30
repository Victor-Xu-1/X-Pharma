from __future__ import annotations

import re
from collections.abc import Sequence

from sqlalchemy import and_, case, false, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from pharma_intel.identity import EntityIdentityService
from pharma_intel.models import Entity, EntityAlias, EntityIdentifier, EntityType, OutboxEvent, ReviewStatus
from pharma_intel.schemas import ENTITY_SORT_FIELDS, EntityCreate, EntitySortField, SortDirection
from pharma_intel.sorting import SortClause, validate_sort_clauses

_space_re = re.compile(r"\s+")


class DuplicateEntityError(RuntimeError):
    pass


def normalize_name(value: str) -> str:
    return _space_re.sub(" ", value.strip()).casefold()


class EntityRepository:
    def __init__(self, session: Session, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def create(self, data: EntityCreate) -> Entity:
        normalized_name = normalize_name(data.name)
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            lock_key = f"{self.tenant_id}:{data.entity_type.value}:{normalized_name}"
            self.session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": lock_key})
        duplicate = self.session.scalar(
            select(Entity.id).where(
                Entity.tenant_id == self.tenant_id,
                Entity.entity_type == data.entity_type,
                Entity.normalized_name == normalized_name,
            )
        )
        if duplicate is not None:
            raise DuplicateEntityError("Entity already exists")
        entity = Entity(
            tenant_id=self.tenant_id,
            entity_type=data.entity_type,
            name=data.name.strip(),
            normalized_name=normalized_name,
            description=data.description,
            external_ids={},
            attributes=data.attributes,
        )
        entity.aliases = [
            EntityAlias(
                tenant_id=self.tenant_id,
                alias=alias.strip(),
                normalized_alias=normalize_name(alias),
            )
            for alias in data.aliases
            if alias.strip() and normalize_name(alias) != entity.normalized_name
        ]
        self.session.add(entity)
        self.session.flush()
        EntityIdentityService(self.session, self.tenant_id).sync_identifiers(
            entity,
            data.external_ids,
            review_status=ReviewStatus.DRAFT,
            provenance={"origin": "human_api"},
        )
        self.session.add(
            OutboxEvent(
                tenant_id=self.tenant_id,
                aggregate_type="entity",
                aggregate_id=entity.id,
                event_type="canonical.entity.upserted",
                payload={"entity_id": entity.id, "schema_version": 1},
            )
        )
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def get(self, entity_id: str) -> Entity | None:
        return self.session.scalar(
            select(Entity)
            .options(
                selectinload(Entity.aliases),
                selectinload(Entity.identity_identifiers),
                selectinload(Entity.canonical_link),
            )
            .where(Entity.id == entity_id, Entity.tenant_id == self.tenant_id)
        )

    def get_many(self, entity_ids: list[str]) -> list[Entity]:
        if not entity_ids:
            return []
        entities = self.session.scalars(
            select(Entity)
            .options(
                selectinload(Entity.aliases),
                selectinload(Entity.identity_identifiers),
                selectinload(Entity.canonical_link),
            )
            .where(Entity.tenant_id == self.tenant_id, Entity.id.in_(entity_ids))
        )
        by_id = {entity.id: entity for entity in entities}
        return [by_id[entity_id] for entity_id in entity_ids if entity_id in by_id]

    def search(
        self,
        query: str | None,
        entity_types: EntityType | Sequence[EntityType] | None,
        limit: int,
        offset: int,
        review_status: ReviewStatus | None = None,
        sort_by: EntitySortField = "relevance",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[EntitySortField]] | None = None,
    ) -> tuple[list[Entity], int]:
        effective_sort = validate_sort_clauses(
            sort,
            ENTITY_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        selected_types = (
            [entity_types]
            if isinstance(entity_types, EntityType)
            else list(entity_types)
            if entity_types is not None
            else []
        )
        filters = [Entity.tenant_id == self.tenant_id]
        if selected_types:
            filters.append(Entity.entity_type.in_(selected_types))
        if review_status is not None:
            filters.append(Entity.review_status == review_status)
        statement = (
            select(Entity)
            .options(
                selectinload(Entity.aliases),
                selectinload(Entity.identity_identifiers),
                selectinload(Entity.canonical_link),
            )
            .where(*filters)
        )
        if query:
            pattern = f"%{normalize_name(query)}%"
            alias_match = (
                select(EntityAlias.id)
                .where(
                    EntityAlias.entity_id == Entity.id,
                    EntityAlias.tenant_id == self.tenant_id,
                    EntityAlias.normalized_alias.like(pattern),
                )
                .exists()
            )
            identifier_match = (
                select(EntityIdentifier.id)
                .where(
                    EntityIdentifier.entity_id == Entity.id,
                    EntityIdentifier.tenant_id == self.tenant_id,
                    EntityIdentifier.normalized_value.like(pattern),
                )
                .exists()
            )
            description_match = func.lower(func.coalesce(Entity.description, "")).like(pattern)
            statement = statement.where(
                or_(Entity.normalized_name.like(pattern), alias_match, identifier_match, description_match)
            )
        count = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        entity_type_order = case(
            {
                EntityType.CLINICAL_TRIAL: 0,
                EntityType.DISEASE: 1,
                EntityType.DRUG: 2,
                EntityType.ORGANIZATION: 3,
                EntityType.PATENT: 4,
                EntityType.PERSON: 5,
                EntityType.PRODUCT: 6,
                EntityType.TARGET: 7,
                EntityType.TECHNOLOGY: 8,
                EntityType.TRANSACTION: 9,
            },
            value=Entity.entity_type,
        )
        normalized_query = normalize_name(query) if query else None
        exact_alias_match = (
            select(EntityAlias.id)
            .where(
                EntityAlias.entity_id == Entity.id,
                EntityAlias.tenant_id == self.tenant_id,
                EntityAlias.normalized_alias == normalized_query,
            )
            .exists()
            if normalized_query
            else false()
        )
        exact_identifier_match = (
            select(EntityIdentifier.id)
            .where(
                EntityIdentifier.entity_id == Entity.id,
                EntityIdentifier.tenant_id == self.tenant_id,
                func.lower(EntityIdentifier.normalized_value) == normalized_query,
            )
            .exists()
            if normalized_query
            else false()
        )
        identity_anchor = (
            select(EntityIdentifier.id)
            .where(
                EntityIdentifier.entity_id == Entity.id,
                EntityIdentifier.tenant_id == self.tenant_id,
            )
            .exists()
            if normalized_query
            else false()
        )
        relevance = (
            case(
                (and_(Entity.normalized_name == normalized_query, identity_anchor), 0),
                (exact_identifier_match, 1),
                (and_(exact_alias_match, identity_anchor), 2),
                (Entity.normalized_name == normalized_query, 3),
                (exact_alias_match, 4),
                (Entity.normalized_name.like(f"{normalized_query}%"), 5),
                (Entity.normalized_name.like(f"%{normalized_query}%"), 6),
                else_=7,
            )
            if normalized_query
            else Entity.normalized_name
        )
        sort_expressions = {
            "relevance": relevance,
            "name": Entity.normalized_name,
            "entity_type": entity_type_order,
            "updated_at": Entity.updated_at,
        }
        ordered_sort = []
        for clause in effective_sort:
            expression = sort_expressions[clause.field]
            if clause.field == "relevance":
                ordered_sort.append(
                    expression.asc() if normalized_query is None or clause.direction == "desc" else expression.desc()
                )
            else:
                ordered_sort.append(expression.desc() if clause.direction == "desc" else expression.asc())
        items = list(
            self.session.scalars(
                statement.order_by(*ordered_sort, Entity.normalized_name.asc(), Entity.id.asc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, count

    def search_facets(
        self,
        query: str | None,
        review_status: ReviewStatus | None = None,
    ) -> dict[str, dict[str, int]]:
        filters = [Entity.tenant_id == self.tenant_id]
        if review_status is not None:
            filters.append(Entity.review_status == review_status)
        if query:
            pattern = f"%{normalize_name(query)}%"
            alias_match = (
                select(EntityAlias.id)
                .where(
                    EntityAlias.entity_id == Entity.id,
                    EntityAlias.tenant_id == self.tenant_id,
                    EntityAlias.normalized_alias.like(pattern),
                )
                .exists()
            )
            identifier_match = (
                select(EntityIdentifier.id)
                .where(
                    EntityIdentifier.entity_id == Entity.id,
                    EntityIdentifier.tenant_id == self.tenant_id,
                    EntityIdentifier.normalized_value.like(pattern),
                )
                .exists()
            )
            description_match = func.lower(func.coalesce(Entity.description, "")).like(pattern)
            filters.append(or_(Entity.normalized_name.like(pattern), alias_match, identifier_match, description_match))
        entity_types = self.session.execute(
            select(Entity.entity_type, func.count()).where(*filters).group_by(Entity.entity_type)
        )
        review_statuses = self.session.execute(
            select(Entity.review_status, func.count()).where(*filters).group_by(Entity.review_status)
        )
        return {
            "entity_type": {item.value: int(count) for item, count in entity_types},
            "review_status": {item.value: int(count) for item, count in review_statuses},
        }
