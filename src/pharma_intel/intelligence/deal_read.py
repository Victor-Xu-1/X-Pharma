from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.deal_filters import _deal_filters
from pharma_intel.intelligence.deal_phase import _current_program_phase_projection
from pharma_intel.intelligence.scope import _published_entity_exists
from pharma_intel.intelligence.vocabulary import _ordered_sort_expressions
from pharma_intel.models import DealAssetAssociation, DealPartyAssociation, DealProfile, DealRight, Entity, Relationship
from pharma_intel.schemas import (
    DEAL_SORT_FIELDS,
    DealAssetAssociationRead,
    DealLinkedEntityRead,
    DealPartyAssociationRead,
    DealRead,
    DealRightRead,
    DealSearchItemRead,
    DealSortField,
    SortDirection,
)
from pharma_intel.sorting import SortClause, validate_sort_clauses


def deals(
    context: QueryContext,
    entity_id: str | None,
    limit: int,
    offset: int = 0,
    query: str | None = None,
    deal_type: str | None = None,
    territory: str | None = None,
    party: str | None = None,
) -> list[DealRead]:
    filters = _deal_filters(context, entity_id, query, deal_type, territory, party)
    rows = context.session.scalars(
        select(DealProfile)
        .where(*filters)
        .order_by(DealProfile.announced_at.desc().nullslast(), DealProfile.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [DealRead.model_validate(row) for row in rows]


def deal_search_items(
    context: QueryContext,
    entity_id: str | None,
    query: str | None,
    deal_type: str | None,
    territory: str | None,
    party: str | None,
    limit: int,
    offset: int = 0,
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
    sort_by: DealSortField = "announced_at",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[DealSortField]] | None = None,
) -> list[DealSearchItemRead]:
    effective_sort = validate_sort_clauses(
        sort,
        DEAL_SORT_FIELDS,
        default_field=sort_by,
        default_direction=sort_direction,
    )
    if (
        any(clause.field in {"upfront_amount", "total_potential_amount"} for clause in effective_sort)
        and currency is None
    ):
        raise ValueError("currency is required when sorting disclosed deal amounts")
    filters = _deal_filters(
        context,
        entity_id,
        query,
        deal_type,
        territory,
        party,
        status=status,
        direction=direction,
        direction_reference_jurisdiction=direction_reference_jurisdiction,
        asset_entity_id=asset_entity_id,
        target_entity_id=target_entity_id,
        disease_entity_id=disease_entity_id,
        asset_modality=asset_modality,
        asset_program_tag=asset_program_tag,
        party_entity_id=party_entity_id,
        party_role=party_role,
        party_country_region=party_country_region,
        party_organization_type=party_organization_type,
        development_phase_at_transaction=development_phase_at_transaction,
        current_development_phase=current_development_phase,
        right_type=right_type,
        rights_territory=rights_territory,
        currency=currency,
        announced_from=announced_from,
        announced_to=announced_to,
        terminated_from=terminated_from,
        terminated_to=terminated_to,
        source_updated_from=source_updated_from,
        source_updated_to=source_updated_to,
        upfront_amount_min=upfront_amount_min,
        upfront_amount_max=upfront_amount_max,
        total_potential_amount_min=total_potential_amount_min,
        total_potential_amount_max=total_potential_amount_max,
    )
    return _deal_search_items(
        context,
        filters,
        limit,
        offset,
        sort=effective_sort,
    )


def deal_detail(context: QueryContext, deal_id: str) -> DealSearchItemRead | None:
    items = _deal_search_items(
        context,
        [
            DealProfile.tenant_id == context.tenant_id,
            DealProfile.id == deal_id,
            _published_entity_exists(context, DealProfile.entity_id),
        ],
        1,
        0,
    )
    return items[0] if items else None


def _deal_search_items(
    context: QueryContext,
    filters: list[ColumnElement[bool]],
    limit: int,
    offset: int,
    *,
    sort_by: DealSortField = "announced_at",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[DealSortField]] | None = None,
) -> list[DealSearchItemRead]:
    effective_sort = validate_sort_clauses(
        sort,
        DEAL_SORT_FIELDS,
        default_field=sort_by,
        default_direction=sort_direction,
    )
    deal_entity = aliased(Entity)
    status_rank = case(
        {
            "announced": 0,
            "active": 1,
            "completed": 2,
            "terminated": 3,
            "withdrawn": 4,
            "superseded": 5,
            "unknown": 6,
        },
        value=DealProfile.status,
        else_=7,
    )
    sort_expressions: dict[DealSortField, Any] = {
        "announced_at": DealProfile.announced_at,
        "name": func.lower(deal_entity.name),
        "deal_type": func.lower(DealProfile.deal_type),
        "status": status_rank,
        "direction": func.lower(DealProfile.direction),
        "territory": func.lower(DealProfile.territory),
        "upfront_amount": DealProfile.upfront_amount,
        "total_potential_amount": DealProfile.total_potential_amount,
    }
    ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
    deal_rows = context.session.execute(
        select(DealProfile, deal_entity.name)
        .join(
            deal_entity,
            and_(deal_entity.tenant_id == context.tenant_id, deal_entity.id == DealProfile.entity_id),
        )
        .where(*filters)
        .order_by(*ordered_sort, func.lower(deal_entity.name), DealProfile.id)
        .limit(limit)
        .offset(offset)
    ).all()
    rows = [row for row, _name in deal_rows]
    name_by_deal = {row.entity_id: name for row, name in deal_rows}
    linked_by_deal: dict[str, dict[str, dict[str, DealLinkedEntityRead]]] = {
        row.entity_id: {"party": {}, "asset": {}} for row in rows
    }
    party_roles_by_deal: dict[str, list[DealPartyAssociationRead]] = {row.id: [] for row in rows}
    asset_stages_by_deal: dict[str, list[DealAssetAssociationRead]] = {row.id: [] for row in rows}
    rights_by_deal: dict[str, list[DealRightRead]] = {row.id: [] for row in rows}
    deal_entity_ids = list(linked_by_deal)
    if deal_entity_ids:
        linked_rows = context.session.execute(
            select(Relationship.subject_id, Relationship.predicate, Entity)
            .join(Entity, and_(Entity.tenant_id == context.tenant_id, Entity.id == Relationship.object_id))
            .where(
                Relationship.tenant_id == context.tenant_id,
                Relationship.predicate.in_(["deal_party", "deal_asset"]),
                Relationship.subject_id.in_(deal_entity_ids),
            )
            .order_by(Relationship.subject_id, Relationship.predicate, Entity.entity_type, Entity.name, Entity.id)
        ).all()
        for deal_entity_id, predicate, entity in linked_rows:
            group = "party" if predicate == "deal_party" else "asset"
            linked_by_deal[deal_entity_id][group][entity.id] = DealLinkedEntityRead(
                id=entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
            )
        legacy_ids = {
            entity_id
            for row in rows
            for entity_id in [
                *row.asset_entity_ids,
                *(str(item.get("entity_id")) for item in row.parties if item.get("entity_id")),
            ]
        }
        if legacy_ids:
            legacy_entities = context.session.scalars(
                select(Entity)
                .where(Entity.tenant_id == context.tenant_id, Entity.id.in_(legacy_ids))
                .order_by(Entity.entity_type, Entity.name, Entity.id)
            ).all()
            entity_by_id = {entity.id: entity for entity in legacy_entities}
            for row in rows:
                for item in row.parties:
                    entity_id = str(item.get("entity_id") or "")
                    if entity := entity_by_id.get(entity_id):
                        linked_by_deal[row.entity_id]["party"].setdefault(
                            entity.id,
                            DealLinkedEntityRead(id=entity.id, name=entity.name, entity_type=entity.entity_type),
                        )
                for entity_id in row.asset_entity_ids:
                    if entity := entity_by_id.get(entity_id):
                        linked_by_deal[row.entity_id]["asset"].setdefault(
                            entity.id,
                            DealLinkedEntityRead(id=entity.id, name=entity.name, entity_type=entity.entity_type),
                        )
    deal_ids = list(party_roles_by_deal)
    if deal_ids:
        party_rows = context.session.execute(
            select(DealPartyAssociation, Entity)
            .join(
                Entity,
                and_(
                    Entity.tenant_id == context.tenant_id,
                    Entity.id == DealPartyAssociation.party_entity_id,
                ),
            )
            .where(
                DealPartyAssociation.tenant_id == context.tenant_id,
                DealPartyAssociation.deal_id.in_(deal_ids),
            )
            .order_by(DealPartyAssociation.deal_id, DealPartyAssociation.role, Entity.name, Entity.id)
        ).all()
        profile_by_id = {row.id: row for row in rows}
        for association, entity in party_rows:
            party_roles_by_deal[association.deal_id].append(
                DealPartyAssociationRead(
                    id=entity.id,
                    name=entity.name,
                    entity_type=entity.entity_type,
                    role=association.role,
                    country_region=association.country_region,
                    organization_type=association.organization_type,
                )
            )
            deal_profile = profile_by_id[association.deal_id]
            linked_by_deal[deal_profile.entity_id]["party"].setdefault(
                entity.id,
                DealLinkedEntityRead(id=entity.id, name=entity.name, entity_type=entity.entity_type),
            )

        asset_rows = context.session.execute(
            select(DealAssetAssociation, Entity)
            .join(
                Entity,
                and_(
                    Entity.tenant_id == context.tenant_id,
                    Entity.id == DealAssetAssociation.asset_entity_id,
                ),
            )
            .where(
                DealAssetAssociation.tenant_id == context.tenant_id,
                DealAssetAssociation.deal_id.in_(deal_ids),
            )
            .order_by(DealAssetAssociation.deal_id, Entity.entity_type, Entity.name, Entity.id)
        ).all()
        asset_entity_ids = {entity.id for _association, entity in asset_rows}
        current_program_by_asset: dict[str, tuple[str, datetime | None]] = {}
        if asset_entity_ids:
            current_programs = _current_program_phase_projection(context)
            program_rows = context.session.execute(
                select(
                    current_programs.c.drug_entity_id,
                    current_programs.c.phase,
                    current_programs.c.status_date,
                ).where(current_programs.c.drug_entity_id.in_(asset_entity_ids))
            ).all()
            for asset_entity_id, phase, status_date in program_rows:
                phase_value = phase.value if hasattr(phase, "value") else str(phase)
                current_program_by_asset[asset_entity_id] = (phase_value, status_date)
        for association, entity in asset_rows:
            current_program = current_program_by_asset.get(entity.id)
            asset_stages_by_deal[association.deal_id].append(
                DealAssetAssociationRead(
                    id=entity.id,
                    name=entity.name,
                    entity_type=entity.entity_type,
                    development_phase_at_transaction=association.development_phase_at_transaction,
                    current_development_phase=current_program[0] if current_program else None,
                    current_phase_as_of=current_program[1] if current_program else None,
                )
            )
            deal_profile = profile_by_id[association.deal_id]
            linked_by_deal[deal_profile.entity_id]["asset"].setdefault(
                entity.id,
                DealLinkedEntityRead(id=entity.id, name=entity.name, entity_type=entity.entity_type),
            )

        right_rows = context.session.execute(
            select(DealRight, Entity)
            .join(
                Entity,
                and_(Entity.tenant_id == context.tenant_id, Entity.id == DealRight.holder_entity_id),
            )
            .where(DealRight.tenant_id == context.tenant_id, DealRight.deal_id.in_(deal_ids))
            .order_by(DealRight.deal_id, DealRight.right_type, DealRight.territory, Entity.name)
        ).all()
        for right, holder in right_rows:
            rights_by_deal[right.deal_id].append(
                DealRightRead(
                    id=right.id,
                    holder_entity_id=holder.id,
                    holder_name=holder.name,
                    right_type=right.right_type,
                    territory=right.territory,
                    exclusive=right.exclusive,
                    scope_description=right.scope_description,
                    source_document_id=right.source_document_id,
                )
            )
    return [
        DealSearchItemRead(
            **DealRead.model_validate(row).model_dump(),
            name=name_by_deal[row.entity_id],
            party_entities=list(linked_by_deal[row.entity_id]["party"].values()),
            asset_entities=list(linked_by_deal[row.entity_id]["asset"].values()),
            party_roles=party_roles_by_deal[row.id],
            asset_stages=asset_stages_by_deal[row.id],
            rights=rights_by_deal[row.id],
        )
        for row in rows
    ]
