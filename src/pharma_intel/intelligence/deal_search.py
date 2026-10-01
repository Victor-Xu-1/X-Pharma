from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import func, literal, select

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.deal_facets import (
    _deal_asset_facets,
    _deal_party_attribute_facets,
    _deal_party_facets,
    _deal_party_role_facets,
    _deal_program_attribute_facets,
    _deal_program_entity_facets,
    _deal_right_facets,
)
from pharma_intel.intelligence.deal_filters import _deal_filters
from pharma_intel.intelligence.deal_phase import _deal_asset_phase_facets, _deal_current_phase_facets
from pharma_intel.intelligence.deal_read import _deal_search_items
from pharma_intel.intelligence.facets import _applied_filters, _scalar_facet_counts
from pharma_intel.intelligence.vocabulary import _sort_criteria_read
from pharma_intel.models import DealProfile
from pharma_intel.program_semantics import public_program_tags
from pharma_intel.schemas import (
    DEAL_SORT_FIELDS,
    DealAnalysisLimit,
    DealLandscapeBucketRead,
    DealLandscapeRead,
    DealSavedSearchQuery,
    DealSearchResult,
    DealSortField,
    SortDirection,
)
from pharma_intel.sorting import SortClause, validate_sort_clauses


def search_deals(
    context: QueryContext,
    query: str | None,
    deal_type: str | None,
    territory: str | None,
    party: str | None,
    limit: int,
    offset: int,
    *,
    entity_id: str | None = None,
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
    landscape_limit: DealAnalysisLimit = 8,
) -> DealSearchResult:
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
    items = _deal_search_items(
        context,
        filters,
        limit,
        offset,
        sort=effective_sort,
    )
    facet_source = (
        select(
            DealProfile.id.label("deal_id"),
            DealProfile.entity_id.label("deal_entity_id"),
            DealProfile.deal_type.label("deal_type"),
            DealProfile.status.label("status"),
            DealProfile.direction.label("direction"),
            DealProfile.territory.label("territory"),
            DealProfile.currency.label("currency"),
        )
        .where(*filters)
        .subquery()
    )
    total = context.session.scalar(select(func.count()).select_from(facet_source)) or 0
    facets = {
        "deal_type": _scalar_facet_counts(context, facet_source, "deal_type"),
        "status": _scalar_facet_counts(context, facet_source, "status"),
        "direction": _scalar_facet_counts(context, facet_source, "direction"),
        "territory": _scalar_facet_counts(context, facet_source, "territory"),
        "currency": _scalar_facet_counts(context, facet_source, "currency"),
        "asset": _deal_asset_facets(context, facet_source),
        "target": _deal_program_entity_facets(context, facet_source, "target"),
        "disease": _deal_program_entity_facets(context, facet_source, "disease"),
        "asset_modality": _deal_program_attribute_facets(context, facet_source, "modality"),
        "asset_program_tag": _deal_program_attribute_facets(context, facet_source, "program_tags"),
        "party": _deal_party_facets(context, facet_source),
        "party_role": _deal_party_role_facets(context, facet_source),
        "party_country_region": _deal_party_attribute_facets(context, facet_source, "country_region"),
        "party_organization_type": _deal_party_attribute_facets(context, facet_source, "organization_type"),
        "development_phase_at_transaction": _deal_asset_phase_facets(context, facet_source),
        "current_development_phase": _deal_current_phase_facets(context, facet_source),
        "right_type": _deal_right_facets(context, facet_source, "right_type"),
        "rights_territory": _deal_right_facets(context, facet_source, "territory"),
    }
    landscape = _deal_landscape(context, facets, total, limit=landscape_limit)
    return DealSearchResult(
        query_schema_version="pharma.deal.search.v8",
        applied_filters=_applied_filters(
            ("entity_id", "eq", entity_id),
            ("q", "contains", query.strip() if query else None),
            ("deal_type", "eq", deal_type),
            ("status", "eq", status),
            ("direction", "eq", direction),
            ("direction_reference_jurisdiction", "eq", direction_reference_jurisdiction),
            ("territory", "eq", territory),
            ("asset_entity_id", "eq", asset_entity_id),
            ("target_entity_id", "eq", target_entity_id),
            ("disease_entity_id", "eq", disease_entity_id),
            ("asset_modality", "in", asset_modality),
            ("asset_program_tag", "in", public_program_tags(asset_program_tag)),
            ("party", "eq", party),
            ("party_entity_id", "eq", party_entity_id),
            ("party_role", "eq", party_role),
            ("party_country_region", "eq", party_country_region),
            ("party_organization_type", "eq", party_organization_type),
            ("development_phase_at_transaction", "eq", development_phase_at_transaction),
            ("current_development_phase", "eq", current_development_phase),
            ("right_type", "eq", right_type),
            ("rights_territory", "eq", rights_territory),
            ("currency", "eq", currency),
            ("announced_from", "gte", announced_from.isoformat() if announced_from else None),
            ("announced_to", "lte", announced_to.isoformat() if announced_to else None),
            ("terminated_from", "gte", terminated_from.isoformat() if terminated_from else None),
            ("terminated_to", "lte", terminated_to.isoformat() if terminated_to else None),
            ("source_updated_from", "gte", source_updated_from.isoformat() if source_updated_from else None),
            ("source_updated_to", "lte", source_updated_to.isoformat() if source_updated_to else None),
            ("upfront_amount_min", "gte", upfront_amount_min),
            ("upfront_amount_max", "lte", upfront_amount_max),
            ("total_potential_amount_min", "gte", total_potential_amount_min),
            ("total_potential_amount_max", "lte", total_potential_amount_max),
        ),
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=effective_sort[0].field,
        sort_direction=effective_sort[0].direction,
        sort=_sort_criteria_read(effective_sort),
        facets=facets,
        landscape=landscape,
        as_of=datetime.now(UTC),
        warnings=["未观察到交易不代表不存在；结果受数据授权、披露完整性、金额口径和治理状态限制。"],
    )


def _deal_landscape(
    context: QueryContext,
    facets: dict[str, dict[str, int]],
    total: int,
    *,
    limit: DealAnalysisLimit,
) -> DealLandscapeRead:
    def buckets(name: str, *, exclusive: bool) -> list[DealLandscapeBucketRead]:
        counts = dict(facets.get(name, {}))
        if exclusive:
            missing = max(0, total - sum(counts.values()))
            if missing:
                counts["__missing__"] = missing
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
        return [
            DealLandscapeBucketRead(
                key=key,
                label="未披露" if key == "__missing__" else key,
                count=int(count),
                share=round(int(count) / total, 6) if total else 0,
            )
            for key, count in ordered
        ]

    return DealLandscapeRead(
        total_deals=total,
        limit=limit,
        deal_type=buckets("deal_type", exclusive=True),
        status=buckets("status", exclusive=True),
        direction=buckets("direction", exclusive=True),
        territory=buckets("territory", exclusive=True),
        currency=buckets("currency", exclusive=True),
        asset_modality=buckets("asset_modality", exclusive=False),
        transaction_phase=buckets("development_phase_at_transaction", exclusive=False),
        current_phase=buckets("current_development_phase", exclusive=False),
        party_country=buckets("party_country_region", exclusive=False),
        rights_territory=buckets("rights_territory", exclusive=False),
    )


def deal_saved_search_matches_entity(
    context: QueryContext,
    entity_id: str,
    query: DealSavedSearchQuery,
) -> bool:
    def start(value: Any) -> datetime | None:
        return datetime.combine(value, time.min, tzinfo=UTC) if value else None

    def end(value: Any) -> datetime | None:
        return datetime.combine(value, time.max, tzinfo=UTC) if value else None

    filters = _deal_filters(
        context,
        entity_id,
        query.q,
        query.deal_type,
        query.territory,
        query.party,
        status=query.status.value if query.status else None,
        direction=query.direction.value if query.direction else None,
        direction_reference_jurisdiction=query.direction_reference_jurisdiction,
        asset_entity_id=query.asset_entity_id,
        target_entity_id=query.target_entity_id,
        disease_entity_id=query.disease_entity_id,
        asset_modality=query.asset_modality,
        asset_program_tag=query.asset_program_tag,
        party_entity_id=query.party_entity_id,
        party_role=query.party_role.value if query.party_role else None,
        party_country_region=query.party_country_region,
        party_organization_type=query.party_organization_type,
        development_phase_at_transaction=(
            query.development_phase_at_transaction.value if query.development_phase_at_transaction else None
        ),
        current_development_phase=(query.current_development_phase.value if query.current_development_phase else None),
        right_type=query.right_type.value if query.right_type else None,
        rights_territory=query.rights_territory,
        currency=query.currency,
        announced_from=start(query.announced_from),
        announced_to=end(query.announced_to),
        terminated_from=start(query.terminated_from),
        terminated_to=end(query.terminated_to),
        source_updated_from=start(query.source_updated_from),
        source_updated_to=end(query.source_updated_to),
        upfront_amount_min=query.upfront_amount_min,
        upfront_amount_max=query.upfront_amount_max,
        total_potential_amount_min=query.total_potential_amount_min,
        total_potential_amount_max=query.total_potential_amount_max,
    )
    statement = select(DealProfile.id).where(*filters).limit(1)
    return context.session.scalar(statement.with_only_columns(literal(True))) is True
