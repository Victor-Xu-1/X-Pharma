from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.release.contracts.core import IMAGE_PATTERN
from scripts.release.contracts.security import SECURITY_REQUIRED_FILES
from scripts.release.io import _load_json_object, _parse_timestamp, _sha256_file
from scripts.release.records import ReleaseEvidenceError, RepositorySubject, SecurityEvidence


def validate_security_evidence(
    directory: Path,
    subject: RepositorySubject,
    *,
    maximum_age_hours: int | None = None,
) -> SecurityEvidence:
    try:
        resolved = directory.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("security evidence directory does not exist") from exc
    if not resolved.is_dir() or directory.is_symlink():
        raise ReleaseEvidenceError("security evidence must be a regular directory")
    present_files: set[str] = set()
    for candidate in resolved.rglob("*"):
        if candidate.is_symlink():
            raise ReleaseEvidenceError(f"security evidence contains a symbolic link: {candidate}")
        if not candidate.is_dir() and not candidate.is_file():
            raise ReleaseEvidenceError(f"security evidence contains a non-regular entry: {candidate}")
        if candidate.is_file():
            present_files.add(candidate.relative_to(resolved).as_posix())
    if missing_files := sorted(SECURITY_REQUIRED_FILES - present_files):
        raise ReleaseEvidenceError(f"security evidence is incomplete: {', '.join(missing_files)}")
    if unexpected_files := sorted(present_files - SECURITY_REQUIRED_FILES):
        raise ReleaseEvidenceError(f"security evidence contains unexpected files: {', '.join(unexpected_files)}")
    manifest_path = resolved / "evidence-manifest.json"
    manifest = _load_json_object(manifest_path, "security evidence manifest")
    if manifest.get("schema_version") != 1:
        raise ReleaseEvidenceError("unsupported security evidence manifest schema")
    if manifest.get("git_commit") != subject.commit or manifest.get("git_worktree_state") != "clean":
        raise ReleaseEvidenceError("security evidence is not bound to the current clean commit")
    if (
        manifest.get("source_file_count") != subject.source_file_count
        or manifest.get("source_tree_sha256") != subject.source_tree_sha256
    ):
        raise ReleaseEvidenceError("security evidence source tree differs from the current commit")
    generated_at = _parse_timestamp(manifest.get("generated_at"), "security evidence generated_at")
    now = datetime.now(UTC)
    if generated_at > now + timedelta(minutes=5):
        raise ReleaseEvidenceError("security evidence timestamp is in the future")
    if maximum_age_hours is not None and now - generated_at > timedelta(hours=maximum_age_hours):
        raise ReleaseEvidenceError("security evidence is older than the release policy permits")
    raw_targets = manifest.get("targets")
    if not isinstance(raw_targets, dict) or not raw_targets:
        raise ReleaseEvidenceError("security evidence does not identify scanned image targets")
    targets: dict[str, str] = {}
    for name, image in raw_targets.items():
        if not isinstance(name, str) or not isinstance(image, str) or not IMAGE_PATTERN.fullmatch(image):
            raise ReleaseEvidenceError("security evidence contains an invalid image target")
        targets[name] = image
    policies = manifest.get("policies")
    if not isinstance(policies, dict) or not isinstance(policies.get("release_mode"), bool):
        raise ReleaseEvidenceError("security evidence policies are invalid")
    unresolved = policies.get("unresolved_high_critical")
    if not isinstance(unresolved, dict) or not unresolved:
        raise ReleaseEvidenceError("security unresolved vulnerability inventory is invalid")
    unresolved_total = 0
    for count in unresolved.values():
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ReleaseEvidenceError("security unresolved vulnerability inventory is invalid")
        unresolved_total += count
    risk_reference = policies.get("risk_acceptance_reference", "")
    if not isinstance(risk_reference, str):
        raise ReleaseEvidenceError("security risk acceptance reference is invalid")
    if policies["release_mode"] and unresolved_total > 0 and not risk_reference.strip():
        raise ReleaseEvidenceError("release security evidence lacks a risk acceptance reference")
    return SecurityEvidence(
        directory=resolved,
        manifest_sha256=_sha256_file(manifest_path),
        generated_at=generated_at,
        targets=targets,
        release_mode=policies["release_mode"],
        risk_acceptance_reference=risk_reference,
    )
