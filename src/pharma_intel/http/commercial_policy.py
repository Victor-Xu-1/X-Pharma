from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from pharma_intel.commercial.accounting import CommercialAccountingService
from pharma_intel.commercial.billing import BillingStatementSigner
from pharma_intel.commercial.cursor import SignedCursorCodec
from pharma_intel.commercial.service import CommercialNotConfigured, CommercialUsageService
from pharma_intel.http import runtime
from pharma_intel.models import Tenant
from pharma_intel.security import Principal


def _commercial_service(session: Session, principal: Principal) -> CommercialUsageService:
    principal.require(runtime.get_settings().mcp_required_scope)
    settings = runtime.get_settings()
    if not settings.mcp_commercial_enforcement_enabled:
        raise CommercialNotConfigured("Commercial MCP data access is disabled")
    return CommercialUsageService(
        session,
        principal,
        reservation_lease_seconds=settings.mcp_reservation_lease_seconds,
        max_result_bytes=settings.mcp_max_durable_result_bytes,
        max_billable_units_per_call=settings.mcp_max_billable_units_per_call,
        max_active_reservations_per_client=settings.mcp_max_active_reservations_per_client,
        cursor_codec=SignedCursorCodec(
            settings.effective_mcp_cursor_signing_secret,
            ttl_seconds=settings.mcp_cursor_ttl_seconds,
            max_token_chars=settings.mcp_cursor_max_token_chars,
        ),
    )


def _require_human_commercial(principal: Principal, scope: str) -> None:
    if principal.actor_type != "user":
        raise HTTPException(status_code=403, detail="Human workspace account required")
    principal.require(scope)


def _commercial_accounting_service(session: Session, principal: Principal) -> CommercialAccountingService:
    _require_human_commercial(principal, "commercial:write")
    tenant = session.get(Tenant, principal.tenant_id)
    if tenant is None or not tenant.active:
        raise HTTPException(status_code=403, detail="Active tenant required")
    settings = runtime.get_settings()
    return CommercialAccountingService(
        session,
        tenant,
        actor_id=principal.actor_id,
        statement_signer=BillingStatementSigner(
            settings.effective_billing_statement_signing_secret,
            key_id=settings.billing_statement_signing_key_id,
        ),
    )
