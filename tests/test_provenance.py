from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.licensing import EvidenceLicensePolicy, internal_evidence_license_policy
from pharma_intel.models import (
    DataSource,
    DataSourceType,
    Entity,
    EntityType,
    EvidenceClaim,
    ExtractionRun,
    FactProvenanceLink,
    GovernanceStatus,
    ReviewStatus,
    RunState,
    SourceAsset,
    SourceAssetState,
    SourceDocument,
    SourceVersion,
    StagedFact,
    Tenant,
    TenantDataset,
)
from pharma_intel.security import Principal, require_principal
from tests.support.commercial import seed_commercial_contract


def test_record_provenance_applies_license_fields_and_omits_withdrawn_sources(
    session: Session,
    tenant: Tenant,
) -> None:
    link, dataset, asset = _provenance_record(session, tenant)

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "web-user",
        "user",
        frozenset({"evidence:read"}),
    )
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/provenance/{link.resource_type}/{link.resource_id}")
            assert response.status_code == 200
            payload = response.json()
            assert payload["resource_id"] == link.resource_id
            assert len(payload["items"]) == 1
            item = payload["items"][0]
            assert item["quote"] == "EGFR activity was 12 nM."
            assert item["locator"] == "page=7;paragraph=2"
            assert "source_document_id" not in item
            assert "source_version_id" not in item
            assert item["evidence_claim_id"] == link.evidence_claim_id
            assert item["license"]["license_id"] == "tenant-owned-internal"

            dataset.license_policy = EvidenceLicensePolicy(
                license_id="restricted-evidence",
                policy_version="v2",
                permitted_channels=["web"],
                allowed_fields=["content"],
                max_content_chars=10,
                attribution="Restricted source",
            ).document()
            session.commit()
            restricted = client.get(f"/api/v1/provenance/{link.resource_type}/{link.resource_id}")
            assert restricted.status_code == 200
            restricted_item = restricted.json()["items"][0]
            assert restricted_item["quote"] == "EGFR activ"
            assert restricted_item["document_name"] == ""
            assert restricted_item.get("locator") is None
            assert "source_document_id" not in restricted_item
            assert "omitted fields" in restricted_item["warnings"][1]

            asset.state = SourceAssetState.DELETED
            session.commit()
            withdrawn = client.get(f"/api/v1/provenance/{link.resource_type}/{link.resource_id}")
            assert withdrawn.status_code == 200
            assert withdrawn.json()["items"] == []
            assert "withdrawn source" in withdrawn.json()["warnings"][0]
    finally:
        app.dependency_overrides.clear()


def test_record_provenance_is_tenant_scoped_and_resource_type_validated(
    session: Session,
    tenant: Tenant,
) -> None:
    link, _, _ = _provenance_record(session, tenant)
    other_tenant = Tenant(slug="other-provenance", name="Other Provenance Tenant")
    session.add(other_tenant)
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        other_tenant.id,
        "other-user",
        "user",
        frozenset({"evidence:read"}),
    )
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/provenance/{link.resource_type}/{link.resource_id}")
            assert response.status_code == 200
            assert response.json()["items"] == []
            invalid = client.get(f"/api/v1/provenance/unknown/{link.resource_id}")
            assert invalid.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_agent_provenance_requires_matching_paid_reservation(
    session: Session,
    tenant: Tenant,
) -> None:
    link, _, _ = _provenance_record(session, tenant)
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={"provenance.read": ("evidence.read", 100)},
    )
    principal = Principal(
        tenant_id=tenant.id,
        actor_id=contract.principal.actor_id,
        actor_type=contract.principal.actor_type,
        scopes=frozenset({"mcp:connect", "evidence:read"}),
        client_id=contract.principal.client_id,
    )

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: principal
    arguments = {
        "resource_type": link.resource_type,
        "resource_id": link.resource_id,
        "limit": 20,
    }
    try:
        with TestClient(app) as client:
            unreserved = client.get(
                f"/internal/v1/domain/provenance/{link.resource_type}/{link.resource_id}",
                headers={"X-Commercial-Reservation-ID": "00000000-0000-4000-8000-000000000000"},
            )
            assert unreserved.status_code == 403
            reservation = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "provenance.read",
                    "idempotency_key": "provenance-read-0001",
                    "request_arguments": arguments,
                    "requested_result_limit": 20,
                    "max_billable_units": "10",
                    "requested_compute_units": "0",
                },
            )
            assert reservation.status_code == 200
            reserved = client.get(
                f"/internal/v1/domain/provenance/{link.resource_type}/{link.resource_id}",
                headers={"X-Commercial-Reservation-ID": reservation.json()["reservation_id"]},
            )
            assert reserved.status_code == 200
            assert reserved.json()["items"][0]["id"] == link.id
    finally:
        app.dependency_overrides.clear()


def _provenance_record(
    session: Session,
    tenant: Tenant,
) -> tuple[FactProvenanceLink, TenantDataset, SourceAsset]:
    dataset = TenantDataset(
        tenant_id=tenant.id,
        dataset_key="literature",
        display_name="Literature",
        required_scopes=["evidence:read"],
        license_policy=internal_evidence_license_policy(source="provenance-test"),
    )
    source = DataSource(
        tenant_id=tenant.id,
        name="Provenance source",
        source_type=DataSourceType.FOLDER,
        root_uri="/provenance-source",
        owner="Research Operations",
        authorization_scopes=["contract:provenance"],
        dataset_key=dataset.dataset_key,
    )
    subject = Entity(
        tenant_id=tenant.id,
        entity_type=EntityType.TARGET,
        name="EGFR",
        normalized_name="egfr",
        review_status=ReviewStatus.VERIFIED,
    )
    session.add_all([dataset, source, subject])
    session.flush()
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="egfr.pdf",
        source_uri="file:///provenance-source/egfr.pdf",
        file_name="egfr.pdf",
        extension=".pdf",
        processing_mode="parse",
    )
    document = SourceDocument(
        tenant_id=tenant.id,
        title="EGFR source",
        source_type="folder",
        source_uri=asset.source_uri,
        content_sha256="a" * 64,
    )
    session.add_all([asset, document])
    session.flush()
    version = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256="a" * 64,
        size_bytes=2048,
        source_document_id=document.id,
    )
    session.add(version)
    session.flush()
    extraction = ExtractionRun(
        tenant_id=tenant.id,
        source_version_id=version.id,
        schema_name="pharma_document_facts",
        schema_version="2.2.0",
        model_provider="test",
        model_name="test-model",
        prompt_sha256="b" * 64,
        policy_sha256="d" * 64,
        input_sha256="c" * 64,
        status=RunState.SUCCEEDED,
    )
    session.add(extraction)
    session.flush()
    staged = StagedFact(
        tenant_id=tenant.id,
        extraction_run_id=extraction.id,
        fact_kind="activity",
        fact_key="egfr-activity",
        raw_payload={"value": 12},
        payload={"value": 12},
        source_document_id=document.id,
        source_locator="page=7;paragraph=2",
        source_quote="EGFR activity was 12 nM.",
        confidence=0.99,
        status=GovernanceStatus.PUBLISHED,
    )
    session.add(staged)
    session.flush()
    claim = EvidenceClaim(
        tenant_id=tenant.id,
        subject_id=subject.id,
        predicate="has_activity",
        value={"value": 12},
        source_document_id=document.id,
        source_locator=staged.source_locator,
        quote=staged.source_quote,
        confidence=staged.confidence,
        review_status=ReviewStatus.VERIFIED,
    )
    session.add(claim)
    session.flush()
    link = FactProvenanceLink(
        tenant_id=tenant.id,
        resource_type="activity_measurement",
        resource_id="11111111-1111-4111-8111-111111111111",
        staged_fact_id=staged.id,
        evidence_claim_id=claim.id,
        source_asset_id=asset.id,
        source_version_id=version.id,
        source_document_id=document.id,
        dataset_key=dataset.dataset_key,
        source_locator=staged.source_locator,
    )
    session.add(link)
    session.commit()
    return link, dataset, asset
