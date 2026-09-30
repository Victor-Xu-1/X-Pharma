from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.commercial.cursor import CursorError, SignedCursorCodec, query_fingerprint
from pharma_intel.dossier import DOSSIER_RECORD_COLLECTIONS
from pharma_intel.models import (
    AgentClient,
    AgentClientSubject,
    BillingAccount,
    BillingAccountStatus,
    BillingPeriodStatement,
    CommercialCoverageRecord,
    CommercialEntitlement,
    CommercialLedgerEntry,
    CommercialLedgerEventType,
    CommercialPolicyEvent,
    CommercialRiskPolicy,
    CommercialSubscription,
    OutboxEvent,
    RateCardItem,
    RateCardVersion,
    SubscriptionStatus,
    UsageEvent,
    UsageReservation,
    UsageReservationState,
    UsageSettlement,
)
from pharma_intel.request_correlation import FINGERPRINT_PATTERN
from pharma_intel.security import Principal

UNIT_QUANTUM = Decimal("0.00000001")
ZERO_UNITS = Decimal("0.00000000")
MAX_REQUEST_ARGUMENT_BYTES = 65_536
MAX_USAGE_METRICS_BYTES = 16_384
IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
BILLING_CLASS_PATTERN = re.compile(r"^[a-z][a-z0-9_.:-]{2,159}$")
PARTITION_ARGUMENT_KEYS = frozenset(
    {"after_id", "bucket", "initial", "letter", "partition", "prefix", "range_end", "range_start", "starts_with"}
)
GENERIC_QUERY_ARGUMENT_KEYS = frozenset({"q", "query", "search"})
MAX_RISK_EVENTS_SCANNED = 50_001


class CommercialError(Exception):
    """Base class for safe commercial-control errors."""


class CommercialAccessDenied(CommercialError):
    pass


class CommercialNotConfigured(CommercialError):
    pass


class InsufficientCredits(CommercialError):
    pass


class IdempotencyConflict(CommercialError):
    pass


class ReservationConflict(CommercialError):
    pass


class ReservationExpired(CommercialError):
    pass


class SettlementLimitExceeded(CommercialError):
    pass


class CommercialInvariantViolation(CommercialError):
    pass


@dataclass(frozen=True)
class ReserveCommand:
    billing_class: str
    idempotency_key: str
    request_arguments: dict[str, Any]
    requested_result_limit: int
    max_billable_units: Decimal | str
    request_id: str
    requested_compute_units: Decimal | str = ZERO_UNITS
    network_fingerprint: str | None = None
    correlation_key_id: str = "local-correlation-v1"


@dataclass(frozen=True)
class SettleCommand:
    reservation_id: str
    result_count: int
    result: dict[str, Any] | list[Any]
    metrics: dict[str, Any]
    request_id: str


@dataclass(frozen=True)
class ReservationOutcome:
    reservation: UsageReservation
    replayed: bool
    settlement: UsageSettlement | None = None


@dataclass(frozen=True)
class SettlementOutcome:
    reservation: UsageReservation
    settlement: UsageSettlement
    usage_event: UsageEvent
    replayed: bool


@dataclass(frozen=True)
class PartitionRiskSignal:
    query_shape_sha256: str
    partition_token_sha256: str
    argument_path_sha256: str


@dataclass(frozen=True)
class RiskAssessment:
    details: dict[str, Any]
    denial_code: str | None = None
    denial_message: str | None = None


class CommercialUsageService:
    def __init__(
        self,
        session: Session,
        principal: Principal,
        *,
        reservation_lease_seconds: int = 120,
        max_result_bytes: int = 2_000_000,
        max_billable_units_per_call: Decimal | str = Decimal("1000000"),
        max_active_reservations_per_client: int = 20,
        cursor_codec: SignedCursorCodec | None = None,
    ) -> None:
        if principal.actor_type not in {"agent", "api_key"}:
            raise CommercialAccessDenied("Commercial MCP access requires an Agent principal")
        if not principal.commercial_client_id:
            raise CommercialAccessDenied("Authenticated Agent client identity is missing")
        if max_active_reservations_per_client <= 0:
            raise ValueError("Active reservation limit must be positive")
        self.session = session
        self.principal = principal
        self.reservation_lease_seconds = reservation_lease_seconds
        self.max_result_bytes = max_result_bytes
        self.max_billable_units_per_call = _units(max_billable_units_per_call)
        self.max_active_reservations_per_client = max_active_reservations_per_client
        self.cursor_codec = cursor_codec

    def access_snapshot(self, *, now: datetime | None = None) -> dict[str, Any]:
        timestamp = _timestamp(now)
        client, _ = self._bound_client()
        subscription = self._subscription(client.id, timestamp, lock=False)
        entitlements = self.session.scalars(
            select(CommercialEntitlement)
            .where(
                CommercialEntitlement.tenant_id == self.principal.tenant_id,
                CommercialEntitlement.subscription_id == subscription.id,
                CommercialEntitlement.enabled.is_(True),
            )
            .order_by(CommercialEntitlement.entitlement_key)
        ).all()
        return {
            "client_id": client.client_key,
            "subscription_id": subscription.subscription_key,
            "status": subscription.status.value,
            "available_units": _unit_string(
                subscription.granted_units - subscription.consumed_units - subscription.reserved_units
            ),
            "consumed_units": _unit_string(subscription.consumed_units),
            "reserved_units": _unit_string(subscription.reserved_units),
            "entitlements": [
                {
                    "key": item.entitlement_key,
                    "max_result_rows": item.max_result_rows,
                    "daily_unit_limit": _unit_string(item.daily_unit_limit) if item.daily_unit_limit else None,
                    "max_page_depth": item.max_page_depth,
                    "daily_unique_record_limit": item.daily_unique_record_limit,
                    "max_response_bytes": item.max_response_bytes,
                    "data_domains": item.data_domains,
                }
                for item in entitlements
            ],
            "as_of": timestamp,
        }

    def estimate(
        self,
        billing_class: str,
        requested_result_limit: int,
        requested_compute_units: Decimal | str = ZERO_UNITS,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = _timestamp(now)
        if not BILLING_CLASS_PATTERN.fullmatch(billing_class):
            raise ValueError("Billing class is invalid")
        if requested_result_limit <= 0 or requested_result_limit > 5000:
            raise ValueError("Requested result limit must be between 1 and 5000")
        compute_units = _nonnegative_units(requested_compute_units, field_name="Requested compute units")
        client, _ = self._bound_client()
        subscription = self._subscription(client.id, timestamp, lock=False)
        item = self._rate_item(subscription, billing_class, timestamp)
        entitlement = self._entitlement(subscription.id, item.entitlement_key)
        maximum_rows = min(item.max_result_rows, entitlement.max_result_rows)
        if requested_result_limit > maximum_rows:
            raise CommercialAccessDenied("Requested result limit exceeds the licensed entitlement")
        card = self.session.get(RateCardVersion, subscription.rate_card_version_id)
        if card is None:
            raise CommercialInvariantViolation("Subscription rate card is missing")
        estimated = _quantize(
            item.base_units + item.per_result_units * requested_result_limit + item.per_compute_unit * compute_units
        )
        return {
            "billing_class": billing_class,
            "entitlement_key": item.entitlement_key,
            "requested_result_limit": requested_result_limit,
            "requested_compute_units": _unit_string(compute_units),
            "estimated_units_before_response_bytes": _unit_string(estimated),
            "base_units": _unit_string(item.base_units),
            "per_result_units": _unit_string(item.per_result_units),
            "per_kib_units": _unit_string(item.per_kib_units),
            "per_compute_unit": _unit_string(item.per_compute_unit),
            "maximum_licensed_result_rows": maximum_rows,
            "available_units": _unit_string(
                subscription.granted_units - subscription.consumed_units - subscription.reserved_units
            ),
            "rate_card_key": card.rate_card_key,
            "rate_card_revision": card.revision,
            "currency": card.currency,
            "as_of": timestamp,
        }

    def usage_summary(self, *, now: datetime | None = None) -> dict[str, Any]:
        timestamp = _timestamp(now)
        period_start = datetime(timestamp.year, timestamp.month, 1, tzinfo=UTC)
        client, _ = self._bound_client()
        subscription = self._subscription(client.id, timestamp, lock=False)
        card = self.session.get(RateCardVersion, subscription.rate_card_version_id)
        if card is None:
            raise CommercialInvariantViolation("Subscription rate card is missing")
        settlement_row = self.session.execute(
            select(
                func.count(UsageSettlement.id),
                func.coalesce(func.sum(UsageSettlement.charged_units), ZERO_UNITS),
                func.coalesce(func.sum(UsageEvent.result_count), 0),
                func.coalesce(func.sum(UsageEvent.response_bytes), 0),
            )
            .select_from(UsageSettlement)
            .join(UsageEvent, UsageEvent.id == UsageSettlement.usage_event_id)
            .where(
                UsageSettlement.tenant_id == self.principal.tenant_id,
                UsageSettlement.subscription_id == subscription.id,
                UsageSettlement.created_at >= period_start,
                UsageSettlement.created_at <= timestamp,
            )
        ).one()
        active_reservations = self.session.scalar(
            select(func.count())
            .select_from(UsageReservation)
            .where(
                UsageReservation.tenant_id == self.principal.tenant_id,
                UsageReservation.subscription_id == subscription.id,
                UsageReservation.state == UsageReservationState.RESERVED,
                UsageReservation.lease_expires_at > timestamp,
            )
        )
        latest_statement = self.session.scalar(
            select(BillingPeriodStatement)
            .where(
                BillingPeriodStatement.tenant_id == self.principal.tenant_id,
                BillingPeriodStatement.subscription_id == subscription.id,
            )
            .order_by(BillingPeriodStatement.period_end.desc(), BillingPeriodStatement.revision.desc())
            .limit(1)
        )
        return {
            "client_id": client.client_key,
            "subscription_id": subscription.subscription_key,
            "rate_card_key": card.rate_card_key,
            "rate_card_revision": card.revision,
            "currency": card.currency,
            "period_start": period_start,
            "as_of": timestamp,
            "settlement_count": int(settlement_row[0]),
            "charged_units": _unit_string(settlement_row[1]),
            "result_count": int(settlement_row[2]),
            "response_bytes": int(settlement_row[3]),
            "active_reservations": int(active_reservations or 0),
            "granted_units": _unit_string(subscription.granted_units),
            "consumed_units": _unit_string(subscription.consumed_units),
            "reserved_units": _unit_string(subscription.reserved_units),
            "available_units": _unit_string(
                subscription.granted_units - subscription.consumed_units - subscription.reserved_units
            ),
            "latest_statement_id": latest_statement.id if latest_statement else None,
            "latest_statement_period_end": latest_statement.period_end if latest_statement else None,
        }

    def reserve(self, command: ReserveCommand, *, now: datetime | None = None) -> ReservationOutcome:
        timestamp = _timestamp(now)
        _validate_reserve_command(command)
        if (
            self.principal.credential_fingerprint is not None
            and FINGERPRINT_PATTERN.fullmatch(self.principal.credential_fingerprint) is None
        ):
            raise ValueError("Credential fingerprint is invalid")
        client_max_units = _units(command.max_billable_units)
        requested_compute_units = _nonnegative_units(
            command.requested_compute_units,
            field_name="Requested compute units",
        )
        if client_max_units > self.max_billable_units_per_call:
            raise SettlementLimitExceeded("Maximum billable units exceed the server-side per-call limit")
        request_sha256 = _sha256(
            {
                "billing_class": command.billing_class,
                "request_arguments": command.request_arguments,
                "requested_result_limit": command.requested_result_limit,
                "max_billable_units": _unit_string(client_max_units),
                "requested_compute_units": _unit_string(requested_compute_units),
                "network_fingerprint": command.network_fingerprint,
                "credential_fingerprint": self.principal.credential_fingerprint,
                "correlation_key_id": command.correlation_key_id,
            }
        )
        query_sha256 = query_fingerprint(
            command.billing_class,
            command.request_arguments,
            command.requested_result_limit,
        )
        client, _ = self._bound_client()
        existing = self._existing_reservation(client.id, command.idempotency_key)
        if existing is not None:
            return self._replay_reservation(existing, request_sha256, timestamp)

        subscription = self._subscription(client.id, timestamp, lock=True)
        existing = self._existing_reservation(client.id, command.idempotency_key)
        if existing is not None:
            return self._replay_reservation(existing, request_sha256, timestamp)

        risk_policy = self._risk_policy(subscription.billing_account_id, lock=True)
        self._expire_stale_locked(subscription, timestamp, command.request_id)
        item = self._rate_item(subscription, command.billing_class, timestamp)
        entitlement = self._entitlement(subscription.id, item.entitlement_key)
        allowed_rows = min(item.max_result_rows, entitlement.max_result_rows)
        if command.requested_result_limit > allowed_rows:
            raise CommercialAccessDenied("Requested result limit exceeds the licensed entitlement")

        cursor_chain_id, page_offset, page_depth = self._resolve_pagination(command, query_sha256)
        period_start = _start_of_day(timestamp)
        existing_coverage = self._coverage_count(subscription.id, entitlement.entitlement_key, period_start)
        account_existing_coverage = self._account_coverage_count(
            subscription.billing_account_id,
            entitlement.entitlement_key,
            period_start,
        )
        account_projected_coverage = self._projected_account_coverage(
            subscription.billing_account_id,
            entitlement.entitlement_key,
            account_existing_coverage,
            command.requested_result_limit,
            timestamp,
        )
        risk_assessment = self._assess_account_risk(
            subscription,
            risk_policy,
            client.id,
            entitlement.entitlement_key,
            command.billing_class,
            command.request_arguments,
            command.network_fingerprint,
            command.correlation_key_id,
            timestamp,
        )
        if risk_policy.enabled and account_projected_coverage > risk_policy.account_daily_unique_record_limit:
            self._append_policy_event(
                subscription,
                client.id,
                entitlement.entitlement_key,
                phase="reserve",
                decision="deny",
                reason_code="account_daily_unique_record_limit_exceeded",
                query_sha256=query_sha256,
                cursor_chain_id=cursor_chain_id,
                page_depth=page_depth,
                requested_records=command.requested_result_limit,
                existing_unique_records=account_existing_coverage,
                projected_unique_records=account_projected_coverage,
                request_id=command.request_id,
                details=risk_assessment.details,
            )
            self.session.commit()
            raise CommercialAccessDenied("Customer-level daily unique-record coverage would be exceeded")
        if risk_assessment.denial_code is not None:
            self._append_policy_event(
                subscription,
                client.id,
                entitlement.entitlement_key,
                phase="reserve",
                decision="deny",
                reason_code=risk_assessment.denial_code,
                query_sha256=query_sha256,
                cursor_chain_id=cursor_chain_id,
                page_depth=page_depth,
                requested_records=command.requested_result_limit,
                existing_unique_records=account_existing_coverage,
                projected_unique_records=account_projected_coverage,
                request_id=command.request_id,
                details=risk_assessment.details,
            )
            self.session.commit()
            raise CommercialAccessDenied(risk_assessment.denial_message or "Commercial risk policy denied the request")
        if page_depth > entitlement.max_page_depth:
            self._append_policy_event(
                subscription,
                client.id,
                entitlement.entitlement_key,
                phase="reserve",
                decision="deny",
                reason_code="page_depth_exceeded",
                query_sha256=query_sha256,
                cursor_chain_id=cursor_chain_id,
                page_depth=page_depth,
                requested_records=command.requested_result_limit,
                existing_unique_records=account_existing_coverage,
                projected_unique_records=account_existing_coverage,
                request_id=command.request_id,
                details=risk_assessment.details,
            )
            self.session.commit()
            raise CommercialAccessDenied("Licensed pagination depth would be exceeded")
        active_reservations = self._active_reservation_count(subscription.id, client.id, timestamp)
        if active_reservations >= self.max_active_reservations_per_client:
            self._append_policy_event(
                subscription,
                client.id,
                entitlement.entitlement_key,
                phase="reserve",
                decision="deny",
                reason_code="active_reservation_limit_exceeded",
                query_sha256=query_sha256,
                cursor_chain_id=cursor_chain_id,
                page_depth=page_depth,
                requested_records=command.requested_result_limit,
                existing_unique_records=account_existing_coverage,
                projected_unique_records=account_existing_coverage,
                request_id=command.request_id,
                details={**risk_assessment.details, "active_reservations": active_reservations},
            )
            self.session.commit()
            raise CommercialAccessDenied("Concurrent commercial request limit would be exceeded")
        projected_coverage = self._projected_coverage(
            subscription.id,
            entitlement,
            existing_coverage,
            command.requested_result_limit,
            timestamp,
        )
        if (
            entitlement.daily_unique_record_limit is not None
            and projected_coverage > entitlement.daily_unique_record_limit
        ):
            self._append_policy_event(
                subscription,
                client.id,
                entitlement.entitlement_key,
                phase="reserve",
                decision="deny",
                reason_code="daily_unique_record_limit_exceeded",
                query_sha256=query_sha256,
                cursor_chain_id=cursor_chain_id,
                page_depth=page_depth,
                requested_records=command.requested_result_limit,
                existing_unique_records=account_existing_coverage,
                projected_unique_records=account_projected_coverage,
                request_id=command.request_id,
                details=risk_assessment.details,
            )
            self.session.commit()
            raise CommercialAccessDenied("Daily licensed unique-record coverage would be exceeded")

        estimated_units = _quantize(
            item.base_units
            + item.per_result_units * command.requested_result_limit
            + item.per_compute_unit * requested_compute_units
        )
        if client_max_units < estimated_units:
            raise SettlementLimitExceeded("Maximum billable units are below the request estimate")
        self._enforce_daily_limit(subscription.id, entitlement, client_max_units, timestamp)
        available_units = _quantize(
            subscription.granted_units - subscription.consumed_units - subscription.reserved_units
        )
        if client_max_units > available_units:
            raise InsufficientCredits("Insufficient available MCP credits")

        reservation = UsageReservation(
            tenant_id=self.principal.tenant_id,
            subscription_id=subscription.id,
            agent_client_id=client.id,
            rate_card_item_id=item.id,
            actor_type=self.principal.actor_type,
            subject_id=self.principal.actor_id,
            network_fingerprint=command.network_fingerprint,
            credential_fingerprint=self.principal.credential_fingerprint,
            correlation_key_id=command.correlation_key_id,
            billing_class=command.billing_class,
            idempotency_key=command.idempotency_key,
            request_sha256=request_sha256,
            query_sha256=query_sha256,
            cursor_chain_id=cursor_chain_id,
            page_offset=page_offset,
            page_depth=page_depth,
            requested_result_limit=command.requested_result_limit,
            requested_compute_units=requested_compute_units,
            client_max_units=client_max_units,
            estimated_units=estimated_units,
            reserved_units=client_max_units,
            state=UsageReservationState.RESERVED,
            request_id=command.request_id,
            lease_expires_at=timestamp + timedelta(seconds=self.reservation_lease_seconds),
            created_at=timestamp,
        )
        subscription.reserved_units = _quantize(subscription.reserved_units + client_max_units)
        subscription.row_version += 1
        self.session.add(reservation)
        self.session.flush()
        self._append_policy_event(
            subscription,
            client.id,
            entitlement.entitlement_key,
            reservation_id=reservation.id,
            phase="reserve",
            decision="allow",
            reason_code="licensed_request_reserved",
            query_sha256=query_sha256,
            cursor_chain_id=cursor_chain_id,
            page_depth=page_depth,
            requested_records=command.requested_result_limit,
            existing_unique_records=account_existing_coverage,
            projected_unique_records=account_projected_coverage,
            request_id=command.request_id,
            details=risk_assessment.details,
        )
        self._append_ledger(
            subscription.id,
            f"reserve:{reservation.id}",
            CommercialLedgerEventType.USAGE_RESERVED,
            command.request_id,
            reservation_id=reservation.id,
            reserved_delta=client_max_units,
            details={"billing_class": command.billing_class, "request_sha256": request_sha256},
        )
        self._append_outbox(
            reservation.id,
            "commercial.usage_reserved.v1",
            {
                "subscription_id": subscription.id,
                "billing_class": command.billing_class,
                "reserved_units": _unit_string(client_max_units),
            },
        )
        self.session.commit()
        return ReservationOutcome(reservation=reservation, replayed=False)

    def settle(self, command: SettleCommand, *, now: datetime | None = None) -> SettlementOutcome:
        timestamp = _timestamp(now)
        if command.result_count < 0:
            raise SettlementLimitExceeded("Result count cannot be negative")
        reservation = self._reservation_for_actor(command.reservation_id, lock=False)
        subscription = self._subscription_by_id(reservation.subscription_id, lock=True)
        reservation = self._reservation_for_actor(command.reservation_id, lock=True)
        if reservation.state == UsageReservationState.SETTLED:
            settlement, event = self._settlement_for_reservation(reservation.id)
            return SettlementOutcome(reservation, settlement, event, replayed=True)
        if reservation.state == UsageReservationState.EXPIRED:
            raise ReservationExpired("Usage reservation has expired")
        if reservation.state == UsageReservationState.RELEASED:
            raise ReservationConflict("Released usage reservation cannot be settled")
        if _timestamp(reservation.lease_expires_at) <= timestamp:
            self._release_locked(
                subscription,
                reservation,
                UsageReservationState.EXPIRED,
                "reservation lease expired",
                command.request_id,
                timestamp,
            )
            self.session.commit()
            raise ReservationExpired("Usage reservation has expired")
        encoded_result = _canonical_bytes(command.result)
        delivered_result_count = _delivered_result_count(reservation.billing_class, command.result)
        if command.result_count != delivered_result_count:
            raise SettlementLimitExceeded("Declared result count does not match the durable result")
        if delivered_result_count > reservation.requested_result_limit:
            raise SettlementLimitExceeded("Delivered result count exceeds the reserved request limit")
        if len(_canonical_bytes(command.metrics)) > MAX_USAGE_METRICS_BYTES:
            raise SettlementLimitExceeded("Commercial usage metrics exceed the size limit")
        delivered_bytes = len(encoded_result)
        declared_delivered_bytes = command.metrics.get("delivered_bytes")
        if declared_delivered_bytes is not None:
            if not reservation.billing_class.startswith("export."):
                raise SettlementLimitExceeded("External delivery bytes are only valid for governed exports")
            if (
                type(declared_delivered_bytes) is not int
                or declared_delivered_bytes < 0
                or (delivered_result_count > 0 and declared_delivered_bytes == 0)
            ):
                raise SettlementLimitExceeded("Delivered export bytes are invalid")
            delivered_bytes = declared_delivered_bytes
        actual_compute_units = _nonnegative_units(
            command.metrics.get("compute_units", ZERO_UNITS),
            field_name="Actual compute units",
        )
        if actual_compute_units != reservation.requested_compute_units:
            raise SettlementLimitExceeded("Actual compute units do not match the reserved compute units")
        item = self.session.get(RateCardItem, reservation.rate_card_item_id)
        if item is None or item.tenant_id != self.principal.tenant_id:
            raise CommercialInvariantViolation("Reserved rate-card item is unavailable")
        entitlement = self._entitlement(subscription.id, item.entitlement_key)
        existing_coverage = self._coverage_count(
            subscription.id,
            entitlement.entitlement_key,
            _start_of_day(timestamp),
        )
        response_limit = (
            entitlement.max_response_bytes
            if reservation.billing_class.startswith("export.")
            else min(self.max_result_bytes, entitlement.max_response_bytes)
        )
        if len(encoded_result) > self.max_result_bytes or delivered_bytes > response_limit:
            self._release_locked(
                subscription,
                reservation,
                UsageReservationState.RELEASED,
                "licensed response size exceeded",
                command.request_id,
                timestamp,
            )
            self._append_policy_event(
                subscription,
                reservation.agent_client_id,
                entitlement.entitlement_key,
                reservation_id=reservation.id,
                phase="settle",
                decision="deny",
                reason_code="response_size_exceeded",
                query_sha256=reservation.query_sha256,
                cursor_chain_id=reservation.cursor_chain_id,
                page_depth=reservation.page_depth,
                requested_records=delivered_result_count,
                existing_unique_records=existing_coverage,
                projected_unique_records=existing_coverage,
                request_id=command.request_id,
                details={
                    "response_bytes": delivered_bytes,
                    "limit_bytes": response_limit,
                    "durable_result_bytes": len(encoded_result),
                    "durable_result_limit_bytes": self.max_result_bytes,
                },
            )
            self.session.commit()
            raise SettlementLimitExceeded("Commercial result exceeds the licensed response size limit")

        record_hashes = _stable_record_hashes(reservation.billing_class, command.result)
        already_covered = self._covered_hashes(
            subscription.id,
            entitlement.entitlement_key,
            _start_of_day(timestamp),
            record_hashes,
        )
        new_record_hashes = record_hashes - already_covered
        projected_coverage = existing_coverage + len(new_record_hashes)
        if (
            entitlement.daily_unique_record_limit is not None
            and projected_coverage > entitlement.daily_unique_record_limit
        ):
            self._release_locked(
                subscription,
                reservation,
                UsageReservationState.RELEASED,
                "daily unique-record coverage exceeded",
                command.request_id,
                timestamp,
            )
            self._append_policy_event(
                subscription,
                reservation.agent_client_id,
                entitlement.entitlement_key,
                reservation_id=reservation.id,
                phase="settle",
                decision="deny",
                reason_code="daily_unique_record_limit_exceeded",
                query_sha256=reservation.query_sha256,
                cursor_chain_id=reservation.cursor_chain_id,
                page_depth=reservation.page_depth,
                requested_records=len(record_hashes),
                existing_unique_records=existing_coverage,
                projected_unique_records=projected_coverage,
                request_id=command.request_id,
            )
            self.session.commit()
            raise CommercialAccessDenied("Daily licensed unique-record coverage would be exceeded")
        response_kib = (delivered_bytes + 1023) // 1024
        charged_units = _quantize(
            item.base_units
            + item.per_result_units * delivered_result_count
            + item.per_kib_units * response_kib
            + item.per_compute_unit * actual_compute_units
        )
        if charged_units > reservation.reserved_units:
            self._release_locked(
                subscription,
                reservation,
                UsageReservationState.RELEASED,
                "actual charge exceeded client maximum",
                command.request_id,
                timestamp,
            )
            self.session.commit()
            raise SettlementLimitExceeded("Actual charge exceeds the reserved client maximum")

        if subscription.reserved_units < reservation.reserved_units:
            raise CommercialInvariantViolation("Subscription reservation balance is inconsistent")
        result_sha256 = hashlib.sha256(encoded_result).hexdigest()
        usage_event = UsageEvent(
            tenant_id=self.principal.tenant_id,
            event_key=f"usage:{reservation.id}",
            reservation_id=reservation.id,
            subscription_id=subscription.id,
            billing_class=reservation.billing_class,
            result_count=delivered_result_count,
            unique_record_count=len(record_hashes),
            new_unique_record_count=len(new_record_hashes),
            response_bytes=delivered_bytes,
            metrics_json=command.metrics,
            result_sha256=result_sha256,
            occurred_at=timestamp,
        )
        self.session.add(usage_event)
        self.session.flush()
        for record_hash in sorted(new_record_hashes):
            self.session.add(
                CommercialCoverageRecord(
                    tenant_id=self.principal.tenant_id,
                    subscription_id=subscription.id,
                    agent_client_id=reservation.agent_client_id,
                    actor_type=reservation.actor_type,
                    subject_id=reservation.subject_id,
                    entitlement_key=entitlement.entitlement_key,
                    period_start=_start_of_day(timestamp),
                    record_type=_coverage_record_type(reservation.billing_class),
                    record_identifier_sha256=record_hash,
                    first_usage_event_id=usage_event.id,
                    first_seen_at=timestamp,
                )
            )
        rate_card = self.session.get(RateCardVersion, subscription.rate_card_version_id)
        if rate_card is None:
            raise CommercialInvariantViolation("Subscription rate card is unavailable")
        settlement = UsageSettlement(
            tenant_id=self.principal.tenant_id,
            settlement_key=f"settlement:{reservation.id}",
            reservation_id=reservation.id,
            usage_event_id=usage_event.id,
            subscription_id=subscription.id,
            rate_card_version_id=rate_card.id,
            charged_units=charged_units,
            price_breakdown={
                "base_units": _unit_string(item.base_units),
                "result_count": delivered_result_count,
                "per_result_units": _unit_string(item.per_result_units),
                "response_kib": response_kib,
                "per_kib_units": _unit_string(item.per_kib_units),
                "compute_units": _unit_string(actual_compute_units),
                "per_compute_unit": _unit_string(item.per_compute_unit),
                "rate_card_key": rate_card.rate_card_key,
                "rate_card_revision": rate_card.revision,
            },
            result_json=command.result,
            created_at=timestamp,
        )
        self.session.add(settlement)
        self.session.flush()
        subscription.reserved_units = _quantize(subscription.reserved_units - reservation.reserved_units)
        subscription.consumed_units = _quantize(subscription.consumed_units + charged_units)
        subscription.row_version += 1
        reservation.state = UsageReservationState.SETTLED
        reservation.settled_at = timestamp
        self._append_policy_event(
            subscription,
            reservation.agent_client_id,
            entitlement.entitlement_key,
            reservation_id=reservation.id,
            phase="settle",
            decision="allow",
            reason_code="licensed_result_settled",
            query_sha256=reservation.query_sha256,
            cursor_chain_id=reservation.cursor_chain_id,
            page_depth=reservation.page_depth,
            requested_records=len(record_hashes),
            existing_unique_records=existing_coverage,
            projected_unique_records=projected_coverage,
            request_id=command.request_id,
            details={
                "result_count": delivered_result_count,
                "new_unique_record_count": len(new_record_hashes),
            },
        )
        self._append_ledger(
            subscription.id,
            f"settle:{reservation.id}",
            CommercialLedgerEventType.USAGE_SETTLED,
            command.request_id,
            reservation_id=reservation.id,
            settlement_id=settlement.id,
            reserved_delta=-reservation.reserved_units,
            consumed_delta=charged_units,
            details={"usage_event_id": usage_event.id, "result_sha256": result_sha256},
        )
        self._append_outbox(
            settlement.id,
            "commercial.usage_settled.v1",
            {
                "reservation_id": reservation.id,
                "subscription_id": subscription.id,
                "charged_units": _unit_string(charged_units),
                "result_count": delivered_result_count,
            },
        )
        self.session.commit()
        return SettlementOutcome(reservation, settlement, usage_event, replayed=False)

    def release(
        self,
        reservation_id: str,
        *,
        reason: str,
        request_id: str,
        now: datetime | None = None,
    ) -> ReservationOutcome:
        timestamp = _timestamp(now)
        reservation = self._reservation_for_actor(reservation_id, lock=False)
        subscription = self._subscription_by_id(reservation.subscription_id, lock=True)
        reservation = self._reservation_for_actor(reservation_id, lock=True)
        if reservation.state == UsageReservationState.SETTLED:
            settlement, _ = self._settlement_for_reservation(reservation.id)
            return ReservationOutcome(reservation, replayed=True, settlement=settlement)
        if reservation.state in {UsageReservationState.RELEASED, UsageReservationState.EXPIRED}:
            return ReservationOutcome(reservation, replayed=True)
        self._release_locked(
            subscription,
            reservation,
            UsageReservationState.RELEASED,
            reason[:500],
            request_id,
            timestamp,
        )
        self.session.commit()
        return ReservationOutcome(reservation, replayed=False)

    def authorize_paginated_query(
        self,
        reservation_id: str,
        *,
        billing_class: str,
        request_arguments: dict[str, Any],
        page_size: int,
        required_compute_units: Decimal | str = ZERO_UNITS,
        now: datetime | None = None,
    ) -> UsageReservation:
        timestamp = _timestamp(now)
        reservation = self._reservation_for_actor(reservation_id, lock=False)
        if reservation.state != UsageReservationState.RESERVED:
            raise ReservationConflict("Usage reservation is not available for data execution")
        if _timestamp(reservation.lease_expires_at) <= timestamp:
            subscription = self._subscription_by_id(reservation.subscription_id, lock=True)
            reservation = self._reservation_for_actor(reservation_id, lock=True)
            self._release_locked(
                subscription,
                reservation,
                UsageReservationState.EXPIRED,
                "reservation lease expired before data execution",
                reservation.request_id,
                timestamp,
            )
            self.session.commit()
            raise ReservationExpired("Usage reservation has expired")
        expected_query = query_fingerprint(billing_class, request_arguments, page_size)
        expected_compute_units = _nonnegative_units(
            required_compute_units,
            field_name="Required compute units",
        )
        if (
            reservation.billing_class != billing_class
            or reservation.requested_result_limit != page_size
            or reservation.query_sha256 != expected_query
            or reservation.requested_compute_units != expected_compute_units
        ):
            raise CommercialAccessDenied("Commercial reservation does not authorize this query")
        reservation = self._reservation_for_actor(reservation_id, lock=True)
        if reservation.state != UsageReservationState.RESERVED:
            raise ReservationConflict("Usage reservation is not available for data execution")
        if reservation.execution_started_at is not None:
            raise ReservationConflict("Usage reservation has already been claimed for data execution")
        reservation.execution_started_at = timestamp
        self.session.commit()
        return reservation

    def issue_next_cursor(self, reservation: UsageReservation, *, next_offset: int, has_more: bool) -> str | None:
        if not has_more:
            return None
        if next_offset <= reservation.page_offset:
            raise CommercialInvariantViolation("Pagination did not advance")
        item = self.session.get(RateCardItem, reservation.rate_card_item_id)
        if item is None or item.tenant_id != self.principal.tenant_id:
            raise CommercialInvariantViolation("Reserved rate-card item is unavailable")
        entitlement = self._entitlement(reservation.subscription_id, item.entitlement_key)
        if reservation.page_depth >= entitlement.max_page_depth:
            return None
        if self.cursor_codec is None:
            raise CommercialInvariantViolation("MCP cursor signing is unavailable")
        return self.cursor_codec.issue(
            self.principal,
            tool=reservation.billing_class,
            query_sha256=reservation.query_sha256,
            page_size=reservation.requested_result_limit,
            offset=next_offset,
            depth=reservation.page_depth + 1,
            chain_id=reservation.cursor_chain_id,
        )

    def _bound_client(self) -> tuple[AgentClient, AgentClientSubject]:
        client = self.session.scalar(
            select(AgentClient).where(
                AgentClient.tenant_id == self.principal.tenant_id,
                AgentClient.oauth_client_id == self.principal.commercial_client_id,
                AgentClient.active.is_(True),
            )
        )
        if client is None:
            raise CommercialNotConfigured("Agent client is not registered for commercial access")
        subject = self.session.scalar(
            select(AgentClientSubject).where(
                AgentClientSubject.tenant_id == self.principal.tenant_id,
                AgentClientSubject.agent_client_id == client.id,
                AgentClientSubject.actor_type == self.principal.actor_type,
                AgentClientSubject.subject_id == self.principal.actor_id,
                AgentClientSubject.active.is_(True),
            )
        )
        if subject is None:
            raise CommercialAccessDenied("Agent subject is not bound to the registered client")
        return client, subject

    def _subscription(self, client_id: str, now: datetime, *, lock: bool) -> CommercialSubscription:
        statement = (
            select(CommercialSubscription)
            .join(BillingAccount)
            .where(
                CommercialSubscription.tenant_id == self.principal.tenant_id,
                CommercialSubscription.agent_client_id == client_id,
                CommercialSubscription.status == SubscriptionStatus.ACTIVE,
                CommercialSubscription.starts_at <= now,
                (CommercialSubscription.ends_at.is_(None) | (CommercialSubscription.ends_at > now)),
                BillingAccount.status == BillingAccountStatus.ACTIVE,
            )
        )
        if lock:
            statement = statement.with_for_update(of=CommercialSubscription)
        subscription = self.session.scalar(statement)
        if subscription is None:
            raise CommercialNotConfigured("No active commercial subscription is available")
        return subscription

    def _subscription_by_id(self, subscription_id: str, *, lock: bool) -> CommercialSubscription:
        statement = select(CommercialSubscription).where(
            CommercialSubscription.tenant_id == self.principal.tenant_id,
            CommercialSubscription.id == subscription_id,
        )
        if lock:
            statement = statement.with_for_update()
        subscription = self.session.scalar(statement)
        if subscription is None:
            raise CommercialInvariantViolation("Commercial subscription is unavailable")
        return subscription

    def _risk_policy(self, billing_account_id: str, *, lock: bool) -> CommercialRiskPolicy:
        statement = select(CommercialRiskPolicy).where(
            CommercialRiskPolicy.tenant_id == self.principal.tenant_id,
            CommercialRiskPolicy.billing_account_id == billing_account_id,
        )
        if lock:
            statement = statement.with_for_update()
        policy = self.session.scalar(statement)
        if policy is None:
            raise CommercialNotConfigured("Customer-level commercial risk policy is not configured")
        return policy

    def _rate_item(
        self,
        subscription: CommercialSubscription,
        billing_class: str,
        now: datetime,
    ) -> RateCardItem:
        item = self.session.scalar(
            select(RateCardItem)
            .join(RateCardVersion)
            .where(
                RateCardItem.tenant_id == self.principal.tenant_id,
                RateCardItem.rate_card_version_id == subscription.rate_card_version_id,
                RateCardItem.billing_class == billing_class,
                RateCardVersion.effective_from <= now,
                (RateCardVersion.effective_until.is_(None) | (RateCardVersion.effective_until > now)),
            )
        )
        if item is None:
            raise CommercialAccessDenied("Billing class is not available on the active rate card")
        return item

    def _entitlement(self, subscription_id: str, entitlement_key: str) -> CommercialEntitlement:
        item = self.session.scalar(
            select(CommercialEntitlement).where(
                CommercialEntitlement.tenant_id == self.principal.tenant_id,
                CommercialEntitlement.subscription_id == subscription_id,
                CommercialEntitlement.entitlement_key == entitlement_key,
                CommercialEntitlement.enabled.is_(True),
            )
        )
        if item is None:
            raise CommercialAccessDenied("Required data entitlement is not active")
        return item

    def _existing_reservation(self, client_id: str, idempotency_key: str) -> UsageReservation | None:
        return self.session.scalar(
            select(UsageReservation).where(
                UsageReservation.tenant_id == self.principal.tenant_id,
                UsageReservation.agent_client_id == client_id,
                UsageReservation.actor_type == self.principal.actor_type,
                UsageReservation.subject_id == self.principal.actor_id,
                UsageReservation.idempotency_key == idempotency_key,
            )
        )

    def _replay_reservation(
        self,
        reservation: UsageReservation,
        request_sha256: str,
        now: datetime,
    ) -> ReservationOutcome:
        if reservation.request_sha256 != request_sha256:
            raise IdempotencyConflict("Idempotency key was already used for a different request")
        if reservation.state == UsageReservationState.SETTLED:
            settlement, _ = self._settlement_for_reservation(reservation.id)
            return ReservationOutcome(reservation, replayed=True, settlement=settlement)
        if reservation.state == UsageReservationState.RESERVED and _timestamp(reservation.lease_expires_at) <= now:
            subscription = self._subscription_by_id(reservation.subscription_id, lock=True)
            reservation = self._reservation_for_actor(reservation.id, lock=True)
            if reservation.state != UsageReservationState.RESERVED:
                return self._replay_reservation(reservation, request_sha256, now)
            self._release_locked(
                subscription,
                reservation,
                UsageReservationState.EXPIRED,
                "reservation lease expired",
                reservation.request_id,
                now,
            )
            self.session.commit()
        return ReservationOutcome(reservation, replayed=True)

    def _reservation_for_actor(self, reservation_id: str, *, lock: bool) -> UsageReservation:
        statement = select(UsageReservation).where(
            UsageReservation.tenant_id == self.principal.tenant_id,
            UsageReservation.id == reservation_id,
            UsageReservation.actor_type == self.principal.actor_type,
            UsageReservation.subject_id == self.principal.actor_id,
        )
        if lock:
            statement = statement.with_for_update()
        reservation = self.session.scalar(statement)
        if reservation is None:
            raise CommercialAccessDenied("Usage reservation is unavailable for this Agent subject")
        return reservation

    def _settlement_for_reservation(self, reservation_id: str) -> tuple[UsageSettlement, UsageEvent]:
        settlement = self.session.scalar(
            select(UsageSettlement).where(
                UsageSettlement.tenant_id == self.principal.tenant_id,
                UsageSettlement.reservation_id == reservation_id,
            )
        )
        if settlement is None:
            raise CommercialInvariantViolation("Settled reservation has no settlement record")
        event = self.session.get(UsageEvent, settlement.usage_event_id)
        if event is None or event.tenant_id != self.principal.tenant_id:
            raise CommercialInvariantViolation("Settlement has no usage event")
        return settlement, event

    def _expire_stale_locked(
        self,
        subscription: CommercialSubscription,
        now: datetime,
        request_id: str,
    ) -> None:
        stale = self.session.scalars(
            select(UsageReservation)
            .where(
                UsageReservation.tenant_id == self.principal.tenant_id,
                UsageReservation.subscription_id == subscription.id,
                UsageReservation.state == UsageReservationState.RESERVED,
                UsageReservation.lease_expires_at <= now,
            )
            .with_for_update()
        ).all()
        for reservation in stale:
            self._release_locked(
                subscription,
                reservation,
                UsageReservationState.EXPIRED,
                "reservation lease expired",
                request_id,
                now,
            )

    def _release_locked(
        self,
        subscription: CommercialSubscription,
        reservation: UsageReservation,
        state: UsageReservationState,
        reason: str,
        request_id: str,
        now: datetime,
    ) -> None:
        if subscription.reserved_units < reservation.reserved_units:
            raise CommercialInvariantViolation("Subscription reservation balance is inconsistent")
        subscription.reserved_units = _quantize(subscription.reserved_units - reservation.reserved_units)
        subscription.row_version += 1
        reservation.state = state
        reservation.released_at = now
        reservation.release_reason = reason
        event_type = (
            CommercialLedgerEventType.RESERVATION_EXPIRED
            if state == UsageReservationState.EXPIRED
            else CommercialLedgerEventType.RESERVATION_RELEASED
        )
        self._append_ledger(
            subscription.id,
            f"{state.value}:{reservation.id}",
            event_type,
            request_id,
            reservation_id=reservation.id,
            reserved_delta=-reservation.reserved_units,
            details={"reason": reason},
        )
        self._append_outbox(
            reservation.id,
            f"commercial.reservation_{state.value}.v1",
            {"subscription_id": subscription.id, "reason": reason},
        )

    def _enforce_daily_limit(
        self,
        subscription_id: str,
        entitlement: CommercialEntitlement,
        requested_units: Decimal,
        now: datetime,
    ) -> None:
        if entitlement.daily_unit_limit is None:
            return
        start_of_day = datetime(now.year, now.month, now.day, tzinfo=UTC)
        consumed = self.session.scalar(
            select(func.coalesce(func.sum(UsageSettlement.charged_units), ZERO_UNITS))
            .join(UsageReservation, UsageReservation.id == UsageSettlement.reservation_id)
            .join(RateCardItem, RateCardItem.id == UsageReservation.rate_card_item_id)
            .where(
                UsageSettlement.tenant_id == self.principal.tenant_id,
                UsageSettlement.subscription_id == subscription_id,
                UsageSettlement.created_at >= start_of_day,
                RateCardItem.entitlement_key == entitlement.entitlement_key,
            )
        )
        reserved = self.session.scalar(
            select(func.coalesce(func.sum(UsageReservation.reserved_units), ZERO_UNITS))
            .join(RateCardItem, RateCardItem.id == UsageReservation.rate_card_item_id)
            .where(
                UsageReservation.tenant_id == self.principal.tenant_id,
                UsageReservation.subscription_id == subscription_id,
                UsageReservation.state == UsageReservationState.RESERVED,
                RateCardItem.entitlement_key == entitlement.entitlement_key,
            )
        )
        projected = _quantize(Decimal(consumed or 0) + Decimal(reserved or 0) + requested_units)
        if projected > entitlement.daily_unit_limit:
            raise CommercialAccessDenied("Daily licensed usage limit would be exceeded")

    def _resolve_pagination(self, command: ReserveCommand, query_sha256: str) -> tuple[str, int, int]:
        cursor = command.request_arguments.get("cursor")
        if cursor is None:
            return str(uuid.uuid4()), 0, 1
        if not isinstance(cursor, str) or not cursor:
            raise CommercialAccessDenied("Pagination cursor is invalid or expired")
        if self.cursor_codec is None:
            raise CommercialInvariantViolation("MCP cursor verification is unavailable")
        try:
            claims = self.cursor_codec.verify(
                cursor,
                self.principal,
                tool=command.billing_class,
                query_sha256=query_sha256,
                page_size=command.requested_result_limit,
            )
        except CursorError as exc:
            raise CommercialAccessDenied("Pagination cursor is invalid or expired") from exc
        return claims.chain_id, claims.offset, claims.depth

    def _coverage_count(self, subscription_id: str, entitlement_key: str, period_start: datetime) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(CommercialCoverageRecord)
                .where(
                    CommercialCoverageRecord.tenant_id == self.principal.tenant_id,
                    CommercialCoverageRecord.subscription_id == subscription_id,
                    CommercialCoverageRecord.entitlement_key == entitlement_key,
                    CommercialCoverageRecord.period_start == period_start,
                )
            )
            or 0
        )

    def _account_coverage_count(
        self,
        billing_account_id: str,
        entitlement_key: str,
        period_start: datetime,
    ) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(CommercialCoverageRecord)
                .join(
                    CommercialSubscription,
                    CommercialSubscription.id == CommercialCoverageRecord.subscription_id,
                )
                .where(
                    CommercialCoverageRecord.tenant_id == self.principal.tenant_id,
                    CommercialSubscription.billing_account_id == billing_account_id,
                    CommercialCoverageRecord.entitlement_key == entitlement_key,
                    CommercialCoverageRecord.period_start == period_start,
                )
            )
            or 0
        )

    def _projected_account_coverage(
        self,
        billing_account_id: str,
        entitlement_key: str,
        existing_coverage: int,
        requested_records: int,
        now: datetime,
    ) -> int:
        reserved_capacity = int(
            self.session.scalar(
                select(func.coalesce(func.sum(UsageReservation.requested_result_limit), 0))
                .join(
                    CommercialSubscription,
                    CommercialSubscription.id == UsageReservation.subscription_id,
                )
                .join(RateCardItem, RateCardItem.id == UsageReservation.rate_card_item_id)
                .where(
                    UsageReservation.tenant_id == self.principal.tenant_id,
                    CommercialSubscription.billing_account_id == billing_account_id,
                    UsageReservation.state == UsageReservationState.RESERVED,
                    UsageReservation.lease_expires_at > now,
                    RateCardItem.entitlement_key == entitlement_key,
                )
            )
            or 0
        )
        return existing_coverage + reserved_capacity + requested_records

    def _assess_account_risk(
        self,
        subscription: CommercialSubscription,
        policy: CommercialRiskPolicy,
        agent_client_id: str,
        entitlement_key: str,
        billing_class: str,
        request_arguments: dict[str, Any],
        network_fingerprint: str | None,
        correlation_key_id: str,
        now: datetime,
    ) -> RiskAssessment:
        signal = _partition_risk_signal(billing_class, request_arguments)
        details: dict[str, Any] = {
            "risk_policy_id": policy.id,
            "risk_policy_version": policy.policy_version,
            "risk_window_seconds": policy.partition_window_seconds,
            "correlation_key_id": correlation_key_id,
        }
        if network_fingerprint is not None:
            details["network_fingerprint"] = network_fingerprint
        if self.principal.credential_fingerprint is not None:
            details["credential_fingerprint"] = self.principal.credential_fingerprint
        if signal is not None:
            details.update(
                {
                    "risk_signal": "partition_query",
                    "query_shape_sha256": signal.query_shape_sha256,
                    "partition_token_sha256": signal.partition_token_sha256,
                    "argument_path_sha256": signal.argument_path_sha256,
                }
            )
        if not policy.enabled:
            details["risk_policy_enabled"] = False
            return RiskAssessment(details)

        window_start = now - timedelta(seconds=policy.partition_window_seconds)
        recent_events = self.session.scalars(
            select(CommercialPolicyEvent)
            .join(
                CommercialSubscription,
                CommercialSubscription.id == CommercialPolicyEvent.subscription_id,
            )
            .where(
                CommercialPolicyEvent.tenant_id == self.principal.tenant_id,
                CommercialSubscription.billing_account_id == subscription.billing_account_id,
                CommercialPolicyEvent.entitlement_key == entitlement_key,
                CommercialPolicyEvent.phase == "reserve",
                CommercialPolicyEvent.occurred_at >= window_start,
            )
            .order_by(CommercialPolicyEvent.occurred_at.desc())
            .limit(min(policy.max_requests_per_window + 1, MAX_RISK_EVENTS_SCANNED))
        ).all()
        distinct_clients = {event.agent_client_id for event in recent_events}
        distinct_clients.add(agent_client_id)
        correlation_events = [
            event for event in recent_events if event.details.get("correlation_key_id") == correlation_key_id
        ]
        network_fingerprints = {
            str(event.details["network_fingerprint"])
            for event in correlation_events
            if isinstance(event.details.get("network_fingerprint"), str)
        }
        credential_fingerprints = {
            str(event.details["credential_fingerprint"])
            for event in correlation_events
            if isinstance(event.details.get("credential_fingerprint"), str)
        }
        if network_fingerprint is not None:
            network_fingerprints.add(network_fingerprint)
        if self.principal.credential_fingerprint is not None:
            credential_fingerprints.add(self.principal.credential_fingerprint)
        details["window_distinct_client_count"] = len(distinct_clients)
        details["window_distinct_network_count"] = len(network_fingerprints)
        details["window_distinct_credential_count"] = len(credential_fingerprints)
        details["window_event_count"] = len(recent_events) + 1
        details["window_event_scan_truncated"] = len(recent_events) == MAX_RISK_EVENTS_SCANNED
        if len(recent_events) >= policy.max_requests_per_window:
            return RiskAssessment(
                details,
                "account_request_window_limit_exceeded",
                "Customer-level request window limit would be exceeded",
            )
        if len(distinct_clients) > policy.max_distinct_clients_per_window:
            return RiskAssessment(
                details,
                "client_fanout_limit_exceeded",
                "Customer-level Agent client fanout would exceed the risk policy",
            )
        if len(network_fingerprints) > policy.max_distinct_networks_per_window:
            return RiskAssessment(
                details,
                "network_rotation_limit_exceeded",
                "Customer-level Agent network rotation would exceed the risk policy",
            )
        if len(credential_fingerprints) > policy.max_distinct_credentials_per_window:
            return RiskAssessment(
                details,
                "credential_rotation_limit_exceeded",
                "Customer-level Agent credential rotation would exceed the risk policy",
            )
        if signal is None:
            return RiskAssessment(details)

        matching_events = [
            event
            for event in recent_events
            if event.details.get("risk_signal") == "partition_query"
            and event.details.get("query_shape_sha256") == signal.query_shape_sha256
        ]
        partition_tokens = {
            str(event.details["partition_token_sha256"])
            for event in matching_events
            if isinstance(event.details.get("partition_token_sha256"), str)
        }
        partition_tokens.add(signal.partition_token_sha256)
        partition_clients = {event.agent_client_id for event in matching_events}
        partition_clients.add(agent_client_id)
        details["window_partition_count"] = len(partition_tokens)
        details["window_partition_client_count"] = len(partition_clients)
        if len(partition_clients) > 1 and len(partition_tokens) > policy.max_cross_client_partition_queries_per_window:
            return RiskAssessment(
                details,
                "cross_client_partition_enumeration_detected",
                "Cross-client partition enumeration was denied by the customer risk policy",
            )
        if len(partition_tokens) > policy.max_partition_queries_per_window:
            return RiskAssessment(
                details,
                "partition_enumeration_detected",
                "Partition enumeration was denied by the customer risk policy",
            )
        return RiskAssessment(details)

    def _projected_coverage(
        self,
        subscription_id: str,
        entitlement: CommercialEntitlement,
        existing_coverage: int,
        requested_records: int,
        now: datetime,
    ) -> int:
        reserved_capacity = int(
            self.session.scalar(
                select(func.coalesce(func.sum(UsageReservation.requested_result_limit), 0))
                .join(RateCardItem, RateCardItem.id == UsageReservation.rate_card_item_id)
                .where(
                    UsageReservation.tenant_id == self.principal.tenant_id,
                    UsageReservation.subscription_id == subscription_id,
                    UsageReservation.state == UsageReservationState.RESERVED,
                    UsageReservation.lease_expires_at > now,
                    RateCardItem.entitlement_key == entitlement.entitlement_key,
                )
            )
            or 0
        )
        return existing_coverage + reserved_capacity + requested_records

    def _active_reservation_count(self, subscription_id: str, client_id: str, now: datetime) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(UsageReservation)
                .where(
                    UsageReservation.tenant_id == self.principal.tenant_id,
                    UsageReservation.subscription_id == subscription_id,
                    UsageReservation.agent_client_id == client_id,
                    UsageReservation.state == UsageReservationState.RESERVED,
                    UsageReservation.lease_expires_at > now,
                )
            )
            or 0
        )

    def _covered_hashes(
        self,
        subscription_id: str,
        entitlement_key: str,
        period_start: datetime,
        record_hashes: set[str],
    ) -> set[str]:
        if not record_hashes:
            return set()
        hashes = sorted(record_hashes)
        covered: set[str] = set()
        for start in range(0, len(hashes), 500):
            batch = hashes[start : start + 500]
            covered.update(
                self.session.scalars(
                    select(CommercialCoverageRecord.record_identifier_sha256).where(
                        CommercialCoverageRecord.tenant_id == self.principal.tenant_id,
                        CommercialCoverageRecord.subscription_id == subscription_id,
                        CommercialCoverageRecord.entitlement_key == entitlement_key,
                        CommercialCoverageRecord.period_start == period_start,
                        CommercialCoverageRecord.record_identifier_sha256.in_(batch),
                    )
                ).all()
            )
        return covered

    def _append_policy_event(
        self,
        subscription: CommercialSubscription,
        agent_client_id: str,
        entitlement_key: str,
        *,
        phase: str,
        decision: str,
        reason_code: str,
        query_sha256: str,
        cursor_chain_id: str,
        page_depth: int,
        requested_records: int,
        existing_unique_records: int,
        projected_unique_records: int,
        request_id: str,
        reservation_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            CommercialPolicyEvent(
                tenant_id=self.principal.tenant_id,
                subscription_id=subscription.id,
                agent_client_id=agent_client_id,
                reservation_id=reservation_id,
                actor_type=self.principal.actor_type,
                subject_id=self.principal.actor_id,
                entitlement_key=entitlement_key,
                phase=phase,
                decision=decision,
                reason_code=reason_code,
                query_sha256=query_sha256,
                cursor_chain_id=cursor_chain_id,
                page_depth=page_depth,
                requested_records=requested_records,
                existing_unique_records=existing_unique_records,
                projected_unique_records=projected_unique_records,
                request_id=request_id,
                details=details or {},
                occurred_at=datetime.now(UTC),
            )
        )

    def _append_ledger(
        self,
        subscription_id: str,
        event_key: str,
        event_type: CommercialLedgerEventType,
        request_id: str,
        *,
        reservation_id: str | None = None,
        settlement_id: str | None = None,
        granted_delta: Decimal = ZERO_UNITS,
        reserved_delta: Decimal = ZERO_UNITS,
        consumed_delta: Decimal = ZERO_UNITS,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            CommercialLedgerEntry(
                tenant_id=self.principal.tenant_id,
                subscription_id=subscription_id,
                reservation_id=reservation_id,
                settlement_id=settlement_id,
                event_key=event_key,
                event_type=event_type,
                granted_delta=_quantize(granted_delta),
                reserved_delta=_quantize(reserved_delta),
                consumed_delta=_quantize(consumed_delta),
                request_id=request_id,
                details=details or {},
            )
        )

    def _append_outbox(self, aggregate_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.session.add(
            OutboxEvent(
                tenant_id=self.principal.tenant_id,
                aggregate_type="commercial_usage",
                aggregate_id=aggregate_id,
                event_type=event_type,
                payload=payload,
            )
        )


def _validate_reserve_command(command: ReserveCommand) -> None:
    if not IDEMPOTENCY_PATTERN.fullmatch(command.idempotency_key):
        raise ValueError("Idempotency key must contain 8-128 safe characters")
    if not BILLING_CLASS_PATTERN.fullmatch(command.billing_class):
        raise ValueError("Billing class is invalid")
    if command.requested_result_limit <= 0:
        raise ValueError("Requested result limit must be positive")
    argument_limit = command.request_arguments.get("limit")
    if argument_limit is not None and (
        type(argument_limit) is not int or argument_limit != command.requested_result_limit
    ):
        raise ValueError("Request limit must match the commercial reservation limit")
    if not command.request_id or len(command.request_id) > 100:
        raise ValueError("Request ID is invalid")
    if command.network_fingerprint is not None and FINGERPRINT_PATTERN.fullmatch(command.network_fingerprint) is None:
        raise ValueError("Network fingerprint is invalid")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}", command.correlation_key_id) is None:
        raise ValueError("Correlation key ID is invalid")
    if len(_canonical_bytes(command.request_arguments)) > MAX_REQUEST_ARGUMENT_BYTES:
        raise ValueError("Commercial request arguments exceed the size limit")


def _units(value: Decimal | str) -> Decimal:
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Billable units must be a decimal number") from exc
    if not parsed.is_finite() or parsed <= ZERO_UNITS:
        raise ValueError("Billable units must be positive and finite")
    return _quantize(parsed)


def _nonnegative_units(value: Any, *, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a decimal number")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a decimal number") from exc
    if not parsed.is_finite() or parsed < ZERO_UNITS:
        raise ValueError(f"{field_name} must be non-negative and finite")
    return _quantize(parsed)


def _quantize(value: Decimal | int) -> Decimal:
    return Decimal(value).quantize(UNIT_QUANTUM, rounding=ROUND_HALF_UP)


def _unit_string(value: Decimal) -> str:
    return format(_quantize(value), "f")


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
            default=_json_default,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Commercial request or result is not valid JSON") from exc


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal | datetime):
        return str(value)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _commercial_result_rows(
    billing_class: str,
    result: dict[str, Any] | list[Any],
) -> list[tuple[str, Any]]:
    record_type = _coverage_record_type(billing_class)
    if isinstance(result, list):
        return [(record_type, row) for row in result]
    if billing_class == "entity.dossier":
        rows: list[tuple[str, Any]] = []
        entity = result.get("entity")
        if not isinstance(entity, dict):
            raise SettlementLimitExceeded("Entity dossier must contain an entity object")
        rows.append((f"{record_type}.entity", entity))
        for key in DOSSIER_RECORD_COLLECTIONS:
            values = result.get(key)
            if not isinstance(values, list):
                raise SettlementLimitExceeded(f"Entity dossier field '{key}' must be an array")
            rows.extend((f"{record_type}.{key}", row) for row in values)
        return rows
    for key in ("items", "chunks"):
        if key in result:
            values = result[key]
            if not isinstance(values, list):
                raise SettlementLimitExceeded(f"Commercial result field '{key}' must be an array")
            return [(record_type, row) for row in values]
    return [(record_type, result)]


def _delivered_result_count(billing_class: str, result: dict[str, Any] | list[Any]) -> int:
    return len(_commercial_result_rows(billing_class, result))


def _stable_record_hashes(billing_class: str, result: dict[str, Any] | list[Any]) -> set[str]:
    return {
        hashlib.sha256(
            _canonical_bytes({"record_type": record_type, "identity": _stable_record_identity(row)})
        ).hexdigest()
        for record_type, row in _commercial_result_rows(billing_class, result)
    }


def _stable_record_identity(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {"value": row}
    for key in (
        "id",
        "entity_id",
        "claim_id",
        "registry_id",
        "family_identifier",
        "page_id",
        "standard_inchi_key",
        "inchi_key",
    ):
        value = row.get(key)
        if isinstance(value, str) and value:
            return {key: value}
    entity = row.get("entity")
    if isinstance(entity, dict):
        entity_id = entity.get("id")
        if isinstance(entity_id, str) and entity_id:
            return {"entity_id": entity_id}
    document_id = row.get("document_id")
    if isinstance(document_id, str) and document_id:
        return {
            "document_id": document_id,
            "dataset_id": row.get("dataset_id"),
            "positions": row.get("positions"),
            "content_sha256": hashlib.sha256(str(row.get("content", "")).encode("utf-8")).hexdigest(),
        }
    return {"record_sha256": hashlib.sha256(_canonical_bytes(row)).hexdigest()}


def _partition_risk_signal(
    billing_class: str,
    request_arguments: dict[str, Any],
) -> PartitionRiskSignal | None:
    candidates: list[tuple[tuple[str, ...], str]] = []

    def visit(value: Any, path: tuple[str, ...]) -> None:
        if isinstance(value, dict):
            for raw_key in sorted(value, key=str):
                key = str(raw_key)
                child = value[raw_key]
                normalized_key = key.casefold()
                token = _partition_token(normalized_key, child)
                if token is not None:
                    candidates.append(((*path, normalized_key), token))
                visit(child, (*path, normalized_key))
        elif isinstance(value, list):
            for index, child in enumerate(value[:100]):
                visit(child, (*path, str(index)))

    visit(request_arguments, ())
    if not candidates:
        return None
    argument_path, token = candidates[0]
    masked_arguments = _mask_partition_argument(request_arguments, argument_path)
    return PartitionRiskSignal(
        query_shape_sha256=_sha256(
            {
                "billing_class": billing_class,
                "argument_path": argument_path,
                "arguments": masked_arguments,
            }
        ),
        partition_token_sha256=_sha256({"partition_token": token}),
        argument_path_sha256=_sha256({"argument_path": argument_path}),
    )


def _partition_token(key: str, value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, str | int):
        return None
    token = str(value).strip().casefold()
    if not token or len(token) > 64:
        return None
    if key in PARTITION_ARGUMENT_KEYS:
        return token
    if key in GENERIC_QUERY_ARGUMENT_KEYS and re.fullmatch(
        r"(?:[a-z0-9]\*?|[a-z0-9]{1,3}\s*(?:-|:|\.\.)\s*[a-z0-9]{1,3})",
        token,
    ):
        return token
    return None


def _mask_partition_argument(value: Any, target_path: tuple[str, ...], path: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for raw_key in sorted(value, key=str):
            key = str(raw_key)
            normalized_key = key.casefold()
            if normalized_key in {"cursor", "limit", "offset", "page_size"}:
                continue
            child_path = (*path, normalized_key)
            masked[key] = (
                "<partition>"
                if child_path == target_path
                else _mask_partition_argument(value[raw_key], target_path, child_path)
            )
        return masked
    if isinstance(value, list):
        return [
            "<partition>"
            if (*path, str(index)) == target_path
            else _mask_partition_argument(child, target_path, (*path, str(index)))
            for index, child in enumerate(value[:100])
        ]
    return value


def _coverage_record_type(billing_class: str) -> str:
    if billing_class.startswith("entity."):
        return "entity"
    return {
        "evidence.search": "evidence_chunk",
        "provenance.read": "fact_provenance",
        "target.profile": "target_profile",
        "target.evidence.search": "target_evidence",
        "bioactivity.search": "bioactivity",
        "sar.compare": "bioactivity",
        "pipeline.search": "competitive_program",
        "structure.search": "compound_structure",
        "structure.exact": "compound_structure",
        "structure.substructure": "compound_structure",
        "structure.similarity": "compound_structure",
        "trial.search": "clinical_trial",
        "trial.read": "clinical_trial",
        "patent.search": "patent_family",
        "deal.search": "deal",
        "company.timeline": "company_timeline_event",
        "regulatory.search": "regulatory_event",
        "epidemiology.search": "epidemiology_observation",
        "news.search": "news_event",
        "knowledge.search": "knowledge_page",
        "knowledge.read": "knowledge_page",
    }.get(billing_class, billing_class)


def _start_of_day(value: datetime) -> datetime:
    timestamp = _timestamp(value)
    return datetime(timestamp.year, timestamp.month, timestamp.day, tzinfo=UTC)


def _timestamp(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(UTC)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)
