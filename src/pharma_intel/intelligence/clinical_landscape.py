from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, literal, select, true, union_all

from pharma_intel.intelligence.clinical_links import trial_drug_bindings
from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.facets import _json_array_facets
from pharma_intel.intelligence.vocabulary import _public_program_drug_category_sql, _public_program_modality_sql
from pharma_intel.models import DevelopmentProgram, DevelopmentProgramOrganization
from pharma_intel.schemas import ClinicalTrialLandscapeMatrixRowRead, ClinicalTrialLandscapeRead


def _clinical_trial_linked_drug_program_facets(context: QueryContext, source: Any) -> dict[str, dict[str, int]]:
    bindings = trial_drug_bindings(context)
    public_modality = _public_program_modality_sql(
        DevelopmentProgram.modality,
        DevelopmentProgram.drug_category,
    )
    public_drug_category = _public_program_drug_category_sql(
        DevelopmentProgram.modality,
        DevelopmentProgram.drug_category,
    )
    programs = (
        select(
            source.c.trial_id,
            DevelopmentProgram.id.label("program_id"),
            DevelopmentProgram.organization_set_version,
            public_modality.label("linked_drug_modality"),
            DevelopmentProgram.innovation_type.label("linked_drug_innovation_type"),
            public_drug_category.label("linked_drug_category"),
            DevelopmentProgram.program_tags.label("linked_drug_program_tag"),
            DevelopmentProgram.global_phase.label("linked_drug_global_phase"),
        )
        .select_from(source)
        .join(
            bindings,
            bindings.c.trial_id == source.c.trial_id,
        )
        .join(
            DevelopmentProgram,
            and_(
                DevelopmentProgram.tenant_id == context.tenant_id,
                DevelopmentProgram.drug_entity_id == bindings.c.drug_entity_id,
            ),
        )
        .subquery("clinical_trial_linked_program_facets")
    )

    def scalar(name: str) -> dict[str, int]:
        column = programs.c[name]
        rows = context.session.execute(
            select(column, func.count(func.distinct(programs.c.trial_id)))
            .select_from(programs)
            .where(column.is_not(None), column != "")
            .group_by(column)
            .order_by(func.count(func.distinct(programs.c.trial_id)).desc(), column)
        ).all()
        return {str(value): int(count) for value, count in rows if value}

    organizations = (
        select(
            programs.c.trial_id,
            DevelopmentProgramOrganization.country_region.label("linked_drug_organization_country_region"),
        )
        .select_from(programs)
        .join(
            DevelopmentProgramOrganization,
            and_(
                DevelopmentProgramOrganization.tenant_id == context.tenant_id,
                DevelopmentProgramOrganization.program_id == programs.c.program_id,
                DevelopmentProgramOrganization.organization_set_version == programs.c.organization_set_version,
            ),
        )
        .distinct()
        .subquery("clinical_trial_linked_program_org_facets")
    )
    organization_country = organizations.c.linked_drug_organization_country_region
    organization_rows = context.session.execute(
        select(organization_country, func.count(func.distinct(organizations.c.trial_id)))
        .select_from(organizations)
        .where(organization_country.is_not(None), organization_country != "")
        .group_by(organization_country)
        .order_by(func.count(func.distinct(organizations.c.trial_id)).desc(), organization_country)
    ).all()
    return {
        "linked_drug_modality": scalar("linked_drug_modality"),
        "linked_drug_innovation_type": scalar("linked_drug_innovation_type"),
        "linked_drug_category": scalar("linked_drug_category"),
        "linked_drug_program_tag": _json_array_facets(
            context,
            programs,
            "linked_drug_program_tag",
            "trial_id",
            public_program_tags_only=True,
        ),
        "linked_drug_global_phase": scalar("linked_drug_global_phase"),
        "linked_drug_organization_country_region": {
            str(value): int(count) for value, count in organization_rows if value
        },
    }


def _clinical_trial_landscape(context: QueryContext, source: Any, total: int) -> ClinicalTrialLandscapeRead:
    if context.session.get_bind().dialect.name == "postgresql":
        phase_values = (
            func.json_array_elements_text(source.c.phases).table_valued("value").alias("trial_landscape_phase")
        )
    else:
        phase_values = func.json_each(source.c.phases).table_valued("key", "value").alias("trial_landscape_phase")
    phase_value = phase_values.c.value
    exploded = union_all(
        select(
            source.c.trial_id,
            phase_value.label("phase"),
            source.c.result_evaluation,
            source.c.published_at,
        )
        .select_from(source.join(phase_values, true()))
        .where(phase_value.is_not(None), phase_value != ""),
        select(
            source.c.trial_id,
            literal("__missing__").label("phase"),
            source.c.result_evaluation,
            source.c.published_at,
        ).where(func.coalesce(func.json_array_length(source.c.phases), 0) == 0),
    ).subquery("clinical_trial_landscape_rows")

    year_counts = context.session.execute(
        select(
            func.extract("year", exploded.c.published_at).label("publication_year"),
            exploded.c.phase,
            func.count(func.distinct(exploded.c.trial_id)),
        )
        .select_from(exploded)
        .group_by("publication_year", exploded.c.phase)
    ).all()
    evaluation = func.coalesce(exploded.c.result_evaluation, "__missing__")
    evaluation_counts = context.session.execute(
        select(
            exploded.c.phase,
            evaluation.label("evaluation"),
            func.count(func.distinct(exploded.c.trial_id)),
        )
        .select_from(exploded)
        .group_by(exploded.c.phase, evaluation)
    ).all()

    publication_rows: dict[str, dict[str, int]] = {}
    for year, phase, count in year_counts:
        year_key = "__missing__" if year is None else str(int(year))
        publication_rows.setdefault(year_key, {})[str(phase)] = int(count)

    evaluation_rows: dict[str, dict[str, int]] = {}
    for phase, result_evaluation, count in evaluation_counts:
        evaluation_rows.setdefault(str(phase), {})[str(result_evaluation)] = int(count)

    phase_order = {
        "EARLY_PHASE1": 0,
        "PHASE1": 1,
        "PHASE1_PHASE2": 2,
        "PHASE2": 3,
        "PHASE2_PHASE3": 4,
        "PHASE3": 5,
        "PHASE4": 6,
        "NA": 7,
        "__missing__": 8,
    }
    publication_year_phase = [
        ClinicalTrialLandscapeMatrixRowRead(key=key, total=sum(values.values()), values=values)
        for key, values in sorted(
            publication_rows.items(),
            key=lambda item: (item[0] == "__missing__", -int(item[0]) if item[0].isdigit() else 0),
        )
    ]
    phase_evaluation = [
        ClinicalTrialLandscapeMatrixRowRead(key=key, total=sum(values.values()), values=values)
        for key, values in sorted(
            evaluation_rows.items(),
            key=lambda item: (phase_order.get(item[0], 99), item[0]),
        )
    ]
    return ClinicalTrialLandscapeRead(
        total_trials=total,
        publication_year_phase=publication_year_phase,
        phase_evaluation=phase_evaluation,
    )
