from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select

from pharma_intel.governance.contracts import GovernanceError
from pharma_intel.governance.fact_identity import _projection
from pharma_intel.governance.materialization_context import MaterializationContext
from pharma_intel.governance.temporal_merge import (
    _merge_strings,
    _merge_trial_status_history,
    _required_datetime,
    _validated_datetime,
)
from pharma_intel.identity import normalize_name
from pharma_intel.models import (
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    ClinicalTrialResultDisclosure,
    DataSourceType,
    Entity,
    EntityType,
    ReviewStatus,
    StagedFact,
    TrialEntityRole,
)


def materialize_trial(
    context: MaterializationContext, staged: StagedFact, payload: dict[str, Any]
) -> list[dict[str, str]]:
    trial_entity = context._entity(cast(dict[str, Any], payload["trial"]), staged.source_document_id)
    trial = context.session.scalar(
        select(ClinicalTrialProfile).where(
            ClinicalTrialProfile.tenant_id == context.tenant_id,
            ClinicalTrialProfile.registry_name == payload["registry_name"],
            ClinicalTrialProfile.registry_id == payload["registry_id"],
        )
    )
    if trial is None:
        trial = ClinicalTrialProfile(
            tenant_id=context.tenant_id,
            entity_id=trial_entity.id,
            registry_name=str(payload["registry_name"]),
            registry_id=str(payload["registry_id"]),
            official_title=str(payload["official_title"]),
        )
        context.session.add(trial)
        context.session.flush()
    elif trial.entity_id != trial_entity.id:
        raise GovernanceError("Clinical trial registry identifier is already assigned to another entity")
    trial.official_title = str(payload["official_title"])
    trial.acronym = cast(str | None, payload.get("acronym"))
    trial.initiation_type = cast(str | None, payload.get("initiation_type"))
    trial.therapy_lines = _merge_strings([], list(payload.get("therapy_lines") or []), limit=12)
    trial.overall_status = cast(str | None, payload.get("overall_status"))
    trial.phases = list(payload.get("phases") or [])
    trial.study_type = cast(str | None, payload.get("study_type"))
    trial.enrollment = cast(int | None, payload.get("enrollment"))
    trial.start_date = _validated_datetime(payload.get("start_date"))
    trial.start_date_precision = cast(str | None, payload.get("start_date_precision"))
    trial.completion_date = _validated_datetime(payload.get("completion_date"))
    trial.completion_date_precision = cast(str | None, payload.get("completion_date_precision"))
    trial.conditions = list(payload.get("conditions") or [])
    trial.interventions = [dict(item) for item in payload.get("interventions") or []]
    trial.sponsors = [dict(item) for item in payload.get("sponsors") or []]
    trial.locations = [dict(item) for item in payload.get("locations") or []]
    trial.study_design = dict(payload.get("study_design") or {})
    trial.eligibility = dict(payload.get("eligibility") or {})
    trial.arms = [dict(item) for item in payload.get("arms") or []]
    trial.outcomes = [dict(item) for item in payload.get("outcomes") or []]
    trial.result_evaluation = cast(str | None, payload.get("result_evaluation"))
    trial.results_first_posted = _validated_datetime(payload.get("results_first_posted"))
    trial.last_update_posted = _validated_datetime(payload.get("last_update_posted"))
    trial.status_history = _merge_trial_status_history(
        trial.status_history or [],
        cast(list[dict[str, Any]], payload.get("status_history") or []),
        current_status=trial.overall_status,
        current_status_at=trial.last_update_posted,
        source_document_id=staged.source_document_id,
    )
    trial.source_document_id = staged.source_document_id
    for reference in payload.get("linked_entities") or []:
        linked = context._entity(cast(dict[str, Any], reference), staged.source_document_id)
        context._relationship(trial_entity, "trial_links_entity", linked, staged)
    materialize_trial_entity_roles(context, trial, trial_entity, staged, payload)
    if context._source_type_for_document(staged.source_document_id) == DataSourceType.CLINICALTRIALS_GOV:
        materialize_official_trial_intervention_roles(context, trial, trial_entity, staged, payload)
    materialize_trial_result_disclosures(context, trial, staged, payload)
    trial.has_results = any(outcome.get("results") for outcome in trial.outcomes) or bool(
        context.session.scalar(
            select(ClinicalTrialResultDisclosure.id)
            .where(
                ClinicalTrialResultDisclosure.tenant_id == context.tenant_id,
                ClinicalTrialResultDisclosure.trial_id == trial.id,
            )
            .limit(1)
        )
    )
    context.session.flush()
    return [_projection("clinical_trial", trial.id)]


def materialize_trial_entity_roles(
    context: MaterializationContext,
    trial: ClinicalTrialProfile,
    trial_entity: Entity,
    staged: StagedFact,
    payload: dict[str, Any],
) -> None:
    for item in payload.get("entity_roles") or []:
        role = TrialEntityRole(str(item["role"]))
        entity = context._entity(cast(dict[str, Any], item["entity"]), staged.source_document_id)
        association = context.session.scalar(
            select(ClinicalTrialEntityRole).where(
                ClinicalTrialEntityRole.tenant_id == context.tenant_id,
                ClinicalTrialEntityRole.trial_id == trial.id,
                ClinicalTrialEntityRole.entity_id == entity.id,
                ClinicalTrialEntityRole.role == role.value,
            )
        )
        if association is None:
            context.session.add(
                ClinicalTrialEntityRole(
                    tenant_id=context.tenant_id,
                    trial_id=trial.id,
                    entity_id=entity.id,
                    role=role.value,
                    source_document_id=staged.source_document_id,
                )
            )
        else:
            association.source_document_id = staged.source_document_id
        context._relationship(trial_entity, "trial_links_entity", entity, staged)
        context._relationship(trial_entity, f"trial_{role.value}", entity, staged)


def materialize_official_trial_intervention_roles(
    context: MaterializationContext,
    trial: ClinicalTrialProfile,
    trial_entity: Entity,
    staged: StagedFact,
    payload: dict[str, Any],
) -> None:
    matched_entities: list[Entity] = []
    seen_entity_ids: set[str] = set()
    for item in payload.get("interventions") or []:
        if not isinstance(item, dict) or str(item.get("type") or "").casefold() not in {
            "drug",
            "biological",
        }:
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        candidates = list(
            context.session.scalars(
                select(Entity)
                .where(
                    Entity.tenant_id == context.tenant_id,
                    Entity.entity_type == EntityType.DRUG,
                    Entity.normalized_name == normalize_name(name),
                    Entity.review_status == ReviewStatus.VERIFIED,
                )
                .order_by(Entity.id)
                .limit(2)
            )
        )
        if len(candidates) != 1 or candidates[0].id in seen_entity_ids:
            continue
        seen_entity_ids.add(candidates[0].id)
        matched_entities.append(candidates[0])

    for position, entity in enumerate(matched_entities):
        role = TrialEntityRole.INVESTIGATIONAL_DRUG if position == 0 else TrialEntityRole.COMBINATION_DRUG
        association = context.session.scalar(
            select(ClinicalTrialEntityRole).where(
                ClinicalTrialEntityRole.tenant_id == context.tenant_id,
                ClinicalTrialEntityRole.trial_id == trial.id,
                ClinicalTrialEntityRole.entity_id == entity.id,
                ClinicalTrialEntityRole.role == role.value,
            )
        )
        if association is None:
            context.session.add(
                ClinicalTrialEntityRole(
                    tenant_id=context.tenant_id,
                    trial_id=trial.id,
                    entity_id=entity.id,
                    role=role.value,
                    source_document_id=staged.source_document_id,
                )
            )
        else:
            association.source_document_id = staged.source_document_id
        context._relationship(trial_entity, "trial_links_entity", entity, staged)
        context._relationship(trial_entity, f"trial_{role.value}", entity, staged)


def materialize_trial_result_disclosures(
    context: MaterializationContext,
    trial: ClinicalTrialProfile,
    staged: StagedFact,
    payload: dict[str, Any],
) -> None:
    for item in payload.get("result_disclosures") or []:
        disclosure_key = str(item["disclosure_key"])
        version = int(item["version"])
        disclosure = context.session.scalar(
            select(ClinicalTrialResultDisclosure).where(
                ClinicalTrialResultDisclosure.tenant_id == context.tenant_id,
                ClinicalTrialResultDisclosure.trial_id == trial.id,
                ClinicalTrialResultDisclosure.disclosure_key == disclosure_key,
                ClinicalTrialResultDisclosure.version == version,
            )
        )
        if disclosure is None:
            disclosure = ClinicalTrialResultDisclosure(
                tenant_id=context.tenant_id,
                trial_id=trial.id,
                disclosure_key=disclosure_key,
                version=version,
                disclosure_type=str(item["disclosure_type"]),
                title=str(item["title"]),
                disclosed_at=_required_datetime(item["disclosed_at"], "disclosed_at"),
            )
            context.session.add(disclosure)
        citation = cast(dict[str, Any], item["citation"])
        disclosure.disclosure_type = str(item["disclosure_type"])
        disclosure.external_id = cast(str | None, item.get("external_id"))
        disclosure.title = str(item["title"])
        disclosure.disclosed_at = _required_datetime(item["disclosed_at"], "disclosed_at")
        disclosure.conference_name = cast(str | None, item.get("conference_name"))
        disclosure.is_key_result = bool(item.get("is_key_result", False))
        disclosure.result_evaluation = cast(str | None, item.get("result_evaluation"))
        disclosure.source_locator = cast(str | None, citation.get("locator"))
        disclosure.source_quote = str(citation["quote"])
        disclosure.source_document_id = staged.source_document_id
