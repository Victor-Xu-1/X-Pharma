from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.identity import EntityIdentityService, IdentityError
from pharma_intel.models import (
    Entity,
    EntityAlias,
    EntityCanonicalLink,
    EntityResolutionCase,
    EntityResolutionDecision,
    EntityType,
    ReviewStatus,
    TargetProfile,
    Tenant,
    UserRole,
)
from pharma_intel.security import Principal, require_principal


def _entity(session: Session, tenant_id: str, name: str, normalized_name: str) -> Entity:
    entity = Entity(
        tenant_id=tenant_id,
        entity_type=EntityType.TARGET,
        name=name,
        normalized_name=normalized_name,
        review_status=ReviewStatus.VERIFIED,
    )
    session.add(entity)
    session.flush()
    session.add(
        EntityAlias(
            tenant_id=tenant_id,
            entity_id=entity.id,
            alias=name,
            normalized_alias=normalized_name,
        )
    )
    return entity


def test_entity_resolution_impact_and_reverse_canonical_rollback_are_audited(
    session: Session,
    tenant: Tenant,
) -> None:
    source = _entity(session, tenant.id, "ERBB1 source", "erbb1")
    candidate = _entity(session, tenant.id, "EGFR candidate", "egfr")
    session.add(TargetProfile(tenant_id=tenant.id, entity_id=candidate.id, gene_symbol="EGFR"))
    case = EntityResolutionCase(
        tenant_id=tenant.id,
        source_entity_id=source.id,
        candidate_entity_id=candidate.id,
        score=0.92,
        risk_tier="medium",
        reasons=[{"code": "curated_synonym", "weight": 0.92}],
        proposed_by="test",
    )
    reviewer = create_account(
        tenant_id=tenant.id,
        email="impact-reviewer@example.test",
        normalized_email="impact-reviewer@example.test",
        display_name="Impact Reviewer",
        password_hash="not-used",  # noqa: S106
        role=UserRole.ADMIN,
    )
    session.add_all([case, reviewer])
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(
            tenant.id,
            reviewer.id,
            "user",
            frozenset({"governance:read", "governance:review"}),
        )

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            before = client.get(f"/api/v1/governance/entity-resolution-cases/{case.id}/impact")
            approve = client.post(
                f"/api/v1/governance/entity-resolution-cases/{case.id}/decision",
                json={
                    "action": "approve",
                    "expected_status": "pending",
                    "canonical_entity_id": source.id,
                    "notes": "The curated source has priority over the imported candidate",
                },
            )
            stale = client.post(
                f"/api/v1/governance/entity-resolution-cases/{case.id}/decision",
                json={
                    "action": "reject",
                    "expected_status": "pending",
                    "notes": "A stale decision must fail closed",
                },
            )
            approved_cases = client.get(
                "/api/v1/governance/entity-resolution-cases",
                params={"status": "approved", "limit": 10},
            )
            after_approve = client.get(f"/api/v1/governance/entity-resolution-cases/{case.id}/impact")
            revert = client.post(
                f"/api/v1/governance/entity-resolution-cases/{case.id}/decision",
                json={
                    "action": "revert",
                    "expected_status": "approved",
                    "notes": "New evidence requires both entities to become independent again",
                },
            )
            after_revert = client.get(f"/api/v1/governance/entity-resolution-cases/{case.id}/impact")
    finally:
        app.dependency_overrides.clear()

    assert before.status_code == 200
    impact = before.json()
    assert impact["case"]["status"] == "pending"
    assert impact["candidate_reference_count"] > impact["source_reference_count"]
    assert any(
        item["table"] == "target_profiles" and item["column"] == "entity_id" and item["candidate_count"] == 1
        for item in impact["references"]
    )
    assert impact["recommended_canonical_entity_id"] == candidate.id
    assert impact["rollback_available"] is False

    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"
    assert stale.status_code == 409
    assert approved_cases.status_code == 200
    assert [item["id"] for item in approved_cases.json()] == [case.id]
    assert after_approve.status_code == 200
    assert after_approve.json()["active_alias_entity_id"] == candidate.id
    assert after_approve.json()["active_canonical_entity_id"] == source.id
    assert after_approve.json()["rollback_available"] is True

    assert revert.status_code == 200
    assert revert.json()["status"] == "reverted"
    assert after_revert.status_code == 200
    reverted_impact = after_revert.json()
    assert reverted_impact["active_alias_entity_id"] is None
    assert reverted_impact["active_canonical_entity_id"] is None
    assert reverted_impact["rollback_available"] is False
    assert [item["action"] for item in reverted_impact["decisions"]] == ["approve", "revert"]

    link = session.scalar(select(EntityCanonicalLink).where(EntityCanonicalLink.resolution_case_id == case.id))
    assert link is not None
    assert link.alias_entity_id == candidate.id
    assert link.canonical_entity_id == source.id
    assert link.active is False
    decisions = list(
        session.scalars(
            select(EntityResolutionDecision)
            .where(EntityResolutionDecision.resolution_case_id == case.id)
            .order_by(EntityResolutionDecision.created_at)
        )
    )
    assert [item.action for item in decisions] == ["approve", "revert"]
    assert decisions[0].snapshot["canonical_entity_id"] == source.id
    assert decisions[0].snapshot["alias_entity_id"] == candidate.id


def test_identity_service_rejects_status_drift_before_mutating_link(
    session: Session,
    tenant: Tenant,
) -> None:
    source = _entity(session, tenant.id, "Status source", "status source")
    candidate = _entity(session, tenant.id, "Status candidate", "status candidate")
    case = EntityResolutionCase(
        tenant_id=tenant.id,
        source_entity_id=source.id,
        candidate_entity_id=candidate.id,
        score=0.8,
        risk_tier="medium",
        reasons=[],
        proposed_by="test",
    )
    reviewer = create_account(
        tenant_id=tenant.id,
        email="status-reviewer@example.test",
        normalized_email="status-reviewer@example.test",
        display_name="Status Reviewer",
        password_hash="not-used",  # noqa: S106
        role=UserRole.ADMIN,
    )
    session.add_all([case, reviewer])
    session.commit()

    service = EntityIdentityService(session, tenant.id)
    service.decide(
        case.id,
        action="reject",
        expected_status="pending",
        canonical_entity_id=None,
        user_id=reviewer.id,
        notes="Keep the records independent",
    )

    with pytest.raises(IdentityError, match="changed; refresh"):
        service.decide(
            case.id,
            action="approve",
            expected_status="pending",
            canonical_entity_id=candidate.id,
            user_id=reviewer.id,
            notes="This stale approval must fail",
        )
