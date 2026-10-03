from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import stat
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, TypeGuard

from scripts.release.contracts.core import REFERENCE_PATTERN
from scripts.release.contracts.mcp import MCP_SENDER_CONSTRAINT_REPORT
from scripts.release.contracts.production import MAX_PRODUCTION_EVIDENCE_FILE_BYTES
from scripts.release.contracts.topology import PRODUCTION_TOPOLOGY_LIVE_REPORT, PRODUCTION_TOPOLOGY_REPORT
from scripts.release.records import ReleaseEvidenceError, RepositorySubject


def _rename_noreplace(source: Path, destination: Path) -> None:
    """Atomically publish a WSL evidence path without replacing an existing target."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
    except (AttributeError, OSError) as exc:
        raise ReleaseEvidenceError("Linux renameat2 is required for no-overwrite evidence publication") from exc
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise ReleaseEvidenceError(f"refusing to overwrite evidence: {destination}")
    raise ReleaseEvidenceError(f"cannot publish evidence at {destination}: {os.strerror(error_number)}")


def _canonical_json(document: object) -> bytes:
    return (json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ReleaseEvidenceError(f"cannot read evidence file: {path}") from exc
    return digest.hexdigest()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise ReleaseEvidenceError(f"refusing to overwrite evidence: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _rename_noreplace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReleaseEvidenceError(f"{label} must be a regular file: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseEvidenceError(f"invalid {label}: {path}") from exc
    if not isinstance(document, dict):
        raise ReleaseEvidenceError(f"{label} must contain a JSON object: {path}")
    return document


def _parse_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ReleaseEvidenceError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseEvidenceError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ReleaseEvidenceError(f"{label} must include a timezone")
    return parsed.astimezone(UTC)


def _subject_document(subject: RepositorySubject, targets: dict[str, str]) -> dict[str, object]:
    return {
        "git_commit": subject.commit,
        "source_file_count": subject.source_file_count,
        "source_tree_sha256": subject.source_tree_sha256,
        "targets": dict(sorted(targets.items())),
    }


def _expected_relative_attachment(path: Path, parent: Path) -> str:
    try:
        relative = path.resolve(strict=False).relative_to(parent.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ReleaseEvidenceError("capture attachments must be regular files below the statement directory") from exc
    relative_path = relative.as_posix()
    if not relative.parts or relative_path == "gate-statement.json" or ".." in relative.parts:
        raise ReleaseEvidenceError(f"unsafe capture attachment path: {relative_path}")
    return relative_path


def _relative_attachment(path: Path, parent: Path) -> str:
    relative_path = _expected_relative_attachment(path, parent)
    if path.is_symlink() or not path.is_file():
        raise ReleaseEvidenceError(f"capture attachment must be a regular file: {path}")
    return relative_path


def _production_intake_destination(
    value: object,
    *,
    category: str,
    approval: bool,
) -> PurePosixPath:
    if not isinstance(value, str) or not value or len(value) > 240 or "\\" in value or "\0" in value:
        raise ReleaseEvidenceError("production evidence destination path is invalid")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or "." in relative.parts
        or ".." in relative.parts
        or relative.as_posix() != value
        or value in {"gate-statement.json", "production-evidence-report.json"}
    ):
        raise ReleaseEvidenceError("production evidence destination path is unsafe")
    if approval:
        if len(relative.parts) < 2 or relative.parts[0] != "approvals":
            raise ReleaseEvidenceError("production approval destinations must be below approvals/")
    elif not (len(relative.parts) >= 2 and relative.parts[0] == "artifacts") and not (
        (category == "mcp_sender_constraint" and value == MCP_SENDER_CONSTRAINT_REPORT)
        or (
            category == "production_topology" and value in {PRODUCTION_TOPOLOGY_REPORT, PRODUCTION_TOPOLOGY_LIVE_REPORT}
        )
    ):
        raise ReleaseEvidenceError("production artifact destinations must be below artifacts/")
    return relative


def _external_evidence_source(value: object, *, repo: Path, request: Path) -> Path:
    if not isinstance(value, str) or not value or len(value) > 4096 or "\0" in value:
        raise ReleaseEvidenceError("production evidence source path is invalid")
    source = Path(value)
    if not source.is_absolute() or source.is_symlink():
        raise ReleaseEvidenceError("production evidence sources must be absolute regular files, not symbolic links")
    try:
        resolved = source.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError(f"production evidence source does not exist: {source}") from exc
    if not resolved.is_file() or resolved == request:
        raise ReleaseEvidenceError(f"production evidence source is not an independent regular file: {source}")
    if resolved == repo or repo in resolved.parents:
        raise ReleaseEvidenceError("production evidence sources must be outside the source repository")
    return resolved


def _copy_external_evidence(source: Path, destination: Path) -> tuple[int, str]:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    source_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    destination_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        source_descriptor = os.open(source, source_flags)
    except OSError as exc:
        raise ReleaseEvidenceError(f"cannot open production evidence source: {source}") from exc
    try:
        before = os.fstat(source_descriptor)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_PRODUCTION_EVIDENCE_FILE_BYTES:
            raise ReleaseEvidenceError(
                f"production evidence source must be non-empty and no larger than "
                f"{MAX_PRODUCTION_EVIDENCE_FILE_BYTES} bytes: {source}"
            )
        try:
            destination_descriptor = os.open(destination, destination_flags, 0o600)
        except OSError as exc:
            raise ReleaseEvidenceError(f"cannot create production evidence attachment: {destination}") from exc
        digest = hashlib.sha256()
        copied = 0
        try:
            while chunk := os.read(source_descriptor, 1024 * 1024):
                copied += len(chunk)
                if copied > MAX_PRODUCTION_EVIDENCE_FILE_BYTES:
                    raise ReleaseEvidenceError(f"production evidence source exceeded its size limit: {source}")
                digest.update(chunk)
                view = memoryview(chunk)
                while view:
                    written = os.write(destination_descriptor, view)
                    if written <= 0:
                        raise ReleaseEvidenceError(f"cannot write production evidence attachment: {destination}")
                    view = view[written:]
            os.fsync(destination_descriptor)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        finally:
            os.close(destination_descriptor)
        after = os.fstat(source_descriptor)
        identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if identity_before != identity_after or copied != before.st_size:
            destination.unlink(missing_ok=True)
            raise ReleaseEvidenceError(f"production evidence source changed while it was copied: {source}")
        return copied, digest.hexdigest()
    finally:
        os.close(source_descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _valid_production_reference(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and len(value) <= 200 and REFERENCE_PATTERN.fullmatch(value) is not None


def _copy_regular_tree(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_symlink():
            raise ReleaseEvidenceError(f"evidence tree contains a symbolic link: {relative}")
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        else:
            raise ReleaseEvidenceError(f"evidence tree contains a non-regular entry: {relative}")


def _payload_inventory(root: Path) -> list[dict[str, object]]:
    inventory: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ReleaseEvidenceError(f"release bundle contains a symbolic link: {path.relative_to(root)}")
        if path.is_file():
            inventory.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )
    return inventory


def _safe_checksum_path(value: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ReleaseEvidenceError(f"unsafe checksum path: {value}")
    return relative


def _external_directory_output(repo: Path, output: Path, label: str) -> tuple[Path, Path]:
    try:
        resolved_repo = repo.resolve(strict=True)
        output_parent = output.parent.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError(f"{label} repository or output parent does not exist") from exc
    resolved_output = output_parent / output.name
    if (
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", output.name) is None
        or resolved_output.exists()
        or resolved_output.is_symlink()
    ):
        raise ReleaseEvidenceError(f"refusing to overwrite {label}: {output}")
    if output_parent == resolved_repo or resolved_repo in output_parent.parents:
        raise ReleaseEvidenceError(f"{label} output must be outside the source repository")
    return resolved_repo, resolved_output
