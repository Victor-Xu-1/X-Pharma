from __future__ import annotations

from typing import Any

from sqlalchemy import and_, case, func, select

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.pipeline_predicates import _pipeline_deal_exists, _pipeline_trial_exists
from pharma_intel.intelligence.scope import _entity_identity_member_ids
from pharma_intel.intelligence.vocabulary import _TRIAL_DRUG_ROLES, _TRIAL_RESULT_EVALUATION_ORDER
from pharma_intel.models import (
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    DealAssetAssociation,
    DealProfile,
    EntityType,
    TrialResultEvaluation,
)


def _pipeline_signal_maps(
    context: QueryContext,
    drug_entity_ids: list[str],
) -> tuple[
    dict[str, int],
    set[str],
    dict[str, list[TrialResultEvaluation]],
    dict[str, int],
    dict[str, list[str]],
]:
    drug_ids = set(drug_entity_ids)
    if not drug_ids:
        return {}, set(), {}, {}, {}
    identity_members = {drug_id: _entity_identity_member_ids(context, drug_id, EntityType.DRUG) for drug_id in drug_ids}
    all_identity_ids = set().union(*identity_members.values())
    trial_rows = context.session.execute(
        select(
            ClinicalTrialEntityRole.entity_id,
            ClinicalTrialEntityRole.trial_id,
            ClinicalTrialProfile.has_results,
        )
        .join(
            ClinicalTrialProfile,
            and_(
                ClinicalTrialProfile.tenant_id == context.tenant_id,
                ClinicalTrialProfile.id == ClinicalTrialEntityRole.trial_id,
            ),
        )
        .where(
            ClinicalTrialEntityRole.tenant_id == context.tenant_id,
            ClinicalTrialEntityRole.entity_id.in_(all_identity_ids),
            ClinicalTrialEntityRole.role.in_(_TRIAL_DRUG_ROLES),
        )
        .distinct()
    ).all()
    raw_trial_ids: dict[str, set[str]] = {}
    raw_drugs_with_results: set[str] = set()
    for raw_drug_id, trial_id, has_results in trial_rows:
        raw_id = str(raw_drug_id)
        raw_trial_ids.setdefault(raw_id, set()).add(str(trial_id))
        if has_results:
            raw_drugs_with_results.add(raw_id)
    trial_counts = {
        drug_id: len(set().union(*(raw_trial_ids.get(member_id, set()) for member_id in members)))
        for drug_id, members in identity_members.items()
    }
    drugs_with_results = {drug_id for drug_id, members in identity_members.items() if members & raw_drugs_with_results}
    evaluation_rows = context.session.execute(
        select(ClinicalTrialEntityRole.entity_id, ClinicalTrialProfile.result_evaluation)
        .join(
            ClinicalTrialProfile,
            and_(
                ClinicalTrialProfile.tenant_id == context.tenant_id,
                ClinicalTrialProfile.id == ClinicalTrialEntityRole.trial_id,
            ),
        )
        .where(
            ClinicalTrialEntityRole.tenant_id == context.tenant_id,
            ClinicalTrialEntityRole.entity_id.in_(all_identity_ids),
            ClinicalTrialEntityRole.role.in_(_TRIAL_DRUG_ROLES),
            ClinicalTrialProfile.has_results.is_(True),
            ClinicalTrialProfile.result_evaluation.is_not(None),
        )
        .distinct()
    ).all()
    evaluation_sets: dict[str, set[TrialResultEvaluation]] = {}
    raw_evaluations: dict[str, set[TrialResultEvaluation]] = {}
    for raw_drug_id, evaluation in evaluation_rows:
        raw_evaluations.setdefault(str(raw_drug_id), set()).add(TrialResultEvaluation(str(evaluation)))
    for drug_id, members in identity_members.items():
        for member_id in members:
            evaluation_sets.setdefault(drug_id, set()).update(raw_evaluations.get(member_id, set()))
    evaluation_rank = {value: index for index, value in enumerate(_TRIAL_RESULT_EVALUATION_ORDER)}
    evaluations = {
        drug_id: sorted(values, key=evaluation_rank.__getitem__) for drug_id, values in evaluation_sets.items()
    }
    deal_rows = context.session.execute(
        select(
            DealAssetAssociation.asset_entity_id,
            func.count(func.distinct(DealAssetAssociation.deal_id)),
        )
        .join(
            DealProfile,
            and_(
                DealProfile.tenant_id == context.tenant_id,
                DealProfile.id == DealAssetAssociation.deal_id,
            ),
        )
        .where(
            DealAssetAssociation.tenant_id == context.tenant_id,
            DealAssetAssociation.asset_entity_id.in_(drug_ids),
        )
        .group_by(DealAssetAssociation.asset_entity_id)
    ).all()
    deal_counts = {str(drug_id): int(count) for drug_id, count in deal_rows}
    currency_rows = context.session.execute(
        select(DealAssetAssociation.asset_entity_id, DealProfile.currency)
        .join(
            DealProfile,
            and_(
                DealProfile.tenant_id == context.tenant_id,
                DealProfile.id == DealAssetAssociation.deal_id,
            ),
        )
        .where(
            DealAssetAssociation.tenant_id == context.tenant_id,
            DealAssetAssociation.asset_entity_id.in_(drug_ids),
            DealProfile.currency.is_not(None),
        )
        .distinct()
    ).all()
    currency_sets: dict[str, set[str]] = {}
    for drug_id, currency in currency_rows:
        currency_sets.setdefault(str(drug_id), set()).add(str(currency))
    currencies = {drug_id: sorted(values) for drug_id, values in currency_sets.items()}
    return trial_counts, drugs_with_results, evaluations, deal_counts, currencies


def _pipeline_signal_facets(context: QueryContext, source: Any, id_name: str) -> dict[str, dict[str, int]]:
    count_expression = func.count(func.distinct(source.c[id_name]))
    result_signal = case(
        (_pipeline_trial_exists(context, source.c.drug_entity_id, require_results=True), "true"),
        else_="false",
    ).label("has_clinical_results")
    deal_signal = case(
        (_pipeline_deal_exists(context, source.c.drug_entity_id), "true"),
        else_="false",
    ).label("has_deal")
    facets: dict[str, dict[str, int]] = {}
    for name, signal in (("has_clinical_results", result_signal), ("has_deal", deal_signal)):
        rows = context.session.execute(
            select(signal, count_expression).select_from(source).group_by(signal).order_by(signal)
        ).all()
        facets[name] = {str(value): int(count) for value, count in rows}
    evaluation_rows = context.session.execute(
        select(
            ClinicalTrialProfile.result_evaluation,
            count_expression,
        )
        .select_from(source)
        .join(
            ClinicalTrialEntityRole,
            and_(
                ClinicalTrialEntityRole.tenant_id == context.tenant_id,
                ClinicalTrialEntityRole.entity_id == source.c.drug_entity_id,
                ClinicalTrialEntityRole.role.in_(_TRIAL_DRUG_ROLES),
            ),
        )
        .join(
            ClinicalTrialProfile,
            and_(
                ClinicalTrialProfile.tenant_id == context.tenant_id,
                ClinicalTrialProfile.id == ClinicalTrialEntityRole.trial_id,
                ClinicalTrialProfile.has_results.is_(True),
            ),
        )
        .where(ClinicalTrialProfile.result_evaluation.is_not(None))
        .group_by(ClinicalTrialProfile.result_evaluation)
        .order_by(count_expression.desc(), ClinicalTrialProfile.result_evaluation)
    ).all()
    facets["clinical_result_evaluation"] = {str(evaluation): int(count) for evaluation, count in evaluation_rows}
    currency_rows = context.session.execute(
        select(DealProfile.currency, count_expression)
        .select_from(source)
        .join(
            DealAssetAssociation,
            and_(
                DealAssetAssociation.tenant_id == context.tenant_id,
                DealAssetAssociation.asset_entity_id == source.c.drug_entity_id,
            ),
        )
        .join(
            DealProfile,
            and_(
                DealProfile.tenant_id == context.tenant_id,
                DealProfile.id == DealAssetAssociation.deal_id,
            ),
        )
        .where(DealProfile.currency.is_not(None))
        .group_by(DealProfile.currency)
        .order_by(count_expression.desc(), DealProfile.currency)
    ).all()
    facets["deal_currency"] = {str(currency): int(count) for currency, count in currency_rows}
    return facets
