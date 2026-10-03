from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from pharma_intel.commercial.accounting import BillingStatementCommand, ReversalCommand, UsageAdjustmentCommand
from pharma_intel.commercial.query import commercial_overview
from pharma_intel.http.commercial_policy import _commercial_accounting_service, _require_human_commercial
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.models import BillingAdjustment, BillingPeriodStatement, CommercialReconciliationRun
from pharma_intel.schemas import (
    BillingStatementCreate,
    BillingStatementRead,
    CommercialAdjustmentRead,
    CommercialExpirationRead,
    CommercialExpirationRequest,
    CommercialOverviewRead,
    CommercialReconciliationCreate,
    CommercialReconciliationRead,
    CommercialReversalCreate,
    CommercialUsageAdjustmentCreate,
)

router = APIRouter()


def _adjustment_read(adjustment: BillingAdjustment) -> CommercialAdjustmentRead:
    return CommercialAdjustmentRead(
        id=adjustment.id,
        subscription_id=adjustment.subscription_id,
        adjustment_key=adjustment.adjustment_key,
        adjustment_kind=adjustment.adjustment_kind,
        reverses_adjustment_id=adjustment.reverses_adjustment_id,
        reverses_settlement_id=adjustment.reverses_settlement_id,
        units_delta=format(adjustment.units_delta, "f"),
        reason=adjustment.reason,
        request_id=adjustment.request_id,
        created_by=adjustment.created_by,
        created_at=adjustment.created_at,
    )


def _reconciliation_read(run: CommercialReconciliationRun) -> CommercialReconciliationRead:
    return CommercialReconciliationRead(
        id=run.id,
        subscription_id=run.subscription_id,
        run_key=run.run_key,
        status=run.status,
        issue_count=run.issue_count,
        snapshot_granted_units=format(run.snapshot_granted_units, "f"),
        snapshot_reserved_units=format(run.snapshot_reserved_units, "f"),
        snapshot_consumed_units=format(run.snapshot_consumed_units, "f"),
        ledger_granted_units=format(run.ledger_granted_units, "f"),
        ledger_reserved_units=format(run.ledger_reserved_units, "f"),
        ledger_consumed_units=format(run.ledger_consumed_units, "f"),
        source_granted_units=format(run.source_granted_units, "f"),
        source_reserved_units=format(run.source_reserved_units, "f"),
        source_consumed_units=format(run.source_consumed_units, "f"),
        issues=run.issues_json,
        requested_by=run.requested_by,
        request_id=run.request_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _statement_read(statement: BillingPeriodStatement) -> BillingStatementRead:
    return BillingStatementRead(
        id=statement.id,
        subscription_id=statement.subscription_id,
        billing_account_id=statement.billing_account_id,
        statement_key=statement.statement_key,
        revision=statement.revision,
        period_start=statement.period_start,
        period_end=statement.period_end,
        settlement_units=format(statement.settlement_units, "f"),
        adjustment_units=format(statement.adjustment_units, "f"),
        net_consumed_units=format(statement.net_consumed_units, "f"),
        settlement_count=statement.settlement_count,
        adjustment_count=statement.adjustment_count,
        result_count=statement.result_count,
        response_bytes=statement.response_bytes,
        manifest_sha256=statement.manifest_sha256,
        signature_key_id=statement.signature_key_id,
        manifest_signature=statement.manifest_signature,
        payload=statement.payload_json,
        generated_by=statement.generated_by,
        request_id=statement.request_id,
        generated_at=statement.generated_at,
    )


@router.get(
    "/api/v1/commercial/overview",
    response_model=CommercialOverviewRead,
    tags=["commercial"],
)
def read_commercial_overview(principal: PrincipalDep, session: SessionDep) -> CommercialOverviewRead:
    _require_human_commercial(principal, "commercial:read")
    return CommercialOverviewRead.model_validate(commercial_overview(session, principal.tenant_id))


@router.post(
    "/api/v1/commercial/adjustments",
    response_model=CommercialAdjustmentRead,
    tags=["commercial"],
)
def create_commercial_adjustment(
    payload: CommercialUsageAdjustmentCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialAdjustmentRead:
    try:
        adjustment = _commercial_accounting_service(session, principal).adjust_usage(
            UsageAdjustmentCommand(
                subscription_key=payload.subscription_key,
                adjustment_key=payload.adjustment_key,
                units_delta=payload.units_delta,
                reason=payload.reason,
                request_id=request.state.request_id,
                metadata=payload.metadata,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _adjustment_read(adjustment)


@router.post(
    "/api/v1/commercial/settlements/{settlement_id}/reversal",
    response_model=CommercialAdjustmentRead,
    tags=["commercial"],
)
def reverse_commercial_settlement(
    settlement_id: str,
    payload: CommercialReversalCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialAdjustmentRead:
    try:
        adjustment = _commercial_accounting_service(session, principal).reverse_settlement(
            settlement_id,
            ReversalCommand(payload.adjustment_key, payload.reason, request.state.request_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _adjustment_read(adjustment)


@router.post(
    "/api/v1/commercial/adjustments/{adjustment_id}/reversal",
    response_model=CommercialAdjustmentRead,
    tags=["commercial"],
)
def reverse_commercial_adjustment(
    adjustment_id: str,
    payload: CommercialReversalCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialAdjustmentRead:
    try:
        adjustment = _commercial_accounting_service(session, principal).reverse_adjustment(
            adjustment_id,
            ReversalCommand(payload.adjustment_key, payload.reason, request.state.request_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _adjustment_read(adjustment)


@router.post(
    "/api/v1/commercial/reservations/expire",
    response_model=CommercialExpirationRead,
    tags=["commercial"],
)
def expire_commercial_reservations(
    payload: CommercialExpirationRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialExpirationRead:
    outcome = _commercial_accounting_service(session, principal).expire_stale_reservations(
        request_id=request.state.request_id,
        limit=payload.limit,
    )
    return CommercialExpirationRead(
        expired_reservations=outcome.expired_reservations,
        released_units=format(outcome.released_units, "f"),
        completed_at=outcome.completed_at,
    )


@router.post(
    "/api/v1/commercial/reconciliations",
    response_model=CommercialReconciliationRead,
    tags=["commercial"],
)
def reconcile_commercial_subscription(
    payload: CommercialReconciliationCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> CommercialReconciliationRead:
    try:
        run = _commercial_accounting_service(session, principal).reconcile(
            payload.subscription_key,
            run_key=payload.run_key,
            request_id=request.state.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _reconciliation_read(run)


@router.post(
    "/api/v1/commercial/statements",
    response_model=BillingStatementRead,
    tags=["commercial"],
)
def create_billing_statement(
    payload: BillingStatementCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> BillingStatementRead:
    try:
        statement = _commercial_accounting_service(session, principal).create_statement(
            BillingStatementCommand(
                subscription_key=payload.subscription_key,
                statement_key=payload.statement_key,
                period_start=payload.period_start,
                period_end=payload.period_end,
                revision=payload.revision,
                request_id=request.state.request_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _statement_read(statement)


@router.get(
    "/api/v1/commercial/statements/{statement_id}",
    response_model=BillingStatementRead,
    tags=["commercial"],
)
def read_billing_statement(
    statement_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> BillingStatementRead:
    _require_human_commercial(principal, "commercial:read")
    statement = session.scalar(
        select(BillingPeriodStatement).where(
            BillingPeriodStatement.tenant_id == principal.tenant_id,
            BillingPeriodStatement.id == statement_id,
        )
    )
    if statement is None:
        raise HTTPException(status_code=404, detail="Billing statement not found")
    return _statement_read(statement)
