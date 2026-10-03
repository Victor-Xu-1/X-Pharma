from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, literal, select, true, union_all

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.deal_filters import _deal_filters
from pharma_intel.intelligence.deal_read import _deal_search_items
from pharma_intel.intelligence.pipeline_read import _read_programs
from pharma_intel.models import DealProfile, DevelopmentProgram, Entity, EntityType, ReviewStatus
from pharma_intel.schemas import CompanyTimelineEventRead, CompanyTimelineResult, EntityRead


def company_timeline(
    context: QueryContext,
    company_entity_id: str,
    limit: int,
    offset: int = 0,
) -> CompanyTimelineResult | None:
    company = context.session.scalar(
        select(Entity).where(
            Entity.id == company_entity_id,
            Entity.tenant_id == context.tenant_id,
            Entity.entity_type == EntityType.ORGANIZATION,
            Entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
        )
    )
    if company is None:
        return None

    deal_filters = _deal_filters(context, company_entity_id)
    program_events = select(
        literal("program_status").label("event_type"),
        DevelopmentProgram.id.label("record_id"),
        DevelopmentProgram.status_date.label("occurred_at"),
    ).where(
        DevelopmentProgram.tenant_id == context.tenant_id,
        DevelopmentProgram.organization_entity_id == company_entity_id,
        DevelopmentProgram.status_date.is_not(None),
    )
    deal_events = select(
        literal("deal_announced").label("event_type"),
        DealProfile.id.label("record_id"),
        DealProfile.announced_at.label("occurred_at"),
    ).where(*deal_filters, DealProfile.announced_at.is_not(None))
    timeline = union_all(program_events, deal_events).subquery()
    total = context.session.scalar(select(func.count()).select_from(timeline)) or 0
    rows = context.session.execute(
        select(timeline.c.event_type, timeline.c.record_id, timeline.c.occurred_at)
        .order_by(timeline.c.occurred_at.desc(), timeline.c.event_type, timeline.c.record_id)
        .limit(limit)
        .offset(offset)
    ).all()

    program_ids = [record_id for event_type, record_id, _occurred_at in rows if event_type == "program_status"]
    deal_ids = [record_id for event_type, record_id, _occurred_at in rows if event_type == "deal_announced"]
    programs = {
        item.id: item
        for item in _read_programs(
            context,
            [
                DevelopmentProgram.tenant_id == context.tenant_id,
                DevelopmentProgram.id.in_(program_ids),
            ],
            len(program_ids),
            0,
        )
    }
    deals = {
        item.id: item
        for item in _deal_search_items(
            context,
            [DealProfile.tenant_id == context.tenant_id, DealProfile.id.in_(deal_ids)],
            len(deal_ids),
            0,
        )
    }

    items: list[CompanyTimelineEventRead] = []
    for event_type, record_id, occurred_at in rows:
        normalized_occurred_at = (
            occurred_at.replace(tzinfo=UTC) if occurred_at is not None and occurred_at.tzinfo is None else occurred_at
        )
        if event_type == "program_status":
            program = programs[record_id]
            items.append(
                CompanyTimelineEventRead(
                    id=f"program_status:{record_id}",
                    event_type="program_status",
                    occurred_at=normalized_occurred_at,
                    title=f"{program.drug_name} · {program.phase}",
                    program=program,
                )
            )
        else:
            deal = deals[record_id]
            items.append(
                CompanyTimelineEventRead(
                    id=f"deal_announced:{record_id}",
                    event_type="deal_announced",
                    occurred_at=normalized_occurred_at,
                    title=deal.name,
                    deal=deal,
                )
            )

    facets = {
        "event_type": {
            str(value): int(count)
            for value, count in context.session.execute(
                select(timeline.c.event_type, func.count())
                .select_from(timeline)
                .group_by(timeline.c.event_type)
                .order_by(timeline.c.event_type)
            ).all()
        },
        "phase": {
            value.value if hasattr(value, "value") else str(value): int(count)
            for value, count in context.session.execute(
                select(DevelopmentProgram.phase, func.count(DevelopmentProgram.id))
                .where(
                    DevelopmentProgram.tenant_id == context.tenant_id,
                    DevelopmentProgram.organization_entity_id == company_entity_id,
                    DevelopmentProgram.status_date.is_not(None),
                )
                .group_by(DevelopmentProgram.phase)
                .order_by(func.count(DevelopmentProgram.id).desc(), DevelopmentProgram.phase)
            ).all()
        },
        "deal_type": {
            str(value): int(count)
            for value, count in context.session.execute(
                select(DealProfile.deal_type, func.count(DealProfile.id))
                .where(*deal_filters, DealProfile.announced_at.is_not(None))
                .group_by(DealProfile.deal_type)
                .order_by(func.count(DealProfile.id).desc(), DealProfile.deal_type)
            ).all()
        },
    }
    return CompanyTimelineResult(
        company=EntityRead.model_validate(company),
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        facets=facets,
        as_of=datetime.now(UTC),
        warnings=["时间线仅包含具有明确日期的管线当前状态和已披露交易公告；未观察到记录不代表公司不存在相关活动。"],
    )
