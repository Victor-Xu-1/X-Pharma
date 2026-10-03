from __future__ import annotations

from typing import Any

from sqlalchemy import String, and_, cast, func, literal, select, union_all

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.models import DevelopmentProgramOrganization, Entity


def _pipeline_organization_source(context: QueryContext, source: Any) -> Any:
    link = DevelopmentProgramOrganization.__table__.alias("landscape_program_organization")
    organization = Entity.__table__.alias("landscape_organization")
    current_link = (
        select(literal(1))
        .select_from(link)
        .where(
            link.c.tenant_id == context.tenant_id,
            link.c.program_id == source.c.program_id,
            link.c.organization_set_version == source.c.organization_set_version,
        )
        .correlate(source)
        .exists()
    )
    linked = select(
        source.c.program_id.label("program_id"),
        source.c.drug_entity_id.label("drug_entity_id"),
        source.c.drug_identity_id.label("drug_identity_id"),
        link.c.organization_entity_id.label("organization_entity_id"),
        organization.c.name.label("organization_name"),
        link.c.role.label("organization_role"),
        link.c.organization_type.label("organization_type"),
        link.c.country_region.label("organization_country_region"),
        source.c.phase.label("phase"),
        source.c.global_phase.label("global_phase"),
        source.c.china_phase.label("china_phase"),
    ).select_from(
        source.join(
            link,
            and_(
                link.c.tenant_id == context.tenant_id,
                link.c.program_id == source.c.program_id,
                link.c.organization_set_version == source.c.organization_set_version,
            ),
        ).join(organization, organization.c.id == link.c.organization_entity_id)
    )
    legacy = select(
        source.c.program_id.label("program_id"),
        source.c.drug_entity_id.label("drug_entity_id"),
        source.c.drug_identity_id.label("drug_identity_id"),
        source.c.organization_entity_id.label("organization_entity_id"),
        source.c.organization_name.label("organization_name"),
        literal("originator").label("organization_role"),
        cast(literal(None), String).label("organization_type"),
        cast(literal(None), String).label("organization_country_region"),
        source.c.phase.label("phase"),
        source.c.global_phase.label("global_phase"),
        source.c.china_phase.label("china_phase"),
    ).where(~current_link)
    return union_all(linked, legacy).subquery("pipeline_landscape_organizations")


def _pipeline_organization_facets(context: QueryContext, source: Any, id_name: str) -> dict[str, dict[str, int]]:
    organization_source = _pipeline_organization_source(context, source)
    count_expression = func.count(func.distinct(organization_source.c[id_name]))
    facets: dict[str, dict[str, int]] = {}
    for name in ("organization_role", "organization_type", "organization_country_region"):
        column = organization_source.c[name]
        rows = context.session.execute(
            select(column, count_expression)
            .select_from(organization_source)
            .where(column.is_not(None), column != "")
            .group_by(column)
            .order_by(count_expression.desc(), column)
        ).all()
        facets[name] = {str(value): int(count) for value, count in rows}
    return facets
