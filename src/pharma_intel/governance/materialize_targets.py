from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select

from pharma_intel.governance.contracts import GovernanceError
from pharma_intel.governance.fact_identity import _projection
from pharma_intel.governance.materialization_context import MaterializationContext
from pharma_intel.governance.temporal_merge import (
    _should_update_temporal_state,
    _validated_datetime,
)
from pharma_intel.models import (
    StagedFact,
    TargetEvidenceObservation,
)


def materialize_target_evidence(
    context: MaterializationContext,
    staged: StagedFact,
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    target = context._entity(cast(dict[str, Any], payload["target"]), staged.source_document_id)
    disease = context._optional_entity(payload.get("disease"), staged.source_document_id)
    observation = context.session.scalar(
        select(TargetEvidenceObservation).where(
            TargetEvidenceObservation.tenant_id == context.tenant_id,
            TargetEvidenceObservation.source_system == "governed_ai",
            TargetEvidenceObservation.source_record_id == payload["record_identifier"],
        )
    )
    if observation is None:
        observation = TargetEvidenceObservation(
            tenant_id=context.tenant_id,
            source_system="governed_ai",
            source_record_id=str(payload["record_identifier"]),
            target_entity_id=target.id,
            disease_entity_id=disease.id if disease else None,
            evidence_type=str(payload["evidence_type"]),
            direction=str(payload["direction"]),
            summary=str(payload["summary"]),
        )
        context.session.add(observation)
    elif observation.target_entity_id != target.id:
        raise GovernanceError("Target evidence record identifier is already assigned to another target")
    incoming_observed_at = _validated_datetime(payload.get("observed_at"))
    if _should_update_temporal_state(observation.observed_at, incoming_observed_at):
        observation.disease_entity_id = disease.id if disease else None
        observation.evidence_type = str(payload["evidence_type"])
        observation.direction = str(payload["direction"])
        observation.study_name = cast(str | None, payload.get("study_name"))
        observation.population = cast(str | None, payload.get("population"))
        observation.tissue = cast(str | None, payload.get("tissue"))
        observation.variant = cast(str | None, payload.get("variant"))
        observation.effect_size = cast(float | None, payload.get("effect_size"))
        observation.effect_unit = cast(str | None, payload.get("effect_unit"))
        observation.p_value = cast(float | None, payload.get("p_value"))
        observation.sample_size = cast(int | None, payload.get("sample_size"))
        observation.summary = str(payload["summary"])
        observation.observed_at = incoming_observed_at
        observation.qualifiers = dict(payload.get("qualifiers") or {})
        observation.source_document_id = staged.source_document_id
    if disease:
        context._relationship(target, "associated_with_disease", disease, staged)
    context.session.flush()
    return [_projection("target_evidence", observation.id)]
