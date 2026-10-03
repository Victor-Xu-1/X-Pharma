from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.knowledge.public import public_knowledge_markdown
from pharma_intel.knowledge.read_model import KnowledgePageNotFound, KnowledgeReadService, KnowledgeVersionNotFound
from pharma_intel.models import KnowledgePage, KnowledgePageStatus, KnowledgePageVersion
from pharma_intel.schemas import (
    PublicKnowledgePageCoverageRead,
    PublicKnowledgePageDetail,
    PublicKnowledgePageSummary,
    PublicKnowledgeVersionDiffRead,
    PublicKnowledgeVersionSummaryRead,
)
from pharma_intel.security import Principal

router = APIRouter()


def _public_knowledge_page_or_404(session: Session, principal: Principal, page_id: str) -> KnowledgePage:
    page = session.scalar(
        select(KnowledgePage).where(
            KnowledgePage.id == page_id,
            KnowledgePage.tenant_id == principal.tenant_id,
            KnowledgePage.status == KnowledgePageStatus.PUBLISHED,
            KnowledgePage.current_version_id.is_not(None),
        )
    )
    if page is None:
        raise HTTPException(status_code=404, detail="Knowledge page not found")
    return page


@router.get("/api/v1/knowledge/pages", response_model=list[PublicKnowledgePageSummary], tags=["knowledge"])
def list_knowledge_pages(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    page_type: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[PublicKnowledgePageSummary]:
    principal.require("knowledge:read")
    statement = select(KnowledgePage).where(
        KnowledgePage.tenant_id == principal.tenant_id,
        KnowledgePage.status == KnowledgePageStatus.PUBLISHED,
        KnowledgePage.current_version_id.is_not(None),
    )
    if q:
        statement = statement.where(KnowledgePage.title.ilike(f"%{q}%"))
    if page_type:
        statement = statement.where(KnowledgePage.page_type == page_type)
    pages = session.scalars(statement.order_by(KnowledgePage.title).limit(limit))
    return [PublicKnowledgePageSummary.model_validate(page) for page in pages]


@router.get("/api/v1/knowledge/pages/{page_id}", response_model=PublicKnowledgePageDetail, tags=["knowledge"])
def get_knowledge_page(page_id: str, principal: PrincipalDep, session: SessionDep) -> PublicKnowledgePageDetail:
    principal.require("knowledge:read")
    page = _public_knowledge_page_or_404(session, principal, page_id)
    version = session.scalar(
        select(KnowledgePageVersion).where(
            KnowledgePageVersion.id == page.current_version_id,
            KnowledgePageVersion.tenant_id == principal.tenant_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=409, detail="Knowledge page current version is unavailable")
    return PublicKnowledgePageDetail(
        **PublicKnowledgePageSummary.model_validate(page).model_dump(),
        version_number=version.version_number,
        rendered_markdown=public_knowledge_markdown(version.rendered_markdown),
        source_snapshot_at=version.source_snapshot_at,
    )


@router.get(
    "/api/v1/knowledge/pages/{page_id}/coverage",
    response_model=PublicKnowledgePageCoverageRead,
    tags=["knowledge"],
)
def get_knowledge_page_coverage(
    page_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> PublicKnowledgePageCoverageRead:
    principal.require("knowledge:read")
    _public_knowledge_page_or_404(session, principal, page_id)
    service = KnowledgeReadService(session, principal.tenant_id)
    try:
        coverage = service.coverage(page_id)
        return PublicKnowledgePageCoverageRead.model_validate(coverage.model_dump())
    except KnowledgePageNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KnowledgeVersionNotFound as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/api/v1/knowledge/pages/{page_id}/versions",
    response_model=list[PublicKnowledgeVersionSummaryRead],
    tags=["knowledge"],
)
def list_knowledge_page_versions(
    page_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PublicKnowledgeVersionSummaryRead]:
    principal.require("knowledge:read")
    _public_knowledge_page_or_404(session, principal, page_id)
    try:
        history = KnowledgeReadService(session, principal.tenant_id).version_history(page_id, limit)
        return [PublicKnowledgeVersionSummaryRead.model_validate(item.model_dump()) for item in history]
    except KnowledgePageNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/api/v1/knowledge/pages/{page_id}/versions/{version_number}/diff",
    response_model=PublicKnowledgeVersionDiffRead,
    tags=["knowledge"],
)
def get_knowledge_page_version_diff(
    page_id: str,
    version_number: int,
    principal: PrincipalDep,
    session: SessionDep,
    compare_to: int | None = Query(default=None, ge=1),
) -> PublicKnowledgeVersionDiffRead:
    principal.require("knowledge:read")
    if version_number < 1:
        raise HTTPException(status_code=422, detail="version_number must be at least 1")
    _public_knowledge_page_or_404(session, principal, page_id)
    try:
        diff = KnowledgeReadService(session, principal.tenant_id).version_diff(
            page_id,
            version_number,
            compare_to,
        )
        return PublicKnowledgeVersionDiffRead.model_validate(diff.model_dump())
    except (KnowledgePageNotFound, KnowledgeVersionNotFound) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
