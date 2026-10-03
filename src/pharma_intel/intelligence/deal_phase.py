from __future__ import annotations

from typing import Any

from sqlalchemy import and_, case, func, select

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.vocabulary import _DEVELOPMENT_PHASE_RANK
from pharma_intel.models import DealAssetAssociation, DevelopmentPhase, DevelopmentProgram


def _current_program_phase_projection(context: QueryContext) -> Any:
    phase_rank = case(
        *[
            (DevelopmentProgram.phase == DevelopmentPhase(phase), rank)
            for phase, rank in _DEVELOPMENT_PHASE_RANK.items()
        ],
        else_=-2,
    )
    ranked = (
        select(
            DevelopmentProgram.drug_entity_id.label("drug_entity_id"),
            DevelopmentProgram.phase.label("phase"),
            DevelopmentProgram.status_date.label("status_date"),
            func.row_number()
            .over(
                partition_by=DevelopmentProgram.drug_entity_id,
                order_by=(
                    phase_rank.desc(),
                    DevelopmentProgram.status_date.desc().nullslast(),
                    DevelopmentProgram.id,
                ),
            )
            .label("phase_rank_row"),
        )
        .where(DevelopmentProgram.tenant_id == context.tenant_id)
        .subquery()
    )
    return (
        select(
            ranked.c.drug_entity_id,
            ranked.c.phase,
            ranked.c.status_date,
        )
        .where(ranked.c.phase_rank_row == 1)
        .subquery()
    )


def _deal_asset_phase_facets(context: QueryContext, source: Any) -> dict[str, int]:
    counts = context.session.execute(
        select(
            DealAssetAssociation.development_phase_at_transaction,
            func.count(func.distinct(source.c.deal_id)),
        )
        .select_from(source)
        .join(
            DealAssetAssociation,
            and_(
                DealAssetAssociation.tenant_id == context.tenant_id,
                DealAssetAssociation.deal_id == source.c.deal_id,
            ),
        )
        .where(DealAssetAssociation.development_phase_at_transaction.is_not(None))
        .group_by(DealAssetAssociation.development_phase_at_transaction)
        .order_by(
            func.count(func.distinct(source.c.deal_id)).desc(),
            DealAssetAssociation.development_phase_at_transaction,
        )
    ).all()
    return {str(phase): int(count) for phase, count in counts if phase}


def _deal_current_phase_facets(context: QueryContext, source: Any) -> dict[str, int]:
    current_programs = _current_program_phase_projection(context)
    counts = context.session.execute(
        select(current_programs.c.phase, func.count(func.distinct(source.c.deal_id)))
        .select_from(source)
        .join(
            DealAssetAssociation,
            and_(
                DealAssetAssociation.tenant_id == context.tenant_id,
                DealAssetAssociation.deal_id == source.c.deal_id,
            ),
        )
        .join(
            current_programs,
            current_programs.c.drug_entity_id == DealAssetAssociation.asset_entity_id,
        )
        .group_by(current_programs.c.phase)
        .order_by(func.count(func.distinct(source.c.deal_id)).desc(), current_programs.c.phase)
    ).all()
    return {phase.value if hasattr(phase, "value") else str(phase): int(count) for phase, count in counts if phase}
