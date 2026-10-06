from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.chembl_program_identity import native_chembl_program
from pharma_intel.governance.chembl_projection_maintenance import ChemblProjectionMaintenance
from pharma_intel.governance.contracts import GovernanceError
from pharma_intel.governance.service import GovernanceService
from pharma_intel.models import (
    AuditEvent,
    DataSource,
    ExtractionRun,
    GovernanceStatus,
    OutboxEvent,
    ReviewTask,
    Tenant,
)
from tests.chembl_projection_fixtures import add_merged_legacy_mechanism
from tests.chembl_projection_fixtures import legacy_projection_fixture as _legacy


def test_preview_is_read_only_and_apply_preserves_fact_evidence_with_audited_idempotency(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    store, version, source_id, program, fact = _legacy(session, tenant, tmp_path)
    before_payload = dict(fact.payload)
    before_raw = store.read_bytes(version.raw_object_uri or "", 1_000_000)
    before_audits = session.scalar(select(func.count()).select_from(AuditEvent))
    before_events = session.scalar(select(func.count()).select_from(OutboxEvent))
    service = ChemblProjectionMaintenance(session, store, tenant.id, source_id)
    plan = service.preview()
    assert len(plan.changes) == 1 and program.global_phase == "approved"
    assert session.scalar(select(func.count()).select_from(AuditEvent)) == before_audits
    result = service.apply(plan.plan_sha256)
    session.refresh(program)
    session.refresh(fact)
    assert result.changes_applied == 1 and program.global_phase is None
    assert fact.payload == before_payload and store.read_bytes(version.raw_object_uri or "", 1_000_000) == before_raw
    assert session.scalar(select(func.count()).select_from(AuditEvent)) == (before_audits or 0) + 1
    assert session.scalar(select(func.count()).select_from(OutboxEvent)) == (before_events or 0) + 1
    assert service.apply(plan.plan_sha256).replayed is True
    assert service.preview().changes == []


@pytest.mark.parametrize("boundary", ["dated", "china", "human", "unrecognized_adapter", "checksum"])
def test_preserves_any_unproven_regional_evidence(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    boundary: str,
) -> None:
    store, version, source_id, program, fact = _legacy(session, tenant, tmp_path)
    if boundary == "dated":
        program.global_phase_started_at = datetime(2026, 1, 1, tzinfo=UTC)
    elif boundary == "china":
        program.china_phase = "phase_2"
    elif boundary == "human":
        session.add(
            ReviewTask(
                tenant_id=tenant.id,
                staged_fact_id=fact.id,
                status=GovernanceStatus.APPROVED,
                decided_at=datetime.now(UTC),
            )
        )
    elif boundary == "unrecognized_adapter":
        run = session.get(ExtractionRun, fact.extraction_run_id)
        assert run
        run.model_name = "chembl_mechanism_json:9.0.0"
    else:
        version.content_sha256 = "0" * 64
    session.commit()
    plan = ChemblProjectionMaintenance(session, store, tenant.id, source_id).preview()
    assert plan.changes == [] and program.id in plan.blocked
    assert program.global_phase == "approved"
    result = ChemblProjectionMaintenance(session, store, tenant.id, source_id).apply(plan.plan_sha256)
    assert result.status == "no_changes" and result.changes_applied == 0 and program.id in result.blocked


def test_stale_plan_refuses_all_writes(session: Session, tenant: Tenant, tmp_path: Path) -> None:
    store, _, source_id, program, _ = _legacy(session, tenant, tmp_path)
    service = ChemblProjectionMaintenance(session, store, tenant.id, source_id)
    plan = service.preview()
    source = session.get(DataSource, source_id)
    assert source
    source.config_version += 1
    session.commit()
    with pytest.raises(ValueError, match="changed"):
        service.apply(plan.plan_sha256)
    session.refresh(program)
    assert program.global_phase == "approved"


def test_cross_tenant_source_is_not_operable(session: Session, tenant: Tenant, tmp_path: Path) -> None:
    store, _, source_id, program, _ = _legacy(session, tenant, tmp_path)
    other = Tenant(name="Independent fixture", slug="independent-phase-repair")
    session.add(other)
    session.commit()
    with pytest.raises(ValueError, match="source"):
        ChemblProjectionMaintenance(session, store, other.id, source_id).preview()
    assert program.global_phase == "approved"


def test_merged_mechanism_copy_can_be_repaired_without_resolving_identity(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    fixture = _legacy(session, tenant, tmp_path)
    second_fact = add_merged_legacy_mechanism(session, tenant, fixture)
    target_before = (fixture.program.target_entity_id, fixture.program.target_set_version)
    maintenance = ChemblProjectionMaintenance(session, fixture.store, tenant.id, fixture.source_id)
    plan = maintenance.preview()
    assert len(plan.changes) == 1 and len(plan.changes[0].evidence) == 2
    assert maintenance.apply(plan.plan_sha256).changes_applied == 1
    session.refresh(fixture.program)
    session.refresh(second_fact)
    assert fixture.program.global_phase is None
    assert (fixture.program.target_entity_id, fixture.program.target_set_version) == target_before
    assert second_fact.payload["global_phase"] == "approved" and second_fact.status == GovernanceStatus.PUBLISHED
    with pytest.raises(GovernanceError, match="Multiple source records"):
        native_chembl_program(GovernanceService(session, Settings(), fixture.store, tenant.id), fixture.fact)


def test_commit_failure_rolls_back_projection_and_audit(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, source_id, program, _ = _legacy(session, tenant, tmp_path)
    maintenance = ChemblProjectionMaintenance(session, store, tenant.id, source_id)
    plan = maintenance.preview()
    audits_before = session.scalar(select(func.count()).select_from(AuditEvent))
    events_before = session.scalar(select(func.count()).select_from(OutboxEvent))

    def refuse_commit() -> None:
        session.flush()
        raise SQLAlchemyError("Controlled commit refusal")

    monkeypatch.setattr(session, "commit", refuse_commit)
    with pytest.raises(SQLAlchemyError, match="Controlled"):
        maintenance.apply(plan.plan_sha256)
    session.refresh(program)
    assert program.global_phase == "approved"
    assert session.scalar(select(func.count()).select_from(AuditEvent)) == audits_before
    assert session.scalar(select(func.count()).select_from(OutboxEvent)) == events_before
