from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from pharma_intel.commercial.exports import default_export_field_policy
from pharma_intel.models import (
    AgentClient,
    AgentClientSubject,
    BillingAccount,
    CommercialEntitlement,
    CommercialExportPolicy,
    CommercialLedgerEntry,
    CommercialLedgerEventType,
    CommercialRiskPolicy,
    CommercialSubscription,
    CreditGrant,
    RateCardItem,
    RateCardVersion,
    Tenant,
)
from pharma_intel.security import Principal


@dataclass(frozen=True)
class CommercialContractFixture:
    principal: Principal
    client: AgentClient
    subscription: CommercialSubscription
    rate_card: RateCardVersion
    items: dict[str, RateCardItem]


def seed_commercial_contract(
    session: Session,
    tenant: Tenant,
    *,
    billing_classes: dict[str, tuple[str, int]] | None = None,
    granted_units: Decimal = Decimal("100.00000000"),
    subject_id: str = "agent-subject-1",
    oauth_client_id: str = "oauth-client-1",
    max_page_depth: int = 10,
    daily_unique_record_limit: int | None = 5000,
    max_response_bytes: int = 2_000_000,
    per_compute_units: dict[str, Decimal] | None = None,
) -> CommercialContractFixture:
    definitions = billing_classes or {"entity.search": ("entities.read", 100)}
    compute_prices = per_compute_units or {}
    now = datetime.now(UTC)
    client = AgentClient(
        tenant_id=tenant.id,
        client_key="test-agent",
        oauth_client_id=oauth_client_id,
        display_name="Test Agent",
    )
    session.add(client)
    session.flush()
    session.add(
        AgentClientSubject(
            tenant_id=tenant.id,
            agent_client_id=client.id,
            actor_type="api_key",
            subject_id=subject_id,
        )
    )
    account = BillingAccount(
        tenant_id=tenant.id,
        account_key="test-account",
        display_name="Test Billing Account",
        currency="CNY",
    )
    card = RateCardVersion(
        tenant_id=tenant.id,
        rate_card_key="test-plan",
        revision=1,
        currency="CNY",
        effective_from=now - timedelta(days=1),
        content_sha256="a" * 64,
        created_by="test-suite",
    )
    session.add_all([account, card])
    session.flush()
    session.add(
        CommercialRiskPolicy(
            tenant_id=tenant.id,
            billing_account_id=account.id,
        )
    )
    session.add(
        CommercialExportPolicy(
            tenant_id=tenant.id,
            billing_account_id=account.id,
            field_policy=default_export_field_policy(policy_version="test-v1"),
        )
    )
    items: dict[str, RateCardItem] = {}
    for billing_class, (entitlement_key, max_rows) in definitions.items():
        item = RateCardItem(
            tenant_id=tenant.id,
            rate_card_version_id=card.id,
            billing_class=billing_class,
            entitlement_key=entitlement_key,
            base_units=Decimal("1.00000000"),
            per_result_units=Decimal("0.10000000"),
            per_kib_units=Decimal("0.01000000"),
            per_compute_unit=compute_prices.get(billing_class, Decimal("0.00000000")),
            max_result_rows=max_rows,
        )
        items[billing_class] = item
        session.add(item)
    subscription = CommercialSubscription(
        tenant_id=tenant.id,
        subscription_key="test-subscription",
        billing_account_id=account.id,
        agent_client_id=client.id,
        rate_card_version_id=card.id,
        starts_at=now - timedelta(hours=1),
        granted_units=granted_units,
        consumed_units=Decimal("0.00000000"),
        reserved_units=Decimal("0.00000000"),
    )
    session.add(subscription)
    session.flush()
    entitlement_limits: dict[str, int] = {}
    for entitlement_key, max_rows in definitions.values():
        entitlement_limits[entitlement_key] = max(max_rows, entitlement_limits.get(entitlement_key, 0))
    session.add_all(
        CommercialEntitlement(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            entitlement_key=key,
            max_result_rows=max_rows,
            max_page_depth=max_page_depth,
            daily_unique_record_limit=daily_unique_record_limit,
            max_response_bytes=max_response_bytes,
        )
        for key, max_rows in entitlement_limits.items()
    )
    session.add(
        CreditGrant(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            granted_units=granted_units,
            granted_at=now - timedelta(hours=1),
            external_reference="test-credit-grant",
            reason="test fixture",
            created_by="test-suite",
        )
    )
    session.add(
        CommercialLedgerEntry(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            event_key=f"credit:test-credit-grant:{subscription.id}",
            event_type=CommercialLedgerEventType.CREDIT_GRANTED,
            granted_delta=granted_units,
            reserved_delta=Decimal("0.00000000"),
            consumed_delta=Decimal("0.00000000"),
            request_id="test-credit-grant",
            details={"external_reference": "test-credit-grant"},
        )
    )
    session.commit()
    principal = Principal(
        tenant_id=tenant.id,
        actor_id=subject_id,
        actor_type="api_key",
        scopes=frozenset({"mcp:connect", "entities:read", "data:export"}),
        client_id=oauth_client_id,
    )
    return CommercialContractFixture(principal, client, subscription, card, items)
