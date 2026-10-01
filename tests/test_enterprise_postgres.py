from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from pharma_intel.accounts.identity import create_account
from pharma_intel.db import set_tenant_context
from pharma_intel.enterprise.admin import (
    AuditCursorCodec,
    EnterpriseAdminConflict,
    EnterpriseAdminService,
    UpdateDatasetStatusCommand,
    UpdateUserRoleCommand,
)
from pharma_intel.licensing import internal_evidence_license_policy
from pharma_intel.models import (
    AuditEvent,
    Entity,
    EntityType,
    EpidemiologyObservation,
    NewsEvent,
    RegulatoryEvent,
    ReviewStatus,
    Tenant,
    TenantDataset,
    User,
    UserGroup,
    UserRole,
    UserSession,
)
from pharma_intel.security import _principal_from_session, issue_human_session
from tests.support.postgres_safety import require_disposable_postgres_url

pytestmark = pytest.mark.integration
CURSOR_SECRET = "enterprise-postgres-cursor-secret-32-bytes"  # noqa: S105


def _service(session: Session, tenant_id: str, actor_id: str, request_id: str) -> EnterpriseAdminService:
    return EnterpriseAdminService(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_id=request_id,
        cursor_codec=AuditCursorCodec(CURSOR_SECRET),
    )


def test_enterprise_concurrency_and_signed_tenant_rls() -> None:
    database_url = os.getenv("TEST_ENTERPRISE_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_ENTERPRISE_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_ENTERPRISE_DATABASE_URL")
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    tenant_id = str(uuid.uuid4())
    other_tenant_id = str(uuid.uuid4())

    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, tenant_id)
        tenant = Tenant(id=tenant_id, slug=f"enterprise-{tenant_id}", name="Enterprise PostgreSQL")
        session.add(tenant)
        session.flush()
        actor = create_account(
            tenant_id=tenant_id,
            email=f"admin-{tenant_id}@example.test",
            normalized_email=f"admin-{tenant_id}@example.test",
            display_name="Enterprise Administrator",
            password_hash="not-used",  # noqa: S106
            role=UserRole.ADMIN,
        )
        target = create_account(
            tenant_id=tenant_id,
            email=f"user-{tenant_id}@example.test",
            normalized_email=f"user-{tenant_id}@example.test",
            display_name="Concurrent User",
            password_hash="not-used",  # noqa: S106
            role=UserRole.VIEWER,
        )
        group = UserGroup(tenant_id=tenant_id, name="Research", normalized_name="research")
        dataset = TenantDataset(
            tenant_id=tenant_id,
            dataset_key="enterprise_test",
            display_name="Enterprise test dataset",
            license_policy=internal_evidence_license_policy(source="enterprise-postgres"),
            required_scopes=["evidence:read"],
        )
        drug = Entity(
            tenant_id=tenant_id,
            entity_type=EntityType.DRUG,
            name="Enterprise RLS Drug",
            normalized_name="enterprise rls drug",
            review_status=ReviewStatus.VERIFIED,
        )
        disease = Entity(
            tenant_id=tenant_id,
            entity_type=EntityType.DISEASE,
            name="Enterprise RLS Disease",
            normalized_name="enterprise rls disease",
            review_status=ReviewStatus.VERIFIED,
        )
        session.add_all([actor, target, group, dataset, drug, disease])
        session.flush()
        now = datetime.now(UTC)
        target_session = UserSession(
            tenant_id=tenant_id,
            user_id=target.id,
            user_agent_sha256="d" * 64,
            issued_at=now,
            expires_at=now + timedelta(hours=8),
        )
        session.add(target_session)
        session.flush()
        target_token, _, _ = issue_human_session(target.memberships[0], target_session.id)
        regulatory = RegulatoryEvent(
            tenant_id=tenant_id,
            subject_entity_id=drug.id,
            agency="FDA",
            jurisdiction="United States",
            event_identifier=f"enterprise-approval-{tenant_id}",
            event_type="approval",
            title="Enterprise tenant RLS approval",
        )
        session.add(regulatory)
        session.add(
            EpidemiologyObservation(
                tenant_id=tenant_id,
                observation_identifier=f"enterprise-epidemiology-{tenant_id}",
                disease_entity_id=disease.id,
                measure="prevalence",
                value=100,
                unit="patients per 100,000",
                geography="Global",
                population_scope="All residents",
            )
        )
        session.commit()
        actor_id = actor.id
        target_id = target.id
        target_session_id = target_session.id
        dataset_id = dataset.id

    with factory() as session:
        request = Request({"type": "http", "method": "GET", "headers": []})
        principal = _principal_from_session(session, request, target_token)
        assert principal is not None
        assert principal.tenant_id == tenant_id
        assert principal.actor_id == target_id
        assert principal.session_id == target_session_id

    barrier = threading.Barrier(2)

    def update(role: UserRole) -> str:
        with factory() as session:
            set_tenant_context(session, tenant_id)
            barrier.wait(timeout=10)
            try:
                _service(session, tenant_id, actor_id, f"concurrent-{role.value}").update_user_role(
                    target_id,
                    UpdateUserRoleCommand(1, role, f"Concurrent role assignment to {role.value}"),
                )
                return "updated"
            except EnterpriseAdminConflict:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(update, (UserRole.ANALYST, UserRole.ADMIN)))
    assert sorted(outcomes) == ["conflict", "updated"]

    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, tenant_id)
        stored_target = session.get(User, target_id)
        assert stored_target is not None
        assert stored_target.token_version == 1
        assert stored_target.memberships[0].token_version == 2
        assert stored_target.memberships[0].role in {UserRole.ANALYST, UserRole.ADMIN}
        stored_session = session.get(UserSession, target_session_id)
        assert stored_session is not None and stored_session.revoked_at is not None
        dataset = _service(session, tenant_id, actor_id, "dataset-status").update_dataset_status(
            dataset_id,
            UpdateDatasetStatusCommand(1, False, "PostgreSQL delivery pause"),
        )
        assert dataset.active is False and dataset.version == 2
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 2
        assert session.scalar(select(func.count()).select_from(UserGroup)) == 1
        assert session.scalar(select(func.count()).select_from(RegulatoryEvent)) == 1
        assert session.scalar(select(func.count()).select_from(EpidemiologyObservation)) == 1
        assert session.scalar(select(func.count()).select_from(UserSession)) == 1

    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, other_tenant_id)
        session.add(Tenant(id=other_tenant_id, slug=f"enterprise-{other_tenant_id}", name="Other Enterprise"))
        session.commit()
        assert session.scalar(select(func.count()).select_from(UserGroup)) == 0
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 0
        assert session.scalar(select(func.count()).select_from(RegulatoryEvent)) == 0
        assert session.scalar(select(func.count()).select_from(EpidemiologyObservation)) == 0
        assert session.scalar(select(func.count()).select_from(NewsEvent)) == 0
        assert session.scalar(select(func.count()).select_from(UserSession)) == 0

    with engine.connect() as connection:
        connection.execute(
            text(
                "SELECT set_config('app.tenant_id', :tenant_id, true), "
                "set_config('app.tenant_signature', 'forged', true)"
            ),
            {"tenant_id": tenant_id},
        )
        assert connection.scalar(text("SELECT public.app_current_tenant_id()")) is None
        assert connection.scalar(select(func.count()).select_from(UserGroup)) == 0
        policies = connection.execute(
            text(
                "SELECT tablename, qual, with_check FROM pg_policies "
                "WHERE schemaname = 'public' "
                "AND tablename IN "
                "('user_groups', 'user_group_memberships', 'regulatory_events', "
                "'epidemiology_observations', 'news_events', 'fact_provenance_links', 'user_sessions')"
            )
        ).all()
        assert {row.tablename for row in policies} == {
            "user_groups",
            "user_group_memberships",
            "regulatory_events",
            "epidemiology_observations",
            "news_events",
            "fact_provenance_links",
            "user_sessions",
        }
        assert all("app_current_tenant_id" in row.qual for row in policies)
        assert all("app_current_tenant_id" in row.with_check for row in policies)
        assert connection.scalar(select(func.count()).select_from(RegulatoryEvent)) == 0
        assert connection.scalar(select(func.count()).select_from(EpidemiologyObservation)) == 0
        assert connection.scalar(select(func.count()).select_from(NewsEvent)) == 0
        assert connection.scalar(select(func.count()).select_from(UserSession)) == 0
    engine.dispose()
