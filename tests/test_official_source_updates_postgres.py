from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.governance import service as governance_module
from pharma_intel.governance.service import GovernanceService
from pharma_intel.governance.source_updates import lock_official_source_record
from pharma_intel.models import ClinicalTrialProfile, SourceVersion, Tenant
from pharma_intel.object_store import FileSystemObjectStore
from tests.support.postgres_safety import require_disposable_postgres_url
from tests.test_clinicaltrials_gov_deterministic_governance import _version
from tests.test_official_source_updates import _updated_version

pytestmark = pytest.mark.integration


def test_concurrent_old_snapshot_waits_then_cannot_overwrite_new_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = os.getenv("TEST_GOVERNANCE_PUBLICATION_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_GOVERNANCE_PUBLICATION_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_GOVERNANCE_PUBLICATION_DATABASE_URL")
    engine = create_engine(database_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    newer_locked = threading.Event()
    older_attempted = threading.Event()
    release_newer = threading.Event()
    try:
        with Session(engine, expire_on_commit=False) as session:
            set_tenant_context(session, tenant_id)
            tenant = Tenant(id=tenant_id, slug=f"official-update-test-{tenant_id}", name="Official update test")
            session.add(tenant)
            session.commit()
            store, older = _version(session, tenant, tmp_path)
            newer = _updated_version(session, store, older)
            older_id, newer_id = older.id, newer.id

        def controlled_lock(session: Session, version: SourceVersion) -> None:
            if version.id == older_id:
                older_attempted.set()
            lock_official_source_record(session, version)
            if version.id == newer_id:
                newer_locked.set()
                if not release_newer.wait(timeout=10):
                    raise RuntimeError("Newer publication release was not signaled")

        monkeypatch.setattr(governance_module, "lock_official_source_record", controlled_lock)

        def govern(version_id: str) -> dict[str, int | str]:
            with Session(engine, expire_on_commit=False) as session:
                set_tenant_context(session, tenant_id)
                session.execute(text("SET LOCAL lock_timeout = '15s'"))
                return GovernanceService(
                    session, Settings(), FileSystemObjectStore(store.root), tenant_id
                ).govern_version(version_id)

        with ThreadPoolExecutor(max_workers=2) as pool:
            newer_future = pool.submit(govern, newer_id)
            assert newer_locked.wait(timeout=10)
            older_future = pool.submit(govern, older_id)
            assert older_attempted.wait(timeout=10)
            assert not older_future.done()
            release_newer.set()
            assert newer_future.result(timeout=20)["published"] == 1
            assert older_future.result(timeout=20)["rejected"] == 1

        with Session(engine) as session:
            set_tenant_context(session, tenant_id)
            trial = session.scalar(select(ClinicalTrialProfile).where(ClinicalTrialProfile.tenant_id == tenant_id))
            assert trial is not None and trial.overall_status == "COMPLETED"
    finally:
        release_newer.set()
        engine.dispose()
