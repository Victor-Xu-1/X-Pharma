from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.models import (
    Entity,
    EvidenceClaim,
    KnowledgePage,
    SourceAsset,
    SourceAssetState,
    SourceVersion,
    Tenant,
)
from pharma_intel.object_store import ObjectStore
from pharma_intel.search.client import OpenSearchGateway
from pharma_intel.search.contracts import ProjectionDocument
from pharma_intel.search.documents import (
    SEARCHABLE_SOURCE_VERSION_STATES,
    entity_projection,
    evidence_claim_projection,
    knowledge_page_projection,
    source_chunk_projections,
)


@dataclass(frozen=True)
class RebuildResult:
    targets: dict[str, str]
    counts: dict[str, int]
    started_at: datetime
    completed_at: datetime


class SearchRebuilder:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        gateway: OpenSearchGateway,
        object_store: ObjectStore,
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.gateway = gateway
        self.object_store = object_store
        self.settings = settings

    def rebuild(self, build_id: str | None = None) -> RebuildResult:
        started_at = datetime.now(UTC)
        targets = self.gateway.create_rebuild_indices(build_id)
        counts = {kind: 0 for kind in targets}
        pending: list[ProjectionDocument] = []

        def flush() -> None:
            if not pending:
                return
            self.gateway.bulk_index(pending, targets=targets)
            for document in pending:
                counts[document.kind] += 1
            pending.clear()

        for document in self.documents(started_at):
            pending.append(document)
            if len(pending) >= self.settings.search_projection_batch_size:
                flush()
        flush()
        self.gateway.refresh(targets)
        actual_counts = {kind: self.gateway.count(kind, target=target) for kind, target in targets.items()}
        if actual_counts != counts:
            raise RuntimeError(f"OpenSearch rebuild count mismatch: expected {counts}, got {actual_counts}")
        self.gateway.swap_rebuild_indices(targets)
        return RebuildResult(targets, counts, started_at, datetime.now(UTC))

    def expected_counts(self) -> dict[str, int]:
        counts = {"entities": 0, "evidence": 0, "knowledge": 0}
        for document in self.documents():
            counts[document.kind] += 1
        return counts

    def current_counts(self) -> dict[str, int]:
        return {kind: self.gateway.count(kind) for kind in ("entities", "evidence", "knowledge")}

    def documents(self, indexed_at: datetime | None = None) -> Iterator[ProjectionDocument]:
        projection_time = indexed_at or datetime.now(UTC)
        for tenant_id in self._tenant_ids():
            with self.session_factory() as session:
                set_tenant_context(session, tenant_id)
                entities = session.scalars(
                    select(Entity)
                    .options(selectinload(Entity.aliases))
                    .where(Entity.tenant_id == tenant_id)
                    .order_by(Entity.id)
                )
                for entity in entities:
                    yield entity_projection(entity)

                current_version_ids = session.scalars(
                    select(SourceVersion.id)
                    .join(
                        SourceAsset,
                        (SourceAsset.id == SourceVersion.source_asset_id)
                        & (SourceAsset.current_version_id == SourceVersion.id),
                    )
                    .where(
                        SourceVersion.tenant_id == tenant_id,
                        SourceAsset.tenant_id == tenant_id,
                        SourceAsset.state != SourceAssetState.DELETED,
                        SourceVersion.state.in_(SEARCHABLE_SOURCE_VERSION_STATES),
                    )
                    .order_by(SourceVersion.id)
                )
                for version_id in current_version_ids:
                    _, documents = source_chunk_projections(
                        session,
                        self.object_store,
                        self.settings,
                        tenant_id,
                        version_id,
                        indexed_at=projection_time,
                    )
                    yield from documents

                claim_ids = session.scalars(
                    select(EvidenceClaim.id).where(EvidenceClaim.tenant_id == tenant_id).order_by(EvidenceClaim.id)
                )
                for claim_id in claim_ids:
                    claim_document = evidence_claim_projection(
                        session,
                        tenant_id,
                        claim_id,
                        indexed_at=projection_time,
                    )
                    if claim_document is not None:
                        yield claim_document

                page_ids = session.scalars(
                    select(KnowledgePage.id)
                    .where(
                        KnowledgePage.tenant_id == tenant_id,
                        KnowledgePage.current_version_id.is_not(None),
                    )
                    .order_by(KnowledgePage.id)
                )
                for page_id in page_ids:
                    page_document = knowledge_page_projection(session, tenant_id, page_id)
                    if page_document is not None:
                        yield page_document

    def _tenant_ids(self) -> list[str]:
        with self.session_factory() as session:
            return list(session.scalars(select(Tenant.id).where(Tenant.active.is_(True)).order_by(Tenant.id)))
