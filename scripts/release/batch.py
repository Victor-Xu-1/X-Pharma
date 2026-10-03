from __future__ import annotations

import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.release.contracts.production import (
    MAX_PRODUCTION_BATCH_CATEGORIES,
    MAX_PRODUCTION_INTAKE_BYTES,
    PRODUCTION_BATCH_ENTRY_FIELDS,
    PRODUCTION_BATCH_INTAKE_FIELDS,
    PRODUCTION_BATCH_INTAKE_SCHEMA,
    PRODUCTION_BATCH_MANIFEST_SCHEMA,
    PRODUCTION_INTAKE_SCHEMA,
)
from scripts.release.intake import register_production_evidence
from scripts.release.io import (
    _atomic_write,
    _canonical_json,
    _external_directory_output,
    _external_evidence_source,
    _fsync_directory,
    _load_json_object,
    _rename_noreplace,
    _sha256_file,
    _subject_document,
)
from scripts.release.policy import _require_authoritative_production_policy, load_policy
from scripts.release.records import ReleaseEvidenceError
from scripts.release.repository import repository_subject
from scripts.release.security import validate_security_evidence
from scripts.release.statements import _statement_category


def register_production_evidence_batch(
    *,
    repo: Path,
    policy_path: Path,
    security_directory: Path,
    manifest_path: Path,
    output: Path,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    _require_authoritative_production_policy(repo, policy, "production")
    resolved_repo, resolved_output = _external_directory_output(repo, output, "production evidence batch")
    try:
        manifest = manifest_path.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("production evidence batch manifest does not exist") from exc
    if manifest_path.is_symlink() or not manifest.is_file():
        raise ReleaseEvidenceError("production evidence batch manifest must be a regular file")
    if manifest == resolved_repo or resolved_repo in manifest.parents:
        raise ReleaseEvidenceError("production evidence batch manifest must be outside the source repository")
    manifest_size = manifest.stat().st_size
    if not 0 < manifest_size <= MAX_PRODUCTION_INTAKE_BYTES:
        raise ReleaseEvidenceError("production evidence batch manifest has an invalid size")
    document = _load_json_object(manifest, "production evidence batch manifest")
    entries = document.get("requests")
    if (
        set(document) != PRODUCTION_BATCH_INTAKE_FIELDS
        or document.get("schema") != PRODUCTION_BATCH_INTAKE_SCHEMA
        or document.get("schema_version") != 1
        or not isinstance(entries, list)
        or not 1 <= len(entries) <= MAX_PRODUCTION_BATCH_CATEGORIES
    ):
        raise ReleaseEvidenceError("production evidence batch manifest has an invalid schema")

    request_paths: dict[str, Path] = {}
    seen_requests: set[Path] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != PRODUCTION_BATCH_ENTRY_FIELDS:
            raise ReleaseEvidenceError("production evidence batch contains an invalid request entry")
        category = entry.get("category")
        if not isinstance(category, str) or category not in policy.production_contracts or category in request_paths:
            raise ReleaseEvidenceError("production evidence batch contains an invalid or duplicate category")
        request = _external_evidence_source(entry.get("request_path"), repo=resolved_repo, request=manifest)
        if request in seen_requests:
            raise ReleaseEvidenceError("production evidence batch cannot reuse one intake request")
        request_document = _load_json_object(request, f"{category} production evidence intake request")
        if request_document.get("category") != category or request_document.get("schema") != PRODUCTION_INTAKE_SCHEMA:
            raise ReleaseEvidenceError("production evidence batch entry does not match its intake request")
        request_paths[category] = request
        seen_requests.add(request)
    expected_categories = set(policy.production_contracts)
    if set(request_paths) != expected_categories:
        missing = ", ".join(sorted(expected_categories - request_paths.keys()))
        raise ReleaseEvidenceError(f"production evidence batch is incomplete; missing categories: {missing}")

    subject = repository_subject(resolved_repo)
    level = policy.levels["production"]
    security = validate_security_evidence(
        security_directory,
        subject,
        maximum_age_hours=level.security_max_age_hours,
    )
    if not security.release_mode:
        raise ReleaseEvidenceError("production evidence batch requires release-mode security evidence")

    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.batch-", dir=resolved_output.parent))
    category_documents: list[dict[str, object]] = []
    try:
        for category, request in sorted(request_paths.items()):
            category_output = staging / category
            register_production_evidence(
                repo=resolved_repo,
                policy_path=policy.path,
                security_directory=security.directory,
                request_path=request,
                output=category_output,
            )
            statement = category_output / "gate-statement.json"
            validated_category, _ = _statement_category(
                statement,
                policy=policy,
                subject=subject,
                security=security,
            )
            if validated_category != category:
                raise ReleaseEvidenceError("registered production category differs from its batch entry")
            category_documents.append(
                {
                    "category": category,
                    "statement": statement.relative_to(staging).as_posix(),
                    "statement_sha256": _sha256_file(statement),
                }
            )
        batch_manifest = {
            "schema": PRODUCTION_BATCH_MANIFEST_SCHEMA,
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "registered",
            "production_claim": False,
            "subject": _subject_document(subject, security.targets),
            "security_manifest_sha256": security.manifest_sha256,
            "categories": category_documents,
        }
        _atomic_write(staging / "batch-manifest.json", _canonical_json(batch_manifest))
        if repository_subject(resolved_repo) != subject:
            raise ReleaseEvidenceError("repository subject changed while registering production evidence batch")
        if (
            validate_security_evidence(
                security.directory,
                subject,
                maximum_age_hours=level.security_max_age_hours,
            )
            != security
        ):
            raise ReleaseEvidenceError("security evidence changed while registering production evidence batch")
        for directory in sorted((path for path in staging.rglob("*") if path.is_dir()), reverse=True):
            directory.chmod(0o700)
            _fsync_directory(directory)
        staging.chmod(0o700)
        _fsync_directory(staging)
        _rename_noreplace(staging, resolved_output)
        _fsync_directory(resolved_output.parent)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        "schema_version": 1,
        "status": "registered",
        "output": str(resolved_output),
        "category_count": len(category_documents),
        "production_claim": False,
    }
