from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.service import GovernanceService
from pharma_intel.models import DevelopmentProgram, ExtractionRun, StagedFact, Tenant
from tests.test_chembl_governance import _version
from tests.test_official_source_updates import _updated_version


@pytest.mark.parametrize("independent_regional_evidence", [False, True])
def test_official_replay_repairs_only_proven_legacy_regional_inference(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    independent_regional_evidence: bool,
) -> None:
    store, older = _version(session, tenant, tmp_path)
    service = GovernanceService(session, Settings(), store, tenant.id)
    first = service.govern_version(older.id)
    program = session.scalar(select(DevelopmentProgram))
    previous = session.scalar(select(StagedFact).where(StagedFact.fact_kind == "program"))
    run = session.get(ExtractionRun, first["run_id"])
    assert program is not None and previous is not None and run is not None
    run.model_name = "chembl_mechanism_json:1.1.0"
    previous.payload = {**previous.payload, "global_phase": "approved"}
    program.global_phase = "approved"
    if independent_regional_evidence:
        previous.payload = {**previous.payload, "china_phase": "phase_2"}
        program.china_phase = "phase_2"
    session.commit()
    newer = _updated_version(session, store, older)
    service.govern_version(newer.id)
    session.refresh(program)
    session.refresh(previous)
    assert program.global_phase == ("approved" if independent_regional_evidence else None)
    assert previous.payload["global_phase"] == "approved"  # Historical candidate remains intact.
    assert store.read_bytes(older.raw_object_uri or "", 1_000_000)
