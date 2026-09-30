from __future__ import annotations

import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import paramiko  # type: ignore[import-untyped]
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.api import app, browser_security_headers_for_path
from pharma_intel.config import Settings
from pharma_intel.db import get_session
from pharma_intel.licensing import internal_evidence_license_policy
from pharma_intel.models import (
    ApiKey,
    AuditEvent,
    DataSource,
    DataSourceType,
    DevelopmentPhase,
    DevelopmentProgram,
    Entity,
    EntityIdentifier,
    ReviewStatus,
    SourceAsset,
    SourceAssetState,
    Tenant,
    TenantDataset,
    User,
    UserRole,
    UserSession,
)
from pharma_intel.repository import EntityRepository
from pharma_intel.schemas import EntityCreate
from pharma_intel.search.contracts import EvidenceMatch
from pharma_intel.security import CSRF_COOKIE, Principal, hash_password, issue_api_key, require_principal


def test_database_readiness_does_not_require_an_opensearch_projection(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def session_override() -> Generator[Session]:
        yield session

    class UnexpectedSearchGateway:
        @staticmethod
        def assert_projection_ready() -> None:
            raise AssertionError("database readiness must not inspect the OpenSearch projection")

    monkeypatch.setattr("pharma_intel.api.get_settings", lambda: Settings(search_backend="database"))
    monkeypatch.setattr("pharma_intel.api.get_opensearch_gateway", UnexpectedSearchGateway)
    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as client:
            response = client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "search": "database"}


def test_data_source_catalog_reads_chembl_routing_rules(
    session: Session,
    tenant: Tenant,
) -> None:
    session.add(
        DataSource(
            tenant_id=tenant.id,
            name="ChEMBL official API",
            source_type=DataSourceType.CHEMBL,
            root_uri="https://www.ebi.ac.uk/chembl/api/data/",
            owner="Scientific Data Operations",
            data_classification="public",
            authorization_scopes=["public:chembl"],
            dataset_key="chembl",
            include_globs=["*"],
            exclude_globs=[],
            routing_rules=[{"target_chembl_id": "chembl203", "max_records": 25, "page_size": 25}],
            stable_seconds=0,
        )
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "chembl-catalog-test", "api_key", frozenset({"*"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/admin/data-sources")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["routing_rules"] == [
        {"target_chembl_id": "CHEMBL203", "max_records": 25, "page_size": 25}
    ]


def test_chembl_source_registration_and_update_preserve_routing_rules(
    session: Session,
    tenant: Tenant,
) -> None:
    session.add(
        TenantDataset(
            tenant_id=tenant.id,
            dataset_key="chembl",
            display_name="ChEMBL",
            license_policy=internal_evidence_license_policy(source="public:chembl"),
        )
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "chembl-admin-test", "api_key", frozenset({"ingestion:manage"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    payload = {
        "name": "Controlled ChEMBL source",
        "source_type": "chembl",
        "root_uri": "https://www.ebi.ac.uk/chembl/api/data/",
        "owner": "Scientific Data Operations",
        "data_classification": "public",
        "authorization_scopes": ["public:chembl"],
        "dataset_key": "chembl",
        "stable_seconds": 0,
        "rate_limit_per_minute": 60,
        "routing_rules": [{"target_chembl_id": "chembl203", "max_records": 25, "page_size": 25}],
    }
    try:
        with TestClient(app) as client:
            created = client.post("/api/v1/admin/data-sources", json=payload)
            assert created.status_code == 201, created.text
            source = session.get(DataSource, created.json()["id"])
            assert source is not None
            assert source.routing_rules[0]["target_chembl_id"] == "CHEMBL203"
            changed = client.patch(
                f"/api/v1/admin/data-sources/{source.id}",
                json={"routing_rules": [{"target_chembl_id": "chembl204", "max_records": 10, "page_size": 10}]},
            )
            assert changed.status_code == 200, changed.text
            session.refresh(source)
            assert source.routing_rules[0] == {"target_chembl_id": "CHEMBL204", "max_records": 10, "page_size": 10}
    finally:
        app.dependency_overrides.clear()


def test_drug_comparison_endpoint_is_bounded_ordered_and_fail_closed(
    session: Session,
    tenant: Tenant,
) -> None:
    repository = EntityRepository(session, tenant.id)
    first = repository.create(EntityCreate(entity_type="drug", name="First compared drug"))
    second = repository.create(EntityCreate(entity_type="drug", name="Second compared drug"))
    target = repository.create(EntityCreate(entity_type="target", name="Compared target"))
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=first.id,
            target_entity_id=target.id,
            phase=DevelopmentPhase.PHASE_2,
            program_status="active",
        )
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "comparison-test", "api_key", frozenset({"*"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/drugs/comparison",
                params=[("drug_ids", second.id), ("drug_ids", first.id)],
            )
            duplicate = client.get(
                "/api/v1/drugs/comparison",
                params=[("drug_ids", first.id), ("drug_ids", first.id)],
            )
            missing = client.get(
                "/api/v1/drugs/comparison",
                params=[("drug_ids", first.id), ("drug_ids", target.id)],
            )
            too_many = client.get(
                "/api/v1/drugs/comparison",
                params=[("drug_ids", str(index)) for index in range(5)],
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_schema_version"] == "pharma.drug.comparison.v1"
    assert [item["entity"]["id"] for item in payload["items"]] == [second.id, first.id]
    assert payload["items"][1]["summary"]["program_count"] == 1
    assert payload["items"][1]["target_names"] == ["Compared target"]
    assert duplicate.status_code == 422
    assert missing.status_code == 404
    assert too_many.status_code == 422


def test_health_and_authenticated_entity_flow(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "test-key", "api_key", frozenset({"*"}))

    class ReadySearchGateway:
        @staticmethod
        def assert_projection_ready() -> None:
            return None

    monkeypatch.setattr("pharma_intel.api.get_opensearch_gateway", ReadySearchGateway)
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            assert client.get("/health/ready").status_code == 200
            created = client.post(
                "/api/v1/entities",
                json={"entity_type": "drug", "name": "Pembrolizumab", "aliases": ["Keytruda"]},
            )
            assert created.status_code == 201
            result = client.get("/api/v1/entities", params={"q": "keytruda"})
            assert result.status_code == 200
            assert result.json()["total"] == 1
            assert result.json()["engine"] == "database"
            assert result.json()["sort_by"] == "relevance"
            assert result.json()["sort_direction"] == "desc"
            assert result.json()["query_schema_version"] == "pharma.entity.search.v2"
            assert result.json()["applied_filters"] == [{"field": "q", "operator": "contains", "value": "keytruda"}]
            assert result.json()["items"][0]["aliases"] == ["Keytruda"]
            assert result.json()["facets"] == {
                "entity_type": {"drug": 1},
                "review_status": {"draft": 1},
            }
            assert result.json()["suggestions"] == []
            governed = client.get("/api/v1/entities", params={"review_status": "verified"})
            assert governed.status_code == 200
            assert governed.json()["total"] == 0
            assert governed.json()["facets"]["review_status"] == {"draft": 1}
            suggestions = client.get("/api/v1/entities/suggestions", params={"q": "keytruda"})
            assert suggestions.status_code == 200
            assert suggestions.json() == {"suggestions": ["Pembrolizumab"], "engine": "database"}
            sorted_result = client.get(
                "/api/v1/entities",
                params={"entity_type": "drug", "sort_by": "updated_at", "sort_direction": "asc"},
            )
            assert sorted_result.status_code == 200
            assert sorted_result.json()["sort_by"] == "updated_at"
            assert sorted_result.json()["sort_direction"] == "asc"
            target = client.post(
                "/api/v1/entities",
                json={
                    "entity_type": "target",
                    "name": "Portfolio target",
                    "aliases": ["Shared portfolio alias"],
                    "external_ids": {"UNIPROT": "P12345"},
                },
            )
            organization = client.post(
                "/api/v1/entities",
                json={
                    "entity_type": "organization",
                    "name": "Portfolio organization",
                    "aliases": ["Shared portfolio alias"],
                },
            )
            assert target.status_code == organization.status_code == 201
            multi_type = client.get(
                "/api/v1/entities",
                params=[
                    ("q", "shared portfolio alias"),
                    ("entity_types", "target"),
                    ("entity_types", "organization"),
                ],
            )
            assert multi_type.status_code == 200
            assert {item["entity_type"] for item in multi_type.json()["items"]} == {"target", "organization"}
            assert multi_type.json()["applied_filters"] == [
                {"field": "q", "operator": "contains", "value": "shared portfolio alias"},
                {"field": "entity_types", "operator": "in", "value": ["organization", "target"]},
            ]
            assert {item["match"]["match_type"] for item in multi_type.json()["items"]} == {"alias"}
            assert {item["match"]["match_relation"] for item in multi_type.json()["items"]} == {"exact"}
            assert {tuple(item["aliases"]) for item in multi_type.json()["items"]} == {("Shared portfolio alias",)}
            identifier = client.get("/api/v1/entities", params={"q": "P12345", "entity_type": "target"})
            assert identifier.status_code == 200
            assert identifier.json()["items"][0]["match"] == {
                "match_type": "external_id",
                "match_relation": "exact",
                "matched_value": "P12345",
                "namespace": "uniprot",
            }
            bounded_aliases = [f"Candidate alias {index:02d}" for index in range(25)]
            bounded = client.post(
                "/api/v1/entities",
                json={
                    "entity_type": "drug",
                    "name": "Bounded alias candidate",
                    "aliases": list(reversed(bounded_aliases)),
                },
            )
            assert bounded.status_code == 201
            bounded_result = client.get("/api/v1/entities", params={"q": "Bounded alias candidate"})
            assert bounded_result.status_code == 200
            assert bounded_result.json()["items"][0]["aliases"] == bounded_aliases[:20]
            assert (
                client.get("/api/v1/entities", params=[("q", "portfolio"), ("entity_types", "unknown")]).status_code
                == 422
            )
            assert client.get("/api/v1/entities", params={"sort_by": "unknown"}).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_external_entity_projection_filters_internal_attributes(
    session: Session,
    tenant: Tenant,
) -> None:
    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "test-key", "api_key", frozenset({"*"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/entities",
                json={
                    "entity_type": "target",
                    "name": "External projection target",
                    "external_ids": {
                        "UniProt": "P00533",
                    },
                    "attributes": {
                        "modality": "small molecule",
                        "origin": "governed_ai_extraction",
                        "source_document_ids": ["document-internal-1"],
                        "internal_review_trace": {"case_id": "case-internal-1"},
                    },
                },
            )
            assert created.status_code == 201
            entity_id = created.json()["id"]
            expected = {"modality": "small molecule"}
            assert created.json()["attributes"] == expected
            assert created.json()["external_ids"] == {"uniprot": "P00533"}

            stored = session.get(Entity, entity_id)
            assert stored is not None
            stored.external_ids = {
                **stored.external_ids,
                "pharmcube_target": "internal-target-hash",
                "internal_row": "internal-row-secret",
                "source_record": "source-record-secret",
            }
            stored.identity_identifiers.append(
                EntityIdentifier(
                    tenant_id=tenant.id,
                    entity_type=stored.entity_type,
                    namespace="pharmcube_target",
                    value="internal-target-hash",
                    normalized_value="internal-target-hash",
                    trusted_namespace=False,
                    review_status=ReviewStatus.VERIFIED,
                )
            )
            session.commit()
            session.expire_all()

            direct = client.get(f"/api/v1/entities/{entity_id}")
            assert direct.status_code == 200
            assert direct.json()["attributes"] == expected
            assert direct.json()["external_ids"] == {"uniprot": "P00533"}
            assert {item["namespace"] for item in direct.json()["identity_identifiers"]} == {"uniprot"}

            search = client.get("/api/v1/entities", params={"q": "External projection target"})
            assert search.status_code == 200
            assert search.json()["items"][0]["attributes"] == expected
            assert search.json()["items"][0]["external_ids"] == {"uniprot": "P00533"}

            dossier = client.get(f"/api/v1/entities/{entity_id}/dossier")
            assert dossier.status_code == 200
            dossier_payload = dossier.json()
            assert dossier_payload["entity"]["attributes"] == expected
            assert dossier_payload["entity"]["external_ids"] == {"uniprot": "P00533"}
            dossier_json = json.dumps(dossier_payload, ensure_ascii=False)
            assert "governed_ai_extraction" not in dossier_json
            assert "source_document_ids" not in dossier_json
            assert "document-internal-1" not in dossier_json
            assert "pharmcube_target" not in dossier_json
            assert "internal-target-hash" not in dossier_json
            assert "internal-row-secret" not in dossier_json
            assert "source-record-secret" not in dossier_json
    finally:
        app.dependency_overrides.clear()


def test_non_governance_principal_cannot_read_unpublished_entities(
    session: Session,
    tenant: Tenant,
) -> None:
    def session_override() -> Generator[Session]:
        yield session

    entity = EntityRepository(session, tenant.id).create(
        EntityCreate(
            entity_type="target",
            name="Unpublished visibility target",
            aliases=["Unpublished visibility alias"],
        )
    )
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=entity.id,
            modality="small molecule",
            phase=DevelopmentPhase.PHASE_1,
            geography="Global",
        )
    )
    session.flush()

    def principal_override() -> Principal:
        return Principal(
            tenant.id,
            "viewer-1",
            "user",
            frozenset(
                {
                    "entities:read",
                    "dossiers:read",
                    "targets:read",
                    "activities:read",
                    "pipelines:read",
                    "structures:read",
                    "trials:read",
                    "patents:read",
                    "deals:read",
                    "regulatory:read",
                    "epidemiology:read",
                    "news:read",
                }
            ),
        )

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            search = client.get("/api/v1/entities", params={"q": "Unpublished visibility"})
            assert search.status_code == 200
            assert search.json()["total"] == 0
            assert search.json()["items"] == []
            assert search.json()["facets"]["review_status"] == {}
            assert search.json()["applied_filters"] == [
                {"field": "q", "operator": "contains", "value": "Unpublished visibility"},
                {"field": "review_status", "operator": "eq", "value": "verified"},
            ]

            pipeline = client.get("/api/v1/pipelines", params={"q": "Unpublished visibility"})
            assert pipeline.status_code == 200
            assert pipeline.json()["total"] == 0
            assert pipeline.json()["items"] == []

            explicit_draft = client.get(
                "/api/v1/entities",
                params={"q": "Unpublished visibility", "review_status": "draft"},
            )
            assert explicit_draft.status_code == 200
            assert explicit_draft.json()["total"] == 0
            assert explicit_draft.json()["applied_filters"][-1] == {
                "field": "review_status",
                "operator": "eq",
                "value": "verified",
            }

            suggestions = client.get(
                "/api/v1/entities/suggestions",
                params={"q": "Unpublished visibility"},
            )
            assert suggestions.status_code == 200
            assert suggestions.json()["suggestions"] == []

            assert client.get(f"/api/v1/entities/{entity.id}").status_code == 404
            assert client.get(f"/api/v1/entities/{entity.id}/dossier").status_code == 404
            assert client.get(f"/api/v1/targets/{entity.id}/bioactivities").status_code == 404
            assert client.get(f"/api/v1/targets/{entity.id}/sar-comparison").status_code == 404
            assert client.get(f"/api/v1/targets/{entity.id}/competitive-programs").status_code == 404
            assert client.get("/api/v1/structures", params={"entity_id": entity.id}).status_code == 404
            assert client.get("/api/v1/clinical-trials", params={"entity_id": entity.id}).status_code == 404
            assert client.get("/api/v1/patents", params={"entity_id": entity.id}).status_code == 404
            assert client.get("/api/v1/deals", params={"entity_id": entity.id}).status_code == 404
            assert client.get("/api/v1/regulatory-events", params={"entity_id": entity.id}).status_code == 404
            assert (
                client.get(
                    "/api/v1/epidemiology-observations",
                    params={"disease_entity_id": entity.id},
                ).status_code
                == 404
            )
            assert client.get("/api/v1/news-events", params={"entity_id": entity.id}).status_code == 404

            def governance_principal_override() -> Principal:
                return Principal(
                    tenant.id,
                    "governance-1",
                    "user",
                    frozenset({"governance:read", "pipelines:read"}),
                )

            app.dependency_overrides[require_principal] = governance_principal_override
            governance_pipeline = client.get("/api/v1/pipelines", params={"q": "Unpublished visibility"})
            assert governance_pipeline.status_code == 200
            assert governance_pipeline.json()["total"] == 1
    finally:
        app.dependency_overrides.clear()


def test_authenticated_route_without_session_dependency_is_audited(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def principal_override(request: Request) -> Principal:
        principal = Principal(tenant.id, "test-key", "api_key", frozenset({"*"}))
        request.state.principal = principal
        return principal

    class ReadyGateway:
        @staticmethod
        def status() -> object:
            return type(
                "Status",
                (),
                {
                    "available": True,
                    "version": "test",
                    "cluster_name": "test",
                    "cluster_status": "green",
                    "aliases": {},
                    "error": None,
                },
            )()

    class ReadyConsumer:
        def __init__(self, *_: object) -> None:
            return None

        @staticmethod
        def delivery_counts() -> dict[str, int]:
            return {}

    monkeypatch.setattr(
        "pharma_intel.api.get_session_factory",
        lambda: sessionmaker(bind=session.get_bind(), autoflush=False, expire_on_commit=False),
    )
    monkeypatch.setattr("pharma_intel.api.get_opensearch_gateway", ReadyGateway)
    monkeypatch.setattr("pharma_intel.api.SearchProjectionConsumer", ReadyConsumer)
    monkeypatch.setattr("pharma_intel.api.object_store_module.build_object_store", lambda _: object())
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/admin/search/status")
        assert response.status_code == 200
        assert (
            session.scalar(select(AuditEvent.id).where(AuditEvent.action == "GET /api/v1/admin/search/status"))
            is not None
        )
    finally:
        app.dependency_overrides.clear()


def test_browser_security_headers_are_fail_closed_and_hsts_is_https_only() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    content_security_policy = response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in content_security_policy
    assert "script-src 'self';" in content_security_policy
    assert "unsafe-eval" not in content_security_policy
    assert "wasm-unsafe-eval" not in content_security_policy
    assert "worker-src 'self'" in content_security_policy
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["cross-origin-opener-policy"] == "same-origin"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
    assert "camera=()" in response.headers["permissions-policy"]
    assert "strict-transport-security" not in response.headers

    with TestClient(app, base_url="https://testserver") as client:
        secure_response = client.get("/health/live")
    assert secure_response.headers["strict-transport-security"] == ("max-age=63072000; includeSubDomains; preload")


def test_rdkit_worker_has_a_narrow_dedicated_content_security_policy() -> None:
    worker_policy = browser_security_headers_for_path("/assets/rdkit.worker-Ab_19.js")["Content-Security-Policy"]
    assert "default-src 'none'" in worker_policy
    assert "script-src 'self' 'unsafe-eval'" in worker_policy
    assert "connect-src 'self'" in worker_policy
    assert "worker-src" not in worker_policy

    ordinary_asset_policy = browser_security_headers_for_path("/assets/index-Ab_19.js")["Content-Security-Policy"]
    assert "unsafe-eval" not in ordinary_asset_policy


def test_indigo_worker_has_only_the_wasm_compilation_capability() -> None:
    worker_policy = browser_security_headers_for_path("/assets/indigoWorker-2c9587b1-Ab_19.js")[
        "Content-Security-Policy"
    ]
    assert "default-src 'none'" in worker_policy
    assert "script-src 'self' 'wasm-unsafe-eval'" in worker_policy
    assert "'unsafe-eval'" not in worker_policy
    assert "connect-src 'self'" in worker_policy
    assert "worker-src" not in worker_policy

    ordinary_asset_policy = browser_security_headers_for_path("/assets/indigoWorker.js")["Content-Security-Policy"]
    assert "wasm-unsafe-eval" not in ordinary_asset_policy


def test_protected_endpoint_requires_key(session: Session) -> None:
    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/entities").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_internal_api_rejects_valid_agent_api_key(session: Session, tenant: Tenant) -> None:
    secret, secret_hash = issue_api_key()
    session.add(
        ApiKey(
            tenant_id=tenant.id,
            name="MCP only",
            prefix=secret[:12],
            secret_hash=secret_hash,
            scopes=["*"],
        )
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/entities", headers={"X-API-Key": secret})
            assert response.status_code == 401
            assert response.json() == {"detail": "Authentication required"}
    finally:
        app.dependency_overrides.clear()


def test_human_login_session_and_csrf_protection(session: Session, tenant: Tenant) -> None:
    user = User(
        tenant_id=tenant.id,
        email="analyst@example.test",
        normalized_email="analyst@example.test",
        display_name="Test Analyst",
        password_hash=hash_password("correct-horse-battery-staple"),
        role=UserRole.ANALYST,
    )
    session.add(user)
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as client:
            rejected = client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": "wrong-password"},
            )
            assert rejected.status_code == 401

            authenticated = client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": "correct-horse-battery-staple"},
            )
            assert authenticated.status_code == 200
            assert authenticated.json()["role"] == "analyst"
            tracked_session = session.scalar(select(UserSession).where(UserSession.user_id == user.id))
            assert tracked_session is not None and tracked_session.revoked_at is None
            assert client.get("/api/v1/auth/me").status_code == 200
            assert client.get("/api/v1/entities").status_code == 200

            missing_csrf = client.post("/api/v1/auth/logout")
            assert missing_csrf.status_code == 403

            csrf_token = client.cookies.get(CSRF_COOKIE)
            assert csrf_token is not None
            logout = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf_token})
            assert logout.status_code == 204
            session.refresh(tracked_session)
            assert tracked_session.revoked_at is not None
            assert client.get("/api/v1/auth/me").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_human_user_can_update_profile_with_server_persistence(
    session: Session,
    tenant: Tenant,
) -> None:
    user = User(
        tenant_id=tenant.id,
        email="profile@example.test",
        normalized_email="profile@example.test",
        display_name="Profile User",
        password_hash=hash_password("profile-password"),
        role=UserRole.ANALYST,
    )
    conflict = User(
        tenant_id=tenant.id,
        email="taken@example.test",
        normalized_email="taken@example.test",
        display_name="Taken User",
        password_hash=hash_password("taken-password"),
        role=UserRole.VIEWER,
    )
    session.add_all([user, conflict])
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as client:
            assert (
                client.post(
                    "/api/v1/auth/login",
                    json={"email": user.email, "password": "profile-password"},
                ).status_code
                == 200
            )
            csrf_token = client.cookies.get(CSRF_COOKIE)
            assert csrf_token is not None

            updated = client.patch(
                "/api/v1/auth/me",
                headers={"X-CSRF-Token": csrf_token},
                json={
                    "display_name": "Updated Profile",
                    "email": "Profile.Updated@example.test",
                    "phone": "+86 138 0000 0000",
                    "avatar_url": "https://cdn.example.test/avatar.png",
                },
            )
            assert updated.status_code == 200
            assert updated.json() == {
                "id": user.id,
                "tenant_id": tenant.id,
                "email": "Profile.Updated@example.test",
                "display_name": "Updated Profile",
                "phone": "+86 138 0000 0000",
                "avatar_url": "https://cdn.example.test/avatar.png",
                "role": "analyst",
            }
            session.refresh(user)
            assert user.normalized_email == "profile.updated@example.test"
            assert user.phone == "+86 138 0000 0000"
            assert user.avatar_url == "https://cdn.example.test/avatar.png"

            assert (
                client.patch(
                    "/api/v1/auth/me",
                    headers={"X-CSRF-Token": csrf_token},
                    json={"email": "taken@example.test"},
                ).status_code
                == 409
            )
            assert (
                client.patch(
                    "/api/v1/auth/me",
                    headers={"X-CSRF-Token": csrf_token},
                    json={"avatar_url": "http://cdn.example.test/avatar.png"},
                ).status_code
                == 422
            )
            assert (
                client.patch(
                    "/api/v1/auth/me",
                    headers={"X-CSRF-Token": csrf_token},
                    json={"display_name": "???????????"},
                ).status_code
                == 422
            )
            session.refresh(user)
            assert user.display_name == "Updated Profile"
    finally:
        app.dependency_overrides.clear()


def test_password_change_keeps_current_session_and_revokes_other_sessions(
    session: Session,
    tenant: Tenant,
) -> None:
    user = User(
        tenant_id=tenant.id,
        email="password@example.test",
        normalized_email="password@example.test",
        display_name="Password User",
        password_hash=hash_password("old-password"),
        role=UserRole.ANALYST,
    )
    session.add(user)
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as current_client, TestClient(app) as other_client:
            for client in (current_client, other_client):
                assert (
                    client.post(
                        "/api/v1/auth/login",
                        json={"email": user.email, "password": "old-password"},
                    ).status_code
                    == 200
                )
            csrf_token = current_client.cookies.get(CSRF_COOKIE)
            assert csrf_token is not None

            changed = current_client.post(
                "/api/v1/auth/me/password",
                headers={"X-CSRF-Token": csrf_token},
                json={"current_password": "old-password", "new_password": "new-password-2026"},
            )
            assert changed.status_code == 204
            assert current_client.get("/api/v1/auth/me").status_code == 200
            assert other_client.get("/api/v1/auth/me").status_code == 401
            assert (
                other_client.post(
                    "/api/v1/auth/login",
                    json={"email": user.email, "password": "new-password-2026"},
                ).status_code
                == 200
            )
    finally:
        app.dependency_overrides.clear()


def test_recent_entity_visits_are_personal_deduplicated_and_permission_checked(
    session: Session,
    tenant: Tenant,
) -> None:
    first_user = User(
        tenant_id=tenant.id,
        email="recent-first@example.test",
        normalized_email="recent-first@example.test",
        display_name="Recent First",
        password_hash=hash_password("recent-first-password"),
        role=UserRole.ANALYST,
    )
    second_user = User(
        tenant_id=tenant.id,
        email="recent-second@example.test",
        normalized_email="recent-second@example.test",
        display_name="Recent Second",
        password_hash=hash_password("recent-second-password"),
        role=UserRole.ANALYST,
    )
    session.add_all([first_user, second_user])
    session.commit()
    repository = EntityRepository(session, tenant.id)
    target = repository.create(EntityCreate(entity_type="target", name="Recent target"))
    drug = repository.create(EntityCreate(entity_type="drug", name="Recent drug"))

    def session_override(request: Request) -> Generator[Session]:
        request.state.db_session = session
        yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as first_client:
            assert (
                first_client.post(
                    "/api/v1/auth/login",
                    json={"email": first_user.email, "password": "recent-first-password"},
                ).status_code
                == 200
            )
            assert first_client.get(f"/api/v1/entities/{drug.id}").status_code == 200
            assert first_client.get(f"/api/v1/targets/{target.id}/dossier").status_code == 200
            assert first_client.get(f"/api/v1/entities/{drug.id}/dossier").status_code == 200
            drug_dossier = first_client.get(f"/api/v1/drugs/{drug.id}/dossier")
            assert drug_dossier.status_code == 200
            assert drug_dossier.json()["entity"]["id"] == drug.id
            summary = drug_dossier.json()["summary"]
            assert summary == {
                "program_count": 0,
                "target_count": 0,
                "indication_count": 0,
                "organization_count": 0,
                "modalities": [],
            }
            drug_programs = first_client.get(
                f"/api/v1/drugs/{drug.id}/programs",
                params={"limit": 1, "offset": 0},
            )
            assert drug_programs.status_code == 200
            assert drug_programs.json()["query_schema_version"] == "pharma.drug.programs.v1"
            assert drug_programs.json()["items"] == []
            assert drug_programs.json()["total"] == 0
            assert drug_programs.json()["limit"] == 1
            assert drug_programs.json()["offset"] == 0
            assert first_client.get(f"/api/v1/drugs/{target.id}/dossier").status_code == 404
            assert first_client.get(f"/api/v1/drugs/{target.id}/programs").status_code == 404
            assert first_client.get("/api/v1/entities/missing").status_code == 404
            assert first_client.get("/api/v1/entities", params={"q": "Recent"}).status_code == 200
            stale_event_time = datetime.now(UTC) + timedelta(seconds=1)
            session.add_all(
                [
                    AuditEvent(
                        tenant_id=tenant.id,
                        actor_type="user",
                        actor_id=first_user.id,
                        action=f"GET /api/v1/entities/removed-{index}",
                        resource_type="research_entity",
                        resource_id=f"removed-entity-{index}",
                        outcome="success",
                        request_id=f"removed-entity-visit-{index}",
                        details={"status_code": 200},
                        occurred_at=stale_event_time + timedelta(microseconds=index),
                    )
                    for index in range(125)
                ]
            )
            session.add(
                AuditEvent(
                    tenant_id=tenant.id,
                    actor_type="user",
                    actor_id=first_user.id,
                    action="GET /api/v1/entities/removed",
                    resource_type="research_entity",
                    resource_id="removed-entity",
                    outcome="success",
                    request_id="removed-entity-visit",
                    details={"status_code": 200},
                    occurred_at=stale_event_time,
                )
            )
            session.commit()

            recent = first_client.get("/api/v1/workspace/recent-entities", params={"limit": 2})
            assert recent.status_code == 200
            assert [item["entity"]["id"] for item in recent.json()] == [drug.id, target.id]
            assert all(item["visited_at"] for item in recent.json())
            assert first_client.get("/api/v1/workspace/recent-entities", params={"limit": 21}).status_code == 422

        with TestClient(app) as second_client:
            assert (
                second_client.post(
                    "/api/v1/auth/login",
                    json={"email": second_user.email, "password": "recent-second-password"},
                ).status_code
                == 200
            )
            recent = second_client.get("/api/v1/workspace/recent-entities")
            assert recent.status_code == 200
            assert recent.json() == []
    finally:
        app.dependency_overrides.clear()


def test_domain_and_data_factory_api_contracts_cover_empty_error_and_state_paths(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(source_roots_config=str(tmp_path), temporal_enabled=False)
    monkeypatch.setattr("pharma_intel.api.get_settings", lambda: settings)
    session.add(
        TenantDataset(
            tenant_id=tenant.id,
            dataset_key="literature",
            display_name="Literature",
            license_policy=internal_evidence_license_policy(source="test"),
        )
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "contract-key", "api_key", frozenset({"*"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            capabilities = client.get("/api/v1/admin/ingestion-capabilities")
            assert capabilities.status_code == 200
            assert capabilities.json() == {
                "automatic_scheduling_enabled": False,
                "durable_workflows_enabled": False,
                "isolated_parser_enabled": False,
                "malware_scanning_enabled": False,
                "ai_governance_enabled": False,
                "ai_model_configured": False,
                "ai_model": None,
                "ai_auto_publish_threshold": 0.95,
                "allowed_folder_roots": [str(tmp_path)],
                "parseable_extensions": [
                    ".cif",
                    ".csv",
                    ".docx",
                    ".htm",
                    ".html",
                    ".json",
                    ".md",
                    ".mmcif",
                    ".mol",
                    ".nxml",
                    ".pdb",
                    ".pdf",
                    ".pptx",
                    ".sdf",
                    ".txt",
                    ".xlsx",
                    ".xml",
                ],
                "asset_only_extensions": [".cdx", ".mdb", ".moe"],
            }
            created = client.post(
                "/api/v1/entities",
                json={"entity_type": "target", "name": "EGFR", "aliases": ["ERBB1"]},
            )
            assert created.status_code == 201
            entity_id = created.json()["id"]
            assert client.get(f"/api/v1/entities/{entity_id}").status_code == 200
            dossier = client.get(f"/api/v1/entities/{entity_id}/dossier", params={"limit": 25})
            assert dossier.status_code == 200
            assert dossier.json()["entity"]["id"] == entity_id
            assert dossier.json()["warnings"] == ["暂无记录不代表全球不存在；结果受来源授权、更新时间和可见范围影响。"]
            assert {item["domain"]: item["status"] for item in dossier.json()["coverage"]} == {
                "relationships": "not_observed",
                "evidence": "not_observed",
                "activities": "not_observed",
                "programs": "not_observed",
                "clinical_trials": "not_observed",
                "patents": "not_observed",
                "deals": "not_observed",
                "regulatory_events": "not_observed",
                "news_events": "not_observed",
                "structures": "not_observed",
                "target_evidence": "not_observed",
            }
            assert client.get("/api/v1/entities/missing/dossier").status_code == 404
            assert client.get("/api/v1/entities/missing").status_code == 404
            assert (
                client.post(
                    "/api/v1/entities",
                    json={"entity_type": "target", "name": "EGFR"},
                ).status_code
                == 409
            )

            assert client.get(f"/api/v1/targets/{entity_id}/profile").status_code == 200
            target_dossier = client.get(f"/api/v1/targets/{entity_id}/dossier", params={"limit": 25})
            assert target_dossier.status_code == 200
            assert target_dossier.json()["profile"]["entity"]["id"] == entity_id
            assert target_dossier.json()["entity"]["id"] == entity_id
            assert client.get("/api/v1/targets/missing/profile").status_code == 404
            assert client.get("/api/v1/targets/missing/dossier").status_code == 404
            empty_paths = [
                f"/api/v1/targets/{entity_id}/bioactivities?standard_type=IC50",
                f"/api/v1/targets/{entity_id}/competitive-programs",
                f"/api/v1/structures?entity_id={entity_id}",
                f"/api/v1/clinical-trials?entity_id={entity_id}&q=phase",
                f"/api/v1/patents?entity_id={entity_id}&q=WO2026",
                f"/api/v1/deals?entity_id={entity_id}",
                f"/api/v1/regulatory-events?entity_id={entity_id}&agency=FDA",
            ]
            for path in empty_paths:
                response = client.get(path)
                assert response.status_code == 200
                assert response.json() == []
            pipeline_response = client.get(
                "/api/v1/pipelines?q=EGFR&phase=phase_1&sort_by=drug_name&sort_direction=asc"
                "&landscape_limit=50&landscape_stage_scope=global"
                "&landscape_target_aggregation=primary&limit=25"
            )
            assert pipeline_response.status_code == 200
            assert pipeline_response.json()["items"] == []
            assert pipeline_response.json()["total"] == 0
            assert pipeline_response.json()["limit"] == 25
            assert pipeline_response.json()["query_schema_version"] == "pharma.pipeline.search.v13"
            assert pipeline_response.json()["sort_by"] == "drug_name"
            assert pipeline_response.json()["sort_direction"] == "asc"
            assert pipeline_response.json()["result_grain"] == "program"
            assert pipeline_response.json()["project_total"] == 0
            assert pipeline_response.json()["landscape"] == {
                "total_programs": 0,
                "distinct_drugs": 0,
                "distinct_targets": 0,
                "distinct_diseases": 0,
                "distinct_organizations": 0,
                "limit": 50,
                "stage_scope": "global",
                "target_aggregation": "primary",
                "overall_phase": [],
                "global_phase": [],
                "china_phase": [],
                "targets": [],
                "diseases": [],
                "target_combinations": [],
                "modality": [],
                "geography": [],
                "organizations": [],
            }
            assert client.get("/api/v1/pipelines?phase=not-a-phase").status_code == 422
            assert client.get("/api/v1/pipelines?sort_by=unknown").status_code == 422
            assert client.get("/api/v1/pipelines?sort_direction=sideways").status_code == 422
            assert client.get("/api/v1/pipelines?sort_by=mechanism_of_action").status_code == 200
            assert client.get("/api/v1/pipelines?landscape_limit=201").status_code == 422
            assert client.get("/api/v1/pipelines?landscape_stage_scope=us").status_code == 422
            assert client.get("/api/v1/pipelines?landscape_target_aggregation=secondary").status_code == 422
            assert client.get("/api/v1/pipelines?global_phase=not-a-phase").status_code == 422
            assert client.get("/api/v1/pipelines?target_combination_key=not-a-target-set").status_code == 422
            assert client.get("/api/v1/pipelines?organization_role=partner").status_code == 422
            drug_grain_response = client.get("/api/v1/pipelines?result_grain=drug")
            assert drug_grain_response.status_code == 200
            assert drug_grain_response.json()["result_grain"] == "drug"
            assert drug_grain_response.json()["project_total"] == 0
            assert client.get("/api/v1/pipelines?result_grain=indication").status_code == 422
            assert (
                client.get(
                    "/api/v1/pipelines?has_clinical_results=false&clinical_result_evaluation=positive"
                ).status_code
                == 422
            )
            assert client.get("/api/v1/pipelines?has_deal=false&deal_currency=USD").status_code == 422
            assert client.get("/api/v1/pipelines?deal_currency=usd").status_code == 422
            assert client.get("/api/v1/pipelines?deal_total_potential_amount_min=1").status_code == 422
            assert (
                client.get(
                    "/api/v1/pipelines?deal_currency=USD&deal_total_potential_amount_min=2"
                    "&deal_total_potential_amount_max=1"
                ).status_code
                == 422
            )
            assert (
                client.get(
                    "/api/v1/pipelines?global_phase_started_from=2026-07-02T00:00:00Z"
                    "&global_phase_started_to=2026-07-01T00:00:00Z"
                ).status_code
                == 422
            )
            assert (
                client.get(
                    "/api/v1/pipelines?milestone_from=2026-07-02T00:00:00Z&milestone_to=2026-07-01T00:00:00Z"
                ).status_code
                == 422
            )
            trial_response = client.get(
                "/api/v1/trials?q=EGFR&registry=ClinicalTrials.gov&status=RECRUITING&phase=PHASE2"
                "&linked_drug_modality=antibody&linked_drug_innovation_type=innovative"
                "&linked_drug_category=biologic&linked_drug_program_tag=first_in_class"
                "&linked_drug_global_phase=phase_3&linked_drug_organization_country_region=CN"
                "&sort_by=registry_id&sort_direction=asc&limit=25"
            )
            assert trial_response.status_code == 200
            assert trial_response.json()["items"] == []
            assert trial_response.json()["total"] == 0
            assert trial_response.json()["limit"] == 25
            assert trial_response.json()["query_schema_version"] == "pharma.clinical_trial.search.v10"
            assert trial_response.json()["sort_by"] == "registry_id"
            assert trial_response.json()["sort_direction"] == "asc"
            assert trial_response.json()["facets"] == {
                "registry": {},
                "overall_status": {},
                "study_type": {},
                "initiation_type": {},
                "phase": {},
                "therapy_line": {},
                "has_results": {},
                "result_evaluation": {},
                "has_key_result": {},
            }
            assert trial_response.json()["applied_filters"][-6:] == [
                {"field": "linked_drug_modality", "operator": "in", "value": ["antibody"]},
                {"field": "linked_drug_innovation_type", "operator": "in", "value": ["innovative"]},
                {"field": "linked_drug_category", "operator": "in", "value": ["biologic"]},
                {"field": "linked_drug_program_tag", "operator": "in", "value": ["first_in_class"]},
                {"field": "linked_drug_global_phase", "operator": "eq", "value": "phase_3"},
                {
                    "field": "linked_drug_organization_country_region",
                    "operator": "eq",
                    "value": "CN",
                },
            ]
            assert client.get("/api/v1/trials?offset=100001").status_code == 422
            assert client.get("/api/v1/trials?sort_by=unknown").status_code == 422
            patent_response = client.get(
                "/api/v1/patent-families?q=EGFR&applicant=Victor%20Therapeutics&legal_status=ACTIVE"
                "&sort_by=family_identifier&sort_direction=asc&limit=25"
            )
            assert patent_response.status_code == 200
            assert patent_response.json()["items"] == []
            assert patent_response.json()["total"] == 0
            assert patent_response.json()["limit"] == 25
            assert patent_response.json()["sort_by"] == "family_identifier"
            assert patent_response.json()["sort_direction"] == "asc"
            assert patent_response.json()["facets"] == {"legal_status": {}, "applicant": {}}
            assert client.get("/api/v1/patent-families?offset=100001").status_code == 422
            assert client.get("/api/v1/patent-families?sort_direction=sideways").status_code == 422
            deal_response = client.get(
                "/api/v1/deal-transactions?q=EGFR&deal_type=license&territory=global&party=Victor%20Therapeutics"
                "&sort_by=name&sort_direction=asc&limit=25"
            )
            assert deal_response.status_code == 200
            assert deal_response.json()["items"] == []
            assert deal_response.json()["total"] == 0
            assert deal_response.json()["limit"] == 25
            assert deal_response.json()["sort_by"] == "name"
            assert deal_response.json()["sort_direction"] == "asc"
            assert deal_response.json()["facets"] == {
                "asset": {},
                "target": {},
                "disease": {},
                "asset_modality": {},
                "asset_program_tag": {},
                "deal_type": {},
                "status": {},
                "direction": {},
                "territory": {},
                "currency": {},
                "party": {},
                "party_role": {},
                "party_country_region": {},
                "party_organization_type": {},
                "development_phase_at_transaction": {},
                "current_development_phase": {},
                "right_type": {},
                "rights_territory": {},
            }
            assert client.get("/api/v1/deal-transactions?offset=100001").status_code == 422
            assert client.get("/api/v1/deal-transactions?sort_by=unknown").status_code == 422
            assert client.get("/api/v1/deal-transactions?sort_by=upfront_amount").status_code == 422
            regulatory_response = client.get(
                "/api/v1/regulatory-event-timeline"
                "?q=EGFR&agency=FDA&jurisdiction=US&event_type=approval&status=approved"
                "&sort_by=subject&sort_direction=asc&limit=25"
            )
            assert regulatory_response.status_code == 200
            assert regulatory_response.json()["items"] == []
            assert regulatory_response.json()["total"] == 0
            assert regulatory_response.json()["limit"] == 25
            assert regulatory_response.json()["sort_by"] == "subject"
            assert regulatory_response.json()["sort_direction"] == "asc"
            assert regulatory_response.json()["facets"] == {
                "agency": {},
                "jurisdiction": {},
                "event_type": {},
                "status": {},
                "designation_type": {},
                "label_change_type": {},
                "has_boxed_warning": {},
                "safety_signal_type": {},
                "safety_severity": {},
                "safety_status": {},
            }
            assert client.get("/api/v1/regulatory-event-timeline?offset=100001").status_code == 422
            assert client.get("/api/v1/regulatory-event-timeline?sort_by=unknown").status_code == 422
            assert (
                client.get(
                    "/api/v1/regulatory-event-timeline"
                    "?decision_from=2026-03-01T00:00:00Z&decision_to=2026-02-01T00:00:00Z"
                ).status_code
                == 422
            )
            assert client.get(f"/api/v1/regulatory-event-timeline/{entity_id}").status_code == 404
            epidemiology_response = client.get(
                "/api/v1/epidemiology-observations"
                "?q=NSCLC&measure=prevalence&geography=China&unit=patients"
                "&population_scope=adults&age_group=18%2B&sex=all"
                "&sort_by=value&sort_direction=asc&limit=25"
            )
            assert epidemiology_response.status_code == 200
            assert epidemiology_response.json()["items"] == []
            assert epidemiology_response.json()["total"] == 0
            assert epidemiology_response.json()["limit"] == 25
            assert epidemiology_response.json()["sort_by"] == "value"
            assert epidemiology_response.json()["sort_direction"] == "asc"
            assert epidemiology_response.json()["facets"] == {
                "measure": {},
                "geography": {},
                "unit": {},
                "population_scope": {},
                "age_group": {},
                "sex": {},
                "disease": {},
                "publisher": {},
            }
            assert client.get("/api/v1/epidemiology-observations?offset=100001").status_code == 422
            assert client.get("/api/v1/epidemiology-observations?sort_by=unknown").status_code == 422
            assert client.get(f"/api/v1/epidemiology-trends/{entity_id}").status_code == 404
            assert client.get("/api/v1/epidemiology-trends/missing").status_code == 404
            news_response = client.get(
                "/api/v1/news-events"
                "?q=Compound%20A&event_type=corporate_announcement&publisher=Acme%20Pharma"
                "&language=en&venue=ASCO%202026&published_from=2026-01-01&published_to=2026-12-31"
                "&sort_by=title&sort_direction=asc&limit=25"
            )
            assert news_response.status_code == 200
            assert news_response.json()["items"] == []
            assert news_response.json()["total"] == 0
            assert news_response.json()["limit"] == 25
            assert news_response.json()["sort_by"] == "title"
            assert news_response.json()["sort_direction"] == "asc"
            assert news_response.json()["facets"] == {
                "event_type": {},
                "language": {},
                "venue": {},
                "publisher": {},
            }
            assert client.get("/api/v1/news-events?offset=100001").status_code == 422
            assert client.get("/api/v1/news-events?sort_by=unknown").status_code == 422

            multi_sort_cases = {
                "/api/v1/entities": ["entity_type:asc", "name:desc"],
                "/api/v1/pipelines": ["phase:desc", "drug_name:asc"],
                "/api/v1/trials": ["overall_status:asc", "registry_id:desc"],
                "/api/v1/patent-families": ["legal_status:asc", "family_identifier:desc"],
                "/api/v1/deal-transactions": ["status:asc", "name:desc"],
                "/api/v1/regulatory-event-timeline": ["agency:asc", "subject:desc"],
                "/api/v1/epidemiology-observations": ["measure:asc", "value:desc"],
                "/api/v1/news-events": ["event_type:asc", "title:desc"],
            }
            for path, sort_tokens in multi_sort_cases.items():
                multi_sort_response = client.get(path, params=[("sort", token) for token in sort_tokens])
                assert multi_sort_response.status_code == 200, (path, multi_sort_response.json())
                assert multi_sort_response.json()["sort"] == [
                    {"field": token.split(":", 1)[0], "direction": token.split(":", 1)[1]} for token in sort_tokens
                ]
                assert multi_sort_response.json()["sort_by"] == sort_tokens[0].split(":", 1)[0]
                assert multi_sort_response.json()["sort_direction"] == sort_tokens[0].split(":", 1)[1]

            assert client.get("/api/v1/entities", params={"sort": "unknown:asc"}).status_code == 422
            assert (
                client.get(
                    "/api/v1/entities",
                    params=[("sort", "name:asc"), ("sort", "name:desc")],
                ).status_code
                == 422
            )
            assert (
                client.get(
                    "/api/v1/pipelines",
                    params=[
                        ("sort", "status_date:desc"),
                        ("sort", "drug_name:asc"),
                        ("sort", "target_name:asc"),
                        ("sort", "disease_name:asc"),
                        ("sort", "organization_name:asc"),
                        ("sort", "modality:asc"),
                    ],
                ).status_code
                == 422
            )
            assert (
                client.get(
                    "/api/v1/entities",
                    params=[
                        ("sort", "name:asc"),
                        ("sort_by", "updated_at"),
                        ("sort_direction", "desc"),
                    ],
                ).status_code
                == 422
            )
            assert client.get("/api/v1/entities", params={"sort": "name:sideways"}).status_code == 422
            assert (
                client.get(
                    "/api/v1/deal-transactions",
                    params=[("sort", "name:asc"), ("sort", "upfront_amount:desc")],
                ).status_code
                == 422
            )
            assert (
                client.get(
                    "/api/v1/deal-transactions",
                    params=[("currency", "USD"), ("sort", "name:asc"), ("sort", "upfront_amount:desc")],
                ).status_code
                == 200
            )

            assert (
                client.post(
                    "/api/v1/evidence/search",
                    json={"query": "EGFR", "dataset_keys": ["unknown"], "limit": 5},
                ).status_code
                == 422
            )
            assert client.post("/api/v1/research-bundles", json={}).status_code == 404
            assert client.get("/api/v1/research-bundles/missing").status_code == 404
            assert client.get("/api/v1/research-bundles/missing/report.pptx").status_code == 404

            invalid_source = {
                "name": "Invalid",
                "root_uri": "relative/source",
                "dataset_key": "literature",
            }
            assert client.post("/api/v1/admin/data-sources", json=invalid_source).status_code == 422
            source_payload = {
                "name": "Literature",
                "root_uri": str(tmp_path),
                "owner": "Research Operations",
                "authorization_scopes": ["contract:test-literature"],
                "dataset_key": "literature",
                "stable_seconds": 0,
                "scan_interval_seconds": 60,
            }
            source_response = client.post("/api/v1/admin/data-sources", json=source_payload)
            assert source_response.status_code == 201
            source_id = source_response.json()["id"]
            assert source_response.json()["owner"] == "Research Operations"
            valid_from = datetime.fromisoformat(
                source_response.json()["authorization_valid_from"].replace("Z", "+00:00")
            )
            assert valid_from.utcoffset() == timedelta(0)
            assert source_response.json()["authorization_valid_until"] is None
            assert "credential_ref" not in source_response.json()
            assert client.post("/api/v1/admin/data-sources", json=source_payload).status_code == 409
            assert len(client.get("/api/v1/admin/data-sources").json()) == 1
            datasets = client.get("/api/v1/admin/data-source-datasets").json()
            assert datasets[0]["license_current"] is True
            readiness = client.get("/api/v1/admin/data-source-readiness").json()
            assert readiness[0]["configuration_ready"] is True
            assert readiness[0]["operational_status"] == "pending"
            now = datetime.now(UTC)
            expired = client.patch(
                f"/api/v1/admin/data-sources/{source_id}",
                json={
                    "authorization_valid_from": (now - timedelta(days=2)).isoformat(),
                    "authorization_valid_until": (now - timedelta(days=1)).isoformat(),
                },
            )
            assert expired.status_code == 200
            readiness = client.get("/api/v1/admin/data-source-readiness").json()
            assert readiness[0]["configuration_ready"] is False
            assert any(check["code"] == "authorization_expired" for check in readiness[0]["checks"])
            renewed = client.patch(
                f"/api/v1/admin/data-sources/{source_id}",
                json={
                    "authorization_valid_from": (now - timedelta(minutes=1)).isoformat(),
                    "authorization_valid_until": (now + timedelta(days=365)).isoformat(),
                },
            )
            assert renewed.status_code == 200
            assert client.get("/api/v1/admin/data-source-readiness").json()[0]["configuration_ready"] is True
            invalid_window = client.patch(
                f"/api/v1/admin/data-sources/{source_id}",
                json={
                    "authorization_valid_from": now.isoformat(),
                    "authorization_valid_until": now.isoformat(),
                },
            )
            assert invalid_window.status_code == 422
            assert (
                client.patch(
                    f"/api/v1/admin/data-sources/{source_id}",
                    json={"authorization_valid_from": "2026-07-19T00:00:00"},
                ).status_code
                == 422
            )
            assert (
                client.patch(
                    f"/api/v1/admin/data-sources/{source_id}",
                    json={"authorization_valid_from": None},
                ).status_code
                == 422
            )
            perpetual = client.patch(
                f"/api/v1/admin/data-sources/{source_id}",
                json={"authorization_valid_until": None},
            )
            assert perpetual.status_code == 200
            assert perpetual.json()["authorization_valid_until"] is None
            assert client.get("/api/v1/admin/data-source-readiness").json()[0]["configuration_ready"] is True
            audit_actions = set(
                session.scalars(
                    select(AuditEvent.action).where(
                        AuditEvent.resource_type == "data_source",
                        AuditEvent.resource_id == source_id,
                    )
                )
            )
            assert {"data_source.create", "data_source.authorization.update"} <= audit_actions
            governed = client.patch(
                f"/api/v1/admin/data-sources/{source_id}",
                json={"owner": "Scientific Data Governance", "data_classification": "confidential"},
            )
            assert governed.status_code == 200
            assert governed.json()["owner"] == "Scientific Data Governance"
            assert governed.json()["config_version"] == 5
            assert (
                client.patch(
                    f"/api/v1/admin/data-sources/{source_id}",
                    json={"root_uri": str(tmp_path.parent / "outside-source-root")},
                ).status_code
                == 422
            )
            assert client.patch("/api/v1/admin/data-sources/missing", json={"owner": "Owner"}).status_code == 404
            updated = client.patch(
                f"/api/v1/admin/data-sources/{source_id}/state",
                json={"state": "paused"},
            )
            assert updated.status_code == 200
            assert updated.json()["state"] == "paused"
            assert (
                client.patch(
                    "/api/v1/admin/data-sources/missing/state",
                    json={"state": "disabled"},
                ).status_code
                == 404
            )
            assert client.post(f"/api/v1/admin/data-sources/{source_id}/scan").status_code == 409
            resumed = client.patch(
                f"/api/v1/admin/data-sources/{source_id}/state",
                json={"state": "active"},
            )
            assert resumed.status_code == 200
            assert client.post(f"/api/v1/admin/data-sources/{source_id}/scan").status_code == 503
            assert client.get(f"/api/v1/admin/ingestion-runs?data_source_id={source_id}").json() == []
            assert client.get("/api/v1/admin/ingestion-runs/missing/findings").json() == []

            assert client.get("/api/v1/governance/review-queue").json() == []
            assert (
                client.post(
                    "/api/v1/governance/staged-facts/missing/decision",
                    json={"decision": "reject", "notes": "unsupported"},
                ).status_code
                == 403
            )
            assert client.get("/api/v1/knowledge/pages?q=EGFR&page_type=target").json() == []
            assert client.get("/api/v1/knowledge/pages/missing").status_code == 404
            assert client.get("/api/v1/news-events?content_scope=research").status_code == 200
            assert client.get("/api/v1/news-events?content_scope=unsupported").status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_http_manifest_source_registration_is_allowlisted_and_never_exposes_credentials(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPPLIER_API_TOKEN", "registration-only-token")
    settings = Settings(
        source_roots_config=str(tmp_path),
        source_credential_env_allowlist_config="SUPPLIER_API_TOKEN",
        source_http_allowed_origins_config="https://supplier.example",
    )
    monkeypatch.setattr("pharma_intel.api.get_settings", lambda: settings)
    session.add(
        TenantDataset(
            tenant_id=tenant.id,
            dataset_key="literature",
            display_name="Literature",
            license_policy=internal_evidence_license_policy(source="test"),
        )
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "contract-key", "api_key", frozenset({"*"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    payload = {
        "name": "Licensed supplier",
        "source_type": "http_manifest",
        "root_uri": "https://supplier.example/v1/manifest",
        "credential_ref": "env://SUPPLIER_API_TOKEN",
        "owner": "Scientific Data Operations",
        "authorization_scopes": ["contract:supplier-2026"],
        "dataset_key": "literature",
        "stable_seconds": 0,
        "scan_interval_seconds": 60,
    }
    try:
        with TestClient(app) as client:
            created = client.post("/api/v1/admin/data-sources", json=payload)
            assert created.status_code == 201
            body = created.json()
            assert body["source_type"] == "http_manifest"
            assert body["credential_configured"] is True
            assert "credential_ref" not in body
            assert "registration-only-token" not in created.text

            disallowed_origin = {**payload, "name": "Unapproved", "root_uri": "https://other.example/manifest"}
            response = client.post("/api/v1/admin/data-sources", json=disallowed_origin)
            assert response.status_code == 422
            assert "SOURCE_HTTP_ALLOWED_ORIGINS" in response.text

            disallowed_credential = {
                **payload,
                "name": "Credential exfiltration",
                "credential_ref": "env://DATABASE_URL",
            }
            response = client.post("/api/v1/admin/data-sources", json=disallowed_credential)
            assert response.status_code == 422
            assert "SOURCE_CREDENTIAL_ENV_ALLOWLIST" in response.text

            source_id = body["id"]
            assert (
                client.patch(
                    f"/api/v1/admin/data-sources/{source_id}",
                    json={"credential_ref": None},
                ).status_code
                == 422
            )
    finally:
        app.dependency_overrides.clear()


def test_public_research_source_registration_preserves_governed_routing_rules(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        source_roots_config=str(tmp_path),
        source_ncbi_tool="pharma-platform-tests",
    )
    monkeypatch.setattr("pharma_intel.api.get_settings", lambda: settings)
    session.add(
        TenantDataset(
            tenant_id=tenant.id,
            dataset_key="literature",
            display_name="Literature",
            license_policy=internal_evidence_license_policy(source="test"),
        )
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "contract-key", "api_key", frozenset({"*"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    pubmed_routing_rule: dict[str, object] = {
        "query_term": "EGFR AND lung cancer",
        "max_records": 150,
        "page_size": 100,
        "include_abstract": True,
    }
    pubmed_payload = {
        "name": "EGFR PubMed",
        "source_type": "pubmed",
        "root_uri": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
        "owner": "Scientific Data Operations",
        "data_classification": "public",
        "authorization_scopes": ["public:ncbi-pubmed-metadata", "public:ncbi-pubmed-abstracts"],
        "dataset_key": "literature",
        "routing_rules": [pubmed_routing_rule],
        "stable_seconds": 0,
        "scan_interval_seconds": 300,
        "rate_limit_per_minute": 60,
    }
    trials_payload = {
        "name": "EGFR ClinicalTrials.gov",
        "source_type": "clinicaltrials_gov",
        "root_uri": "https://clinicaltrials.gov/api/v2/studies",
        "owner": "Clinical Intelligence",
        "data_classification": "public",
        "authorization_scopes": ["public:clinicaltrials-gov"],
        "dataset_key": "literature",
        "routing_rules": [
            {
                "query_term": "AREA[ConditionSearch]lung cancer AND AREA[InterventionSearch]EGFR",
                "max_records": 200,
                "page_size": 100,
                "sort": "LastUpdatePostDate:desc",
            }
        ],
        "stable_seconds": 0,
        "scan_interval_seconds": 300,
        "rate_limit_per_minute": 60,
    }
    try:
        with TestClient(app) as client:
            pubmed = client.post("/api/v1/admin/data-sources", json=pubmed_payload)
            assert pubmed.status_code == 201, pubmed.text
            assert pubmed.json()["routing_rules"] == pubmed_payload["routing_rules"]
            assert pubmed.json()["credential_configured"] is False

            trials = client.post("/api/v1/admin/data-sources", json=trials_payload)
            assert trials.status_code == 201, trials.text
            assert trials.json()["routing_rules"] == trials_payload["routing_rules"]
            assert trials.json()["credential_configured"] is False

            pubmed_source = session.get(DataSource, pubmed.json()["id"])
            assert pubmed_source is not None
            pubmed_source.connector_cursor = {"stale": True}
            session.commit()

            replacement_rules = [
                {
                    "query_term": "KRAS AND NSCLC",
                    "max_records": 80,
                    "page_size": 40,
                    "include_abstract": False,
                }
            ]
            updated = client.patch(
                f"/api/v1/admin/data-sources/{pubmed_source.id}",
                json={"routing_rules": replacement_rules},
            )
            assert updated.status_code == 200
            assert updated.json()["routing_rules"] == replacement_rules
            session.refresh(pubmed_source)
            assert pubmed_source.connector_cursor == {}
            assert pubmed_source.last_cursor_at is None

            session.add(
                SourceAsset(
                    tenant_id=tenant.id,
                    data_source_id=pubmed_source.id,
                    logical_path="articles/12345.md",
                    source_uri="https://pubmed.ncbi.nlm.nih.gov/12345/",
                    file_name="12345.md",
                    extension=".md",
                    processing_mode="parse",
                )
            )
            session.commit()
            blocked = client.patch(
                f"/api/v1/admin/data-sources/{pubmed_source.id}",
                json={"routing_rules": [{**replacement_rules[0], "query_term": "ALK AND NSCLC"}]},
            )
            assert blocked.status_code == 409
            assert "routing-rule changes require a governed source migration" in blocked.text

            invalid = client.post(
                "/api/v1/admin/data-sources",
                json={
                    **pubmed_payload,
                    "name": "Unbounded PubMed",
                    "routing_rules": [{**pubmed_routing_rule, "max_records": 1001}],
                },
            )
            assert invalid.status_code == 422
            assert "max_records" in invalid.text
    finally:
        app.dependency_overrides.clear()


def test_s3_snapshot_source_registration_is_allowlisted_and_never_exposes_credentials(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential_name = "SUPPLIER_S3_CREDENTIALS"
    secret_value = json.dumps(
        {"access_key_id": "supplier-access", "secret_access_key": "supplier-secret"},  # noqa: S106
        separators=(",", ":"),
    )
    monkeypatch.setenv(credential_name, secret_value)
    settings = Settings(
        source_roots_config=str(tmp_path),
        source_credential_env_allowlist_config=credential_name,
        source_s3_allowed_buckets_config="licensed-supplier",
    )
    monkeypatch.setattr("pharma_intel.api.get_settings", lambda: settings)
    session.add(
        TenantDataset(
            tenant_id=tenant.id,
            dataset_key="literature",
            display_name="Literature",
            license_policy=internal_evidence_license_policy(source="test"),
        )
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "contract-key", "api_key", frozenset({"*"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    payload = {
        "name": "Supplier data lake",
        "source_type": "s3_snapshot",
        "root_uri": "s3://licensed-supplier/research/",
        "credential_ref": f"env://{credential_name}",
        "owner": "Scientific Data Operations",
        "authorization_scopes": ["contract:supplier-s3-2026"],
        "dataset_key": "literature",
        "stable_seconds": 0,
        "scan_interval_seconds": 60,
    }
    try:
        with TestClient(app) as client:
            created = client.post("/api/v1/admin/data-sources", json=payload)
            assert created.status_code == 201
            body = created.json()
            assert body["source_type"] == "s3_snapshot"
            assert body["root_uri"] == "s3://licensed-supplier/research/"
            assert body["credential_configured"] is True
            assert "credential_ref" not in body
            assert "supplier-secret" not in created.text

            disallowed_bucket = {
                **payload,
                "name": "Unapproved S3",
                "root_uri": "s3://unapproved-supplier/research/",
            }
            response = client.post("/api/v1/admin/data-sources", json=disallowed_bucket)
            assert response.status_code == 422
            assert "SOURCE_S3_ALLOWED_BUCKETS" in response.text
    finally:
        app.dependency_overrides.clear()


def test_sftp_snapshot_source_registration_requires_host_trust_and_never_exposes_credentials(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential_name = "SUPPLIER_SFTP_CREDENTIALS"
    secret_value = json.dumps(
        {"username": "source-user", "password": "supplier-password"},  # noqa: S106
        separators=(",", ":"),
    )
    monkeypatch.setenv(credential_name, secret_value)
    host_key = paramiko.RSAKey.generate(1024)
    known_hosts = tmp_path / "known_hosts"
    known_hosts.write_text(
        f"supplier.example {host_key.get_name()} {host_key.get_base64()}\n",
        encoding="ascii",
    )
    settings = Settings(
        source_roots_config=str(tmp_path),
        source_credential_env_allowlist_config=credential_name,
        source_sftp_allowed_origins_config="sftp://supplier.example:22",
        source_sftp_known_hosts_path=str(known_hosts),
        source_sftp_allow_password_auth=True,
    )
    monkeypatch.setattr("pharma_intel.api.get_settings", lambda: settings)
    session.add(
        TenantDataset(
            tenant_id=tenant.id,
            dataset_key="literature",
            display_name="Literature",
            license_policy=internal_evidence_license_policy(source="test"),
        )
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "contract-key", "api_key", frozenset({"*"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    payload = {
        "name": "Supplier SFTP delivery",
        "source_type": "sftp_snapshot",
        "root_uri": "sftp://supplier.example:22/delivery/",
        "credential_ref": f"env://{credential_name}",
        "owner": "Scientific Data Operations",
        "authorization_scopes": ["contract:supplier-sftp-2026"],
        "dataset_key": "literature",
        "stable_seconds": 0,
        "scan_interval_seconds": 60,
    }
    try:
        with TestClient(app) as client:
            created = client.post("/api/v1/admin/data-sources", json=payload)
            assert created.status_code == 201
            body = created.json()
            assert body["source_type"] == "sftp_snapshot"
            assert body["root_uri"] == "sftp://supplier.example:22/delivery/"
            assert body["credential_configured"] is True
            assert "credential_ref" not in body
            assert "supplier-password" not in created.text

            response = client.post(
                "/api/v1/admin/data-sources",
                json={**payload, "name": "Unapproved SFTP", "root_uri": "sftp://unapproved.example:22/data/"},
            )
            assert response.status_code == 422
            assert "SOURCE_SFTP_ALLOWED_ORIGINS" in response.text
    finally:
        app.dependency_overrides.clear()


def test_smb_snapshot_source_registration_requires_allowlisted_encrypted_origin_and_hides_credentials(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential_name = "ENTERPRISE_SMB_CREDENTIALS"
    secret_value = json.dumps(
        {"username": "source-user", "password": "enterprise-share-password"},  # noqa: S106
        separators=(",", ":"),
    )
    monkeypatch.setenv(credential_name, secret_value)
    settings = Settings(
        source_roots_config=str(tmp_path),
        source_credential_env_allowlist_config=credential_name,
        source_smb_allowed_origins_config="smb://fileserver.example:445",
        source_smb_require_encryption=True,
    )
    monkeypatch.setattr("pharma_intel.api.get_settings", lambda: settings)
    session.add(
        TenantDataset(
            tenant_id=tenant.id,
            dataset_key="literature",
            display_name="Literature",
            license_policy=internal_evidence_license_policy(source="test"),
        )
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "contract-key", "api_key", frozenset({"*"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    payload = {
        "name": "Enterprise research share",
        "source_type": "smb_snapshot",
        "root_uri": "smb://fileserver.example:445/research/delivery/",
        "credential_ref": f"env://{credential_name}",
        "owner": "Scientific Data Operations",
        "authorization_scopes": ["contract:enterprise-smb-2026"],
        "dataset_key": "literature",
        "stable_seconds": 0,
        "scan_interval_seconds": 60,
    }
    try:
        with TestClient(app) as client:
            created = client.post("/api/v1/admin/data-sources", json=payload)
            assert created.status_code == 201
            body = created.json()
            assert body["source_type"] == "smb_snapshot"
            assert body["root_uri"] == "smb://fileserver.example:445/research/delivery/"
            assert body["credential_configured"] is True
            assert "credential_ref" not in body
            assert "enterprise-share-password" not in created.text

            response = client.post(
                "/api/v1/admin/data-sources",
                json={
                    **payload,
                    "name": "Unapproved SMB",
                    "root_uri": "smb://unapproved.example:445/research/",
                },
            )
            assert response.status_code == 422
            assert "SOURCE_SMB_ALLOWED_ORIGINS" in response.text
    finally:
        app.dependency_overrides.clear()


def test_web_evidence_search_hides_internal_projection_details(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session.add(
        TenantDataset(
            tenant_id=tenant.id,
            dataset_key="web-literature",
            display_name="Web Literature",
            required_scopes=["evidence:read"],
            license_policy=internal_evidence_license_policy(source="web-projection-test"),
        )
    )
    session.commit()

    class Gateway:
        @staticmethod
        def search_evidence(
            tenant_id: str,
            query: str,
            dataset_keys: list[str],
            limit: int,
            offset: int = 0,
        ) -> list[EvidenceMatch]:
            assert tenant_id == tenant.id
            assert query == "EGFR"
            assert dataset_keys == ["web-literature"]
            assert limit == 2
            assert offset == 0
            return [
                EvidenceMatch(
                    content="Internal source excerpt",
                    document_id="private-document-id",
                    document_name="internal-note.md",
                    dataset_key="web-literature",
                    score=7.25,
                    positions=[{"page": 2}],
                    metadata={
                        "source": "file:///controlled/internal-note.md",
                        "source_version_id": "private-version-id",
                        "content_sha256": "a" * 64,
                        "evidence_claim_id": "private-claim-id",
                        "subject_entity_id": "private-subject-id",
                        "review_status": "verified",
                    },
                ),
                EvidenceMatch(
                    content="Public source excerpt",
                    document_id="public-document-id",
                    document_name="public-study.json",
                    dataset_key="web-literature",
                    score=3.5,
                    positions=[{"section": "summary"}],
                    metadata={
                        "source": "https://example.test/studies/EGFR",
                        "source_version_id": "another-private-version-id",
                        "content_sha256": "b" * 64,
                    },
                ),
            ]

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "external-viewer",
        "user",
        frozenset({"evidence:read"}),
    )
    monkeypatch.setattr("pharma_intel.api.get_settings", lambda: Settings(search_semantic_enabled=True))
    monkeypatch.setattr("pharma_intel.api.get_opensearch_gateway", lambda: Gateway())
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/evidence/search",
                json={"query": "EGFR", "dataset_keys": ["web-literature"], "limit": 2},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["engine"] == "evidence"
        assert body["chunks"][0]["similarity"] is None
        assert body["chunks"][0]["document_id"].startswith("citation-")
        assert body["chunks"][0]["metadata"] == {"license": {"attribution": "Tenant-provided source material"}}
        assert body["chunks"][1]["metadata"] == {
            "source": "https://example.test/studies/EGFR",
            "license": {"attribution": "Tenant-provided source material"},
        }
        for private_value in (
            "private-document-id",
            "public-document-id",
            "file:///controlled/internal-note.md",
            "private-version-id",
            "private-claim-id",
            "private-subject-id",
            "tenant-owned-internal",
            "opensearch",
        ):
            assert private_value not in response.text
    finally:
        app.dependency_overrides.clear()


def test_evidence_search_applies_dataset_license_and_hides_private_projection_ids(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session.add(
        TenantDataset(
            tenant_id=tenant.id,
            dataset_key="licensed-literature",
            display_name="Licensed Literature",
            ragflow_dataset_id="private-ragflow-dataset-id",
            required_scopes=["evidence:read"],
            license_policy={
                "schema_version": "1.0",
                "license_id": "abstract-license-1",
                "policy_version": "contract-v1",
                "permitted_channels": ["mcp"],
                "allowed_fields": ["content"],
                "max_content_chars": 4,
                "attribution": "Abstract-only source",
            },
        )
    )
    session.commit()

    class Gateway:
        @staticmethod
        def search_evidence(
            tenant_id: str,
            query: str,
            dataset_keys: list[str],
            limit: int,
            offset: int = 0,
        ) -> list[EvidenceMatch]:
            assert tenant_id == tenant.id
            assert query == "EGFR"
            assert dataset_keys == ["licensed-literature"]
            assert limit == 5
            assert offset == 0
            return [
                EvidenceMatch(
                    content="abcdefgh",
                    document_id="document-1",
                    document_name="private-name.pdf",
                    dataset_key="licensed-literature",
                    score=0.9,
                    positions=[{"page": 4}],
                    metadata={
                        "source": "s3://private/source",
                        "content_sha256": "a" * 64,
                    },
                )
            ]

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(
            tenant.id,
            "licensed-agent",
            "api_key",
            frozenset({"evidence:read"}),
        )

    monkeypatch.setattr(
        "pharma_intel.api.get_settings",
        lambda: Settings(search_semantic_enabled=True),
    )
    monkeypatch.setattr("pharma_intel.api.get_opensearch_gateway", lambda: Gateway())
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/evidence/search",
                json={
                    "query": "EGFR",
                    "dataset_keys": ["licensed-literature"],
                    "limit": 5,
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["engine"] == "opensearch-hybrid"
        assert body["chunks"][0] == {
            "content": "abcd",
            "document_id": "document-1",
            "document_name": "",
            "dataset_id": "licensed-literature",
            "similarity": 0.9,
            "positions": [],
            "metadata": {
                "license": {
                    "schema_version": "1.0",
                    "license_id": "abstract-license-1",
                    "policy_version": "contract-v1",
                    "attribution": "Abstract-only source",
                }
            },
        }
        assert body["license_scopes"][0]["delivery_channel"] == "mcp"
        assert body["license_scopes"][0]["dataset_key"] == "licensed-literature"
        assert any("truncated" in warning for warning in body["warnings"])
        assert "private-ragflow-dataset-id" not in response.text
        assert "s3://private/source" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_evidence_dataset_catalog_only_returns_current_web_licensed_datasets(
    session: Session,
    tenant: Tenant,
) -> None:
    policy = {
        "schema_version": "1.0",
        "license_id": "catalog-license",
        "policy_version": "contract-v1",
        "allowed_fields": ["content", "document_name", "locator"],
        "max_content_chars": 1000,
        "attribution": "Catalog source",
    }
    session.add_all(
        [
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key="allowed-web",
                display_name="Allowed Web Literature",
                ragflow_dataset_id="private-web-id",
                required_scopes=["evidence:read"],
                license_policy={**policy, "permitted_channels": ["web"]},
            ),
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key="mcp-only",
                display_name="MCP Only Literature",
                ragflow_dataset_id="private-mcp-id",
                required_scopes=["evidence:read"],
                license_policy={**policy, "permitted_channels": ["mcp"]},
            ),
        ]
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "catalog-user",
        "user",
        frozenset({"evidence:read"}),
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/evidence/datasets")
        assert response.status_code == 200
        datasets = {item["dataset_key"]: item for item in response.json()}
        assert datasets["allowed-web"] == {
            "dataset_key": "allowed-web",
            "display_name": "Allowed Web Literature",
            "attribution": "Catalog source",
        }
        assert "mcp-only" not in datasets
        assert "private-web-id" not in response.text
        assert "private-mcp-id" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_evidence_dataset_catalog_returns_empty_when_none_are_authorized(
    session: Session,
    tenant: Tenant,
) -> None:
    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "catalog-user",
        "user",
        frozenset({"evidence:read"}),
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/evidence/datasets")
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()


def test_evidence_search_rejects_results_outside_approved_logical_datasets(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session.add(
        TenantDataset(
            tenant_id=tenant.id,
            dataset_key="migration-literature",
            display_name="Migration Literature",
            ragflow_dataset_id="private-ragflow-id",
            required_scopes=["evidence:read"],
            license_policy={
                "schema_version": "1.0",
                "license_id": "migration-license-1",
                "policy_version": "contract-v1",
                "permitted_channels": ["mcp"],
                "allowed_fields": ["content", "document_name", "locator"],
                "max_content_chars": 100,
                "attribution": "Licensed migration source",
            },
        )
    )
    session.commit()

    class Gateway:
        @staticmethod
        def search_evidence(
            tenant_id: str,
            query: str,
            dataset_keys: list[str],
            limit: int,
            offset: int = 0,
        ) -> list[EvidenceMatch]:
            assert tenant_id == tenant.id
            assert query == "KRAS"
            assert dataset_keys == ["migration-literature"]
            assert limit == 3
            assert offset == 0
            return [
                EvidenceMatch(
                    content="licensed evidence",
                    document_id="document-2",
                    document_name="source.pdf",
                    dataset_key="outside-approved-dataset",
                    score=0.8,
                    positions=[{"page": 2}],
                    metadata={},
                )
            ]

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(
            tenant.id,
            "migration-agent",
            "api_key",
            frozenset({"evidence:read"}),
        )

    monkeypatch.setattr("pharma_intel.api.get_opensearch_gateway", lambda: Gateway())
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/evidence/search",
                json={
                    "query": "KRAS",
                    "dataset_keys": ["migration-literature"],
                    "limit": 3,
                },
            )
        assert response.status_code == 503
        assert response.json()["detail"] == "Evidence search returned an unauthorized dataset"
        assert "private-ragflow-id" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_evidence_search_filters_deleted_source_assets_before_projection_cleanup(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = TenantDataset(
        tenant_id=tenant.id,
        dataset_key="withdrawn-literature",
        display_name="Withdrawn Literature",
        required_scopes=["evidence:read"],
        license_policy=internal_evidence_license_policy(source="withdrawal-test"),
    )
    source = DataSource(
        tenant_id=tenant.id,
        name="Withdrawn API source",
        source_type=DataSourceType.FOLDER,
        root_uri="/withdrawn-api-source",
        owner="Research Operations",
        authorization_scopes=["contract:withdrawal-test"],
        dataset_key=dataset.dataset_key,
    )
    session.add_all([dataset, source])
    session.flush()
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="withdrawn.md",
        source_uri="file:///withdrawn-api-source/withdrawn.md",
        file_name="withdrawn.md",
        extension=".md",
        processing_mode="parse",
        state=SourceAssetState.DELETED,
    )
    session.add(asset)
    session.commit()

    class Gateway:
        @staticmethod
        def search_evidence(
            tenant_id: str,
            query: str,
            dataset_keys: list[str],
            limit: int,
            offset: int = 0,
        ) -> list[EvidenceMatch]:
            del query, limit, offset
            assert tenant_id == tenant.id
            assert dataset_keys == [dataset.dataset_key]
            return [
                EvidenceMatch(
                    content="stale withdrawn evidence",
                    document_id="withdrawn-document",
                    document_name="withdrawn.md",
                    dataset_key=dataset.dataset_key,
                    score=1.0,
                    positions=[],
                    metadata={"source_asset_id": asset.id},
                )
            ]

    monkeypatch.setattr("pharma_intel.api.get_opensearch_gateway", lambda: Gateway())

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "withdrawal-agent",
        "api_key",
        frozenset({"evidence:read"}),
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/evidence/search",
                json={"query": "EGFR", "dataset_keys": [dataset.dataset_key], "limit": 5},
            )
        assert response.status_code == 200
        assert response.json()["chunks"] == []
        assert "Withdrawn source evidence" in response.json()["warnings"][0]
    finally:
        app.dependency_overrides.clear()
