from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select

from pharma_intel.governance.fact_identity import _projection
from pharma_intel.governance.materialization_context import MaterializationContext
from pharma_intel.identity import normalize_name
from pharma_intel.models import Entity, EntityAlias, OutboxEvent, StagedFact


def publish_alias(context: MaterializationContext, subject: Entity, name: str) -> EntityAlias:
    """Use the identity lock already held by _entity; aliases are never merge keys."""
    normalized = normalize_name(name)
    existing = context.session.scalar(
        select(EntityAlias).where(
            EntityAlias.tenant_id == context.tenant_id,
            EntityAlias.entity_id == subject.id,
            EntityAlias.normalized_alias == normalized,
        )
    )
    if existing is not None:
        return existing
    alias = EntityAlias(
        tenant_id=context.tenant_id, entity_id=subject.id, alias=name.strip(), normalized_alias=normalized
    )
    context.session.add(alias)
    context.session.flush()
    subject.updated_at = datetime.now(UTC)
    context.session.expire(subject, ["aliases"])
    context.session.add(
        OutboxEvent(
            tenant_id=context.tenant_id,
            aggregate_type="entity",
            aggregate_id=subject.id,
            event_type="canonical.entity.upserted",
            payload={"entity_id": subject.id, "schema_version": 1},
        )
    )
    return alias


def materialize_entity_alias(
    context: MaterializationContext, staged: StagedFact, payload: dict[str, Any]
) -> list[dict[str, str]]:
    subject = context._entity(cast(dict[str, Any], payload["subject"]), staged.source_document_id)
    alias = publish_alias(context, subject, str(payload["alias"]))
    return [_projection("entity_alias", alias.id)]
