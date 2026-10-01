from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.config import Settings
from pharma_intel.governance.model_gateway import ExtractionResponse, OpenAICompatibleExtractionGateway
from pharma_intel.governance.schemas import Citation, EntityReference, ExtractionEnvelope, StructureFact
from pharma_intel.governance.service import GovernanceError, GovernanceService
from pharma_intel.models import (
    CompoundStructure,
    DataSource,
    DataSourceType,
    Entity,
    EntityType,
    EvidenceClaim,
    GovernanceStatus,
    ReviewTask,
    SourceAsset,
    SourceDocument,
    SourceVersion,
    StagedFact,
    StageStatus,
    Tenant,
    UserRole,
)
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.security import hash_password
from tests.support.postgres_safety import require_disposable_postgres_url


class StaticStructureGateway(OpenAICompatibleExtractionGateway):
    def __init__(self, envelope: ExtractionEnvelope) -> None:
        self.envelope = envelope

    def extract(
        self,
        document_segment: str,
        *,
        fact_kind_allowlist: frozenset[str] | None = None,
        max_facts: int | None = None,
        source_profile: str | None = None,
    ) -> ExtractionResponse:
        del fact_kind_allowlist, max_facts, source_profile
        assert document_segment
        return ExtractionResponse(self.envelope, 25, 15)


@pytest.mark.integration
def test_governed_structure_publishes_rdkit_authority_and_rolls_back_entity_conflict(tmp_path: Path) -> None:
    admin_url = os.getenv("TEST_CHEMISTRY_ADMIN_DATABASE_URL")
    if not admin_url:
        pytest.skip("TEST_CHEMISTRY_ADMIN_DATABASE_URL is required")
    require_disposable_postgres_url(admin_url, "TEST_CHEMISTRY_ADMIN_DATABASE_URL")

    engine = create_engine(admin_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    store = FileSystemObjectStore(tmp_path / "objects")
    settings = Settings(
        ai_governance_enabled=True,
        ai_base_url="https://model.test",
        ai_api_key="test-key",
        ai_model="test-model",
        object_store_root=tmp_path / "objects",
        markdown_export_root=tmp_path / "wiki",
    )

    with Session(engine, expire_on_commit=False) as session:
        tenant = Tenant(id=tenant_id, slug=f"governed-chem-{tenant_id}", name="Governed Chemistry Test")
        source = DataSource(
            tenant_id=tenant_id,
            name="Governed Chemistry Source",
            source_type=DataSourceType.FOLDER,
            root_uri=str(tmp_path),
            owner="Research Operations",
            authorization_scopes=["contract:test-source"],
            dataset_key="chemistry",
        )
        reviewer = create_account(
            tenant_id=tenant_id,
            email=f"reviewer-{tenant_id}@example.test",
            normalized_email=f"reviewer-{tenant_id}@example.test",
            display_name="Chemistry Reviewer",
            password_hash=hash_password("governance-postgres-test-password"),
            role=UserRole.ANALYST,
        )
        session.add(tenant)
        session.flush()
        session.add_all([source, reviewer])
        session.flush()

        first_text = "Compound A has reported SMILES CCO. Invalid Compound has reported SMILES not-a-smiles."
        first_version = _source_version(session, store, tenant_id, source.id, "first.txt", first_text)
        second_text = "Compound B has reported SMILES CCO."
        second_version = _source_version(session, store, tenant_id, source.id, "second.txt", second_text)
        session.commit()

        compound_a = EntityReference(entity_type=EntityType.DRUG, name="Compound A")
        invalid_compound = EntityReference(entity_type=EntityType.DRUG, name="Invalid Compound")
        first_envelope = ExtractionEnvelope(
            document_type="chemistry_report",
            document_summary="Reported structures",
            facts=[
                StructureFact(
                    fact_kind="structure",
                    subject=compound_a,
                    canonical_smiles="CCO",
                    citation=Citation(quote="Compound A has reported SMILES CCO.", confidence=0.99),
                ),
                StructureFact(
                    fact_kind="structure",
                    subject=invalid_compound,
                    canonical_smiles="not-a-smiles",
                    citation=Citation(
                        quote="Invalid Compound has reported SMILES not-a-smiles.",
                        confidence=0.99,
                    ),
                ),
            ],
        )
        service = GovernanceService(
            session,
            settings,
            store,
            tenant_id,
            gateway=StaticStructureGateway(first_envelope),
        )
        first_result = service.govern_version(first_version.id)

        assert first_result["review_pending"] == 1
        assert first_result["rejected"] == 1
        valid_fact = session.scalar(
            select(StagedFact).where(
                StagedFact.extraction_run_id == first_result["run_id"],
                StagedFact.status == GovernanceStatus.REVIEW_PENDING,
            )
        )
        invalid_fact = session.scalar(
            select(StagedFact).where(
                StagedFact.extraction_run_id == first_result["run_id"],
                StagedFact.status == GovernanceStatus.REJECTED,
            )
        )
        assert valid_fact is not None
        assert invalid_fact is not None
        assert valid_fact.raw_payload["standard_inchi_key"] is None
        assert valid_fact.payload["standard_inchi_key"] == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
        assert invalid_fact.quality_findings[0]["code"] == "invalid_smiles"
        assert invalid_fact.normalization_version is None

        service.approve_fact(valid_fact.id, reviewer.id, "RDKit identifiers and source quote verified")
        structure = session.scalar(select(CompoundStructure).where(CompoundStructure.tenant_id == tenant_id))
        assert structure is not None
        assert structure.standard_inchi_key == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
        assert structure.molecular_formula == "C2H6O"
        materialized = session.execute(
            text(
                "SELECT rdkit_mol IS NOT NULL, morgan_bfp IS NOT NULL FROM compound_structures WHERE id = :structure_id"
            ),
            {"structure_id": structure.id},
        ).one()
        assert materialized == (True, True)

        second_envelope = ExtractionEnvelope(
            document_type="chemistry_report",
            document_summary="Conflicting entity assignment",
            facts=[
                StructureFact(
                    fact_kind="structure",
                    subject=EntityReference(entity_type=EntityType.DRUG, name="Compound B"),
                    canonical_smiles="CCO",
                    citation=Citation(quote=second_text, confidence=0.99),
                )
            ],
        )
        conflict_service = GovernanceService(
            session,
            settings,
            store,
            tenant_id,
            gateway=StaticStructureGateway(second_envelope),
        )
        second_result = conflict_service.govern_version(second_version.id)
        assert second_result["conflict"] == 1
        conflict_fact = session.scalar(
            select(StagedFact).where(StagedFact.extraction_run_id == second_result["run_id"])
        )
        assert conflict_fact is not None
        assert "structure_entity_conflict" in {item["code"] for item in conflict_fact.quality_findings}

        with pytest.raises(GovernanceError, match="another normalized entity"):
            conflict_service.approve_fact(conflict_fact.id, reviewer.id, "Investigated duplicate structure assignment")

        assert (
            session.scalar(
                select(func.count()).select_from(CompoundStructure).where(CompoundStructure.tenant_id == tenant_id)
            )
            == 1
        )
        assert (
            session.scalar(select(func.count()).select_from(EvidenceClaim).where(EvidenceClaim.tenant_id == tenant_id))
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Entity)
                .where(Entity.tenant_id == tenant_id, Entity.normalized_name == "compound b")
            )
            == 0
        )
        open_task = session.scalar(select(ReviewTask).where(ReviewTask.staged_fact_id == conflict_fact.id))
        assert open_task is not None
        assert open_task.status == GovernanceStatus.REVIEW_PENDING

    engine.dispose()


def _source_version(
    session: Session,
    store: FileSystemObjectStore,
    tenant_id: str,
    source_id: str,
    file_name: str,
    content: str,
) -> SourceVersion:
    data = content.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    stored = store.put_bytes(tenant_id, "extracted-text", data, digest, ".txt")
    asset = SourceAsset(
        tenant_id=tenant_id,
        data_source_id=source_id,
        logical_path=file_name,
        source_uri=file_name,
        file_name=file_name,
        extension=".txt",
        processing_mode="parse",
    )
    document = SourceDocument(
        tenant_id=tenant_id,
        title=file_name,
        source_type="folder",
        source_uri=file_name,
        content_sha256=digest,
    )
    session.add_all([asset, document])
    session.flush()
    version = SourceVersion(
        tenant_id=tenant_id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256=digest,
        size_bytes=len(data),
        snapshot_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.SUCCEEDED,
        extracted_text_object_uri=stored.uri,
        extracted_text_sha256=digest,
        source_document_id=document.id,
    )
    session.add(version)
    session.flush()
    return version
