from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from scripts.release.contracts.core import CATEGORY_PATTERN, ENVIRONMENT_ID_PATTERN, SHA256_PATTERN
from scripts.release.contracts.production import (
    PRODUCTION_APPROVAL_FIELDS,
    PRODUCTION_ARTIFACT_FIELDS,
    PRODUCTION_GATE_FIELDS,
    PRODUCTION_GATE_SCHEMA,
)
from scripts.release.io import _load_json_object, _parse_timestamp, _sha256_file, _valid_production_reference
from scripts.release.records import ProductionEvidenceContract, ReleaseEvidenceError


def _validate_production_gate_evidence(
    statement_path: Path,
    category: str,
    statement: dict[str, Any],
    *,
    contract: ProductionEvidenceContract,
    maximum_age_hours: int,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError(f"{category} production evidence attachments are invalid")
    attachment_inventory: dict[str, tuple[int, str]] = {}
    for raw_attachment in raw_attachments:
        if not isinstance(raw_attachment, dict):
            raise ReleaseEvidenceError(f"{category} production evidence contains invalid attachment metadata")
        relative_text = raw_attachment.get("path")
        relative = PurePosixPath(relative_text) if isinstance(relative_text, str) else PurePosixPath("/")
        size = raw_attachment.get("size")
        digest = raw_attachment.get("sha256")
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 1
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
            or relative_text in attachment_inventory
        ):
            raise ReleaseEvidenceError(f"{category} production evidence contains invalid attachment metadata")
        attachment_path = statement_path.parent.joinpath(*relative.parts)
        if (
            attachment_path.is_symlink()
            or not attachment_path.is_file()
            or attachment_path.stat().st_size != size
            or _sha256_file(attachment_path) != digest
        ):
            raise ReleaseEvidenceError(f"{category} production evidence attachment is missing or modified")
        attachment_inventory[str(relative_text)] = (size, digest)
    report_metadata = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == contract.report_name
    ]
    if len(report_metadata) != 1:
        raise ReleaseEvidenceError(
            f"{category} production evidence requires exactly one {contract.report_name} attachment"
        )
    report = _load_json_object(statement_path.parent / contract.report_name, f"{category} production report")
    environment_kind = report.get("environment_kind")
    environment_id = report.get("environment_id")
    if (
        set(report) != PRODUCTION_GATE_FIELDS
        or report.get("schema") != PRODUCTION_GATE_SCHEMA
        or report.get("schema_version") != 2
        or report.get("category") != category
        or report.get("status") != "passed"
        or environment_kind not in {"preproduction", "production"}
        or not isinstance(environment_id, str)
        or ENVIRONMENT_ID_PATTERN.fullmatch(environment_id) is None
    ):
        raise ReleaseEvidenceError(f"{category} report is not approved production-environment evidence")
    environment_tokens = set(re.split(r"[^a-z0-9]+", environment_id.casefold()))
    if environment_tokens.intersection({"dev", "development", "local", "test", "testing"}):
        raise ReleaseEvidenceError(f"{category} report identifies a local or development environment")
    if report.get("subject") != statement.get("subject"):
        raise ReleaseEvidenceError(f"{category} report is not bound to the release subject")
    statement_time = _parse_timestamp(statement.get("generated_at"), f"{category} statement generated_at")
    tested_at = _parse_timestamp(report.get("tested_at"), f"{category} tested_at")
    if tested_at > statement_time + timedelta(minutes=5) or statement_time - tested_at > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError(f"{category} report is outside the allowed evidence window")
    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or set(checks) != contract.checks
        or not all(value is True for value in checks.values())
    ):
        raise ReleaseEvidenceError(f"{category} report did not pass every contracted check")
    executor = report.get("executor")
    if (
        not isinstance(executor, dict)
        or set(executor) != {"organization", "team", "independent"}
        or not _valid_production_reference(executor.get("organization"))
        or not _valid_production_reference(executor.get("team"))
        or not isinstance(executor.get("independent"), bool)
        or (contract.require_independent_executor and executor.get("independent") is not True)
    ):
        raise ReleaseEvidenceError(f"{category} report has an invalid or non-independent executor")
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list) or not contract.minimum_artifacts <= len(artifacts) <= 100:
        raise ReleaseEvidenceError(f"{category} report has insufficient bounded artifacts")
    artifact_names: set[str] = set()
    referenced_attachment_paths: set[str] = {contract.report_name}
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != PRODUCTION_ARTIFACT_FIELDS:
            raise ReleaseEvidenceError(f"{category} report contains an invalid artifact")
        name = artifact.get("name")
        path = artifact.get("path")
        size = artifact.get("size")
        digest = artifact.get("sha256")
        reference = artifact.get("reference")
        if (
            not _valid_production_reference(name)
            or name in artifact_names
            or not isinstance(path, str)
            or path == contract.report_name
            or path in referenced_attachment_paths
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 1
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
            or not _valid_production_reference(reference)
            or attachment_inventory.get(path) != (size, digest)
        ):
            raise ReleaseEvidenceError(f"{category} report contains an invalid, unbound or duplicate artifact")
        artifact_names.add(name)
        referenced_attachment_paths.add(path)
    approvals = report.get("approvals")
    if not isinstance(approvals, list) or not contract.approval_roles <= {
        item.get("role") for item in approvals if isinstance(item, dict) and isinstance(item.get("role"), str)
    }:
        raise ReleaseEvidenceError(f"{category} report is missing required approval roles")
    approval_roles: set[str] = set()
    for approval in approvals:
        if not isinstance(approval, dict) or set(approval) != PRODUCTION_APPROVAL_FIELDS:
            raise ReleaseEvidenceError(f"{category} report contains an invalid approval")
        role = approval.get("role")
        reference = approval.get("reference")
        organization = approval.get("organization")
        artifact_path = approval.get("artifact_path")
        artifact_size = approval.get("artifact_size")
        artifact_sha256 = approval.get("artifact_sha256")
        if (
            not isinstance(role, str)
            or CATEGORY_PATTERN.fullmatch(role) is None
            or role in approval_roles
            or not _valid_production_reference(reference)
            or not _valid_production_reference(organization)
            or not isinstance(artifact_path, str)
            or artifact_path == contract.report_name
            or artifact_path in referenced_attachment_paths
            or not isinstance(artifact_size, int)
            or isinstance(artifact_size, bool)
            or artifact_size < 1
            or not isinstance(artifact_sha256, str)
            or SHA256_PATTERN.fullmatch(artifact_sha256) is None
            or attachment_inventory.get(artifact_path) != (artifact_size, artifact_sha256)
        ):
            raise ReleaseEvidenceError(f"{category} report contains an invalid, unbound or duplicate approval")
        approved_at = _parse_timestamp(approval.get("approved_at"), f"{category} {role} approved_at")
        if approved_at < tested_at - timedelta(minutes=5):
            raise ReleaseEvidenceError(f"{category} {role} approval predates the tested evidence")
        if approved_at > statement_time + timedelta(minutes=5):
            raise ReleaseEvidenceError(f"{category} report contains a future approval")
        approval_roles.add(role)
        referenced_attachment_paths.add(artifact_path)
    if referenced_attachment_paths != set(attachment_inventory):
        raise ReleaseEvidenceError(f"{category} production evidence contains unreferenced attachments")
