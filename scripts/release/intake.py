from __future__ import annotations

import re
import shutil
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.core import CATEGORY_PATTERN, ENVIRONMENT_ID_PATTERN, STATEMENT_SCHEMA
from scripts.release.contracts.production import (
    MAX_PRODUCTION_EVIDENCE_TOTAL_BYTES,
    MAX_PRODUCTION_INTAKE_BYTES,
    PRODUCTION_GATE_SCHEMA,
    PRODUCTION_INTAKE_APPROVAL_FIELDS,
    PRODUCTION_INTAKE_ARTIFACT_FIELDS,
    PRODUCTION_INTAKE_FIELDS,
    PRODUCTION_INTAKE_SCHEMA,
)
from scripts.release.io import (
    _atomic_write,
    _canonical_json,
    _copy_external_evidence,
    _external_evidence_source,
    _fsync_directory,
    _load_json_object,
    _parse_timestamp,
    _production_intake_destination,
    _rename_noreplace,
    _sha256_bytes,
    _sha256_file,
    _subject_document,
    _valid_production_reference,
)
from scripts.release.policy import load_policy
from scripts.release.records import ReleaseEvidenceError
from scripts.release.repository import repository_subject
from scripts.release.security import validate_security_evidence
from scripts.release.validation import _validate_specialized_evidence


def register_production_evidence(
    *,
    repo: Path,
    policy_path: Path,
    security_directory: Path,
    request_path: Path,
    output: Path,
) -> dict[str, Any]:
    try:
        repo = repo.resolve(strict=True)
        request = request_path.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("production evidence repository or intake request does not exist") from exc
    policy = load_policy(policy_path)
    if request_path.is_symlink() or not request.is_file():
        raise ReleaseEvidenceError("production evidence intake request must be a regular file")
    request_size = request.stat().st_size
    if not 0 < request_size <= MAX_PRODUCTION_INTAKE_BYTES:
        raise ReleaseEvidenceError(
            "production evidence intake request must be non-empty and no larger than "
            f"{MAX_PRODUCTION_INTAKE_BYTES} bytes"
        )
    if request == repo or repo in request.parents:
        raise ReleaseEvidenceError("production evidence intake request must be outside the source repository")
    document = _load_json_object(request, "production evidence intake request")
    category = document.get("category")
    if (
        set(document) != PRODUCTION_INTAKE_FIELDS
        or document.get("schema") != PRODUCTION_INTAKE_SCHEMA
        or document.get("schema_version") != 1
        or not isinstance(category, str)
        or category not in policy.production_contracts
    ):
        raise ReleaseEvidenceError("production evidence intake request has an invalid schema or category")
    contract = policy.production_contracts[category]
    checks = document.get("checks")
    if (
        not isinstance(checks, list)
        or not all(isinstance(item, str) for item in checks)
        or len(checks) != len(set(checks))
        or set(checks) != contract.checks
    ):
        raise ReleaseEvidenceError("production evidence intake must acknowledge every contracted check exactly once")
    artifacts = document.get("artifacts")
    approvals = document.get("approvals")
    if (
        not isinstance(artifacts, list)
        or not contract.minimum_artifacts <= len(artifacts) <= 100
        or not isinstance(approvals, list)
        or not 1 <= len(approvals) <= 100
    ):
        raise ReleaseEvidenceError("production evidence intake has an invalid artifact or approval count")
    executor = document.get("executor")
    environment_id = document.get("environment_id")
    if (
        document.get("environment_kind") not in {"preproduction", "production"}
        or not isinstance(environment_id, str)
        or ENVIRONMENT_ID_PATTERN.fullmatch(environment_id) is None
    ):
        raise ReleaseEvidenceError("production evidence intake environment is invalid")
    environment_tokens = set(re.split(r"[^a-z0-9]+", environment_id.casefold()))
    if environment_tokens.intersection({"dev", "development", "local", "test", "testing"}):
        raise ReleaseEvidenceError("production evidence intake identifies a local or development environment")
    tested_at = _parse_timestamp(document.get("tested_at"), "production evidence intake tested_at")
    if (
        not isinstance(executor, dict)
        or set(executor) != {"organization", "team", "independent"}
        or not _valid_production_reference(executor.get("organization"))
        or not _valid_production_reference(executor.get("team"))
        or not isinstance(executor.get("independent"), bool)
        or (contract.require_independent_executor and executor.get("independent") is not True)
    ):
        raise ReleaseEvidenceError("production evidence intake executor is invalid")

    subject_before = repository_subject(repo)
    security = validate_security_evidence(security_directory, subject_before)
    try:
        output_parent = output.parent.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("production evidence output parent does not exist") from exc
    resolved_output = output_parent / output.name
    if (
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", output.name) is None
        or resolved_output.exists()
        or resolved_output.is_symlink()
    ):
        raise ReleaseEvidenceError(f"refusing to overwrite production evidence: {output}")
    if output_parent == repo or repo in output_parent.parents:
        raise ReleaseEvidenceError("production evidence output must be outside the source repository")

    started_at = datetime.now(UTC)
    started_clock = time.monotonic()
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.intake-", dir=output_parent))
    seen_destinations: set[str] = {contract.report_name, "gate-statement.json"}
    seen_sources: set[Path] = set()
    total_bytes = 0
    artifact_documents: list[dict[str, object]] = []
    approval_documents: list[dict[str, object]] = []
    try:
        artifact_names: set[str] = set()
        for item in artifacts:
            if not isinstance(item, dict) or set(item) != PRODUCTION_INTAKE_ARTIFACT_FIELDS:
                raise ReleaseEvidenceError("production evidence intake contains an invalid artifact")
            name = item.get("name")
            reference = item.get("reference")
            if (
                not _valid_production_reference(name)
                or name in artifact_names
                or not _valid_production_reference(reference)
            ):
                raise ReleaseEvidenceError("production evidence intake contains an invalid artifact identity")
            relative = _production_intake_destination(item.get("destination"), category=category, approval=False)
            destination_text = relative.as_posix()
            if destination_text in seen_destinations:
                raise ReleaseEvidenceError("production evidence intake contains a duplicate destination")
            source = _external_evidence_source(item.get("source_path"), repo=repo, request=request)
            if source in seen_sources:
                raise ReleaseEvidenceError("production evidence intake cannot reuse one source file")
            size, digest = _copy_external_evidence(source, staging.joinpath(*relative.parts))
            total_bytes += size
            if total_bytes > MAX_PRODUCTION_EVIDENCE_TOTAL_BYTES:
                raise ReleaseEvidenceError("production evidence intake exceeds its total size limit")
            artifact_names.add(name)
            seen_destinations.add(destination_text)
            seen_sources.add(source)
            artifact_documents.append(
                {"name": name, "path": destination_text, "size": size, "sha256": digest, "reference": reference}
            )

        approval_roles: set[str] = set()
        for item in approvals:
            if not isinstance(item, dict) or set(item) != PRODUCTION_INTAKE_APPROVAL_FIELDS:
                raise ReleaseEvidenceError("production evidence intake contains an invalid approval")
            role = item.get("role")
            reference = item.get("reference")
            organization = item.get("organization")
            approved_at = item.get("approved_at")
            if (
                not isinstance(role, str)
                or CATEGORY_PATTERN.fullmatch(role) is None
                or role in approval_roles
                or not _valid_production_reference(reference)
                or not _valid_production_reference(organization)
            ):
                raise ReleaseEvidenceError("production evidence intake contains an invalid approval identity")
            approval_time = _parse_timestamp(approved_at, f"production intake {role} approved_at")
            if approval_time < tested_at - timedelta(minutes=5):
                raise ReleaseEvidenceError(f"production intake {role} approval predates the tested evidence")
            relative = _production_intake_destination(item.get("destination"), category=category, approval=True)
            destination_text = relative.as_posix()
            if destination_text in seen_destinations:
                raise ReleaseEvidenceError("production evidence intake contains a duplicate destination")
            source = _external_evidence_source(item.get("source_path"), repo=repo, request=request)
            if source in seen_sources:
                raise ReleaseEvidenceError("production evidence intake cannot reuse one source file")
            size, digest = _copy_external_evidence(source, staging.joinpath(*relative.parts))
            total_bytes += size
            if total_bytes > MAX_PRODUCTION_EVIDENCE_TOTAL_BYTES:
                raise ReleaseEvidenceError("production evidence intake exceeds its total size limit")
            approval_roles.add(role)
            seen_destinations.add(destination_text)
            seen_sources.add(source)
            approval_documents.append(
                {
                    "role": role,
                    "reference": reference,
                    "organization": organization,
                    "approved_at": approved_at,
                    "artifact_path": destination_text,
                    "artifact_size": size,
                    "artifact_sha256": digest,
                }
            )
        if not contract.approval_roles <= approval_roles:
            raise ReleaseEvidenceError("production evidence intake is missing required approval roles")

        report = {
            "schema": PRODUCTION_GATE_SCHEMA,
            "schema_version": 2,
            "category": category,
            "status": "passed",
            "environment_kind": document.get("environment_kind"),
            "environment_id": document.get("environment_id"),
            "tested_at": document.get("tested_at"),
            "subject": _subject_document(subject_before, security.targets),
            "checks": {name: True for name in sorted(contract.checks)},
            "executor": executor,
            "artifacts": artifact_documents,
            "approvals": approval_documents,
        }
        report_path = staging / contract.report_name
        _atomic_write(report_path, _canonical_json(report))
        finished_at = datetime.now(UTC)
        command = ["release-evidence", "register-production", category]
        attachment_documents = [
            {"path": path.relative_to(staging).as_posix(), "size": path.stat().st_size, "sha256": _sha256_file(path)}
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        ]
        statement: dict[str, Any] = {
            "schema": STATEMENT_SCHEMA,
            "schema_version": 1,
            "generated_at": finished_at.isoformat(),
            "category": category,
            "status": "passed",
            "subject": _subject_document(subject_before, security.targets),
            "security_manifest_sha256": security.manifest_sha256,
            "execution": {
                "argv": command,
                "argv_sha256": _sha256_bytes("\0".join(command).encode()),
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": round(time.monotonic() - started_clock, 6),
                "exit_code": 0,
            },
            "log_attachment": None,
            "missing_attachments": [],
            "attachments": attachment_documents,
        }
        statement_path = staging / "gate-statement.json"
        _validate_specialized_evidence(statement_path, category, statement, policy=policy)
        if repository_subject(repo) != subject_before:
            raise ReleaseEvidenceError("repository subject changed while registering production evidence")
        if validate_security_evidence(security_directory, subject_before) != security:
            raise ReleaseEvidenceError("security evidence changed while registering production evidence")
        _atomic_write(statement_path, _canonical_json(statement))
        for directory in sorted((path for path in staging.rglob("*") if path.is_dir()), reverse=True):
            _fsync_directory(directory)
        _fsync_directory(staging)
        _rename_noreplace(staging, resolved_output)
        _fsync_directory(output_parent)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        "schema_version": 1,
        "status": "registered",
        "category": category,
        "statement": str(resolved_output / "gate-statement.json"),
        "attachment_count": len(artifact_documents) + len(approval_documents) + 1,
        "total_attachment_bytes": total_bytes + (resolved_output / contract.report_name).stat().st_size,
        "production_claim": False,
    }
