from __future__ import annotations

import base64
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.release.contracts.core import BUNDLE_SCHEMA, SIGNATURE_SCHEMA
from scripts.release.crypto import _load_signing_key, _public_key_fingerprint
from scripts.release.io import (
    _canonical_json,
    _copy_regular_tree,
    _payload_inventory,
    _rename_noreplace,
    _sha256_bytes,
    _sha256_file,
    _subject_document,
)
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
from scripts.release.verification import _verify_bundle


def assemble_bundle(
    *,
    repo: Path,
    policy_path: Path,
    level_name: str,
    security_directory: Path,
    statements: list[Path],
    output: Path,
    release_tag: str | None = None,
    signing_key_path: Path | None = None,
    signing_key_id: str | None = None,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    if level_name not in policy.levels:
        raise ReleaseEvidenceError(f"unknown release evidence level: {level_name}")
    _require_authoritative_production_policy(repo, policy, level_name)
    level = policy.levels[level_name]
    if output.exists() or output.is_symlink():
        raise ReleaseEvidenceError(f"refusing to overwrite release bundle: {output}")
    subject = repository_subject(repo)
    matrix, matrix_schema_path = _repository_goal_matrix_contract(repo, policy, level_name)
    security = validate_security_evidence(
        security_directory,
        subject,
        maximum_age_hours=level.security_max_age_hours,
    )
    if level.require_release_security and not security.release_mode:
        raise ReleaseEvidenceError("production evidence requires a security gate run in release mode")
    release_tag = _check_release_tag(repo, subject, release_tag, level.require_signed_git_tag)
    if level.require_bundle_signature and signing_key_path is None:
        raise ReleaseEvidenceError("production evidence requires an Ed25519 bundle signature")
    if signing_key_path is not None and not signing_key_id:
        raise ReleaseEvidenceError("a stable signing key ID is required with --signing-key")
    if signing_key_id is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}", signing_key_id):
        raise ReleaseEvidenceError("release signing key ID is invalid")

    validated: dict[str, tuple[Path, dict[str, Any]]] = {}
    for statement_path in statements:
        category, statement = _statement_category(
            statement_path.resolve(), policy=policy, subject=subject, security=security
        )
        if category in validated:
            raise ReleaseEvidenceError(f"duplicate release gate category: {category}")
        validated[category] = (statement_path.resolve(), statement)
    missing = sorted(level.required_categories - validated.keys())
    if missing:
        raise ReleaseEvidenceError(f"missing required {level_name} evidence categories: {', '.join(missing)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        policy_destination = staging / "policy" / "evidence-policy.json"
        policy_destination.parent.mkdir(parents=True)
        shutil.copyfile(policy.path, policy_destination)
        if matrix is not None and matrix_schema_path is not None:
            shutil.copyfile(matrix.path, staging / "policy" / matrix.path.name)
            shutil.copyfile(matrix_schema_path, staging / "policy" / matrix_schema_path.name)
        _copy_regular_tree(security.directory, staging / "evidence" / "security")
        statement_index: dict[str, str] = {}
        for category, (statement_path, statement) in sorted(validated.items()):
            category_root = staging / "evidence" / category
            category_root.mkdir(parents=True)
            destination_statement = category_root / "gate-statement.json"
            shutil.copyfile(statement_path, destination_statement)
            statement_index[category] = destination_statement.relative_to(staging).as_posix()
            for raw_attachment in statement["attachments"]:
                relative = PurePosixPath(raw_attachment["path"])
                source = statement_path.parent.joinpath(*relative.parts)
                destination = category_root.joinpath(*relative.parts)
                if destination == destination_statement:
                    raise ReleaseEvidenceError(f"attachment collides with bundled statement: {category}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)

        inventory = _payload_inventory(staging)
        generated_at = datetime.now(UTC).isoformat()
        manifest: dict[str, Any] = {
            "schema": BUNDLE_SCHEMA,
            "schema_version": 1,
            "generated_at": generated_at,
            "release_level": level_name,
            "gate_status": "evidence_complete",
            "approval_status": "pending_deployment_approval",
            "production_claim": False,
            "release_tag": release_tag,
            "subject": _subject_document(subject, security.targets),
            "security": {
                "manifest_sha256": security.manifest_sha256,
                "generated_at": security.generated_at.isoformat(),
                "release_mode": security.release_mode,
                "risk_acceptance_reference": security.risk_acceptance_reference,
            },
            "policy": {
                "sha256": _sha256_file(policy_destination),
                "required_categories": sorted(level.required_categories),
            },
            "statements": statement_index,
            "files": inventory,
            "signature": {
                "required": level.require_bundle_signature,
                "present": signing_key_path is not None,
                "key_id": signing_key_id,
            },
        }
        if matrix is not None:
            manifest["goal_section_19"] = goal_completion_audit(
                matrix,
                present_categories=set(validated),
                release_security_verified=security.release_mode,
                signed_git_tag_verified=level.require_signed_git_tag,
                bundle_signature_verified=signing_key_path is not None,
                release_level=level_name,
                release_eligible=True,
            )
        manifest_payload = _canonical_json(manifest)
        (staging / "release-manifest.json").write_bytes(manifest_payload)
        signer: Ed25519PrivateKey | None = None
        if signing_key_path is not None:
            signer = _load_signing_key(signing_key_path)
            public_key = signer.public_key()
            signature_document = {
                "schema": SIGNATURE_SCHEMA,
                "schema_version": 1,
                "algorithm": "Ed25519",
                "key_id": signing_key_id,
                "public_key_sha256": _public_key_fingerprint(public_key),
                "manifest_sha256": _sha256_bytes(manifest_payload),
                "signature": base64.b64encode(signer.sign(manifest_payload)).decode("ascii"),
            }
            (staging / "release-manifest.sig.json").write_bytes(_canonical_json(signature_document))
        checksum_lines = [
            f"{item['sha256']}  {item['path']}" for item in _payload_inventory(staging) if item["path"] != "SHA256SUMS"
        ]
        (staging / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
        verified = _verify_bundle(staging, signer.public_key() if signer is not None else None)
        if repository_subject(repo) != subject:
            raise ReleaseEvidenceError("repository subject changed while assembling the release bundle")
        for directory in [staging, *[path for path in staging.rglob("*") if path.is_dir()]]:
            directory.chmod(0o700)
        for file_path in [path for path in staging.rglob("*") if path.is_file()]:
            file_path.chmod(0o600)
        _rename_noreplace(staging, output)
        return verified
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
