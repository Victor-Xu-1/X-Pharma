from __future__ import annotations

import os
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.governance import adapter_chembl
from pharma_intel.governance.chembl import ChemblRecord, parse_chembl_snapshot
from pharma_intel.governance.chembl_projection_maintenance import ChemblProjectionMaintenance
from pharma_intel.governance.service import GovernanceService
from pharma_intel.models import AuditEvent, DevelopmentProgram, SourceAsset, StagedFact, Tenant
from tests.support.postgres_safety import require_disposable_postgres_url
from tests.test_chembl_governance import _version


@pytest.mark.integration
def test_postgres_regional_repair_is_atomic_audited_and_tenant_scoped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = os.getenv("TEST_PROJECTION_MAINTENANCE_DATABASE_URL")
    if not value:
        pytest.skip("TEST_PROJECTION_MAINTENANCE_DATABASE_URL is not configured")
    engine = create_engine(require_disposable_postgres_url(value, "TEST_PROJECTION_MAINTENANCE_DATABASE_URL"))
    original = parse_chembl_snapshot

    def legacy_parser(raw: bytes) -> ChemblRecord:
        record = original(raw)
        return replace(record, fact=record.fact.model_copy(update={"global_phase": record.fact.phase}))

    # Seed a controlled legacy result before publication, without rewriting a
    # committed fact or changing the real parser outside this isolated fixture.
    monkeypatch.setattr(adapter_chembl, "parse_chembl_snapshot", legacy_parser)
    monkeypatch.setattr(adapter_chembl, "CHEMBL_ADAPTER_VERSION", "1.1.0")
    tenant_id, other_id = str(uuid.uuid4()), str(uuid.uuid4())
    with Session(engine) as session:
        set_tenant_context(session, tenant_id)
        role = session.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
        assert not role.rolsuper and not role.rolbypassrls
        tenant = Tenant(id=tenant_id, slug=f"projection-{tenant_id}", name="Controlled legacy fixture")
        session.add_all([tenant, Tenant(id=other_id, slug=f"projection-{other_id}", name="Independent fixture")])
        session.commit()
        set_tenant_context(session, tenant_id)
        store, version = _version(session, tenant, tmp_path)
        GovernanceService(session, Settings(), store, tenant_id).govern_version(version.id)
        set_tenant_context(session, tenant_id)
        program = session.scalar(select(DevelopmentProgram).where(DevelopmentProgram.tenant_id == tenant_id))
        asset = session.get(SourceAsset, version.source_asset_id)
        assert program and asset and program.global_phase == "approved"
        facts_before = list(session.scalars(select(StagedFact).where(StagedFact.tenant_id == tenant_id)))
        payloads = {fact.id: dict(fact.payload) for fact in facts_before}
        raw_before = store.read_bytes(version.raw_object_uri or "", 1_000_000)
        source_id = asset.data_source_id
        maintenance = ChemblProjectionMaintenance(session, store, tenant_id, source_id)
        plan = maintenance.preview()
        assert len(plan.changes) == 1
        result = maintenance.apply(plan.plan_sha256)
        assert result.changes_applied == 1
        set_tenant_context(session, tenant_id)
        assert (
            session.scalar(select(DevelopmentProgram.global_phase).where(DevelopmentProgram.id == program.id)) is None
        )
        facts_after = list(session.scalars(select(StagedFact).where(StagedFact.tenant_id == tenant_id)))
        assert {fact.id: fact.payload for fact in facts_after} == payloads
        assert store.read_bytes(version.raw_object_uri or "", 1_000_000) == raw_before
        audits = session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.tenant_id == tenant_id))
        assert maintenance.apply(plan.plan_sha256).replayed is True
        assert (
            session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.tenant_id == tenant_id))
            == audits
        )
        session.rollback()
        set_tenant_context(session, other_id)
        with pytest.raises(ValueError, match="source"):
            ChemblProjectionMaintenance(session, store, other_id, source_id).preview()
    engine.dispose()
