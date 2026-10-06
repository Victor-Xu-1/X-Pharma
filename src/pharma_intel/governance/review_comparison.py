from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.models import DataSource, ExtractionRun, SourceAsset, SourceVersion, StagedFact
from pharma_intel.schemas.governance import (
    GovernanceFactComparisonItemRead,
    GovernanceFactComparisonRead,
    GovernanceFactOriginRead,
    StagedFactRead,
)

MAX_COMPARISON_CONFLICTS = 20


def read_fact_comparison(session: Session, tenant_id: str, fact_id: str) -> GovernanceFactComparisonRead:
    fact = session.scalar(select(StagedFact).where(StagedFact.tenant_id == tenant_id, StagedFact.id == fact_id))
    if fact is None:
        raise LookupError("Staged fact not found")
    conflict_ids = list(dict.fromkeys(fact.conflict_with_ids))
    requested = conflict_ids[:MAX_COMPARISON_CONFLICTS]
    conflicts = list(
        session.scalars(
            select(StagedFact)
            .where(
                StagedFact.tenant_id == tenant_id,
                StagedFact.id.in_(requested),
            )
            .order_by(StagedFact.created_at.desc(), StagedFact.id)
        )
    )
    run_ids = {item.extraction_run_id for item in [fact, *conflicts]}
    rows = session.execute(
        select(ExtractionRun, SourceVersion, SourceAsset, DataSource)
        .join(
            SourceVersion,
            (SourceVersion.id == ExtractionRun.source_version_id)
            & (SourceVersion.tenant_id == ExtractionRun.tenant_id),
        )
        .join(
            SourceAsset,
            (SourceAsset.id == SourceVersion.source_asset_id) & (SourceAsset.tenant_id == SourceVersion.tenant_id),
        )
        .join(
            DataSource, (DataSource.id == SourceAsset.data_source_id) & (DataSource.tenant_id == SourceAsset.tenant_id)
        )
        .where(ExtractionRun.tenant_id == tenant_id, ExtractionRun.id.in_(run_ids))
    )
    origins = {
        run.id: GovernanceFactOriginRead(
            model_provider=run.model_provider,
            model_name=run.model_name,
            source_name=source.name,
            source_file_name=asset.file_name,
            source_version_number=version.version_number,
            source_content_sha256=version.content_sha256,
            collected_at=version.created_at,
        )
        for run, version, asset, source in rows
    }
    return GovernanceFactComparisonRead(
        fact=StagedFactRead.model_validate(fact),
        origin=origins.get(fact.extraction_run_id),
        conflicts=[
            GovernanceFactComparisonItemRead(
                fact=StagedFactRead.model_validate(item), origin=origins.get(item.extraction_run_id)
            )
            for item in conflicts
        ],
        conflict_total=len(conflict_ids),
        unavailable_conflicts=len(requested) - len(conflicts),
        truncated=len(conflict_ids) > len(requested),
    )
