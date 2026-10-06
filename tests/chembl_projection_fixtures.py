from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.service import GovernanceService
from pharma_intel.models import (
    DevelopmentProgram,
    ExtractionRun,
    FactProvenanceLink,
    SourceAsset,
    SourceDocument,
    SourceVersion,
    SourceVersionState,
    StagedFact,
    StageStatus,
    Tenant,
)
from pharma_intel.object_store import FileSystemObjectStore
from tests.test_chembl_governance import _version


class LegacyProjectionFixture(NamedTuple):
    store: FileSystemObjectStore
    version: SourceVersion
    source_id: str
    program: DevelopmentProgram
    fact: StagedFact


def legacy_projection_fixture(session: Session, tenant: Tenant, tmp_path: Path) -> LegacyProjectionFixture:
    store, version = _version(session, tenant, tmp_path)
    first = GovernanceService(session, Settings(), store, tenant.id).govern_version(version.id)
    program = session.scalar(select(DevelopmentProgram))
    fact = session.scalar(select(StagedFact).where(StagedFact.fact_kind == "program"))
    run = session.get(ExtractionRun, first["run_id"])
    asset = session.get(SourceAsset, version.source_asset_id)
    assert program and fact and run and asset
    run.model_name = "chembl_mechanism_json:1.1.0"
    fact.payload = {**fact.payload, "global_phase": program.phase.value}
    program.global_phase = program.phase.value
    session.commit()
    return LegacyProjectionFixture(store, version, asset.data_source_id, program, fact)


def add_merged_legacy_mechanism(session: Session, tenant: Tenant, fixture: LegacyProjectionFixture) -> StagedFact:
    previous_payload = dict(fixture.fact.payload)
    previous_global_phase = fixture.program.global_phase
    # Build both validated projections before reproducing the legacy merge.
    # A new published record must not bypass a genuine current conflict.
    fixture.fact.payload = {**fixture.fact.payload, "global_phase": None}
    fixture.program.global_phase = None
    session.commit()
    payload = json.loads(fixture.store.read_bytes(fixture.version.raw_object_uri or "", 1_000_000))
    payload["mechanism"]["mec_id"] = 242
    payload["citation"] = {"locator": "mechanism:242", "quote": "Controlled legacy second mechanism"}
    uri = "https://www.ebi.ac.uk/chembl/api/data/mechanism.json?mec_id=242"
    payload["source"]["mechanism_uri"] = uri
    raw = json.dumps(payload).encode()
    digest = hashlib.sha256(raw).hexdigest()
    stored = fixture.store.put_bytes(tenant.id, "raw", raw, digest, ".json")
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=fixture.source_id,
        logical_path="mechanisms/242.json",
        source_uri=uri,
        file_name="242.json",
        extension=".json",
        processing_mode="parse",
    )
    document = SourceDocument(
        tenant_id=tenant.id,
        title="Controlled legacy second mechanism",
        source_type="chembl",
        source_uri=uri,
        content_sha256=digest,
    )
    session.add_all([asset, document])
    session.flush()
    version = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        source_document_id=document.id,
        version_number=1,
        content_sha256=digest,
        size_bytes=len(raw),
        raw_object_uri=stored.uri,
        extracted_text_object_uri=stored.uri,
        extracted_text_sha256=digest,
        snapshot_status=StageStatus.SUCCEEDED,
        malware_scan_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.SUCCEEDED,
        state=SourceVersionState.PARSED,
    )
    session.add(version)
    session.flush()
    asset.current_version_id = version.id
    session.commit()
    result = GovernanceService(session, Settings(), fixture.store, tenant.id).govern_version(version.id)
    run = session.get(ExtractionRun, result["run_id"])
    fact = session.scalar(
        select(StagedFact).where(StagedFact.extraction_run_id == result["run_id"], StagedFact.fact_kind == "program")
    )
    assert run and fact
    link = session.scalar(
        select(FactProvenanceLink).where(
            FactProvenanceLink.staged_fact_id == fact.id, FactProvenanceLink.resource_type == "development_program"
        )
    )
    assert link
    # Controlled fixture reproduces the old merged-record projection. Production
    # writes still go through governance; this setup never touches live data.
    run.model_name = "chembl_mechanism_json:1.1.0"
    fact.payload = {**fact.payload, "global_phase": "approved"}
    link.resource_id = fixture.program.id
    fixture.fact.payload = previous_payload
    fixture.program.global_phase = previous_global_phase
    session.commit()
    return fact
