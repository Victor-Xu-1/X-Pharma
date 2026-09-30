from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.commercial.admin import CommercialAdminConflict, CommercialAdminService
from pharma_intel.commercial.cursor import SignedCursorCodec
from pharma_intel.commercial.exports import (
    CommercialExportService,
    CreateExportCommand,
    ExportManifestSigner,
    ExportValidationError,
    default_export_field_policy,
)
from pharma_intel.commercial.service import CommercialAccessDenied, IdempotencyConflict
from pharma_intel.models import (
    CommercialExportPolicy,
    DataExportJob,
    Entity,
    EntityType,
    ReviewStatus,
    Tenant,
    UsageEvent,
    UsageReservation,
    UsageReservationState,
)
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.schemas import DataExportCreate
from pharma_intel.security import Principal
from tests.support.commercial import seed_commercial_contract

SIGNING_SECRET = "export-signing-secret-for-tests-1234567890"  # noqa: S105
CURSOR_SECRET = "export-cursor-secret-for-tests-12345678901"  # noqa: S105


def test_default_export_policy_covers_every_governed_domain_dataset() -> None:
    policy = default_export_field_policy()

    assert set(policy["datasets"]) == {
        "entities",
        "structures",
        "bioactivities",
        "competitive_programs",
        "clinical_trials",
        "patents",
        "deals",
        "regulatory_events",
        "fact_provenance",
    }
    regulatory = policy["datasets"]["regulatory_events"]
    assert "source_document_id" in regulatory["fields"]
    assert {"agency", "event_type", "decision_date"} <= set(regulatory["filter_fields"])
    provenance = policy["datasets"]["fact_provenance"]
    assert {"resource_type", "resource_id", "source_version_id", "source_locator"} <= set(provenance["fields"])
    assert {"resource_type", "resource_id", "dataset_key"} <= set(provenance["filter_fields"])


def test_agent_export_request_accepts_governed_fact_provenance_dataset() -> None:
    request = DataExportCreate(
        dataset="fact_provenance",
        export_format="jsonl",
        filters={"resource_id": "11111111-1111-4111-8111-111111111111"},
        fields=["resource_id", "source_version_id", "source_locator"],
        max_records=10,
        max_billable_units="100",
        idempotency_key="fact-provenance-export-0001",
    )

    assert request.dataset == "fact_provenance"


def test_new_customer_export_allowlist_matches_licensed_field_policy(
    session: Session,
    tenant: Tenant,
) -> None:
    seed_commercial_contract(
        session,
        tenant,
        billing_classes={"export.data": ("data.export", 5000)},
        granted_units=Decimal("1000"),
    )

    policy = session.scalar(select(CommercialExportPolicy).where(CommercialExportPolicy.tenant_id == tenant.id))
    assert policy is not None
    assert set(policy.allowed_datasets) == set(default_export_field_policy()["datasets"])


def _service(session: Session, root: Path) -> CommercialExportService:
    return CommercialExportService(
        session,
        FileSystemObjectStore(root),
        ExportManifestSigner(SIGNING_SECRET, key_id="test-export-v1"),
        SignedCursorCodec(CURSOR_SECRET),
        export_reservation_lease_seconds=7200,
        read_page_size_max=10,
    )


def _command(
    key: str,
    *,
    max_records: int = 2,
    filters: dict[str, object] | None = None,
    fields: list[str] | None = None,
) -> CreateExportCommand:
    return CreateExportCommand(
        dataset="entities",
        export_format="jsonl",
        filters=filters or {},
        fields=fields if fields is not None else ["id", "name", "entity_type", "external_ids", "created_at"],
        max_records=max_records,
        max_billable_units=Decimal("200"),
        idempotency_key=key,
    )


def _seed_entities(session: Session, tenant: Tenant) -> None:
    session.add_all(
        Entity(
            tenant_id=tenant.id,
            entity_type=EntityType.TARGET,
            name=name,
            normalized_name=name.casefold(),
            external_ids={"symbol": name},
            review_status=ReviewStatus.VERIFIED,
        )
        for name in ("EGFR", "KRAS", "BRAF")
    )
    session.commit()


def test_export_executes_settles_signs_and_reads_owned_chunks(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={"export.data": ("data.export", 5000)},
        granted_units=Decimal("1000"),
        max_response_bytes=10_000_000,
    )
    _seed_entities(session, tenant)
    service = _service(session, tmp_path)

    queued = service.create(contract.principal, _command("export-entities-0001"))
    assert queued.state == "queued"
    assert queued.reservation_id is not None

    completed = service.execute(tenant.id, queued.id)
    assert completed.state == "completed"
    assert completed.record_count == 2
    assert completed.artifact_sha256
    assert completed.manifest_signature
    assert completed.manifest_key_id == "test-export-v1"
    assert completed.license_policy_version == "test-v1"
    assert len(completed.license_policy_sha256) == 64
    usage = session.scalar(select(UsageEvent).where(UsageEvent.reservation_id == completed.reservation_id))
    assert usage is not None
    assert usage.result_count == 2
    assert usage.response_bytes == completed.artifact_bytes

    first = service.read_chunk(contract.principal, completed.id, limit=1, cursor=None)
    assert first.count == 1
    assert first.items[0]["name"] in {"EGFR", "KRAS", "BRAF"}
    assert first.next_cursor
    assert first.manifest["schema"] == "pharma.data-export-envelope.v1"
    assert first.manifest["payload"]["license"] == {
        "policy_version": completed.license_policy_version,
        "policy_sha256": completed.license_policy_sha256,
        "attribution": completed.license_attribution,
    }
    second = service.read_chunk(contract.principal, completed.id, limit=1, cursor=first.next_cursor)
    assert second.items[0]["id"] != first.items[0]["id"]

    wrong_subject = replace(contract.principal, actor_id="different-subject")
    with pytest.raises(CommercialAccessDenied):
        service.read_chunk(wrong_subject, completed.id, limit=1, cursor=None)


def test_export_approval_idempotency_validation_and_cancel_release(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={"export.data": ("data.export", 5000)},
        granted_units=Decimal("1000"),
        max_response_bytes=10_000_000,
    )
    service = _service(session, tmp_path)
    pending = service.create(contract.principal, _command("export-approval-001", max_records=1001))
    assert pending.state == "pending_approval"
    assert pending.reservation_id is None

    replay = service.create(contract.principal, _command("export-approval-001", max_records=1001))
    assert replay.id == pending.id
    with pytest.raises(IdempotencyConflict):
        service.create(contract.principal, _command("export-approval-001", max_records=1002))

    operator = Principal(tenant.id, "operator-1", "user", frozenset({"commercial:write"}))
    queued = service.approve(operator, pending.id)
    assert queued.state == "queued"
    assert queued.approved_by == "operator-1"
    reservation = session.get(UsageReservation, queued.reservation_id)
    assert reservation is not None and reservation.state == UsageReservationState.RESERVED

    cancelled = service.cancel(contract.principal, queued.id)
    assert cancelled.state == "cancelled"
    released_reservation = session.get(UsageReservation, reservation.id, populate_existing=True)
    assert released_reservation is not None
    assert released_reservation.state == UsageReservationState.RELEASED

    with pytest.raises(ExportValidationError):
        service.create(
            contract.principal,
            _command("export-invalid-0001", filters={"description": {"contains": "secret"}}),
        )
    jobs = session.scalars(select(DataExportJob).where(DataExportJob.tenant_id == tenant.id)).all()
    assert len(jobs) == 1


def _restricted_entity_policy(version: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "policy_version": version,
        "attribution": "Contracted entity subset",
        "datasets": {
            "entities": {
                "fields": ["id", "name"],
                "filter_fields": ["id"],
            }
        },
    }


def test_export_field_and_filter_licenses_are_enforced_and_revocable(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={"export.data": ("data.export", 5000)},
        granted_units=Decimal("1000"),
        max_response_bytes=10_000_000,
    )
    _seed_entities(session, tenant)
    policy = session.scalar(select(CommercialExportPolicy).where(CommercialExportPolicy.tenant_id == tenant.id))
    assert policy is not None
    policy.field_policy = _restricted_entity_policy("contract-v1")
    session.commit()
    service = _service(session, tmp_path)

    with pytest.raises(ExportValidationError, match="unlicensed"):
        service.create(contract.principal, _command("export-field-denied-001"))
    with pytest.raises(ExportValidationError, match="filter"):
        service.create(
            contract.principal,
            _command(
                "export-filter-denied-001",
                filters={"name": "EGFR"},
                fields=[],
            ),
        )

    queued = service.create(
        contract.principal,
        _command("export-licensed-subset-001", fields=[]),
    )
    assert queued.fields_json == ["id", "name"]
    completed = service.execute(tenant.id, queued.id)

    admin = CommercialAdminService(session, tenant, actor_id="operator-1")
    admin.set_export_field_policy("test-account", _restricted_entity_policy("contract-v2"))
    with pytest.raises(CommercialAccessDenied, match="license policy changed"):
        service.read_chunk(contract.principal, completed.id, limit=1, cursor=None)
    with pytest.raises(CommercialAdminConflict, match="cannot be reused"):
        admin.set_export_field_policy("test-account", _restricted_entity_policy("contract-v1"))
