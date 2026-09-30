from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.commercial.cursor import SignedCursorCodec
from pharma_intel.commercial.exports import (
    CommercialExportService,
    CreateExportCommand,
    ExportManifestSigner,
)
from pharma_intel.commercial.operations import (
    CommercialOperationsConflict,
    CommercialOperationsService,
)
from pharma_intel.commercial.risk_cursor import RiskCursorCodec, RiskCursorError
from pharma_intel.commercial.service import CommercialNotConfigured, CommercialUsageService, ReserveCommand
from pharma_intel.models import (
    AgentClient,
    AuditEvent,
    CommercialPolicyEvent,
    DataExportJob,
    Tenant,
    UsageReservation,
    UsageReservationState,
)
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.security import Principal
from tests.support.commercial import seed_commercial_contract


def test_client_revocation_releases_credit_cancels_exports_and_blocks_new_access(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={
            "entity.search": ("entities.read", 100),
            "export.data": ("data.export", 5000),
        },
        granted_units=Decimal("1000"),
        max_response_bytes=10_000_000,
    )
    interactive = (
        CommercialUsageService(session, contract.principal)
        .reserve(ReserveCommand("entity.search", "revoke-reserve-001", {"q": "EGFR"}, 1, "10", "revoke-test"))
        .reservation
    )
    export_service = CommercialExportService(
        session,
        FileSystemObjectStore(tmp_path),
        ExportManifestSigner("operation-export-signing-secret-123456789", key_id="operations-v1"),  # noqa: S106
        SignedCursorCodec("operation-export-cursor-secret-12345678901"),  # noqa: S106
    )
    export = export_service.create(
        contract.principal,
        CreateExportCommand("entities", "jsonl", {}, ["id", "name"], 2, "10", "revoke-export-0001"),
    )
    assert export.state == "queued"
    export_reservation_id = export.reservation_id

    operator = Principal(tenant.id, "security-operator", "user", frozenset({"*"}))
    result = CommercialOperationsService(session, operator).set_client_active(
        contract.client.id,
        active=False,
        reason="credential compromise investigation",
    )

    assert result["active"] is False
    assert result["active_reservations"] == 0
    assert session.get(UsageReservation, interactive.id).state == UsageReservationState.RELEASED  # type: ignore[union-attr]
    assert session.get(UsageReservation, export_reservation_id).state == UsageReservationState.RELEASED  # type: ignore[union-attr]
    assert session.get(DataExportJob, export.id).state == "cancelled"  # type: ignore[union-attr]
    assert session.get(AgentClient, contract.client.id).active is False  # type: ignore[union-attr]
    assert session.scalar(
        select(AuditEvent).where(
            AuditEvent.resource_id == contract.client.id,
            AuditEvent.action == "commercial.client.revoke",
        )
    )
    with pytest.raises(CommercialNotConfigured):
        CommercialUsageService(session, contract.principal).reserve(
            ReserveCommand("entity.search", "revoke-blocked-001", {"q": "KRAS"}, 1, "10", "blocked")
        )

    reactivated = CommercialOperationsService(session, operator).set_client_active(
        contract.client.id,
        active=True,
        reason="new credential binding approved",
    )
    assert reactivated["active"] is True


def test_denied_risk_events_have_persisted_review_workflow(session: Session, tenant: Tenant) -> None:
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
        reason_code="cross_client_partition_limit_exceeded",
        query_sha256="a" * 64,
        cursor_chain_id="11111111-1111-1111-1111-111111111111",
        page_depth=1,
        requested_records=100,
        existing_unique_records=1000,
        projected_unique_records=1100,
        request_id="risk-review-request",
        details={"distinct_clients": 3},
        occurred_at=datetime.now(UTC),
    )
    session.add(event)
    session.commit()
    operator = Principal(tenant.id, "risk-operator", "user", frozenset({"*"}))
    operations = CommercialOperationsService(session, operator)

    opened = operations.list_risk_events(status="open")
    assert len(opened) == 1
    assert opened[0]["case_status"] == "open"
    acknowledged = operations.review_risk_event(
        event.id,
        status="acknowledged",
        notes="Client owner contacted",
    )
    assert acknowledged["case_status"] == "acknowledged"
    assert operations.list_risk_events(status="open") == []
    assert len(operations.list_risk_events(status="acknowledged")) == 1

    resolved = operations.review_risk_event(event.id, status="resolved", notes="Credential rotated")
    assert resolved["case_status"] == "resolved"
    with pytest.raises(CommercialOperationsConflict):
        operations.review_risk_event(event.id, status="dismissed", notes="Cannot rewrite closure")


def test_risk_event_page_uses_signed_filter_bound_keyset_cursor(session: Session, tenant: Tenant) -> None:
    contract = seed_commercial_contract(session, tenant)
    occurred_at = datetime.now(UTC)
    for ordinal in range(1, 4):
        session.add(
            CommercialPolicyEvent(
                id=f"00000000-0000-0000-0000-{ordinal:012d}",
                tenant_id=tenant.id,
                subscription_id=contract.subscription.id,
                agent_client_id=contract.client.id,
                actor_type=contract.principal.actor_type,
                subject_id=contract.principal.actor_id,
                entitlement_key="entities.read",
                phase="reserve",
                decision="deny",
                reason_code="page_depth_exceeded",
                query_sha256=f"{ordinal:x}" * 64,
                cursor_chain_id=f"11111111-1111-1111-1111-{ordinal:012d}",
                page_depth=ordinal,
                requested_records=10,
                existing_unique_records=20,
                projected_unique_records=30,
                request_id=f"risk-page-{ordinal}",
                details={},
                occurred_at=occurred_at,
            )
        )
    session.commit()
    operator = Principal(tenant.id, "risk-operator", "user", frozenset({"commercial:read"}))
    codec = RiskCursorCodec("risk-pagination-test-secret-123456789012")  # noqa: S106
    service = CommercialOperationsService(session, operator)

    first = service.list_risk_event_page(status="open", limit=2, cursor=None, cursor_codec=codec)
    assert first.total_items == 3
    assert [item["request_id"] for item in first.items] == ["risk-page-3", "risk-page-2"]
    assert first.next_cursor is not None

    second = service.list_risk_event_page(
        status="open",
        limit=2,
        cursor=first.next_cursor,
        cursor_codec=codec,
    )
    assert second.total_items == 3
    assert [item["request_id"] for item in second.items] == ["risk-page-1"]
    assert second.next_cursor is None

    with pytest.raises(RiskCursorError, match="invalid or expired"):
        service.list_risk_event_page(
            status="all",
            limit=2,
            cursor=first.next_cursor,
            cursor_codec=codec,
        )
    with pytest.raises(RiskCursorError, match="invalid or expired"):
        service.list_risk_event_page(
            status="open",
            limit=1,
            cursor=first.next_cursor,
            cursor_codec=codec,
        )
    other_operator = Principal(tenant.id, "other-operator", "user", frozenset({"commercial:read"}))
    with pytest.raises(RiskCursorError, match="invalid or expired"):
        CommercialOperationsService(session, other_operator).list_risk_event_page(
            status="open",
            limit=2,
            cursor=first.next_cursor,
            cursor_codec=codec,
        )
