from __future__ import annotations

from typing import Any, cast

from sqlalchemy import delete, select

from pharma_intel.governance.fact_identity import _projection
from pharma_intel.governance.materialization_context import MaterializationContext
from pharma_intel.governance.temporal_merge import (
    _as_utc,
    _merge_patent_claims,
    _merge_patent_legal_events,
    _merge_patent_publications,
    _merge_strings,
    _should_update_temporal_state,
    _validated_datetime,
)
from pharma_intel.models import (
    DealAssetAssociation,
    DealDirection,
    DealPartyAssociation,
    DealPartyRole,
    DealProfile,
    DealRight,
    DealStatus,
    Entity,
    PatentFamily,
    StagedFact,
)


def materialize_patent(
    context: MaterializationContext, staged: StagedFact, payload: dict[str, Any]
) -> list[dict[str, str]]:
    patent_entity = context._entity(cast(dict[str, Any], payload["patent"]), staged.source_document_id)
    linked_entities = [
        context._entity(cast(dict[str, Any], reference), staged.source_document_id)
        for reference in payload.get("linked_entities") or []
    ]
    patent = context.session.scalar(
        select(PatentFamily).where(
            PatentFamily.tenant_id == context.tenant_id,
            PatentFamily.family_identifier == payload["family_identifier"],
        )
    )
    if patent is None:
        patent = PatentFamily(
            tenant_id=context.tenant_id,
            entity_id=patent_entity.id,
            family_identifier=str(payload["family_identifier"]),
            title=str(payload["title"]),
        )
        context.session.add(patent)
    patent.title = str(payload["title"])
    patent.applicants = _merge_strings(patent.applicants or [], list(payload.get("applicants") or []), limit=100)
    patent.inventors = _merge_strings(patent.inventors or [], list(payload.get("inventors") or []), limit=200)
    patent.publications = _merge_patent_publications(
        patent.publications or [],
        cast(list[dict[str, Any] | str], payload.get("publications") or []),
    )
    incoming_priority_date = _validated_datetime(payload.get("priority_date"))
    if incoming_priority_date is not None and (
        patent.priority_date is None or _as_utc(incoming_priority_date) < _as_utc(patent.priority_date)
    ):
        patent.priority_date = incoming_priority_date
    incoming_status_at = _validated_datetime(payload.get("legal_status_at"))
    should_update_status = _should_update_temporal_state(patent.legal_status_at, incoming_status_at)
    if should_update_status and payload.get("legal_status") is not None:
        patent.legal_status = cast(str | None, payload.get("legal_status"))
        patent.legal_status_at = incoming_status_at
        if payload.get("expiration_date") is not None:
            patent.expiration_date = _validated_datetime(payload.get("expiration_date"))
    patent.legal_events = _merge_patent_legal_events(
        patent.legal_events or [],
        cast(list[dict[str, Any]], payload.get("legal_events") or []),
        current_status=cast(str | None, payload.get("legal_status")),
        current_status_at=incoming_status_at,
        source_document_id=staged.source_document_id,
    )
    patent.independent_claims = _merge_patent_claims(
        patent.independent_claims or [],
        cast(list[dict[str, Any]], payload.get("independent_claims") or []),
        source_document_id=staged.source_document_id,
    )
    patent.linked_entity_ids = sorted({*(patent.linked_entity_ids or []), *(entity.id for entity in linked_entities)})
    patent.source_document_id = staged.source_document_id
    for linked in linked_entities:
        context._relationship(patent_entity, "patent_links_entity", linked, staged)
    context.session.flush()
    return [_projection("patent_family", patent.id)]


def materialize_deal(
    context: MaterializationContext, staged: StagedFact, payload: dict[str, Any]
) -> list[dict[str, str]]:
    deal_entity = context._entity(cast(dict[str, Any], payload["deal"]), staged.source_document_id)
    legacy_parties = [
        context._entity(cast(dict[str, Any], reference), staged.source_document_id)
        for reference in payload.get("parties") or []
    ]
    role_rows: list[tuple[Entity, dict[str, Any]]] = []
    for association in payload.get("party_roles") or []:
        association_payload = cast(dict[str, Any], association)
        role_rows.append(
            (
                context._entity(
                    cast(dict[str, Any], association_payload["party"]),
                    staged.source_document_id,
                ),
                association_payload,
            )
        )
    parties_by_id = {entity.id: entity for entity in legacy_parties}
    parties_by_id.update({entity.id: entity for entity, _association in role_rows})
    parties = list(parties_by_id.values())

    legacy_assets = [
        context._entity(cast(dict[str, Any], reference), staged.source_document_id)
        for reference in payload.get("assets") or []
    ]
    staged_assets: list[tuple[Entity, dict[str, Any]]] = []
    for association in payload.get("asset_stages") or []:
        association_payload = cast(dict[str, Any], association)
        staged_assets.append(
            (
                context._entity(
                    cast(dict[str, Any], association_payload["asset"]),
                    staged.source_document_id,
                ),
                association_payload,
            )
        )
    assets_by_id = {entity.id: entity for entity in legacy_assets}
    assets_by_id.update({entity.id: entity for entity, _association in staged_assets})
    assets = list(assets_by_id.values())
    deal = context.session.scalar(
        select(DealProfile).where(
            DealProfile.tenant_id == context.tenant_id,
            DealProfile.entity_id == deal_entity.id,
        )
    )
    if deal is None:
        deal = DealProfile(
            tenant_id=context.tenant_id,
            entity_id=deal_entity.id,
            deal_type=str(payload["deal_type"]),
        )
        context.session.add(deal)
    deal.deal_type = str(payload["deal_type"])
    deal.status = str(payload.get("status") or DealStatus.UNKNOWN.value)
    deal.direction = str(payload.get("direction") or DealDirection.UNDISCLOSED.value)
    deal.direction_reference_jurisdiction = cast(
        str | None,
        payload.get("direction_reference_jurisdiction"),
    )
    deal.parties = [
        {"entity_id": entity.id, "name": entity.name, "entity_type": entity.entity_type.value} for entity in parties
    ]
    deal.asset_entity_ids = [entity.id for entity in assets]
    deal.announced_at = _validated_datetime(payload.get("announced_at"))
    deal.terminated_at = _validated_datetime(payload.get("terminated_at"))
    deal.source_updated_at = _validated_datetime(payload.get("source_updated_at"))
    deal.territory = cast(str | None, payload.get("territory"))
    deal.upfront_amount = cast(float | None, payload.get("upfront_amount"))
    deal.total_potential_amount = cast(float | None, payload.get("total_potential_amount"))
    deal.currency = cast(str | None, payload.get("currency"))
    deal.terms = cast(dict[str, Any], payload.get("terms") or {})
    deal.source_document_id = staged.source_document_id
    context.session.flush()

    context.session.execute(
        delete(DealPartyAssociation).where(
            DealPartyAssociation.tenant_id == context.tenant_id,
            DealPartyAssociation.deal_id == deal.id,
        )
    )
    context.session.execute(
        delete(DealAssetAssociation).where(
            DealAssetAssociation.tenant_id == context.tenant_id,
            DealAssetAssociation.deal_id == deal.id,
        )
    )
    context.session.execute(
        delete(DealRight).where(
            DealRight.tenant_id == context.tenant_id,
            DealRight.deal_id == deal.id,
        )
    )

    explicit_role_party_ids = {entity.id for entity, _association in role_rows}
    for party in legacy_parties:
        if party.id not in explicit_role_party_ids:
            role_rows.append((party, {"role": DealPartyRole.OTHER.value}))
    for party, association in role_rows:
        role = str(association["role"])
        context.session.add(
            DealPartyAssociation(
                tenant_id=context.tenant_id,
                deal_id=deal.id,
                party_entity_id=party.id,
                role=role,
                country_region=cast(str | None, association.get("country_region")),
                organization_type=cast(str | None, association.get("organization_type")),
                source_document_id=staged.source_document_id,
            )
        )
        context._relationship(deal_entity, f"deal_party_{role}", party, staged)

    staged_asset_ids = {entity.id for entity, _association in staged_assets}
    staged_assets.extend(
        (asset, {"development_phase_at_transaction": None})
        for asset in legacy_assets
        if asset.id not in staged_asset_ids
    )
    for asset, association in staged_assets:
        context.session.add(
            DealAssetAssociation(
                tenant_id=context.tenant_id,
                deal_id=deal.id,
                asset_entity_id=asset.id,
                development_phase_at_transaction=cast(
                    str | None,
                    association.get("development_phase_at_transaction"),
                ),
                source_document_id=staged.source_document_id,
            )
        )

    for right_payload in payload.get("rights") or []:
        right = cast(dict[str, Any], right_payload)
        holder = context._entity(cast(dict[str, Any], right["holder"]), staged.source_document_id)
        context.session.add(
            DealRight(
                tenant_id=context.tenant_id,
                deal_id=deal.id,
                holder_entity_id=holder.id,
                right_type=str(right["right_type"]),
                territory=str(right["territory"]),
                exclusive=cast(bool | None, right.get("exclusive")),
                scope_description=cast(str | None, right.get("scope_description")),
                source_document_id=staged.source_document_id,
            )
        )
        context._relationship(deal_entity, "deal_right_holder", holder, staged)
    for party in parties:
        context._relationship(deal_entity, "deal_party", party, staged)
    for asset in assets:
        context._relationship(deal_entity, "deal_asset", asset, staged)
    context.session.flush()
    return [_projection("deal", deal.id)]
