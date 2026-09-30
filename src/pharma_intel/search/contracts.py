from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EntitySearchMatch:
    match_type: str
    match_relation: str
    matched_value: str | None = None
    namespace: str | None = None


@dataclass(frozen=True)
class EntitySearchPage:
    entity_ids: list[str]
    total: int
    facets: dict[str, dict[str, int]] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    engine: str = "opensearch"
    took_ms: int | None = None


@dataclass(frozen=True)
class EvidenceMatch:
    content: str
    document_id: str
    document_name: str
    dataset_key: str
    score: float | None
    positions: list[Any]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ProjectionDocument:
    kind: str
    document_id: str
    tenant_id: str
    source: dict[str, Any]


@dataclass(frozen=True)
class OpenSearchStatus:
    available: bool
    version: str | None
    cluster_name: str | None
    cluster_status: str | None
    aliases: dict[str, list[str]]
    error: str | None = None
