from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pharma_intel.config import Settings
from pharma_intel.product import PACKAGE_NAME

ENTITY_INDEX = "entities"
EVIDENCE_INDEX = "evidence"
KNOWLEDGE_INDEX = "knowledge"
SCHEMA_VERSION = 2


@dataclass(frozen=True)
class IndexDefinition:
    kind: str
    mappings: dict[str, Any]


def index_definitions(settings: Settings | None = None) -> tuple[IndexDefinition, ...]:
    embedding_dimensions = settings.search_embedding_dimensions if settings is not None else 1024
    embedding_model = settings.search_embedding_model if settings is not None else "unconfigured-api-model"
    return (
        IndexDefinition(ENTITY_INDEX, _entity_mapping(embedding_dimensions, embedding_model)),
        IndexDefinition(EVIDENCE_INDEX, _evidence_mapping(embedding_dimensions, embedding_model)),
        IndexDefinition(KNOWLEDGE_INDEX, _knowledge_mapping(embedding_dimensions, embedding_model)),
    )


def index_template(settings: Settings, definition: IndexDefinition) -> dict[str, Any]:
    return {
        "index_patterns": [f"{settings.opensearch_index_prefix}-{definition.kind}-v{SCHEMA_VERSION}-*"],
        "priority": 500,
        "_meta": {
            "owner": PACKAGE_NAME,
            "projection": definition.kind,
            "schema_version": SCHEMA_VERSION,
        },
        "template": {
            "settings": {
                "number_of_shards": settings.opensearch_index_shards,
                "number_of_replicas": settings.opensearch_index_replicas,
                "refresh_interval": "1s",
                "index.mapping.total_fields.limit": 1000,
                "index.knn": True,
                "analysis": _analysis(),
            },
            "mappings": definition.mappings,
        },
    }


def _analysis() -> dict[str, Any]:
    return {
        "normalizer": {
            "pharma_folded": {
                "type": "custom",
                "filter": ["lowercase", "asciifolding"],
            }
        },
        "tokenizer": {
            "pharma_edge": {
                "type": "edge_ngram",
                "min_gram": 1,
                "max_gram": 30,
                "token_chars": ["letter", "digit"],
            }
        },
        "analyzer": {
            "pharma_text": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "asciifolding"],
            },
            "pharma_autocomplete": {
                "type": "custom",
                "tokenizer": "pharma_edge",
                "filter": ["lowercase", "asciifolding"],
            },
        },
    }


def _searchable_text(*, keyword: bool = False) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "autocomplete": {
            "type": "text",
            "analyzer": "pharma_autocomplete",
            "search_analyzer": "pharma_text",
        }
    }
    if keyword:
        fields["keyword"] = {"type": "keyword", "normalizer": "pharma_folded", "ignore_above": 512}
    return {"type": "text", "analyzer": "pharma_text", "fields": fields}


def _entity_mapping(embedding_dimensions: int, embedding_model: str) -> dict[str, Any]:
    return {
        "dynamic": "strict",
        "_meta": {
            "schema_version": SCHEMA_VERSION,
            "projection": ENTITY_INDEX,
            "embedding_model": embedding_model,
        },
        "properties": {
            "schema_version": {"type": "integer"},
            "tenant_id": {"type": "keyword"},
            "entity_id": {"type": "keyword"},
            "entity_type": {"type": "keyword"},
            "name": _searchable_text(keyword=True),
            "normalized_name": {"type": "keyword", "normalizer": "pharma_folded"},
            "aliases": _searchable_text(keyword=True),
            "description": {"type": "text", "analyzer": "pharma_text"},
            "external_id_values": {"type": "keyword", "normalizer": "pharma_folded"},
            "external_ids": {"type": "object", "enabled": False},
            "review_status": {"type": "keyword"},
            "updated_at": {"type": "date"},
            "embedding": _embedding_mapping(embedding_dimensions),
            "embedding_model": {"type": "keyword"},
        },
    }


def _evidence_mapping(embedding_dimensions: int, embedding_model: str) -> dict[str, Any]:
    return {
        "dynamic": "strict",
        "_meta": {
            "schema_version": SCHEMA_VERSION,
            "projection": EVIDENCE_INDEX,
            "embedding_model": embedding_model,
        },
        "properties": {
            "schema_version": {"type": "integer"},
            "tenant_id": {"type": "keyword"},
            "document_kind": {"type": "keyword"},
            "projection_id": {"type": "keyword"},
            "dataset_key": {"type": "keyword"},
            "source_document_id": {"type": "keyword"},
            "source_version_id": {"type": "keyword"},
            "source_asset_id": {"type": "keyword"},
            "evidence_claim_id": {"type": "keyword"},
            "subject_entity_id": {"type": "keyword"},
            "object_entity_id": {"type": "keyword"},
            "title": _searchable_text(keyword=True),
            "content": {"type": "text", "analyzer": "pharma_text"},
            "predicate": {"type": "keyword"},
            "source_uri": {"type": "keyword", "index": False},
            "content_sha256": {"type": "keyword"},
            "chunk_ordinal": {"type": "integer"},
            "start_char": {"type": "integer"},
            "end_char": {"type": "integer"},
            "locator_kind": {"type": "keyword"},
            "locator_value": {"type": "keyword"},
            "confidence": {"type": "float"},
            "review_status": {"type": "keyword"},
            "published_at": {"type": "date"},
            "indexed_at": {"type": "date"},
            "embedding": _embedding_mapping(embedding_dimensions),
            "embedding_model": {"type": "keyword"},
        },
    }


def _knowledge_mapping(embedding_dimensions: int, embedding_model: str) -> dict[str, Any]:
    return {
        "dynamic": "strict",
        "_meta": {
            "schema_version": SCHEMA_VERSION,
            "projection": KNOWLEDGE_INDEX,
            "embedding_model": embedding_model,
        },
        "properties": {
            "schema_version": {"type": "integer"},
            "tenant_id": {"type": "keyword"},
            "knowledge_page_id": {"type": "keyword"},
            "page_version_id": {"type": "keyword"},
            "page_key": {"type": "keyword"},
            "page_type": {"type": "keyword"},
            "title": _searchable_text(keyword=True),
            "subject_entity_id": {"type": "keyword"},
            "content": {"type": "text", "analyzer": "pharma_text"},
            "content_sha256": {"type": "keyword"},
            "source_snapshot_at": {"type": "date"},
            "updated_at": {"type": "date"},
            "embedding": _embedding_mapping(embedding_dimensions),
            "embedding_model": {"type": "keyword"},
        },
    }


def _embedding_mapping(dimensions: int) -> dict[str, Any]:
    return {
        "type": "knn_vector",
        "dimension": dimensions,
        "method": {
            "name": "hnsw",
            "engine": "lucene",
            "space_type": "cosinesimil",
            "parameters": {"ef_construction": 128, "m": 24},
        },
    }
