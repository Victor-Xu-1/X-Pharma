from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

import pharma_intel.object_store as object_store_module
from pharma_intel.governance.publication import GovernancePublicationService, PublicationError
from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.schemas import (
    PublicationBatchCommitRequest,
    PublicationBatchItemRead,
    PublicationBatchPreviewRequest,
    PublicationBatchRead,
)

router = APIRouter()


def _publication_service(session: Session, tenant_id: str) -> GovernancePublicationService:
    settings = runtime.get_settings()
    return GovernancePublicationService(
        session,
        settings,
        object_store_module.build_object_store(settings),
        tenant_id,
    )


def _publication_batch_read(
    service: GovernancePublicationService,
    batch_id: str,
) -> PublicationBatchRead:
    batch = service.get(batch_id)
    return PublicationBatchRead(
        **PublicationBatchRead.model_validate(batch).model_dump(exclude={"items"}),
        items=[PublicationBatchItemRead.model_validate(item) for item in service.items(batch.id)],
    )


@router.get(
    "/api/v1/governance/publication-batches",
    response_model=list[PublicationBatchRead],
    tags=["governance"],
)
def list_publication_batches(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[PublicationBatchRead]:
    principal.require("governance:review")
    service = _publication_service(session, principal.tenant_id)
    return [
        PublicationBatchRead(
            **PublicationBatchRead.model_validate(batch).model_dump(exclude={"items"}),
            items=[],
        )
        for batch in service.list_batches(limit)
    ]


@router.get(
    "/api/v1/governance/publication-batches/{batch_id}",
    response_model=PublicationBatchRead,
    tags=["governance"],
)
def get_publication_batch(
    batch_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> PublicationBatchRead:
    principal.require("governance:review")
    try:
        return _publication_batch_read(_publication_service(session, principal.tenant_id), batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/api/v1/governance/publication-batches/preview",
    response_model=PublicationBatchRead,
    status_code=status.HTTP_201_CREATED,
    tags=["governance"],
)
def preview_publication_batch(
    payload: PublicationBatchPreviewRequest,
    principal: PrincipalDep,
    session: SessionDep,
) -> PublicationBatchRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    service = _publication_service(session, principal.tenant_id)
    try:
        batch = service.preview(
            operation=payload.operation,
            staged_fact_ids=payload.staged_fact_ids,
            idempotency_key=payload.idempotency_key,
            user_id=principal.user_id,
            reason=payload.reason,
        )
        return _publication_batch_read(service, batch.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PublicationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/api/v1/governance/publication-batches/{batch_id}/commit",
    response_model=PublicationBatchRead,
    tags=["governance"],
)
def commit_publication_batch(
    batch_id: str,
    payload: PublicationBatchCommitRequest,
    principal: PrincipalDep,
    session: SessionDep,
) -> PublicationBatchRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    service = _publication_service(session, principal.tenant_id)
    try:
        batch = service.commit(batch_id, payload.preview_sha256, principal.user_id)
        return _publication_batch_read(service, batch.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PublicationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
