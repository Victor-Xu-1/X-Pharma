from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.config import Settings
from pharma_intel.ingest.data_factory import DataFactoryService
from pharma_intel.licensing import internal_evidence_license_policy
from pharma_intel.models import (
    DataSource,
    DataSourceType,
    EntityType,
    OutboxEvent,
    ProjectionDelivery,
    ProjectionDeliveryState,
    SourceVersion,
    StageStatus,
    Tenant,
    TenantDataset,
)
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.repository import EntityRepository
from pharma_intel.schemas import EntityCreate
from pharma_intel.search.chunking import chunk_text
from pharma_intel.search.client import OpenSearchGateway
from pharma_intel.search.contracts import ProjectionDocument
from pharma_intel.search.documents import source_chunk_projections
from pharma_intel.search.projector import SearchProjectionConsumer


class RecordingGateway:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.documents: list[ProjectionDocument] = []
        self.replaced_sources: list[tuple[str, str, str]] = []
        self.deleted_sources: list[tuple[str, str]] = []
        self.deleted_claims: list[tuple[str, str]] = []

    def bulk_index(
        self,
        documents: list[ProjectionDocument],
        *,
        targets: dict[str, str] | None = None,
        refresh: bool = False,
    ) -> int:
        del targets, refresh
        if self.fail:
            raise RuntimeError("search cluster unavailable")
        self.documents.extend(documents)
        return len(documents)

    def replace_source_chunks(
        self,
        tenant_id: str,
        source_asset_id: str,
        source_version_id: str,
        documents: list[ProjectionDocument],
    ) -> int:
        if self.fail:
            raise RuntimeError("search cluster unavailable")
        self.replaced_sources.append((tenant_id, source_asset_id, source_version_id))
        self.documents.extend(documents)
        return len(documents)

    def delete_source_asset_evidence(self, tenant_id: str, source_asset_id: str) -> int:
        if self.fail:
            raise RuntimeError("search cluster unavailable")
        self.deleted_sources.append((tenant_id, source_asset_id))
        return 1

    def delete_evidence_claim(self, tenant_id: str, evidence_claim_id: str) -> bool:
        if self.fail:
            raise RuntimeError("search cluster unavailable")
        self.deleted_claims.append((tenant_id, evidence_claim_id))
        return True

    @staticmethod
    def read_alias(kind: str) -> str:
        return f"test-{kind}"


def _factory(session: Session) -> sessionmaker[Session]:
    return sessionmaker(bind=session.get_bind(), expire_on_commit=False)


def test_chunker_preserves_source_locators_and_bounded_overlap() -> None:
    text = "[[page:1]]\nEGFR evidence line one.\nEGFR evidence line two.\n[[page:2]]\nKRAS evidence."

    chunks = chunk_text(text, max_chars=35, overlap_chars=5)

    assert chunks
    assert all(len(chunk.content) <= 35 for chunk in chunks)
    assert chunks[0].locator_kind == "page"
    assert chunks[0].locator_value == "1"
    assert chunks[-1].locator_value == "2"
    assert all(chunk.start_char < chunk.end_char for chunk in chunks)
    with pytest.raises(ValueError, match="overlap"):
        chunk_text(text, max_chars=10, overlap_chars=10)


def test_entity_and_parsed_source_events_project_idempotently(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "target.md").write_text("[[page:1]]\nEGFR is a receptor tyrosine kinase.", encoding="utf-8")
    dataset = TenantDataset(
        tenant_id=tenant.id,
        dataset_key="literature",
        display_name="Literature",
        ragflow_dataset_id="migration-only-literature",
        license_policy=internal_evidence_license_policy(source="test"),
    )
    source = DataSource(
        tenant_id=tenant.id,
        name="Literature",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        stable_seconds=0,
    )
    session.add_all([dataset, source])
    session.commit()
    entity = EntityRepository(session, tenant.id).create(
        EntityCreate(entity_type=EntityType.TARGET, name="EGFR", aliases=["ERBB1"])
    )
    settings = Settings(
        object_store_root=tmp_path / "objects",
        source_roots_config=str(tmp_path),
        search_chunk_chars=500,
        search_chunk_overlap_chars=50,
    )
    store = FileSystemObjectStore(settings.object_store_root)
    data_factory = DataFactoryService(session, settings, store, tenant.id)
    scan = data_factory.scan_source(source.id, "search-projection-workflow")
    pending_asset_id, pending_documents = source_chunk_projections(
        session,
        store,
        settings,
        tenant.id,
        scan.version_ids[0],
    )
    assert pending_asset_id is not None
    assert pending_documents == []
    data_factory.process_version(scan.version_ids[0])
    gateway = RecordingGateway()
    consumer = SearchProjectionConsumer(
        _factory(session),
        cast(OpenSearchGateway, gateway),
        store,
        settings,
        worker_id="unit-projector",
    )

    result = consumer.drain()

    assert result.processed == 2
    assert result.succeeded == 2
    assert consumer.drain_once().processed == 0
    assert any(
        document.kind == "entities" and document.source["entity_id"] == entity.id for document in gateway.documents
    )
    evidence = [document for document in gateway.documents if document.kind == "evidence"]
    assert len(evidence) == 1
    assert evidence[0].source["dataset_key"] == "literature"
    assert evidence[0].source["content_sha256"]
    assert evidence[0].source["source_uri"] == str(root / "target.md")
    version = session.get(SourceVersion, scan.version_ids[0])
    assert version is not None
    session.refresh(version)
    assert version.retrieval_status == StageStatus.SUCCEEDED
    assert version.retrieval_projection_id is not None
    deliveries = list(session.scalars(select(ProjectionDelivery)))
    assert len(deliveries) == 2
    assert {delivery.state for delivery in deliveries} == {ProjectionDeliveryState.SUCCEEDED}


def test_projection_failure_enters_dead_letter_and_requires_explicit_replay(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    EntityRepository(session, tenant.id).create(EntityCreate(entity_type=EntityType.TARGET, name="KRAS"))
    settings = Settings(search_projection_max_attempts=1)
    gateway = RecordingGateway(fail=True)
    consumer = SearchProjectionConsumer(
        _factory(session),
        cast(OpenSearchGateway, gateway),
        FileSystemObjectStore(tmp_path / "objects"),
        settings,
        worker_id="failed-projector",
    )

    result = consumer.drain_once()

    assert result.dead == 1
    delivery = session.scalar(select(ProjectionDelivery))
    assert delivery is not None
    session.refresh(delivery)
    assert delivery.state == ProjectionDeliveryState.DEAD
    assert "search cluster unavailable" in (delivery.last_error or "")
    assert consumer.drain_once().processed == 0
    assert consumer.retry_dead(tenant.id) == 1
    gateway.fail = False
    replay = consumer.drain_once()
    assert replay.succeeded == 1
    replayed_delivery = session.get(ProjectionDelivery, delivery.id, populate_existing=True)
    assert replayed_delivery is not None
    assert replayed_delivery.state == ProjectionDeliveryState.SUCCEEDED
    assert session.scalar(select(OutboxEvent).where(OutboxEvent.event_type == "canonical.entity.upserted")) is not None


def test_source_withdrawal_event_deletes_projected_evidence(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    event = OutboxEvent(
        tenant_id=tenant.id,
        aggregate_type="source_asset",
        aggregate_id="11111111-1111-4111-8111-111111111119",
        event_type="source.asset.deleted",
        payload={"source_asset_id": "11111111-1111-4111-8111-111111111119"},
    )
    session.add(event)
    session.commit()
    gateway = RecordingGateway()
    consumer = SearchProjectionConsumer(
        _factory(session),
        cast(OpenSearchGateway, gateway),
        FileSystemObjectStore(tmp_path / "objects"),
        Settings(),
        worker_id="withdrawal-projector",
    )

    result = consumer.drain_once()

    assert result.succeeded == 1
    assert gateway.deleted_sources == [(tenant.id, event.aggregate_id)]

    reauthorized_event = OutboxEvent(
        tenant_id=tenant.id,
        aggregate_type="source_asset",
        aggregate_id=event.aggregate_id,
        event_type="source.asset.reauthorized",
        payload={"source_asset_id": event.aggregate_id},
    )
    session.add(reauthorized_event)
    session.commit()

    acknowledged = consumer.drain_once()

    assert acknowledged.succeeded == 1
    assert gateway.deleted_sources == [(tenant.id, event.aggregate_id)]


def test_fact_withdrawal_event_deletes_the_exact_claim_projection(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    event = OutboxEvent(
        tenant_id=tenant.id,
        aggregate_type="staged_fact",
        aggregate_id="11111111-1111-4111-8111-111111111117",
        event_type="governance.fact.withdrawn",
        payload={
            "staged_fact_id": "11111111-1111-4111-8111-111111111117",
            "evidence_claim_id": "11111111-1111-4111-8111-111111111118",
            "resources": [],
        },
    )
    session.add(event)
    session.commit()
    gateway = RecordingGateway()
    consumer = SearchProjectionConsumer(
        _factory(session),
        cast(OpenSearchGateway, gateway),
        FileSystemObjectStore(tmp_path / "objects"),
        Settings(),
        worker_id="fact-withdrawal-projector",
    )

    result = consumer.drain_once()

    assert result.succeeded == 1
    assert gateway.deleted_claims == [(tenant.id, "11111111-1111-4111-8111-111111111118")]
