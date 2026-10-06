from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.models import ExtractionRun, GovernanceStatus, StagedFact, Tenant
from pharma_intel.security import Principal, require_principal
from tests.test_chembl_governance import _version


def test_comparison_resolves_prior_values_and_origin_without_other_tenant_reads(
    session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    _, version = _version(session, tenant, tmp_path)
    run = ExtractionRun(
        tenant_id=tenant.id,
        source_version_id=version.id,
        schema_name="test",
        schema_version="1",
        model_provider="deterministic-adapter",
        model_name="chembl_mechanism_json:1.3.0",
        input_sha256="a" * 64,
        prompt_sha256="b" * 64,
        policy_sha256="c" * 64,
    )
    session.add(run)
    session.flush()
    prior = StagedFact(
        tenant_id=tenant.id,
        extraction_run_id=run.id,
        fact_kind="program",
        fact_key="prior",
        raw_payload={"phase": "phase_2"},
        payload={"phase": "phase_2"},
        source_quote="max_phase=2",
        confidence=1,
        status=GovernanceStatus.PUBLISHED,
    )
    session.add(prior)
    session.flush()
    current = StagedFact(
        tenant_id=tenant.id,
        extraction_run_id=run.id,
        fact_kind="program",
        fact_key="current",
        raw_payload={"phase": "phase_3"},
        payload={"phase": "phase_3"},
        source_quote="max_phase=3",
        confidence=1,
        status=GovernanceStatus.CONFLICT,
        conflict_with_ids=[prior.id, "not-available"],
    )
    session.add(current)
    session.commit()

    def override_session() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id, "reviewer", "user", frozenset({"governance:read"})
    )
    path = f"/api/v1/governance/staged-facts/{current.id}/comparison"
    try:
        with TestClient(app) as client:
            response = client.get(path)
            assert response.status_code == 200
            data = response.json()
            assert data["fact"]["payload"]["phase"] == "phase_3"
            assert data["origin"]["model_provider"] == "deterministic-adapter"
            assert data["origin"]["source_version_number"] == 1
            assert data["conflicts"][0]["fact"]["payload"]["phase"] == "phase_2"
            assert data["conflict_total"] == 2
            assert data["unavailable_conflicts"] == 1
            assert "raw_object_uri" not in response.text
            assert "credential_ref" not in response.text
            app.dependency_overrides[require_principal] = lambda: Principal(tenant.id, "reader", "user", frozenset())
            assert client.get(path).status_code == 403
            app.dependency_overrides[require_principal] = lambda: Principal(
                "other-tenant", "reviewer", "user", frozenset({"governance:read"})
            )
            assert client.get(path).status_code == 404
    finally:
        app.dependency_overrides.clear()
