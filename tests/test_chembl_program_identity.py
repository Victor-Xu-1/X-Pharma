from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.service import GovernanceService
from pharma_intel.ingest.source_routing import source_scope_digest
from pharma_intel.models import (
    DataSource,
    DataSourceType,
    DevelopmentProgram,
    DevelopmentProgramTarget,
    SourceAsset,
    SourceDocument,
    SourceVersion,
    SourceVersionState,
    StageStatus,
    Tenant,
)
from tests.test_chembl_governance import _version


def test_independent_chembl_mechanisms_do_not_replace_each_others_current_targets(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    store, first = _version(session, tenant, tmp_path)
    service = GovernanceService(session, Settings(), store, tenant.id)
    service.govern_version(first.id)
    payload = json.loads(store.read_bytes(first.raw_object_uri or "", 1_000_000))
    payload["target"].update(
        chembl_id="CHEMBL999", pref_name="Controlled second target", gene_symbol=None, uniprot_accession=None
    )
    payload["mechanism"].update(
        mec_id=942, target_chembl_id="CHEMBL999", mechanism_of_action="Controlled second mechanism"
    )
    payload["citation"] = {"locator": "mechanism:942", "quote": "Controlled second mechanism fixture"}
    content = json.dumps(payload).encode()
    digest = hashlib.sha256(content).hexdigest()
    raw = store.put_bytes(tenant.id, "raw", content, digest, ".json")
    rule = [{"target_chembl_id": "CHEMBL999", "max_records": 1, "page_size": 1}]
    source = DataSource(
        tenant_id=tenant.id,
        name="Second target fixture",
        source_type=DataSourceType.CHEMBL,
        root_uri="https://www.ebi.ac.uk/chembl/api/data/",
        scope_digest=source_scope_digest(DataSourceType.CHEMBL, rule),
        routing_rules=rule,
        owner="Test",
        data_classification="public",
        dataset_key="chembl",
        authorization_scopes=["public:chembl"],
        stable_seconds=0,
        max_file_bytes=1_000_000,
    )
    session.add(source)
    session.flush()
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="mechanisms/CHEMBL999/942.json",
        source_uri="https://www.ebi.ac.uk/chembl/api/data/mechanism.json?mec_id=942",
        file_name="942.json",
        extension=".json",
        processing_mode="parse",
    )
    document = SourceDocument(
        tenant_id=tenant.id,
        title="Second mechanism fixture",
        source_type="chembl",
        source_uri=asset.source_uri,
        content_sha256=digest,
    )
    session.add_all([asset, document])
    session.flush()
    second = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        source_document_id=document.id,
        version_number=1,
        content_sha256=digest,
        size_bytes=len(content),
        raw_object_uri=raw.uri,
        extracted_text_object_uri=raw.uri,
        extracted_text_sha256=digest,
        parse_status=StageStatus.SUCCEEDED,
        snapshot_status=StageStatus.SUCCEEDED,
        state=SourceVersionState.PARSED,
    )
    session.add(second)
    session.commit()
    service.govern_version(second.id)
    assert session.scalar(select(func.count()).select_from(DevelopmentProgram)) == 2
    programs = list(session.scalars(select(DevelopmentProgram)))
    assert len({program.target_entity_id for program in programs}) == 2
    assert (
        session.scalar(
            select(func.count())
            .select_from(DevelopmentProgramTarget)
            .where(DevelopmentProgramTarget.target_set_version == 1)
        )
        == 2
    )
