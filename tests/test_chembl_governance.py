from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.chembl import ADAPTER_VERSION, reconcile_chembl_target_links
from pharma_intel.governance.service import GovernanceService
from pharma_intel.models import (
    DataSource,
    DataSourceType,
    DevelopmentPhase,
    DevelopmentProgram,
    DevelopmentProgramTarget,
    Entity,
    EntityAlias,
    EntityType,
    ExtractionRun,
    GovernanceStatus,
    ProgramTargetRole,
    ReviewStatus,
    SourceAsset,
    SourceDocument,
    SourceVersion,
    SourceVersionState,
    StagedFact,
    StageStatus,
    TargetProfile,
    Tenant,
)
from pharma_intel.object_store import FileSystemObjectStore


def _snapshot() -> bytes:
    payload = {
        "schema_version": "pharma.chembl.mechanism.v1",
        "provider": "ChEMBL",
        "target": {
            "chembl_id": "CHEMBL203",
            "pref_name": "Epidermal growth factor receptor",
            "target_type": "SINGLE PROTEIN",
            "organism": "Homo sapiens",
            "gene_symbol": "EGFR",
            "uniprot_accession": "P00533",
        },
        "molecule": {
            "chembl_id": "CHEMBL1201827",
            "pref_name": "PANITUMUMAB",
            "molecule_type": "Antibody",
            "max_phase": 4.0,
        },
        "mechanism": {
            "mec_id": 241,
            "target_chembl_id": "CHEMBL203",
            "molecule_chembl_id": "CHEMBL1201827",
            "action_type": "INHIBITOR",
            "mechanism_of_action": "Epidermal growth factor receptor erbB1 inhibitor",
            "max_phase": 4,
            "direct_interaction": 1,
            "molecular_mechanism": 1,
            "mechanism_refs": [],
        },
        "citation": {
            "locator": "mechanism:241",
            "quote": (
                "mec_id=241; target_chembl_id=CHEMBL203; "
                "molecule_chembl_id=CHEMBL1201827; max_phase=4; "
                "mechanism_of_action=Epidermal growth factor receptor erbB1 inhibitor"
            ),
        },
        "source": {
            "api_root": "https://www.ebi.ac.uk/chembl/api/data/",
            "mechanism_uri": "https://www.ebi.ac.uk/chembl/api/data/mechanism.json?mec_id=241",
            "molecule_uri": "https://www.ebi.ac.uk/chembl/api/data/molecule/CHEMBL1201827.json",
            "target_uri": "https://www.ebi.ac.uk/chembl/api/data/target/CHEMBL203.json",
            "license": "CC BY-SA 3.0",
            "license_uri": "https://www.ebi.ac.uk/chembl/",
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _version(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> tuple[FileSystemObjectStore, SourceVersion]:
    store = FileSystemObjectStore(tmp_path / "objects")
    content = _snapshot()
    digest = hashlib.sha256(content).hexdigest()
    raw = store.put_bytes(tenant.id, "raw", content, digest, ".json")
    extracted = b"chembl snapshot"
    extracted_digest = hashlib.sha256(extracted).hexdigest()
    extracted_object = store.put_bytes(tenant.id, "extracted-text", extracted, extracted_digest, ".txt")
    source = DataSource(
        tenant_id=tenant.id,
        name="ChEMBL EGFR",
        source_type=DataSourceType.CHEMBL,
        root_uri="https://www.ebi.ac.uk/chembl/api/data/",
        owner="Public Biomedical Data Operations",
        data_classification="public",
        authorization_scopes=["public:chembl"],
        dataset_key="chembl",
        include_globs=["mechanisms/*.json"],
        exclude_globs=[],
        routing_rules=[{"target_chembl_id": "CHEMBL203", "max_records": 1, "page_size": 1}],
        stable_seconds=0,
        max_file_bytes=1_000_000,
        scan_interval_seconds=86_400,
        expected_freshness_seconds=604_800,
        rate_limit_per_minute=30,
    )
    session.add(source)
    session.flush()
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="mechanisms/CHEMBL203/241.json",
        source_uri="https://www.ebi.ac.uk/chembl/api/data/mechanism.json?mec_id=241",
        file_name="241.json",
        extension=".json",
        processing_mode="parse",
    )
    session.add(asset)
    session.flush()
    document = SourceDocument(
        tenant_id=tenant.id,
        title="241.json",
        source_type="chembl",
        source_uri=asset.source_uri,
        content_sha256=digest,
    )
    session.add(document)
    session.flush()
    version = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256=digest,
        size_bytes=len(content),
        snapshot_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.SUCCEEDED,
        raw_object_uri=raw.uri,
        extracted_text_object_uri=extracted_object.uri,
        extracted_text_sha256=extracted_digest,
        source_document_id=document.id,
        state=SourceVersionState.PARSED,
    )
    session.add(version)
    session.commit()
    return store, version


def test_authorized_chembl_governance_publishes_an_idempotent_program_with_citation(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    store, version = _version(session, tenant, tmp_path)
    service = GovernanceService(
        session,
        Settings(
            ai_governance_enabled=True,
            ai_base_url="https://model.test",
            ai_api_key="must-not-be-called",
            ai_model="must-not-be-called",
            object_store_root=tmp_path / "objects",
        ),
        store,
        tenant.id,
    )

    first = service.govern_version(version.id)
    repeated = service.govern_version(version.id)

    assert first["run_id"] == repeated["run_id"]
    assert first["fact_count"] == 2
    assert first["published"] == 2
    assert first["review_pending"] == first["rejected"] == first["conflict"] == 0
    assert session.scalar(select(func.count()).select_from(DevelopmentProgram)) == 1
    program = session.scalar(select(DevelopmentProgram))
    assert program is not None
    assert program.program_tags == []
    assert program.modality == "Antibody"
    assert program.drug_category == "biologic"
    target = session.scalar(select(Entity).where(Entity.entity_type == EntityType.TARGET))
    assert target is not None
    assert target.name == "Epidermal growth factor receptor"
    assert target.external_ids["chembl"] == "CHEMBL203"
    assert (
        session.scalar(
            select(EntityAlias.id).where(
                EntityAlias.entity_id == target.id,
                EntityAlias.normalized_alias == "egfr",
            )
        )
        is not None
    )
    profile = session.scalar(select(TargetProfile).where(TargetProfile.entity_id == target.id))
    assert profile is not None
    assert profile.gene_symbol == "EGFR"
    assert profile.uniprot_accession == "P00533"
    staged_facts = list(session.scalars(select(StagedFact)))
    assert len(staged_facts) == 2
    assert all(staged.status == GovernanceStatus.PUBLISHED for staged in staged_facts)
    program_staged = next(staged for staged in staged_facts if staged.source_locator == "mechanism:241")
    profile_staged = next(staged for staged in staged_facts if staged.source_locator == "target:CHEMBL203")
    assert "molecule_chembl_id=CHEMBL1201827" in program_staged.source_quote
    assert "gene_symbol=EGFR" in profile_staged.source_quote
    run = session.get(ExtractionRun, first["run_id"])
    assert run is not None
    assert run.model_provider == "deterministic-adapter"
    assert run.model_name == f"chembl_mechanism_json:{ADAPTER_VERSION}"
    assert run.structured_output is not None
    assert run.structured_output["deterministic_adapter"]["mechanism_id"] == 241
    assert version.state == SourceVersionState.PUBLISHED


def test_chembl_identity_reconciliation_remaps_program_relationships_idempotently(
    session: Session,
    tenant: Tenant,
) -> None:
    canonical = Entity(
        tenant_id=tenant.id,
        entity_type=EntityType.TARGET,
        name="Epidermal growth factor receptor",
        normalized_name="epidermal growth factor receptor",
        external_ids={"chembl": "CHEMBL203"},
        review_status=ReviewStatus.VERIFIED,
    )
    duplicate = Entity(
        tenant_id=tenant.id,
        entity_type=EntityType.TARGET,
        name="Epidermal growth factor receptor",
        normalized_name="epidermal growth factor receptor",
        external_ids={"chembl": "CHEMBL203"},
        review_status=ReviewStatus.DRAFT,
    )
    drug = Entity(
        tenant_id=tenant.id,
        entity_type=EntityType.DRUG,
        name="ChEMBL test drug",
        normalized_name="chembl test drug",
        review_status=ReviewStatus.VERIFIED,
    )
    session.add_all([canonical, duplicate, drug])
    session.flush()
    program = DevelopmentProgram(
        tenant_id=tenant.id,
        drug_entity_id=drug.id,
        target_entity_id=duplicate.id,
        phase=DevelopmentPhase.PHASE_2,
    )
    session.add(program)
    session.flush()
    program_target = DevelopmentProgramTarget(
        tenant_id=tenant.id,
        program_id=program.id,
        target_set_version=1,
        target_entity_id=duplicate.id,
        role=ProgramTargetRole.PRIMARY,
        position=0,
    )
    session.add(program_target)
    session.commit()

    first = reconcile_chembl_target_links(
        session,
        tenant_id=tenant.id,
        chembl_id="chembl203",
        canonical_entity_id=canonical.id,
    )
    session.commit()

    assert first.duplicate_entity_ids == (duplicate.id,)
    assert first.remapped_programs == 1
    assert first.remapped_program_targets == 1
    persisted_program = session.get(DevelopmentProgram, program.id)
    assert persisted_program is not None
    assert persisted_program.target_entity_id == canonical.id
    assert persisted_program.target_set_version == 2
    current_target = session.scalar(
        select(DevelopmentProgramTarget).where(
            DevelopmentProgramTarget.program_id == program.id,
            DevelopmentProgramTarget.target_set_version == 2,
        )
    )
    assert current_target is not None
    assert current_target.target_entity_id == canonical.id
    previous_target = session.get(DevelopmentProgramTarget, program_target.id)
    assert previous_target is not None
    assert previous_target.target_entity_id == duplicate.id

    repeated = reconcile_chembl_target_links(
        session,
        tenant_id=tenant.id,
        chembl_id="CHEMBL203",
        canonical_entity_id=canonical.id,
    )
    assert repeated.remapped_programs == repeated.remapped_program_targets == 0
