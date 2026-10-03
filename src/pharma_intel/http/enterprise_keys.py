from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from pharma_intel.api_key_lifecycle import (
    API_KEY_MAX_TTL,
    API_KEY_MIN_TTL,
    MANAGED_API_KEY_SCOPES,
    ApiKeyLifecycleError,
    ApiKeyLifecycleNotFound,
    ApiKeyLifecycleService,
    ApiKeyView,
)
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.enterprise_access import _enterprise_service
from pharma_intel.http.response_policy import _prevent_secret_caching
from pharma_intel.models import (
    Tenant,
)
from pharma_intel.schemas import (
    EnterpriseApiKeyCatalogRead,
    EnterpriseApiKeyCreate,
    EnterpriseApiKeyRead,
    EnterpriseApiKeyRevoke,
    EnterpriseApiKeyRotate,
    EnterpriseApiKeySecretRead,
)
from pharma_intel.security import (
    Principal,
)

router = APIRouter()


def _api_key_service(request: Request, session: Session, principal: Principal) -> ApiKeyLifecycleService:
    _enterprise_service(request, session, principal)
    tenant = session.get(Tenant, principal.tenant_id)
    if tenant is None or not tenant.active:
        raise HTTPException(status_code=403, detail="Active tenant required")
    return ApiKeyLifecycleService(
        session,
        tenant,
        actor_id=principal.actor_id,
        actor_type="user",
    )


def _enterprise_api_key_read(view: ApiKeyView) -> EnterpriseApiKeyRead:
    key = view.key
    now = datetime.now(UTC)
    expires_at = key.expires_at
    comparable_expiry = (
        expires_at.replace(tzinfo=UTC)
        if expires_at is not None and (expires_at.tzinfo is None or expires_at.utcoffset() is None)
        else expires_at
    )
    if key.revoked_at is not None:
        key_status = "revoked"
    elif comparable_expiry is not None and comparable_expiry <= now:
        key_status = "expired"
    elif key.active:
        key_status = "active"
    else:
        key_status = "disabled"
    return EnterpriseApiKeyRead(
        id=key.id,
        name=key.name,
        prefix=key.prefix,
        scopes=list(key.scopes),
        active=key.active,
        status=key_status,
        last_used_at=key.last_used_at,
        expires_at=key.expires_at,
        revoked_at=key.revoked_at,
        commercial_client_id=view.commercial_client_id,
        commercial_client_name=view.commercial_client_name,
        created_at=key.created_at,
        updated_at=key.updated_at,
    )


def _api_key_http_error(session: Session, exc: ApiKeyLifecycleError) -> HTTPException:
    session.rollback()
    if isinstance(exc, ApiKeyLifecycleNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


@router.get(
    "/api/v1/enterprise/api-keys",
    response_model=EnterpriseApiKeyCatalogRead,
    tags=["enterprise"],
)
def list_enterprise_api_keys(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> EnterpriseApiKeyCatalogRead:
    service = _api_key_service(request, session, principal)
    return EnterpriseApiKeyCatalogRead(
        items=[_enterprise_api_key_read(view) for view in service.list_keys(limit=limit)],
        required_scope="mcp:connect",
        allowed_scopes=list(MANAGED_API_KEY_SCOPES),
        min_ttl_hours=int(API_KEY_MIN_TTL.total_seconds() // 3600),
        max_ttl_days=API_KEY_MAX_TTL.days,
    )


@router.post(
    "/api/v1/enterprise/api-keys",
    response_model=EnterpriseApiKeySecretRead,
    status_code=status.HTTP_201_CREATED,
    tags=["enterprise"],
)
def create_enterprise_api_key(
    payload: EnterpriseApiKeyCreate,
    request: Request,
    response: Response,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseApiKeySecretRead:
    service = _api_key_service(request, session, principal)
    try:
        issued = service.create(
            name=payload.name,
            scopes=payload.scopes,
            expires_at=payload.expires_at,
            reason=payload.reason,
            request_id=request.state.request_id,
        )
        session.commit()
    except ApiKeyLifecycleError as exc:
        raise _api_key_http_error(session, exc) from exc
    _prevent_secret_caching(response)
    item = _enterprise_api_key_read(ApiKeyView(issued.key, None, None))
    return EnterpriseApiKeySecretRead(**item.model_dump(), secret=issued.secret)


@router.post(
    "/api/v1/enterprise/api-keys/{key_id}/rotate",
    response_model=EnterpriseApiKeySecretRead,
    tags=["enterprise"],
)
def rotate_enterprise_api_key(
    key_id: str,
    payload: EnterpriseApiKeyRotate,
    request: Request,
    response: Response,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseApiKeySecretRead:
    service = _api_key_service(request, session, principal)
    try:
        rotation = service.rotate(
            key_id,
            new_name=payload.name,
            expires_at=payload.expires_at,
            reason=payload.reason,
            request_id=request.state.request_id,
        )
        session.commit()
        view = service.get(rotation.new_key_id)
    except ApiKeyLifecycleError as exc:
        raise _api_key_http_error(session, exc) from exc
    _prevent_secret_caching(response)
    item = _enterprise_api_key_read(view)
    return EnterpriseApiKeySecretRead(**item.model_dump(), secret=rotation.secret)


@router.post(
    "/api/v1/enterprise/api-keys/{key_id}/revoke",
    response_model=EnterpriseApiKeyRead,
    tags=["enterprise"],
)
def revoke_enterprise_api_key(
    key_id: str,
    payload: EnterpriseApiKeyRevoke,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseApiKeyRead:
    service = _api_key_service(request, session, principal)
    try:
        service.revoke(
            key_id,
            reason=payload.reason,
            request_id=request.state.request_id,
        )
        session.commit()
        view = service.get(key_id)
    except ApiKeyLifecycleError as exc:
        raise _api_key_http_error(session, exc) from exc
    return _enterprise_api_key_read(view)
