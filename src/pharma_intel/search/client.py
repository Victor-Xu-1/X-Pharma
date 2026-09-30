from __future__ import annotations

import math
import re
import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, cast
from urllib.parse import urlparse

import structlog
from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import OpenSearchException

from pharma_intel.config import Settings, get_settings
from pharma_intel.models import EntityType, ReviewStatus
from pharma_intel.schemas import ENTITY_SORT_FIELDS, EntitySortField, SortDirection
from pharma_intel.search.contracts import (
    EntitySearchPage,
    EvidenceMatch,
    OpenSearchStatus,
    ProjectionDocument,
)
from pharma_intel.search.embedding import (
    EmbeddingGatewayError,
    OpenAICompatibleEmbeddingGateway,
    TextEmbedder,
)
from pharma_intel.search.mappings import (
    ENTITY_INDEX,
    EVIDENCE_INDEX,
    SCHEMA_VERSION,
    IndexDefinition,
    index_definitions,
    index_template,
)
from pharma_intel.sorting import SortClause, validate_sort_clauses


class SearchProjectionError(RuntimeError):
    """Raised when the rebuildable search projection is unavailable or invalid."""


_NON_AUTHORITATIVE_INDEX_MARKERS = ("-acceptance-", "-browser-", "-fixture-", "-test-")
_EXACT_IDENTITY_RANK_SOURCE = """
double exactRank = 0.0;
double identityAnchor = doc['external_id_values'].size() == 0 ? 0.0 : 3.0;
if (doc['normalized_name'].size() != 0 && doc['normalized_name'].value == params.query) {
    exactRank = 3.0 + identityAnchor;
} else if (doc['external_id_values'].size() != 0 && doc['external_id_values'].contains(params.query)) {
    exactRank = 5.0;
} else if (doc['aliases.keyword'].size() != 0 && doc['aliases.keyword'].contains(params.query)) {
    exactRank = 2.0 + identityAnchor;
}
""".strip()


class OpenSearchGateway:
    def __init__(
        self,
        settings: Settings,
        client: OpenSearch | None = None,
        embedder: TextEmbedder | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or _build_client(settings)
        self.embedder = embedder
        if self.settings.search_semantic_enabled and self.embedder is None:
            try:
                self.embedder = OpenAICompatibleEmbeddingGateway(settings)
            except EmbeddingGatewayError as exc:
                raise SearchProjectionError(f"Could not configure embedding gateway: {exc}") from exc

    def assert_compatible(self) -> dict[str, Any]:
        try:
            info = cast(dict[str, Any], self.client.info())
        except OpenSearchException as exc:
            raise SearchProjectionError(f"OpenSearch connection failed: {exc}") from exc
        version = str((info.get("version") or {}).get("number", ""))
        if not re.fullmatch(r"3\.\d+\.\d+(?:[-+].+)?", version):
            raise SearchProjectionError(f"OpenSearch 3.x is required; cluster reported {version or 'unknown'}")
        return info

    def ensure_indices(self) -> dict[str, str]:
        self._prepare_templates()
        for definition in index_definitions(self.settings):
            try:
                self._ensure_aliases(definition)
            except OpenSearchException as exc:
                raise SearchProjectionError(f"Could not initialize {definition.kind} index: {exc}") from exc
        active = self._active_alias_targets()
        self._assert_semantic_index_contract(active)
        return active

    def status(self) -> OpenSearchStatus:
        aliases: dict[str, list[str]] = {definition.kind: [] for definition in index_definitions(self.settings)}
        try:
            info = self.assert_compatible()
            health = cast(dict[str, Any], self.client.cluster.health())
            for definition in index_definitions(self.settings):
                aliases[definition.kind] = self.alias_indices(definition.kind)
            active = self._validate_alias_targets(aliases)
            self._assert_semantic_index_contract(active)
            return OpenSearchStatus(
                available=True,
                version=str((info.get("version") or {}).get("number", "")),
                cluster_name=str(info.get("cluster_name", "")),
                cluster_status=str(health.get("status", "")),
                aliases=aliases,
            )
        except (OpenSearchException, SearchProjectionError) as exc:
            return OpenSearchStatus(False, None, None, None, aliases, str(exc))

    def alias_indices(self, kind: str) -> list[str]:
        alias = self.read_alias(kind)
        try:
            response = cast(dict[str, Any], self.client.indices.get_alias(name=alias))
        except OpenSearchException as exc:
            if _is_not_found(exc):
                return []
            raise
        return sorted(response)

    def create_rebuild_indices(self, build_id: str | None = None) -> dict[str, str]:
        self._prepare_templates()
        suffix = build_id or f"{datetime.now(UTC):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}"
        targets: dict[str, str] = {}
        for definition in index_definitions(self.settings):
            index_name = f"{self._physical_prefix(definition.kind)}-{suffix}"
            try:
                self.client.indices.create(index=index_name)
            except OpenSearchException as exc:
                raise SearchProjectionError(f"Could not create rebuild index {index_name}: {exc}") from exc
            targets[definition.kind] = index_name
        return targets

    def swap_rebuild_indices(self, targets: dict[str, str]) -> None:
        expected = {definition.kind for definition in index_definitions(self.settings)}
        if set(targets) != expected:
            raise ValueError("Rebuild target set does not match the configured projections")
        actions: list[dict[str, Any]] = []
        for kind, target in targets.items():
            read_alias = self.read_alias(kind)
            write_alias = self.write_alias(kind)
            for index_name in self._indices_for_aliases(read_alias, write_alias):
                actions.extend(
                    [
                        {"remove": {"index": index_name, "alias": read_alias, "must_exist": False}},
                        {"remove": {"index": index_name, "alias": write_alias, "must_exist": False}},
                    ]
                )
            actions.extend(
                [
                    {"add": {"index": target, "alias": read_alias}},
                    {"add": {"index": target, "alias": write_alias, "is_write_index": True}},
                ]
            )
        try:
            self.client.indices.update_aliases(body={"actions": actions})
        except OpenSearchException as exc:
            raise SearchProjectionError(f"Could not atomically activate rebuilt indexes: {exc}") from exc

    def bulk_index(
        self,
        documents: list[ProjectionDocument],
        *,
        targets: dict[str, str] | None = None,
        refresh: bool = False,
    ) -> int:
        if not documents:
            return 0
        prepared = self._embed_documents(documents)
        actions = [
            {
                "_op_type": "index",
                "_index": (targets or {}).get(document.kind, self.write_alias(document.kind)),
                "_id": document.document_id,
                "_routing": document.tenant_id,
                "_source": document.source,
            }
            for document in prepared
        ]
        try:
            succeeded, _ = helpers.bulk(
                self.client,
                actions,
                chunk_size=min(500, len(actions)),
                max_retries=self.settings.opensearch_max_retries,
                raise_on_error=True,
                raise_on_exception=True,
                refresh=refresh,
                request_timeout=self.settings.opensearch_request_timeout_seconds,
            )
        except OpenSearchException as exc:
            raise SearchProjectionError(f"OpenSearch bulk projection failed: {exc}") from exc
        return int(succeeded)

    def replace_source_chunks(
        self,
        tenant_id: str,
        source_asset_id: str,
        source_version_id: str,
        documents: list[ProjectionDocument],
    ) -> int:
        indexed = self.bulk_index(documents, refresh=False)
        query = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"tenant_id": tenant_id}},
                        {"term": {"source_asset_id": source_asset_id}},
                        {"term": {"document_kind": "source_chunk"}},
                    ],
                    "must_not": [{"term": {"source_version_id": source_version_id}}],
                }
            }
        }
        try:
            self.client.delete_by_query(
                index=self.write_alias(EVIDENCE_INDEX),
                body=query,
                routing=tenant_id,
                conflicts="proceed",
                refresh=True,
            )
        except OpenSearchException as exc:
            raise SearchProjectionError(f"Could not retire superseded evidence chunks: {exc}") from exc
        return indexed

    def delete_source_asset_evidence(self, tenant_id: str, source_asset_id: str) -> int:
        query = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"tenant_id": tenant_id}},
                        {"term": {"source_asset_id": source_asset_id}},
                    ]
                }
            }
        }
        try:
            response = cast(
                dict[str, Any],
                self.client.delete_by_query(
                    index=self.write_alias(EVIDENCE_INDEX),
                    body=query,
                    routing=tenant_id,
                    conflicts="proceed",
                    refresh=True,
                ),
            )
        except OpenSearchException as exc:
            raise SearchProjectionError(f"Could not withdraw source evidence: {exc}") from exc
        failures = response.get("failures") or []
        if failures:
            raise SearchProjectionError("OpenSearch source withdrawal reported shard failures")
        return int(response.get("deleted", 0))

    def delete_evidence_claim(self, tenant_id: str, evidence_claim_id: str) -> bool:
        try:
            response = cast(
                dict[str, Any],
                self.client.delete(
                    index=self.write_alias(EVIDENCE_INDEX),
                    id=f"{tenant_id}:claim:{evidence_claim_id}",
                    routing=tenant_id,
                    refresh=True,
                    ignore=[404],
                ),
            )
        except OpenSearchException as exc:
            raise SearchProjectionError(f"Could not withdraw evidence claim: {exc}") from exc
        result = response.get("result")
        if result not in {"deleted", "not_found"}:
            raise SearchProjectionError("OpenSearch evidence-claim withdrawal returned an invalid result")
        return str(result) == "deleted"

    def search_entities(
        self,
        tenant_id: str,
        query: str | None,
        entity_types: EntityType | Sequence[EntityType] | None,
        limit: int,
        offset: int,
        review_status: ReviewStatus | None = None,
        sort_by: EntitySortField = "relevance",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[EntitySortField]] | None = None,
        facet_review_status: ReviewStatus | None = None,
    ) -> EntitySearchPage:
        effective_sort = validate_sort_clauses(
            sort,
            ENTITY_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        tenant_filter: dict[str, Any] = {"term": {"tenant_id": tenant_id}}
        filters: list[dict[str, Any]] = []
        selected_types = (
            [entity_types]
            if isinstance(entity_types, EntityType)
            else list(entity_types)
            if entity_types is not None
            else []
        )
        if len(selected_types) == 1:
            filters.append({"term": {"entity_type": selected_types[0].value}})
        elif selected_types:
            filters.append({"terms": {"entity_type": [item.value for item in selected_types]}})
        if review_status is not None:
            filters.append({"term": {"review_status": review_status.value}})
        search_parameters: dict[str, Any] = {}
        retrieval_mode = "lexical"
        if query:
            normalized = query.strip()
            lexical_query: dict[str, Any] = {
                "bool": {
                    "should": [
                        {"term": {"normalized_name": {"value": normalized.casefold(), "boost": 20}}},
                        {"term": {"external_id_values": {"value": normalized.casefold(), "boost": 18}}},
                        {"match_phrase": {"name": {"query": normalized, "boost": 12}}},
                        {"match_phrase": {"aliases": {"query": normalized, "boost": 10}}},
                        {
                            "multi_match": {
                                "query": normalized,
                                "fields": [
                                    "name^8",
                                    "aliases^6",
                                    "name.autocomplete^5",
                                    "aliases.autocomplete^4",
                                    "description",
                                ],
                                "type": "best_fields",
                                "operator": "and",
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            }
            if self.settings.search_semantic_enabled and effective_sort[0].field == "relevance":
                candidate_count = self._hybrid_candidate_count(offset, limit)
                query_clause = {
                    "hybrid": {
                        "pagination_depth": candidate_count,
                        "queries": [
                            lexical_query,
                            {
                                "knn": {
                                    "embedding": {
                                        "vector": self._embed_query(normalized),
                                        "min_score": self.settings.search_semantic_min_score,
                                    }
                                }
                            },
                        ],
                        "filter": tenant_filter,
                    }
                }
                search_parameters["search_pipeline"] = self.hybrid_pipeline_name
                retrieval_mode = "hybrid"
            else:
                lexical_query["bool"]["filter"] = [tenant_filter]
                query_clause = lexical_query
        else:
            query_clause = {"bool": {"filter": [tenant_filter]}}
        sort_fields = {
            "name": "normalized_name",
            "entity_type": "entity_type",
            "updated_at": "updated_at",
        }
        sort_spec: list[dict[str, Any]] = []
        exact_identity_sort = bool(query and effective_sort[0].field == "relevance")
        if exact_identity_sort and query is not None:
            normalized_query = query.strip().casefold()
            if retrieval_mode == "hybrid":
                relevance_fraction = (
                    "0.5 * relevance / (1.0 + relevance)"
                    if effective_sort[0].direction == "desc"
                    else "0.5 / (1.0 + relevance)"
                )
                sort_spec.append(
                    {
                        "_script": {
                            "type": "number",
                            "order": "desc",
                            "script": {
                                "lang": "painless",
                                "source": (
                                    f"{_EXACT_IDENTITY_RANK_SOURCE}\n"
                                    "double relevance = Math.max(_score, 0.0);\n"
                                    f"return exactRank + ({relevance_fraction});"
                                ),
                                "params": {"query": normalized_query},
                            },
                        }
                    }
                )
        for clause in effective_sort:
            if retrieval_mode == "hybrid" and exact_identity_sort and clause.field == "relevance":
                continue
            if clause.field == "relevance":
                sort_spec.append({"_score": {"order": clause.direction}})
            else:
                sort_spec.append({sort_fields[clause.field]: {"order": clause.direction, "missing": "_last"}})
        if exact_identity_sort and retrieval_mode != "hybrid" and query is not None:
            sort_spec.insert(
                0,
                {
                    "_script": {
                        "type": "number",
                        "order": "desc",
                        "script": {
                            "lang": "painless",
                            "source": f"{_EXACT_IDENTITY_RANK_SOURCE}\nreturn exactRank;",
                            "params": {"query": query.strip().casefold()},
                        },
                    }
                },
            )
        if retrieval_mode != "hybrid" or exact_identity_sort or len(effective_sort) > 1:
            if not any(clause.field == "name" for clause in effective_sort):
                sort_spec.append({"normalized_name": {"order": "asc"}})
            sort_spec.append({"entity_id": {"order": "asc"}})
        aggregations: dict[str, Any] = {
            "entity_types": {"terms": {"field": "entity_type", "size": 50}},
            "review_statuses": {"terms": {"field": "review_status", "size": 20}},
        }
        facet_filters: list[dict[str, Any]] = [tenant_filter]
        if facet_review_status is not None:
            facet_filters.append({"term": {"review_status": facet_review_status.value}})
        facet_visibility: dict[str, Any] = {"bool": {"filter": facet_filters}}
        if query:
            # Facet counts must describe the current keyword result set. Keep the
            # selected entity type in post_filter so sibling types remain available
            # as filter choices, while still applying the lexical query to counts.
            facet_visibility["bool"]["must"] = [lexical_query]
        aggregations = {
            "entity_types": {
                "filter": facet_visibility,
                "aggs": {"values": {"terms": {"field": "entity_type", "size": 50}}},
            },
            "review_statuses": {
                "filter": facet_visibility,
                "aggs": {"values": {"terms": {"field": "review_status", "size": 20}}},
            },
        }
        body: dict[str, Any] = {
            "from": offset,
            "size": limit,
            "track_total_hits": True,
            "query": query_clause,
            "sort": sort_spec,
            "aggs": aggregations,
            "_source": {"includes": ["entity_id", "name", "entity_type"], "excludes": ["embedding"]},
        }
        if retrieval_mode == "hybrid" and exact_identity_sort:
            body["track_scores"] = False
        if filters:
            body["post_filter"] = {"bool": {"filter": filters}}
        try:
            response = cast(
                dict[str, Any],
                self.client.search(
                    index=self.read_alias(ENTITY_INDEX),
                    routing=tenant_id,
                    body=body,
                    params=search_parameters,
                    request_timeout=self.settings.opensearch_request_timeout_seconds,
                ),
            )
        except OpenSearchException as exc:
            raise SearchProjectionError(f"Entity search failed: {exc}") from exc
        hits_block = cast(dict[str, Any], response.get("hits") or {})
        hits = cast(list[dict[str, Any]], hits_block.get("hits") or [])
        total_raw = hits_block.get("total") or 0
        total = int(total_raw.get("value", 0)) if isinstance(total_raw, dict) else int(total_raw)
        aggregation_response = cast(dict[str, Any], response.get("aggregations") or {})

        def facet_buckets(name: str) -> list[dict[str, Any]]:
            aggregation = cast(dict[str, Any], aggregation_response.get(name) or {})
            if isinstance(aggregation.get("values"), dict):
                aggregation = cast(dict[str, Any], aggregation.get("values") or {})
            return cast(list[dict[str, Any]], aggregation.get("buckets") or [])

        buckets = facet_buckets("entity_types")
        review_buckets = facet_buckets("review_statuses")
        suggestions = list(
            dict.fromkeys(
                str((hit.get("_source") or {}).get("name", ""))
                for hit in hits
                if (hit.get("_source") or {}).get("name")
            )
        )[:10]
        return EntitySearchPage(
            entity_ids=[str((hit.get("_source") or {}).get("entity_id", "")) for hit in hits],
            total=total,
            facets={
                "entity_type": {str(bucket["key"]): int(bucket["doc_count"]) for bucket in buckets},
                "review_status": {str(bucket["key"]): int(bucket["doc_count"]) for bucket in review_buckets},
            },
            suggestions=suggestions,
            engine="opensearch-hybrid" if retrieval_mode == "hybrid" else "opensearch",
            took_ms=int(response.get("took", 0)),
        )

    def search_evidence(
        self,
        tenant_id: str,
        query: str,
        dataset_keys: list[str],
        limit: int,
        offset: int = 0,
    ) -> list[EvidenceMatch]:
        filters: list[dict[str, Any]] = [{"term": {"tenant_id": tenant_id}}]
        if dataset_keys:
            filters.append({"terms": {"dataset_key": dataset_keys}})
        lexical_query: dict[str, Any] = {
            "multi_match": {
                "query": query,
                "fields": ["title^3", "content", "predicate^2"],
                "type": "best_fields",
                "operator": "and",
            }
        }
        search_parameters: dict[str, Any] = {}
        retrieval_mode = "lexical"
        if self.settings.search_semantic_enabled:
            vector = self._embed_query(query)
            candidate_count = self._hybrid_candidate_count(offset, limit)
            filter_query: dict[str, Any]
            if len(filters) == 1:
                filter_query = filters[0]
            else:
                filter_query = {"bool": {"filter": filters}}
            query_clause: dict[str, Any] = {
                "hybrid": {
                    "pagination_depth": candidate_count,
                    "queries": [
                        lexical_query,
                        {
                            "knn": {
                                "embedding": {
                                    "vector": vector,
                                    "min_score": self.settings.search_semantic_min_score,
                                }
                            }
                        },
                    ],
                    "filter": filter_query,
                }
            }
            search_parameters["search_pipeline"] = self.hybrid_pipeline_name
            retrieval_mode = "hybrid"
        else:
            query_clause = {
                "bool": {
                    "filter": filters,
                    "must": [lexical_query],
                }
            }
        body = {
            "size": limit,
            "from": offset,
            "track_total_hits": False,
            "query": query_clause,
            "sort": (
                [{"_score": {"order": "desc"}}]
                if self.settings.search_semantic_enabled
                else [{"_score": {"order": "desc"}}, {"projection_id": {"order": "asc"}}]
            ),
            "_source": {"excludes": ["embedding"]},
        }
        try:
            response = cast(
                dict[str, Any],
                self.client.search(
                    index=self.read_alias(EVIDENCE_INDEX),
                    routing=tenant_id,
                    body=body,
                    params=search_parameters,
                    request_timeout=self.settings.opensearch_request_timeout_seconds,
                ),
            )
        except OpenSearchException as exc:
            raise SearchProjectionError(f"Evidence search failed: {exc}") from exc
        hits = cast(list[dict[str, Any]], ((response.get("hits") or {}).get("hits") or []))
        matches: list[EvidenceMatch] = []
        for hit in hits:
            source = cast(dict[str, Any], hit.get("_source") or {})
            positions = [
                {
                    "start_char": source.get("start_char"),
                    "end_char": source.get("end_char"),
                    "locator_kind": source.get("locator_kind"),
                    "locator_value": source.get("locator_value"),
                }
            ]
            matches.append(
                EvidenceMatch(
                    content=str(source.get("content", "")),
                    document_id=str(source.get("source_document_id", "")),
                    document_name=str(source.get("title", "")),
                    dataset_key=str(source.get("dataset_key", "")),
                    score=float(hit["_score"]) if hit.get("_score") is not None else None,
                    positions=positions,
                    metadata={
                        "source": source.get("source_uri"),
                        "source_version_id": source.get("source_version_id"),
                        "source_asset_id": source.get("source_asset_id"),
                        "content_sha256": source.get("content_sha256"),
                        "evidence_claim_id": source.get("evidence_claim_id"),
                        "subject_entity_id": source.get("subject_entity_id"),
                        "review_status": source.get("review_status"),
                        "retrieval_mode": retrieval_mode,
                        "embedding_model": source.get("embedding_model"),
                    },
                )
            )
        return matches

    def refresh(self, targets: dict[str, str] | None = None) -> None:
        indexes = list(
            (
                targets
                or {
                    definition.kind: self.read_alias(definition.kind) for definition in index_definitions(self.settings)
                }
            ).values()
        )
        try:
            self.client.indices.refresh(index=",".join(indexes))
        except OpenSearchException as exc:
            raise SearchProjectionError(f"Could not refresh search projections: {exc}") from exc

    def count(self, kind: str, *, target: str | None = None) -> int:
        try:
            response = cast(dict[str, Any], self.client.count(index=target or self.read_alias(kind)))
        except OpenSearchException as exc:
            raise SearchProjectionError(f"Could not count {kind} projection: {exc}") from exc
        return int(response.get("count", 0))

    def read_alias(self, kind: str) -> str:
        return f"{self.settings.opensearch_index_prefix}-{kind}"

    def write_alias(self, kind: str) -> str:
        return f"{self.settings.opensearch_index_prefix}-{kind}-write"

    def assert_projection_ready(self) -> None:
        self.assert_compatible()
        self._assert_semantic_index_contract(self._active_alias_targets())

    @property
    def hybrid_pipeline_name(self) -> str:
        return f"{self.settings.opensearch_index_prefix}-hybrid-v{SCHEMA_VERSION}"

    def _template_name(self, definition: IndexDefinition) -> str:
        return f"{self.settings.opensearch_index_prefix}-{definition.kind}-template-v{SCHEMA_VERSION}"

    def _physical_prefix(self, kind: str) -> str:
        return f"{self.settings.opensearch_index_prefix}-{kind}-v{SCHEMA_VERSION}"

    def _ensure_hybrid_pipeline(self) -> None:
        try:
            self.client.transport.perform_request(
                "PUT",
                f"/_search/pipeline/{self.hybrid_pipeline_name}",
                body=self._hybrid_pipeline_body(),
            )
        except OpenSearchException as exc:
            raise SearchProjectionError(f"Could not initialize hybrid search pipeline: {exc}") from exc

    def _hybrid_pipeline_body(self) -> dict[str, Any]:
        lexical_weight = self.settings.search_hybrid_lexical_weight
        return {
            "description": "Versioned pharmaceutical lexical and vector score normalization",
            "phase_results_processors": [
                {
                    "normalization-processor": {
                        "normalization": {"technique": "min_max"},
                        "combination": {
                            "technique": "arithmetic_mean",
                            "parameters": {"weights": [lexical_weight, 1.0 - lexical_weight]},
                        },
                    }
                }
            ],
        }

    def _assert_hybrid_pipeline_ready(self) -> None:
        try:
            response = cast(
                dict[str, Any],
                self.client.transport.perform_request(
                    "GET",
                    f"/_search/pipeline/{self.hybrid_pipeline_name}",
                ),
            )
        except OpenSearchException as exc:
            raise SearchProjectionError(f"Hybrid search pipeline is unavailable: {exc}") from exc
        if response.get(self.hybrid_pipeline_name) != self._hybrid_pipeline_body():
            raise SearchProjectionError("Hybrid search pipeline does not match the configured scoring contract")

    def _prepare_templates(self) -> None:
        self.assert_compatible()
        if self.settings.search_semantic_enabled:
            self._ensure_hybrid_pipeline()
        for definition in index_definitions(self.settings):
            try:
                self.client.indices.put_index_template(
                    name=self._template_name(definition),
                    body=index_template(self.settings, definition),
                )
            except OpenSearchException as exc:
                raise SearchProjectionError(f"Could not initialize {definition.kind} template: {exc}") from exc

    def _assert_semantic_alias_versions(self, aliases: dict[str, str]) -> None:
        if not self.settings.search_semantic_enabled:
            return
        stale = [
            index_name
            for kind, index_name in aliases.items()
            if not index_name.startswith(f"{self._physical_prefix(kind)}-")
        ]
        if stale:
            raise SearchProjectionError("Semantic search requires an atomic rebuild to the current vector index schema")

    def _assert_runtime_alias_versions(self, aliases: dict[str, str]) -> None:
        stale = [
            f"{kind}={index_name}"
            for kind, index_name in aliases.items()
            if not index_name.startswith(f"{self._physical_prefix(kind)}-")
        ]
        if stale:
            raise SearchProjectionError(
                "OpenSearch projection aliases do not match the current schema; run an atomic rebuild: "
                + ", ".join(sorted(stale))
            )

    def _assert_authoritative_aliases(self, aliases: dict[str, str]) -> None:
        if self.settings.search_allow_non_authoritative_projection:
            return
        unsafe = [
            f"{kind}={index_name}"
            for kind, index_name in aliases.items()
            if any(marker in index_name for marker in _NON_AUTHORITATIVE_INDEX_MARKERS)
        ]
        if unsafe:
            raise SearchProjectionError(
                "OpenSearch projection aliases point to a non-authoritative acceptance/test index: "
                + ", ".join(sorted(unsafe))
            )

    def _assert_semantic_mapping_contract(self, aliases: dict[str, str]) -> None:
        try:
            response = cast(
                dict[str, Any],
                self.client.indices.get_mapping(index=",".join(sorted(aliases.values()))),
            )
        except OpenSearchException as exc:
            raise SearchProjectionError(f"Could not inspect semantic index mappings: {exc}") from exc
        invalid: list[str] = []
        for kind, index_name in aliases.items():
            mappings = cast(dict[str, Any], (response.get(index_name) or {}).get("mappings") or {})
            metadata = cast(dict[str, Any], mappings.get("_meta") or {})
            properties = cast(dict[str, Any], mappings.get("properties") or {})
            embedding = cast(dict[str, Any], properties.get("embedding") or {})
            if (
                metadata.get("schema_version") != SCHEMA_VERSION
                or metadata.get("projection") != kind
                or metadata.get("embedding_model") != self.settings.search_embedding_model
                or embedding.get("type") != "knn_vector"
                or embedding.get("dimension") != self.settings.search_embedding_dimensions
            ):
                invalid.append(kind)
        if invalid:
            raise SearchProjectionError(
                "Semantic index mappings do not match the configured schema: " + ", ".join(sorted(invalid))
            )

    def _assert_semantic_index_contract(self, aliases: dict[str, str]) -> None:
        if self.settings.search_semantic_enabled:
            self._assert_semantic_alias_versions(aliases)
        else:
            self._assert_runtime_alias_versions(aliases)
        self._assert_authoritative_aliases(aliases)
        if not self.settings.search_semantic_enabled:
            return
        self._required_embedder()
        self._assert_semantic_mapping_contract(aliases)
        self._assert_hybrid_pipeline_ready()

    def _active_alias_targets(self) -> dict[str, str]:
        aliases = {
            definition.kind: self.alias_indices(definition.kind) for definition in index_definitions(self.settings)
        }
        return self._validate_alias_targets(aliases)

    def _validate_alias_targets(self, aliases: dict[str, list[str]]) -> dict[str, str]:
        if any(len(indexes) != 1 for indexes in aliases.values()):
            raise SearchProjectionError("OpenSearch projection aliases must each resolve to exactly one active index")
        return {kind: indexes[0] for kind, indexes in aliases.items()}

    def _embed_documents(self, documents: Sequence[ProjectionDocument]) -> list[ProjectionDocument]:
        if not self.settings.search_semantic_enabled:
            return list(documents)
        embedder = self._required_embedder()
        prepared: list[ProjectionDocument] = []
        batch_size = self.settings.search_embedding_batch_size
        for start in range(0, len(documents), batch_size):
            batch = list(documents[start : start + batch_size])
            texts = [self._embedding_text(document) for document in batch]
            try:
                vectors = embedder.embed(texts)
            except EmbeddingGatewayError as exc:
                raise SearchProjectionError(f"Document embedding failed: {exc}") from exc
            if len(vectors) != len(batch):
                raise SearchProjectionError("Embedding gateway returned the wrong document count")
            for document, vector in zip(batch, vectors, strict=True):
                self._validate_embedding_dimensions(vector, embedder)
                prepared.append(
                    replace(
                        document,
                        source={
                            **document.source,
                            "embedding": vector,
                            "embedding_model": embedder.model,
                        },
                    )
                )
        return prepared

    def _embed_query(self, query: str) -> list[float]:
        embedder = self._required_embedder()
        try:
            vectors = embedder.embed([query[: self.settings.search_embedding_max_input_chars]])
        except EmbeddingGatewayError as exc:
            raise SearchProjectionError(f"Query embedding failed: {exc}") from exc
        if len(vectors) != 1:
            raise SearchProjectionError("Embedding gateway returned the wrong query count")
        self._validate_embedding_dimensions(vectors[0], embedder)
        return vectors[0]

    def _hybrid_candidate_count(self, offset: int, limit: int) -> int:
        candidate_count = self.settings.search_hybrid_max_candidates
        if offset + limit > candidate_count:
            raise SearchProjectionError("Hybrid search pagination window exceeds the configured candidate limit")
        return candidate_count

    def _required_embedder(self) -> TextEmbedder:
        if self.embedder is None:
            raise SearchProjectionError("Semantic search is enabled without an embedding gateway")
        if self.embedder.model != self.settings.search_embedding_model:
            raise SearchProjectionError("Embedding gateway model does not match the index contract")
        if self.embedder.dimensions != self.settings.search_embedding_dimensions:
            raise SearchProjectionError("Embedding gateway dimensions do not match the index contract")
        return self.embedder

    def _validate_embedding_dimensions(self, vector: list[float], embedder: TextEmbedder) -> None:
        if len(vector) != embedder.dimensions:
            raise SearchProjectionError("Embedding vector dimensions do not match the index contract")
        if any(not math.isfinite(value) for value in vector):
            raise SearchProjectionError("Embedding vector contains a non-finite value")
        if not any(value != 0 for value in vector):
            raise SearchProjectionError("Embedding vector cannot be the zero vector")

    def _embedding_text(self, document: ProjectionDocument) -> str:
        values: list[str] = []
        for key in ("name", "aliases", "description", "title", "content", "predicate"):
            value = document.source.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
            elif isinstance(value, list):
                values.extend(str(item).strip() for item in value if str(item).strip())
        text = "\n".join(values)
        if not text:
            raise SearchProjectionError(f"{document.kind} projection has no embeddable text")
        return text[: self.settings.search_embedding_max_input_chars]

    def _ensure_aliases(self, definition: IndexDefinition, *, allow_creation: bool = True) -> str:
        read_alias = self.read_alias(definition.kind)
        write_alias = self.write_alias(definition.kind)
        current = self.alias_indices(definition.kind)
        if current:
            write_indices = self._indices_for_aliases(write_alias)
            if not write_indices:
                self.client.indices.update_aliases(
                    body={"actions": [{"add": {"index": current[0], "alias": write_alias, "is_write_index": True}}]}
                )
            return current[0]
        initial = f"{self._physical_prefix(definition.kind)}-000001"
        if bool(self.client.indices.exists(index=initial)):
            self.client.indices.update_aliases(
                body={
                    "actions": [
                        {"add": {"index": initial, "alias": read_alias}},
                        {"add": {"index": initial, "alias": write_alias, "is_write_index": True}},
                    ]
                }
            )
        else:
            if not allow_creation:
                raise SearchProjectionError(
                    f"Concurrent initial {definition.kind} index disappeared before reconciliation"
                )
            try:
                self.client.indices.create(
                    index=initial,
                    body={
                        "aliases": {
                            read_alias: {},
                            write_alias: {"is_write_index": True},
                        }
                    },
                )
            except OpenSearchException as exc:
                if (
                    getattr(exc, "status_code", None) != 400
                    or getattr(exc, "error", None) != "resource_already_exists_exception"
                ):
                    raise
                # Another role may initialize or rebuild while this role checks existence.
                # Re-read the authoritative aliases once; never overwrite a newer winner.
                structlog.get_logger(__name__).info(
                    "search_index_creation_reconciled", kind=definition.kind, index=initial
                )
                return self._ensure_aliases(definition, allow_creation=False)
        return initial

    def _indices_for_aliases(self, *aliases: str) -> list[str]:
        indexes: set[str] = set()
        for alias in aliases:
            try:
                response = cast(dict[str, Any], self.client.indices.get_alias(name=alias))
            except OpenSearchException as exc:
                if _is_not_found(exc):
                    continue
                raise
            indexes.update(response)
        return sorted(indexes)


def _build_client(settings: Settings) -> OpenSearch:
    parsed = urlparse(settings.opensearch_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path not in {"", "/"}:
        raise SearchProjectionError("OPENSEARCH_URL must be an HTTP(S) cluster root URL")
    auth = None
    if settings.opensearch_username or settings.opensearch_password:
        if not settings.opensearch_username or not settings.opensearch_password:
            raise SearchProjectionError("OpenSearch username and password must be configured together")
        auth = (settings.opensearch_username, settings.opensearch_password)
    elif settings.app_env.lower() == "production":
        raise SearchProjectionError("Production OpenSearch client credentials are not configured")
    options: dict[str, Any] = {
        "hosts": [
            {
                "host": parsed.hostname,
                "port": parsed.port or (443 if parsed.scheme == "https" else 80),
                "scheme": parsed.scheme,
            }
        ],
        "http_auth": auth,
        "use_ssl": parsed.scheme == "https",
        "verify_certs": settings.opensearch_verify_certs if parsed.scheme == "https" else False,
        "ssl_assert_hostname": settings.opensearch_verify_certs if parsed.scheme == "https" else False,
        "http_compress": True,
        "timeout": settings.opensearch_request_timeout_seconds,
        "max_retries": settings.opensearch_max_retries,
        "pool_maxsize": settings.opensearch_pool_maxsize,
        "retry_on_timeout": True,
    }
    if settings.opensearch_ca_certs:
        options["ca_certs"] = settings.opensearch_ca_certs
    return OpenSearch(**options)


def _is_not_found(exc: OpenSearchException) -> bool:
    return getattr(exc, "status_code", None) == 404


@lru_cache
def get_opensearch_gateway() -> OpenSearchGateway:
    return OpenSearchGateway(get_settings())
