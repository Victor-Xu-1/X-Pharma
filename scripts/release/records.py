from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class ReleaseEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class RepositorySubject:
    commit: str
    source_file_count: int
    source_tree_sha256: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class SecurityEvidence:
    directory: Path
    manifest_sha256: str
    generated_at: datetime
    targets: dict[str, str]
    release_mode: bool
    risk_acceptance_reference: str


@dataclass(frozen=True)
class PolicyLevel:
    required_categories: frozenset[str]
    require_release_security: bool
    require_signed_git_tag: bool
    require_bundle_signature: bool
    security_max_age_hours: int


@dataclass(frozen=True)
class ProductionEvidenceContract:
    report_name: str
    checks: frozenset[str]
    approval_roles: frozenset[str]
    minimum_artifacts: int
    require_independent_executor: bool


@dataclass(frozen=True)
class EvidencePolicy:
    path: Path
    categories: dict[str, int]
    levels: dict[str, PolicyLevel]
    production_contracts: dict[str, ProductionEvidenceContract]


@dataclass(frozen=True)
class GoalRequirement:
    identifier: str
    ordinal: int
    group: str
    title: str
    baseline_categories: frozenset[str]
    production_categories: frozenset[str]
    requires_release_security: bool
    requires_signed_git_tag: bool
    requires_bundle_signature: bool


@dataclass(frozen=True)
class GoalCompletionMatrix:
    path: Path
    goal_document_id: str
    goal_version: str
    section: int
    requirements: tuple[GoalRequirement, ...]
