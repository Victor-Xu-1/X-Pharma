from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from scripts.release.contracts.core import COMMIT_PATTERN, SHA256_PATTERN
from scripts.release.contracts.production import (
    PRODUCTION_HANDOFF_CATEGORY_FIELDS,
    PRODUCTION_HANDOFF_FIELDS,
    PRODUCTION_HANDOFF_FILE_FIELDS,
    PRODUCTION_HANDOFF_SCHEMA,
    PRODUCTION_HANDOFF_SUBJECT_FIELDS,
)
from scripts.release.crypto import _verify_production_handoff_signature
from scripts.release.io import _load_json_object, _parse_timestamp, _safe_checksum_path, _sha256_file
from scripts.release.policy import (
    _repository_goal_matrix_contract,
    _require_authoritative_production_policy,
    load_policy,
    production_evidence_requirements,
)
from scripts.release.records import ReleaseEvidenceError
from scripts.release.repository import repository_subject


def verify_production_evidence_handoff(
    *,
    repo: Path,
    policy_path: Path,
    handoff: Path,
    trusted_public_key: Path | None = None,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    _require_authoritative_production_policy(repo, policy, "production")
    subject = repository_subject(repo)
    if handoff.is_symlink():
        raise ReleaseEvidenceError("production handoff cannot be a symbolic link")
    try:
        root = handoff.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("production handoff does not exist") from exc
    if not root.is_dir():
        raise ReleaseEvidenceError("production handoff must be a directory")
    manifest_path = root / "handoff-manifest.json"
    manifest = _load_json_object(manifest_path, "production handoff manifest")
    categories = manifest.get("categories")
    files = manifest.get("files")
    expected_subject = {
        "git_commit": subject.commit,
        "source_file_count": subject.source_file_count,
        "source_tree_sha256": subject.source_tree_sha256,
    }
    if (
        set(manifest) != PRODUCTION_HANDOFF_FIELDS
        or manifest.get("schema") != PRODUCTION_HANDOFF_SCHEMA
        or manifest.get("schema_version") != 2
        or manifest.get("status") != "requirements_only"
        or manifest.get("production_claim") is not False
        or manifest.get("subject") != expected_subject
        or manifest.get("policy_sha256") != _sha256_file(policy.path)
        or not isinstance(categories, list)
        or not isinstance(files, list)
    ):
        raise ReleaseEvidenceError("production handoff manifest has an invalid contract or source binding")
    _parse_timestamp(manifest.get("generated_at"), "production handoff generated_at")

    declared_categories: set[str] = set()
    for item in categories:
        if not isinstance(item, dict) or set(item) != PRODUCTION_HANDOFF_CATEGORY_FIELDS:
            raise ReleaseEvidenceError("production handoff contains an invalid category requirement")
        category = item.get("category")
        requirements_path = item.get("requirements")
        if (
            not isinstance(category, str)
            or category in declared_categories
            or category not in policy.production_contracts
            or not isinstance(requirements_path, str)
            or requirements_path != f"requirements/{category}.json"
        ):
            raise ReleaseEvidenceError("production handoff category binding is invalid")
        expected_requirements = production_evidence_requirements(policy_path=policy.path, category=category)
        actual_requirements = _load_json_object(root / requirements_path, f"{category} production requirements")
        if actual_requirements != expected_requirements:
            raise ReleaseEvidenceError("production handoff requirements differ from the authoritative policy")
        declared_categories.add(category)
    if declared_categories != set(policy.production_contracts):
        raise ReleaseEvidenceError("production handoff does not cover every external production category")

    actual_files: dict[str, tuple[int, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ReleaseEvidenceError(f"production handoff contains a symbolic link: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ReleaseEvidenceError(f"production handoff contains a non-regular entry: {relative}")
        if path not in {manifest_path, root / "handoff-manifest.sig.json"}:
            actual_files[relative] = (path.stat().st_size, _sha256_file(path))
    declared_files: dict[str, tuple[int, str]] = {}
    for item in files:
        if not isinstance(item, dict) or set(item) != PRODUCTION_HANDOFF_FILE_FIELDS:
            raise ReleaseEvidenceError("production handoff contains invalid file metadata")
        raw_path = item.get("path")
        size = item.get("size")
        digest = item.get("sha256")
        if not isinstance(raw_path, str):
            raise ReleaseEvidenceError("production handoff contains invalid file metadata")
        relative_path = PurePosixPath(raw_path)
        if (
            relative_path.is_absolute()
            or not relative_path.parts
            or ".." in relative_path.parts
            or relative_path.as_posix() != raw_path
            or raw_path == "handoff-manifest.json"
            or raw_path in declared_files
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size <= 0
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
        ):
            raise ReleaseEvidenceError("production handoff contains invalid file metadata")
        declared_files[raw_path] = (size, digest)
    if declared_files != actual_files:
        raise ReleaseEvidenceError("production handoff file inventory is incomplete or has a digest mismatch")
    copied_policy = root / "policy" / "evidence-policy.json"
    if _sha256_file(copied_policy) != _sha256_file(policy.path):
        raise ReleaseEvidenceError("production handoff policy snapshot differs from the authoritative policy")
    load_policy(copied_policy)
    source_matrix, source_matrix_schema = _repository_goal_matrix_contract(repo, policy, "production")
    copied_matrix, copied_matrix_schema = _repository_goal_matrix_contract(
        root, load_policy(copied_policy), "production"
    )
    if (source_matrix is None) != (copied_matrix is None):
        raise ReleaseEvidenceError("production handoff GOAL matrix snapshot is incomplete")
    if source_matrix is not None and copied_matrix is not None:
        if (
            _sha256_file(source_matrix.path) != _sha256_file(copied_matrix.path)
            or source_matrix_schema is None
            or copied_matrix_schema is None
            or _sha256_file(source_matrix_schema) != _sha256_file(copied_matrix_schema)
        ):
            raise ReleaseEvidenceError("production handoff GOAL matrix differs from the authoritative repository")
    for name in (
        "mcp-sender-constraint-report.schema.json",
        "production-evidence-batch-intake.schema.json",
        "production-evidence-batch-manifest.schema.json",
        "production-evidence-handoff-manifest.schema.json",
        "production-evidence-intake.schema.json",
        "production-evidence-report.schema.json",
        "production-topology-live-probe.schema.json",
        "production-topology-report.schema.json",
    ):
        if _sha256_file(root / "schemas" / name) != _sha256_file(repo / "deploy" / "release" / name):
            raise ReleaseEvidenceError("production handoff schema snapshot differs from the authoritative repository")
    signature_verified = _verify_production_handoff_signature(
        root=root,
        manifest=manifest,
        trusted_public_key=trusted_public_key,
    )
    return {
        "schema_version": 2,
        "status": "passed",
        "handoff": str(root),
        "category_count": len(declared_categories),
        "files_verified": len(declared_files),
        "signature_verified": signature_verified,
        "production_claim": False,
    }


def verify_production_evidence_handoff_offline(
    *,
    handoff: Path,
    trusted_public_key: Path,
) -> dict[str, Any]:
    if handoff.is_symlink():
        raise ReleaseEvidenceError("production handoff cannot be a symbolic link")
    try:
        root = handoff.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("production handoff does not exist") from exc
    if not root.is_dir():
        raise ReleaseEvidenceError("production handoff must be a directory")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ReleaseEvidenceError(f"production handoff contains a symbolic link: {path.relative_to(root)}")
        if not path.is_dir() and not path.is_file():
            raise ReleaseEvidenceError(f"production handoff contains a non-regular entry: {path.relative_to(root)}")
    manifest = _load_json_object(root / "handoff-manifest.json", "production handoff manifest")
    if (
        set(manifest) != PRODUCTION_HANDOFF_FIELDS
        or manifest.get("schema") != PRODUCTION_HANDOFF_SCHEMA
        or manifest.get("schema_version") != 2
        or manifest.get("status") != "requirements_only"
        or manifest.get("production_claim") is not False
    ):
        raise ReleaseEvidenceError("production handoff manifest is invalid")
    subject = manifest.get("subject")
    if (
        not isinstance(subject, dict)
        or set(subject) != PRODUCTION_HANDOFF_SUBJECT_FIELDS
        or not isinstance(subject.get("git_commit"), str)
        or COMMIT_PATTERN.fullmatch(subject["git_commit"]) is None
        or not isinstance(subject.get("source_file_count"), int)
        or isinstance(subject.get("source_file_count"), bool)
        or subject["source_file_count"] <= 0
        or not isinstance(subject.get("source_tree_sha256"), str)
        or SHA256_PATTERN.fullmatch(subject["source_tree_sha256"]) is None
    ):
        raise ReleaseEvidenceError("production handoff subject is invalid")
    _parse_timestamp(manifest.get("generated_at"), "production handoff generated_at")
    policy_path = root / "policy" / "evidence-policy.json"
    if manifest.get("policy_sha256") != _sha256_file(policy_path):
        raise ReleaseEvidenceError("production handoff policy digest is invalid")
    policy = load_policy(policy_path)
    _repository_goal_matrix_contract(root, policy, "production")
    categories = manifest.get("categories")
    if not isinstance(categories, list):
        raise ReleaseEvidenceError("production handoff categories are invalid")
    declared_categories: set[str] = set()
    for item in categories:
        if not isinstance(item, dict) or set(item) != PRODUCTION_HANDOFF_CATEGORY_FIELDS:
            raise ReleaseEvidenceError("production handoff contains an invalid category requirement")
        category = item.get("category")
        requirement_path = item.get("requirements")
        if (
            not isinstance(category, str)
            or category in declared_categories
            or category not in policy.production_contracts
            or requirement_path != f"requirements/{category}.json"
        ):
            raise ReleaseEvidenceError("production handoff category binding is invalid")
        expected = production_evidence_requirements(policy_path=policy_path, category=category)
        if _load_json_object(root / requirement_path, f"{category} production requirements") != expected:
            raise ReleaseEvidenceError("production handoff requirements differ from its bundled policy")
        declared_categories.add(category)
    if declared_categories != set(policy.production_contracts):
        raise ReleaseEvidenceError("production handoff does not cover every external production category")
    manifest_path = root / "handoff-manifest.json"
    signature_path = root / "handoff-manifest.sig.json"
    actual_files = {
        path.relative_to(root).as_posix(): (path.stat().st_size, _sha256_file(path))
        for path in sorted(root.rglob("*"))
        if path.is_file() and path not in {manifest_path, signature_path}
    }
    declared_files: dict[str, tuple[int, str]] = {}
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ReleaseEvidenceError("production handoff file inventory is invalid")
    for item in files:
        if not isinstance(item, dict) or set(item) != PRODUCTION_HANDOFF_FILE_FIELDS:
            raise ReleaseEvidenceError("production handoff contains invalid file metadata")
        raw_path, size, digest = item.get("path"), item.get("size"), item.get("sha256")
        if (
            not isinstance(raw_path, str)
            or _safe_checksum_path(raw_path).as_posix() != raw_path
            or raw_path in declared_files
            or raw_path in {"handoff-manifest.json", "handoff-manifest.sig.json"}
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size <= 0
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
        ):
            raise ReleaseEvidenceError("production handoff contains invalid file metadata")
        declared_files[raw_path] = (size, digest)
    if declared_files != actual_files:
        raise ReleaseEvidenceError("production handoff file inventory is incomplete or has a digest mismatch")
    if not _verify_production_handoff_signature(
        root=root,
        manifest=manifest,
        trusted_public_key=trusted_public_key,
    ):
        raise ReleaseEvidenceError("offline production handoff verification requires a signature")
    return {
        "schema_version": 2,
        "status": "passed",
        "handoff": str(root),
        "category_count": len(declared_categories),
        "files_verified": len(declared_files),
        "signature_verified": True,
        "production_claim": False,
    }
