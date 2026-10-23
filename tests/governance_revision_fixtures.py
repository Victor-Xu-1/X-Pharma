from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.service import GovernanceService
from pharma_intel.models import ExtractionRun, SourceDocument, SourceVersion, StagedFact, Tenant
from pharma_intel.object_store import FileSystemObjectStore
from tests.test_chembl_governance import _snapshot, _version


def published_official_revision(
    session: Session, tenant: Tenant, tmp_path: Path, *, same_document: bool = False
) -> tuple[FileSystemObjectStore, Settings, list[StagedFact], list[StagedFact]]:
    store, first = _version(session, tenant, tmp_path)
    settings = Settings(object_store_root=tmp_path / "objects", markdown_export_root=tmp_path / "wiki")
    service = GovernanceService(session, settings, store, tenant.id)
    service.govern_version(first.id)
    old_facts = list(session.scalars(select(StagedFact)))
    assert old_facts
    content = _snapshot()
    document_id = first.source_document_id
    if not same_document:
        payload = json.loads(content)
        payload["molecule"]["max_phase"] = 3
        payload["mechanism"]["max_phase"] = 3
        payload["citation"]["quote"] = payload["citation"]["quote"].replace("max_phase=4", "max_phase=3")
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        source = session.get(SourceDocument, document_id)
        assert source is not None
        document = SourceDocument(
            tenant_id=tenant.id,
            title=source.title,
            source_type=source.source_type,
            source_uri=source.source_uri,
            content_sha256=hashlib.sha256(content).hexdigest(),
        )
        session.add(document)
        session.flush()
        document_id = document.id
    digest = hashlib.sha256(content).hexdigest()
    raw = store.put_bytes(tenant.id, "raw", content, digest, ".json")
    second = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=first.source_asset_id,
        version_number=2,
        content_sha256=digest,
        size_bytes=len(content),
        raw_object_uri=raw.uri,
        snapshot_status=first.snapshot_status,
        parse_status=first.parse_status,
        extracted_text_object_uri=first.extracted_text_object_uri,
        extracted_text_sha256=first.extracted_text_sha256,
        source_document_id=document_id,
        state=first.state,
    )
    session.add(second)
    session.commit()
    service.govern_version(second.id)
    new_facts = list(
        session.scalars(
            select(StagedFact)
            .join(ExtractionRun, ExtractionRun.id == StagedFact.extraction_run_id)
            .where(ExtractionRun.source_version_id == second.id)
        )
    )
    assert new_facts
    return store, settings, old_facts, new_facts
