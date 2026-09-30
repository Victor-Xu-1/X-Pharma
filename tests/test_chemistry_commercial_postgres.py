from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session, set_tenant_context
from pharma_intel.models import AgentClient, CompoundStructure, Entity, EntityType, ReviewStatus, Tenant
from pharma_intel.security import Principal, require_principal
from tests.support.commercial import seed_commercial_contract
from tests.support.postgres_safety import require_disposable_postgres_url, require_same_database


@pytest.mark.integration
def test_paid_chemistry_api_binds_query_compute_charge_and_tenant() -> None:
    admin_url = os.getenv("TEST_CHEMISTRY_ADMIN_DATABASE_URL")
    runtime_url = os.getenv("TEST_CHEMISTRY_RUNTIME_DATABASE_URL")
    if not admin_url or not runtime_url:
        pytest.skip("TEST_CHEMISTRY_ADMIN_DATABASE_URL and TEST_CHEMISTRY_RUNTIME_DATABASE_URL are required")
    require_disposable_postgres_url(admin_url, "TEST_CHEMISTRY_ADMIN_DATABASE_URL")
    require_disposable_postgres_url(runtime_url, "TEST_CHEMISTRY_RUNTIME_DATABASE_URL")
    require_same_database(
        admin_url,
        runtime_url,
        "TEST_CHEMISTRY_ADMIN_DATABASE_URL",
        "TEST_CHEMISTRY_RUNTIME_DATABASE_URL",
    )

    admin_engine = create_engine(admin_url, pool_pre_ping=True)
    runtime_engine = create_engine(runtime_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    other_tenant_id = str(uuid.uuid4())
    tenant_slug = f"paid-chem-{tenant_id}"
    aspirin_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"

    with Session(admin_engine) as admin_session:
        tenant = Tenant(id=tenant_id, slug=tenant_slug, name="Paid Chemistry Test")
        other_tenant = Tenant(
            id=other_tenant_id,
            slug=f"other-paid-chem-{other_tenant_id}",
            name="Other Paid Chemistry Test",
        )
        admin_session.add_all([tenant, other_tenant])
        admin_session.flush()
        aspirin = Entity(
            tenant_id=tenant_id,
            entity_type=EntityType.DRUG,
            name="Aspirin",
            normalized_name=f"aspirin-{tenant_id}",
            review_status=ReviewStatus.VERIFIED,
        )
        paracetamol = Entity(
            tenant_id=tenant_id,
            entity_type=EntityType.DRUG,
            name="Paracetamol",
            normalized_name=f"paracetamol-{tenant_id}",
            review_status=ReviewStatus.VERIFIED,
        )
        other_drug = Entity(
            tenant_id=other_tenant_id,
            entity_type=EntityType.DRUG,
            name="Ibuprofen Other Tenant",
            normalized_name=f"ibuprofen-{other_tenant_id}",
            review_status=ReviewStatus.VERIFIED,
        )
        admin_session.add_all([aspirin, paracetamol, other_drug])
        admin_session.flush()
        admin_session.add_all(
            [
                CompoundStructure(
                    tenant_id=tenant_id,
                    entity_id=aspirin.id,
                    canonical_smiles=aspirin_smiles,
                    standard_inchi_key="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                    structure_version="commercial-test/v1",
                ),
                CompoundStructure(
                    tenant_id=tenant_id,
                    entity_id=paracetamol.id,
                    canonical_smiles="CC(=O)NC1=CC=C(O)C=C1",
                    standard_inchi_key="RZVAJINKPMORJF-UHFFFAOYSA-N",
                    structure_version="commercial-test/v1",
                ),
                CompoundStructure(
                    tenant_id=other_tenant_id,
                    entity_id=other_drug.id,
                    canonical_smiles="CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
                    standard_inchi_key="HEFNNWSXXWATRW-UHFFFAOYSA-N",
                    structure_version="commercial-test/v1",
                ),
            ]
        )
        admin_session.commit()
        contract = seed_commercial_contract(
            admin_session,
            tenant,
            billing_classes={"structure.similarity": ("structures.read", 50)},
            daily_unique_record_limit=5,
            per_compute_units={"structure.similarity": Decimal("3.00000000")},
        )
        principal = Principal(
            tenant_id=tenant_id,
            actor_id=contract.principal.actor_id,
            actor_type="api_key",
            scopes=frozenset({"mcp:connect", "structures:read"}),
            client_id=contract.principal.client_id,
        )

    with Session(runtime_engine) as visibility_session:
        set_tenant_context(visibility_session, tenant_id)
        assert visibility_session.scalar(text("SELECT app_current_tenant_id()")) == tenant_id
        visible_clients = visibility_session.scalar(
            select(func.count())
            .select_from(AgentClient)
            .where(
                AgentClient.oauth_client_id == principal.client_id,
            )
        )
        assert visible_clients == 1

    def runtime_session_override() -> Generator[Session]:
        with Session(runtime_engine) as session:
            set_tenant_context(session, tenant_id)
            yield session

    app.dependency_overrides[get_session] = runtime_session_override
    app.dependency_overrides[require_principal] = lambda: principal
    arguments = {
        "mode": "similarity",
        "query": aspirin_smiles,
        "threshold": 0.1,
        "limit": 1,
    }
    try:
        with TestClient(app) as client:
            insufficient_compute = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "structure.similarity",
                    "idempotency_key": "00000000-0000-0000-0000-000000000000",
                    "request_arguments": arguments,
                    "requested_result_limit": 1,
                    "requested_compute_units": "0",
                    "max_billable_units": "10",
                },
            )
            assert insufficient_compute.status_code == 200, insufficient_compute.text
            denied = client.post(
                "/internal/v1/domain/chemistry/search",
                json=arguments,
                headers={"X-Commercial-Reservation-ID": insufficient_compute.json()["reservation_id"]},
            )
            assert denied.status_code == 403
            assert "does not authorize" in denied.json()["detail"]
            released = client.post(
                f"/internal/v1/commercial/reservations/{insufficient_compute.json()['reservation_id']}/release",
                json={"reason": "compute contract test complete"},
            )
            assert released.status_code == 200

            reservation = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "structure.similarity",
                    "idempotency_key": "00000000-0000-0000-0000-000000000001",
                    "request_arguments": arguments,
                    "requested_result_limit": 1,
                    "requested_compute_units": "1",
                    "max_billable_units": "10",
                },
            )
            assert reservation.status_code == 200
            reservation_data = reservation.json()
            assert reservation_data["requested_compute_units"] == "1.00000000"

            tampered = client.post(
                "/internal/v1/domain/chemistry/search",
                json={**arguments, "threshold": 0.9},
                headers={"X-Commercial-Reservation-ID": reservation_data["reservation_id"]},
            )
            assert tampered.status_code == 403

            search = client.post(
                "/internal/v1/domain/chemistry/search",
                json=arguments,
                headers={"X-Commercial-Reservation-ID": reservation_data["reservation_id"]},
            )
            assert search.status_code == 200
            result = search.json()
            assert [item["entity_name"] for item in result["items"]] == ["Aspirin"]
            assert result["items"][0]["similarity"] == pytest.approx(1.0)
            assert result["page_depth"] == 1
            assert result["next_cursor"]
            assert all(item["entity_name"] != "Ibuprofen Other Tenant" for item in result["items"])

            settlement = client.post(
                f"/internal/v1/commercial/reservations/{reservation_data['reservation_id']}/settle",
                json={
                    "result_count": len(result["items"]),
                    "result": result,
                    "metrics": {"tool": "structure.similarity", "compute_units": "1"},
                },
            )
            assert settlement.status_code == 200
            settlement_data = settlement.json()["settlement"]
            breakdown = settlement_data["price_breakdown"]
            assert breakdown["compute_units"] == "1.00000000"
            assert breakdown["per_compute_unit"] == "3.00000000"
            assert settlement_data["unique_record_count"] == 1
            assert settlement_data["new_unique_record_count"] == 1
            expected_charge = (
                Decimal("1") + Decimal("0.1") + Decimal("0.01") * Decimal(str(breakdown["response_kib"])) + Decimal("3")
            )
            assert Decimal(settlement_data["charged_units"]) == expected_charge

            cursor = result["next_cursor"]
            second_arguments = {**arguments, "cursor": cursor}
            second_reservation = client.post(
                "/internal/v1/commercial/reservations",
                json={
                    "billing_class": "structure.similarity",
                    "idempotency_key": "00000000-0000-0000-0000-000000000002",
                    "request_arguments": second_arguments,
                    "requested_result_limit": 1,
                    "requested_compute_units": "1",
                    "max_billable_units": "10",
                },
            )
            assert second_reservation.status_code == 200
            second_reservation_data = second_reservation.json()
            assert second_reservation_data["page_depth"] == 2

            second_search = client.post(
                "/internal/v1/domain/chemistry/search",
                params={"cursor": cursor},
                json=arguments,
                headers={"X-Commercial-Reservation-ID": second_reservation_data["reservation_id"]},
            )
            assert second_search.status_code == 200
            second_result = second_search.json()
            assert [item["entity_name"] for item in second_result["items"]] == ["Paracetamol"]
            assert second_result["page_depth"] == 2
            assert second_result["next_cursor"] is None
            assert all(item["entity_name"] != "Ibuprofen Other Tenant" for item in second_result["items"])

            second_settlement = client.post(
                f"/internal/v1/commercial/reservations/{second_reservation_data['reservation_id']}/settle",
                json={
                    "result_count": len(second_result["items"]),
                    "result": second_result,
                    "metrics": {"tool": "structure.similarity", "compute_units": "1"},
                },
            )
            assert second_settlement.status_code == 200
            second_settlement_data = second_settlement.json()["settlement"]
            assert second_settlement_data["unique_record_count"] == 1
            assert second_settlement_data["new_unique_record_count"] == 1
    finally:
        app.dependency_overrides.clear()
        admin_engine.dispose()
        runtime_engine.dispose()
