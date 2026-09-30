from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_intel.models import (
    AuditEvent,
    ComparisonSet,
    ComparisonSetMember,
    ComparisonSetVersion,
    Entity,
    SavedSearchVisibility,
)
from pharma_intel.schemas import ComparisonSetCreate, ComparisonSetUpdate, EntityRead

MAX_COMPARISON_SET_MEMBERS = 20


class ComparisonSetError(Exception):
    pass


class ComparisonSetNotFound(ComparisonSetError):
    pass


class ComparisonSetConflict(ComparisonSetError):
    pass


class ComparisonSetLimitExceeded(ComparisonSetError):
    pass


@dataclass(frozen=True)
class ComparisonSetView:
    item: ComparisonSet
    member_count: int
    editable: bool
    members: list[dict[str, object]]


class ComparisonSetService:
    def __init__(self, session: Session, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    def list_sets(self) -> list[ComparisonSetView]:
        rows = self.session.execute(
            select(ComparisonSet, func.count(ComparisonSetMember.id))
            .outerjoin(ComparisonSetMember, ComparisonSetMember.comparison_set_id == ComparisonSet.id)
            .where(
                ComparisonSet.tenant_id == self.tenant_id,
                or_(
                    ComparisonSet.owner_user_id == self.user_id,
                    ComparisonSet.visibility == SavedSearchVisibility.TENANT,
                ),
            )
            .group_by(ComparisonSet.id)
            .order_by(ComparisonSet.updated_at.desc(), ComparisonSet.id)
            .limit(100)
        )
        return [
            ComparisonSetView(
                item=item,
                member_count=int(count),
                editable=item.owner_user_id == self.user_id,
                members=[],
            )
            for item, count in rows
        ]

    def get_set(self, item_id: str) -> ComparisonSetView:
        item = self._visible_set(item_id, lock=False)
        members = self._members(item.id)
        return ComparisonSetView(
            item=item,
            member_count=len(members),
            editable=item.owner_user_id == self.user_id,
            members=members,
        )

    def create_set(self, command: ComparisonSetCreate) -> ComparisonSetView:
        item = ComparisonSet(
            tenant_id=self.tenant_id,
            owner_user_id=self.user_id,
            name=command.name.strip(),
            description=command.description.strip(),
            visibility=command.visibility,
            version=1,
        )
        self.session.add(item)
        try:
            self.session.flush()
            self._append_version(item)
            self._audit(item.id, "comparison_set.create", {"version": item.version})
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ComparisonSetConflict("A comparison set with this name already exists") from exc
        self.session.refresh(item)
        return ComparisonSetView(item=item, member_count=0, editable=True, members=[])

    def update_set(self, item_id: str, command: ComparisonSetUpdate) -> ComparisonSetView:
        item = self._owned_set(item_id, lock=True)
        self._require_version(item, command.expected_version)
        if command.name is not None:
            item.name = command.name.strip()
        if command.description is not None:
            item.description = command.description.strip()
        if command.visibility is not None:
            item.visibility = command.visibility
        item.version += 1
        try:
            self.session.flush()
            self._append_version(item)
            self._audit(item.id, "comparison_set.update", {"version": item.version})
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ComparisonSetConflict("A comparison set with this name already exists") from exc
        self.session.refresh(item)
        return self.get_set(item.id)

    def add_member(self, item_id: str, entity_id: str, *, expected_version: int) -> ComparisonSetView:
        item = self._owned_set(item_id, lock=True)
        self._require_version(item, expected_version)
        entity = self.session.scalar(select(Entity).where(Entity.id == entity_id, Entity.tenant_id == self.tenant_id))
        if entity is None:
            raise ComparisonSetNotFound("Entity not found")
        existing = self.session.scalar(
            select(ComparisonSetMember.id).where(
                ComparisonSetMember.tenant_id == self.tenant_id,
                ComparisonSetMember.comparison_set_id == item.id,
                ComparisonSetMember.entity_id == entity_id,
            )
        )
        if existing is not None:
            raise ComparisonSetConflict("Entity is already in this comparison set")
        count = self.session.scalar(
            select(func.count())
            .select_from(ComparisonSetMember)
            .where(
                ComparisonSetMember.tenant_id == self.tenant_id,
                ComparisonSetMember.comparison_set_id == item.id,
            )
        )
        if int(count or 0) >= MAX_COMPARISON_SET_MEMBERS:
            raise ComparisonSetLimitExceeded(f"Comparison sets are limited to {MAX_COMPARISON_SET_MEMBERS} entities")
        next_position = self.session.scalar(
            select(func.coalesce(func.max(ComparisonSetMember.position), -1)).where(
                ComparisonSetMember.tenant_id == self.tenant_id,
                ComparisonSetMember.comparison_set_id == item.id,
            )
        )
        self.session.add(
            ComparisonSetMember(
                tenant_id=self.tenant_id,
                comparison_set_id=item.id,
                entity_id=entity_id,
                position=(-1 if next_position is None else int(next_position)) + 1,
                added_by_user_id=self.user_id,
            )
        )
        item.version += 1
        try:
            self.session.flush()
            self._append_version(item)
            self._audit(item.id, "comparison_set.member.add", {"entity_id": entity_id, "version": item.version})
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ComparisonSetConflict("Comparison set changed concurrently") from exc
        return self.get_set(item.id)

    def add_members(self, item_id: str, entity_ids: list[str], *, expected_version: int) -> ComparisonSetView:
        item = self._owned_set(item_id, lock=True)
        self._require_version(item, expected_version)
        existing_ids = set(
            self.session.scalars(
                select(ComparisonSetMember.entity_id).where(
                    ComparisonSetMember.tenant_id == self.tenant_id,
                    ComparisonSetMember.comparison_set_id == item.id,
                    ComparisonSetMember.entity_id.in_(entity_ids),
                )
            )
        )
        if existing_ids:
            raise ComparisonSetConflict("One or more entities are already in this comparison set")
        available_ids = set(
            self.session.scalars(select(Entity.id).where(Entity.tenant_id == self.tenant_id, Entity.id.in_(entity_ids)))
        )
        if available_ids != set(entity_ids):
            raise ComparisonSetNotFound("One or more entities were not found")
        count = int(
            self.session.scalar(
                select(func.count())
                .select_from(ComparisonSetMember)
                .where(
                    ComparisonSetMember.tenant_id == self.tenant_id,
                    ComparisonSetMember.comparison_set_id == item.id,
                )
            )
            or 0
        )
        if count + len(entity_ids) > MAX_COMPARISON_SET_MEMBERS:
            raise ComparisonSetLimitExceeded(f"Comparison sets are limited to {MAX_COMPARISON_SET_MEMBERS} entities")
        last_position = self.session.scalar(
            select(func.coalesce(func.max(ComparisonSetMember.position), -1)).where(
                ComparisonSetMember.tenant_id == self.tenant_id,
                ComparisonSetMember.comparison_set_id == item.id,
            )
        )
        next_position = (-1 if last_position is None else int(last_position)) + 1
        self.session.add_all(
            [
                ComparisonSetMember(
                    tenant_id=self.tenant_id,
                    comparison_set_id=item.id,
                    entity_id=entity_id,
                    position=next_position + index,
                    added_by_user_id=self.user_id,
                )
                for index, entity_id in enumerate(entity_ids)
            ]
        )
        item.version += 1
        try:
            self.session.flush()
            self._append_version(item)
            self._audit(
                item.id,
                "comparison_set.members.add",
                {"entity_ids": entity_ids, "member_count": len(entity_ids), "version": item.version},
            )
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ComparisonSetConflict("Comparison set changed concurrently") from exc
        return self.get_set(item.id)

    def remove_member(self, item_id: str, entity_id: str, *, expected_version: int) -> ComparisonSetView:
        item = self._owned_set(item_id, lock=True)
        self._require_version(item, expected_version)
        result = self.session.execute(
            delete(ComparisonSetMember).where(
                ComparisonSetMember.tenant_id == self.tenant_id,
                ComparisonSetMember.comparison_set_id == item.id,
                ComparisonSetMember.entity_id == entity_id,
            )
        )
        if result.rowcount != 1:
            self.session.rollback()
            raise ComparisonSetNotFound("Comparison set member not found")
        item.version += 1
        self.session.flush()
        self._append_version(item)
        self._audit(item.id, "comparison_set.member.remove", {"entity_id": entity_id, "version": item.version})
        self.session.commit()
        return self.get_set(item.id)

    def list_versions(self, item_id: str) -> list[ComparisonSetVersion]:
        item = self._visible_set(item_id, lock=False)
        return list(
            self.session.scalars(
                select(ComparisonSetVersion)
                .where(
                    ComparisonSetVersion.tenant_id == self.tenant_id,
                    ComparisonSetVersion.comparison_set_id == item.id,
                )
                .order_by(ComparisonSetVersion.version.desc())
            )
        )

    def _members(self, item_id: str) -> list[dict[str, object]]:
        rows = self.session.execute(
            select(ComparisonSetMember, Entity)
            .join(Entity, Entity.id == ComparisonSetMember.entity_id)
            .where(
                ComparisonSetMember.tenant_id == self.tenant_id,
                ComparisonSetMember.comparison_set_id == item_id,
                Entity.tenant_id == self.tenant_id,
            )
            .order_by(ComparisonSetMember.position, ComparisonSetMember.id)
        )
        return [
            {
                "id": member.id,
                "position": member.position,
                "added_by_user_id": member.added_by_user_id,
                "created_at": member.created_at,
                "entity": EntityRead.model_validate(entity).model_dump(mode="json"),
            }
            for member, entity in rows
        ]

    def _append_version(self, item: ComparisonSet) -> None:
        member_ids = list(
            self.session.scalars(
                select(ComparisonSetMember.entity_id)
                .where(
                    ComparisonSetMember.tenant_id == self.tenant_id,
                    ComparisonSetMember.comparison_set_id == item.id,
                )
                .order_by(ComparisonSetMember.position, ComparisonSetMember.id)
            )
        )
        self.session.add(
            ComparisonSetVersion(
                tenant_id=self.tenant_id,
                comparison_set_id=item.id,
                version=item.version,
                snapshot_json={
                    "name": item.name,
                    "description": item.description,
                    "visibility": (
                        item.visibility.value
                        if isinstance(item.visibility, SavedSearchVisibility)
                        else str(item.visibility)
                    ),
                    "member_entity_ids": member_ids,
                },
                changed_by_user_id=self.user_id,
            )
        )

    def _visible_set(self, item_id: str, *, lock: bool) -> ComparisonSet:
        statement = select(ComparisonSet).where(
            ComparisonSet.id == item_id,
            ComparisonSet.tenant_id == self.tenant_id,
            or_(
                ComparisonSet.owner_user_id == self.user_id,
                ComparisonSet.visibility == SavedSearchVisibility.TENANT,
            ),
        )
        if lock:
            statement = statement.with_for_update()
        item = self.session.scalar(statement)
        if item is None:
            raise ComparisonSetNotFound("Comparison set not found")
        return item

    def _owned_set(self, item_id: str, *, lock: bool) -> ComparisonSet:
        statement = select(ComparisonSet).where(
            ComparisonSet.id == item_id,
            ComparisonSet.tenant_id == self.tenant_id,
            ComparisonSet.owner_user_id == self.user_id,
        )
        if lock:
            statement = statement.with_for_update()
        item = self.session.scalar(statement)
        if item is None:
            raise ComparisonSetNotFound("Comparison set not found")
        return item

    @staticmethod
    def _require_version(item: ComparisonSet, expected: int) -> None:
        if item.version != expected:
            raise ComparisonSetConflict(f"Comparison set version changed; current version is {item.version}")

    def _audit(self, resource_id: str, action: str, details: dict[str, object]) -> None:
        self.session.add(
            AuditEvent(
                tenant_id=self.tenant_id,
                actor_type="user",
                actor_id=self.user_id,
                action=action,
                resource_type="comparison_set",
                resource_id=resource_id,
                outcome="success",
                request_id=str(uuid.uuid4()),
                details=details,
            )
        )
