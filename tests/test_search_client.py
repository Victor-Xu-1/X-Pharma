from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import pytest
from opensearchpy import OpenSearch
from opensearchpy.exceptions import OpenSearchException, RequestError

from pharma_intel.config import Settings
from pharma_intel.models import EntityType, ReviewStatus
from pharma_intel.search.client import OpenSearchGateway, SearchProjectionError, _build_client
from pharma_intel.search.contracts import ProjectionDocument
from pharma_intel.search.mappings import SCHEMA_VERSION
from pharma_intel.sorting import SortClause


class FakeNotFound(OpenSearchException):
    status_code = 404


class FakeCluster:
    def health(self) -> dict[str, str]:
        return {"status": "green"}


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.pipelines: dict[str, dict[str, Any]] = {}

    def perform_request(self, method: str, path: str, *, body: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((method, path, body))
        pipeline_name = path.rsplit("/", maxsplit=1)[-1]
        if method == "PUT":
            assert body is not None
            self.pipelines[pipeline_name] = body
        elif method == "GET":
            if pipeline_name not in self.pipelines:
                raise FakeNotFound("pipeline missing")
            return {pipeline_name: self.pipelines[pipeline_name]}
        elif method == "DELETE":
            self.pipelines.pop(pipeline_name, None)
        return {"acknowledged": True}


class FakeIndices:
    def __init__(self) -> None:
        self.templates: dict[str, dict[str, Any]] = {}
        self.indexes: set[str] = set()
        self.aliases: dict[str, set[str]] = {}
        self.alias_actions: list[list[dict[str, Any]]] = []
        self.refreshed: list[str] = []
        self.mapping_overrides: dict[str, dict[str, Any]] = {}

    def put_index_template(self, *, name: str, body: dict[str, Any]) -> dict[str, bool]:
        self.templates[name] = body
        return {"acknowledged": True}

    def get_alias(self, *, name: str) -> dict[str, dict[str, Any]]:
        indexes = self.aliases.get(name)
        if not indexes:
            raise FakeNotFound("alias missing")
        return {index: {} for index in indexes}

    def get_mapping(self, *, index: str) -> dict[str, dict[str, Any]]:
        response: dict[str, dict[str, Any]] = {}
        for index_name in index.split(","):
            if index_name in self.mapping_overrides:
                response[index_name] = {"mappings": self.mapping_overrides[index_name]}
                continue
            for template in self.templates.values():
                patterns = template.get("index_patterns", [])
                if any(pattern.endswith("*") and index_name.startswith(pattern[:-1]) for pattern in patterns):
                    response[index_name] = {"mappings": template["template"]["mappings"]}
                    break
        return response

    def exists(self, *, index: str) -> bool:
        return index in self.indexes

    def create(self, *, index: str, body: dict[str, Any] | None = None) -> dict[str, bool]:
        self.indexes.add(index)
        for alias in (body or {}).get("aliases", {}):
            self.aliases.setdefault(alias, set()).add(index)
        return {"acknowledged": True}

    def update_aliases(self, *, body: dict[str, list[dict[str, Any]]]) -> dict[str, bool]:
        actions = body["actions"]
        self.alias_actions.append(actions)
        for action in actions:
            if "remove" in action:
                operation = action["remove"]
                self.aliases.setdefault(str(operation["alias"]), set()).discard(str(operation["index"]))
            if "add" in action:
                operation = action["add"]
                self.aliases.setdefault(str(operation["alias"]), set()).add(str(operation["index"]))
        return {"acknowledged": True}

    def refresh(self, *, index: str) -> dict[str, bool]:
        self.refreshed.append(index)
        return {"acknowledged": True}


class FakeOpenSearch:
    def __init__(self, version: str = "3.7.0") -> None:
        self.version = version
        self.indices = FakeIndices()
        self.cluster = FakeCluster()
        self.transport = FakeTransport()
        self.search_responses: list[dict[str, Any]] = []
        self.search_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []

    def info(self) -> dict[str, Any]:
        return {"version": {"number": self.version}, "cluster_name": "test-search"}

    def search(self, **kwargs: Any) -> dict[str, Any]:
        self.search_calls.append(kwargs)
        return self.search_responses.pop(0)

    def delete_by_query(self, **kwargs: Any) -> dict[str, Any]:
        self.delete_calls.append(kwargs)
        return {"deleted": 2}

    def count(self, **_kwargs: Any) -> dict[str, int]:
        return {"count": 7}


def test_gateway_initializes_projects_searches_and_swaps_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        opensearch_index_prefix="contract",
        opensearch_max_retries=2,
        opensearch_request_timeout_seconds=9,
    )
    fake = FakeOpenSearch()
    gateway = OpenSearchGateway(settings, cast(OpenSearch, fake))

    initialized = gateway.ensure_indices()

    assert set(initialized) == {"entities", "evidence", "knowledge"}
    assert len(fake.indices.templates) == 3
    assert gateway.status().available is True
    assert gateway.status().aliases["entities"] == [f"contract-entities-v{SCHEMA_VERSION}-000001"]

    captured_actions: list[dict[str, Any]] = []

    def fake_bulk(_client: object, actions: list[dict[str, Any]], **kwargs: Any) -> tuple[int, list[Any]]:
        captured_actions.extend(actions)
        assert kwargs["chunk_size"] == 1
        assert kwargs["max_retries"] == 2
        assert kwargs["request_timeout"] == 9
        return len(actions), []

    monkeypatch.setattr("pharma_intel.search.client.helpers.bulk", fake_bulk)
    document = ProjectionDocument(
        kind="entities",
        document_id="entity-1",
        tenant_id="tenant-a",
        source={"entity_id": "entity-1", "tenant_id": "tenant-a", "name": "EGFR"},
    )
    assert gateway.bulk_index([]) == 0
    assert gateway.bulk_index([document]) == 1
    assert captured_actions[0]["_routing"] == "tenant-a"
    assert captured_actions[0]["_index"] == "contract-entities-write"

    evidence = ProjectionDocument(
        kind="evidence",
        document_id="chunk-1",
        tenant_id="tenant-a",
        source={"tenant_id": "tenant-a", "source_version_id": "version-2"},
    )
    assert gateway.replace_source_chunks("tenant-a", "asset-1", "version-2", [evidence]) == 1
    delete_call = fake.delete_calls[0]
    assert delete_call["routing"] == "tenant-a"
    assert delete_call["body"]["query"]["bool"]["must_not"] == [{"term": {"source_version_id": "version-2"}}]
    assert gateway.delete_source_asset_evidence("tenant-a", "asset-1") == 2
    withdrawal_call = fake.delete_calls[1]
    assert withdrawal_call["routing"] == "tenant-a"
    assert {"term": {"source_asset_id": "asset-1"}} in withdrawal_call["body"]["query"]["bool"]["filter"]

    fake.search_responses.extend(
        [
            {
                "took": 6,
                "hits": {
                    "total": {"value": 1},
                    "hits": [{"_source": {"entity_id": "entity-1", "name": "EGFR", "entity_type": "target"}}],
                },
                "aggregations": {
                    "entity_types": {"buckets": [{"key": "target", "doc_count": 1}]},
                    "review_statuses": {"buckets": [{"key": "verified", "doc_count": 1}]},
                },
            },
            {
                "hits": {
                    "hits": [
                        {
                            "_score": 3.5,
                            "_source": {
                                "content": "EGFR activity was measured.",
                                "source_document_id": "document-1",
                                "title": "EGFR assay",
                                "dataset_key": "literature",
                                "source_uri": "s3://evidence/document-1",
                                "source_version_id": "version-2",
                                "source_asset_id": "asset-1",
                                "content_sha256": "abc123",
                                "start_char": 10,
                                "end_char": 37,
                                "locator_kind": "page",
                                "locator_value": "4",
                            },
                        }
                    ]
                }
            },
        ]
    )
    entity_page = gateway.search_entities("tenant-a", "P00533", EntityType.TARGET, 25, 0, ReviewStatus.VERIFIED)
    assert entity_page.entity_ids == ["entity-1"]
    assert entity_page.facets == {
        "entity_type": {"target": 1},
        "review_status": {"verified": 1},
    }
    assert entity_page.suggestions == ["EGFR"]
    assert entity_page.took_ms == 6
    entity_request = fake.search_calls[0]
    assert entity_request["routing"] == "tenant-a"
    assert {"term": {"tenant_id": "tenant-a"}} in entity_request["body"]["query"]["bool"]["filter"]
    assert entity_request["body"]["aggs"]["entity_types"]["filter"]["bool"]["must"] == [entity_request["body"]["query"]]
    assert entity_request["body"]["post_filter"] == {
        "bool": {
            "filter": [
                {"term": {"entity_type": "target"}},
                {"term": {"review_status": "verified"}},
            ]
        }
    }

    matches = gateway.search_evidence("tenant-a", "EGFR activity", ["literature"], 5, 7)
    assert len(matches) == 1
    assert matches[0].document_id == "document-1"
    assert matches[0].positions == [{"start_char": 10, "end_char": 37, "locator_kind": "page", "locator_value": "4"}]
    assert matches[0].metadata["source_version_id"] == "version-2"
    assert matches[0].metadata["source_asset_id"] == "asset-1"
    assert fake.search_calls[1]["routing"] == "tenant-a"
    assert fake.search_calls[1]["body"]["from"] == 7

    targets = gateway.create_rebuild_indices("release-20260716")
    assert targets["entities"] == f"contract-entities-v{SCHEMA_VERSION}-release-20260716"
    with pytest.raises(ValueError, match="target set"):
        gateway.swap_rebuild_indices({"entities": targets["entities"]})
    gateway.swap_rebuild_indices(targets)
    assert gateway.alias_indices("entities") == [targets["entities"]]
    gateway.refresh(targets)
    assert set(fake.indices.refreshed[0].split(",")) == set(targets.values())
    assert gateway.count("entities", target=targets["entities"]) == 7


def test_entity_facets_can_be_clamped_to_review_visibility() -> None:
    settings = Settings(
        opensearch_index_prefix="contract",
        opensearch_max_retries=1,
        opensearch_request_timeout_seconds=5,
    )
    fake = FakeOpenSearch()
    fake.search_responses.append(
        {
            "hits": {"total": {"value": 0}, "hits": []},
            "aggregations": {
                "entity_types": {
                    "doc_count": 0,
                    "values": {"buckets": []},
                },
                "review_statuses": {
                    "doc_count": 0,
                    "values": {"buckets": []},
                },
            },
        },
    )
    gateway = OpenSearchGateway(settings, cast(OpenSearch, fake))

    page = gateway.search_entities(
        "tenant-a",
        "draft-only",
        None,
        5,
        0,
        facet_review_status=ReviewStatus.VERIFIED,
    )

    request = fake.search_calls[-1]
    facet_filter = request["body"]["aggs"]["review_statuses"]["filter"]["bool"]["filter"]
    assert {"term": {"review_status": "verified"}} in facet_filter
    assert request["body"]["aggs"]["review_statuses"]["filter"]["bool"]["must"] == [request["body"]["query"]]
    assert page.facets == {"entity_type": {}, "review_status": {}}


def test_entity_relevance_sort_prioritizes_exact_identity_signals() -> None:
    settings = Settings(
        _env_file=None,
        opensearch_index_prefix="contract",
        search_semantic_enabled=False,
    )
    fake = FakeOpenSearch()
    fake.search_responses.insert(
        0,
        {
            "hits": {"total": {"value": 0}, "hits": []},
            "aggregations": {
                "entity_types": {"buckets": []},
                "review_statuses": {"buckets": []},
            },
        },
    )
    gateway = OpenSearchGateway(settings, cast(OpenSearch, fake))

    gateway.search_entities("tenant-a", " EGFR ", EntityType.TARGET, 10, 0)

    sort = fake.search_calls[-1]["body"]["sort"]
    exact_sort = sort[0]["_script"]
    assert exact_sort["type"] == "number"
    assert exact_sort["order"] == "desc"
    assert exact_sort["script"]["params"] == {"query": "egfr"}
    source = exact_sort["script"]["source"]
    assert "normalized_name" in source
    assert "aliases.keyword" in source
    assert "external_id_values" in source
    assert "identityAnchor" in source
    assert "3.0 + identityAnchor" in source
    assert "2.0 + identityAnchor" in source
    assert sort[1:] == [
        {"_score": {"order": "desc"}},
        {"normalized_name": {"order": "asc"}},
        {"entity_id": {"order": "asc"}},
    ]


def test_gateway_rejects_incompatible_clusters_and_invalid_client_configuration() -> None:
    incompatible = OpenSearchGateway(Settings(), cast(OpenSearch, FakeOpenSearch("2.19.0")))
    with pytest.raises(SearchProjectionError, match="3.x is required"):
        incompatible.assert_compatible()
    status = incompatible.status()
    assert status.available is False
    assert status.error is not None

    with pytest.raises(SearchProjectionError, match="cluster root URL"):
        _build_client(Settings(opensearch_url="https://search.example.test/path"))
    with pytest.raises(SearchProjectionError, match="configured together"):
        _build_client(Settings(opensearch_username="search-user", opensearch_password=""))
    with pytest.raises(SearchProjectionError, match="Production OpenSearch client credentials"):
        _build_client(
            Settings(
                _env_file=None,
                app_env="production",
                opensearch_url="https://search.example.test",
                opensearch_verify_certs=True,
            )
        )


def test_nonsemantic_gateway_rejects_legacy_acceptance_projection_aliases() -> None:
    settings = Settings(_env_file=None, opensearch_index_prefix="contract")
    fake = FakeOpenSearch()
    for kind in ("entities", "evidence", "knowledge"):
        legacy = f"contract-{kind}-v1-acceptance-20260716"
        fake.indices.indexes.add(legacy)
        fake.indices.aliases[f"contract-{kind}"] = {legacy}
        fake.indices.aliases[f"contract-{kind}-write"] = {legacy}

    with pytest.raises(SearchProjectionError, match="current schema"):
        OpenSearchGateway(settings, cast(OpenSearch, fake)).ensure_indices()


def test_gateway_rejects_browser_projection_aliases_after_acceptance_cleanup() -> None:
    settings = Settings(_env_file=None, opensearch_index_prefix="contract")
    fake = FakeOpenSearch()
    for kind in ("entities", "evidence", "knowledge"):
        browser_index = f"contract-{kind}-v{SCHEMA_VERSION}-browser-20260803"
        fake.indices.indexes.add(browser_index)
        fake.indices.aliases[f"contract-{kind}"] = {browser_index}
        fake.indices.aliases[f"contract-{kind}-write"] = {browser_index}

    with pytest.raises(SearchProjectionError, match="non-authoritative"):
        OpenSearchGateway(settings, cast(OpenSearch, fake)).ensure_indices()


def test_acceptance_mode_allows_browser_projection_aliases_for_projector() -> None:
    settings = Settings(
        _env_file=None,
        opensearch_index_prefix="contract",
        search_allow_non_authoritative_projection=True,
    )
    fake = FakeOpenSearch()
    for kind in ("entities", "evidence", "knowledge"):
        browser_index = f"contract-{kind}-v{SCHEMA_VERSION}-browser-20260803"
        fake.indices.indexes.add(browser_index)
        fake.indices.aliases[f"contract-{kind}"] = {browser_index}
        fake.indices.aliases[f"contract-{kind}-write"] = {browser_index}

    active = OpenSearchGateway(settings, cast(OpenSearch, fake)).ensure_indices()

    assert set(active) == {"entities", "evidence", "knowledge"}


def test_gateway_accepts_a_concurrent_initial_index_winner(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeOpenSearch()
    create = fake.indices.create
    calls: list[str] = []

    def competing_create(*, index: str, body: dict[str, Any] | None = None) -> dict[str, bool]:
        calls.append(index)
        create(index=index, body=body)
        raise RequestError(400, "resource_already_exists_exception", {})

    monkeypatch.setattr(fake.indices, "create", competing_create)
    gateway = OpenSearchGateway(Settings(_env_file=None, opensearch_index_prefix="race"), cast(OpenSearch, fake))

    assert set(gateway.ensure_indices()) == {"entities", "evidence", "knowledge"}
    assert len(calls) == 3
    assert gateway.status().available


@pytest.mark.parametrize("error", ["mapper_parsing_exception", "security_exception"])
def test_gateway_does_not_suppress_other_index_creation_failures(error: str, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeOpenSearch()

    def failed_create(**_kwargs: Any) -> dict[str, bool]:
        raise RequestError(400, error, {})

    monkeypatch.setattr(fake.indices, "create", failed_create)
    gateway = OpenSearchGateway(Settings(_env_file=None), cast(OpenSearch, fake))
    with pytest.raises(SearchProjectionError, match=error):
        gateway.ensure_indices()


def test_gateway_bounds_reconciliation_if_the_concurrent_index_disappears(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeOpenSearch()
    calls: list[str] = []

    def vanished_create(*, index: str, **_kwargs: Any) -> dict[str, bool]:
        calls.append(index)
        raise RequestError(400, "resource_already_exists_exception", {})

    monkeypatch.setattr(fake.indices, "create", vanished_create)
    gateway = OpenSearchGateway(Settings(_env_file=None), cast(OpenSearch, fake))
    with pytest.raises(SearchProjectionError, match="disappeared"):
        gateway.ensure_indices()
    assert len(calls) == 1


def test_gateway_preserves_a_newer_alias_winner_during_initialization(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeOpenSearch()
    create = fake.indices.create

    def rebuilt_winner(*, index: str, body: dict[str, Any] | None = None) -> dict[str, bool]:
        fake.indices.indexes.add(index)
        create(index=f"{index}-rebuilt", body=body)
        raise RequestError(400, "resource_already_exists_exception", {})

    monkeypatch.setattr(fake.indices, "create", rebuilt_winner)
    gateway = OpenSearchGateway(Settings(_env_file=None, opensearch_index_prefix="race"), cast(OpenSearch, fake))

    active = gateway.ensure_indices()
    assert all(index.endswith("-rebuilt") for index in active.values())
    assert fake.indices.alias_actions == []


class ContractEmbedder:
    model = "contract-embedding-v1"
    dimensions = 3

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float("c797s" in text.casefold()), float("egfr" in text.casefold()), 0.25] for text in texts]


def test_gateway_projects_vectors_and_uses_versioned_native_hybrid_query(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        _env_file=None,
        opensearch_index_prefix="semantic",
        search_semantic_enabled=True,
        search_embedding_base_url="https://model.test",
        search_embedding_api_key="secret",
        search_embedding_model="contract-embedding-v1",
        search_embedding_dimensions=3,
    )
    fake = FakeOpenSearch()
    gateway = OpenSearchGateway(settings, cast(OpenSearch, fake), ContractEmbedder())

    gateway.ensure_indices()

    assert fake.transport.calls[0][0:2] == (
        "PUT",
        f"/_search/pipeline/semantic-hybrid-v{SCHEMA_VERSION}",
    )
    pipeline = fake.transport.calls[0][2]
    assert pipeline is not None
    weights = pipeline["phase_results_processors"][0]["normalization-processor"]["combination"]["parameters"]
    assert weights == {"weights": [0.4, 0.6]}
    evidence_mapping = fake.indices.templates[f"semantic-evidence-template-v{SCHEMA_VERSION}"]
    assert evidence_mapping["template"]["mappings"]["properties"]["embedding"]["dimension"] == 3
    assert evidence_mapping["template"]["mappings"]["_meta"]["embedding_model"] == "contract-embedding-v1"

    captured_actions: list[dict[str, Any]] = []

    def fake_bulk(_client: object, actions: list[dict[str, Any]], **_kwargs: Any) -> tuple[int, list[Any]]:
        captured_actions.extend(actions)
        return len(actions), []

    monkeypatch.setattr("pharma_intel.search.client.helpers.bulk", fake_bulk)
    document = ProjectionDocument(
        kind="evidence",
        document_id="chunk-1",
        tenant_id="tenant-a",
        source={"tenant_id": "tenant-a", "title": "EGFR resistance", "content": "C797S"},
    )
    assert gateway.bulk_index([document]) == 1
    assert captured_actions[0]["_source"]["embedding"] == [1.0, 1.0, 0.25]
    assert captured_actions[0]["_source"]["embedding_model"] == "contract-embedding-v1"
    assert "embedding" not in document.source

    fake.search_responses.extend(
        [
            {
                "took": 2,
                "hits": {
                    "total": {"value": 1},
                    "hits": [{"_source": {"entity_id": "entity-1", "name": "EGFR", "entity_type": "target"}}],
                },
                "aggregations": {
                    "entity_types": {"buckets": [{"key": "target", "doc_count": 1}]},
                    "review_statuses": {"buckets": [{"key": "verified", "doc_count": 1}]},
                },
            },
            {
                "took": 3,
                "hits": {
                    "total": {"value": 1},
                    "hits": [{"_source": {"entity_id": "entity-1", "name": "EGFR", "entity_type": "target"}}],
                },
                "aggregations": {
                    "entity_types": {"buckets": [{"key": "target", "doc_count": 1}]},
                    "review_statuses": {"buckets": [{"key": "verified", "doc_count": 1}]},
                },
            },
            {
                "took": 4,
                "hits": {
                    "total": {"value": 2},
                    "hits": [
                        {"_source": {"entity_id": "entity-1", "name": "EGFR", "entity_type": "target"}},
                        {"_source": {"entity_id": "entity-2", "name": "EGFR drug", "entity_type": "drug"}},
                    ],
                },
                "aggregations": {
                    "entity_types": {"buckets": [{"key": "target", "doc_count": 1}, {"key": "drug", "doc_count": 1}]},
                    "review_statuses": {"buckets": [{"key": "verified", "doc_count": 2}]},
                },
            },
            {
                "hits": {
                    "hits": [
                        {
                            "_score": 0.9,
                            "_source": {
                                "content": "C797S resistance",
                                "source_document_id": "doc-1",
                                "title": "EGFR",
                                "dataset_key": "literature",
                                "embedding_model": "contract-embedding-v1",
                            },
                        }
                    ]
                }
            },
        ]
    )
    entity_page = gateway.search_entities("tenant-a", "EGFR", EntityType.TARGET, 5, 0)
    entity_request = fake.search_calls[-1]
    assert entity_page.engine == "opensearch-hybrid"
    assert entity_request["params"] == {"search_pipeline": gateway.hybrid_pipeline_name}
    assert entity_request["body"]["query"]["hybrid"]["filter"] == {"term": {"tenant_id": "tenant-a"}}
    assert entity_request["body"]["post_filter"] == {"bool": {"filter": [{"term": {"entity_type": "target"}}]}}
    hybrid_sort = entity_request["body"]["sort"]
    assert len(hybrid_sort) == 3
    assert hybrid_sort[0]["_script"]["script"]["params"] == {"query": "egfr"}
    assert "0.5 * relevance / (1.0 + relevance)" in hybrid_sort[0]["_script"]["script"]["source"]
    assert hybrid_sort[1:] == [
        {"normalized_name": {"order": "asc"}},
        {"entity_id": {"order": "asc"}},
    ]
    assert entity_request["body"]["track_scores"] is False

    fake.search_responses.insert(
        0,
        {
            "hits": {"total": {"value": 0}, "hits": []},
            "aggregations": {
                "entity_types": {"buckets": []},
                "review_statuses": {"buckets": []},
            },
        },
    )
    gateway.search_entities(
        "tenant-a",
        "EGFR",
        EntityType.TARGET,
        5,
        0,
        sort_by="relevance",
        sort_direction="asc",
    )
    ascending_source = fake.search_calls[-1]["body"]["sort"][0]["_script"]["script"]["source"]
    assert "0.5 / (1.0 + relevance)" in ascending_source

    field_sorted_page = gateway.search_entities(
        "tenant-a",
        "EGFR",
        EntityType.TARGET,
        5,
        100,
        sort=(
            SortClause(field="entity_type", direction="desc"),
            SortClause(field="updated_at", direction="asc"),
        ),
    )
    field_sorted_request = fake.search_calls[-1]
    assert field_sorted_page.engine == "opensearch"
    assert field_sorted_request["params"] == {}
    assert "hybrid" not in field_sorted_request["body"]["query"]
    assert field_sorted_request["body"]["from"] == 100
    assert field_sorted_request["body"]["sort"] == [
        {"entity_type": {"order": "desc", "missing": "_last"}},
        {"updated_at": {"order": "asc", "missing": "_last"}},
        {"normalized_name": {"order": "asc"}},
        {"entity_id": {"order": "asc"}},
    ]

    multi_type_page = gateway.search_entities(
        "tenant-a", "EGFR", [EntityType.TARGET, EntityType.DRUG], 5, 0, ReviewStatus.VERIFIED
    )
    multi_type_request = fake.search_calls[-1]
    assert multi_type_page.entity_ids == ["entity-1", "entity-2"]
    assert multi_type_request["body"]["post_filter"] == {
        "bool": {
            "filter": [
                {"terms": {"entity_type": ["target", "drug"]}},
                {"term": {"review_status": "verified"}},
            ]
        }
    }

    matches = gateway.search_evidence("tenant-a", "C797S resistance", ["literature"], 5, 2)

    request = fake.search_calls[-1]
    assert request["params"] == {"search_pipeline": gateway.hybrid_pipeline_name}
    hybrid = request["body"]["query"]["hybrid"]
    assert hybrid["filter"] == {
        "bool": {"filter": [{"term": {"tenant_id": "tenant-a"}}, {"terms": {"dataset_key": ["literature"]}}]}
    }
    assert hybrid["pagination_depth"] == 1000
    assert hybrid["queries"][1]["knn"]["embedding"]["min_score"] == 0.55
    assert request["body"]["_source"] == {"excludes": ["embedding"]}
    assert request["body"]["sort"] == [{"_score": {"order": "desc"}}]
    assert matches[0].metadata["retrieval_mode"] == "hybrid"
    assert matches[0].metadata["embedding_model"] == "contract-embedding-v1"
    with pytest.raises(SearchProjectionError, match="candidate limit"):
        gateway.search_evidence("tenant-a", "C797S", ["literature"], 50, 951)


def test_gateway_rejects_embedding_dimension_mismatch() -> None:
    settings = Settings(
        _env_file=None,
        search_semantic_enabled=True,
        search_embedding_base_url="https://model.test",
        search_embedding_api_key="secret",
        search_embedding_model="contract-embedding-v1",
        search_embedding_dimensions=4,
    )
    gateway = OpenSearchGateway(settings, cast(OpenSearch, FakeOpenSearch()), ContractEmbedder())

    with pytest.raises(SearchProjectionError, match="dimensions"):
        gateway.bulk_index(
            [
                ProjectionDocument(
                    kind="entities",
                    document_id="entity-1",
                    tenant_id="tenant-a",
                    source={"name": "EGFR"},
                )
            ]
        )

    model_mismatch = settings.model_copy(
        update={"search_embedding_model": "different-embedding-v1", "search_embedding_dimensions": 3}
    )
    with pytest.raises(SearchProjectionError, match="model"):
        OpenSearchGateway(
            model_mismatch,
            cast(OpenSearch, FakeOpenSearch()),
            ContractEmbedder(),
        ).ensure_indices()


def test_semantic_gateway_requires_embedding_credentials_at_consumer_boundary() -> None:
    with pytest.raises(SearchProjectionError, match="embedding API key"):
        OpenSearchGateway(
            Settings(
                _env_file=None,
                search_semantic_enabled=True,
                search_embedding_base_url="https://model.test",
                search_embedding_api_key="",
                search_embedding_model="contract-embedding-v1",
            ),
            cast(OpenSearch, FakeOpenSearch()),
        )


def test_semantic_gateway_requires_atomic_rebuild_from_legacy_aliases() -> None:
    settings = Settings(
        _env_file=None,
        opensearch_index_prefix="semantic",
        search_semantic_enabled=True,
        search_embedding_base_url="https://model.test",
        search_embedding_api_key="secret",
        search_embedding_model="contract-embedding-v1",
        search_embedding_dimensions=3,
    )
    fake = FakeOpenSearch()
    for kind in ("entities", "evidence", "knowledge"):
        legacy = f"semantic-{kind}-v1-000001"
        fake.indices.indexes.add(legacy)
        fake.indices.aliases[f"semantic-{kind}"] = {legacy}
        fake.indices.aliases[f"semantic-{kind}-write"] = {legacy}
    gateway = OpenSearchGateway(settings, cast(OpenSearch, fake), ContractEmbedder())

    with pytest.raises(SearchProjectionError, match="atomic rebuild"):
        gateway.ensure_indices()
    with pytest.raises(SearchProjectionError, match="atomic rebuild"):
        gateway.assert_projection_ready()
    assert gateway.status().available is False
    rebuild = gateway.create_rebuild_indices("hybrid-upgrade")
    assert rebuild == {
        "entities": f"semantic-entities-v{SCHEMA_VERSION}-hybrid-upgrade",
        "evidence": f"semantic-evidence-v{SCHEMA_VERSION}-hybrid-upgrade",
        "knowledge": f"semantic-knowledge-v{SCHEMA_VERSION}-hybrid-upgrade",
    }


def test_semantic_readiness_fails_closed_for_pipeline_mapping_and_alias_drift() -> None:
    settings = Settings(
        _env_file=None,
        opensearch_index_prefix="semantic",
        search_semantic_enabled=True,
        search_embedding_base_url="https://model.test",
        search_embedding_api_key="secret",
        search_embedding_model="contract-embedding-v1",
        search_embedding_dimensions=3,
    )
    fake = FakeOpenSearch()
    gateway = OpenSearchGateway(settings, cast(OpenSearch, fake), ContractEmbedder())
    active = gateway.ensure_indices()
    gateway.assert_projection_ready()

    fake.transport.pipelines.clear()
    with pytest.raises(SearchProjectionError, match="pipeline is unavailable"):
        gateway.assert_projection_ready()
    fake.transport.pipelines[gateway.hybrid_pipeline_name] = gateway._hybrid_pipeline_body()

    evidence_mapping = fake.indices.templates[f"semantic-evidence-template-v{SCHEMA_VERSION}"]["template"]["mappings"]
    fake.indices.mapping_overrides[active["evidence"]] = {
        **evidence_mapping,
        "properties": {
            **evidence_mapping["properties"],
            "embedding": {**evidence_mapping["properties"]["embedding"], "dimension": 4},
        },
    }
    with pytest.raises(SearchProjectionError, match="evidence"):
        gateway.assert_projection_ready()
    fake.indices.mapping_overrides.clear()

    duplicate = f"semantic-entities-v{SCHEMA_VERSION}-duplicate"
    fake.indices.aliases["semantic-entities"].add(duplicate)
    with pytest.raises(SearchProjectionError, match="exactly one active index"):
        gateway.assert_projection_ready()
