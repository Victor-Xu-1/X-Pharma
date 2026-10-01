from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.release.io import _subject_document
from scripts.release.policy import (
    _repository_goal_matrix_contract,
    _require_authoritative_production_policy,
    goal_completion_audit,
    load_policy,
)
from scripts.release.records import ReleaseEvidenceError
from scripts.release.repository import _check_release_tag, repository_subject
from scripts.release.security import validate_security_evidence
from scripts.release.statements import _statement_category


def audit_release(
    *,
    repo: Path,
    policy_path: Path,
    level_name: str,
    security_directory: Path,
    statements: list[Path],
    release_tag: str | None,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    if level_name not in policy.levels:
        raise ReleaseEvidenceError(f"unknown release evidence level: {level_name}")
    _require_authoritative_production_policy(repo, policy, level_name)
    level = policy.levels[level_name]
    subject = repository_subject(repo)
    matrix, _ = _repository_goal_matrix_contract(repo, policy, level_name)
    security = validate_security_evidence(
        security_directory,
        subject,
        maximum_age_hours=level.security_max_age_hours,
    )
    categories: set[str] = set()
    blockers: list[str] = []
    for statement_path in statements:
        try:
            category, _ = _statement_category(
                statement_path.resolve(), policy=policy, subject=subject, security=security
            )
            if category in categories:
                blockers.append(f"duplicate evidence category: {category}")
            categories.add(category)
        except ReleaseEvidenceError as exc:
            blockers.append(str(exc))
    missing = sorted(level.required_categories - categories)
    blockers.extend(f"missing evidence category: {category}" for category in missing)
    if level.require_release_security and not security.release_mode:
        blockers.append("security evidence was not generated in release mode")
    signed_git_tag_verified = False
    try:
        _check_release_tag(repo, subject, release_tag, level.require_signed_git_tag)
    except ReleaseEvidenceError as exc:
        blockers.append(str(exc))
    if release_tag is not None:
        try:
            _check_release_tag(repo, subject, release_tag, True)
            signed_git_tag_verified = True
        except ReleaseEvidenceError:
            pass
    if level.require_bundle_signature:
        blockers.append("production assembly requires an external Ed25519 signing key")
    result: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "release_level": level_name,
        "status": "eligible" if not blockers else "blocked",
        "subject": _subject_document(subject, security.targets),
        "present_categories": sorted(categories),
        "missing_categories": missing,
        "blockers": blockers,
        "production_claim": False,
    }
    if matrix is not None:
        result["goal_section_19"] = goal_completion_audit(
            matrix,
            present_categories=categories,
            release_security_verified=security.release_mode,
            signed_git_tag_verified=signed_git_tag_verified,
            bundle_signature_verified=False,
            release_level=level_name,
            release_eligible=not blockers,
        )
    return result
