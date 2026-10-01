from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.api import app
from pharma_intel.config import Settings
from pharma_intel.db import get_session
from pharma_intel.models import DataQualityIssue, Tenant, UserRole
from pharma_intel.quality.service import DataQualityService
from pharma_intel.security import Principal, require_principal
from tests.test_data_quality import _quality_fixture


def test_quality_api_exposes_trends_owners_and_optimistic_issue_actions(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    fixture = _quality_fixture(session, tenant, tmp_path)
    administrator = create_account(
        tenant_id=tenant.id,
        email="quality-admin@example.test",
        normalized_email="quality-admin@example.test",
        display_name="Quality Administrator",
        password_hash="not-used",  # noqa: S106
        role=UserRole.ADMIN,
    )
    session.add(administrator)
    session.commit()
    DataQualityService(session, Settings(), tenant.id).evaluate(
        trigger="scheduled",
        actor_type="system",
        actor_id="quality-worker",
    )

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(
            tenant.id,
            administrator.id,
            "user",
            frozenset({"governance:read", "governance:review"}),
        )

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            snapshots = client.get("/api/v1/governance/quality/snapshots")
            assert snapshots.status_code == 200
            assert snapshots.json()[0]["definitions_version"] == "quality-v1"

            coverage = client.get("/api/v1/governance/quality/coverage", params={"limit": 1})
            assert coverage.status_code == 200
            assert coverage.json()[0]["dataset_key"] == "literature"
            assert coverage.json()[0]["freshness_status"] == "stale"
            assert coverage.json()[0]["parse_missing_count"] == 1

            issues = client.get("/api/v1/governance/quality/issues", params={"status": "open"})
            assert issues.status_code == 200
            completeness = next(item for item in issues.json() if item["metric_key"] == "completeness")
            assert completeness["owner_user_id"] is None

            owners = client.get("/api/v1/governance/quality/owners")
            assert owners.status_code == 200
            assert {owner["id"] for owner in owners.json()} == {administrator.id, fixture["owner"].id}

            assigned = client.post(
                f"/api/v1/governance/quality/issues/{completeness['id']}/actions",
                json={
                    "action": "assign",
                    "expected_version": completeness["version"],
                    "owner_user_id": fixture["owner"].id,
                },
            )
            assert assigned.status_code == 200
            assert assigned.json()["owner_display_name"] == "Quality Owner"

            stale = client.post(
                f"/api/v1/governance/quality/issues/{completeness['id']}/actions",
                json={
                    "action": "acknowledge",
                    "expected_version": completeness["version"],
                },
            )
            assert stale.status_code == 409

            events = client.get(f"/api/v1/governance/quality/issues/{completeness['id']}/events")
            assert events.status_code == 200
            assert [event["action"] for event in events.json()] == ["opened", "assign"]

            evaluated = client.post("/api/v1/governance/quality/evaluations")
            assert evaluated.status_code == 201
            assert evaluated.json()["trigger"] == "manual"
    finally:
        app.dependency_overrides.clear()


def test_quality_api_enforces_owner_roles_and_administrator_waivers(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    fixture = _quality_fixture(session, tenant, tmp_path)
    administrator = create_account(
        tenant_id=tenant.id,
        email="quality-policy-admin@example.test",
        normalized_email="quality-policy-admin@example.test",
        display_name="Quality Policy Administrator",
        password_hash="not-used",  # noqa: S106
        role=UserRole.ADMIN,
    )
    viewer = create_account(
        tenant_id=tenant.id,
        email="quality-policy-viewer@example.test",
        normalized_email="quality-policy-viewer@example.test",
        display_name="Quality Policy Viewer",
        password_hash="not-used",  # noqa: S106
        role=UserRole.VIEWER,
    )
    session.add_all([administrator, viewer])
    session.commit()
    DataQualityService(session, Settings(), tenant.id).evaluate(
        trigger="scheduled",
        actor_type="system",
        actor_id="quality-worker",
    )
    issue = session.scalar(
        select(DataQualityIssue).where(
            DataQualityIssue.tenant_id == tenant.id,
            DataQualityIssue.metric_key == "completeness",
        )
    )
    assert issue is not None
    active_actor_id = {"value": administrator.id}

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(
            tenant.id,
            active_actor_id["value"],
            "user",
            frozenset({"governance:read", "governance:review"}),
        )

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            invalid_owner = client.post(
                f"/api/v1/governance/quality/issues/{issue.id}/actions",
                json={
                    "action": "assign",
                    "expected_version": issue.version,
                    "owner_user_id": viewer.id,
                },
            )
            assert invalid_owner.status_code == 409
            assert "administrator or analyst" in invalid_owner.json()["detail"]

            unassigned_ack = client.post(
                f"/api/v1/governance/quality/issues/{issue.id}/actions",
                json={"action": "acknowledge", "expected_version": issue.version},
            )
            assert unassigned_ack.status_code == 409
            assert "Assign an owner" in unassigned_ack.json()["detail"]

            active_actor_id["value"] = fixture["owner"].id
            forbidden_waiver = client.post(
                f"/api/v1/governance/quality/issues/{issue.id}/actions",
                json={
                    "action": "waive",
                    "expected_version": issue.version,
                    "notes": "Analysts cannot approve exceptions",
                },
            )
            assert forbidden_waiver.status_code == 403
            assert "administrators" in forbidden_waiver.json()["detail"]
    finally:
        app.dependency_overrides.clear()
