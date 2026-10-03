from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from pharma_intel.http.commercial_policy import _commercial_service
from pharma_intel.http.public_read_policy import _assert_public_entity_ids_visible
from pharma_intel.schemas import AgentPageResult, SortCriterionRead
from pharma_intel.security import Principal


def _agent_page[PageRecord](
    principal: Principal,
    session: Session,
    reservation_id: str,
    *,
    billing_class: str,
    arguments: dict[str, object],
    page_size: int,
    fetch: Callable[[int, int], list[PageRecord]],
    visible_entity_ids: list[str | None] | None = None,
    visible_filter_entity_ids: list[str | None] | None = None,
    required_compute_units: str = "0",
    sort: list[SortCriterionRead] | None = None,
) -> AgentPageResult[PageRecord]:
    if visible_entity_ids is not None:
        _assert_public_entity_ids_visible(session, principal, visible_entity_ids)
    if visible_filter_entity_ids is not None:
        _assert_public_entity_ids_visible(
            session,
            principal,
            visible_filter_entity_ids,
            reject_missing=False,
        )
    service = _commercial_service(session, principal)
    reservation = service.authorize_paginated_query(
        reservation_id,
        billing_class=billing_class,
        request_arguments=arguments,
        page_size=page_size,
        required_compute_units=required_compute_units,
    )
    rows = fetch(reservation.page_offset, page_size + 1)
    items = rows[:page_size]
    next_offset = reservation.page_offset + len(items)
    next_cursor = service.issue_next_cursor(
        reservation,
        next_offset=next_offset,
        has_more=len(rows) > page_size,
    )
    return AgentPageResult(
        items=items,
        limit=page_size,
        page_depth=reservation.page_depth,
        next_cursor=next_cursor,
        sort=sort or [],
    )
