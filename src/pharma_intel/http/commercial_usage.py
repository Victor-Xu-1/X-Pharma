from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session

from pharma_intel.commercial.service import (
    CommercialInvariantViolation,
    ReservationOutcome,
    ReserveCommand,
    SettleCommand,
    SettlementOutcome,
)
from pharma_intel.http import runtime
from pharma_intel.http.commercial_policy import _commercial_service
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.models import UsageEvent, UsageSettlement
from pharma_intel.request_correlation import (
    NETWORK_FINGERPRINT_HEADER,
    CorrelationSignalError,
    validate_internal_network_fingerprint,
)
from pharma_intel.schemas import (
    CommercialAccessRead,
    CommercialEstimateRead,
    CommercialEstimateRequest,
    CommercialReleaseRequest,
    CommercialReservationRead,
    CommercialReserveRequest,
    CommercialSettlementRead,
    CommercialSettlementRequest,
    CommercialUsageSummaryRead,
)

router = APIRouter()


def _settlement_read(settlement: UsageSettlement, usage_event: UsageEvent) -> CommercialSettlementRead:
    return CommercialSettlementRead(
        settlement_id=settlement.id,
        usage_event_id=usage_event.id,
        charged_units=format(settlement.charged_units, "f"),
        result_count=usage_event.result_count,
        unique_record_count=usage_event.unique_record_count,
        new_unique_record_count=usage_event.new_unique_record_count,
        response_bytes=usage_event.response_bytes,
        price_breakdown=settlement.price_breakdown,
        result=settlement.result_json,
        created_at=settlement.created_at,
    )


def _reservation_read(
    outcome: ReservationOutcome,
    session: Session,
) -> CommercialReservationRead:
    settlement_read: CommercialSettlementRead | None = None
    if outcome.settlement is not None:
        usage_event = session.get(UsageEvent, outcome.settlement.usage_event_id)
        if usage_event is None or usage_event.tenant_id != outcome.reservation.tenant_id:
            raise CommercialInvariantViolation("Settlement usage event is unavailable")
        settlement_read = _settlement_read(outcome.settlement, usage_event)
    return CommercialReservationRead(
        reservation_id=outcome.reservation.id,
        state=outcome.reservation.state,
        billing_class=outcome.reservation.billing_class,
        estimated_units=format(outcome.reservation.estimated_units, "f"),
        reserved_units=format(outcome.reservation.reserved_units, "f"),
        requested_compute_units=format(outcome.reservation.requested_compute_units, "f"),
        lease_expires_at=outcome.reservation.lease_expires_at,
        page_depth=outcome.reservation.page_depth,
        replayed=outcome.replayed,
        settlement=settlement_read,
    )


@router.get(
    "/internal/v1/commercial/access",
    response_model=CommercialAccessRead,
    tags=["internal-commercial"],
)
def commercial_access(principal: PrincipalDep, session: SessionDep) -> CommercialAccessRead:
    snapshot = _commercial_service(session, principal).access_snapshot()
    return CommercialAccessRead.model_validate(snapshot)


@router.post(
    "/internal/v1/commercial/estimate",
    response_model=CommercialEstimateRead,
    tags=["internal-commercial"],
)
def estimate_commercial_usage(
    payload: CommercialEstimateRequest,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialEstimateRead:
    estimate = _commercial_service(session, principal).estimate(
        payload.billing_class,
        payload.requested_result_limit,
        payload.requested_compute_units,
    )
    return CommercialEstimateRead.model_validate(estimate)


@router.get(
    "/internal/v1/commercial/usage-summary",
    response_model=CommercialUsageSummaryRead,
    tags=["internal-commercial"],
)
def commercial_usage_summary(principal: PrincipalDep, session: SessionDep) -> CommercialUsageSummaryRead:
    summary = _commercial_service(session, principal).usage_summary()
    return CommercialUsageSummaryRead.model_validate(summary)


@router.post(
    "/internal/v1/commercial/reservations",
    response_model=CommercialReservationRead,
    tags=["internal-commercial"],
)
def reserve_commercial_usage(
    payload: CommercialReserveRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialReservationRead:
    settings = runtime.get_settings()
    try:
        network_fingerprint = validate_internal_network_fingerprint(
            request.headers.get(NETWORK_FINGERPRINT_HEADER),
            settings,
        )
    except CorrelationSignalError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        outcome = _commercial_service(session, principal).reserve(
            ReserveCommand(
                billing_class=payload.billing_class,
                idempotency_key=payload.idempotency_key,
                request_arguments=payload.request_arguments,
                requested_result_limit=payload.requested_result_limit,
                max_billable_units=payload.max_billable_units,
                request_id=request.state.request_id,
                requested_compute_units=payload.requested_compute_units,
                network_fingerprint=network_fingerprint,
                correlation_key_id=settings.mcp_correlation_key_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _reservation_read(outcome, session)


@router.post(
    "/internal/v1/commercial/reservations/{reservation_id}/settle",
    response_model=CommercialReservationRead,
    tags=["internal-commercial"],
)
def settle_commercial_usage(
    reservation_id: str,
    payload: CommercialSettlementRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialReservationRead:
    outcome: SettlementOutcome = _commercial_service(session, principal).settle(
        SettleCommand(
            reservation_id=reservation_id,
            result_count=payload.result_count,
            result=payload.result,
            metrics=payload.metrics,
            request_id=request.state.request_id,
        )
    )
    return CommercialReservationRead(
        reservation_id=outcome.reservation.id,
        state=outcome.reservation.state,
        billing_class=outcome.reservation.billing_class,
        estimated_units=format(outcome.reservation.estimated_units, "f"),
        reserved_units=format(outcome.reservation.reserved_units, "f"),
        requested_compute_units=format(outcome.reservation.requested_compute_units, "f"),
        lease_expires_at=outcome.reservation.lease_expires_at,
        page_depth=outcome.reservation.page_depth,
        replayed=outcome.replayed,
        settlement=_settlement_read(outcome.settlement, outcome.usage_event),
    )


@router.post(
    "/internal/v1/commercial/reservations/{reservation_id}/release",
    response_model=CommercialReservationRead,
    tags=["internal-commercial"],
)
def release_commercial_usage(
    reservation_id: str,
    payload: CommercialReleaseRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialReservationRead:
    outcome = _commercial_service(session, principal).release(
        reservation_id,
        reason=payload.reason,
        request_id=request.state.request_id,
    )
    return _reservation_read(outcome, session)
