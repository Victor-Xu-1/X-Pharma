from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from pharma_intel.db import set_tenant_context
from pharma_intel.models import KnowledgePage, KnowledgePageStatus
from pharma_intel.schemas.knowledge import PublicKnowledgePageSearchResult, PublicKnowledgePageSummary
from pharma_intel.sorting import SortDirection


def published_knowledge_statement(
    tenant_id: str,
    *,
    query: str | None = None,
    page_type: str | None = None,
    sort_by: Literal["title", "updated_at"] = "title",
    sort_direction: SortDirection = "asc",
) -> Select[tuple[KnowledgePage]]:
    statement = select(KnowledgePage).where(
        KnowledgePage.tenant_id == tenant_id,
        KnowledgePage.status == KnowledgePageStatus.PUBLISHED,
        KnowledgePage.current_version_id.is_not(None),
    )
    if query and query.strip():
        statement = statement.where(func.lower(KnowledgePage.title).contains(query.strip().casefold(), autoescape=True))
    if page_type:
        statement = statement.where(KnowledgePage.page_type == page_type)
    column = KnowledgePage.title if sort_by == "title" else KnowledgePage.updated_at
    order = column.asc() if sort_direction == "asc" else column.desc()
    return statement.order_by(order, KnowledgePage.id.asc())


def search_published_knowledge(
    session: Session,
    tenant_id: str,
    *,
    query: str | None = None,
    page_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: Literal["title", "updated_at"] = "title",
    sort_direction: SortDirection = "asc",
) -> PublicKnowledgePageSearchResult:
    """One tenant-scoped published-page query for paged and legacy transports."""
    if not 1 <= limit <= 1000 or not 0 <= offset <= 1_000_000:
        raise ValueError("Knowledge pagination is outside the supported bounds")
    set_tenant_context(session, tenant_id)
    statement = published_knowledge_statement(
        tenant_id,
        query=query,
        page_type=page_type,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )
    matching = statement.order_by(None).subquery()
    total = int(session.scalar(select(func.count()).select_from(matching)) or 0)
    # Keep alternatives available while filtering this dimension. Query/tenant/publication
    # scope still comes from the single authority; total and rows apply page_type.
    facet_scope = published_knowledge_statement(tenant_id, query=query).order_by(None).subquery()
    facet_rows = session.execute(select(facet_scope.c.page_type, func.count()).group_by(facet_scope.c.page_type))
    pages = session.scalars(statement.limit(limit).offset(offset))
    return PublicKnowledgePageSearchResult(
        items=[PublicKnowledgePageSummary.model_validate(page) for page in pages],
        total=total,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_direction=sort_direction,
        facets={"page_type": {str(kind): int(count) for kind, count in facet_rows}},
        as_of=datetime.now(UTC),
    )
