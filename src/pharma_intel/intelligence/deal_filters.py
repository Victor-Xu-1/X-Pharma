from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import String, and_, cast, func, literal, or_, select, true, union_all
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.deal_phase import _current_program_phase_projection
from pharma_intel.intelligence.facets import _json_array_value_exists
from pharma_intel.intelligence.scope import _published_entity_exists
from pharma_intel.intelligence.vocabulary import _public_program_modality_sql
from pharma_intel.models import (
    DealAssetAssociation,
    DealPartyAssociation,
    DealProfile,
    DealRight,
    DevelopmentPhase,
    DevelopmentProgram,
    DevelopmentProgramTarget,
    Entity,
    Relationship,
    ReviewStatus,
)
from pharma_intel.program_semantics import public_program_tags


def _target_asset_ids(context: QueryContext, target_entity_id: str) -> Any:
    target_edge = aliased(Relationship)
    relationship_assets = select(target_edge.subject_id.label("asset_entity_id")).where(
        target_edge.tenant_id == context.tenant_id,
        target_edge.predicate == "has_target",
        target_edge.object_id == target_entity_id,
    )
    legacy_program_assets = select(DevelopmentProgram.drug_entity_id.label("asset_entity_id")).where(
        DevelopmentProgram.tenant_id == context.tenant_id,
        DevelopmentProgram.target_entity_id == target_entity_id,
    )
    normalized_program_assets = (
        select(DevelopmentProgram.drug_entity_id.label("asset_entity_id"))
        .join(
            DevelopmentProgramTarget,
            and_(
                DevelopmentProgramTarget.tenant_id == context.tenant_id,
                DevelopmentProgramTarget.program_id == DevelopmentProgram.id,
                DevelopmentProgramTarget.target_set_version == DevelopmentProgram.target_set_version,
            ),
        )
        .where(
            DevelopmentProgram.tenant_id == context.tenant_id,
            DevelopmentProgramTarget.target_entity_id == target_entity_id,
        )
    )
    return union_all(relationship_assets, legacy_program_assets, normalized_program_assets)


def _deal_filters(
    context: QueryContext,
    entity_id: str | None,
    query: str | None = None,
    deal_type: str | None = None,
    territory: str | None = None,
    party: str | None = None,
    *,
    status: str | None = None,
    direction: str | None = None,
    direction_reference_jurisdiction: str | None = None,
    asset_entity_id: str | None = None,
    target_entity_id: str | None = None,
    disease_entity_id: str | None = None,
    asset_modality: list[str] | None = None,
    asset_program_tag: list[str] | None = None,
    party_entity_id: str | None = None,
    party_role: str | None = None,
    party_country_region: str | None = None,
    party_organization_type: str | None = None,
    development_phase_at_transaction: str | None = None,
    current_development_phase: str | None = None,
    right_type: str | None = None,
    rights_territory: str | None = None,
    currency: str | None = None,
    announced_from: datetime | None = None,
    announced_to: datetime | None = None,
    terminated_from: datetime | None = None,
    terminated_to: datetime | None = None,
    source_updated_from: datetime | None = None,
    source_updated_to: datetime | None = None,
    upfront_amount_min: float | None = None,
    upfront_amount_max: float | None = None,
    total_potential_amount_min: float | None = None,
    total_potential_amount_max: float | None = None,
) -> list[ColumnElement[bool]]:
    filters = [
        DealProfile.tenant_id == context.tenant_id,
        _published_entity_exists(context, DealProfile.entity_id),
    ]
    if not context.include_unpublished:
        unpublished_asset = (
            select(literal(1))
            .select_from(DealAssetAssociation)
            .join(Entity, Entity.id == DealAssetAssociation.asset_entity_id)
            .where(
                DealAssetAssociation.tenant_id == context.tenant_id,
                DealAssetAssociation.deal_id == DealProfile.id,
                Entity.review_status != ReviewStatus.VERIFIED,
            )
            .correlate(DealProfile)
            .exists()
        )
        unpublished_party = (
            select(literal(1))
            .select_from(DealPartyAssociation)
            .join(Entity, Entity.id == DealPartyAssociation.party_entity_id)
            .where(
                DealPartyAssociation.tenant_id == context.tenant_id,
                DealPartyAssociation.deal_id == DealProfile.id,
                Entity.review_status != ReviewStatus.VERIFIED,
            )
            .correlate(DealProfile)
            .exists()
        )
        unpublished_right = (
            select(literal(1))
            .select_from(DealRight)
            .join(Entity, Entity.id == DealRight.holder_entity_id)
            .where(
                DealRight.tenant_id == context.tenant_id,
                DealRight.deal_id == DealProfile.id,
                Entity.review_status != ReviewStatus.VERIFIED,
            )
            .correlate(DealProfile)
            .exists()
        )
        filters.extend([~unpublished_asset, ~unpublished_party, ~unpublished_right])
    if entity_id:
        target_asset_ids = _target_asset_ids(context, entity_id)
        disease_asset_ids = select(DevelopmentProgram.drug_entity_id).where(
            DevelopmentProgram.tenant_id == context.tenant_id,
            DevelopmentProgram.disease_entity_id == entity_id,
        )
        linked_deal_ids = select(Relationship.subject_id).where(
            Relationship.tenant_id == context.tenant_id,
            or_(
                and_(
                    Relationship.predicate.in_(["deal_asset", "deal_party"]),
                    Relationship.object_id == entity_id,
                ),
                and_(
                    Relationship.predicate == "deal_asset",
                    or_(
                        Relationship.object_id.in_(target_asset_ids),
                        Relationship.object_id.in_(disease_asset_ids),
                    ),
                ),
            ),
        )
        normalized_party_deal_ids = (
            select(DealProfile.entity_id)
            .join(
                DealPartyAssociation,
                and_(
                    DealPartyAssociation.tenant_id == context.tenant_id,
                    DealPartyAssociation.deal_id == DealProfile.id,
                    DealPartyAssociation.party_entity_id == entity_id,
                ),
            )
            .where(DealProfile.tenant_id == context.tenant_id)
        )
        normalized_asset_deal_ids = (
            select(DealProfile.entity_id)
            .join(
                DealAssetAssociation,
                and_(
                    DealAssetAssociation.tenant_id == context.tenant_id,
                    DealAssetAssociation.deal_id == DealProfile.id,
                    or_(
                        DealAssetAssociation.asset_entity_id == entity_id,
                        DealAssetAssociation.asset_entity_id.in_(target_asset_ids),
                        DealAssetAssociation.asset_entity_id.in_(disease_asset_ids),
                    ),
                ),
            )
            .where(DealProfile.tenant_id == context.tenant_id)
        )
        filters.append(
            or_(
                DealProfile.entity_id == entity_id,
                DealProfile.entity_id.in_(linked_deal_ids),
                DealProfile.entity_id.in_(normalized_party_deal_ids),
                DealProfile.entity_id.in_(normalized_asset_deal_ids),
                cast(DealProfile.asset_entity_ids, String).contains(f'"{entity_id}"', autoescape=True),
            )
        )
    if query:
        normalized_query = query.strip().casefold()
        linked_entity_match = (
            select(Relationship.id)
            .join(Entity, and_(Entity.tenant_id == context.tenant_id, Entity.id == Relationship.object_id))
            .where(
                Relationship.tenant_id == context.tenant_id,
                Relationship.subject_id == DealProfile.entity_id,
                Relationship.predicate.in_(["deal_party", "deal_asset"]),
                Entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                func.lower(Entity.name).contains(normalized_query, autoescape=True),
            )
            .exists()
        )
        normalized_party_name_match = (
            select(DealPartyAssociation.id)
            .join(
                Entity,
                and_(
                    Entity.tenant_id == context.tenant_id,
                    Entity.id == DealPartyAssociation.party_entity_id,
                    Entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                ),
            )
            .where(
                DealPartyAssociation.tenant_id == context.tenant_id,
                DealPartyAssociation.deal_id == DealProfile.id,
                func.lower(Entity.name).contains(normalized_query, autoescape=True),
            )
            .exists()
        )
        normalized_asset_name_match = (
            select(DealAssetAssociation.id)
            .join(
                Entity,
                and_(
                    Entity.tenant_id == context.tenant_id,
                    Entity.id == DealAssetAssociation.asset_entity_id,
                    Entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                ),
            )
            .where(
                DealAssetAssociation.tenant_id == context.tenant_id,
                DealAssetAssociation.deal_id == DealProfile.id,
                func.lower(Entity.name).contains(normalized_query, autoescape=True),
            )
            .exists()
        )
        deal_name_match = (
            select(Entity.id)
            .where(
                Entity.tenant_id == context.tenant_id,
                Entity.id == DealProfile.entity_id,
                Entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                func.lower(Entity.name).contains(normalized_query, autoescape=True),
            )
            .exists()
        )
        filters.append(
            or_(
                func.lower(DealProfile.deal_type).contains(normalized_query, autoescape=True),
                func.lower(DealProfile.territory).contains(normalized_query, autoescape=True),
                func.lower(DealProfile.currency).contains(normalized_query, autoescape=True),
                func.lower(cast(DealProfile.parties, String)).contains(normalized_query, autoescape=True),
                deal_name_match,
                linked_entity_match,
                normalized_party_name_match,
                normalized_asset_name_match,
            )
        )
    if deal_type:
        filters.append(DealProfile.deal_type == deal_type)
    if status:
        filters.append(DealProfile.status == status)
    if direction:
        filters.append(DealProfile.direction == direction)
    if direction_reference_jurisdiction:
        filters.append(DealProfile.direction_reference_jurisdiction == direction_reference_jurisdiction)
    if territory:
        filters.append(DealProfile.territory == territory)
    normalized_target_asset_ids = _target_asset_ids(context, target_entity_id) if target_entity_id else None
    normalized_disease_asset_ids = (
        select(DevelopmentProgram.drug_entity_id).where(
            DevelopmentProgram.tenant_id == context.tenant_id,
            DevelopmentProgram.disease_entity_id == disease_entity_id,
        )
        if disease_entity_id
        else None
    )
    normalized_asset_constraints: list[ColumnElement[bool]] = []
    if asset_entity_id:
        normalized_asset_constraints.append(DealAssetAssociation.asset_entity_id == asset_entity_id)
    if normalized_target_asset_ids is not None:
        normalized_asset_constraints.append(DealAssetAssociation.asset_entity_id.in_(normalized_target_asset_ids))
    if normalized_disease_asset_ids is not None:
        normalized_asset_constraints.append(DealAssetAssociation.asset_entity_id.in_(normalized_disease_asset_ids))
    if asset_entity_id:
        structured_asset_match = select(DealAssetAssociation.id).where(
            DealAssetAssociation.tenant_id == context.tenant_id,
            DealAssetAssociation.deal_id == DealProfile.id,
            DealAssetAssociation.asset_entity_id == asset_entity_id,
        )
        relationship_asset_match = select(Relationship.id).where(
            Relationship.tenant_id == context.tenant_id,
            Relationship.subject_id == DealProfile.entity_id,
            Relationship.predicate == "deal_asset",
            Relationship.object_id == asset_entity_id,
        )
        filters.append(
            or_(
                structured_asset_match.exists(),
                relationship_asset_match.exists(),
                cast(DealProfile.asset_entity_ids, String).contains(f'"{asset_entity_id}"', autoescape=True),
            )
        )
    if target_entity_id:
        assert normalized_target_asset_ids is not None
        structured_target_match = select(DealAssetAssociation.id).where(
            DealAssetAssociation.tenant_id == context.tenant_id,
            DealAssetAssociation.deal_id == DealProfile.id,
            *normalized_asset_constraints,
        )
        relationship_target_match = select(Relationship.id).where(
            Relationship.tenant_id == context.tenant_id,
            Relationship.subject_id == DealProfile.entity_id,
            Relationship.predicate == "deal_asset",
            Relationship.object_id.in_(normalized_target_asset_ids),
        )
        filters.append(
            structured_target_match.exists()
            if asset_entity_id or disease_entity_id
            else or_(structured_target_match.exists(), relationship_target_match.exists())
        )
    if disease_entity_id:
        assert normalized_disease_asset_ids is not None
        structured_disease_match = select(DealAssetAssociation.id).where(
            DealAssetAssociation.tenant_id == context.tenant_id,
            DealAssetAssociation.deal_id == DealProfile.id,
            *normalized_asset_constraints,
        )
        relationship_disease_match = select(Relationship.id).where(
            Relationship.tenant_id == context.tenant_id,
            Relationship.subject_id == DealProfile.entity_id,
            Relationship.predicate == "deal_asset",
            Relationship.object_id.in_(normalized_disease_asset_ids),
        )
        filters.append(
            structured_disease_match.exists()
            if asset_entity_id or target_entity_id
            else or_(structured_disease_match.exists(), relationship_disease_match.exists())
        )
    if asset_modality or asset_program_tag:
        program_filters: list[ColumnElement[bool]] = []
        if asset_modality:
            program_filters.append(
                _public_program_modality_sql(
                    DevelopmentProgram.modality,
                    DevelopmentProgram.drug_category,
                ).in_(asset_modality)
            )
        if asset_program_tag:
            visible_program_tags = public_program_tags(asset_program_tag)
            program_filters.append(
                or_(
                    *(
                        _json_array_value_exists(context, DevelopmentProgram.program_tags, program_tag)
                        for program_tag in visible_program_tags
                    )
                )
                if visible_program_tags
                else literal(False)
            )
        structured_program_match = (
            select(DevelopmentProgram.id)
            .join(
                DealAssetAssociation,
                and_(
                    DealAssetAssociation.tenant_id == context.tenant_id,
                    DealAssetAssociation.asset_entity_id == DevelopmentProgram.drug_entity_id,
                ),
            )
            .where(
                DevelopmentProgram.tenant_id == context.tenant_id,
                DealAssetAssociation.deal_id == DealProfile.id,
                *normalized_asset_constraints,
                *program_filters,
            )
        )
        relationship_program_match = (
            select(DevelopmentProgram.id)
            .join(
                Relationship,
                and_(
                    Relationship.tenant_id == context.tenant_id,
                    Relationship.predicate == "deal_asset",
                    Relationship.object_id == DevelopmentProgram.drug_entity_id,
                ),
            )
            .where(
                DevelopmentProgram.tenant_id == context.tenant_id,
                Relationship.subject_id == DealProfile.entity_id,
                *program_filters,
            )
        )
        filters.append(
            structured_program_match.exists()
            if normalized_asset_constraints
            else or_(structured_program_match.exists(), relationship_program_match.exists())
        )
    if party:
        normalized_party = party.strip().casefold()
        party_match = (
            select(Relationship.id)
            .join(Entity, and_(Entity.tenant_id == context.tenant_id, Entity.id == Relationship.object_id))
            .where(
                Relationship.tenant_id == context.tenant_id,
                Relationship.subject_id == DealProfile.entity_id,
                Relationship.predicate == "deal_party",
                func.lower(Entity.name) == normalized_party,
            )
            .exists()
        )
        normalized_party_match = (
            select(DealPartyAssociation.id)
            .join(
                Entity,
                and_(
                    Entity.tenant_id == context.tenant_id,
                    Entity.id == DealPartyAssociation.party_entity_id,
                ),
            )
            .where(
                DealPartyAssociation.tenant_id == context.tenant_id,
                DealPartyAssociation.deal_id == DealProfile.id,
                func.lower(Entity.name) == normalized_party,
            )
            .exists()
        )
        filters.append(
            or_(
                party_match,
                normalized_party_match,
                func.lower(cast(DealProfile.parties, String)).contains(normalized_party, autoescape=True),
            )
        )
    if party_entity_id or party_role or party_country_region or party_organization_type:
        role_match = select(DealPartyAssociation.id).where(
            DealPartyAssociation.tenant_id == context.tenant_id,
            DealPartyAssociation.deal_id == DealProfile.id,
        )
        if party_entity_id:
            role_match = role_match.where(DealPartyAssociation.party_entity_id == party_entity_id)
        if party_role:
            role_match = role_match.where(DealPartyAssociation.role == party_role)
        if party_country_region:
            role_match = role_match.where(DealPartyAssociation.country_region == party_country_region)
        if party_organization_type:
            role_match = role_match.where(DealPartyAssociation.organization_type == party_organization_type)
        filters.append(role_match.exists())
    if development_phase_at_transaction:
        filters.append(
            select(DealAssetAssociation.id)
            .where(
                DealAssetAssociation.tenant_id == context.tenant_id,
                DealAssetAssociation.deal_id == DealProfile.id,
                *normalized_asset_constraints,
                DealAssetAssociation.development_phase_at_transaction == development_phase_at_transaction,
            )
            .exists()
        )
    if current_development_phase:
        current_programs = _current_program_phase_projection(context)
        filters.append(
            select(DealAssetAssociation.id)
            .join(
                current_programs,
                current_programs.c.drug_entity_id == DealAssetAssociation.asset_entity_id,
            )
            .where(
                DealAssetAssociation.tenant_id == context.tenant_id,
                DealAssetAssociation.deal_id == DealProfile.id,
                *normalized_asset_constraints,
                current_programs.c.phase == DevelopmentPhase(current_development_phase),
            )
            .exists()
        )
    if right_type or rights_territory:
        rights_match = select(DealRight.id).where(
            DealRight.tenant_id == context.tenant_id,
            DealRight.deal_id == DealProfile.id,
        )
        if right_type:
            rights_match = rights_match.where(DealRight.right_type == right_type)
        if rights_territory:
            rights_match = rights_match.where(DealRight.territory == rights_territory)
        filters.append(rights_match.exists())
    if currency:
        filters.append(DealProfile.currency == currency)
    if announced_from:
        filters.append(DealProfile.announced_at >= announced_from)
    if announced_to:
        filters.append(DealProfile.announced_at <= announced_to)
    if terminated_from:
        filters.append(DealProfile.terminated_at >= terminated_from)
    if terminated_to:
        filters.append(DealProfile.terminated_at <= terminated_to)
    if source_updated_from:
        filters.append(DealProfile.source_updated_at >= source_updated_from)
    if source_updated_to:
        filters.append(DealProfile.source_updated_at <= source_updated_to)
    if upfront_amount_min is not None:
        filters.append(DealProfile.upfront_amount >= upfront_amount_min)
    if upfront_amount_max is not None:
        filters.append(DealProfile.upfront_amount <= upfront_amount_max)
    if total_potential_amount_min is not None:
        filters.append(DealProfile.total_potential_amount >= total_potential_amount_min)
    if total_potential_amount_max is not None:
        filters.append(DealProfile.total_potential_amount <= total_potential_amount_max)
    return filters
