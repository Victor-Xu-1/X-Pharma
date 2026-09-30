from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import pharma_intel.object_store as object_store_module
from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.models import DataSource, DataSourceType, SourceAsset, SourceAssetState, Tenant
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.security import Principal, require_principal


def test_data_lifecycle_http_contract_is_human_admin_only(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = Principal(tenant.id, "lifecycle-admin", "user", frozenset({"*"}))
    store = FileSystemObjectStore(tmp_path / "objects")

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: principal
    monkeypatch.setattr(object_store_module, "build_object_store", lambda _settings: store)
    try:
        with TestClient(app) as client:
            created = client.put(
                "/api/v1/commercial/data-lifecycle/retention-policies/export-artifacts",
                json={
                    "retention_seconds": 3600,
                    "legal_basis": "enterprise contractual retention schedule",
                    "geographic_scope": ["CN", "SG"],
                    "active": True,
                },
            )
            assert created.status_code == 200
            assert created.json()["policy_version"] == 1

            updated = client.put(
                "/api/v1/commercial/data-lifecycle/retention-policies/export-artifacts",
                json={
                    "retention_seconds": 7200,
                    "legal_basis": "approved retention schedule revision",
                    "geographic_scope": ["CN"],
                    "active": True,
                },
            )
            assert updated.status_code == 200
            assert updated.json()["policy_version"] == 2
            source_policy = client.put(
                "/api/v1/commercial/data-lifecycle/retention-policies/source-assets",
                json={
                    "retention_seconds": 86400,
                    "legal_basis": "approved source lifecycle schedule",
                    "geographic_scope": ["CN"],
                    "active": True,
                },
            )
            assert source_policy.status_code == 200
            assert source_policy.json()["data_class"] == "source_asset_snapshot"
            assert client.get("/api/v1/commercial/data-lifecycle/retention-policies").status_code == 200

            data_source = DataSource(
                tenant_id=tenant.id,
                name="Lifecycle API source",
                source_type=DataSourceType.FOLDER,
                root_uri="/lifecycle-api-source",
                owner="Research Operations",
                authorization_scopes=["contract:lifecycle-api"],
                dataset_key="literature",
            )
            session.add(data_source)
            session.flush()
            deleted_asset = SourceAsset(
                tenant_id=tenant.id,
                data_source_id=data_source.id,
                logical_path="withdrawn/egfr.md",
                source_uri="file:///lifecycle-api-source/withdrawn/egfr.md",
                file_name="egfr.md",
                extension=".md",
                processing_mode="parse",
                state=SourceAssetState.DELETED,
            )
            session.add(deleted_asset)
            session.commit()
            source_hold = client.post(
                "/api/v1/commercial/data-lifecycle/legal-holds",
                json={
                    "scope_type": "data_source",
                    "scope_id": data_source.id,
                    "matter_reference": "MATTER-API-SOURCE",
                    "reason": "preserve governed source assets",
                },
            )
            assert source_hold.status_code == 201

            hold = client.post(
                "/api/v1/commercial/data-lifecycle/legal-holds",
                json={
                    "scope_type": "tenant",
                    "scope_id": None,
                    "matter_reference": "MATTER-API-001",
                    "reason": "preserve tenant export evidence",
                },
            )
            assert hold.status_code == 201
            hold_id = hold.json()["id"]
            assert hold.json()["status"] == "active"
            active_holds = client.get("/api/v1/commercial/data-lifecycle/legal-holds?active_only=true")
            assert active_holds.json()[0]["id"] == hold_id

            released = client.post(
                f"/api/v1/commercial/data-lifecycle/legal-holds/{hold_id}/release",
                json={"reason": "matter closed by legal counsel"},
            )
            assert released.status_code == 200
            assert released.json()["status"] == "released"
            assert client.get("/api/v1/commercial/data-lifecycle/events").json() == []

            deleted_assets = client.get("/api/v1/commercial/data-lifecycle/source-assets/deleted")
            assert deleted_assets.status_code == 200
            assert deleted_assets.json()[0]["id"] == deleted_asset.id
            blocked_reauthorization = client.post(
                f"/api/v1/commercial/data-lifecycle/source-assets/{deleted_asset.id}/reauthorize",
                json={
                    "idempotency_key": "api.source.reauthorize.blocked",
                    "reason": "restore approved source path",
                },
            )
            assert blocked_reauthorization.status_code == 200
            assert blocked_reauthorization.json()["event"]["action"] == "reauthorize"
            assert blocked_reauthorization.json()["event"]["outcome"] == "blocked"

            released_source_hold = client.post(
                f"/api/v1/commercial/data-lifecycle/legal-holds/{source_hold.json()['id']}/release",
                json={"reason": "source reauthorization approved"},
            )
            assert released_source_hold.status_code == 200
            reauthorized = client.post(
                f"/api/v1/commercial/data-lifecycle/source-assets/{deleted_asset.id}/reauthorize",
                json={
                    "idempotency_key": "api.source.reauthorize.success",
                    "reason": "restore approved source path",
                },
            )
            assert reauthorized.status_code == 200
            assert reauthorized.json()["event"]["outcome"] == "succeeded"
            session.refresh(deleted_asset)
            assert deleted_asset.state == SourceAssetState.MISSING
            assert client.get("/api/v1/commercial/data-lifecycle/source-assets/deleted").json() == []

            app.dependency_overrides[require_principal] = lambda: Principal(
                tenant.id,
                "agent-1",
                "agent",
                frozenset({"*"}),
                "client-1",
            )
            denied = client.get("/api/v1/commercial/data-lifecycle/retention-policies")
            assert denied.status_code == 403
    finally:
        app.dependency_overrides.clear()
