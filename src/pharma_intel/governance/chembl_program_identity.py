from __future__ import annotations

import re

from sqlalchemy import select

from pharma_intel.governance.contracts import GovernanceError
from pharma_intel.governance.materialization_context import MaterializationContext
from pharma_intel.models import DataSourceType, DevelopmentProgram, ExtractionRun, FactProvenanceLink, StagedFact


def native_chembl_program(
    context: MaterializationContext,
    staged: StagedFact,
) -> tuple[bool, DevelopmentProgram | None]:
    if context._source_type_for_document(staged.source_document_id) != DataSourceType.CHEMBL:
        return False, None
    run = context.session.scalar(
        select(ExtractionRun).where(
            ExtractionRun.tenant_id == context.tenant_id,
            ExtractionRun.id == staged.extraction_run_id,
        )
    )
    if (
        run is None
        or run.model_provider != "deterministic-adapter"
        or not run.model_name.startswith("chembl_mechanism_json:")
    ):
        return False, None
    locator = staged.source_locator
    if locator is None or re.fullmatch(r"mechanism:[0-9]+", locator) is None:
        raise GovernanceError("Native ChEMBL program requires its explicit mechanism record identity")
    identifiers = list(
        context.session.scalars(
            select(FactProvenanceLink.resource_id)
            .join(
                StagedFact,
                (StagedFact.id == FactProvenanceLink.staged_fact_id)
                & (StagedFact.tenant_id == FactProvenanceLink.tenant_id),
            )
            .join(
                ExtractionRun,
                (ExtractionRun.id == StagedFact.extraction_run_id) & (ExtractionRun.tenant_id == StagedFact.tenant_id),
            )
            .where(
                FactProvenanceLink.tenant_id == context.tenant_id,
                FactProvenanceLink.resource_type == "development_program",
                StagedFact.fact_kind == "program",
                StagedFact.source_locator == locator,
                ExtractionRun.model_provider == "deterministic-adapter",
                ExtractionRun.model_name.startswith("chembl_mechanism_json:"),
            )
            .distinct()
            .limit(2)
        )
    )
    if len(identifiers) > 1:
        raise GovernanceError("ChEMBL mechanism is linked to multiple programs; identity review is required")
    if not identifiers:
        return True, None
    program = context.session.scalar(
        select(DevelopmentProgram)
        .where(
            DevelopmentProgram.tenant_id == context.tenant_id,
            DevelopmentProgram.id == identifiers[0],
        )
        .with_for_update()
    )
    if program is None:
        raise GovernanceError("ChEMBL mechanism program provenance is incomplete")
    other_record = context.session.scalar(
        select(StagedFact.id)
        .join(
            FactProvenanceLink,
            (FactProvenanceLink.staged_fact_id == StagedFact.id)
            & (FactProvenanceLink.tenant_id == StagedFact.tenant_id),
        )
        .where(
            StagedFact.tenant_id == context.tenant_id,
            StagedFact.fact_kind == "program",
            FactProvenanceLink.resource_type == "development_program",
            FactProvenanceLink.resource_id == program.id,
            (StagedFact.source_locator != locator) | StagedFact.source_locator.is_(None),
        )
        .limit(1)
    )
    if other_record is not None:
        raise GovernanceError("Multiple source records share this program; preserve history and review identity")
    return True, program
