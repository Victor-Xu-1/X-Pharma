from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.service import GovernanceService
from pharma_intel.ingest.data_factory import DataFactoryService, _requires_reprocessing
from pharma_intel.models import ExtractionRun, GovernanceStatus, StagedFact, StageStatus, Tenant
from tests.test_chembl_governance import _version as chembl_version
from tests.test_clinicaltrials_gov_deterministic_governance import _version as trial_version


@pytest.mark.parametrize("source_kind", ["chembl", "trial"])
def test_official_factory_governs_without_a_model(
    source_kind: Literal["chembl", "trial"], session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    store, version = (chembl_version if source_kind == "chembl" else trial_version)(session, tenant, tmp_path)
    settings = Settings(
        ai_governance_enabled=False,
        object_store_root=tmp_path / "objects",
        markdown_export_root=tmp_path / "wiki",
    )

    result = DataFactoryService(session, settings, store, tenant.id).process_version(version.id)

    assert result.governance_status == StageStatus.SUCCEEDED.value
    assert session.scalar(select(func.count()).select_from(ExtractionRun)) == 1
    facts = list(session.scalars(select(StagedFact)))
    assert facts and all(fact.status == GovernanceStatus.PUBLISHED for fact in facts)
    assert not _requires_reprocessing(session, version, settings=settings, include_snapshot=False)


@pytest.mark.parametrize("source_kind", ["chembl", "trial"])
def test_successful_official_policy_is_not_requeued_by_model_configuration(
    source_kind: Literal["chembl", "trial"], session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    store, version = (chembl_version if source_kind == "chembl" else trial_version)(session, tenant, tmp_path)
    settings = Settings(
        ai_governance_enabled=True,
        ai_base_url="https://unused-model.example.test",
        ai_api_key="unused-contract-placeholder",
        ai_model="unused-model",
    )
    GovernanceService(session, settings, store, tenant.id).govern_version(version.id)

    assert not _requires_reprocessing(session, version, settings=settings, include_snapshot=False)
    changed_model = settings.model_copy(update={"ai_model": "another-unused-model"})
    assert not _requires_reprocessing(session, version, settings=changed_model, include_snapshot=False)
