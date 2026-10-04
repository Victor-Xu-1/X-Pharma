from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.service import GovernanceService
from pharma_intel.models import GovernanceStatus, SourceVersion, SourceVersionState, StagedFact, StageStatus, Tenant
from pharma_intel.object_store import FileSystemObjectStore
from tests.test_chembl_governance import _version as chembl_version
from tests.test_clinicaltrials_gov_deterministic_governance import _version as trial_version


def _updated_version(session: Session, store: FileSystemObjectStore, older: SourceVersion) -> SourceVersion:
    assert older.raw_object_uri is not None
    payload = json.loads(store.read_bytes(older.raw_object_uri, 1_000_000))
    if "protocolSection" in payload:
        payload["protocolSection"]["statusModule"]["overallStatus"] = "COMPLETED"
    else:
        payload["mechanism"]["max_phase"] = 3
        payload["molecule"]["max_phase"] = 3
        payload["citation"]["quote"] = payload["citation"]["quote"].replace("max_phase=4", "max_phase=3")
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(content).hexdigest()
    raw = store.put_bytes(older.tenant_id, "raw", content, digest, ".json")
    extracted = store.put_bytes(older.tenant_id, "extracted-text", content, digest, ".txt")
    newer = SourceVersion(
        tenant_id=older.tenant_id,
        source_asset_id=older.source_asset_id,
        source_document_id=older.source_document_id,
        version_number=2,
        content_sha256=digest,
        size_bytes=len(content),
        snapshot_status=StageStatus.SUCCEEDED,
        malware_scan_status=StageStatus.SKIPPED,
        parse_status=StageStatus.SUCCEEDED,
        raw_object_uri=raw.uri,
        extracted_text_object_uri=extracted.uri,
        extracted_text_sha256=digest,
        state=SourceVersionState.PARSED,
    )
    session.add(newer)
    session.commit()
    return newer


@pytest.mark.parametrize("source_kind", ["chembl", "trial"])
def test_newer_same_record_replaces_only_its_own_official_fact(
    source_kind: Literal["chembl", "trial"], session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    store, older = (chembl_version if source_kind == "chembl" else trial_version)(session, tenant, tmp_path)
    service = GovernanceService(session, Settings(), store, tenant.id)
    service.govern_version(older.id)
    original = list(session.scalars(select(StagedFact)))
    newer = _updated_version(session, store, older)

    result = service.govern_version(newer.id)

    assert int(result["published"]) >= 1
    assert result["conflict"] == 0
    assert any(fact.status == GovernanceStatus.WITHDRAWN for fact in original)
    assert store.read_bytes(older.raw_object_uri or "", 1_000_000) != store.read_bytes(
        newer.raw_object_uri or "", 1_000_000
    )


@pytest.mark.parametrize("source_kind", ["chembl", "trial"])
def test_late_old_snapshot_cannot_replace_a_newer_published_record(
    source_kind: Literal["chembl", "trial"], session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    store, older = (chembl_version if source_kind == "chembl" else trial_version)(session, tenant, tmp_path)
    newer = _updated_version(session, store, older)
    service = GovernanceService(session, Settings(), store, tenant.id)
    service.govern_version(newer.id)

    result = service.govern_version(older.id)

    assert int(result["rejected"]) >= 1
    assert result["conflict"] == 0
