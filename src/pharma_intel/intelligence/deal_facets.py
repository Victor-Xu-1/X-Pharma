from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import and_, func, select, union_all

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.facets import _json_array_facets
from pharma_intel.intelligence.vocabulary import _public_program_modality_sql
from pharma_intel.models import (
    DealAssetAssociation,
    DealPartyAssociation,
    DealRight,
    DevelopmentProgram,
    DevelopmentProgramTarget,
    Entity,
    Relationship,
)


def _deal_party_facets(context: QueryContext, source: Any) -> dict[str, int]:
    relationship_parties = (
        select(source.c.deal_id.label("deal_id"), Entity.name.label("party_name"))
        .select_from(source)
        .join(
            Relationship,
            and_(
                Relationship.tenant_id == context.tenant_id,
                Relationship.subject_id == source.c.deal_entity_id,
                Relationship.predicate == "deal_party",
            ),
        )
        .join(Entity, and_(Entity.tenant_id == context.tenant_id, Entity.id == Relationship.object_id))
    )
    structured_parties = (
        select(source.c.deal_id.label("deal_id"), Entity.name.label("party_name"))
        .select_from(source)
        .join(
            DealPartyAssociation,
            and_(
                DealPartyAssociation.tenant_id == context.tenant_id,
                DealPartyAssociation.deal_id == source.c.deal_id,
            ),
        )
        .join(Entity, and_(Entity.tenant_id == context.tenant_id, Entity.id == DealPartyAssociation.party_entity_id))
    )
    party_rows = relationship_parties.union(structured_parties).subquery()
    counts = context.session.execute(
        select(party_rows.c.party_name, func.count(func.distinct(party_rows.c.deal_id)))
        .group_by(party_rows.c.party_name)
        .order_by(func.count(func.distinct(party_rows.c.deal_id)).desc(), party_rows.c.party_name)
    ).all()
    return {str(name): int(count) for name, count in counts if name}


def _deal_asset_links(context: QueryContext, source: Any) -> Any:
    structured_assets = (
        select(source.c.deal_id.label("deal_id"), DealAssetAssociation.asset_entity_id.label("asset_entity_id"))
        .select_from(source)
        .join(
            DealAssetAssociation,
            and_(
                DealAssetAssociation.tenant_id == context.tenant_id,
                DealAssetAssociation.deal_id == source.c.deal_id,
            ),
        )
    )
    relationship_assets = (
        select(source.c.deal_id.label("deal_id"), Relationship.object_id.label("asset_entity_id"))
        .select_from(source)
        .join(
            Relationship,
            and_(
                Relationship.tenant_id == context.tenant_id,
                Relationship.subject_id == source.c.deal_entity_id,
                Relationship.predicate == "deal_asset",
            ),
        )
    )
    return structured_assets.union(relationship_assets).subquery()


def _deal_asset_facets(context: QueryContext, source: Any) -> dict[str, int]:
    asset_links = _deal_asset_links(context, source)
    counts = context.session.execute(
        select(Entity.name, func.count(func.distinct(asset_links.c.deal_id)))
        .select_from(asset_links)
        .join(Entity, and_(Entity.tenant_id == context.tenant_id, Entity.id == asset_links.c.asset_entity_id))
        .group_by(Entity.name)
        .order_by(func.count(func.distinct(asset_links.c.deal_id)).desc(), Entity.name)
    ).all()
    return {str(name): int(count) for name, count in counts if name}


def _deal_program_entity_facets(
    context: QueryContext, source: Any, kind: Literal["target", "disease"]
) -> dict[str, int]:
    asset_links = _deal_asset_links(context, source)
    if kind == "disease":
        program_entities = union_all(
            select(
                DevelopmentProgram.drug_entity_id.label("asset_entity_id"),
                DevelopmentProgram.disease_entity_id.label("entity_id"),
            ).where(
                DevelopmentProgram.tenant_id == context.tenant_id,
                DevelopmentProgram.disease_entity_id.is_not(None),
            )
        )
    else:
        relationship_targets = select(
            Relationship.subject_id.label("asset_entity_id"),
            Relationship.object_id.label("entity_id"),
        ).where(
            Relationship.tenant_id == context.tenant_id,
            Relationship.predicate == "has_target",
        )
        legacy_targets = select(
            DevelopmentProgram.drug_entity_id.label("asset_entity_id"),
            DevelopmentProgram.target_entity_id.label("entity_id"),
        ).where(
            DevelopmentProgram.tenant_id == context.tenant_id,
            DevelopmentProgram.target_entity_id.is_not(None),
        )
        normalized_targets = (
            select(
                DevelopmentProgram.drug_entity_id.label("asset_entity_id"),
                DevelopmentProgramTarget.target_entity_id.label("entity_id"),
            )
            .join(
                DevelopmentProgramTarget,
                and_(
                    DevelopmentProgramTarget.tenant_id == context.tenant_id,
                    DevelopmentProgramTarget.program_id == DevelopmentProgram.id,
                    DevelopmentProgramTarget.target_set_version == DevelopmentProgram.target_set_version,
                ),
            )
            .where(DevelopmentProgram.tenant_id == context.tenant_id)
        )
        program_entities = union_all(relationship_targets, legacy_targets, normalized_targets)
    entity_links = program_entities.subquery()
    counts = context.session.execute(
        select(Entity.name, func.count(func.distinct(asset_links.c.deal_id)))
        .select_from(asset_links)
        .join(entity_links, entity_links.c.asset_entity_id == asset_links.c.asset_entity_id)
        .join(Entity, and_(Entity.tenant_id == context.tenant_id, Entity.id == entity_links.c.entity_id))
        .group_by(Entity.name)
        .order_by(func.count(func.distinct(asset_links.c.deal_id)).desc(), Entity.name)
    ).all()
    return {str(name): int(count) for name, count in counts if name}


def _deal_program_attribute_facets(
    context: QueryContext,
    source: Any,
    field: Literal["modality", "program_tags"],
) -> dict[str, int]:
    asset_links = _deal_asset_links(context, source)
    public_modality = _public_program_modality_sql(
        DevelopmentProgram.modality,
        DevelopmentProgram.drug_category,
    )
    program_rows = (
        select(
            asset_links.c.deal_id.label("deal_id"),
            public_modality.label("modality"),
            DevelopmentProgram.program_tags.label("program_tags"),
        )
        .select_from(asset_links)
        .join(
            DevelopmentProgram,
            and_(
                DevelopmentProgram.tenant_id == context.tenant_id,
                DevelopmentProgram.drug_entity_id == asset_links.c.asset_entity_id,
            ),
        )
        .subquery()
    )
    if field == "program_tags":
        return _json_array_facets(
            context,
            program_rows,
            "program_tags",
            "deal_id",
            public_program_tags_only=True,
        )
    counts = context.session.execute(
        select(program_rows.c.modality, func.count(func.distinct(program_rows.c.deal_id)))
        .where(program_rows.c.modality.is_not(None))
        .group_by(program_rows.c.modality)
        .order_by(func.count(func.distinct(program_rows.c.deal_id)).desc(), program_rows.c.modality)
    ).all()
    return {str(modality): int(count) for modality, count in counts if modality}


def _deal_party_role_facets(context: QueryContext, source: Any) -> dict[str, int]:
    counts = context.session.execute(
        select(DealPartyAssociation.role, func.count(func.distinct(source.c.deal_id)))
        .select_from(source)
        .join(
            DealPartyAssociation,
            and_(
                DealPartyAssociation.tenant_id == context.tenant_id,
                DealPartyAssociation.deal_id == source.c.deal_id,
            ),
        )
        .group_by(DealPartyAssociation.role)
        .order_by(func.count(func.distinct(source.c.deal_id)).desc(), DealPartyAssociation.role)
    ).all()
    return {str(role): int(count) for role, count in counts if role}


def _deal_party_attribute_facets(
    context: QueryContext,
    source: Any,
    field: Literal["country_region", "organization_type"],
) -> dict[str, int]:
    column = getattr(DealPartyAssociation, field)
    counts = context.session.execute(
        select(column, func.count(func.distinct(source.c.deal_id)))
        .select_from(source)
        .join(
            DealPartyAssociation,
            and_(
                DealPartyAssociation.tenant_id == context.tenant_id,
                DealPartyAssociation.deal_id == source.c.deal_id,
            ),
        )
        .where(column.is_not(None))
        .group_by(column)
        .order_by(func.count(func.distinct(source.c.deal_id)).desc(), column)
    ).all()
    return {str(value): int(count) for value, count in counts if value}


def _deal_right_facets(context: QueryContext, source: Any, field: Literal["right_type", "territory"]) -> dict[str, int]:
    column = getattr(DealRight, field)
    counts = context.session.execute(
        select(column, func.count(func.distinct(source.c.deal_id)))
        .select_from(source)
        .join(
            DealRight,
            and_(DealRight.tenant_id == context.tenant_id, DealRight.deal_id == source.c.deal_id),
        )
        .group_by(column)
        .order_by(func.count(func.distinct(source.c.deal_id)).desc(), column)
    ).all()
    return {str(value): int(count) for value, count in counts if value}
