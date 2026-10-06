from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.governance.materialization_context import MaterializationContext
from pharma_intel.models import DevelopmentProgram, ExtractionRun, FactProvenanceLink, SourceVersion, StagedFact


def legacy_regional_copy_candidate(program: DevelopmentProgram) -> bool:
    return (
        program.global_phase is not None
        and program.global_phase_started_at is None
        and program.global_phase == program.phase.value
        and program.china_phase is None
    )


def legacy_chembl_regional_history(
    session: Session,
    tenant_id: str,
    program: DevelopmentProgram,
    *,
    required_source_asset_id: str | None = None,
    limit: int | None = None,
    lock_facts: bool = False,
) -> list[tuple[StagedFact, ExtractionRun, SourceVersion]] | None:
    if not legacy_regional_copy_candidate(program):
        return None
    statement = (
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
            StagedFact.tenant_id == tenant_id,
            StagedFact.fact_kind == "program",
            FactProvenanceLink.resource_type == "development_program",
            FactProvenanceLink.resource_id == program.id,
        )
        .order_by(StagedFact.id)
        .limit(limit)
        .execution_options(populate_existing=True)
    )
    if lock_facts:
        statement = statement.with_for_update(of=StagedFact)
    previous = [(fact, run, version) for fact, run, version in session.execute(statement).all()]
    if not previous:
        return None
    for fact, run, version in previous:
        if (
            run.model_provider != "deterministic-adapter"
            or not run.model_name.startswith("chembl_mechanism_json:")
            or (required_source_asset_id is not None and version.source_asset_id != required_source_asset_id)
            or fact.payload.get("global_phase") not in (None, fact.payload.get("phase"))
            or fact.payload.get("china_phase") is not None
        ):
            return None
    return previous


def clear_proven_legacy_chembl_regional_inference(
    context: MaterializationContext,
    staged: StagedFact,
    program: DevelopmentProgram,
) -> None:
    """Repair only a projection whose complete recorded history proves the old inference.

    Historical staged facts, snapshots and links remain immutable. Mixed, missing,
    or explicitly regional evidence is never cleared by this adapter correction.
    """
    if not legacy_regional_copy_candidate(program) or staged.payload.get("global_phase") is not None:
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
    if (
        legacy_chembl_regional_history(
            context.session, context.tenant_id, program, required_source_asset_id=current_version.source_asset_id
        )
        is None
    ):
        return
    program.global_phase = None
