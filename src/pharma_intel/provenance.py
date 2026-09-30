from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.models import (
    EvidenceClaim,
    FactProvenanceLink,
    GovernanceStatus,
    SourceAsset,
    SourceAssetState,
    SourceDocument,
    SourceVersion,
    StagedFact,
)

SUPPORTED_PROVENANCE_RESOURCE_TYPES = frozenset(
    {
        "activity_measurement",
        "assay",
        "clinical_trial",
        "compound_structure",
        "deal",
        "development_program",
        "epidemiology_observation",
        "evidence_claim",
        "news_event",
        "patient_population",
        "patent_family",
        "regulatory_event",
        "target_profile",
        "target_evidence",
    }
)


@dataclass(frozen=True)
class ProvenanceRecord:
    link: FactProvenanceLink
    staged_fact: StagedFact
    claim: EvidenceClaim
    document: SourceDocument
    version: SourceVersion
    asset: SourceAsset


class ProvenanceRepository:
    def __init__(self, session: Session, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def list_for_record(
        self,
        resource_type: str,
        resource_id: str,
        limit: int,
    ) -> list[ProvenanceRecord]:
        self._validate_type(resource_type)
        rows = self.session.execute(
            select(
                FactProvenanceLink,
                StagedFact,
                EvidenceClaim,
                SourceDocument,
                SourceVersion,
                SourceAsset,
            )
            .join(StagedFact, StagedFact.id == FactProvenanceLink.staged_fact_id)
            .join(EvidenceClaim, EvidenceClaim.id == FactProvenanceLink.evidence_claim_id)
            .join(SourceDocument, SourceDocument.id == FactProvenanceLink.source_document_id)
            .join(SourceVersion, SourceVersion.id == FactProvenanceLink.source_version_id)
            .join(SourceAsset, SourceAsset.id == FactProvenanceLink.source_asset_id)
            .where(
                FactProvenanceLink.tenant_id == self.tenant_id,
                FactProvenanceLink.resource_type == resource_type,
                FactProvenanceLink.resource_id == resource_id,
                StagedFact.tenant_id == self.tenant_id,
                StagedFact.status == GovernanceStatus.PUBLISHED,
                EvidenceClaim.tenant_id == self.tenant_id,
                SourceDocument.tenant_id == self.tenant_id,
                SourceVersion.tenant_id == self.tenant_id,
                SourceAsset.tenant_id == self.tenant_id,
                SourceAsset.state != SourceAssetState.DELETED,
            )
            .order_by(FactProvenanceLink.created_at, FactProvenanceLink.id)
            .limit(limit)
        )
        return [ProvenanceRecord(*row) for row in rows]

    def dataset_keys_for_record(self, resource_type: str, resource_id: str) -> list[str]:
        self._validate_type(resource_type)
        return list(
            self.session.scalars(
                select(FactProvenanceLink.dataset_key)
                .join(StagedFact, StagedFact.id == FactProvenanceLink.staged_fact_id)
                .where(
                    FactProvenanceLink.tenant_id == self.tenant_id,
                    FactProvenanceLink.resource_type == resource_type,
                    FactProvenanceLink.resource_id == resource_id,
                    StagedFact.tenant_id == self.tenant_id,
                    StagedFact.status == GovernanceStatus.PUBLISHED,
                )
                .distinct()
                .order_by(FactProvenanceLink.dataset_key)
            )
        )

    def withdrawn_count(self, resource_type: str, resource_id: str) -> int:
        self._validate_type(resource_type)
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(FactProvenanceLink)
                .join(StagedFact, StagedFact.id == FactProvenanceLink.staged_fact_id)
                .join(SourceAsset, SourceAsset.id == FactProvenanceLink.source_asset_id)
                .where(
                    FactProvenanceLink.tenant_id == self.tenant_id,
                    FactProvenanceLink.resource_type == resource_type,
                    FactProvenanceLink.resource_id == resource_id,
                    StagedFact.tenant_id == self.tenant_id,
                    StagedFact.status == GovernanceStatus.PUBLISHED,
                    SourceAsset.tenant_id == self.tenant_id,
                    SourceAsset.state == SourceAssetState.DELETED,
                )
            )
            or 0
        )

    @staticmethod
    def _validate_type(resource_type: str) -> None:
        if resource_type not in SUPPORTED_PROVENANCE_RESOURCE_TYPES:
            raise ValueError("Unsupported provenance resource type")
