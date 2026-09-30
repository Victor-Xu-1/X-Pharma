from __future__ import annotations

import socket
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.models import DataQualitySnapshot, Tenant
from pharma_intel.quality.service import DataQualityService


class DataQualityWorker:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        settings: Settings,
        *,
        worker_id: str | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.worker_id = worker_id or f"{socket.gethostname()}:{uuid.uuid4()}"
        self._next_check = 0.0

    def process_once(self) -> DataQualitySnapshot | None:
        now_monotonic = time.monotonic()
        if now_monotonic < self._next_check:
            return None
        self._next_check = now_monotonic + min(60, self.settings.data_quality_evaluation_interval_seconds / 4)
        now = datetime.now(UTC)
        due_before = now - timedelta(seconds=self.settings.data_quality_evaluation_interval_seconds)
        for tenant_id in self._tenant_ids():
            with self.session_factory() as session:
                set_tenant_context(session, tenant_id)
                if session.bind is not None and session.bind.dialect.name == "postgresql":
                    locked = session.scalar(
                        text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))"),
                        {"key": f"data-quality:{tenant_id}"},
                    )
                    if not locked:
                        session.rollback()
                        continue
                latest = session.scalar(
                    select(DataQualitySnapshot.measured_at)
                    .where(DataQualitySnapshot.tenant_id == tenant_id)
                    .order_by(DataQualitySnapshot.measured_at.desc(), DataQualitySnapshot.id.desc())
                    .limit(1)
                )
                if latest is not None and self._aware(latest) > due_before:
                    session.rollback()
                    continue
                return DataQualityService(session, self.settings, tenant_id).evaluate(
                    trigger="scheduled",
                    actor_type="system",
                    actor_id=self.worker_id,
                )
        return None

    def _tenant_ids(self) -> list[str]:
        with self.session_factory() as session:
            return list(session.scalars(select(Tenant.id).where(Tenant.active.is_(True)).order_by(Tenant.id)))

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
