from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_intel.models import (
    Entity,
    MonitoringAlert,
    MonitoringAlertReceipt,
    MonitoringTopic,
    SavedSearch,
    SavedSearchVersion,
    SavedSearchVisibility,
)
from pharma_intel.schemas import EntitySearchQuery, SavedSearchCreate, SavedSearchQuery, SavedSearchUpdate


def _entity_search_query_payload(query: EntitySearchQuery) -> dict[str, object]:
    payload: dict[str, object] = query.model_dump(mode="json", exclude_none=True)
    if not query.entity_types:
        payload.pop("entity_types", None)
    return payload


def _saved_search_query_payload(query: SavedSearchQuery) -> dict[str, object]:
    if isinstance(query, EntitySearchQuery):
        return _entity_search_query_payload(query)
    return query.model_dump(mode="json", exclude_none=True)


class MonitoringError(Exception):
    pass


class MonitoringNotFound(MonitoringError):
    pass


class MonitoringConflict(MonitoringError):
    pass


class MonitoringService:
    def __init__(self, session: Session, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    def list_saved_searches(self) -> list[SavedSearch]:
        return list(
            self.session.scalars(
                select(SavedSearch)
                .where(
                    SavedSearch.tenant_id == self.tenant_id,
                    or_(
                        SavedSearch.owner_user_id == self.user_id,
                        SavedSearch.visibility == SavedSearchVisibility.TENANT,
                    ),
                )
                .order_by(SavedSearch.updated_at.desc(), SavedSearch.id)
            )
        )

    def get_saved_search(self, saved_search_id: str) -> SavedSearch:
        return self._visible_saved_search(saved_search_id)

    def create_saved_search(self, command: SavedSearchCreate) -> SavedSearch:
        item = SavedSearch(
            tenant_id=self.tenant_id,
            owner_user_id=self.user_id,
            name=command.name.strip(),
            description=command.description.strip(),
            query_type=command.query_type,
            query_version=1,
            query_json=_saved_search_query_payload(command.query),
            visibility=command.visibility,
        )
        self.session.add(item)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise MonitoringConflict("A saved search with this name already exists") from exc
        self.session.add(
            SavedSearchVersion(
                tenant_id=self.tenant_id,
                saved_search_id=item.id,
                version=item.query_version,
                query_type=item.query_type,
                query_json=item.query_json,
                changed_by_user_id=self.user_id,
            )
        )
        self._commit_unique("A saved search with this name already exists")
        self.session.refresh(item)
        return item

    def update_saved_search(self, saved_search_id: str, command: SavedSearchUpdate) -> SavedSearch:
        item = self._owned_saved_search(saved_search_id)
        if command.name is not None:
            item.name = command.name.strip()
        if command.description is not None:
            item.description = command.description.strip()
        if command.query is not None:
            requested_type = command.query_type or "entity_search"
            if requested_type != item.query_type:
                raise MonitoringConflict("Saved search query type cannot change")
            item.query_json = _saved_search_query_payload(command.query)
            item.query_version += 1
            self.session.add(
                SavedSearchVersion(
                    tenant_id=self.tenant_id,
                    saved_search_id=item.id,
                    version=item.query_version,
                    query_type=item.query_type,
                    query_json=item.query_json,
                    changed_by_user_id=self.user_id,
                )
            )
        if command.visibility is not None:
            item.visibility = command.visibility
            if command.visibility == SavedSearchVisibility.PRIVATE:
                self.session.execute(
                    update(MonitoringTopic)
                    .where(
                        MonitoringTopic.tenant_id == self.tenant_id,
                        MonitoringTopic.saved_search_id == item.id,
                        MonitoringTopic.owner_user_id != self.user_id,
                        MonitoringTopic.active.is_(True),
                    )
                    .values(active=False, updated_at=datetime.now(UTC))
                )
        self._commit_unique("A saved search with this name already exists")
        self.session.refresh(item)
        return item

    def list_topics(self) -> list[MonitoringTopic]:
        return list(
            self.session.scalars(
                select(MonitoringTopic)
                .where(MonitoringTopic.tenant_id == self.tenant_id, MonitoringTopic.owner_user_id == self.user_id)
                .order_by(MonitoringTopic.updated_at.desc(), MonitoringTopic.id)
            )
        )

    def create_topic(self, name: str, saved_search_id: str) -> MonitoringTopic:
        saved_search = self._visible_saved_search(saved_search_id)
        if saved_search.query_type == "chemistry_search":
            raise MonitoringConflict("Chemistry saved searches do not support change monitoring yet")
        topic = MonitoringTopic(
            tenant_id=self.tenant_id,
            owner_user_id=self.user_id,
            saved_search_id=saved_search_id,
            query_version=saved_search.query_version,
            name=name.strip(),
            active=True,
        )
        self.session.add(topic)
        self._commit_unique("A monitoring topic with this name already exists")
        self.session.refresh(topic)
        return topic

    def update_topic(
        self,
        topic_id: str,
        *,
        name: str | None,
        active: bool | None,
        query_version: int | None,
    ) -> MonitoringTopic:
        topic = self._owned_topic(topic_id)
        if name is not None:
            topic.name = name.strip()
        if active is not None:
            if active:
                saved_search = self._visible_saved_search(topic.saved_search_id)
                if saved_search.query_type == "chemistry_search":
                    raise MonitoringConflict("Chemistry saved searches do not support change monitoring yet")
            topic.active = active
        if query_version is not None:
            self._visible_saved_search_version(topic.saved_search_id, query_version)
            topic.query_version = query_version
        self._commit_unique("A monitoring topic with this name already exists")
        self.session.refresh(topic)
        return topic

    def list_alerts(self, *, unread_only: bool, limit: int) -> list[dict[str, object]]:
        receipt_match = and_(
            MonitoringAlertReceipt.alert_id == MonitoringAlert.id,
            MonitoringAlertReceipt.user_id == self.user_id,
            MonitoringAlertReceipt.tenant_id == self.tenant_id,
        )
        statement = (
            select(MonitoringAlert, MonitoringTopic.name, Entity.name, MonitoringAlertReceipt.read_at)
            .join(MonitoringTopic, MonitoringTopic.id == MonitoringAlert.topic_id)
            .join(Entity, Entity.id == MonitoringAlert.entity_id)
            .outerjoin(MonitoringAlertReceipt, receipt_match)
            .where(
                MonitoringAlert.tenant_id == self.tenant_id,
                MonitoringAlert.recipient_user_id == self.user_id,
            )
            .order_by(MonitoringAlert.occurred_at.desc(), MonitoringAlert.id.desc())
            .limit(limit)
        )
        if unread_only:
            statement = statement.where(MonitoringAlertReceipt.id.is_(None))
        return [
            {
                "id": alert.id,
                "topic_id": alert.topic_id,
                "topic_name": topic_name,
                "entity_id": alert.entity_id,
                "entity_name": entity_name,
                "event_type": alert.event_type,
                "title": alert.title,
                "summary": alert.summary,
                "payload_json": alert.payload_json,
                "occurred_at": alert.occurred_at,
                "read_at": read_at,
            }
            for alert, topic_name, entity_name, read_at in self.session.execute(statement)
        ]

    def mark_alert_read(self, alert_id: str) -> datetime:
        alert = self.session.scalar(
            select(MonitoringAlert).where(
                MonitoringAlert.id == alert_id,
                MonitoringAlert.tenant_id == self.tenant_id,
                MonitoringAlert.recipient_user_id == self.user_id,
            )
        )
        if alert is None:
            raise MonitoringNotFound("Monitoring alert not found")
        receipt = self.session.scalar(
            select(MonitoringAlertReceipt).where(
                MonitoringAlertReceipt.tenant_id == self.tenant_id,
                MonitoringAlertReceipt.alert_id == alert_id,
                MonitoringAlertReceipt.user_id == self.user_id,
            )
        )
        if receipt is None:
            receipt = MonitoringAlertReceipt(
                tenant_id=self.tenant_id,
                alert_id=alert_id,
                user_id=self.user_id,
                read_at=datetime.now(UTC),
            )
            self.session.add(receipt)
            try:
                self.session.commit()
            except IntegrityError:
                self.session.rollback()
                receipt = self.session.scalar(
                    select(MonitoringAlertReceipt).where(
                        MonitoringAlertReceipt.tenant_id == self.tenant_id,
                        MonitoringAlertReceipt.alert_id == alert_id,
                        MonitoringAlertReceipt.user_id == self.user_id,
                    )
                )
                if receipt is None:
                    raise
        return receipt.read_at

    def _visible_saved_search(self, item_id: str) -> SavedSearch:
        item = self.session.scalar(
            select(SavedSearch).where(
                SavedSearch.id == item_id,
                SavedSearch.tenant_id == self.tenant_id,
                or_(
                    SavedSearch.owner_user_id == self.user_id,
                    SavedSearch.visibility == SavedSearchVisibility.TENANT,
                ),
            )
        )
        if item is None:
            raise MonitoringNotFound("Saved search not found")
        return item

    def _owned_saved_search(self, item_id: str) -> SavedSearch:
        item = self.session.scalar(
            select(SavedSearch).where(
                SavedSearch.id == item_id,
                SavedSearch.tenant_id == self.tenant_id,
                SavedSearch.owner_user_id == self.user_id,
            )
        )
        if item is None:
            raise MonitoringNotFound("Saved search not found")
        return item

    def _visible_saved_search_version(self, saved_search_id: str, version: int) -> SavedSearchVersion:
        self._visible_saved_search(saved_search_id)
        item = self.session.scalar(
            select(SavedSearchVersion).where(
                SavedSearchVersion.tenant_id == self.tenant_id,
                SavedSearchVersion.saved_search_id == saved_search_id,
                SavedSearchVersion.version == version,
            )
        )
        if item is None:
            raise MonitoringNotFound("Saved search version not found")
        return item

    def _owned_topic(self, item_id: str) -> MonitoringTopic:
        item = self.session.scalar(
            select(MonitoringTopic).where(
                MonitoringTopic.id == item_id,
                MonitoringTopic.tenant_id == self.tenant_id,
                MonitoringTopic.owner_user_id == self.user_id,
            )
        )
        if item is None:
            raise MonitoringNotFound("Monitoring topic not found")
        return item

    def _commit_unique(self, message: str) -> None:
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise MonitoringConflict(message) from exc
