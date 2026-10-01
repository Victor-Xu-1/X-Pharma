from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from pharma_intel.accounts.access import organization_administrator
from pharma_intel.enterprise.admin import (
    AuditCursorCodec,
    EnterpriseAdminService,
)
from pharma_intel.http import runtime
from pharma_intel.security import (
    Principal,
)


def _enterprise_service(request: Request, session: Session, principal: Principal) -> EnterpriseAdminService:
    if principal.actor_type != "user" or principal.user_id is None:
        raise HTTPException(status_code=403, detail="Human workspace account required")
    principal.require("enterprise:admin")
    if organization_administrator(session, principal.tenant_id, principal.user_id) is None:
        raise HTTPException(status_code=403, detail="An active organization administrator is required")
    settings = runtime.get_settings()
    return EnterpriseAdminService(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request.state.request_id,
        cursor_codec=AuditCursorCodec(settings.jwt_secret),
    )
