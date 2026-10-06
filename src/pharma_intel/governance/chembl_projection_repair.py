from __future__ import annotations

from sqlalchemy import select

from pharma_intel.governance.materialization_context import MaterializationContext
from pharma_intel.models import DevelopmentProgram, ExtractionRun, FactProvenanceLink, SourceVersion, StagedFact


def clear_proven_legacy_chembl_regional_inference(
    context: MaterializationContext,
    staged: StagedFact,
    program: DevelopmentProgram,
) -> None:
    """Repair only a projection whose complete recorded history proves the old inference.

    Historical staged facts, snapshots and links remain immutable. Mixed, missing,
    or explicitly regional evidence is never cleared by this adapter correction.
    """
    if (
        program.global_phase is None
        or program.global_phase_started_at is not None
        or program.global_phase != program.phase.value
        or program.china_phase is not None
        or staged.payload.get("global_phase") is not None
    ):
        return
    current = context.session.execute(
        select(ExtractionRun, SourceVersion)
        .join(
            SourceVersion,
            (SourceVersion.id == ExtractionRun.source_version_id)
            & (SourceVersion.tenant_id == ExtractionRun.tenant_id),
        )
        .where(ExtractionRun.tenant_id == context.tenant_id, ExtractionRun.id == staged.extraction_run_id)
    ).one_or_none()
    if current is None:
        return
    current_run, current_version = current
    if current_run.model_provider != "deterministic-adapter" or not current_run.model_name.startswith(
        "chembl_mechanism_json:"
    ):
        return
    previous = context.session.execute(
        select(StagedFact, ExtractionRun, SourceVersion)
        .join(
            FactProvenanceLink,
            (FactProvenanceLink.staged_fact_id == StagedFact.id)
            & (FactProvenanceLink.tenant_id == StagedFact.tenant_id),
        )
        .join(
            ExtractionRun,
            (ExtractionRun.id == StagedFact.extraction_run_id) & (ExtractionRun.tenant_id == StagedFact.tenant_id),
        )
        .join(
            SourceVersion,
            (SourceVersion.id == ExtractionRun.source_version_id)
            & (SourceVersion.tenant_id == ExtractionRun.tenant_id),
        )
        .where(
            StagedFact.tenant_id == context.tenant_id,
            StagedFact.fact_kind == "program",
            FactProvenanceLink.resource_type == "development_program",
            FactProvenanceLink.resource_id == program.id,
        )
    ).all()
    if not previous:
        return
    for fact, run, version in previous:
        if (
            run.model_provider != "deterministic-adapter"
            or not run.model_name.startswith("chembl_mechanism_json:")
            or version.source_asset_id != current_version.source_asset_id
            or fact.payload.get("global_phase") not in (None, fact.payload.get("phase"))
            or fact.payload.get("china_phase") is not None
        ):
            return
    program.global_phase = None
