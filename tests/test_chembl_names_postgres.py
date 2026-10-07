from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.governance.service import GovernanceService
from pharma_intel.models import EntityAlias, EntityType, ReviewStatus, Tenant
from pharma_intel.search.service import EntitySearchService
from tests.support.postgres_safety import require_disposable_postgres_url
from tests.test_chembl_governance import _version
from tests.test_chembl_names import _named_snapshot


@pytest.mark.integration
def test_postgres_names_preserve_snapshots_and_respect_forced_tenant_isolation(tmp_path: Path) -> None:
    value = os.getenv("TEST_ENTITY_NAMES_DATABASE_URL")
    if not value:
        pytest.skip("TEST_ENTITY_NAMES_DATABASE_URL is not configured")
    engine = create_engine(require_disposable_postgres_url(value, "TEST_ENTITY_NAMES_DATABASE_URL"))
    tenant_id, other_id = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        with Session(engine) as session:
            set_tenant_context(session, tenant_id)
            role = session.execute(
                text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
            ).one()
            assert not role.rolsuper and not role.rolbypassrls
            tenant = Tenant(id=tenant_id, slug=f"names-{tenant_id}", name="Names fixture")
            session.add_all([tenant, Tenant(id=other_id, slug=f"names-{other_id}", name="Isolated names")])
            session.commit()
            store, version = _version(session, tenant, tmp_path, _named_snapshot())
            raw = store.read_bytes(version.raw_object_uri or "", 1_000_000)
            service = GovernanceService(session, Settings(), store, tenant_id)
            result = service.govern_version(version.id)
            assert result["published"] == 6
            assert service.govern_version(version.id)["run_id"] == result["run_id"]
            assert store.read_bytes(version.raw_object_uri or "", 1_000_000) == raw
            search = EntitySearchService(session, tenant_id, Settings(search_backend="database"))
            direct = search.search("ABX-EGF", EntityType.DRUG, 10, 0, ReviewStatus.VERIFIED)
            assert direct.total == 1 and direct.matches[direct.items[0].id].match_type == "alias"
            assert (
                search.search("ERBB1", EntityType.DRUG, 10, 0, ReviewStatus.VERIFIED, include_related=True).total == 1
            )
            session.rollback()
            set_tenant_context(session, other_id)
            assert list(session.scalars(select(EntityAlias))) == []
            assert (
                EntitySearchService(session, other_id, Settings(search_backend="database"))
                .search("ABX-EGF", None, 10, 0, ReviewStatus.VERIFIED)
                .total
                == 0
            )
    finally:
        engine.dispose()
