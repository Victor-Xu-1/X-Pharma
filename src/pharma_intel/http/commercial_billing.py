from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, status

from pharma_intel.commercial.billing_operations import BillingOperationsService
from pharma_intel.commercial.disputes import (
    BillingDisputeService,
    CreateBillingDisputeCommand,
    TransitionBillingDisputeCommand,
)
from pharma_intel.http import runtime
from pharma_intel.http.commercial_policy import _require_human_commercial
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.schemas import (
    BillingAccountRead,
    BillingCustomerMappingUpdate,
    BillingDeliveryRead,
    BillingDeliveryReplayRequest,
    BillingDisputeCreate,
    BillingDisputeRead,
    BillingDisputeTransition,
)

router = APIRouter()


@router.get(
    "/api/v1/commercial/billing-accounts",
    response_model=list[BillingAccountRead],
    tags=["commercial"],
)
def list_billing_accounts(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[BillingAccountRead]:
    _require_human_commercial(principal, "commercial:read")
    items = BillingOperationsService(session, principal).list_accounts(limit=limit)
    return [BillingAccountRead.model_validate(item) for item in items]


@router.post(
    "/api/v1/commercial/billing-accounts/{account_id}/provider-mapping",
    response_model=BillingAccountRead,
    tags=["commercial"],
)
def update_billing_customer_mapping(
    account_id: str,
    payload: BillingCustomerMappingUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> BillingAccountRead:
    _require_human_commercial(principal, "commercial:write")
    try:
        item = BillingOperationsService(session, principal).set_customer_mapping(
            account_id,
            external_customer_reference=payload.external_customer_reference,
            reason=payload.reason,
            request_id=request.state.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BillingAccountRead.model_validate(item)


@router.get(
    "/api/v1/commercial/billing-deliveries",
    response_model=list[BillingDeliveryRead],
    tags=["commercial"],
)
def list_billing_deliveries(
    principal: PrincipalDep,
    session: SessionDep,
    delivery_state: Literal["all", "pending", "processing", "retry", "succeeded", "dead"] = "all",
    limit: int = Query(default=200, ge=1, le=500),
) -> list[BillingDeliveryRead]:
    _require_human_commercial(principal, "commercial:read")
    items = BillingOperationsService(session, principal).list_deliveries(
        state=delivery_state,
        limit=limit,
    )
    return [BillingDeliveryRead.model_validate(item) for item in items]


@router.post(
    "/api/v1/commercial/billing-deliveries/{delivery_id}/replay",
    response_model=BillingDeliveryRead,
    tags=["commercial"],
)
def replay_billing_delivery(
    delivery_id: str,
    payload: BillingDeliveryReplayRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> BillingDeliveryRead:
    _require_human_commercial(principal, "commercial:write")
    try:
        item = BillingOperationsService(session, principal).replay_delivery(
            delivery_id,
            reason=payload.reason,
            request_id=request.state.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BillingDeliveryRead.model_validate(item)


@router.get(
    "/api/v1/commercial/billing-disputes",
    response_model=list[BillingDisputeRead],
    tags=["commercial"],
)
def list_billing_disputes(
    principal: PrincipalDep,
    session: SessionDep,
    dispute_status: Literal["all", "open", "investigating", "resolved", "rejected", "cancelled"] = "all",
    limit: int = Query(default=200, ge=1, le=500),
) -> list[BillingDisputeRead]:
    _require_human_commercial(principal, "commercial:read")
    service = BillingDisputeService(
        session,
        principal,
        sla_hours=runtime.get_settings().billing_dispute_sla_hours,
    )
    return [BillingDisputeRead.model_validate(item) for item in service.list(status=dispute_status, limit=limit)]


@router.post(
    "/api/v1/commercial/billing-disputes",
    response_model=BillingDisputeRead,
    status_code=status.HTTP_201_CREATED,
    tags=["commercial"],
)
def create_billing_dispute(
    payload: BillingDisputeCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> BillingDisputeRead:
    _require_human_commercial(principal, "commercial:write")
    try:
        item = BillingDisputeService(
            session,
            principal,
            sla_hours=runtime.get_settings().billing_dispute_sla_hours,
        ).create(
            CreateBillingDisputeCommand(
                dispute_key=payload.dispute_key,
                statement_id=payload.statement_id,
                invoice_reference_id=payload.invoice_reference_id,
                category=payload.category,
                disputed_units=payload.disputed_units,
                subject=payload.subject,
                description=payload.description,
            ),
            request_id=request.state.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BillingDisputeRead.model_validate(item)


@router.post(
    "/api/v1/commercial/billing-disputes/{dispute_id}/transition",
    response_model=BillingDisputeRead,
    tags=["commercial"],
)
def transition_billing_dispute(
    dispute_id: str,
    payload: BillingDisputeTransition,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> BillingDisputeRead:
    _require_human_commercial(principal, "commercial:write")
    try:
        item = BillingDisputeService(
            session,
            principal,
            sla_hours=runtime.get_settings().billing_dispute_sla_hours,
        ).transition(
            dispute_id,
            TransitionBillingDisputeCommand(
                operation_key=payload.operation_key,
                expected_version=payload.expected_version,
                action=payload.action,
                notes=payload.notes,
                assigned_to=payload.assigned_to,
                adjustment_key=payload.adjustment_key,
                credit_units=payload.credit_units,
            ),
            request_id=request.state.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BillingDisputeRead.model_validate(item)
