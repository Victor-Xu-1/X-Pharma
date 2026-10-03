from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from scripts.release.contracts.core import CATEGORY_PATTERN
from scripts.release.contracts.goal import (
    GOAL_COMPLETION_AUDIT_SCHEMA,
    GOAL_COMPLETION_MATRIX_SCHEMA,
    GOAL_DOCUMENT_VERSION,
    GOAL_MATRIX_FIELDS,
    GOAL_REQUIREMENT_FIELDS,
    GOAL_REQUIREMENT_ID_PATTERN,
    GOAL_SECTION_19_REQUIREMENTS,
)
from scripts.release.contracts.mcp import MCP_SENDER_CONSTRAINT_REPORT, MCP_SENDER_CONSTRAINT_SCHEMA
from scripts.release.contracts.topology import (
    PRODUCTION_TOPOLOGY_LIVE_REPORT,
    PRODUCTION_TOPOLOGY_LIVE_SCHEMA,
    PRODUCTION_TOPOLOGY_REPORT,
    PRODUCTION_TOPOLOGY_SCHEMA,
)
from scripts.release.io import _load_json_object, _sha256_file
from scripts.release.records import (
    EvidencePolicy,
    GoalCompletionMatrix,
    GoalRequirement,
    PolicyLevel,
    ProductionEvidenceContract,
    ReleaseEvidenceError,
)


def load_policy(path: Path) -> EvidencePolicy:
    resolved = path.resolve()
    document = _load_json_object(resolved, "release evidence policy")
    if document.get("schema_version") != 1:
        raise ReleaseEvidenceError("unsupported release evidence policy schema")
    raw_categories = document.get("categories")
    raw_levels = document.get("levels")
    raw_security_age = document.get("security_max_age_hours")
    raw_production_contracts = document.get("production_evidence_contracts", {})
    if (
        not isinstance(raw_categories, dict)
        or not isinstance(raw_levels, dict)
        or not isinstance(raw_security_age, dict)
        or not isinstance(raw_production_contracts, dict)
    ):
        raise ReleaseEvidenceError("release evidence policy sections are invalid")
    categories: dict[str, int] = {}
    for name, configuration in raw_categories.items():
        if not isinstance(name, str) or not CATEGORY_PATTERN.fullmatch(name) or not isinstance(configuration, dict):
            raise ReleaseEvidenceError("release evidence policy contains an invalid category")
        maximum_age = configuration.get("max_age_hours")
        if not isinstance(maximum_age, int) or isinstance(maximum_age, bool) or maximum_age <= 0:
            raise ReleaseEvidenceError(f"category {name} has an invalid maximum age")
        categories[name] = maximum_age
    production_contracts: dict[str, ProductionEvidenceContract] = {}
    for category, configuration in raw_production_contracts.items():
        if not isinstance(category, str) or category not in categories or not isinstance(configuration, dict):
            raise ReleaseEvidenceError("release evidence policy contains an invalid production contract")
        report_name = configuration.get("report_name")
        checks = configuration.get("checks")
        approval_roles = configuration.get("approval_roles")
        minimum_artifacts = configuration.get("minimum_artifacts")
        require_independent_executor = configuration.get("require_independent_executor")
        if (
            not isinstance(report_name, str)
            or PurePosixPath(report_name).name != report_name
            or not report_name.endswith(".json")
            or not isinstance(checks, list)
            or not checks
            or not all(isinstance(item, str) and CATEGORY_PATTERN.fullmatch(item) for item in checks)
            or len(set(checks)) != len(checks)
            or not isinstance(approval_roles, list)
            or not approval_roles
            or not all(isinstance(item, str) and CATEGORY_PATTERN.fullmatch(item) for item in approval_roles)
            or len(set(approval_roles)) != len(approval_roles)
            or not isinstance(minimum_artifacts, int)
            or isinstance(minimum_artifacts, bool)
            or not 1 <= minimum_artifacts <= 100
            or not isinstance(require_independent_executor, bool)
        ):
            raise ReleaseEvidenceError(f"production evidence contract {category} is invalid")
        production_contracts[category] = ProductionEvidenceContract(
            report_name=report_name,
            checks=frozenset(checks),
            approval_roles=frozenset(approval_roles),
            minimum_artifacts=minimum_artifacts,
            require_independent_executor=require_independent_executor,
        )
    levels: dict[str, PolicyLevel] = {}
    for level_name, configuration in raw_levels.items():
        if not isinstance(level_name, str) or not isinstance(configuration, dict):
            raise ReleaseEvidenceError("release evidence policy contains an invalid level")
        required = configuration.get("required_categories")
        security_age = raw_security_age.get(level_name)
        if (
            not isinstance(required, list)
            or not all(isinstance(item, str) and item in categories for item in required)
            or len(set(required)) != len(required)
            or not isinstance(security_age, int)
            or isinstance(security_age, bool)
            or security_age <= 0
        ):
            raise ReleaseEvidenceError(f"release evidence policy level {level_name} is invalid")
        boolean_names = ("require_release_security", "require_signed_git_tag", "require_bundle_signature")
        if not all(isinstance(configuration.get(name), bool) for name in boolean_names):
            raise ReleaseEvidenceError(f"release evidence policy level {level_name} has invalid booleans")
        levels[level_name] = PolicyLevel(
            required_categories=frozenset(required),
            require_release_security=configuration["require_release_security"],
            require_signed_git_tag=configuration["require_signed_git_tag"],
            require_bundle_signature=configuration["require_bundle_signature"],
            security_max_age_hours=security_age,
        )
    production_categories = levels.get("production")
    if production_contracts and (
        production_categories is None or not production_contracts.keys() <= production_categories.required_categories
    ):
        raise ReleaseEvidenceError("production evidence contracts must map to required production categories")
    return EvidencePolicy(resolved, categories, levels, production_contracts)


def _goal_categories(value: object, *, label: str, policy: EvidencePolicy) -> frozenset[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and CATEGORY_PATTERN.fullmatch(item) for item in value)
        or len(set(value)) != len(value)
    ):
        raise ReleaseEvidenceError(f"{label} must be a non-empty unique category list")
    categories = frozenset(value)
    unknown = categories - policy.categories.keys()
    if unknown:
        raise ReleaseEvidenceError(f"{label} contains unknown categories: {', '.join(sorted(unknown))}")
    return categories


def load_goal_completion_matrix(path: Path, policy: EvidencePolicy) -> GoalCompletionMatrix:
    resolved = path.resolve()
    document = _load_json_object(resolved, "GOAL completion matrix")
    if set(document) != GOAL_MATRIX_FIELDS:
        raise ReleaseEvidenceError("GOAL completion matrix fields are invalid")
    if (
        document.get("schema") != GOAL_COMPLETION_MATRIX_SCHEMA
        or document.get("schema_version") != 1
        or document.get("goal_document_id") != "PIP-GOAL-001"
        or document.get("goal_version") != GOAL_DOCUMENT_VERSION
        or document.get("section") != 19
    ):
        raise ReleaseEvidenceError("GOAL completion matrix identity is invalid")
    raw_requirements = document.get("requirements")
    if not isinstance(raw_requirements, list) or len(raw_requirements) != len(GOAL_SECTION_19_REQUIREMENTS):
        raise ReleaseEvidenceError(
            f"GOAL completion matrix must contain exactly {len(GOAL_SECTION_19_REQUIREMENTS)} requirements"
        )
    pilot = policy.levels.get("pilot")
    production = policy.levels.get("production")
    if pilot is None or production is None:
        raise ReleaseEvidenceError("GOAL completion matrix requires pilot and production policy levels")

    requirements: list[GoalRequirement] = []
    for index, raw_requirement in enumerate(raw_requirements, start=1):
        if not isinstance(raw_requirement, dict) or set(raw_requirement) != GOAL_REQUIREMENT_FIELDS:
            raise ReleaseEvidenceError(f"GOAL requirement {index} fields are invalid")
        identifier = raw_requirement.get("id")
        ordinal = raw_requirement.get("ordinal")
        group = raw_requirement.get("group")
        title = raw_requirement.get("title")
        expected_identifier, expected_group = GOAL_SECTION_19_REQUIREMENTS[index - 1]
        if (
            not isinstance(identifier, str)
            or GOAL_REQUIREMENT_ID_PATTERN.fullmatch(identifier) is None
            or identifier != expected_identifier
            or ordinal != index
            or group != expected_group
            or not isinstance(title, str)
            or title != title.strip()
            or not 4 <= len(title) <= 120
        ):
            raise ReleaseEvidenceError(f"GOAL requirement {index} identity is invalid")
        requires_release_security = raw_requirement.get("requires_release_security")
        requires_signed_git_tag = raw_requirement.get("requires_signed_git_tag")
        requires_bundle_signature = raw_requirement.get("requires_bundle_signature")
        if not (
            isinstance(requires_release_security, bool)
            and isinstance(requires_signed_git_tag, bool)
            and isinstance(requires_bundle_signature, bool)
        ):
            raise ReleaseEvidenceError(f"GOAL requirement {identifier} controls are invalid")
        baseline_categories = _goal_categories(
            raw_requirement.get("baseline_categories"), label=f"GOAL requirement {identifier} baseline", policy=policy
        )
        production_categories = _goal_categories(
            raw_requirement.get("production_categories"),
            label=f"GOAL requirement {identifier} production",
            policy=policy,
        )
        if not baseline_categories <= pilot.required_categories:
            raise ReleaseEvidenceError(f"GOAL requirement {identifier} baseline is not required by pilot policy")
        if not production_categories <= production.required_categories:
            raise ReleaseEvidenceError(f"GOAL requirement {identifier} production evidence is not required by policy")
        requirements.append(
            GoalRequirement(
                identifier=identifier,
                ordinal=index,
                group=group,
                title=title,
                baseline_categories=baseline_categories,
                production_categories=production_categories,
                requires_release_security=requires_release_security,
                requires_signed_git_tag=requires_signed_git_tag,
                requires_bundle_signature=requires_bundle_signature,
            )
        )

    release_bundle = next(
        requirement for requirement in requirements if requirement.identifier == "engineering.release_evidence_bundle"
    )
    if (
        release_bundle.baseline_categories != pilot.required_categories
        or release_bundle.production_categories != production.required_categories
        or not release_bundle.requires_release_security
        or not release_bundle.requires_signed_git_tag
        or not release_bundle.requires_bundle_signature
    ):
        raise ReleaseEvidenceError("GOAL release evidence bundle requirement must cover the complete release policy")
    return GoalCompletionMatrix(
        path=resolved,
        goal_document_id="PIP-GOAL-001",
        goal_version=GOAL_DOCUMENT_VERSION,
        section=19,
        requirements=tuple(requirements),
    )


def _repository_goal_matrix_contract(
    repo: Path, policy: EvidencePolicy, level_name: str
) -> tuple[GoalCompletionMatrix | None, Path | None]:
    matrix_path = policy.path.with_name("goal-section-19-matrix.json")
    schema_path = policy.path.with_name("goal-section-19-matrix.schema.json")
    if not matrix_path.exists() and not schema_path.exists():
        if level_name == "production" and (repo / "GOAL.md").is_file():
            raise ReleaseEvidenceError("authoritative GOAL completion matrix is missing from the repository")
        return None, None
    if matrix_path.is_symlink() or schema_path.is_symlink() or not matrix_path.is_file() or not schema_path.is_file():
        raise ReleaseEvidenceError("GOAL completion matrix and schema must both be regular files")
    schema = _load_json_object(schema_path, "GOAL completion matrix schema")
    if (
        schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
    ):
        raise ReleaseEvidenceError("GOAL completion matrix schema contract is invalid")
    return load_goal_completion_matrix(matrix_path, policy), schema_path.resolve()


def _require_authoritative_production_policy(
    repo: Path,
    policy: EvidencePolicy,
    level_name: str,
) -> None:
    if level_name != "production":
        return
    try:
        expected = (repo.resolve(strict=True) / "deploy" / "release" / "evidence-policy.json").resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("authoritative production evidence policy is missing from the repository") from exc
    if policy.path != expected:
        raise ReleaseEvidenceError("production releases require the committed authoritative evidence policy")


def goal_completion_audit(
    matrix: GoalCompletionMatrix,
    *,
    present_categories: set[str],
    release_security_verified: bool,
    signed_git_tag_verified: bool,
    bundle_signature_verified: bool,
    release_level: str,
    release_eligible: bool,
) -> dict[str, Any]:
    requirement_results: list[dict[str, Any]] = []
    counts = {"proven": 0, "baseline_only": 0, "missing": 0}
    for requirement in matrix.requirements:
        missing_baseline = sorted(requirement.baseline_categories - present_categories)
        missing_production = sorted(requirement.production_categories - present_categories)
        missing_controls: list[str] = []
        if requirement.requires_release_security and not release_security_verified:
            missing_controls.append("release_security")
        if requirement.requires_signed_git_tag and not signed_git_tag_verified:
            missing_controls.append("signed_git_tag")
        if requirement.requires_bundle_signature and not bundle_signature_verified:
            missing_controls.append("bundle_signature")
        if not missing_production and not missing_controls:
            status = "proven"
        elif not missing_baseline:
            status = "baseline_only"
        else:
            status = "missing"
        counts[status] += 1
        requirement_results.append(
            {
                "id": requirement.identifier,
                "ordinal": requirement.ordinal,
                "group": requirement.group,
                "title": requirement.title,
                "status": status,
                "missing_baseline_categories": missing_baseline,
                "missing_production_categories": missing_production,
                "missing_production_controls": missing_controls,
            }
        )
    production_complete = (
        release_level == "production" and release_eligible and counts["proven"] == len(matrix.requirements)
    )
    return {
        "schema": GOAL_COMPLETION_AUDIT_SCHEMA,
        "schema_version": 1,
        "goal_document_id": matrix.goal_document_id,
        "goal_version": matrix.goal_version,
        "section": matrix.section,
        "matrix_sha256": _sha256_file(matrix.path),
        "requirement_count": len(matrix.requirements),
        "proven_count": counts["proven"],
        "baseline_only_count": counts["baseline_only"],
        "missing_count": counts["missing"],
        "production_complete": production_complete,
        "requirements": requirement_results,
    }


def production_evidence_requirements(*, policy_path: Path, category: str) -> dict[str, Any]:
    policy = load_policy(policy_path)
    contract = policy.production_contracts.get(category)
    if contract is None:
        raise ReleaseEvidenceError(f"category does not accept external production evidence: {category}")
    detail_reports: list[dict[str, str]] = []
    if category == "mcp_sender_constraint":
        detail_reports.append(
            {
                "path": MCP_SENDER_CONSTRAINT_REPORT,
                "schema": MCP_SENDER_CONSTRAINT_SCHEMA,
                "schema_file": "deploy/release/mcp-sender-constraint-report.schema.json",
            }
        )
    elif category == "production_topology":
        detail_reports.extend(
            [
                {
                    "path": PRODUCTION_TOPOLOGY_REPORT,
                    "schema": PRODUCTION_TOPOLOGY_SCHEMA,
                    "schema_file": "deploy/release/production-topology-report.schema.json",
                },
                {
                    "path": PRODUCTION_TOPOLOGY_LIVE_REPORT,
                    "schema": PRODUCTION_TOPOLOGY_LIVE_SCHEMA,
                    "schema_file": "deploy/release/production-topology-live-probe.schema.json",
                },
            ]
        )
    return {
        "schema": "pharma.production-evidence-requirements.v2",
        "schema_version": 2,
        "category": category,
        "max_age_hours": policy.categories[category],
        "checks": sorted(contract.checks),
        "approval_roles": sorted(contract.approval_roles),
        "minimum_artifacts": contract.minimum_artifacts,
        "require_independent_executor": contract.require_independent_executor,
        "intake_schema": "deploy/release/production-evidence-intake.schema.json",
        "report_schema": "deploy/release/production-evidence-report.schema.json",
        "detail_reports": detail_reports,
        "production_claim": False,
    }
