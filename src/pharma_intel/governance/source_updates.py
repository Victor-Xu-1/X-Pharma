from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.models import (
    DataSource,
    DataSourceType,
    ExtractionRun,
    GovernanceStatus,
    SourceAsset,
    SourceVersion,
    StagedFact,
)


@dataclass(frozen=True)
class OfficialSourceUpdate:
    superseded_ids: frozenset[str] = frozenset()
    stale: bool = False


def lock_official_source_record(session: Session, version: SourceVersion) -> None:
    session.scalar(
        select(SourceAsset.id)
        .join(DataSource, DataSource.id == SourceAsset.data_source_id)
        .where(
            SourceAsset.id == version.source_asset_id,
            SourceAsset.tenant_id == version.tenant_id,
            DataSource.tenant_id == version.tenant_id,
            DataSource.source_type.in_([DataSourceType.CLINICALTRIALS_GOV, DataSourceType.CHEMBL]),
        )
        .with_for_update(of=SourceAsset)
    )


def official_source_update(
    session: Session, version: SourceVersion, prior_facts: list[StagedFact]
) -> OfficialSourceUpdate:
    """Only a validated deterministic revision of the same raw record may supersede itself."""
    source_type = session.scalar(
        select(DataSource.source_type)
        .join(SourceAsset, SourceAsset.data_source_id == DataSource.id)
        .where(
            DataSource.tenant_id == version.tenant_id,
            SourceAsset.tenant_id == version.tenant_id,
            SourceAsset.id == version.source_asset_id,
        )
    )
    if source_type not in {DataSourceType.CLINICALTRIALS_GOV, DataSourceType.CHEMBL} or not prior_facts:
        return OfficialSourceUpdate()
    rows = session.execute(
        select(StagedFact.id, SourceVersion.version_number, StagedFact.status)
        .join(ExtractionRun, ExtractionRun.id == StagedFact.extraction_run_id)
        .join(SourceVersion, SourceVersion.id == ExtractionRun.source_version_id)
        .where(
            StagedFact.tenant_id == version.tenant_id,
            StagedFact.id.in_([fact.id for fact in prior_facts]),
            ExtractionRun.tenant_id == version.tenant_id,
            ExtractionRun.model_provider == "deterministic-adapter",
            SourceVersion.tenant_id == version.tenant_id,
            SourceVersion.source_asset_id == version.source_asset_id,
        )
    ).all()
    return OfficialSourceUpdate(
        superseded_ids=frozenset(fact_id for fact_id, number, _status in rows if number < version.version_number),
        stale=any(
            number > version.version_number and status in {GovernanceStatus.APPROVED, GovernanceStatus.PUBLISHED}
            for _fact_id, number, status in rows
        ),
    )
