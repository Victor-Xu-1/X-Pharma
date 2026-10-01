from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import select

from pharma_intel.http.agent_page import _agent_page
from pharma_intel.http.commercial_policy import _commercial_service
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.models import KnowledgePage, KnowledgePageStatus, KnowledgePageVersion
from pharma_intel.schemas import AgentPageResult, KnowledgePageDetail, KnowledgePageSummary

router = APIRouter()


@router.get(
    "/internal/v1/domain/knowledge/pages",
    response_model=AgentPageResult[KnowledgePageSummary],
    tags=["internal-domain"],
)
def search_knowledge_pages_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    q: str | None = Query(default=None, max_length=500),
    page_type: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentPageResult[KnowledgePageSummary]:
    principal.require("knowledge:read")
    arguments: dict[str, object] = {"limit": limit}
    if q is not None:
        arguments["q"] = q
    if page_type is not None:
        arguments["page_type"] = page_type
    if cursor is not None:
        arguments["cursor"] = cursor

    def fetch(offset: int, fetch_limit: int) -> list[KnowledgePageSummary]:
        statement = select(KnowledgePage).where(
            KnowledgePage.tenant_id == principal.tenant_id,
            KnowledgePage.status == KnowledgePageStatus.PUBLISHED,
            KnowledgePage.current_version_id.is_not(None),
        )
        if q:
            statement = statement.where(KnowledgePage.title.ilike(f"%{q}%"))
        if page_type:
            statement = statement.where(KnowledgePage.page_type == page_type)
        pages = session.scalars(
            statement.order_by(KnowledgePage.title, KnowledgePage.id).limit(fetch_limit).offset(offset)
        )
        return [KnowledgePageSummary.model_validate(page) for page in pages]

    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="knowledge.search",
        arguments=arguments,
        page_size=limit,
        fetch=fetch,
    )


@router.get(
    "/internal/v1/domain/knowledge/pages/{page_id}",
    response_model=KnowledgePageDetail,
    tags=["internal-domain"],
)
def get_knowledge_page_for_agent(
    page_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
) -> KnowledgePageDetail:
    principal.require("knowledge:read")
    _commercial_service(session, principal).authorize_paginated_query(
        reservation_id,
        billing_class="knowledge.read",
        request_arguments={"page_id": page_id},
        page_size=1,
    )
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
    version = session.scalar(
        select(KnowledgePageVersion).where(
            KnowledgePageVersion.id == page.current_version_id,
            KnowledgePageVersion.tenant_id == principal.tenant_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=409, detail="Knowledge page current version is unavailable")
    return KnowledgePageDetail(
        **KnowledgePageSummary.model_validate(page).model_dump(),
        version_number=version.version_number,
        compiler_version=version.compiler_version,
        content_json=version.content_json,
        rendered_markdown=version.rendered_markdown,
        content_sha256=version.content_sha256,
        source_snapshot_at=version.source_snapshot_at,
    )
