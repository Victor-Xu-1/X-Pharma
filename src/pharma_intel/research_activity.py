from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from pharma_intel.models import AuditEvent, Entity
from pharma_intel.repository import EntityRepository

RESEARCH_ENTITY_RESOURCE_TYPE = "research_entity"


@dataclass(frozen=True)
class RequestAuditResource:
    resource_type: str
    resource_id: str
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RecentEntityVisit:
    entity: Entity
    visited_at: datetime


class ResearchActivityService:
    def __init__(self, session: Session, tenant_id: str, user_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._user_id = user_id

    def list_recent_entities(self, limit: int) -> list[RecentEntityVisit]:
        latest_visit = (
            select(
                AuditEvent.resource_id.label("entity_id"),
                func.max(AuditEvent.occurred_at).label("visited_at"),
            )
            .where(
                AuditEvent.tenant_id == self._tenant_id,
                AuditEvent.actor_type == "user",
                AuditEvent.actor_id == self._user_id,
                AuditEvent.resource_type == RESEARCH_ENTITY_RESOURCE_TYPE,
                AuditEvent.resource_id.is_not(None),
                AuditEvent.outcome == "success",
            )
            .group_by(AuditEvent.resource_id)
            .subquery()
        )
        rows = self._session.execute(
            select(latest_visit.c.entity_id, latest_visit.c.visited_at)
            .join(
                Entity,
                and_(
                    Entity.id == latest_visit.c.entity_id,
                    Entity.tenant_id == self._tenant_id,
                ),
            )
            .order_by(latest_visit.c.visited_at.desc(), latest_visit.c.entity_id.asc())
            .limit(limit)
        ).all()
        entity_ids = [row.entity_id for row in rows]
        visited_at_by_id = {row.entity_id: row.visited_at for row in rows}

        entities = EntityRepository(self._session, self._tenant_id).get_many(entity_ids)
        return [RecentEntityVisit(entity=entity, visited_at=visited_at_by_id[entity.id]) for entity in entities[:limit]]
