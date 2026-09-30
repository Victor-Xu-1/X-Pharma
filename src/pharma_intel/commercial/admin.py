from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.commercial.exports import validate_export_field_policy
from pharma_intel.commercial.plans import RateCardDefinition
from pharma_intel.commercial.service import UNIT_QUANTUM, ZERO_UNITS
from pharma_intel.licensing import canonical_policy_sha256
from pharma_intel.models import (
    AgentClient,
    AgentClientSubject,
    AuditEvent,
    BillingAccount,
    CommercialEntitlement,
    CommercialExportPolicy,
    CommercialLedgerEntry,
    CommercialLedgerEventType,
    CommercialRiskPolicy,
    CommercialSubscription,
    CreditGrant,
    DataExportJob,
    OutboxEvent,
    RateCardItem,
    RateCardVersion,
    SubscriptionStatus,
    Tenant,
    UsageReservation,
    UsageReservationState,
    new_uuid,
)


class CommercialAdminConflict(Exception):
    pass


@dataclass(frozen=True)
class ProvisionClientCommand:
    client_key: str
    oauth_client_id: str
    display_name: str
    actor_type: str
    subject_id: str
    account_key: str
    account_name: str
    subscription_key: str
    rate_card_key: str
    rate_card_revision: int
    created_by: str
    export_field_policy: dict[str, Any]
    max_page_depth: int = 10
    daily_unique_record_limit: int | None = 5000
    max_response_bytes: int = 2_000_000


@dataclass(frozen=True)
class RateCardMigrationCommand:
    subscription_key: str
    rate_card_key: str
    rate_card_revision: int
    reason: str


class CommercialAdminService:
    def __init__(self, session: Session, tenant: Tenant, *, actor_id: str) -> None:
        self.session = session
        self.tenant = tenant
        self.actor_id = actor_id

    def publish_rate_card(self, definition: RateCardDefinition) -> RateCardVersion:
        existing = self.session.scalar(
            select(RateCardVersion).where(
                RateCardVersion.tenant_id == self.tenant.id,
                RateCardVersion.rate_card_key == definition.rate_card_key,
                RateCardVersion.revision == definition.revision,
            )
        )
        if existing is not None:
            if existing.content_sha256 != definition.content_sha256:
                raise CommercialAdminConflict("Rate-card key and revision already exist with different content")
            return existing
        card = RateCardVersion(
            tenant_id=self.tenant.id,
            rate_card_key=definition.rate_card_key,
            revision=definition.revision,
            currency=definition.currency,
            effective_from=definition.effective_from,
            effective_until=definition.effective_until,
            content_sha256=definition.content_sha256,
            created_by=self.actor_id,
        )
        self.session.add(card)
        self.session.flush()
        for item in definition.items:
            self.session.add(
                RateCardItem(
                    tenant_id=self.tenant.id,
                    rate_card_version_id=card.id,
                    billing_class=item.billing_class,
                    entitlement_key=item.entitlement_key,
                    base_units=item.base_units,
                    per_result_units=item.per_result_units,
                    per_kib_units=item.per_kib_units,
                    per_compute_unit=item.per_compute_unit,
                    max_result_rows=item.max_result_rows,
                )
            )
        self._audit("commercial.rate_card.publish", "rate_card_version", card.id, definition.content_sha256)
        self._outbox(card.id, "commercial.rate_card_published.v1", {"content_sha256": definition.content_sha256})
        self.session.commit()
        return card

    def provision_client(self, command: ProvisionClientCommand) -> CommercialSubscription:
        if command.actor_type not in {"agent", "api_key"}:
            raise ValueError("actor_type must be agent or api_key")
        if command.max_page_depth <= 0:
            raise ValueError("max_page_depth must be positive")
        if command.daily_unique_record_limit is not None and command.daily_unique_record_limit <= 0:
            raise ValueError("daily_unique_record_limit must be positive when configured")
        if command.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        requested_export_policy = validate_export_field_policy(command.export_field_policy).document()
        card = self.session.scalar(
            select(RateCardVersion).where(
                RateCardVersion.tenant_id == self.tenant.id,
                RateCardVersion.rate_card_key == command.rate_card_key,
                RateCardVersion.revision == command.rate_card_revision,
            )
        )
        if card is None:
            raise ValueError("Requested rate-card version does not exist")
        changed = False
        client = self.session.scalar(
            select(AgentClient).where(
                AgentClient.tenant_id == self.tenant.id,
                AgentClient.client_key == command.client_key,
            )
        )
        if client is None:
            client = AgentClient(
                tenant_id=self.tenant.id,
                client_key=command.client_key,
                oauth_client_id=command.oauth_client_id,
                display_name=command.display_name,
            )
            self.session.add(client)
            self.session.flush()
            changed = True
        elif client.oauth_client_id != command.oauth_client_id:
            raise CommercialAdminConflict("Client key is already bound to a different OAuth client")
        subject = self.session.scalar(
            select(AgentClientSubject).where(
                AgentClientSubject.tenant_id == self.tenant.id,
                AgentClientSubject.agent_client_id == client.id,
                AgentClientSubject.actor_type == command.actor_type,
                AgentClientSubject.subject_id == command.subject_id,
            )
        )
        if subject is None:
            self.session.add(
                AgentClientSubject(
                    tenant_id=self.tenant.id,
                    agent_client_id=client.id,
                    actor_type=command.actor_type,
                    subject_id=command.subject_id,
                )
            )
            changed = True
        account = self.session.scalar(
            select(BillingAccount).where(
                BillingAccount.tenant_id == self.tenant.id,
                BillingAccount.account_key == command.account_key,
            )
        )
        if account is None:
            account = BillingAccount(
                tenant_id=self.tenant.id,
                account_key=command.account_key,
                display_name=command.account_name,
                currency=card.currency,
            )
            self.session.add(account)
            self.session.flush()
            changed = True
        elif account.currency != card.currency:
            raise CommercialAdminConflict("Billing account and rate card currencies do not match")
        risk_policy = self.session.scalar(
            select(CommercialRiskPolicy).where(
                CommercialRiskPolicy.tenant_id == self.tenant.id,
                CommercialRiskPolicy.billing_account_id == account.id,
            )
        )
        if risk_policy is None:
            self.session.add(
                CommercialRiskPolicy(
                    tenant_id=self.tenant.id,
                    billing_account_id=account.id,
                )
            )
            changed = True
        export_policy = self.session.scalar(
            select(CommercialExportPolicy).where(
                CommercialExportPolicy.tenant_id == self.tenant.id,
                CommercialExportPolicy.billing_account_id == account.id,
            )
        )
        if export_policy is None:
            self.session.add(
                CommercialExportPolicy(
                    tenant_id=self.tenant.id,
                    billing_account_id=account.id,
                    allowed_datasets=sorted(requested_export_policy["datasets"]),
                    field_policy=requested_export_policy,
                )
            )
            changed = True
        elif validate_export_field_policy(export_policy.field_policy).document() != requested_export_policy:
            raise CommercialAdminConflict("Billing account already has a different export field policy")
        subscription = self.session.scalar(
            select(CommercialSubscription).where(
                CommercialSubscription.tenant_id == self.tenant.id,
                CommercialSubscription.agent_client_id == client.id,
            )
        )
        if subscription is None:
            now = datetime.now(UTC)
            subscription = CommercialSubscription(
                tenant_id=self.tenant.id,
                subscription_key=command.subscription_key,
                billing_account_id=account.id,
                agent_client_id=client.id,
                rate_card_version_id=card.id,
                status=SubscriptionStatus.ACTIVE,
                starts_at=now,
                granted_units=ZERO_UNITS,
                consumed_units=ZERO_UNITS,
                reserved_units=ZERO_UNITS,
            )
            self.session.add(subscription)
            self.session.flush()
            maxima: dict[str, int] = {}
            for item in self.session.scalars(
                select(RateCardItem).where(RateCardItem.rate_card_version_id == card.id)
            ).all():
                maxima[item.entitlement_key] = max(maxima.get(item.entitlement_key, 0), item.max_result_rows)
            for entitlement_key, max_rows in maxima.items():
                self.session.add(
                    CommercialEntitlement(
                        tenant_id=self.tenant.id,
                        subscription_id=subscription.id,
                        entitlement_key=entitlement_key,
                        max_result_rows=max_rows,
                        max_page_depth=command.max_page_depth,
                        daily_unique_record_limit=command.daily_unique_record_limit,
                        max_response_bytes=command.max_response_bytes,
                    )
                )
            changed = True
        elif (
            subscription.subscription_key != command.subscription_key
            or subscription.billing_account_id != account.id
            or subscription.rate_card_version_id != card.id
        ):
            raise CommercialAdminConflict("Agent client already has a different subscription contract")
        else:
            entitlements = self.session.scalars(
                select(CommercialEntitlement).where(CommercialEntitlement.subscription_id == subscription.id)
            ).all()
            if any(
                entitlement.max_page_depth != command.max_page_depth
                or entitlement.daily_unique_record_limit != command.daily_unique_record_limit
                or entitlement.max_response_bytes != command.max_response_bytes
                for entitlement in entitlements
            ):
                raise CommercialAdminConflict("Agent client already has different extraction-control limits")
        if not changed:
            return subscription
        self._audit("commercial.client.provision", "commercial_subscription", subscription.id, command.client_key)
        self._outbox(
            subscription.id,
            "commercial.client_provisioned.v1",
            {"client_key": command.client_key, "rate_card_version_id": card.id},
        )
        self.session.commit()
        return subscription

    def set_export_field_policy(
        self,
        account_key: str,
        field_policy: dict[str, Any],
    ) -> CommercialExportPolicy:
        validated = validate_export_field_policy(field_policy)
        document = validated.document()
        account = self.session.scalar(
            select(BillingAccount).where(
                BillingAccount.tenant_id == self.tenant.id,
                BillingAccount.account_key == account_key,
            )
        )
        if account is None:
            raise ValueError("Billing account does not exist")
        policy = self.session.scalar(
            select(CommercialExportPolicy)
            .where(
                CommercialExportPolicy.tenant_id == self.tenant.id,
                CommercialExportPolicy.billing_account_id == account.id,
            )
            .with_for_update()
        )
        if policy is None:
            raise ValueError("Billing account export policy does not exist")
        current_policy = validate_export_field_policy(policy.field_policy)
        if current_policy.document() == document:
            return policy
        if current_policy.policy_version == validated.policy_version:
            raise CommercialAdminConflict("Export field policy versions are immutable")
        reused_job_id = self.session.scalar(
            select(DataExportJob.id)
            .where(
                DataExportJob.tenant_id == self.tenant.id,
                DataExportJob.billing_account_id == account.id,
                DataExportJob.license_policy_version == validated.policy_version,
            )
            .limit(1)
        )
        if reused_job_id is not None:
            raise CommercialAdminConflict("Export field policy versions used by export jobs cannot be reused")
        policy.field_policy = document
        policy.policy_version = validated.policy_version
        policy_sha256 = canonical_policy_sha256(document)
        self._audit(
            "commercial.export_field_policy.update",
            "commercial_export_policy",
            policy.id,
            policy_sha256,
        )
        self._outbox(
            policy.id,
            "commercial.export_field_policy_updated.v1",
            {
                "account_key": account_key,
                "policy_version": validated.policy_version,
                "policy_sha256": policy_sha256,
            },
        )
        self.session.commit()
        return policy

    def migrate_rate_card(self, command: RateCardMigrationCommand) -> CommercialSubscription:
        reason = command.reason.strip()
        if len(reason) < 8:
            raise ValueError("Rate-card migration reason must contain at least 8 characters")
        subscription = self.session.scalar(
            select(CommercialSubscription)
            .where(
                CommercialSubscription.tenant_id == self.tenant.id,
                CommercialSubscription.subscription_key == command.subscription_key,
            )
            .with_for_update()
        )
        if subscription is None:
            raise ValueError("Commercial subscription does not exist")
        card = self.session.scalar(
            select(RateCardVersion).where(
                RateCardVersion.tenant_id == self.tenant.id,
                RateCardVersion.rate_card_key == command.rate_card_key,
                RateCardVersion.revision == command.rate_card_revision,
            )
        )
        if card is None:
            raise ValueError("Requested rate-card version does not exist")
        if subscription.rate_card_version_id == card.id:
            return subscription
        now = datetime.now(UTC)
        active_card = self.session.scalar(
            select(RateCardVersion.id).where(
                RateCardVersion.id == card.id,
                RateCardVersion.effective_from <= now,
                RateCardVersion.effective_until.is_(None) | (RateCardVersion.effective_until > now),
            )
        )
        if active_card is None:
            raise CommercialAdminConflict("Requested rate-card version is not currently effective")
        account = self.session.get(BillingAccount, subscription.billing_account_id)
        if account is None or account.tenant_id != self.tenant.id:
            raise CommercialAdminConflict("Subscription billing account is invalid")
        if account.currency != card.currency:
            raise CommercialAdminConflict("Billing account and rate card currencies do not match")
        active_reservation_id = self.session.scalar(
            select(UsageReservation.id)
            .where(
                UsageReservation.tenant_id == self.tenant.id,
                UsageReservation.subscription_id == subscription.id,
                UsageReservation.state == UsageReservationState.RESERVED,
            )
            .limit(1)
        )
        if active_reservation_id is not None:
            raise CommercialAdminConflict("Active usage reservations must settle or expire before migration")
        items = self.session.scalars(
            select(RateCardItem).where(
                RateCardItem.tenant_id == self.tenant.id,
                RateCardItem.rate_card_version_id == card.id,
            )
        ).all()
        maxima: dict[str, int] = {}
        for item in items:
            maxima[item.entitlement_key] = max(maxima.get(item.entitlement_key, 0), item.max_result_rows)
        if not maxima:
            raise CommercialAdminConflict("Requested rate-card version has no billable items")
        entitlements = self.session.scalars(
            select(CommercialEntitlement)
            .where(
                CommercialEntitlement.tenant_id == self.tenant.id,
                CommercialEntitlement.subscription_id == subscription.id,
            )
            .with_for_update()
        ).all()
        if not entitlements:
            raise CommercialAdminConflict("Subscription has no extraction-control entitlements")
        by_key = {entitlement.entitlement_key: entitlement for entitlement in entitlements}
        new_keys = sorted(set(maxima) - set(by_key))
        if new_keys:
            domain_policies = {tuple(sorted(entitlement.data_domains)) for entitlement in entitlements}
            constraint_policies = {
                canonical_policy_sha256(entitlement.constraints_json): entitlement.constraints_json
                for entitlement in entitlements
            }
            if len(domain_policies) != 1 or len(constraint_policies) != 1:
                raise CommercialAdminConflict(
                    "New entitlements require an explicit policy because existing domain controls differ"
                )
            daily_units = [
                entitlement.daily_unit_limit for entitlement in entitlements if entitlement.daily_unit_limit is not None
            ]
            daily_records = [
                entitlement.daily_unique_record_limit
                for entitlement in entitlements
                if entitlement.daily_unique_record_limit is not None
            ]
            template = min(entitlements, key=lambda entitlement: entitlement.max_response_bytes)
            for entitlement_key in new_keys:
                self.session.add(
                    CommercialEntitlement(
                        tenant_id=self.tenant.id,
                        subscription_id=subscription.id,
                        entitlement_key=entitlement_key,
                        max_result_rows=maxima[entitlement_key],
                        daily_unit_limit=min(daily_units) if daily_units else None,
                        max_page_depth=min(entitlement.max_page_depth for entitlement in entitlements),
                        daily_unique_record_limit=min(daily_records) if daily_records else None,
                        max_response_bytes=template.max_response_bytes,
                        data_domains=list(template.data_domains),
                        constraints_json=dict(template.constraints_json),
                    )
                )
        for entitlement in entitlements:
            max_rows = maxima.get(entitlement.entitlement_key)
            entitlement.enabled = max_rows is not None
            if max_rows is not None:
                entitlement.max_result_rows = max_rows
        previous_rate_card_id = subscription.rate_card_version_id
        subscription.rate_card_version_id = card.id
        subscription.row_version += 1
        self._audit(
            "commercial.subscription.rate_card_migrate",
            "commercial_subscription",
            subscription.id,
            reason,
        )
        self._outbox(
            subscription.id,
            "commercial.subscription_rate_card_migrated.v1",
            {
                "previous_rate_card_version_id": previous_rate_card_id,
                "rate_card_version_id": card.id,
                "reason": reason,
            },
        )
        self.session.commit()
        return subscription

    def grant_credit(
        self,
        subscription_key: str,
        units: Decimal,
        *,
        external_reference: str,
        reason: str,
    ) -> CreditGrant:
        normalized_units = units.quantize(UNIT_QUANTUM)
        if normalized_units <= ZERO_UNITS:
            raise ValueError("Credit grant must be positive")
        subscription = self.session.scalar(
            select(CommercialSubscription)
            .where(
                CommercialSubscription.tenant_id == self.tenant.id,
                CommercialSubscription.subscription_key == subscription_key,
            )
            .with_for_update()
        )
        if subscription is None:
            raise ValueError("Commercial subscription does not exist")
        existing = self.session.scalar(
            select(CreditGrant).where(
                CreditGrant.tenant_id == self.tenant.id,
                CreditGrant.external_reference == external_reference,
            )
        )
        if existing is not None:
            if existing.subscription_id != subscription.id or existing.granted_units != normalized_units:
                raise CommercialAdminConflict("Credit reference already exists with different values")
            return existing
        grant = CreditGrant(
            tenant_id=self.tenant.id,
            subscription_id=subscription.id,
            granted_units=normalized_units,
            granted_at=datetime.now(UTC),
            external_reference=external_reference,
            reason=reason,
            created_by=self.actor_id,
        )
        self.session.add(grant)
        self.session.flush()
        subscription.granted_units = (subscription.granted_units + normalized_units).quantize(UNIT_QUANTUM)
        subscription.row_version += 1
        request_id = new_uuid()
        self.session.add(
            CommercialLedgerEntry(
                tenant_id=self.tenant.id,
                subscription_id=subscription.id,
                event_key=f"credit:{grant.id}",
                event_type=CommercialLedgerEventType.CREDIT_GRANTED,
                granted_delta=normalized_units,
                reserved_delta=ZERO_UNITS,
                consumed_delta=ZERO_UNITS,
                request_id=request_id,
                details={"external_reference": external_reference, "reason": reason},
            )
        )
        self._audit("commercial.credit.grant", "credit_grant", grant.id, external_reference, request_id=request_id)
        self._outbox(
            grant.id,
            "commercial.credit_granted.v1",
            {"subscription_id": subscription.id, "granted_units": format(normalized_units, "f")},
        )
        self.session.commit()
        return grant

    def _audit(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        reference: str,
        *,
        request_id: str | None = None,
    ) -> None:
        self.session.add(
            AuditEvent(
                tenant_id=self.tenant.id,
                actor_type="operator",
                actor_id=self.actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="success",
                request_id=request_id or new_uuid(),
                details={"reference": reference},
            )
        )

    def _outbox(self, aggregate_id: str, event_type: str, payload: dict[str, object]) -> None:
        self.session.add(
            OutboxEvent(
                tenant_id=self.tenant.id,
                aggregate_type="commercial_configuration",
                aggregate_id=aggregate_id,
                event_type=event_type,
                payload=payload,
            )
        )
