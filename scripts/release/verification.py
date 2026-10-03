from __future__ import annotations

import base64
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from scripts.release.contracts.core import (
    BUNDLE_SCHEMA,
    COMMIT_PATTERN,
    IMAGE_PATTERN,
    SHA256_PATTERN,
    SIGNATURE_SCHEMA,
    STATEMENT_SCHEMA,
)
from scripts.release.contracts.security import SECURITY_REQUIRED_FILES
from scripts.release.crypto import _load_public_key, _public_key_fingerprint
from scripts.release.io import _load_json_object, _parse_timestamp, _safe_checksum_path, _sha256_bytes, _sha256_file
from scripts.release.policy import _repository_goal_matrix_contract, goal_completion_audit, load_policy
from scripts.release.records import PolicyLevel, ReleaseEvidenceError
from scripts.release.validation import _validate_specialized_evidence


def _validate_bundled_semantics(root: Path, manifest: dict[str, Any]) -> tuple[str, PolicyLevel]:
    level_name = manifest.get("release_level")
    if not isinstance(level_name, str):
        raise ReleaseEvidenceError("release manifest level is invalid")
    policy_path = root / "policy" / "evidence-policy.json"
    policy = load_policy(policy_path)
    if level_name not in policy.levels:
        raise ReleaseEvidenceError("release manifest level is absent from its bundled policy")
    level = policy.levels[level_name]
    policy_metadata = manifest.get("policy")
    if (
        not isinstance(policy_metadata, dict)
        or policy_metadata.get("sha256") != _sha256_file(policy_path)
        or policy_metadata.get("required_categories") != sorted(level.required_categories)
    ):
        raise ReleaseEvidenceError("release manifest policy binding is invalid")
    if (
        manifest.get("gate_status") != "evidence_complete"
        or manifest.get("approval_status") != "pending_deployment_approval"
        or manifest.get("production_claim") is not False
    ):
        raise ReleaseEvidenceError("release manifest makes an invalid approval claim")
    subject = manifest.get("subject")
    if not isinstance(subject, dict):
        raise ReleaseEvidenceError("release manifest subject is invalid")
    commit = subject.get("git_commit")
    source_count = subject.get("source_file_count")
    source_sha256 = subject.get("source_tree_sha256")
    targets = subject.get("targets")
    if (
        not isinstance(commit, str)
        or not COMMIT_PATTERN.fullmatch(commit)
        or not isinstance(source_count, int)
        or isinstance(source_count, bool)
        or source_count <= 0
        or not isinstance(source_sha256, str)
        or not SHA256_PATTERN.fullmatch(source_sha256)
        or not isinstance(targets, dict)
        or not targets
        or not all(
            isinstance(name, str) and isinstance(image, str) and IMAGE_PATTERN.fullmatch(image)
            for name, image in targets.items()
        )
    ):
        raise ReleaseEvidenceError("release manifest subject is invalid")

    generated_at = _parse_timestamp(manifest.get("generated_at"), "release bundle generated_at")
    if generated_at > datetime.now(UTC) + timedelta(minutes=5):
        raise ReleaseEvidenceError("release bundle timestamp is in the future")
    security_root = root / "evidence" / "security"
    security_files = {path.relative_to(security_root).as_posix() for path in security_root.rglob("*") if path.is_file()}
    if security_files != SECURITY_REQUIRED_FILES:
        raise ReleaseEvidenceError("bundled security evidence inventory is incomplete or unexpected")
    security_metadata = manifest.get("security")
    security_manifest_path = security_root / "evidence-manifest.json"
    security_manifest = _load_json_object(security_manifest_path, "bundled security evidence manifest")
    if not isinstance(security_metadata, dict):
        raise ReleaseEvidenceError("release manifest security binding is invalid")
    security_sha256 = _sha256_file(security_manifest_path)
    security_policies = security_manifest.get("policies")
    unresolved = security_policies.get("unresolved_high_critical") if isinstance(security_policies, dict) else None
    release_mode = security_policies.get("release_mode") if isinstance(security_policies, dict) else None
    risk_reference = security_policies.get("risk_acceptance_reference") if isinstance(security_policies, dict) else None
    if (
        security_manifest.get("schema_version") != 1
        or not isinstance(release_mode, bool)
        or not isinstance(risk_reference, str)
        or not isinstance(unresolved, dict)
        or not unresolved
        or not all(
            isinstance(count, int) and not isinstance(count, bool) and count >= 0 for count in unresolved.values()
        )
    ):
        raise ReleaseEvidenceError("bundled security evidence policies are invalid")
    if release_mode and sum(unresolved.values()) > 0 and not risk_reference.strip():
        raise ReleaseEvidenceError("bundled release security evidence lacks a risk acceptance reference")
    security_generated_at = _parse_timestamp(security_manifest.get("generated_at"), "bundled security generated_at")
    if security_generated_at > generated_at + timedelta(minutes=5) or generated_at - security_generated_at > timedelta(
        hours=level.security_max_age_hours
    ):
        raise ReleaseEvidenceError("bundled security evidence is outside its evidence window")
    if (
        security_metadata.get("manifest_sha256") != security_sha256
        or security_manifest.get("git_commit") != commit
        or security_manifest.get("git_worktree_state") != "clean"
        or security_manifest.get("source_file_count") != source_count
        or security_manifest.get("source_tree_sha256") != source_sha256
        or security_manifest.get("targets") != targets
        or not isinstance(security_policies, dict)
        or security_metadata.get("release_mode") != security_policies.get("release_mode")
        or security_metadata.get("risk_acceptance_reference") != security_policies.get("risk_acceptance_reference")
        or _parse_timestamp(security_metadata.get("generated_at"), "release security generated_at")
        != security_generated_at
    ):
        raise ReleaseEvidenceError("release manifest security binding is invalid")
    if level.require_release_security and security_metadata.get("release_mode") is not True:
        raise ReleaseEvidenceError("production bundle does not contain release-mode security evidence")

    statement_index = manifest.get("statements")
    if not isinstance(statement_index, dict):
        raise ReleaseEvidenceError("release manifest statement index is invalid")
    if not level.required_categories.issubset(statement_index):
        raise ReleaseEvidenceError("release manifest omits required evidence categories")
    for category, relative_text in statement_index.items():
        if category not in policy.categories or relative_text != f"evidence/{category}/gate-statement.json":
            raise ReleaseEvidenceError("release manifest statement index is invalid")
        statement_path = root.joinpath(*PurePosixPath(relative_text).parts)
        statement = _load_json_object(statement_path, f"bundled {category} statement")
        execution = statement.get("execution")
        if (
            statement.get("schema") != STATEMENT_SCHEMA
            or statement.get("schema_version") != 1
            or statement.get("category") != category
            or statement.get("status") != "passed"
            or statement.get("subject") != subject
            or statement.get("security_manifest_sha256") != security_sha256
            or not isinstance(execution, dict)
            or execution.get("exit_code") != 0
        ):
            raise ReleaseEvidenceError(f"bundled release statement is invalid: {category}")
        statement_time = _parse_timestamp(statement.get("generated_at"), f"bundled {category} generated_at")
        if statement_time > generated_at + timedelta(minutes=5) or generated_at - statement_time > timedelta(
            hours=policy.categories[category]
        ):
            raise ReleaseEvidenceError(f"bundled release statement is outside its evidence window: {category}")
        raw_attachments = statement.get("attachments")
        if not isinstance(raw_attachments, list):
            raise ReleaseEvidenceError(f"bundled release statement attachments are invalid: {category}")
        for attachment_metadata in raw_attachments:
            if not isinstance(attachment_metadata, dict):
                raise ReleaseEvidenceError(f"bundled release statement attachment is invalid: {category}")
            attachment_text = attachment_metadata.get("path")
            if not isinstance(attachment_text, str):
                raise ReleaseEvidenceError(f"bundled release statement attachment is invalid: {category}")
            attachment_relative = _safe_checksum_path(attachment_text)
            attachment = statement_path.parent.joinpath(*attachment_relative.parts)
            if (
                attachment.is_symlink()
                or not attachment.is_file()
                or attachment_metadata.get("size") != attachment.stat().st_size
                or attachment_metadata.get("sha256") != _sha256_file(attachment)
            ):
                raise ReleaseEvidenceError(f"bundled release statement attachment was modified: {category}")
        _validate_specialized_evidence(statement_path, category, statement, policy=policy)
    if level.require_signed_git_tag and not isinstance(manifest.get("release_tag"), str):
        raise ReleaseEvidenceError("production bundle does not identify its verified Git tag")
    return level_name, level


def _verify_bundle(root: Path, trusted_key: Ed25519PublicKey | None) -> dict[str, Any]:
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("release bundle does not exist") from exc
    if not resolved.is_dir() or root.is_symlink():
        raise ReleaseEvidenceError("release bundle must be a regular directory")
    for path in resolved.rglob("*"):
        if path.is_symlink():
            raise ReleaseEvidenceError(f"release bundle contains a symbolic link: {path.relative_to(resolved)}")
        if not path.is_dir() and not path.is_file():
            raise ReleaseEvidenceError(f"release bundle contains a non-regular entry: {path.relative_to(resolved)}")
    checksum_path = resolved / "SHA256SUMS"
    if not checksum_path.is_file():
        raise ReleaseEvidenceError("release bundle is missing SHA256SUMS")
    checksums: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ReleaseEvidenceError("release bundle contains an invalid checksum line")
        digest, relative_text = match.groups()
        relative = _safe_checksum_path(relative_text)
        normalized = relative.as_posix()
        if normalized in checksums or normalized == "SHA256SUMS":
            raise ReleaseEvidenceError(f"duplicate or recursive checksum entry: {normalized}")
        checksums[normalized] = digest
    actual_files = {
        path.relative_to(resolved).as_posix()
        for path in resolved.rglob("*")
        if path.is_file() and path != checksum_path
    }
    if set(checksums) != actual_files:
        raise ReleaseEvidenceError("release bundle checksum inventory differs from its files")
    for relative_text, expected in checksums.items():
        if _sha256_file(resolved.joinpath(*PurePosixPath(relative_text).parts)) != expected:
            raise ReleaseEvidenceError(f"release bundle file digest mismatch: {relative_text}")

    manifest_path = resolved / "release-manifest.json"
    manifest = _load_json_object(manifest_path, "release bundle manifest")
    if manifest.get("schema") != BUNDLE_SCHEMA or manifest.get("schema_version") != 1:
        raise ReleaseEvidenceError("unsupported release bundle schema")
    raw_inventory = manifest.get("files")
    if not isinstance(raw_inventory, list):
        raise ReleaseEvidenceError("release bundle payload inventory is invalid")
    manifest_inventory: dict[str, tuple[int, str]] = {}
    for item in raw_inventory:
        if not isinstance(item, dict):
            raise ReleaseEvidenceError("release bundle payload entry is invalid")
        relative_text = item.get("path")
        size = item.get("size")
        digest = item.get("sha256")
        if (
            not isinstance(relative_text, str)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(digest, str)
            or not SHA256_PATTERN.fullmatch(digest)
        ):
            raise ReleaseEvidenceError("release bundle payload entry is invalid")
        normalized_path = _safe_checksum_path(relative_text).as_posix()
        if normalized_path in manifest_inventory:
            raise ReleaseEvidenceError(f"duplicate release bundle payload entry: {normalized_path}")
        manifest_inventory[normalized_path] = (size, digest)
    control_files = {"release-manifest.json", "release-manifest.sig.json", "SHA256SUMS"}
    payload_files = actual_files - control_files
    if set(manifest_inventory) != payload_files:
        raise ReleaseEvidenceError("release manifest payload inventory differs from bundled evidence")
    for relative_text, (expected_size, expected_digest) in manifest_inventory.items():
        path = resolved.joinpath(*PurePosixPath(relative_text).parts)
        if path.stat().st_size != expected_size or checksums.get(relative_text) != expected_digest:
            raise ReleaseEvidenceError(f"release manifest payload metadata mismatch: {relative_text}")

    level_name, level = _validate_bundled_semantics(resolved, manifest)

    signature_metadata = manifest.get("signature")
    if not isinstance(signature_metadata, dict):
        raise ReleaseEvidenceError("release manifest signature policy is invalid")
    signature_required = signature_metadata.get("required")
    signature_present = signature_metadata.get("present")
    if not isinstance(signature_required, bool) or not isinstance(signature_present, bool):
        raise ReleaseEvidenceError("release manifest signature policy is invalid")
    if signature_required != level.require_bundle_signature:
        raise ReleaseEvidenceError("release manifest signature requirement differs from policy")
    signature_path = resolved / "release-manifest.sig.json"
    if signature_present != signature_path.is_file():
        raise ReleaseEvidenceError("release bundle signature presence differs from its manifest")
    if signature_required and not signature_present:
        raise ReleaseEvidenceError("release bundle requires a signature")
    if signature_present:
        if trusted_key is None:
            raise ReleaseEvidenceError("a trusted Ed25519 public key is required to verify this bundle")
        signature_document = _load_json_object(signature_path, "release bundle signature")
        if (
            signature_document.get("schema") != SIGNATURE_SCHEMA
            or signature_document.get("schema_version") != 1
            or signature_document.get("algorithm") != "Ed25519"
            or signature_document.get("key_id") != signature_metadata.get("key_id")
            or signature_document.get("public_key_sha256") != _public_key_fingerprint(trusted_key)
        ):
            raise ReleaseEvidenceError("release bundle signature metadata is invalid")
        manifest_payload = manifest_path.read_bytes()
        if signature_document.get("manifest_sha256") != _sha256_bytes(manifest_payload):
            raise ReleaseEvidenceError("release bundle signature references a different manifest")
        encoded_signature = signature_document.get("signature")
        if not isinstance(encoded_signature, str):
            raise ReleaseEvidenceError("release bundle signature is invalid")
        try:
            signature = base64.b64decode(encoded_signature, validate=True)
            trusted_key.verify(signature, manifest_payload)
        except (ValueError, InvalidSignature) as exc:
            raise ReleaseEvidenceError("release bundle signature verification failed") from exc
    if level_name == "production" and not signature_present:
        raise ReleaseEvidenceError("production release bundle is unsigned")
    bundled_policy = load_policy(resolved / "policy" / "evidence-policy.json")
    matrix, _ = _repository_goal_matrix_contract(resolved, bundled_policy, level_name)
    declared_goal = manifest.get("goal_section_19")
    goal_result: dict[str, Any] | None = None
    if matrix is None:
        if declared_goal is not None:
            raise ReleaseEvidenceError("release manifest declares GOAL status without a bundled matrix")
    else:
        statements = manifest.get("statements")
        security = manifest.get("security")
        if not isinstance(statements, dict) or not isinstance(security, dict):
            raise ReleaseEvidenceError("release manifest GOAL inputs are invalid")
        goal_result = goal_completion_audit(
            matrix,
            present_categories=set(statements),
            release_security_verified=security.get("release_mode") is True,
            signed_git_tag_verified=level.require_signed_git_tag and isinstance(manifest.get("release_tag"), str),
            bundle_signature_verified=signature_present,
            release_level=level_name,
            release_eligible=True,
        )
        if declared_goal != goal_result:
            raise ReleaseEvidenceError("release manifest GOAL completion status is invalid")
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "passed",
        "release_level": level_name,
        "git_commit": manifest.get("subject", {}).get("git_commit")
        if isinstance(manifest.get("subject"), dict)
        else None,
        "files_verified": len(actual_files),
        "signature_verified": signature_present,
        "production_claim": False,
    }
    if goal_result is not None:
        result["goal_section_19"] = goal_result
    return result


def verify_bundle(bundle: Path, trusted_public_key: Path | None = None) -> dict[str, Any]:
    key = _load_public_key(trusted_public_key) if trusted_public_key is not None else None
    return _verify_bundle(bundle, key)
