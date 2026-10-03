from __future__ import annotations

import re
from typing import Any, cast

from sqlalchemy import select

from pharma_intel.governance.contracts import GovernanceError
from pharma_intel.governance.fact_identity import _projection
from pharma_intel.governance.materialization_context import MaterializationContext
from pharma_intel.governance.materialize_assets import materialize_deal, materialize_patent
from pharma_intel.governance.materialize_chemistry import materialize_activity, materialize_structure
from pharma_intel.governance.materialize_events import (
    materialize_epidemiology,
    materialize_news,
    materialize_regulatory,
)
from pharma_intel.governance.materialize_programs import materialize_program
from pharma_intel.governance.materialize_targets import materialize_target_evidence
from pharma_intel.governance.materialize_trials import materialize_trial
from pharma_intel.models import (
    StagedFact,
    TargetProfile,
)


def materialize_structured_fact(
    context: MaterializationContext, staged: StagedFact, payload: dict[str, Any]
) -> list[dict[str, str]]:
    fact_kind = staged.fact_kind
    if fact_kind == "claim":
        return []
    if fact_kind == "target_profile":
        subject = context._entity(cast(dict[str, Any], payload["subject"]), staged.source_document_id)
        profile = context.session.scalar(
            select(TargetProfile).where(
                TargetProfile.tenant_id == context.tenant_id,
                TargetProfile.entity_id == subject.id,
            )
        )
        if profile is None:
            profile = TargetProfile(
                tenant_id=context.tenant_id,
                entity_id=subject.id,
                organism=str(payload.get("organism") or "Homo sapiens"),
            )
            context.session.add(profile)
        for field in ("gene_symbol", "uniprot_accession", "target_class", "function_summary"):
            if payload.get(field) is not None:
                setattr(profile, field, payload[field])
        if payload.get("sequence") is not None:
            profile.sequence = re.sub(r"\s+", "", str(payload["sequence"])).upper()
        if payload.get("organism") is not None:
            profile.organism = str(payload["organism"])
        profile.source_document_id = staged.source_document_id
        context.session.flush()
        return [_projection("target_profile", profile.id)]
    if fact_kind == "target_evidence":
        return materialize_target_evidence(context, staged, payload)
    if fact_kind == "structure":
        return materialize_structure(context, staged, payload)
    if fact_kind == "activity":
        return materialize_activity(context, staged, payload)
    if fact_kind == "program":
        return materialize_program(context, staged, payload)
    if fact_kind == "trial":
        return materialize_trial(context, staged, payload)
    if fact_kind == "patent":
        return materialize_patent(context, staged, payload)
    if fact_kind == "deal":
        return materialize_deal(context, staged, payload)
    if fact_kind == "regulatory":
        return materialize_regulatory(context, staged, payload)
    if fact_kind == "epidemiology":
        return materialize_epidemiology(context, staged, payload)
    if fact_kind == "news":
        return materialize_news(context, staged, payload)
    raise GovernanceError(f"Unsupported structured fact kind: {fact_kind}")
