from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session, set_tenant_context
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
    User,
    UserRole,
)
from pharma_intel.security import Principal, require_principal
from tests.support.postgres_safety import require_disposable_postgres_url

pytestmark = pytest.mark.integration


def _entity(session: Session, tenant_id: str, name: str) -> Entity:
    entity = Entity(
        tenant_id=tenant_id,
        entity_type=EntityType.TARGET,
        name=name,
        normalized_name=name.casefold(),
        review_status=ReviewStatus.VERIFIED,
    )
    session.add(entity)
    session.flush()
    session.add(
        EntityAlias(
            tenant_id=tenant_id,
            entity_id=entity.id,
            alias=name,
            normalized_alias=name.casefold(),
        )
    )
    return entity


def test_entity_resolution_api_is_reversible_tenant_scoped_and_append_only() -> None:
    database_url = os.getenv("TEST_ENTITY_RESOLUTION_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_ENTITY_RESOLUTION_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_ENTITY_RESOLUTION_DATABASE_URL")

    engine = create_engine(database_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    other_tenant_id = str(uuid.uuid4())
    try:
        with Session(engine, expire_on_commit=False) as session:
            set_tenant_context(session, tenant_id)
            session.add(Tenant(id=tenant_id, slug=f"resolution-{tenant_id}", name="Resolution acceptance"))
            session.flush()
            source = _entity(session, tenant_id, "ERBB2 imported")
            candidate = _entity(session, tenant_id, "HER2 canonical")
            target_profile = TargetProfile(tenant_id=tenant_id, entity_id=candidate.id, gene_symbol="ERBB2")
            reviewer = User(
                tenant_id=tenant_id,
                email=f"resolution-{tenant_id}@example.test",
                normalized_email=f"resolution-{tenant_id}@example.test",
                display_name="Resolution Reviewer",
                password_hash="not-used",  # noqa: S106
                role=UserRole.ADMIN,
            )
            case = EntityResolutionCase(
                tenant_id=tenant_id,
                source_entity_id=source.id,
                candidate_entity_id=candidate.id,
                score=0.97,
                risk_tier="medium",
                reasons=[{"code": "curated_identifier_match", "weight": 0.97}],
                proposed_by="postgres_acceptance",
            )
            session.add_all([target_profile, reviewer, case])
            session.commit()
            case_id = case.id

            def session_override() -> Generator[Session]:
                set_tenant_context(session, tenant_id)
                yield session

            def principal_override() -> Principal:
                return Principal(
                    tenant_id,
                    reviewer.id,
                    "user",
                    frozenset({"governance:read", "governance:review"}),
                )

            app.dependency_overrides[get_session] = session_override
            app.dependency_overrides[require_principal] = principal_override
            try:
                with TestClient(app) as client:
                    before = client.get(f"/api/v1/governance/entity-resolution-cases/{case.id}/impact")
                    approved = client.post(
                        f"/api/v1/governance/entity-resolution-cases/{case.id}/decision",
                        json={
                            "action": "approve",
                            "expected_status": "pending",
                            "canonical_entity_id": candidate.id,
                            "notes": "Verified HGNC identity and retained the curated entity",
                        },
                    )
                    stale = client.post(
                        f"/api/v1/governance/entity-resolution-cases/{case.id}/decision",
                        json={
                            "action": "reject",
                            "expected_status": "pending",
                            "notes": "This stale write must not mutate governance state",
                        },
                    )
                    merged = client.get(f"/api/v1/governance/entity-resolution-cases/{case.id}/impact")
                    reverted = client.post(
                        f"/api/v1/governance/entity-resolution-cases/{case.id}/decision",
                        json={
                            "action": "revert",
                            "expected_status": "approved",
                            "notes": "New curated evidence requires independent identities",
                        },
                    )
                    after = client.get(f"/api/v1/governance/entity-resolution-cases/{case.id}/impact")
            finally:
                app.dependency_overrides.clear()

            assert before.status_code == 200
            assert before.json()["candidate_reference_count"] >= 1
            assert approved.status_code == 200
            assert stale.status_code == 409
            assert merged.status_code == 200 and merged.json()["rollback_available"] is True
            assert reverted.status_code == 200
            assert after.status_code == 200 and after.json()["rollback_available"] is False
            assert [item["action"] for item in after.json()["decisions"]] == ["approve", "revert"]

            session.expire_all()
            set_tenant_context(session, tenant_id)
            link = session.scalar(select(EntityCanonicalLink).where(EntityCanonicalLink.resolution_case_id == case.id))
            assert link is not None and link.active is False
            profile = session.get(TargetProfile, target_profile.id)
            assert profile is not None and profile.entity_id == candidate.id
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(EntityResolutionDecision)
                    .where(EntityResolutionDecision.resolution_case_id == case.id)
                )
                == 2
            )

            decision_id = session.scalar(
                select(EntityResolutionDecision.id)
                .where(EntityResolutionDecision.resolution_case_id == case.id)
                .order_by(EntityResolutionDecision.created_at)
                .limit(1)
            )
            with pytest.raises(DBAPIError, match="append-only"):
                session.execute(
                    update(EntityResolutionDecision)
                    .where(EntityResolutionDecision.id == decision_id)
                    .values(notes="tampered")
                )
                session.commit()
            session.rollback()

        with Session(engine) as other_session:
            set_tenant_context(other_session, other_tenant_id)
            other_session.add(
                Tenant(id=other_tenant_id, slug=f"resolution-{other_tenant_id}", name="Other resolution tenant")
            )
            other_session.commit()
            assert other_session.get(EntityResolutionCase, case_id) is None
            assert other_session.scalar(select(func.count()).select_from(EntityResolutionDecision)) == 0

        with engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT set_config('app.tenant_id', :tenant_id, true), "
                    "set_config('app.tenant_signature', 'forged', true)"
                ),
                {"tenant_id": tenant_id},
            )
            assert connection.scalar(text("SELECT public.app_current_tenant_id()")) is None
            assert connection.scalar(select(func.count()).select_from(EntityResolutionDecision)) == 0
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
