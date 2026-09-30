from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.models import (
    DataQualityIssue,
    DataQualityIssueEvent,
    DataQualitySnapshot,
    Tenant,
)
from pharma_intel.quality.service import DataQualityError, DataQualityService
from tests.support.postgres_safety import require_disposable_postgres_url
from tests.test_data_quality import _quality_fixture

pytestmark = pytest.mark.integration


def test_data_quality_is_durable_tenant_scoped_append_only_and_concurrency_safe(tmp_path: Path) -> None:
    database_url = os.getenv("TEST_DATA_QUALITY_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATA_QUALITY_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_DATA_QUALITY_DATABASE_URL")

    engine = create_engine(database_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    other_tenant_id = str(uuid.uuid4())
    snapshot_id = ""
    issue_id = ""
    event_id = ""
    try:
        with Session(engine, expire_on_commit=False) as session:
            set_tenant_context(session, tenant_id)
            tenant = Tenant(id=tenant_id, slug=f"quality-{tenant_id}", name="Quality acceptance")
            session.add(tenant)
            session.commit()
            fixture = _quality_fixture(session, tenant, tmp_path)
            service = DataQualityService(
                session,
                Settings(data_quality_issue_sla_hours=8),
                tenant_id,
            )
            scheduled = service.evaluate(
                trigger="scheduled",
                actor_type="system",
                actor_id="quality-worker",
            )
            snapshot_id = scheduled.id
            issue = next(item for item in service.issues() if item.metric_key == "completeness")
            issue_id = issue.id
            assert issue.status == "open"
            assert issue.version == 1
            assert issue.sla_due_at > issue.detected_at

            assigned = service.act(
                issue.id,
                action="assign",
                expected_version=1,
                actor_id=fixture["owner"].id,
                request_id="postgres-quality-assign",
                owner_user_id=fixture["owner"].id,
                notes=None,
            )
            acknowledged = service.act(
                issue.id,
                action="acknowledge",
                expected_version=assigned.version,
                actor_id=fixture["owner"].id,
                request_id="postgres-quality-acknowledge",
                owner_user_id=None,
                notes=None,
            )
            assert acknowledged.status == "acknowledged"

            manual = service.evaluate(
                trigger="manual",
                actor_type="user",
                actor_id=fixture["owner"].id,
            )
            session.refresh(issue)
            assert manual.id != scheduled.id
            assert issue.version == 4
            assert issue.status == "acknowledged"
            with pytest.raises(DataQualityError, match="changed"):
                service.act(
                    issue.id,
                    action="waive",
                    expected_version=3,
                    actor_id=fixture["owner"].id,
                    request_id="postgres-quality-stale",
                    owner_user_id=None,
                    notes="stale exception attempt",
                )

            events = service.events(issue.id)
            event_id = events[0].id
            assert [event.action for event in events] == ["opened", "assign", "acknowledge"]
            with pytest.raises(DBAPIError, match="append-only"):
                session.execute(
                    update(DataQualityIssueEvent)
                    .where(DataQualityIssueEvent.id == event_id)
                    .values(details={"tampered": True})
                )
                session.commit()
            session.rollback()

        with Session(engine, expire_on_commit=False) as other_session:
            set_tenant_context(other_session, other_tenant_id)
            other_session.add(
                Tenant(
                    id=other_tenant_id,
                    slug=f"quality-{other_tenant_id}",
                    name="Other quality tenant",
                )
            )
            other_session.commit()
            assert other_session.get(DataQualitySnapshot, snapshot_id) is None
            assert other_session.get(DataQualityIssue, issue_id) is None
            assert other_session.get(DataQualityIssueEvent, event_id) is None

        with engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT set_config('app.tenant_id', :tenant_id, true), "
                    "set_config('app.tenant_signature', 'forged', true)"
                ),
                {"tenant_id": tenant_id},
            )
            assert connection.scalar(text("SELECT public.app_current_tenant_id()")) is None
            assert connection.scalar(select(func.count()).select_from(DataQualitySnapshot)) == 0
            assert connection.scalar(select(func.count()).select_from(DataQualityIssue)) == 0
            assert connection.scalar(select(func.count()).select_from(DataQualityIssueEvent)) == 0
    finally:
        engine.dispose()
