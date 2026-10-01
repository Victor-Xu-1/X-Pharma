from __future__ import annotations

import base64
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.release.contracts.core import SIGNATURE_SCHEMA
from scripts.release.contracts.production import PRODUCTION_HANDOFF_SCHEMA
from scripts.release.crypto import _load_signing_key, _public_key_fingerprint
from scripts.release.io import (
    _atomic_write,
    _canonical_json,
    _external_directory_output,
    _fsync_directory,
    _payload_inventory,
    _rename_noreplace,
    _sha256_bytes,
)
from scripts.release.policy import (
    _repository_goal_matrix_contract,
    _require_authoritative_production_policy,
    load_policy,
    production_evidence_requirements,
)
from scripts.release.records import ReleaseEvidenceError
from scripts.release.repository import repository_subject


def prepare_production_evidence_handoff(
    *,
    repo: Path,
    policy_path: Path,
    output: Path,
    signing_key_path: Path | None = None,
    signing_key_id: str | None = None,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    _require_authoritative_production_policy(repo, policy, "production")
    resolved_repo, resolved_output = _external_directory_output(repo, output, "production handoff")
    if signing_key_path is None and signing_key_id is not None:
        raise ReleaseEvidenceError("production handoff signing key id requires a signing key")
    if signing_key_path is not None and not signing_key_id:
        raise ReleaseEvidenceError("production handoff signing key id is required")
    if signing_key_id is not None and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}", signing_key_id) is None:
        raise ReleaseEvidenceError("production handoff signing key id is invalid")
    signer = _load_signing_key(signing_key_path) if signing_key_path is not None else None
    subject = repository_subject(resolved_repo)
    matrix, matrix_schema_path = _repository_goal_matrix_contract(resolved_repo, policy, "production")
    schema_names = (
        "mcp-sender-constraint-report.schema.json",
        "production-evidence-batch-intake.schema.json",
        "production-evidence-batch-manifest.schema.json",
        "production-evidence-handoff-manifest.schema.json",
        "production-evidence-intake.schema.json",
        "production-evidence-report.schema.json",
        "production-topology-live-probe.schema.json",
        "production-topology-report.schema.json",
    )
    schema_sources = [resolved_repo / "deploy" / "release" / name for name in schema_names]
    if any(path.is_symlink() or not path.is_file() for path in schema_sources):
        raise ReleaseEvidenceError("production handoff schemas are missing from the committed repository")
    try:
        policy_payload = policy.path.read_bytes()
        schema_payloads = {source.name: source.read_bytes() for source in schema_sources}
        matrix_payload = matrix.path.read_bytes() if matrix is not None else None
        matrix_schema_payload = matrix_schema_path.read_bytes() if matrix_schema_path is not None else None
    except OSError as exc:
        raise ReleaseEvidenceError("cannot read the committed production handoff contracts") from exc

    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.handoff-", dir=resolved_output.parent))
    try:
        _atomic_write(staging / "policy" / "evidence-policy.json", policy_payload)
        if (
            matrix is not None
            and matrix_schema_path is not None
            and matrix_payload is not None
            and matrix_schema_payload is not None
        ):
            _atomic_write(staging / "policy" / matrix.path.name, matrix_payload)
            _atomic_write(staging / "policy" / matrix_schema_path.name, matrix_schema_payload)
        for name, payload in schema_payloads.items():
            _atomic_write(staging / "schemas" / name, payload)
        categories: list[dict[str, object]] = []
        for category in sorted(policy.production_contracts):
            requirement_path = staging / "requirements" / f"{category}.json"
            requirements = production_evidence_requirements(policy_path=policy.path, category=category)
            _atomic_write(requirement_path, _canonical_json(requirements))
            categories.append(
                {
                    "category": category,
                    "requirements": requirement_path.relative_to(staging).as_posix(),
                }
            )
        inventory = _payload_inventory(staging)
        manifest = {
            "schema": PRODUCTION_HANDOFF_SCHEMA,
            "schema_version": 2,
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "requirements_only",
            "production_claim": False,
            "subject": {
                "git_commit": subject.commit,
                "source_file_count": subject.source_file_count,
                "source_tree_sha256": subject.source_tree_sha256,
            },
            "policy_sha256": _sha256_bytes(policy_payload),
            "categories": categories,
            "files": inventory,
            "signature": {
                "present": signer is not None,
                "key_id": signing_key_id,
                "public_key_sha256": _public_key_fingerprint(signer.public_key()) if signer is not None else None,
            },
        }
        manifest_payload = _canonical_json(manifest)
        _atomic_write(staging / "handoff-manifest.json", manifest_payload)
        if signer is not None:
            signature_document = {
                "schema": SIGNATURE_SCHEMA,
                "schema_version": 1,
                "algorithm": "Ed25519",
                "key_id": signing_key_id,
                "public_key_sha256": _public_key_fingerprint(signer.public_key()),
                "manifest_sha256": _sha256_bytes(manifest_payload),
                "signature": base64.b64encode(signer.sign(manifest_payload)).decode("ascii"),
            }
            _atomic_write(staging / "handoff-manifest.sig.json", _canonical_json(signature_document))
        if repository_subject(resolved_repo) != subject:
            raise ReleaseEvidenceError("repository subject changed while preparing the production handoff")
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
        "schema_version": 2,
        "status": "prepared",
        "output": str(resolved_output),
        "category_count": len(categories),
        "signature_present": signer is not None,
        "production_claim": False,
    }
