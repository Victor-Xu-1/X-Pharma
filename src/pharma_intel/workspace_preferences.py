from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_intel.models import WorkspaceTablePreference
from pharma_intel.schemas import WorkspaceTablePreferenceKey, WorkspaceTablePreferenceUpdate


class WorkspaceTablePreferenceConflict(Exception):
    pass


class WorkspaceTablePreferenceService:
    def __init__(self, session: Session, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    def get(self, preference_key: WorkspaceTablePreferenceKey) -> WorkspaceTablePreference | None:
        return self.session.scalar(
            select(WorkspaceTablePreference).where(
                WorkspaceTablePreference.tenant_id == self.tenant_id,
                WorkspaceTablePreference.user_id == self.user_id,
                WorkspaceTablePreference.preference_key == preference_key,
            )
        )

    def upsert(
        self,
        preference_key: WorkspaceTablePreferenceKey,
        command: WorkspaceTablePreferenceUpdate,
    ) -> WorkspaceTablePreference:
        item = self.session.scalar(
            select(WorkspaceTablePreference)
            .where(
                WorkspaceTablePreference.tenant_id == self.tenant_id,
                WorkspaceTablePreference.user_id == self.user_id,
                WorkspaceTablePreference.preference_key == preference_key,
            )
            .with_for_update()
        )
        if item is None:
            if command.expected_version != 0:
                self.session.rollback()
                raise WorkspaceTablePreferenceConflict("Table preference version is stale")
            item = WorkspaceTablePreference(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                preference_key=preference_key,
                schema_version=command.schema_version,
                column_visibility=dict(command.column_visibility),
                column_order=list(command.column_order),
                density=command.density,
                version=1,
            )
            self.session.add(item)
        else:
            if item.version != command.expected_version:
                self.session.rollback()
                raise WorkspaceTablePreferenceConflict("Table preference version is stale")
            item.schema_version = command.schema_version
            item.column_visibility = dict(command.column_visibility)
            item.column_order = list(command.column_order)
            item.density = command.density
            item.version += 1
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise WorkspaceTablePreferenceConflict("Table preference changed concurrently") from exc
        self.session.refresh(item)
        return item
