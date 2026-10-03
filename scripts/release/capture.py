from __future__ import annotations

import os
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from scripts.release.contracts.core import MAX_CAPTURE_LOG_BYTES, STATEMENT_SCHEMA
from scripts.release.io import (
    _atomic_write,
    _canonical_json,
    _expected_relative_attachment,
    _relative_attachment,
    _sha256_bytes,
    _sha256_file,
    _subject_document,
)
from scripts.release.policy import load_policy
from scripts.release.records import ReleaseEvidenceError
from scripts.release.repository import repository_subject
from scripts.release.security import validate_security_evidence
from scripts.release.validation import _validate_specialized_evidence


def _prepare_log_attachment(path: Path, statement_parent: Path, output: Path) -> Path:
    statement_parent.mkdir(parents=True, exist_ok=True)
    parent = statement_parent.resolve(strict=True)
    candidate = path.resolve(strict=False)
    try:
        relative = candidate.relative_to(parent)
    except ValueError as exc:
        raise ReleaseEvidenceError("capture log must be below the statement directory") from exc
    if not relative.parts or ".." in relative.parts or candidate == output.resolve(strict=False):
        raise ReleaseEvidenceError("capture log path is unsafe")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate = candidate.resolve(strict=False)
    try:
        candidate.relative_to(parent)
    except ValueError as exc:
        raise ReleaseEvidenceError("capture log parent escaped the statement directory") from exc
    if candidate.exists() or candidate.is_symlink():
        raise ReleaseEvidenceError(f"refusing to overwrite capture log: {candidate}")
    return candidate


def _open_capture_log(path: Path) -> BinaryIO:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    return os.fdopen(descriptor, "wb")


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def _run_gate_command(command: list[str], repo: Path, log_handle: BinaryIO | None) -> int:
    if log_handle is None:
        completed = subprocess.run(  # noqa: S603 - operator argv is executed without a shell.
            command, cwd=repo, check=False
        )
        return completed.returncode

    process = subprocess.Popen(  # noqa: S603 - operator argv is executed without a shell.
        command,
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    assert process.stdout is not None
    written = 0
    try:
        while chunk := process.stdout.read(64 * 1024):
            written += len(chunk)
            if written > MAX_CAPTURE_LOG_BYTES:
                _kill_process_group(process)
                raise ReleaseEvidenceError(f"capture log exceeds the {MAX_CAPTURE_LOG_BYTES}-byte safety limit")
            log_handle.write(chunk)
        return process.wait()
    except BaseException:
        _kill_process_group(process)
        raise
    finally:
        process.stdout.close()


def capture_gate(
    *,
    repo: Path,
    policy_path: Path,
    category: str,
    security_directory: Path,
    output: Path,
    command: list[str],
    attachments: list[Path],
    log_attachment: Path | None = None,
) -> tuple[dict[str, Any], int]:
    policy = load_policy(policy_path)
    if category not in policy.categories:
        raise ReleaseEvidenceError(f"unknown release evidence category: {category}")
    if not command:
        raise ReleaseEvidenceError("capture requires a command after --")
    if output.exists() or output.is_symlink():
        raise ReleaseEvidenceError(f"refusing to overwrite evidence: {output}")
    subject_before = repository_subject(repo)
    security = validate_security_evidence(security_directory, subject_before)
    output.parent.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(UTC)
    started_clock = time.monotonic()
    capture_log: Path | None = None
    log_handle: BinaryIO | None = None
    try:
        if log_attachment is not None:
            capture_log = _prepare_log_attachment(log_attachment, output.parent, output)
            log_handle = _open_capture_log(capture_log)
        exit_code = _run_gate_command(command, repo, log_handle)
    except OSError as exc:
        raise ReleaseEvidenceError(f"cannot execute release gate command: {command[0]}") from exc
    finally:
        if log_handle is not None:
            log_handle.flush()
            os.fsync(log_handle.fileno())
            log_handle.close()
    finished_at = datetime.now(UTC)
    subject_after = repository_subject(repo)
    if subject_after != subject_before:
        raise ReleaseEvidenceError("repository subject changed while the release gate was running")
    attachment_documents: list[dict[str, object]] = []
    attachment_paths: set[str] = set()
    for attachment in attachments:
        relative_path = _expected_relative_attachment(attachment, output.parent)
        if relative_path in attachment_paths:
            raise ReleaseEvidenceError(f"duplicate capture attachment: {relative_path}")
        attachment_paths.add(relative_path)
        if not attachment.exists() and not attachment.is_symlink() and exit_code != 0:
            continue
        _relative_attachment(attachment, output.parent)
        attachment_documents.append(
            {
                "path": relative_path,
                "size": attachment.stat().st_size,
                "sha256": _sha256_file(attachment),
            }
        )
    missing_attachments = sorted(
        _expected_relative_attachment(attachment, output.parent)
        for attachment in attachments
        if not attachment.exists() and not attachment.is_symlink()
    )
    if capture_log is not None:
        relative_path = _relative_attachment(capture_log, output.parent)
        if relative_path in attachment_paths:
            raise ReleaseEvidenceError(f"duplicate capture attachment: {relative_path}")
        attachment_documents.append(
            {
                "path": relative_path,
                "size": capture_log.stat().st_size,
                "sha256": _sha256_file(capture_log),
            }
        )
    statement: dict[str, Any] = {
        "schema": STATEMENT_SCHEMA,
        "schema_version": 1,
        "generated_at": finished_at.isoformat(),
        "category": category,
        "status": "passed" if exit_code == 0 else "failed",
        "subject": _subject_document(subject_before, security.targets),
        "security_manifest_sha256": security.manifest_sha256,
        "execution": {
            "argv": command,
            "argv_sha256": _sha256_bytes("\0".join(command).encode()),
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round(time.monotonic() - started_clock, 6),
            "exit_code": exit_code,
        },
        "log_attachment": _relative_attachment(capture_log, output.parent) if capture_log else None,
        "missing_attachments": missing_attachments,
        "attachments": sorted(attachment_documents, key=lambda item: str(item["path"])),
    }
    if exit_code == 0:
        _validate_specialized_evidence(output, category, statement, policy=policy)
    _atomic_write(output, _canonical_json(statement))
    return statement, exit_code
