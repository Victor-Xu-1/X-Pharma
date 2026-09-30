from __future__ import annotations

import hashlib
from collections.abc import Generator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel import api as api_module
from pharma_intel.api import app
from pharma_intel.commercial.accounting import BillingStatementCommand, CommercialAccountingService
from pharma_intel.commercial.billing import BillingStatementSigner
from pharma_intel.commercial.billing_operations import BILLING_CONSUMER_NAME, BILLING_STATEMENT_EVENT_TYPE
from pharma_intel.commercial.cursor import SignedCursorCodec
from pharma_intel.commercial.exports import CommercialExportService, ExportManifestSigner
from pharma_intel.commercial.service import CommercialUsageService, ReserveCommand, SettleCommand
from pharma_intel.db import get_session
from pharma_intel.models import (
    BillingAccount,
    CommercialCoverageRecord,
    CommercialPolicyEvent,
    Entity,
    EntityType,
    KnowledgePage,
    KnowledgePageStatus,
    KnowledgePageVersion,
    OutboxEvent,
    ProjectionDelivery,
    ProjectionDeliveryState,
    ReviewStatus,
    Tenant,
    UsageReservation,
    UsageSettlement,
)
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.request_correlation import NETWORK_FINGERPRINT_HEADER
from pharma_intel.security import Principal, require_principal
from pharma_intel.sorting import SortClause
from tests.support.commercial import seed_commercial_contract


def test_agent_entity_dossier_requires_matching_paid_reservation_and_scope(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={"entity.dossier": ("dossiers.read", 1001)},
    )
    entity = Entity(
        tenant_id=tenant.id,
        entity_type=EntityType.DRUG,
        name="Compound A",
        normalized_name="compound a",
        external_ids={},
        attributes={},
        review_status=ReviewStatus.VERIFIED,
    )
    session.add(entity)
    session.commit()
    principal = replace(contract.principal, scopes=frozenset({"mcp:connect", "dossiers:read"}))

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: principal
    try:
        with TestClient(app) as client:
            reservation = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "entity.dossier",
                    "idempotency_key": "entity-dossier-api-001",
                    "request_arguments": {"entity_id": entity.id, "domain_limit": 25, "limit": 251},
                    "requested_result_limit": 251,
                    "max_billable_units": "100",
                },
            )
            assert reservation.status_code == 200
            response = client.get(
                f"/internal/v1/domain/entities/{entity.id}/dossier",
                params={"limit": 25},
                headers={"X-Commercial-Reservation-ID": reservation.json()["reservation_id"]},
            )
            assert response.status_code == 200
            assert response.json()["entity"]["id"] == entity.id
            assert all(item["status"] == "not_observed" for item in response.json()["coverage"])
    finally:
        app.dependency_overrides.clear()


def test_non_governance_agent_cannot_use_draft_entity_as_domain_filter(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={"target.evidence.search": ("targets.read", 10)},
    )
    draft_target = Entity(
        tenant_id=tenant.id,
        entity_type=EntityType.TARGET,
        name="Draft target filter",
        normalized_name="draft target filter",
        external_ids={},
        attributes={},
        review_status=ReviewStatus.DRAFT,
    )
    session.add(draft_target)
    session.commit()

    principal = replace(contract.principal, scopes=frozenset({"mcp:connect", "targets:read"}))

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: principal
    try:
        with TestClient(app) as client:
            reservation = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "target.evidence.search",
                    "idempotency_key": "draft-target-domain-001",
                    "request_arguments": {"target_entity_id": draft_target.id, "limit": 1},
                    "requested_result_limit": 1,
                    "max_billable_units": "100",
                },
            )
            assert reservation.status_code == 200
            response = client.get(
                f"/internal/v1/domain/targets/{draft_target.id}/evidence",
                params={"limit": 1},
                headers={"X-Commercial-Reservation-ID": reservation.json()["reservation_id"]},
            )
            assert response.status_code == 404
            assert session.scalar(select(func.count()).select_from(UsageReservation)) == 1
    finally:
        app.dependency_overrides.clear()


def test_export_http_contract_separates_agent_data_and_human_approval_paths(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={"export.data": ("data.export", 5000)},
        granted_units=Decimal("1000"),
        max_response_bytes=10_000_000,
    )
    export_service = CommercialExportService(
        session,
        FileSystemObjectStore(tmp_path),
        ExportManifestSigner("api-export-signing-secret-1234567890123", key_id="api-export-v1"),  # noqa: S106
        SignedCursorCodec("api-export-cursor-secret-123456789012345"),  # noqa: S106
        read_page_size_max=25,
    )
    monkeypatch.setattr(api_module, "build_export_service", lambda _session, _settings: export_service)

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: contract.principal
    try:
        with TestClient(app) as client:
            response = client.post(
                "/internal/v1/exports",
                json={
                    "dataset": "entities",
                    "export_format": "jsonl",
                    "fields": ["id", "name"],
                    "filters": {},
                    "max_records": 2,
                    "max_billable_units": "10",
                    "idempotency_key": "api-export-create-001",
                },
            )
            assert response.status_code == 202
            job_id = response.json()["id"]
            assert response.json()["state"] == "queued"
            assert client.get(f"/internal/v1/exports/{job_id}").status_code == 200

            human = Principal(tenant.id, "commercial-admin", "user", frozenset({"*"}))
            app.dependency_overrides[require_principal] = lambda: human
            listed = client.get("/api/v1/commercial/exports")
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()] == [job_id]
            assert client.get(f"/internal/v1/exports/{job_id}").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_internal_commercial_api_reserves_settles_and_replays_durable_result(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant)

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    principal = replace(contract.principal, credential_fingerprint="b" * 64)
    app.dependency_overrides[require_principal] = lambda: principal
    try:
        with TestClient(app) as client:
            access = client.get("/internal/v1/commercial/access")
            assert access.status_code == 200
            assert access.json()["available_units"] == "100.00000000"
            assert access.json()["entitlements"][0]["max_page_depth"] == 10
            assert access.json()["entitlements"][0]["daily_unique_record_limit"] == 5000

            estimate = client.post(
                "/internal/v1/commercial/estimate",
                json={
                    "billing_class": "entity.search",
                    "requested_result_limit": 10,
                    "requested_compute_units": "0",
                },
            )
            assert estimate.status_code == 200
            assert estimate.json()["estimated_units_before_response_bytes"] == "2.00000000"
            assert estimate.json()["maximum_licensed_result_rows"] == 100
            assert estimate.json()["rate_card_revision"] == 1

            empty_summary = client.get("/internal/v1/commercial/usage-summary")
            assert empty_summary.status_code == 200
            assert empty_summary.json()["settlement_count"] == 0
            assert empty_summary.json()["charged_units"] == "0.00000000"

            payload = {
                "billing_class": "entity.search",
                "idempotency_key": "api-entity-search-0001",
                "request_arguments": {"q": "EGFR", "limit": 10},
                "requested_result_limit": 10,
                "max_billable_units": "5.00000000",
            }
            correlation_headers = {NETWORK_FINGERPRINT_HEADER: "a" * 64}
            reserved = client.post(
                "/internal/v1/commercial/reservations",
                json=payload,
                headers=correlation_headers,
            )
            assert reserved.status_code == 200
            assert reserved.json()["state"] == "reserved"
            reservation_id = reserved.json()["reservation_id"]
            stored_reservation = session.get(UsageReservation, reservation_id)
            assert stored_reservation is not None
            assert stored_reservation.network_fingerprint == "a" * 64
            assert stored_reservation.credential_fingerprint == "b" * 64

            result = {"items": [{"id": "target-egfr"}], "total": 1, "limit": 10, "offset": 0}
            settled = client.post(
                f"/internal/v1/commercial/reservations/{reservation_id}/settle",
                json={"result_count": 1, "result": result, "metrics": {"tool": "entity.search"}},
            )
            assert settled.status_code == 200
            assert settled.json()["state"] == "settled"
            assert settled.json()["settlement"]["result"] == result
            assert settled.json()["settlement"]["charged_units"] == "1.11000000"
            assert settled.json()["settlement"]["unique_record_count"] == 1
            assert settled.json()["settlement"]["new_unique_record_count"] == 1

            summary = client.get("/internal/v1/commercial/usage-summary")
            assert summary.status_code == 200
            assert summary.json()["settlement_count"] == 1
            assert summary.json()["charged_units"] == "1.11000000"
            assert summary.json()["result_count"] == 1
            assert summary.json()["latest_statement_id"] is None

            replay = client.post(
                "/internal/v1/commercial/reservations",
                json=payload,
                headers=correlation_headers,
            )
            assert replay.status_code == 200
            assert replay.json()["replayed"] is True
            assert replay.json()["settlement"]["settlement_id"] == settled.json()["settlement"]["settlement_id"]
            assert session.scalar(select(func.count()).select_from(UsageSettlement)) == 1
    finally:
        app.dependency_overrides.clear()


def test_agent_entity_domain_uses_reserved_opaque_cursor_without_offset_enumeration(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant, max_page_depth=3, daily_unique_record_limit=10)
    session.add_all(
        [
            Entity(
                tenant_id=tenant.id,
                entity_type=EntityType.TARGET,
                name="Alpha Target",
                normalized_name="alpha target",
                review_status=ReviewStatus.VERIFIED,
            ),
            Entity(
                tenant_id=tenant.id,
                entity_type=EntityType.TARGET,
                name="Beta Target",
                normalized_name="beta target",
                review_status=ReviewStatus.VERIFIED,
            ),
        ]
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: contract.principal
    try:
        with TestClient(app) as client:
            first_arguments = {
                "q": "Target",
                "entity_type": "target",
                "review_status": "verified",
                "limit": 1,
                "sort": ["name:desc"],
            }
            first_reservation = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "entity.search",
                    "idempotency_key": "agent-cursor-page-01",
                    "request_arguments": first_arguments,
                    "requested_result_limit": 1,
                    "max_billable_units": "5",
                },
            )
            assert first_reservation.status_code == 200
            first_id = first_reservation.json()["reservation_id"]
            first_page = client.get(
                "/internal/v1/domain/entities",
                params={**first_arguments, "billing_class": "entity.search"},
                headers={"X-Commercial-Reservation-ID": first_id},
            )
            assert first_page.status_code == 200
            first_result = first_page.json()
            assert first_result["page_depth"] == 1
            assert first_result["next_cursor"]
            assert "offset" not in first_result and "total" not in first_result
            assert first_result["sort_by"] == "name"
            assert first_result["sort_direction"] == "desc"
            assert first_result["sort"] == [{"field": "name", "direction": "desc"}]
            assert first_result["query_schema_version"] == "pharma.entity.search.v2"
            assert {"field": "q", "operator": "contains", "value": first_arguments["q"]} in first_result[
                "applied_filters"
            ]
            assert first_result["items"][0]["name"] == "Beta Target"
            assert (
                client.post(
                    f"/internal/v1/commercial/reservations/{first_id}/settle",
                    json={"result_count": 1, "result": first_result, "metrics": {}},
                ).status_code
                == 200
            )

            cursor = first_result["next_cursor"]
            second_arguments = {**first_arguments, "cursor": cursor}
            second_reservation = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "entity.search",
                    "idempotency_key": "agent-cursor-page-02",
                    "request_arguments": second_arguments,
                    "requested_result_limit": 1,
                    "max_billable_units": "5",
                },
            )
            assert second_reservation.status_code == 200
            second_id = second_reservation.json()["reservation_id"]
            second_page = client.get(
                "/internal/v1/domain/entities",
                params={**second_arguments, "billing_class": "entity.search"},
                headers={"X-Commercial-Reservation-ID": second_id},
            )
            assert second_page.status_code == 200
            assert second_page.json()["page_depth"] == 2
            assert second_page.json()["next_cursor"] is None
            assert second_page.json()["items"][0]["name"] == "Alpha Target"
            assert (
                client.post(
                    f"/internal/v1/commercial/reservations/{second_id}/settle",
                    json={"result_count": 1, "result": second_page.json(), "metrics": {}},
                ).status_code
                == 200
            )

            changed_query = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "entity.search",
                    "idempotency_key": "agent-cursor-tamper1",
                    "request_arguments": {**second_arguments, "q": "KRAS"},
                    "requested_result_limit": 1,
                    "max_billable_units": "5",
                },
            )
            assert changed_query.status_code == 403
            assert "invalid or expired" in changed_query.json()["detail"]
            assert session.scalar(select(func.count()).select_from(CommercialCoverageRecord)) == 2
    finally:
        app.dependency_overrides.clear()


def test_agent_knowledge_pages_enforce_publication_cursor_binding_and_depth(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={
            "knowledge.search": ("knowledge.read", 10),
            "knowledge.read": ("knowledge.read", 1),
            "deal.search": ("deals.read", 10),
        },
        max_page_depth=2,
        daily_unique_record_limit=10,
    )
    agent_principal = Principal(
        tenant_id=contract.principal.tenant_id,
        actor_id=contract.principal.actor_id,
        actor_type=contract.principal.actor_type,
        scopes=frozenset({"mcp:connect", "knowledge:read", "deals:read"}),
        client_id=contract.principal.client_id,
    )
    now = datetime.now(UTC)
    page_ids: dict[str, str] = {}
    for index, (title, page_status) in enumerate(
        [
            ("A Draft", KnowledgePageStatus.DRAFT),
            ("Alpha", KnowledgePageStatus.PUBLISHED),
            ("Beta", KnowledgePageStatus.PUBLISHED),
            ("Gamma", KnowledgePageStatus.PUBLISHED),
        ],
        start=1,
    ):
        page = KnowledgePage(
            tenant_id=tenant.id,
            page_key=f"target-page-{index}",
            page_type="target",
            title=title,
            status=page_status,
        )
        session.add(page)
        session.flush()
        version = KnowledgePageVersion(
            tenant_id=tenant.id,
            knowledge_page_id=page.id,
            version_number=1,
            compiler_version="test-v1",
            content_json={"title": title},
            rendered_markdown=f"# {title}",
            content_sha256=f"{index:064x}",
            source_snapshot_at=now,
        )
        session.add(version)
        session.flush()
        page.current_version_id = version.id
        page_ids[title] = page.id
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: agent_principal
    try:
        with TestClient(app) as client:
            first_arguments = {"limit": 1}
            first_reservation = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "knowledge.search",
                    "idempotency_key": "knowledge-cursor-page-01",
                    "request_arguments": first_arguments,
                    "requested_result_limit": 1,
                    "max_billable_units": "5",
                },
            )
            assert first_reservation.status_code == 200
            first_id = first_reservation.json()["reservation_id"]
            first_page = client.get(
                "/internal/v1/domain/knowledge/pages",
                params=first_arguments,
                headers={"X-Commercial-Reservation-ID": first_id},
            )
            assert first_page.status_code == 200
            first_result = first_page.json()
            assert [item["title"] for item in first_result["items"]] == ["Alpha"]
            assert first_result["page_depth"] == 1
            assert first_result["next_cursor"]
            assert "offset" not in first_result and "total" not in first_result
            assert (
                client.post(
                    f"/internal/v1/commercial/reservations/{first_id}/settle",
                    json={"result_count": 1, "result": first_result, "metrics": {}},
                ).status_code
                == 200
            )

            cursor = first_result["next_cursor"]
            cross_tool = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "deal.search",
                    "idempotency_key": "knowledge-cursor-cross-tool",
                    "request_arguments": {"limit": 1, "cursor": cursor},
                    "requested_result_limit": 1,
                    "max_billable_units": "5",
                },
            )
            assert cross_tool.status_code == 403

            second_arguments = {"limit": 1, "cursor": cursor}
            second_reservation = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "knowledge.search",
                    "idempotency_key": "knowledge-cursor-page-02",
                    "request_arguments": second_arguments,
                    "requested_result_limit": 1,
                    "max_billable_units": "5",
                },
            )
            assert second_reservation.status_code == 200
            second_id = second_reservation.json()["reservation_id"]
            second_page = client.get(
                "/internal/v1/domain/knowledge/pages",
                params=second_arguments,
                headers={"X-Commercial-Reservation-ID": second_id},
            )
            assert second_page.status_code == 200
            second_result = second_page.json()
            assert [item["title"] for item in second_result["items"]] == ["Beta"]
            assert second_result["page_depth"] == 2
            assert second_result["next_cursor"] is None
            assert (
                client.post(
                    f"/internal/v1/commercial/reservations/{second_id}/settle",
                    json={"result_count": 1, "result": second_result, "metrics": {}},
                ).status_code
                == 200
            )

            published_arguments = {"page_id": page_ids["Alpha"]}
            published_reservation = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "knowledge.read",
                    "idempotency_key": "knowledge-read-published",
                    "request_arguments": published_arguments,
                    "requested_result_limit": 1,
                    "max_billable_units": "5",
                },
            )
            assert published_reservation.status_code == 200
            published_id = published_reservation.json()["reservation_id"]
            published_page = client.get(
                f"/internal/v1/domain/knowledge/pages/{page_ids['Alpha']}",
                headers={"X-Commercial-Reservation-ID": published_id},
            )
            assert published_page.status_code == 200
            assert published_page.json()["title"] == "Alpha"
            assert published_page.json()["compiler_version"] == "test-v1"
            assert published_page.json()["content_sha256"] == f"{2:064x}"
            assert published_page.json()["content_json"] == {"title": "Alpha"}
            assert published_page.json()["rendered_markdown"] == "# Alpha"
            published_settlement = client.post(
                f"/internal/v1/commercial/reservations/{published_id}/settle",
                json={"result_count": 1, "result": published_page.json(), "metrics": {}},
            )
            assert published_settlement.status_code == 200
            assert published_settlement.json()["settlement"]["unique_record_count"] == 1
            assert published_settlement.json()["settlement"]["new_unique_record_count"] == 0

            draft_arguments = {"page_id": page_ids["A Draft"]}
            draft_reservation = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "knowledge.read",
                    "idempotency_key": "knowledge-read-draft",
                    "request_arguments": draft_arguments,
                    "requested_result_limit": 1,
                    "max_billable_units": "5",
                },
            )
            assert draft_reservation.status_code == 200
            draft_id = draft_reservation.json()["reservation_id"]
            draft_page = client.get(
                f"/internal/v1/domain/knowledge/pages/{page_ids['A Draft']}",
                headers={"X-Commercial-Reservation-ID": draft_id},
            )
            assert draft_page.status_code == 404
            assert (
                client.post(
                    f"/internal/v1/commercial/reservations/{draft_id}/release",
                    json={"reason": "draft visibility test"},
                ).status_code
                == 200
            )

            assert session.scalar(select(func.count()).select_from(UsageSettlement)) == 3
            assert session.scalar(select(func.count()).select_from(CommercialCoverageRecord)) == 2
    finally:
        app.dependency_overrides.clear()


def test_agent_page_routes_bind_commercial_arguments_and_fetch_one_extra_row(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={
            "target.evidence.search": ("targets.read", 10),
            "bioactivity.search": ("activities.read", 10),
            "sar.compare": ("activities.read", 10),
            "pipeline.search": ("pipelines.read", 10),
            "structure.search": ("structures.read", 10),
            "trial.search": ("trials.read", 10),
            "patent.search": ("patents.read", 10),
            "deal.search": ("deals.read", 10),
            "company.timeline": ("dossiers.read", 10),
            "regulatory.search": ("regulatory.read", 10),
            "epidemiology.search": ("epidemiology.read", 10),
            "news.search": ("news.read", 10),
        },
    )
    agent_principal = Principal(
        tenant_id=contract.principal.tenant_id,
        actor_id=contract.principal.actor_id,
        actor_type=contract.principal.actor_type,
        scopes=frozenset(
            {
                "mcp:connect",
                "*",
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
        client_id=contract.principal.client_id,
    )
    calls: list[tuple[object, ...]] = []

    def captured_sort_tokens(sort: object) -> list[str]:
        if sort is None:
            return []
        assert isinstance(sort, list | tuple)
        tokens: list[str] = []
        for clause in sort:
            assert isinstance(clause, SortClause)
            tokens.append(clause.token)
        return tokens

    class FakeIntelligenceService:
        def __init__(self, _session: Session, _tenant_id: str, *, include_unpublished: bool = True) -> None:
            self.include_unpublished = include_unpublished

        def bioactivities(self, target_id: str, standard_type: str | None, limit: int, offset: int) -> list[object]:
            calls.append(("bioactivities", target_id, standard_type, limit, offset))
            return []

        def sar_comparison(
            self,
            target_id: str,
            *,
            standard_type: str | None,
            assay_type: str | None,
            assay_format: str | None,
            organism: str | None,
            cell_line: str | None,
            limit: int,
            offset: int,
        ) -> SimpleNamespace:
            calls.append(
                (
                    "sar_comparison",
                    target_id,
                    standard_type,
                    assay_type,
                    assay_format,
                    organism,
                    cell_line,
                    limit,
                    offset,
                )
            )
            return SimpleNamespace(items=[])

        def target_evidence_for_entity(
            self,
            target_id: str,
            limit: int,
            offset: int,
            *,
            evidence_type: str | None = None,
            direction: str | None = None,
            disease_entity_id: str | None = None,
        ) -> list[object]:
            calls.append(
                (
                    "target_evidence_for_entity",
                    target_id,
                    evidence_type,
                    direction,
                    disease_entity_id,
                    limit,
                    offset,
                )
            )
            return []

        def search_programs(
            self,
            query: str | None,
            modality: str | None,
            phase: str | None,
            geography: str | None,
            limit: int,
            offset: int,
            **filters: object,
        ) -> SimpleNamespace:
            filters["sort"] = captured_sort_tokens(filters.get("sort"))
            calls.append(("search_programs", query, modality, phase, geography, limit, offset, filters))
            return SimpleNamespace(items=[])

        def structures(self, entity_id: str | None, inchi_key: str | None, limit: int, offset: int) -> list[object]:
            calls.append(("structures", entity_id, inchi_key, limit, offset))
            return []

        def clinical_trial_search_items(
            self,
            entity_id: str | None,
            query: str | None,
            registry: str | None,
            overall_status: str | None,
            phase: str | None,
            study_type: str | None,
            has_results: bool | None,
            limit: int,
            offset: int,
            *,
            results_posted_from: datetime | None = None,
            results_posted_to: datetime | None = None,
            result_evaluation: str | None = None,
            acronym: str | None = None,
            initiation_type: str | None = None,
            therapy_line: str | None = None,
            investigational_drug: str | None = None,
            combination_drug: str | None = None,
            investigational_target: str | None = None,
            combination_target: str | None = None,
            investigational_drug_entity_ids: list[str] | None = None,
            combination_drug_entity_ids: list[str] | None = None,
            investigational_target_entity_ids: list[str] | None = None,
            combination_target_entity_ids: list[str] | None = None,
            linked_drug_modality: list[str] | None = None,
            linked_drug_innovation_type: list[str] | None = None,
            linked_drug_category: list[str] | None = None,
            linked_drug_program_tag: list[str] | None = None,
            linked_drug_global_phase: str | None = None,
            linked_drug_organization_country_region: str | None = None,
            role_entity_id: str | None = None,
            role_entity_ids: list[str] | None = None,
            role_entity_role: str | None = None,
            has_key_result: bool | None = None,
            publication_id: str | None = None,
            conference: str | None = None,
            disclosed_from: datetime | None = None,
            disclosed_to: datetime | None = None,
            sort_by: str = "last_update_posted",
            sort_direction: str = "desc",
            sort: object = None,
        ) -> list[object]:
            calls.append(
                (
                    "clinical_trial_search_items",
                    entity_id,
                    query,
                    registry,
                    overall_status,
                    phase,
                    study_type,
                    acronym,
                    initiation_type,
                    therapy_line,
                    role_entity_ids,
                    investigational_drug_entity_ids,
                    combination_drug_entity_ids,
                    investigational_target_entity_ids,
                    combination_target_entity_ids,
                    linked_drug_modality,
                    linked_drug_innovation_type,
                    linked_drug_category,
                    linked_drug_program_tag,
                    linked_drug_global_phase,
                    linked_drug_organization_country_region,
                    has_results,
                    limit,
                    offset,
                    captured_sort_tokens(sort),
                )
            )
            return []

        def patent_search_items(
            self,
            entity_id: str | None,
            query: str | None,
            applicant: str | None,
            legal_status: str | None,
            limit: int,
            offset: int,
            *,
            sort_by: str = "priority_date",
            sort_direction: str = "desc",
            sort: object = None,
        ) -> list[object]:
            calls.append(
                (
                    "patent_search_items",
                    entity_id,
                    query,
                    applicant,
                    legal_status,
                    limit,
                    offset,
                    captured_sort_tokens(sort),
                )
            )
            return []

        def deal_search_items(
            self,
            entity_id: str | None,
            query: str | None,
            deal_type: str | None,
            territory: str | None,
            party: str | None,
            limit: int,
            offset: int,
            *,
            status: str | None = None,
            direction: str | None = None,
            direction_reference_jurisdiction: str | None = None,
            asset_entity_id: str | None = None,
            target_entity_id: str | None = None,
            disease_entity_id: str | None = None,
            asset_modality: list[str] | None = None,
            asset_program_tag: list[str] | None = None,
            party_entity_id: str | None = None,
            party_role: str | None = None,
            party_country_region: str | None = None,
            party_organization_type: str | None = None,
            development_phase_at_transaction: str | None = None,
            current_development_phase: str | None = None,
            right_type: str | None = None,
            rights_territory: str | None = None,
            currency: str | None = None,
            announced_from: datetime | None = None,
            announced_to: datetime | None = None,
            terminated_from: datetime | None = None,
            terminated_to: datetime | None = None,
            source_updated_from: datetime | None = None,
            source_updated_to: datetime | None = None,
            upfront_amount_min: float | None = None,
            upfront_amount_max: float | None = None,
            total_potential_amount_min: float | None = None,
            total_potential_amount_max: float | None = None,
            sort_by: str = "announced_at",
            sort_direction: str = "desc",
            sort: object = None,
        ) -> list[object]:
            calls.append(
                (
                    "deal_search_items",
                    entity_id,
                    query,
                    deal_type,
                    territory,
                    party,
                    asset_entity_id,
                    target_entity_id,
                    disease_entity_id,
                    asset_modality,
                    asset_program_tag,
                    limit,
                    offset,
                    captured_sort_tokens(sort),
                )
            )
            return []

        def company_timeline(self, company_id: str, limit: int, offset: int) -> SimpleNamespace:
            calls.append(("company_timeline", company_id, limit, offset))
            return SimpleNamespace(items=[])

        def regulatory_search_items(
            self,
            entity_id: str | None,
            query: str | None,
            agency: str | None,
            jurisdiction: str | None,
            event_type: str | None,
            status: str | None,
            limit: int,
            offset: int,
            *,
            sort_by: str = "decision_date",
            sort_direction: str = "desc",
            sort: object = None,
            **_: object,
        ) -> list[object]:
            calls.append(
                (
                    "regulatory_search_items",
                    entity_id,
                    query,
                    agency,
                    jurisdiction,
                    event_type,
                    status,
                    limit,
                    offset,
                    captured_sort_tokens(sort),
                )
            )
            return []

        def epidemiology_search_items(
            self,
            disease_entity_id: str | None,
            query: str | None,
            measure: str | None,
            geography: str | None,
            unit: str | None,
            population_scope: str | None,
            age_group: str | None,
            sex: str | None,
            period_start_from: datetime | None,
            period_end_to: datetime | None,
            limit: int,
            offset: int,
            *,
            patient_population_id: str | None = None,
            sort_by: str = "period_end",
            sort_direction: str = "desc",
            sort: object = None,
        ) -> list[object]:
            calls.append(
                (
                    "epidemiology_search_items",
                    disease_entity_id,
                    query,
                    measure,
                    geography,
                    unit,
                    population_scope,
                    age_group,
                    sex,
                    period_start_from,
                    period_end_to,
                    patient_population_id,
                    limit,
                    offset,
                    captured_sort_tokens(sort),
                )
            )
            return []

        def news_event_search_items(
            self,
            entity_id: str | None,
            query: str | None,
            event_type: str | None,
            publisher: str | None,
            language: str | None,
            venue: str | None,
            published_from: datetime | None,
            published_to: datetime | None,
            limit: int,
            offset: int,
            *,
            sort_by: str = "published_at",
            sort_direction: str = "desc",
            sort: object = None,
        ) -> list[object]:
            calls.append(
                (
                    "news_event_search_items",
                    entity_id,
                    query,
                    event_type,
                    publisher,
                    language,
                    venue,
                    published_from,
                    published_to,
                    limit,
                    offset,
                    captured_sort_tokens(sort),
                )
            )
            return []

    monkeypatch.setattr(api_module, "IntelligenceService", FakeIntelligenceService)

    def session_override() -> Generator[Session]:
        yield session

    cases: list[tuple[str, str, dict[str, object], dict[str, object]]] = [
        (
            "target.evidence.search",
            "/internal/v1/domain/targets/target-1/evidence",
            {
                "evidence_type": "genetic_association",
                "direction": "supports",
                "disease_entity_id": "disease-1",
                "limit": 1,
            },
            {
                "target_entity_id": "target-1",
                "evidence_type": "genetic_association",
                "direction": "supports",
                "disease_entity_id": "disease-1",
                "limit": 1,
            },
        ),
        (
            "bioactivity.search",
            "/internal/v1/domain/targets/target-1/bioactivities",
            {"standard_type": "IC50", "limit": 1},
            {"target_entity_id": "target-1", "standard_type": "IC50", "limit": 1},
        ),
        (
            "sar.compare",
            "/internal/v1/domain/targets/target-1/sar-comparison",
            {
                "standard_type": "IC50",
                "assay_type": "binding",
                "assay_format": "biochemical",
                "organism": "Homo sapiens",
                "cell_line": "A549",
                "limit": 1,
            },
            {
                "target_entity_id": "target-1",
                "standard_type": "IC50",
                "assay_type": "binding",
                "assay_format": "biochemical",
                "organism": "Homo sapiens",
                "cell_line": "A549",
                "limit": 1,
            },
        ),
        (
            "pipeline.search",
            "/internal/v1/domain/targets/target-1/competitive-programs",
            {
                "drug_entity_id": "550e8400-e29b-41d4-a716-446655440020",
                "disease_entity_id": "disease-1",
                "organization_entity_id": "organization-1",
                "program_status": "active",
                "organization_role": "collaborator",
                "organization_type": "biotech",
                "organization_country_region": "US",
                "modality": ["small molecule", "antibody"],
                "global_phase": "phase_2",
                "china_phase": "phase_1",
                "global_phase_started_from": "2026-01-01T00:00:00Z",
                "global_phase_started_to": "2026-12-31T23:59:59Z",
                "development_rights_region": "Global",
                "commercialization_rights_region": "Greater China",
                "program_tag": ["first_in_class", "new_modality"],
                "milestone_type": "first_patient_in",
                "milestone_from": "2026-06-01T00:00:00Z",
                "milestone_to": "2026-06-30T23:59:59Z",
                "has_clinical_results": True,
                "clinical_result_evaluation": "positive",
                "has_deal": True,
                "deal_currency": "USD",
                "deal_total_potential_amount_min": 400_000_000.0,
                "deal_total_potential_amount_max": 600_000_000.0,
                "sort": ["drug_name:asc"],
                "limit": 1,
            },
            {
                "target_entity_id": "target-1",
                "drug_entity_id": "550e8400-e29b-41d4-a716-446655440020",
                "disease_entity_id": "disease-1",
                "organization_entity_id": "organization-1",
                "program_status": "active",
                "organization_role": "collaborator",
                "organization_type": "biotech",
                "organization_country_region": "US",
                "modality": ["small molecule", "antibody"],
                "global_phase": "phase_2",
                "china_phase": "phase_1",
                "global_phase_started_from": "2026-01-01T00:00:00+00:00",
                "global_phase_started_to": "2026-12-31T23:59:59+00:00",
                "development_rights_region": "Global",
                "commercialization_rights_region": "Greater China",
                "program_tag": ["first_in_class", "new_modality"],
                "milestone_type": "first_patient_in",
                "milestone_from": "2026-06-01T00:00:00+00:00",
                "milestone_to": "2026-06-30T23:59:59+00:00",
                "has_clinical_results": True,
                "clinical_result_evaluation": "positive",
                "has_deal": True,
                "deal_currency": "USD",
                "deal_total_potential_amount_min": 400_000_000.0,
                "deal_total_potential_amount_max": 600_000_000.0,
                "sort": ["drug_name:asc"],
                "limit": 1,
            },
        ),
        ("structure.search", "/internal/v1/domain/structures", {"limit": 1}, {"limit": 1}),
        (
            "trial.search",
            "/internal/v1/domain/clinical-trials",
            {
                "entity_id": "target-1",
                "q": "lung cancer",
                "registry": "ClinicalTrials.gov",
                "status": "RECRUITING",
                "phase": "PHASE2",
                "study_type": "INTERVENTIONAL",
                "acronym": "KEYNOTE",
                "initiation_type": "ist",
                "therapy_line": "first_line",
                "role_entity_ids": [
                    "550e8400-e29b-41d4-a716-446655440003",
                    "550e8400-e29b-41d4-a716-446655440004",
                ],
                "investigational_drug_entity_ids": ["550e8400-e29b-41d4-a716-446655440010"],
                "combination_drug_entity_ids": ["550e8400-e29b-41d4-a716-446655440011"],
                "investigational_target_entity_ids": ["550e8400-e29b-41d4-a716-446655440012"],
                "combination_target_entity_ids": ["550e8400-e29b-41d4-a716-446655440013"],
                "linked_drug_modality": ["antibody"],
                "linked_drug_innovation_type": ["innovative"],
                "linked_drug_category": ["biologic"],
                "linked_drug_program_tag": ["first_in_class"],
                "linked_drug_global_phase": "phase_3",
                "linked_drug_organization_country_region": "CN",
                "has_results": True,
                "sort": ["registry_id:asc"],
                "limit": 1,
            },
            {
                "entity_id": "target-1",
                "q": "lung cancer",
                "registry": "ClinicalTrials.gov",
                "status": "RECRUITING",
                "phase": "PHASE2",
                "study_type": "INTERVENTIONAL",
                "acronym": "KEYNOTE",
                "initiation_type": "ist",
                "therapy_line": "first_line",
                "role_entity_ids": [
                    "550e8400-e29b-41d4-a716-446655440003",
                    "550e8400-e29b-41d4-a716-446655440004",
                ],
                "investigational_drug_entity_ids": ["550e8400-e29b-41d4-a716-446655440010"],
                "combination_drug_entity_ids": ["550e8400-e29b-41d4-a716-446655440011"],
                "investigational_target_entity_ids": ["550e8400-e29b-41d4-a716-446655440012"],
                "combination_target_entity_ids": ["550e8400-e29b-41d4-a716-446655440013"],
                "linked_drug_modality": ["antibody"],
                "linked_drug_innovation_type": ["innovative"],
                "linked_drug_category": ["biologic"],
                "linked_drug_program_tag": ["first_in_class"],
                "linked_drug_global_phase": "phase_3",
                "linked_drug_organization_country_region": "CN",
                "has_results": True,
                "sort": ["registry_id:asc"],
                "limit": 1,
            },
        ),
        (
            "patent.search",
            "/internal/v1/domain/patents",
            {
                "entity_id": "target-1",
                "q": "WO2026",
                "applicant": "Victor Therapeutics",
                "legal_status": "ACTIVE",
                "sort": ["family_identifier:asc"],
                "limit": 1,
            },
            {
                "entity_id": "target-1",
                "q": "WO2026",
                "applicant": "Victor Therapeutics",
                "legal_status": "ACTIVE",
                "sort": ["family_identifier:asc"],
                "limit": 1,
            },
        ),
        (
            "deal.search",
            "/internal/v1/domain/deals",
            {
                "entity_id": "drug-1",
                "q": "license",
                "deal_type": "license",
                "territory": "global",
                "asset_entity_id": "550e8400-e29b-41d4-a716-446655440004",
                "target_entity_id": "550e8400-e29b-41d4-a716-446655440005",
                "disease_entity_id": "550e8400-e29b-41d4-a716-446655440006",
                "asset_modality": ["antibody", "small molecule"],
                "asset_program_tag": ["first_in_class", "best_in_class"],
                "party": "Victor Therapeutics",
                "sort": ["name:asc"],
                "limit": 1,
            },
            {
                "entity_id": "drug-1",
                "q": "license",
                "deal_type": "license",
                "territory": "global",
                "asset_entity_id": "550e8400-e29b-41d4-a716-446655440004",
                "target_entity_id": "550e8400-e29b-41d4-a716-446655440005",
                "disease_entity_id": "550e8400-e29b-41d4-a716-446655440006",
                "asset_modality": ["antibody", "small molecule"],
                "asset_program_tag": ["first_in_class", "best_in_class"],
                "party": "Victor Therapeutics",
                "sort": ["name:asc"],
                "limit": 1,
            },
        ),
        (
            "company.timeline",
            "/internal/v1/domain/companies/company-1/timeline",
            {"limit": 1},
            {"company_entity_id": "company-1", "limit": 1},
        ),
        (
            "regulatory.search",
            "/internal/v1/domain/regulatory-events",
            {
                "entity_id": "drug-1",
                "q": "approval",
                "agency": "FDA",
                "jurisdiction": "US",
                "event_type": "approval",
                "status": "approved",
                "sort": ["subject:asc"],
                "limit": 1,
            },
            {
                "entity_id": "drug-1",
                "q": "approval",
                "agency": "FDA",
                "jurisdiction": "US",
                "event_type": "approval",
                "status": "approved",
                "sort": ["subject:asc"],
                "limit": 1,
            },
        ),
        (
            "epidemiology.search",
            "/internal/v1/domain/epidemiology-observations",
            {
                "disease_entity_id": "disease-1",
                "patient_population_id": "population-1",
                "q": "NSCLC burden",
                "measure": "prevalence",
                "geography": "China",
                "unit": "patients",
                "population_scope": "adults",
                "age_group": "18+",
                "sex": "all",
                "period_start_from": "2025-01-01T00:00:00Z",
                "period_end_to": "2025-12-31T00:00:00Z",
                "sort": ["value:asc"],
                "limit": 1,
            },
            {
                "disease_entity_id": "disease-1",
                "patient_population_id": "population-1",
                "q": "NSCLC burden",
                "measure": "prevalence",
                "geography": "China",
                "unit": "patients",
                "population_scope": "adults",
                "age_group": "18+",
                "sex": "all",
                "period_start_from": "2025-01-01T00:00:00+00:00",
                "period_end_to": "2025-12-31T00:00:00+00:00",
                "sort": ["value:asc"],
                "limit": 1,
            },
        ),
        (
            "news.search",
            "/internal/v1/domain/news-events",
            {
                "entity_id": "target-1",
                "q": "Phase 2 update",
                "event_type": "press_release",
                "publisher": "Victor Therapeutics",
                "language": "en",
                "venue": "ASCO 2026",
                "published_from": "2026-01-01T00:00:00Z",
                "published_to": "2026-12-31T00:00:00Z",
                "sort": ["title:asc"],
                "limit": 1,
            },
            {
                "entity_id": "target-1",
                "q": "Phase 2 update",
                "event_type": "press_release",
                "publisher": "Victor Therapeutics",
                "language": "en",
                "venue": "ASCO 2026",
                "published_from": "2026-01-01T00:00:00+00:00",
                "published_to": "2026-12-31T00:00:00+00:00",
                "sort": ["title:asc"],
                "limit": 1,
            },
        ),
    ]
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: agent_principal
    try:
        with TestClient(app) as client:
            for index, (billing_class, path, params, request_arguments) in enumerate(cases, start=1):
                reservation = client.post(
                    "/internal/v1/commercial/reservations",
                    json={
                        "billing_class": billing_class,
                        "idempotency_key": f"domain-page-matrix-{index:02d}",
                        "request_arguments": request_arguments,
                        "requested_result_limit": 1,
                        "max_billable_units": "5",
                    },
                )
                assert reservation.status_code == 200, reservation.text
                reservation_id = reservation.json()["reservation_id"]
                response = client.get(
                    path,
                    params=params,
                    headers={"X-Commercial-Reservation-ID": reservation_id},
                )
                assert response.status_code == 200, response.text
                result = response.json()
                sort_tokens = request_arguments.get("sort", [])
                assert isinstance(sort_tokens, list)
                expected_sort = [
                    {"field": token.rsplit(":", 1)[0], "direction": token.rsplit(":", 1)[1]}
                    for token in sort_tokens
                    if isinstance(token, str)
                ]
                assert result == {
                    "items": [],
                    "limit": 1,
                    "page_depth": 1,
                    "next_cursor": None,
                    "sort": expected_sort,
                }
                settlement = client.post(
                    f"/internal/v1/commercial/reservations/{reservation_id}/settle",
                    json={"result_count": 0, "result": result, "metrics": {}},
                )
                assert settlement.status_code == 200, settlement.text

        assert calls == [
            (
                "target_evidence_for_entity",
                "target-1",
                "genetic_association",
                "supports",
                "disease-1",
                2,
                0,
            ),
            ("bioactivities", "target-1", "IC50", 2, 0),
            (
                "sar_comparison",
                "target-1",
                "IC50",
                "binding",
                "biochemical",
                "Homo sapiens",
                "A549",
                2,
                0,
            ),
            (
                "search_programs",
                None,
                ["small molecule", "antibody"],
                None,
                None,
                2,
                0,
                {
                    "innovation_type": None,
                    "therapeutic_area": None,
                    "drug_category": None,
                    "program_status": "active",
                    "organization_role": "collaborator",
                    "organization_type": "biotech",
                    "organization_country_region": "US",
                    "drug_entity_id": "550e8400-e29b-41d4-a716-446655440020",
                    "target_entity_id": "target-1",
                    "disease_entity_id": "disease-1",
                    "organization_entity_id": "organization-1",
                    "global_phase": "phase_2",
                    "china_phase": "phase_1",
                    "global_phase_started_from": datetime(2026, 1, 1, tzinfo=UTC),
                    "global_phase_started_to": datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC),
                    "china_phase_started_from": None,
                    "china_phase_started_to": None,
                    "development_rights_region": "Global",
                    "commercialization_rights_region": "Greater China",
                    "program_tag": ["first_in_class", "new_modality"],
                    "milestone_type": "first_patient_in",
                    "milestone_from": datetime(2026, 6, 1, tzinfo=UTC),
                    "milestone_to": datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC),
                    "has_clinical_results": True,
                    "clinical_result_evaluation": "positive",
                    "has_deal": True,
                    "deal_currency": "USD",
                    "deal_total_potential_amount_min": 400_000_000.0,
                    "deal_total_potential_amount_max": 600_000_000.0,
                    "sort": ["drug_name:asc"],
                },
            ),
            ("structures", None, None, 2, 0),
            (
                "clinical_trial_search_items",
                "target-1",
                "lung cancer",
                "ClinicalTrials.gov",
                "RECRUITING",
                "PHASE2",
                "INTERVENTIONAL",
                "KEYNOTE",
                "ist",
                "first_line",
                [
                    "550e8400-e29b-41d4-a716-446655440003",
                    "550e8400-e29b-41d4-a716-446655440004",
                ],
                ["550e8400-e29b-41d4-a716-446655440010"],
                ["550e8400-e29b-41d4-a716-446655440011"],
                ["550e8400-e29b-41d4-a716-446655440012"],
                ["550e8400-e29b-41d4-a716-446655440013"],
                ["antibody"],
                ["innovative"],
                ["biologic"],
                ["first_in_class"],
                "phase_3",
                "CN",
                True,
                2,
                0,
                ["registry_id:asc"],
            ),
            (
                "patent_search_items",
                "target-1",
                "WO2026",
                "Victor Therapeutics",
                "ACTIVE",
                2,
                0,
                ["family_identifier:asc"],
            ),
            (
                "deal_search_items",
                "drug-1",
                "license",
                "license",
                "global",
                "Victor Therapeutics",
                "550e8400-e29b-41d4-a716-446655440004",
                "550e8400-e29b-41d4-a716-446655440005",
                "550e8400-e29b-41d4-a716-446655440006",
                ["antibody", "small molecule"],
                ["first_in_class", "best_in_class"],
                2,
                0,
                ["name:asc"],
            ),
            ("company_timeline", "company-1", 2, 0),
            (
                "regulatory_search_items",
                "drug-1",
                "approval",
                "FDA",
                "US",
                "approval",
                "approved",
                2,
                0,
                ["subject:asc"],
            ),
            (
                "epidemiology_search_items",
                "disease-1",
                "NSCLC burden",
                "prevalence",
                "China",
                "patients",
                "adults",
                "18+",
                "all",
                datetime(2025, 1, 1, tzinfo=UTC),
                datetime(2025, 12, 31, tzinfo=UTC),
                "population-1",
                2,
                0,
                ["value:asc"],
            ),
            (
                "news_event_search_items",
                "target-1",
                "Phase 2 update",
                "press_release",
                "Victor Therapeutics",
                "en",
                "ASCO 2026",
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 12, 31, tzinfo=UTC),
                2,
                0,
                ["title:asc"],
            ),
        ]
        assert session.scalar(select(func.count()).select_from(UsageSettlement)) == len(cases)
    finally:
        app.dependency_overrides.clear()


def test_internal_commercial_api_fails_before_data_access_without_contract(
    session: Session,
    tenant: Tenant,
) -> None:
    principal = Principal(
        tenant.id,
        "unregistered-subject",
        "agent",
        frozenset({"mcp:connect", "entities:read"}),
        "unregistered-client",
    )

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: principal
    try:
        with TestClient(app) as client:
            response = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "entity.search",
                    "idempotency_key": "unregistered-call-001",
                    "request_arguments": {"q": "EGFR"},
                    "requested_result_limit": 10,
                    "max_billable_units": "10",
                },
            )
            assert response.status_code == 402
            assert "not registered" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_human_commercial_overview_reports_authoritative_balance_usage_and_coverage(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant, daily_unique_record_limit=25)
    service = CommercialUsageService(session, contract.principal)
    reservation = service.reserve(
        ReserveCommand(
            "entity.search",
            "overview-usage-0001",
            {"q": "EGFR", "limit": 2},
            2,
            "5",
            "overview-reserve",
        )
    ).reservation
    service.settle(
        SettleCommand(
            reservation.id,
            2,
            {"items": [{"id": "entity-1"}, {"id": "entity-2"}]},
            {},
            "overview-settle",
        )
    )
    human = Principal(tenant.id, "admin-user", "user", frozenset({"commercial:read"}))

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: human
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/commercial/overview")
            assert response.status_code == 200
            overview = response.json()
            assert overview["open_risk_count"] == 0
            assert len(overview["subscriptions"]) == 1
            subscription = overview["subscriptions"][0]
            assert subscription["client_key"] == "test-agent"
            assert subscription["available_units"] == "98.79000000"
            assert subscription["active_reservations"] == 0
            assert subscription["daily_unique_records"] == 2
            assert subscription["daily_usage"] == {
                "settlement_count": 1,
                "result_count": 2,
                "unique_record_count": 2,
                "new_unique_record_count": 2,
                "response_bytes": subscription["daily_usage"]["response_bytes"],
            }
            assert subscription["entitlements"][0]["daily_unique_record_limit"] == 25

            app.dependency_overrides[require_principal] = lambda: contract.principal
            assert client.get("/api/v1/commercial/overview").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_human_commercial_operations_api_reviews_risk_and_revokes_client(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant)
    event = CommercialPolicyEvent(
        tenant_id=tenant.id,
        subscription_id=contract.subscription.id,
        agent_client_id=contract.client.id,
        actor_type=contract.principal.actor_type,
        subject_id=contract.principal.actor_id,
        entitlement_key="entities.read",
        phase="reserve",
        decision="deny",
        reason_code="page_depth_exceeded",
        query_sha256="b" * 64,
        cursor_chain_id="22222222-2222-2222-2222-222222222222",
        page_depth=11,
        requested_records=10,
        existing_unique_records=20,
        projected_unique_records=30,
        request_id="operations-api-risk",
        details={"configured_page_depth": 10},
        occurred_at=datetime.now(UTC),
    )
    session.add(event)
    session.commit()
    human = Principal(tenant.id, "security-admin", "user", frozenset({"*"}))

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: human
    try:
        with TestClient(app) as client:
            clients = client.get("/api/v1/commercial/clients")
            assert clients.status_code == 200
            assert clients.json()[0]["client_key"] == contract.client.client_key
            assert clients.json()[0]["denial_count_24h"] == 1

            risks = client.get("/api/v1/commercial/risk-events", params={"case_status": "open"})
            assert risks.status_code == 200
            assert risks.json()[0]["reason_code"] == "page_depth_exceeded"
            assert risks.json()[0]["case_status"] == "open"

            risk_page = client.get(
                "/api/v1/commercial/risk-events/page",
                params={"case_status": "open", "limit": 1},
            )
            assert risk_page.status_code == 200
            assert risk_page.json()["total_items"] == 1
            assert risk_page.json()["items"][0]["id"] == event.id
            assert risk_page.json()["next_cursor"] is None

            invalid_cursor = client.get(
                "/api/v1/commercial/risk-events/page",
                params={"case_status": "open", "cursor": "invalid.cursor.signature"},
            )
            assert invalid_cursor.status_code == 409
            assert invalid_cursor.json()["detail"] == "Risk pagination cursor is invalid or expired"

            reviewed = client.post(
                f"/api/v1/commercial/risk-events/{event.id}/review",
                json={"status": "acknowledged", "notes": "Owner contacted"},
            )
            assert reviewed.status_code == 200
            assert reviewed.json()["case_status"] == "acknowledged"
            assert (
                client.get(
                    "/api/v1/commercial/risk-events",
                    params={"case_status": "open"},
                ).json()
                == []
            )

            revoked = client.post(
                f"/api/v1/commercial/clients/{contract.client.id}/status",
                json={"active": False, "reason": "Credential rotation"},
            )
            assert revoked.status_code == 200
            assert revoked.json()["active"] is False
    finally:
        app.dependency_overrides.clear()


def test_human_billing_operations_api_maps_accounts_and_replays_dead_delivery(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant)
    account = session.get(BillingAccount, contract.subscription.billing_account_id)
    assert account is not None
    now = datetime.now(UTC)
    statement = CommercialAccountingService(
        session,
        tenant,
        actor_id="billing-api-test",
        statement_signer=BillingStatementSigner(
            hashlib.sha256(b"billing-api-signing-key").hexdigest(),
            key_id="billing-api-v1",
        ),
    ).create_statement(
        BillingStatementCommand(
            contract.subscription.subscription_key,
            "statement-api-operations-2026-07",
            now - timedelta(hours=1),
            now - timedelta(seconds=1),
            1,
            "billing-api-statement",
        ),
        now=now,
    )
    event = session.scalar(
        select(OutboxEvent).where(
            OutboxEvent.aggregate_id == statement.id,
            OutboxEvent.event_type == BILLING_STATEMENT_EVENT_TYPE,
        )
    )
    assert event is not None
    delivery = ProjectionDelivery(
        tenant_id=tenant.id,
        consumer_name=BILLING_CONSUMER_NAME,
        outbox_event_id=event.id,
        state=ProjectionDeliveryState.DEAD,
        attempts=3,
        available_at=now,
        last_error="unknown provider customer",
    )
    session.add(delivery)
    session.commit()
    human = Principal(tenant.id, "billing-admin", "user", frozenset({"*"}))

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: human
    try:
        with TestClient(app) as client:
            accounts = client.get("/api/v1/commercial/billing-accounts")
            assert accounts.status_code == 200
            assert accounts.json()[0]["mapping_configured"] is False
            mapped = client.post(
                f"/api/v1/commercial/billing-accounts/{account.id}/provider-mapping",
                json={
                    "external_customer_reference": "ERP-API-CUSTOMER-1001",
                    "reason": "Finance owner approved mapping",
                },
            )
            assert mapped.status_code == 200
            assert mapped.json()["external_customer_reference_masked"].endswith("1001")

            dead = client.get(
                "/api/v1/commercial/billing-deliveries",
                params={"delivery_state": "dead"},
            )
            assert dead.status_code == 200
            assert dead.json()[0]["delivery_id"] == delivery.id
            replay = client.post(
                f"/api/v1/commercial/billing-deliveries/{delivery.id}/replay",
                json={"reason": "Customer mapping has been verified"},
            )
            assert replay.status_code == 200
            assert replay.json()["state"] == "retry"
            assert (
                client.post(
                    f"/api/v1/commercial/billing-deliveries/{delivery.id}/replay",
                    json={"reason": "Duplicate replay"},
                ).status_code
                == 409
            )

            app.dependency_overrides[require_principal] = lambda: contract.principal
            assert client.get("/api/v1/commercial/billing-accounts").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_human_commercial_accounting_api_adjusts_reverses_reconciles_and_closes_period(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant)
    usage = CommercialUsageService(session, contract.principal)
    reservation = usage.reserve(
        ReserveCommand(
            "entity.search",
            "api-accounting-usage-01",
            {"q": "EGFR", "limit": 1},
            1,
            "5",
            "api-accounting-reserve",
        )
    ).reservation
    settlement = usage.settle(
        SettleCommand(
            reservation.id,
            1,
            {"items": [{"id": "entity-egfr", "confidential": "not-a-billing-line"}]},
            {},
            "api-accounting-settle",
        )
    ).settlement
    human = Principal(tenant.id, "finance-admin", "user", frozenset({"*"}))

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: human
    try:
        with TestClient(app) as client:
            adjustment = client.post(
                "/api/v1/commercial/adjustments",
                json={
                    "subscription_key": "test-subscription",
                    "adjustment_key": "api-manual-debit-0001",
                    "units_delta": "2.5",
                    "reason": "approved correction",
                    "metadata": {"ticket": "FIN-1"},
                },
            )
            assert adjustment.status_code == 200
            assert adjustment.json()["adjustment_kind"] == "usage_adjustment"

            reversal = client.post(
                f"/api/v1/commercial/settlements/{settlement.id}/reversal",
                json={
                    "adjustment_key": "api-settlement-reversal-1",
                    "reason": "approved duplicate delivery",
                },
            )
            assert reversal.status_code == 200
            assert reversal.json()["adjustment_kind"] == "settlement_reversal"

            reconciliation = client.post(
                "/api/v1/commercial/reconciliations",
                json={"subscription_key": "test-subscription", "run_key": "00000000-0000-0000-0000-000000000001"},
            )
            assert reconciliation.status_code == 200
            assert reconciliation.json()["status"] == "clean"

            period_end = datetime.now(UTC)
            statement = client.post(
                "/api/v1/commercial/statements",
                json={
                    "subscription_key": "test-subscription",
                    "statement_key": "api-statement-2026-07-r1",
                    "period_start": (period_end - timedelta(hours=1)).isoformat(),
                    "period_end": period_end.isoformat(),
                    "revision": 1,
                },
            )
            assert statement.status_code == 200
            body = statement.json()
            assert body["net_consumed_units"] == "2.50000000"
            assert body["settlement_count"] == 1
            assert body["adjustment_count"] == 2
            assert "not-a-billing-line" not in str(body["payload"])
            assert client.get(f"/api/v1/commercial/statements/{body['id']}").status_code == 200

            app.dependency_overrides[require_principal] = lambda: Principal(
                tenant.id,
                "readonly-user",
                "user",
                frozenset({"commercial:read"}),
            )
            denied = client.post(
                "/api/v1/commercial/adjustments",
                json={
                    "subscription_key": "test-subscription",
                    "adjustment_key": "api-denied-debit-0001",
                    "units_delta": "1",
                    "reason": "must be denied",
                },
            )
            assert denied.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_internal_commercial_api_rejects_human_and_unlicensed_scope(
    session: Session,
    tenant: Tenant,
) -> None:
    principals = [
        Principal(tenant.id, "human-1", "user", frozenset({"*"})),
        Principal(tenant.id, "agent-1", "agent", frozenset({"entities:read"}), "client-1"),
    ]

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as client:
            for principal in principals:
                app.dependency_overrides[require_principal] = lambda principal=principal: principal
                response = client.get("/internal/v1/commercial/access")
                assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
