from __future__ import annotations

import json
import secrets
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.models import Entity, EntityType, ReviewStatus, Tenant, UserRole, WorkspaceExportEvent
from pharma_intel.repository import EntityRepository
from pharma_intel.schemas import EntityCreate
from pharma_intel.security import CSRF_COOKIE, hash_password


def test_real_session_exports_and_comparisons_cannot_reveal_unpublished_records_after_role_change(
    session: Session,
    tenant: Tenant,
) -> None:
    password = secrets.token_urlsafe(32)
    user = create_account(
        tenant_id=tenant.id,
        email="publication@example.test",
        normalized_email="publication@example.test",
        display_name="Publication tester",
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
    )
    session.add(user)
    session.commit()
    repository = EntityRepository(session, tenant.id)
    published = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="Visibility published"))
    draft = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="Visibility draft"))
    published.review_status = ReviewStatus.VERIFIED
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def login(client: TestClient) -> dict[str, str]:
        response = client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
        assert response.status_code == 200
        return {"X-CSRF-Token": client.cookies[CSRF_COOKIE]}

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as client:
            headers = login(client)
            policy = client.post(
                "/api/v1/admin/workspace-export-policy",
                headers=headers,
                json={
                    "policy_version": "publication-visibility-v1",
                    "enabled": True,
                    "allowed_formats": ["json"],
                    "allowed_fields": [
                        "id",
                        "entity_type",
                        "name",
                        "entities.id",
                        "entities.name",
                        "entities.review_status",
                    ],
                    "max_records_per_export": 20,
                    "attribution": "Synthetic acceptance data",
                },
            )
            assert policy.status_code == 200
            created = client.post("/api/v1/comparison-sets", headers=headers, json={"name": "Visibility comparison"})
            assert created.status_code == 201
            item_id = created.json()["id"]
            added = client.post(
                f"/api/v1/comparison-sets/{item_id}/members/batch",
                headers=headers,
                json={"entity_ids": [published.id, draft.id], "expected_version": 1},
            )
            assert added.status_code == 200
            command = {
                "dataset": "entities",
                "query": {"q": "Visibility"},
                "export_format": "json",
                "fields": ["id", "name", "review_status"],
                "max_records": 20,
                "idempotency_key": "publication-review-context-0001",
            }
            reviewed = client.post("/api/v1/workspace/domain-exports", headers=headers, json=command)
            assert reviewed.status_code == 200
            assert {row["id"] for row in reviewed.json()["records"]} == {published.id, draft.id}
            event_id = reviewed.headers["x-export-event-id"]
            user.memberships[0].role = UserRole.VIEWER
            user.memberships[0].token_version += 1
            session.commit()
            headers = login(client)
            replay = client.post("/api/v1/workspace/domain-exports", headers=headers, json=command)
            assert replay.status_code == 409
            public = client.post(
                "/api/v1/workspace/domain-exports",
                headers=headers,
                json={**command, "idempotency_key": "publication-public-context-0001"},
            )
            assert public.status_code == 200
            assert [row["id"] for row in public.json()["records"]] == [published.id]
            denied = client.post(
                "/api/v1/workspace/domain-exports",
                headers=headers,
                json={
                    **command,
                    "query": {"q": "Visibility", "review_status": "draft"},
                    "idempotency_key": "publication-denied-context-0001",
                },
            )
            assert denied.status_code == 403
            detail = client.get(f"/api/v1/comparison-sets/{item_id}")
            assert detail.status_code == 200
            assert [member["entity"]["id"] for member in detail.json()["members"]] == [published.id]
            assert "Visibility draft" not in detail.text
            assert session.get(Entity, draft.id) is not None
            event = session.get(WorkspaceExportEvent, event_id)
            assert event is not None and event.record_count == 2
            assert "Visibility draft" in json.dumps(event.records_json)
    finally:
        app.dependency_overrides.pop(get_session, None)
