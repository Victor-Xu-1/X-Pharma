from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from scripts.release.contracts.core import CATEGORY_PATTERN, MAX_RELEASE_STATEMENTS, SHA256_PATTERN, STATEMENT_SCHEMA
from scripts.release.contracts.production import (
    MAX_PRODUCTION_BATCH_CATEGORIES,
    PRODUCTION_BATCH_CATEGORY_FIELDS,
    PRODUCTION_BATCH_MANIFEST_FIELDS,
    PRODUCTION_BATCH_MANIFEST_SCHEMA,
)
from scripts.release.io import _load_json_object, _parse_timestamp, _sha256_file, _subject_document
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError, RepositorySubject, SecurityEvidence
from scripts.release.validation import _validate_specialized_evidence


def collect_release_statements(
    statements: list[Path],
    statement_directories: list[Path],
) -> list[Path]:
    collected: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path, *, require_standard_name: bool = False) -> None:
        if path.is_symlink():
            raise ReleaseEvidenceError(f"release gate statement cannot be a symbolic link: {path}")
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ReleaseEvidenceError(f"release gate statement does not exist: {path}") from exc
        if not resolved.is_file() or (require_standard_name and resolved.name != "gate-statement.json"):
            raise ReleaseEvidenceError(f"release gate statement path is invalid: {path}")
        if resolved in seen:
            raise ReleaseEvidenceError(f"duplicate release gate statement path: {resolved}")
        if len(collected) >= MAX_RELEASE_STATEMENTS:
            raise ReleaseEvidenceError(f"release statement count exceeds {MAX_RELEASE_STATEMENTS}")
        seen.add(resolved)
        collected.append(resolved)

    for statement in statements:
        add(statement)
    for raw_directory in statement_directories:
        if raw_directory.is_symlink():
            raise ReleaseEvidenceError(f"release statement directory cannot be a symbolic link: {raw_directory}")
        try:
            directory = raw_directory.resolve(strict=True)
        except OSError as exc:
            raise ReleaseEvidenceError(f"release statement directory does not exist: {raw_directory}") from exc
        if not directory.is_dir():
            raise ReleaseEvidenceError(f"release statement directory is invalid: {raw_directory}")
        discovered = 0
        discovered_categories: dict[str, Path] = {}
        for category_directory in sorted(directory.iterdir(), key=lambda item: item.name):
            if category_directory.is_symlink():
                raise ReleaseEvidenceError(
                    f"release statement category directory cannot be a symbolic link: {category_directory}"
                )
            if not category_directory.is_dir() or CATEGORY_PATTERN.fullmatch(category_directory.name) is None:
                continue
            candidate = category_directory / "gate-statement.json"
            if candidate.exists() or candidate.is_symlink():
                add(candidate, require_standard_name=True)
                discovered += 1
                discovered_categories[category_directory.name] = candidate.resolve(strict=True)
        if discovered == 0:
            raise ReleaseEvidenceError(f"release statement directory contains no category statements: {directory}")
        batch_manifest_path = directory / "batch-manifest.json"
        if batch_manifest_path.exists() or batch_manifest_path.is_symlink():
            _validate_production_batch_directory(batch_manifest_path, discovered_categories)
    return collected


def _validate_production_batch_directory(
    manifest_path: Path,
    statements: dict[str, Path],
) -> None:
    if manifest_path.is_symlink():
        raise ReleaseEvidenceError("production evidence batch manifest cannot be a symbolic link")
    document = _load_json_object(manifest_path, "production evidence batch manifest")
    categories = document.get("categories")
    if (
        set(document) != PRODUCTION_BATCH_MANIFEST_FIELDS
        or document.get("schema") != PRODUCTION_BATCH_MANIFEST_SCHEMA
        or document.get("schema_version") != 1
        or document.get("status") != "registered"
        or document.get("production_claim") is not False
        or not isinstance(categories, list)
        or not 1 <= len(categories) <= MAX_PRODUCTION_BATCH_CATEGORIES
        or not isinstance(document.get("subject"), dict)
        or not isinstance(document.get("security_manifest_sha256"), str)
        or SHA256_PATTERN.fullmatch(document["security_manifest_sha256"]) is None
    ):
        raise ReleaseEvidenceError("production evidence batch manifest has an invalid registered contract")
    _parse_timestamp(document.get("generated_at"), "production evidence batch generated_at")
    batch_subject = document["subject"]
    batch_security_sha256 = document["security_manifest_sha256"]
    declared: set[str] = set()
    for item in categories:
        if not isinstance(item, dict) or set(item) != PRODUCTION_BATCH_CATEGORY_FIELDS:
            raise ReleaseEvidenceError("production evidence batch manifest contains an invalid category")
        category = item.get("category")
        statement = item.get("statement")
        digest = item.get("statement_sha256")
        if (
            not isinstance(category, str)
            or category in declared
            or category not in statements
            or statement != f"{category}/gate-statement.json"
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
            or _sha256_file(statements[category]) != digest
        ):
            raise ReleaseEvidenceError("production evidence batch manifest statement binding is invalid")
        statement_document = _load_json_object(statements[category], f"{category} production gate statement")
        if (
            statement_document.get("category") != category
            or statement_document.get("subject") != batch_subject
            or statement_document.get("security_manifest_sha256") != batch_security_sha256
        ):
            raise ReleaseEvidenceError("production evidence batch manifest release binding is invalid")
        declared.add(category)
    if declared != set(statements):
        raise ReleaseEvidenceError("production evidence batch manifest does not cover every category statement")


def _statement_category(
    path: Path,
    *,
    policy: EvidencePolicy,
    subject: RepositorySubject,
    security: SecurityEvidence,
) -> tuple[str, dict[str, Any]]:
    statement = _load_json_object(path, "release gate statement")
    if statement.get("schema") != STATEMENT_SCHEMA or statement.get("schema_version") != 1:
        raise ReleaseEvidenceError(f"unsupported release gate statement schema: {path}")
    category = statement.get("category")
    if not isinstance(category, str) or category not in policy.categories:
        raise ReleaseEvidenceError(f"release gate statement has an unknown category: {path}")
    if statement.get("status") != "passed":
        raise ReleaseEvidenceError(f"release gate statement did not pass: {category}")
    execution = statement.get("execution")
    if not isinstance(execution, dict) or execution.get("exit_code") != 0:
        raise ReleaseEvidenceError(f"release gate statement has an invalid execution result: {category}")
    if statement.get("subject") != _subject_document(subject, security.targets):
        raise ReleaseEvidenceError(f"release gate statement subject differs from the release: {category}")
    if statement.get("security_manifest_sha256") != security.manifest_sha256:
        raise ReleaseEvidenceError(f"release gate statement uses different security evidence: {category}")
    generated_at = _parse_timestamp(statement.get("generated_at"), f"{category} generated_at")
    now = datetime.now(UTC)
    if generated_at > now + timedelta(minutes=5):
        raise ReleaseEvidenceError(f"release gate statement timestamp is in the future: {category}")
    if now - generated_at > timedelta(hours=policy.categories[category]):
        raise ReleaseEvidenceError(f"release gate statement is stale: {category}")
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError(f"release gate statement attachments are invalid: {category}")
    missing_attachments = statement.get("missing_attachments", [])
    if not isinstance(missing_attachments, list) or missing_attachments:
        raise ReleaseEvidenceError(f"passed release gate statement has missing attachments: {category}")
    seen: set[str] = set()
    for raw_attachment in raw_attachments:
        if not isinstance(raw_attachment, dict):
            raise ReleaseEvidenceError(f"release gate statement attachment is invalid: {category}")
        relative_text = raw_attachment.get("path")
        relative = PurePosixPath(relative_text) if isinstance(relative_text, str) else PurePosixPath("/")
        if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative_text in seen:
            raise ReleaseEvidenceError(f"release gate statement attachment path is unsafe: {category}")
        seen.add(str(relative_text))
        attachment = path.parent.joinpath(*relative.parts)
        if attachment.is_symlink() or not attachment.is_file():
            raise ReleaseEvidenceError(f"release gate statement attachment is missing: {relative_text}")
        size = raw_attachment.get("size")
        sha256 = raw_attachment.get("sha256")
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or attachment.stat().st_size != size
            or not isinstance(sha256, str)
            or not SHA256_PATTERN.fullmatch(sha256)
            or _sha256_file(attachment) != sha256
        ):
            raise ReleaseEvidenceError(f"release gate statement attachment was modified: {relative_text}")
    _validate_specialized_evidence(path, category, statement, policy=policy)
    return category, statement
