from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pharma_intel.config import Settings
from pharma_intel.models import (
    DataSource,
    Entity,
    EvidenceClaim,
    FactProvenanceLink,
    GovernanceStatus,
    KnowledgePage,
    KnowledgePageVersion,
    SourceAsset,
    SourceAssetState,
    SourceDocument,
    SourceVersion,
    SourceVersionState,
    StagedFact,
)
from pharma_intel.object_store import ObjectStore, ObjectStoreError
from pharma_intel.search.chunking import chunk_text
from pharma_intel.search.contracts import ProjectionDocument
from pharma_intel.search.mappings import ENTITY_INDEX, EVIDENCE_INDEX, KNOWLEDGE_INDEX, SCHEMA_VERSION

SEARCHABLE_SOURCE_VERSION_STATES = frozenset(
    {
        SourceVersionState.PARSED,
        SourceVersionState.INDEXED,
        SourceVersionState.REVIEW_PENDING,
        SourceVersionState.PUBLISHED,
    }
)


def entity_projection(entity: Entity) -> ProjectionDocument:
    return ProjectionDocument(
        kind=ENTITY_INDEX,
        document_id=f"{entity.tenant_id}:{entity.id}",
        tenant_id=entity.tenant_id,
        source={
            "schema_version": SCHEMA_VERSION,
            "tenant_id": entity.tenant_id,
            "entity_id": entity.id,
            "entity_type": entity.entity_type.value,
            "name": entity.name,
            "normalized_name": entity.normalized_name,
            "aliases": [alias.alias for alias in entity.aliases],
            "description": entity.description,
            "external_id_values": sorted(set(entity.external_ids.values())),
            "external_ids": entity.external_ids,
            "review_status": entity.review_status.value,
            "updated_at": _iso(entity.updated_at),
        },
    )


def load_entity_projection(session: Session, tenant_id: str, entity_id: str) -> ProjectionDocument | None:
    entity = session.scalar(
        select(Entity)
        .options(selectinload(Entity.aliases))
        .where(Entity.tenant_id == tenant_id, Entity.id == entity_id)
    )
    return entity_projection(entity) if entity is not None else None


def source_chunk_projections(
    session: Session,
    object_store: ObjectStore,
    settings: Settings,
    tenant_id: str,
    source_version_id: str,
    *,
    indexed_at: datetime | None = None,
) -> tuple[str | None, list[ProjectionDocument]]:
    version = session.scalar(
        select(SourceVersion).where(
            SourceVersion.tenant_id == tenant_id,
            SourceVersion.id == source_version_id,
        )
    )
    if version is None:
        return None, []
    asset = session.scalar(
        select(SourceAsset).where(
            SourceAsset.tenant_id == tenant_id,
            SourceAsset.id == version.source_asset_id,
        )
    )
    if asset is None:
        raise LookupError("Source asset is missing for the parsed source version")
    if asset.state == SourceAssetState.DELETED or asset.current_version_id != version.id:
        return asset.id, []
    if version.state not in SEARCHABLE_SOURCE_VERSION_STATES:
        return asset.id, []
    if not version.source_document_id or not version.extracted_text_object_uri or not version.extracted_text_sha256:
        raise LookupError("Parsed source version does not have an immutable extracted-text object")
    source_document = session.scalar(
        select(SourceDocument).where(
            SourceDocument.tenant_id == tenant_id,
            SourceDocument.id == version.source_document_id,
        )
    )
    data_source = session.scalar(
        select(DataSource).where(
            DataSource.tenant_id == tenant_id,
            DataSource.id == asset.data_source_id,
        )
    )
    if source_document is None or data_source is None:
        raise LookupError("Source metadata is incomplete for the parsed source version")
    raw = object_store.read_bytes(version.extracted_text_object_uri, settings.search_max_source_text_bytes)
    if hashlib.sha256(raw).hexdigest() != version.extracted_text_sha256:
        raise ObjectStoreError("Extracted-text object failed checksum verification before indexing")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ObjectStoreError("Extracted-text object is not valid UTF-8") from exc
    timestamp = indexed_at or datetime.now(UTC)
    documents = [
        ProjectionDocument(
            kind=EVIDENCE_INDEX,
            document_id=f"{tenant_id}:{version.id}:chunk:{chunk.ordinal}",
            tenant_id=tenant_id,
            source={
                "schema_version": SCHEMA_VERSION,
                "tenant_id": tenant_id,
                "document_kind": "source_chunk",
                "projection_id": f"{version.id}:chunk:{chunk.ordinal}",
                "dataset_key": data_source.dataset_key,
                "source_document_id": source_document.id,
                "source_version_id": version.id,
                "source_asset_id": asset.id,
                "evidence_claim_id": None,
                "subject_entity_id": None,
                "object_entity_id": None,
                "title": source_document.title,
                "content": chunk.content,
                "predicate": None,
                "source_uri": asset.source_uri,
                "content_sha256": source_document.content_sha256,
                "chunk_ordinal": chunk.ordinal,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "locator_kind": chunk.locator_kind,
                "locator_value": chunk.locator_value,
                "confidence": None,
                "review_status": "raw",
                "published_at": _iso(source_document.published_at),
                "indexed_at": _iso(timestamp),
            },
        )
        for chunk in chunk_text(text, settings.search_chunk_chars, settings.search_chunk_overlap_chars)
    ]
    if not documents:
        raise ObjectStoreError("Parsed source text produced no searchable chunks")
    return asset.id, documents


def evidence_claim_projection(
    session: Session,
    tenant_id: str,
    evidence_claim_id: str,
    *,
    indexed_at: datetime | None = None,
) -> ProjectionDocument | None:
    claim = session.scalar(
        select(EvidenceClaim).where(
            EvidenceClaim.tenant_id == tenant_id,
            EvidenceClaim.id == evidence_claim_id,
        )
    )
    if claim is None:
        return None
    source_document = session.scalar(
        select(SourceDocument).where(
            SourceDocument.tenant_id == tenant_id,
            SourceDocument.id == claim.source_document_id,
        )
    )
    if source_document is None:
        raise LookupError("Evidence claim source document is missing")
    source_context = session.execute(
        select(
            FactProvenanceLink.source_version_id,
            FactProvenanceLink.source_asset_id,
            FactProvenanceLink.dataset_key,
            SourceAsset.source_uri,
        )
        .join(StagedFact, StagedFact.id == FactProvenanceLink.staged_fact_id)
        .join(SourceAsset, SourceAsset.id == FactProvenanceLink.source_asset_id)
        .where(
            FactProvenanceLink.tenant_id == tenant_id,
            FactProvenanceLink.resource_type == "evidence_claim",
            FactProvenanceLink.resource_id == claim.id,
            FactProvenanceLink.evidence_claim_id == claim.id,
            FactProvenanceLink.source_document_id == source_document.id,
            StagedFact.tenant_id == tenant_id,
            StagedFact.status == GovernanceStatus.PUBLISHED,
            SourceAsset.tenant_id == tenant_id,
            SourceAsset.state != SourceAssetState.DELETED,
        )
        .order_by(FactProvenanceLink.created_at.desc(), FactProvenanceLink.id.desc())
        .limit(1)
    ).first()
    source_version_id = str(source_context[0]) if source_context else None
    source_asset_id = str(source_context[1]) if source_context else None
    dataset_key = str(source_context[2]) if source_context else "unclassified"
    source_uri = str(source_context[3]) if source_context else source_document.source_uri
    value_text = json.dumps(claim.value, ensure_ascii=False, sort_keys=True) if claim.value is not None else ""
    content = claim.quote or value_text or claim.predicate
    locator_kind = "page" if claim.page_number is not None else ("source" if claim.source_locator else None)
    locator_value = str(claim.page_number) if claim.page_number is not None else claim.source_locator
    timestamp = indexed_at or datetime.now(UTC)
    return ProjectionDocument(
        kind=EVIDENCE_INDEX,
        document_id=f"{tenant_id}:claim:{claim.id}",
        tenant_id=tenant_id,
        source={
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "document_kind": "evidence_claim",
            "projection_id": f"claim:{claim.id}",
            "dataset_key": dataset_key,
            "source_document_id": source_document.id,
            "source_version_id": source_version_id,
            "source_asset_id": source_asset_id,
            "evidence_claim_id": claim.id,
            "subject_entity_id": claim.subject_id,
            "object_entity_id": claim.object_id,
            "title": source_document.title,
            "content": content,
            "predicate": claim.predicate,
            "source_uri": source_uri,
            "content_sha256": source_document.content_sha256,
            "chunk_ordinal": 0,
            "start_char": None,
            "end_char": None,
            "locator_kind": locator_kind,
            "locator_value": locator_value,
            "confidence": claim.confidence,
            "review_status": claim.review_status.value,
            "published_at": _iso(source_document.published_at),
            "indexed_at": _iso(timestamp),
        },
    )


def knowledge_page_projection(
    session: Session,
    tenant_id: str,
    knowledge_page_id: str,
) -> ProjectionDocument | None:
    page = session.scalar(
        select(KnowledgePage).where(
            KnowledgePage.tenant_id == tenant_id,
            KnowledgePage.id == knowledge_page_id,
        )
    )
    if page is None or page.current_version_id is None:
        return None
    version = session.scalar(
        select(KnowledgePageVersion).where(
            KnowledgePageVersion.tenant_id == tenant_id,
            KnowledgePageVersion.id == page.current_version_id,
            KnowledgePageVersion.knowledge_page_id == page.id,
        )
    )
    if version is None:
        raise LookupError("Knowledge page current version is missing")
    return ProjectionDocument(
        kind=KNOWLEDGE_INDEX,
        document_id=f"{tenant_id}:{page.id}",
        tenant_id=tenant_id,
        source={
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "knowledge_page_id": page.id,
            "page_version_id": version.id,
            "page_key": page.page_key,
            "page_type": page.page_type,
            "title": page.title,
            "subject_entity_id": page.subject_entity_id,
            "content": version.rendered_markdown,
            "content_sha256": version.content_sha256,
            "source_snapshot_at": _iso(version.source_snapshot_at),
            "updated_at": _iso(page.updated_at),
        },
    )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
