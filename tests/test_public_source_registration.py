from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.config import Settings
from pharma_intel.ingest import public_sources
from pharma_intel.models import AuditEvent, DataSource, Tenant


def test_public_registration_is_scoped_audited_and_idempotent(
    session: Session, tenant: Tenant, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(public_sources, "get_session_factory", lambda: factory)
    monkeypatch.setattr(public_sources, "get_settings", lambda: Settings(object_store_root=tmp_path))

    def register() -> DataSource:
        return public_sources.register_clinicaltrials_gov_source(
            tenant_slug=tenant.slug,
            query_term="configured query",
            max_records=5,
            page_size=5,
            sync_mode="continuous",
            start_date=date(2026, 7, 1),
        )

    first = register()
    repeated = register()
    assert first.id == repeated.id
    assert first.tenant_id == tenant.id
    assert first.routing_rules[0]["start_date"] == "2026-07-01"
    assert session.scalar(select(func.count()).select_from(DataSource)) == 1
    assert (
        session.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "data_source.public_registration")
        )
        == 1
    )


def test_public_registration_validates_before_any_database_write(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden_factory() -> None:
        pytest.fail("Invalid input must be rejected before database access")

    monkeypatch.setattr(public_sources, "get_session_factory", forbidden_factory)
    with pytest.raises(ValueError):
        public_sources.register_chembl_source(
            tenant_slug="never-used",
            target_chembl_id="https://untrusted.test",
            max_records=10,
            page_size=100,
        )
    with pytest.raises(ValueError):
        public_sources.register_clinicaltrials_gov_source(
            tenant_slug="never-used",
            query_term="query",
            max_records=10,
            page_size=1001,
        )


def test_chembl_topics_are_independent_and_existing_checkpoint_is_preserved(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(public_sources, "get_session_factory", lambda: factory)
    monkeypatch.setattr(public_sources, "get_settings", lambda: Settings(object_store_root=tmp_path))
    first = public_sources.register_chembl_source(
        tenant_slug=tenant.slug, target_chembl_id="CHEMBL203", max_records=5, page_size=5
    )
    old = session.get(DataSource, first.id)
    assert old is not None
    old.connector_cursor = {"retained-audit-marker": "checkpoint"}
    session.commit()
    second = public_sources.register_chembl_source(
        tenant_slug=tenant.slug, target_chembl_id="CHEMBL999", max_records=5, page_size=5
    )
    assert second.id != first.id and second.scope_digest != first.scope_digest
    session.refresh(old)
    assert old.connector_cursor == {"retained-audit-marker": "checkpoint"}
    repeated = public_sources.register_chembl_source(
        tenant_slug=tenant.slug, target_chembl_id="CHEMBL999", max_records=5, page_size=5
    )
    assert repeated.id == second.id
