from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session

from pharma_intel.enterprise.llm_providers import (
    CreateLLMProviderCommand,
    LLMProviderCatalogService,
    LLMProviderConflict,
    LLMProviderError,
    LLMProviderNotFound,
    UpdateLLMProviderCommand,
)
from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.enterprise_access import _enterprise_service
from pharma_intel.schemas import (
    EnterpriseLLMProviderCreate,
    EnterpriseLLMProviderPrimaryUpdate,
    EnterpriseLLMProviderRead,
    EnterpriseLLMProviderUpdate,
)
from pharma_intel.security import (
    Principal,
)

router = APIRouter()


def _llm_provider_service(request: Request, session: Session, principal: Principal) -> LLMProviderCatalogService:
    _enterprise_service(request, session, principal)
    assert principal.user_id is not None
    return LLMProviderCatalogService(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.user_id,
        request_id=request.state.request_id,
        settings=runtime.get_settings(),
    )


def _llm_provider_http_error(session: Session, exc: LLMProviderError) -> HTTPException:
    session.rollback()
    if isinstance(exc, LLMProviderNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, LLMProviderConflict):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=503, detail=str(exc))


@router.get(
    "/api/v1/enterprise/llm-providers",
    response_model=list[EnterpriseLLMProviderRead],
    tags=["enterprise"],
)
def list_enterprise_llm_providers(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[EnterpriseLLMProviderRead]:
    try:
        providers = _llm_provider_service(request, session, principal).list()
    except LLMProviderError as exc:
        raise _llm_provider_http_error(session, exc) from exc
    return [EnterpriseLLMProviderRead.model_validate(provider) for provider in providers]


@router.post(
    "/api/v1/enterprise/llm-providers",
    response_model=EnterpriseLLMProviderRead,
    status_code=status.HTTP_201_CREATED,
    tags=["enterprise"],
)
def create_enterprise_llm_provider(
    payload: EnterpriseLLMProviderCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseLLMProviderRead:
    try:
        provider = _llm_provider_service(request, session, principal).create(
            CreateLLMProviderCommand(**payload.model_dump())
        )
    except LLMProviderError as exc:
        raise _llm_provider_http_error(session, exc) from exc
    return EnterpriseLLMProviderRead.model_validate(provider)


@router.put(
    "/api/v1/enterprise/llm-providers/{provider_id}",
    response_model=EnterpriseLLMProviderRead,
    tags=["enterprise"],
)
def update_enterprise_llm_provider(
    provider_id: str,
    payload: EnterpriseLLMProviderUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseLLMProviderRead:
    try:
        provider = _llm_provider_service(request, session, principal).update(
            provider_id,
            UpdateLLMProviderCommand(**payload.model_dump()),
        )
    except LLMProviderError as exc:
        raise _llm_provider_http_error(session, exc) from exc
    return EnterpriseLLMProviderRead.model_validate(provider)


@router.post(
    "/api/v1/enterprise/llm-providers/{provider_id}/make-primary",
    response_model=list[EnterpriseLLMProviderRead],
    tags=["enterprise"],
)
def make_enterprise_llm_provider_primary(
    provider_id: str,
    payload: EnterpriseLLMProviderPrimaryUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[EnterpriseLLMProviderRead]:
    try:
        providers = _llm_provider_service(request, session, principal).make_primary(
            provider_id,
            payload.expected_version,
            payload.reason,
        )
    except LLMProviderError as exc:
        raise _llm_provider_http_error(session, exc) from exc
    return [EnterpriseLLMProviderRead.model_validate(provider) for provider in providers]


@router.post(
    "/api/v1/enterprise/llm-providers/{provider_id}/test",
    response_model=EnterpriseLLMProviderRead,
    tags=["enterprise"],
)
def test_enterprise_llm_provider(
    provider_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseLLMProviderRead:
    try:
        provider = _llm_provider_service(request, session, principal).test(provider_id)
    except LLMProviderError as exc:
        raise _llm_provider_http_error(session, exc) from exc
    return EnterpriseLLMProviderRead.model_validate(provider)
