from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.commercial.admin import (
    CommercialAdminConflict,
    CommercialAdminService,
    ProvisionClientCommand,
    RateCardMigrationCommand,
)
from pharma_intel.commercial.cursor import SignedCursorCodec, query_fingerprint
from pharma_intel.commercial.exports import default_export_field_policy
from pharma_intel.commercial.plans import RateCardDefinition
from pharma_intel.commercial.service import (
    CommercialAccessDenied,
    CommercialUsageService,
    IdempotencyConflict,
    InsufficientCredits,
    ReservationConflict,
    ReservationExpired,
    ReserveCommand,
    SettleCommand,
    SettlementLimitExceeded,
)
from pharma_intel.models import (
    AuditEvent,
    CommercialCoverageRecord,
    CommercialEntitlement,
    CommercialLedgerEntry,
    CommercialPolicyEvent,
    CommercialRiskPolicy,
    CommercialSubscription,
    OutboxEvent,
    RateCardVersion,
    Tenant,
    UsageEvent,
    UsageReservationState,
    UsageSettlement,
)
from pharma_intel.security import Principal
from tests.support.commercial import seed_commercial_contract


def _provision_related_client(
    session: Session,
    tenant: Tenant,
    *,
    suffix: str,
) -> Principal:
    admin = CommercialAdminService(session, tenant, actor_id="risk-test-admin")
    admin.provision_client(
        ProvisionClientCommand(
            client_key=f"related-{suffix}",
            oauth_client_id=f"related-oauth-{suffix}",
            display_name=f"Related Client {suffix}",
            actor_type="api_key",
            subject_id=f"related-subject-{suffix}",
            account_key="test-account",
            account_name="Test Billing Account",
            subscription_key=f"related-subscription-{suffix}",
            rate_card_key="test-plan",
            rate_card_revision=1,
            created_by="risk-test-admin",
            export_field_policy=default_export_field_policy(policy_version="test-v1"),
        )
    )
    admin.grant_credit(
        f"related-subscription-{suffix}",
        Decimal("100"),
        external_reference=f"risk-test-credit-{suffix}",
        reason="risk integration test",
    )
    return Principal(
        tenant_id=tenant.id,
        actor_id=f"related-subject-{suffix}",
        actor_type="api_key",
        scopes=frozenset({"mcp:connect", "entities:read"}),
        client_id=f"related-oauth-{suffix}",
    )


def test_reserve_settle_and_replay_preserve_exact_single_charge(session: Session, tenant: Tenant) -> None:
    contract = seed_commercial_contract(session, tenant)
    service = CommercialUsageService(session, contract.principal)
    command = ReserveCommand(
        billing_class="entity.search",
        idempotency_key="entity-search-0001",
        request_arguments={"q": "EGFR", "limit": 10},
        requested_result_limit=10,
        max_billable_units="5.00000000",
        request_id="request-reserve-1",
    )

    reserved = service.reserve(command)

    assert reserved.replayed is False
    assert reserved.reservation.state == UsageReservationState.RESERVED
    assert reserved.reservation.estimated_units == Decimal("2.00000000")
    session.refresh(contract.subscription)
    assert contract.subscription.reserved_units == Decimal("5.00000000")

    result = {"items": [{"id": "target-1"}, {"id": "target-2"}], "total": 2, "limit": 10, "offset": 0}
    settled = service.settle(
        SettleCommand(
            reservation_id=reserved.reservation.id,
            result_count=2,
            result=result,
            metrics={"tool": "entity.search"},
            request_id="request-settle-1",
        )
    )

    assert settled.replayed is False
    assert settled.settlement.charged_units == Decimal("1.21000000")
    assert settled.settlement.result_json == result
    assert settled.usage_event.result_count == 2
    session.refresh(contract.subscription)
    assert contract.subscription.reserved_units == Decimal("0E-8")
    assert contract.subscription.consumed_units == Decimal("1.21000000")

    replay = service.reserve(command)
    replay_settlement = service.settle(
        SettleCommand(
            reservation_id=reserved.reservation.id,
            result_count=2,
            result=result,
            metrics={"tool": "entity.search"},
            request_id="request-settle-retry",
        )
    )
    assert replay.replayed is True and replay.settlement is not None
    assert replay.settlement.id == settled.settlement.id
    assert replay_settlement.replayed is True
    assert session.scalar(select(func.count()).select_from(UsageSettlement)) == 1
    assert session.scalar(select(func.count()).select_from(CommercialLedgerEntry)) == 3
    with pytest.raises(IdempotencyConflict):
        service.reserve(replace(command, network_fingerprint="a" * 64))


def test_entity_dossier_bills_and_limits_each_nested_domain_record(session: Session, tenant: Tenant) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={"entity.dossier": ("dossiers.read", 1001)},
        daily_unique_record_limit=20,
    )
    service = CommercialUsageService(session, contract.principal)
    reservation = service.reserve(
        ReserveCommand(
            "entity.dossier",
            "entity-dossier-coverage-1",
            {"entity_id": "entity-1", "domain_limit": 2, "limit": 17},
            17,
            "10",
            "request-dossier-reserve",
        )
    ).reservation
    dossier = {
        "entity": {"id": "entity-1"},
        "relationships": [{"id": "relationship-1"}],
        "target_evidence": [],
        "activities": [],
        "programs": [],
        "clinical_trials": [{"id": "trial-1"}],
        "patents": [],
        "deals": [],
        "regulatory_events": [],
        "news_events": [],
        "structures": [],
        "coverage": [],
        "warnings": [],
    }

    settled = service.settle(
        SettleCommand(
            reservation.id,
            3,
            dossier,
            {"tool": "entity.dossier"},
            "request-dossier-settle",
        )
    )

    assert settled.usage_event.result_count == 3
    assert settled.usage_event.unique_record_count == 3
    assert settled.usage_event.new_unique_record_count == 3
    assert session.scalar(select(func.count()).select_from(CommercialCoverageRecord)) == 3


def test_entity_dossier_rejects_underdeclared_nested_result_count(session: Session, tenant: Tenant) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={"entity.dossier": ("dossiers.read", 1001)},
    )
    service = CommercialUsageService(session, contract.principal)
    reservation = service.reserve(
        ReserveCommand("entity.dossier", "entity-dossier-count-01", {}, 9, "10", "request-dossier-count")
    ).reservation
    dossier = {
        "entity": {"id": "entity-1"},
        "relationships": [],
        "target_evidence": [],
        "activities": [],
        "programs": [],
        "clinical_trials": [{"id": "trial-1"}],
        "patents": [],
        "deals": [],
        "regulatory_events": [],
        "news_events": [],
        "structures": [],
    }

    with pytest.raises(SettlementLimitExceeded, match="Declared result count"):
        service.settle(
            SettleCommand(
                reservation.id,
                1,
                dossier,
                {"tool": "entity.dossier"},
                "request-dossier-count-settle",
            )
        )


def test_commercial_limits_idempotency_and_release_fail_closed(session: Session, tenant: Tenant) -> None:
    contract = seed_commercial_contract(session, tenant, granted_units=Decimal("3.00000000"))
    service = CommercialUsageService(session, contract.principal)

    with pytest.raises(CommercialAccessDenied, match="licensed entitlement"):
        service.reserve(ReserveCommand("entity.search", "limit-denied-001", {}, 101, "20", "request-limit"))
    with pytest.raises(SettlementLimitExceeded, match="below the request estimate"):
        service.reserve(ReserveCommand("entity.search", "estimate-low-001", {}, 20, "2", "request-estimate"))
    with pytest.raises(InsufficientCredits):
        service.reserve(ReserveCommand("entity.search", "credit-low-0001", {}, 10, "3.00000001", "request-credit"))

    command = ReserveCommand("entity.search", "stable-key-00001", {"q": "EGFR"}, 5, "2", "request-a")
    reservation = service.reserve(command).reservation
    with pytest.raises(IdempotencyConflict):
        service.reserve(ReserveCommand("entity.search", "stable-key-00001", {"q": "KRAS"}, 5, "2", "request-b"))
    released = service.release(reservation.id, reason="domain failed", request_id="request-release")
    assert released.reservation.state == UsageReservationState.RELEASED
    assert service.release(reservation.id, reason="retry", request_id="request-release-retry").replayed is True
    with pytest.raises(ReservationConflict):
        service.settle(SettleCommand(reservation.id, 0, {"items": []}, {}, "request-invalid-settle"))
    session.refresh(contract.subscription)
    assert contract.subscription.reserved_units == Decimal("0E-8")
    assert contract.subscription.consumed_units == Decimal("0E-8")


def test_compute_units_are_reserved_bound_and_settled_from_immutable_rate_card(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={"structure.similarity": ("structures.read", 50)},
        per_compute_units={"structure.similarity": Decimal("3.00000000")},
    )
    service = CommercialUsageService(session, contract.principal)
    arguments = {
        "mode": "similarity",
        "query": "CC(=O)OC1=CC=CC=C1C(=O)O",
        "threshold": 0.7,
        "limit": 2,
    }
    reservation = service.reserve(
        ReserveCommand(
            "structure.similarity",
            "compute-meter-0001",
            arguments,
            2,
            "10",
            "compute-reserve-1",
            requested_compute_units="1",
        )
    ).reservation

    assert reservation.estimated_units == Decimal("4.20000000")
    assert reservation.requested_compute_units == Decimal("1.00000000")
    service.authorize_paginated_query(
        reservation.id,
        billing_class="structure.similarity",
        request_arguments=arguments,
        page_size=2,
        required_compute_units="1",
    )
    with pytest.raises(ReservationConflict, match="already been claimed"):
        service.authorize_paginated_query(
            reservation.id,
            billing_class="structure.similarity",
            request_arguments=arguments,
            page_size=2,
            required_compute_units="1",
        )
    with pytest.raises(CommercialAccessDenied, match="does not authorize"):
        service.authorize_paginated_query(
            reservation.id,
            billing_class="structure.similarity",
            request_arguments=arguments,
            page_size=2,
            required_compute_units="0",
        )

    settled = service.settle(
        SettleCommand(
            reservation.id,
            1,
            {"items": [{"id": "structure-1", "standard_inchi_key": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"}]},
            {"tool": "structure.similarity", "compute_units": "1"},
            "compute-settle-1",
        )
    )
    assert settled.settlement.charged_units == Decimal("4.11000000")
    assert settled.settlement.price_breakdown["compute_units"] == "1.00000000"
    assert settled.settlement.price_breakdown["per_compute_unit"] == "3.00000000"

    second = service.reserve(
        ReserveCommand(
            "structure.similarity",
            "compute-meter-0002",
            arguments,
            2,
            "10",
            "compute-reserve-2",
            requested_compute_units="1",
        )
    ).reservation
    with pytest.raises(SettlementLimitExceeded, match="compute units do not match"):
        service.settle(
            SettleCommand(
                second.id,
                0,
                {"items": []},
                {"compute_units": "2"},
                "compute-overrun",
            )
        )


def test_expired_reservation_is_released_without_charge(session: Session, tenant: Tenant) -> None:
    contract = seed_commercial_contract(session, tenant)
    service = CommercialUsageService(session, contract.principal, reservation_lease_seconds=15)
    now = datetime.now(UTC)
    reservation = service.reserve(
        ReserveCommand("entity.search", "expiring-key-001", {}, 1, "2", "request-expire"),
        now=now,
    ).reservation

    with pytest.raises(ReservationExpired):
        service.settle(
            SettleCommand(reservation.id, 1, {"items": [{"id": "one"}]}, {}, "request-late"),
            now=now + timedelta(seconds=16),
        )

    session.refresh(reservation)
    session.refresh(contract.subscription)
    assert reservation.state == UsageReservationState.EXPIRED
    assert contract.subscription.reserved_units == Decimal("0E-8")
    assert contract.subscription.consumed_units == Decimal("0E-8")
    assert session.scalar(select(func.count()).select_from(UsageSettlement)) == 0


def test_daily_limit_counts_active_reservations_and_settlement_count_is_server_verified(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant)
    entitlement = session.scalar(
        select(CommercialEntitlement).where(CommercialEntitlement.subscription_id == contract.subscription.id)
    )
    assert entitlement is not None
    entitlement.daily_unit_limit = Decimal("4.00000000")
    session.commit()
    service = CommercialUsageService(session, contract.principal)
    first = service.reserve(
        ReserveCommand("entity.search", "daily-limit-first", {}, 5, "3", "request-daily-1")
    ).reservation

    with pytest.raises(CommercialAccessDenied, match="Daily licensed"):
        service.reserve(ReserveCommand("entity.search", "daily-limit-second", {}, 5, "2", "request-daily-2"))
    with pytest.raises(SettlementLimitExceeded, match="does not match"):
        service.settle(SettleCommand(first.id, 0, {"items": [{"id": "one"}]}, {}, "request-count-mismatch"))

    service.release(first.id, reason="test complete", request_id="request-daily-release")


def test_signed_pagination_chain_enforces_depth_query_and_client_binding(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant, max_page_depth=2)
    codec = SignedCursorCodec("service-cursor-secret-that-is-at-least-thirty-two-bytes")  # noqa: S106
    service = CommercialUsageService(session, contract.principal, cursor_codec=codec)
    first = service.reserve(
        ReserveCommand(
            "entity.search",
            "cursor-first-page",
            {"q": "EGFR", "limit": 2},
            2,
            "5",
            "request-cursor-1",
        )
    ).reservation
    cursor = service.issue_next_cursor(first, next_offset=2, has_more=True)
    assert cursor is not None

    second = service.reserve(
        ReserveCommand(
            "entity.search",
            "cursor-second-page",
            {"q": "EGFR", "limit": 2, "cursor": cursor},
            2,
            "5",
            "request-cursor-2",
        )
    ).reservation
    assert second.page_offset == 2
    assert second.page_depth == 2
    assert second.cursor_chain_id == first.cursor_chain_id
    assert service.issue_next_cursor(second, next_offset=4, has_more=True) is None

    fingerprint = query_fingerprint("entity.search", {"q": "EGFR", "limit": 2}, 2)
    depth_three = codec.issue(
        contract.principal,
        tool="entity.search",
        query_sha256=fingerprint,
        page_size=2,
        offset=4,
        depth=3,
        chain_id=first.cursor_chain_id,
    )
    with pytest.raises(CommercialAccessDenied, match="pagination depth"):
        service.reserve(
            ReserveCommand(
                "entity.search",
                "cursor-third-page",
                {"q": "EGFR", "limit": 2, "cursor": depth_three},
                2,
                "5",
                "request-cursor-3",
            )
        )
    denied = session.scalar(
        select(CommercialPolicyEvent).where(CommercialPolicyEvent.reason_code == "page_depth_exceeded")
    )
    assert denied is not None and denied.decision == "deny"

    service.release(first.id, reason="cursor test complete", request_id="release-cursor-1")
    service.release(second.id, reason="cursor test complete", request_id="release-cursor-2")


def test_active_reservation_limit_is_serialized_and_audited(session: Session, tenant: Tenant) -> None:
    contract = seed_commercial_contract(session, tenant)
    service = CommercialUsageService(session, contract.principal, max_active_reservations_per_client=1)
    first = service.reserve(
        ReserveCommand("entity.search", "active-limit-first", {"q": "EGFR", "limit": 1}, 1, "2", "active-1")
    ).reservation

    with pytest.raises(CommercialAccessDenied, match="Concurrent commercial"):
        service.reserve(
            ReserveCommand("entity.search", "active-limit-next1", {"q": "KRAS", "limit": 1}, 1, "2", "active-2")
        )
    event = session.scalar(
        select(CommercialPolicyEvent).where(CommercialPolicyEvent.reason_code == "active_reservation_limit_exceeded")
    )
    assert event is not None and event.decision == "deny"
    service.release(first.id, reason="active limit test complete", request_id="active-release")


def test_exact_daily_coverage_deduplicates_stable_records_across_tools(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        billing_classes={
            "entity.search": ("entities.read", 10),
            "entity.resolve": ("entities.read", 10),
        },
        daily_unique_record_limit=3,
    )
    service = CommercialUsageService(session, contract.principal)

    first = service.reserve(
        ReserveCommand("entity.search", "coverage-first-01", {"q": "EGFR", "limit": 2}, 2, "5", "coverage-1")
    ).reservation
    service.settle(
        SettleCommand(
            first.id,
            2,
            {"items": [{"id": "entity-1"}, {"id": "entity-2"}]},
            {},
            "coverage-settle-1",
        )
    )
    duplicate = service.reserve(
        ReserveCommand(
            "entity.resolve",
            "coverage-duplicate",
            {"q": "P00533", "limit": 1},
            1,
            "5",
            "coverage-2",
        )
    ).reservation
    service.settle(SettleCommand(duplicate.id, 1, {"items": [{"id": "entity-2"}]}, {}, "coverage-settle-2"))
    third = service.reserve(
        ReserveCommand("entity.search", "coverage-third-001", {"q": "KRAS", "limit": 1}, 1, "5", "coverage-3")
    ).reservation
    service.settle(SettleCommand(third.id, 1, {"items": [{"id": "entity-3"}]}, {}, "coverage-settle-3"))

    with pytest.raises(CommercialAccessDenied, match="unique-record coverage"):
        service.reserve(
            ReserveCommand("entity.search", "coverage-denied-01", {"q": "BRAF", "limit": 1}, 1, "5", "coverage-4")
        )

    coverage = session.scalars(select(CommercialCoverageRecord)).all()
    events = session.scalars(select(UsageEvent)).all()
    assert len(coverage) == 3
    assert {item.record_type for item in coverage} == {"entity"}
    assert sorted((event.unique_record_count, event.new_unique_record_count) for event in events) == [
        (1, 0),
        (1, 1),
        (2, 2),
    ]
    denied = session.scalar(
        select(CommercialPolicyEvent).where(CommercialPolicyEvent.reason_code == "daily_unique_record_limit_exceeded")
    )
    assert denied is not None
    assert denied.existing_unique_records == 3
    assert denied.projected_unique_records == 4


def test_account_risk_denies_partition_enumeration_coordinated_across_clients(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant)
    related_principal = _provision_related_client(session, tenant, suffix="partition")
    policy = session.scalar(select(CommercialRiskPolicy).where(CommercialRiskPolicy.tenant_id == tenant.id))
    assert policy is not None
    policy.max_cross_client_partition_queries_per_window = 2
    session.commit()

    first_service = CommercialUsageService(session, contract.principal)
    first = first_service.reserve(
        ReserveCommand("entity.search", "partition-first", {"q": "A", "limit": 1}, 1, "5", "risk-a")
    ).reservation
    first_service.release(first.id, reason="risk test page complete", request_id="risk-release-a")

    related_service = CommercialUsageService(session, related_principal)
    second = related_service.reserve(
        ReserveCommand("entity.search", "partition-second", {"q": "B", "limit": 1}, 1, "5", "risk-b")
    ).reservation
    related_service.release(second.id, reason="risk test page complete", request_id="risk-release-b")

    with pytest.raises(CommercialAccessDenied, match="Cross-client partition enumeration"):
        first_service.reserve(
            ReserveCommand("entity.search", "partition-third", {"q": "C", "limit": 1}, 1, "5", "risk-c")
        )

    denied = session.scalar(
        select(CommercialPolicyEvent).where(
            CommercialPolicyEvent.reason_code == "cross_client_partition_enumeration_detected"
        )
    )
    assert denied is not None
    assert denied.details["window_partition_count"] == 3
    assert denied.details["window_partition_client_count"] == 2
    assert denied.details["risk_signal"] == "partition_query"
    assert "A" not in str(denied.details) and "B" not in str(denied.details) and "C" not in str(denied.details)


def test_account_risk_denies_network_rotation_without_persisting_raw_addresses(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant)
    policy = session.scalar(select(CommercialRiskPolicy).where(CommercialRiskPolicy.tenant_id == tenant.id))
    assert policy is not None
    policy.max_distinct_networks_per_window = 2
    session.commit()
    service = CommercialUsageService(session, contract.principal)

    for index, fingerprint in enumerate(("a" * 64, "b" * 64), start=1):
        reservation = service.reserve(
            ReserveCommand(
                "entity.search",
                f"network-rotation-{index:02d}",
                {"q": "EGFR", "limit": 1},
                1,
                "5",
                f"network-risk-{index}",
                network_fingerprint=fingerprint,
                correlation_key_id="correlation-v1",
            )
        ).reservation
        service.release(reservation.id, reason="network risk test", request_id=f"network-release-{index}")

    with pytest.raises(CommercialAccessDenied, match="network rotation"):
        service.reserve(
            ReserveCommand(
                "entity.search",
                "network-rotation-03",
                {"q": "EGFR", "limit": 1},
                1,
                "5",
                "network-risk-3",
                network_fingerprint="c" * 64,
                correlation_key_id="correlation-v1",
            )
        )

    denied = session.scalar(
        select(CommercialPolicyEvent).where(CommercialPolicyEvent.reason_code == "network_rotation_limit_exceeded")
    )
    assert denied is not None
    assert denied.details["window_distinct_network_count"] == 3
    assert denied.details["network_fingerprint"] == "c" * 64
    assert "198.51.100" not in str(denied.details)


def test_account_risk_denies_credential_rotation_within_one_bound_client(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant)
    policy = session.scalar(select(CommercialRiskPolicy).where(CommercialRiskPolicy.tenant_id == tenant.id))
    assert policy is not None
    policy.max_distinct_credentials_per_window = 2
    session.commit()

    for index, fingerprint in enumerate(("a" * 64, "b" * 64), start=1):
        principal = replace(contract.principal, credential_fingerprint=fingerprint)
        service = CommercialUsageService(session, principal)
        reservation = service.reserve(
            ReserveCommand(
                "entity.search",
                f"credential-rotation-{index:02d}",
                {"q": "EGFR", "limit": 1},
                1,
                "5",
                f"credential-risk-{index}",
                correlation_key_id="correlation-v1",
            )
        ).reservation
        service.release(reservation.id, reason="credential risk test", request_id=f"credential-release-{index}")

    rotated = CommercialUsageService(session, replace(contract.principal, credential_fingerprint="c" * 64))
    with pytest.raises(CommercialAccessDenied, match="credential rotation"):
        rotated.reserve(
            ReserveCommand(
                "entity.search",
                "credential-rotation-03",
                {"q": "EGFR", "limit": 1},
                1,
                "5",
                "credential-risk-3",
                correlation_key_id="correlation-v1",
            )
        )

    denied = session.scalar(
        select(CommercialPolicyEvent).where(CommercialPolicyEvent.reason_code == "credential_rotation_limit_exceeded")
    )
    assert denied is not None
    assert denied.details["window_distinct_credential_count"] == 3


def test_reservation_rejects_an_invalid_principal_credential_fingerprint(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant)
    service = CommercialUsageService(session, replace(contract.principal, credential_fingerprint="not-a-fingerprint"))

    with pytest.raises(ValueError, match="Credential fingerprint is invalid"):
        service.reserve(
            ReserveCommand(
                "entity.search",
                "invalid-credential-fingerprint",
                {"q": "EGFR", "limit": 1},
                1,
                "5",
                "invalid-credential-request",
            )
        )


def test_account_daily_coverage_cannot_be_split_across_client_subscriptions(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant)
    related_principal = _provision_related_client(session, tenant, suffix="coverage")
    policy = session.scalar(select(CommercialRiskPolicy).where(CommercialRiskPolicy.tenant_id == tenant.id))
    assert policy is not None
    policy.account_daily_unique_record_limit = 2
    session.commit()

    first_service = CommercialUsageService(session, contract.principal)
    first = first_service.reserve(
        ReserveCommand("entity.search", "account-cover-first", {"q": "EGFR", "limit": 1}, 1, "5", "account-1")
    ).reservation
    first_service.settle(SettleCommand(first.id, 1, {"items": [{"id": "entity-egfr"}]}, {}, "account-settle-1"))

    with pytest.raises(CommercialAccessDenied, match="Customer-level daily unique-record coverage"):
        CommercialUsageService(session, related_principal).reserve(
            ReserveCommand(
                "entity.search",
                "account-cover-next1",
                {"q": "kinase", "limit": 2},
                2,
                "5",
                "account-2",
            )
        )

    denied = session.scalar(
        select(CommercialPolicyEvent).where(
            CommercialPolicyEvent.reason_code == "account_daily_unique_record_limit_exceeded"
        )
    )
    assert denied is not None
    assert denied.existing_unique_records == 1
    assert denied.projected_unique_records == 3


def test_commercial_admin_publishes_immutable_plan_and_provisions_idempotently(
    session: Session,
    tenant: Tenant,
) -> None:
    definition_path = Path(__file__).parents[1] / "deploy" / "commercial" / "rate-card.schema-example.json"
    definition = RateCardDefinition.model_validate_json(definition_path.read_text(encoding="utf-8"))
    admin = CommercialAdminService(session, tenant, actor_id="CHG-TEST-1")

    card = admin.publish_rate_card(definition)
    assert admin.publish_rate_card(definition).id == card.id
    changed = definition.model_copy(update={"currency": "USD"})
    with pytest.raises(CommercialAdminConflict):
        admin.publish_rate_card(changed)

    command = ProvisionClientCommand(
        client_key="production-agent",
        oauth_client_id="client-123",
        display_name="Production Agent",
        actor_type="agent",
        subject_id="subject-123",
        account_key="customer-main",
        account_name="Customer Main",
        subscription_key="customer-2026",
        rate_card_key=card.rate_card_key,
        rate_card_revision=card.revision,
        created_by="CHG-TEST-1",
        export_field_policy=default_export_field_policy(policy_version="test-v1"),
    )
    subscription = admin.provision_client(command)
    assert admin.provision_client(command).id == subscription.id
    revised_items = [
        item.model_copy(update={"max_result_rows": 125}) if item.billing_class == "provenance.read" else item
        for item in definition.items
    ]
    next_revision = definition.model_copy(update={"revision": definition.revision + 1, "items": revised_items})
    revised_card = admin.publish_rate_card(next_revision)
    migration = RateCardMigrationCommand(
        subscription_key=subscription.subscription_key,
        rate_card_key=revised_card.rate_card_key,
        rate_card_revision=revised_card.revision,
        reason="approved test rate-card migration",
    )
    previous_row_version = subscription.row_version
    assert admin.migrate_rate_card(migration).id == subscription.id
    assert subscription.rate_card_version_id == revised_card.id
    assert subscription.row_version == previous_row_version + 1
    assert admin.migrate_rate_card(migration).id == subscription.id
    evidence_entitlement = session.scalar(
        select(CommercialEntitlement).where(
            CommercialEntitlement.subscription_id == subscription.id,
            CommercialEntitlement.entitlement_key == "evidence.read",
        )
    )
    assert evidence_entitlement is not None
    assert evidence_entitlement.max_result_rows == 125
    rotated_field_policy = default_export_field_policy(policy_version="test-v2")
    export_policy = admin.set_export_field_policy("customer-main", rotated_field_policy)
    assert export_policy.policy_version == "test-v2"
    assert admin.set_export_field_policy("customer-main", rotated_field_policy).id == export_policy.id
    with pytest.raises(CommercialAdminConflict, match="versions are immutable"):
        admin.set_export_field_policy(
            "customer-main",
            default_export_field_policy(policy_version="test-v2", attribution="Different contract"),
        )
    grant = admin.grant_credit(
        subscription.subscription_key,
        Decimal("1000"),
        external_reference="PO-TEST-1",
        reason="approved test allocation",
    )
    assert (
        admin.grant_credit(
            subscription.subscription_key,
            Decimal("1000"),
            external_reference="PO-TEST-1",
            reason="approved test allocation",
        ).id
        == grant.id
    )
    session.refresh(subscription)
    assert subscription.granted_units == Decimal("1000.00000000")
    assert session.scalar(select(func.count()).select_from(RateCardVersion)) == 2
    assert session.scalar(select(func.count()).select_from(CommercialSubscription)) == 1
    assert session.scalar(select(func.count()).select_from(CommercialLedgerEntry)) == 1
    assert session.scalar(select(func.count()).select_from(AuditEvent)) == 6
    assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 6


def test_rate_card_migration_rejects_active_usage_reservations(session: Session, tenant: Tenant) -> None:
    contract = seed_commercial_contract(session, tenant)
    admin = CommercialAdminService(session, tenant, actor_id="CHG-TEST-2")
    revision_two = RateCardDefinition(
        rate_card_key="test-plan",
        revision=2,
        currency="CNY",
        effective_from=datetime.now(UTC) - timedelta(minutes=1),
        items=[
            {
                "billing_class": "entity.search",
                "entitlement_key": "entities.read",
                "base_units": "1",
                "per_result_units": "0.1",
                "per_kib_units": "0.01",
                "per_compute_unit": "0",
                "max_result_rows": 125,
            }
        ],
    )
    admin.publish_rate_card(revision_two)
    usage = CommercialUsageService(session, contract.principal)
    usage.reserve(
        ReserveCommand(
            "entity.search",
            "rate-card-migration-active",
            {"q": "EGFR", "limit": 1},
            1,
            "5",
            "rate-card-migration-request",
        )
    )

    with pytest.raises(CommercialAdminConflict, match="Active usage reservations"):
        admin.migrate_rate_card(
            RateCardMigrationCommand(
                subscription_key=contract.subscription.subscription_key,
                rate_card_key="test-plan",
                rate_card_revision=2,
                reason="approved migration after request drain",
            )
        )

    session.refresh(contract.subscription)
    assert contract.subscription.rate_card_version_id == contract.rate_card.id


def test_rate_card_migration_inherits_limits_for_new_entitlements(session: Session, tenant: Tenant) -> None:
    contract = seed_commercial_contract(
        session,
        tenant,
        max_page_depth=4,
        daily_unique_record_limit=250,
        max_response_bytes=64_000,
    )
    existing = session.scalar(
        select(CommercialEntitlement).where(
            CommercialEntitlement.subscription_id == contract.subscription.id,
            CommercialEntitlement.entitlement_key == "entities.read",
        )
    )
    assert existing is not None
    existing.daily_unit_limit = Decimal("200")
    existing.data_domains = ["publications"]
    existing.constraints_json = {"licensed": True}
    session.commit()
    admin = CommercialAdminService(session, tenant, actor_id="CHG-TEST-3")
    admin.publish_rate_card(
        RateCardDefinition(
            rate_card_key="test-plan",
            revision=2,
            currency="CNY",
            effective_from=datetime.now(UTC) - timedelta(minutes=1),
            items=[
                {
                    "billing_class": "entity.search",
                    "entitlement_key": "entities.read",
                    "base_units": "1",
                    "per_result_units": "0.1",
                    "per_kib_units": "0.01",
                    "per_compute_unit": "0",
                    "max_result_rows": 125,
                },
                {
                    "billing_class": "provenance.read",
                    "entitlement_key": "evidence.read",
                    "base_units": "1",
                    "per_result_units": "0.1",
                    "per_kib_units": "0.01",
                    "per_compute_unit": "0",
                    "max_result_rows": 75,
                },
            ],
        )
    )

    admin.migrate_rate_card(
        RateCardMigrationCommand(
            subscription_key=contract.subscription.subscription_key,
            rate_card_key="test-plan",
            rate_card_revision=2,
            reason="approved new evidence entitlement",
        )
    )

    evidence = session.scalar(
        select(CommercialEntitlement).where(
            CommercialEntitlement.subscription_id == contract.subscription.id,
            CommercialEntitlement.entitlement_key == "evidence.read",
        )
    )
    assert evidence is not None
    assert evidence.max_result_rows == 75
    assert evidence.daily_unit_limit == Decimal("200.00000000")
    assert evidence.max_page_depth == 4
    assert evidence.daily_unique_record_limit == 250
    assert evidence.max_response_bytes == 64_000
    assert evidence.data_domains == ["publications"]
    assert evidence.constraints_json == {"licensed": True}
