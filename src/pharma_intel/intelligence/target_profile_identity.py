from __future__ import annotations

from sqlalchemy import case, literal, or_, select, true
from sqlalchemy.orm import aliased

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.models import (
    Entity,
    EntityCanonicalLink,
    EntityResolutionCase,
    EntityType,
    ResolutionStatus,
    ReviewStatus,
    TargetProfile,
)


def governed_target_profile(context: QueryContext, entity_id: str) -> TargetProfile | None:
    own = context.session.scalar(
        select(TargetProfile).where(TargetProfile.entity_id == entity_id, TargetProfile.tenant_id == context.tenant_id)
    )
    if own is not None:
        return own

    # A matching name/identifier is evidence for governance, never a second read-time identity authority.
    alias_entity = aliased(Entity, name="profile_alias_entity")
    canonical_entity = aliased(Entity, name="profile_canonical_entity")
    members = select(literal(entity_id).label("entity_id")).cte("approved_target_profile_members", recursive=True)
    members = members.union(
        select(
            case(
                (EntityCanonicalLink.alias_entity_id == members.c.entity_id, EntityCanonicalLink.canonical_entity_id),
                else_=EntityCanonicalLink.alias_entity_id,
            ).label("entity_id")
        )
        .join(
            members,
            or_(
                EntityCanonicalLink.alias_entity_id == members.c.entity_id,
                EntityCanonicalLink.canonical_entity_id == members.c.entity_id,
            ),
        )
        .join(EntityResolutionCase, EntityResolutionCase.id == EntityCanonicalLink.resolution_case_id)
        .join(alias_entity, alias_entity.id == EntityCanonicalLink.alias_entity_id)
        .join(canonical_entity, canonical_entity.id == EntityCanonicalLink.canonical_entity_id)
        .where(
            EntityCanonicalLink.tenant_id == context.tenant_id,
            EntityCanonicalLink.active.is_(True),
            EntityResolutionCase.tenant_id == context.tenant_id,
            EntityResolutionCase.status == ResolutionStatus.APPROVED,
            alias_entity.tenant_id == context.tenant_id,
            canonical_entity.tenant_id == context.tenant_id,
            alias_entity.entity_type == EntityType.TARGET,
            canonical_entity.entity_type == EntityType.TARGET,
            alias_entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
            canonical_entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
        )
    )
    profiles = list(
        context.session.scalars(
            select(TargetProfile)
            .join(Entity, Entity.id == TargetProfile.entity_id)
            .where(
                TargetProfile.tenant_id == context.tenant_id,
                Entity.tenant_id == context.tenant_id,
                Entity.entity_type == EntityType.TARGET,
                Entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                Entity.id.in_(select(members.c.entity_id)),
            )
            .order_by(TargetProfile.id)
            .limit(2)
        )
    )
    # Preserve contradictory profiles for explicit governance; never pick the richest/latest by guesswork.
    return profiles[0] if len(profiles) == 1 else None
