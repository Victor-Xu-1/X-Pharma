from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.models import (
    AgentClient,
    BillingAccount,
    CommercialCoverageRecord,
    CommercialEntitlement,
    CommercialPolicyEvent,
    CommercialRiskCase,
    CommercialSubscription,
    RateCardVersion,
    UsageEvent,
    UsageReservation,
    UsageReservationState,
)


def commercial_overview(session: Session, tenant_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    timestamp = _timestamp(now)
    period_start = datetime(timestamp.year, timestamp.month, timestamp.day, tzinfo=UTC)
    open_risk_count = int(
        session.scalar(
            select(func.count())
            .select_from(CommercialPolicyEvent)
            .outerjoin(CommercialRiskCase, CommercialRiskCase.policy_event_id == CommercialPolicyEvent.id)
            .where(
                CommercialPolicyEvent.tenant_id == tenant_id,
                CommercialPolicyEvent.decision == "deny",
                CommercialRiskCase.id.is_(None),
            )
        )
        or 0
    )
    subscriptions = list(
        session.scalars(
            select(CommercialSubscription)
            .where(CommercialSubscription.tenant_id == tenant_id)
            .order_by(CommercialSubscription.subscription_key)
        ).all()
    )
    if not subscriptions:
        return {
            "as_of": timestamp,
            "period_start": period_start,
            "open_risk_count": open_risk_count,
            "subscriptions": [],
        }

    subscription_ids = [item.id for item in subscriptions]
    client_ids = [item.agent_client_id for item in subscriptions]
    account_ids = [item.billing_account_id for item in subscriptions]
    rate_card_ids = [item.rate_card_version_id for item in subscriptions]
    clients = {
        item.id: item
        for item in session.scalars(
            select(AgentClient).where(AgentClient.tenant_id == tenant_id, AgentClient.id.in_(client_ids))
        ).all()
    }
    accounts = {
        item.id: item
        for item in session.scalars(
            select(BillingAccount).where(BillingAccount.tenant_id == tenant_id, BillingAccount.id.in_(account_ids))
        ).all()
    }
    rate_cards = {
        item.id: item
        for item in session.scalars(
            select(RateCardVersion).where(RateCardVersion.tenant_id == tenant_id, RateCardVersion.id.in_(rate_card_ids))
        ).all()
    }
    entitlements: dict[str, list[CommercialEntitlement]] = {item.id: [] for item in subscriptions}
    for item in session.scalars(
        select(CommercialEntitlement)
        .where(
            CommercialEntitlement.tenant_id == tenant_id,
            CommercialEntitlement.subscription_id.in_(subscription_ids),
        )
        .order_by(CommercialEntitlement.entitlement_key)
    ).all():
        entitlements[item.subscription_id].append(item)

    active_reservations = _count_by_subscription(
        session,
        select(UsageReservation.subscription_id, func.count())
        .where(
            UsageReservation.tenant_id == tenant_id,
            UsageReservation.subscription_id.in_(subscription_ids),
            UsageReservation.state == UsageReservationState.RESERVED,
            UsageReservation.lease_expires_at > timestamp,
        )
        .group_by(UsageReservation.subscription_id),
    )
    daily_coverage = _count_by_subscription(
        session,
        select(CommercialCoverageRecord.subscription_id, func.count())
        .where(
            CommercialCoverageRecord.tenant_id == tenant_id,
            CommercialCoverageRecord.subscription_id.in_(subscription_ids),
            CommercialCoverageRecord.period_start == period_start,
        )
        .group_by(CommercialCoverageRecord.subscription_id),
    )
    usage = {
        row.subscription_id: {
            "settlement_count": int(row.settlement_count),
            "result_count": int(row.result_count or 0),
            "unique_record_count": int(row.unique_record_count or 0),
            "new_unique_record_count": int(row.new_unique_record_count or 0),
            "response_bytes": int(row.response_bytes or 0),
        }
        for row in session.execute(
            select(
                UsageEvent.subscription_id.label("subscription_id"),
                func.count().label("settlement_count"),
                func.sum(UsageEvent.result_count).label("result_count"),
                func.sum(UsageEvent.unique_record_count).label("unique_record_count"),
                func.sum(UsageEvent.new_unique_record_count).label("new_unique_record_count"),
                func.sum(UsageEvent.response_bytes).label("response_bytes"),
            )
            .where(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.subscription_id.in_(subscription_ids),
                UsageEvent.occurred_at >= period_start,
            )
            .group_by(UsageEvent.subscription_id)
        )
    }

    rows: list[dict[str, Any]] = []
    for subscription in subscriptions:
        client = clients.get(subscription.agent_client_id)
        account = accounts.get(subscription.billing_account_id)
        rate_card = rate_cards.get(subscription.rate_card_version_id)
        if client is None or account is None or rate_card is None:
            raise RuntimeError("Commercial overview references an incomplete contract")
        available = subscription.granted_units - subscription.consumed_units - subscription.reserved_units
        rows.append(
            {
                "subscription_id": subscription.id,
                "subscription_key": subscription.subscription_key,
                "status": subscription.status.value,
                "client_key": client.client_key,
                "client_name": client.display_name,
                "billing_account_key": account.account_key,
                "billing_account_name": account.display_name,
                "rate_card_key": rate_card.rate_card_key,
                "rate_card_revision": rate_card.revision,
                "starts_at": subscription.starts_at,
                "ends_at": subscription.ends_at,
                "granted_units": _decimal(subscription.granted_units),
                "consumed_units": _decimal(subscription.consumed_units),
                "reserved_units": _decimal(subscription.reserved_units),
                "available_units": _decimal(available),
                "active_reservations": active_reservations.get(subscription.id, 0),
                "daily_unique_records": daily_coverage.get(subscription.id, 0),
                "daily_usage": usage.get(
                    subscription.id,
                    {
                        "settlement_count": 0,
                        "result_count": 0,
                        "unique_record_count": 0,
                        "new_unique_record_count": 0,
                        "response_bytes": 0,
                    },
                ),
                "entitlements": [
                    {
                        "key": entitlement.entitlement_key,
                        "max_result_rows": entitlement.max_result_rows,
                        "daily_unit_limit": (
                            _decimal(entitlement.daily_unit_limit) if entitlement.daily_unit_limit is not None else None
                        ),
                        "max_page_depth": entitlement.max_page_depth,
                        "daily_unique_record_limit": entitlement.daily_unique_record_limit,
                        "max_response_bytes": entitlement.max_response_bytes,
                        "data_domains": entitlement.data_domains,
                    }
                    for entitlement in entitlements[subscription.id]
                    if entitlement.enabled
                ],
            }
        )
    return {
        "as_of": timestamp,
        "period_start": period_start,
        "open_risk_count": open_risk_count,
        "subscriptions": rows,
    }


def _count_by_subscription(session: Session, statement: Any) -> dict[str, int]:
    return {str(subscription_id): int(count) for subscription_id, count in session.execute(statement)}


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _timestamp(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(UTC)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)
