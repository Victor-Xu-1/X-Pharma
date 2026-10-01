from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session


@dataclass(slots=True)
class QueryContext:
    """Request-scoped database, publication policy and bounded identity cache."""

    session: Session
    tenant_id: str
    include_unpublished: bool = True
    _placeholder_target_ids_cache: tuple[str, ...] | None = field(default=None, init=False)
