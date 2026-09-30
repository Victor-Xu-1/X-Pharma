from __future__ import annotations

import os
import uuid
from collections.abc import Sequence
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pharma_intel.config import Settings
from pharma_intel.ingest.data_factory import DataFactoryService
from pharma_intel.licensing import internal_evidence_license_policy
from pharma_intel.models import Base, DataSource, DataSourceType, EntityType, Tenant, TenantDataset
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.repository import EntityRepository
from pharma_intel.schemas import EntityCreate
from pharma_intel.search.client import OpenSearchGateway
from pharma_intel.search.mappings import SCHEMA_VERSION, index_definitions
from pharma_intel.search.projector import SearchProjectionConsumer
from pharma_intel.search.rebuild import SearchRebuilder


class DeterministicSemanticEmbedder:
    model = "deterministic-integration-v1"
    dimensions = 4

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            normalized = text.casefold()
            vectors.append(
                [
                    float("egfr" in normalized or "erbb1" in normalized or "p00533" in normalized),
                    float("c797s" in normalized),
                    float("l858r" in normalized),
                    max(float("resistance" in normalized), 0.01),
                ]
            )
        return vectors


@pytest.mark.integration
def test_real_opensearch_projects_searches_isolates_and_rebuilds(tmp_path: Path) -> None:
    opensearch_url = os.getenv("TEST_OPENSEARCH_URL")
    if not opensearch_url:
        pytest.skip("TEST_OPENSEARCH_URL is not configured")
    prefix = f"itest-{uuid.uuid4().hex[:10]}"
    settings = Settings(
        search_backend="opensearch",
        opensearch_url=opensearch_url,
        opensearch_verify_certs=False,
        opensearch_index_prefix=prefix,
        opensearch_index_replicas=0,
        search_projection_enabled=True,
        search_semantic_enabled=True,
        search_embedding_base_url="http://unused.integration.test",
        search_embedding_api_key="integration-secret",
        search_embedding_model="deterministic-integration-v1",
        search_embedding_dimensions=4,
        search_semantic_min_score=0.75,
        search_projection_batch_size=10,
        search_chunk_chars=500,
        search_chunk_overlap_chars=50,
        object_store_root=tmp_path / "objects",
        source_roots_config=str(tmp_path),
    )
    gateway = OpenSearchGateway(settings, embedder=DeterministicSemanticEmbedder())
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    store = FileSystemObjectStore(settings.object_store_root)
    try:
        initialized = gateway.ensure_indices()
        assert set(initialized) == {"entities", "evidence", "knowledge"}
        with factory() as session:
            tenant = Tenant(slug="search-a", name="Search Tenant A")
            other = Tenant(slug="search-b", name="Search Tenant B")
            session.add_all([tenant, other])
            session.commit()
            session.add(
                TenantDataset(
                    tenant_id=tenant.id,
                    dataset_key="literature",
                    display_name="Literature",
                    ragflow_dataset_id="migration-literature",
                    license_policy=internal_evidence_license_policy(source="test"),
                )
            )
            source_root = tmp_path / "source"
            source_root.mkdir()
            (source_root / "egfr.md").write_text(
                "[[page:1]]\nEGFR L858R alters inhibitor response and kinase activity.",
                encoding="utf-8",
            )
            (source_root / "egfr-resistance.md").write_text(
                "[[page:2]]\nEGFR C797S changes kinase activity and resistance mechanisms.",
                encoding="utf-8",
            )
            source = DataSource(
                tenant_id=tenant.id,
                name="Literature",
                source_type=DataSourceType.FOLDER,
                root_uri=str(source_root),
                owner="Research Operations",
                authorization_scopes=["contract:test-source"],
                dataset_key="literature",
                stable_seconds=0,
            )
            session.add(source)
            session.commit()
            repository = EntityRepository(session, tenant.id)
            primary_target = repository.create(
                EntityCreate(
                    entity_type=EntityType.TARGET,
                    name="Epidermal growth factor receptor",
                    aliases=["EGFR", "ERBB1"],
                    external_ids={"uniprot": "P00533"},
                )
            )
            egfr_amplification = repository.create(
                EntityCreate(entity_type=EntityType.TARGET, name="EGFR amplification")
            )
            alpha_target = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="Alpha target"))
            zulu_target = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="Zulu target"))
            EntityRepository(session, other.id).create(
                EntityCreate(entity_type=EntityType.TARGET, name="Tenant B private target")
            )
            data_factory = DataFactoryService(session, settings, store, tenant.id)
            scan = data_factory.scan_source(source.id, "real-opensearch-ingest")
            for version_id in scan.version_ids:
                data_factory.process_version(version_id)

        consumer = SearchProjectionConsumer(factory, gateway, store, settings, worker_id="real-opensearch-test")
        projected = consumer.drain()
        assert projected.succeeded == 7
        gateway.refresh()

        entity_page = gateway.search_entities(tenant.id, "ERBB1", EntityType.TARGET, 10, 0)
        assert entity_page.total == 2
        assert entity_page.entity_ids[0] == primary_target.id
        assert egfr_amplification.id in entity_page.entity_ids[1:]
        assert entity_page.facets["entity_type"] == {"target": 1}
        exact_alias_page = gateway.search_entities(tenant.id, "EGFR", EntityType.TARGET, 10, 0)
        assert exact_alias_page.entity_ids[0] == primary_target.id
        assert egfr_amplification.id in exact_alias_page.entity_ids[1:]
        first_name_page = gateway.search_entities(
            tenant.id,
            None,
            EntityType.TARGET,
            1,
            0,
            sort_by="name",
            sort_direction="desc",
        )
        second_name_page = gateway.search_entities(
            tenant.id,
            None,
            EntityType.TARGET,
            1,
            1,
            sort_by="name",
            sort_direction="desc",
        )
        assert first_name_page.total == second_name_page.total == 4
        assert first_name_page.entity_ids == [zulu_target.id]
        assert second_name_page.entity_ids == [primary_target.id]
        assert alpha_target.id not in first_name_page.entity_ids + second_name_page.entity_ids
        assert gateway.search_entities(other.id, "EGFR", None, 10, 0).total == 0
        first_evidence = gateway.search_evidence(tenant.id, "kinase activity", ["literature"], 1)
        second_evidence = gateway.search_evidence(tenant.id, "kinase activity", ["literature"], 1, 1)
        assert len(first_evidence) == len(second_evidence) == 1
        assert first_evidence[0].document_id != second_evidence[0].document_id
        assert {first_evidence[0].dataset_key, second_evidence[0].dataset_key} == {"literature"}
        assert first_evidence[0].metadata["content_sha256"]
        assert {first_evidence[0].positions[0]["locator_value"], second_evidence[0].positions[0]["locator_value"]} == {
            "1",
            "2",
        }
        semantic_evidence = gateway.search_evidence(tenant.id, "C797S resistance", ["literature"], 1)
        assert len(semantic_evidence) == 1
        assert "C797S" in semantic_evidence[0].content
        assert semantic_evidence[0].metadata["retrieval_mode"] == "hybrid"
        assert semantic_evidence[0].metadata["embedding_model"] == "deterministic-integration-v1"
        withdrawn_asset_id = str(semantic_evidence[0].metadata["source_asset_id"])
        assert gateway.delete_source_asset_evidence(tenant.id, withdrawn_asset_id) == 1
        assert gateway.search_evidence(tenant.id, "C797S resistance", ["literature"], 1) == []

        claim_id = str(uuid.uuid4())
        claim_document_id = f"{tenant.id}:claim:{claim_id}"
        gateway.client.index(
            index=gateway.write_alias("evidence"),
            id=claim_document_id,
            routing=tenant.id,
            refresh=True,
            body={
                "schema_version": SCHEMA_VERSION,
                "tenant_id": tenant.id,
                "document_kind": "evidence_claim",
                "projection_id": claim_id,
                "dataset_key": "literature",
                "evidence_claim_id": claim_id,
                "title": "Withdrawn claim",
                "content": "Claim projection that must be removed by deterministic ID.",
            },
        )
        assert gateway.client.exists(
            index=gateway.write_alias("evidence"),
            id=claim_document_id,
            routing=tenant.id,
        )
        assert gateway.delete_evidence_claim(tenant.id, claim_id) is True
        assert gateway.delete_evidence_claim(tenant.id, claim_id) is False
        assert not gateway.client.exists(
            index=gateway.write_alias("evidence"),
            id=claim_document_id,
            routing=tenant.id,
        )

        previous = gateway.alias_indices("entities")
        rebuilt = SearchRebuilder(factory, gateway, store, settings).rebuild("verified-rebuild")
        assert rebuilt.counts == {"entities": 5, "evidence": 2, "knowledge": 0}
        assert gateway.alias_indices("entities") == [rebuilt.targets["entities"]]
        assert gateway.alias_indices("entities") != previous
        identifier_page = gateway.search_entities(tenant.id, "P00533", None, 10, 0)
        assert identifier_page.entity_ids[0] == primary_target.id
        assert egfr_amplification.id in identifier_page.entity_ids[1:]
    finally:
        try:
            gateway.client.indices.delete(index=f"{prefix}-*", ignore=[400, 404])
            for definition in index_definitions():
                gateway.client.indices.delete_index_template(
                    name=f"{prefix}-{definition.kind}-template-v{SCHEMA_VERSION}",
                    ignore=[404],
                )
            gateway.client.transport.perform_request(
                "DELETE",
                f"/_search/pipeline/{gateway.hybrid_pipeline_name}",
                ignore=[404],
            )
        finally:
            Base.metadata.drop_all(engine)
            engine.dispose()
