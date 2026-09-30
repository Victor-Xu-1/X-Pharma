from __future__ import annotations

import argparse
import json
import os
import re
import stat
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

HEARTBEAT_SCHEMA = "pharma.runtime-heartbeat.v1"
DEFAULT_HEARTBEAT_DIRECTORY = Path(
    "/tmp/pharma-runtime-heartbeats"  # noqa: S108 - dedicated non-secret heartbeat data on container tmpfs.
)
HEARTBEAT_DIRECTORY_ENV = "PHARMA_RUNTIME_HEARTBEAT_DIR"
HEARTBEAT_SERVICE_ENV = "PHARMA_RUNTIME_HEARTBEAT_SERVICE"
SERVICE_PATTERN = re.compile(r"[a-z][a-z0-9-]{0,62}")
MAX_HEARTBEAT_BYTES = 4096
MAX_FUTURE_SKEW_SECONDS = 5.0


class RuntimeHeartbeatError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeHeartbeatStatus:
    service: str
    pid: int
    observed_at_epoch_ms: int


def _validate_service_name(service: str) -> str:
    service = service.strip()
    if SERVICE_PATTERN.fullmatch(service) is None:
        raise RuntimeHeartbeatError("runtime heartbeat service name is invalid")
    return service


def _heartbeat_directory(directory: Path | None = None) -> Path:
    configured = directory or Path(os.environ.get(HEARTBEAT_DIRECTORY_ENV, DEFAULT_HEARTBEAT_DIRECTORY))
    if not configured.is_absolute():
        raise RuntimeHeartbeatError("runtime heartbeat directory must be absolute")
    return configured


class RuntimeHeartbeat:
    def __init__(
        self,
        service: str,
        *,
        directory: Path | None = None,
        pid: int | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.service = _validate_service_name(os.environ.get(HEARTBEAT_SERVICE_ENV, service))
        self.directory = _heartbeat_directory(directory)
        self.path = self.directory / f"{self.service}.json"
        self.pid = os.getpid() if pid is None else pid
        self._clock = clock
        if self.pid <= 0:
            raise RuntimeHeartbeatError("runtime heartbeat PID must be positive")

    def beat(self) -> None:
        if self.directory.is_symlink():
            raise RuntimeHeartbeatError("runtime heartbeat directory cannot be a symbolic link")
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.directory.is_symlink() or not self.directory.is_dir():
            raise RuntimeHeartbeatError("runtime heartbeat directory is invalid")
        directory_metadata = self.directory.stat()
        if directory_metadata.st_uid != os.geteuid() or directory_metadata.st_mode & 0o077:
            raise RuntimeHeartbeatError("runtime heartbeat directory must be private and process-owned")
        payload = json.dumps(
            {
                "observed_at_epoch_ms": int(self._clock() * 1000),
                "pid": self.pid,
                "schema": HEARTBEAT_SCHEMA,
                "service": self.service,
                "status": "ready",
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{self.service}.", dir=self.directory)
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            directory_descriptor = os.open(
                self.directory,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            )
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)
            raise

    def close(self) -> None:
        self.path.unlink(missing_ok=True)

    def __enter__(self) -> RuntimeHeartbeat:
        self.beat()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()


def verify_runtime_heartbeat(
    service: str,
    *,
    directory: Path | None = None,
    max_age_seconds: float = 90,
    clock: Callable[[], float] = time.time,
    process_probe: Callable[[int, int], None] = os.kill,
) -> RuntimeHeartbeatStatus:
    validated_service = _validate_service_name(service)
    root = _heartbeat_directory(directory)
    if not 0 < max_age_seconds <= 3600:
        raise RuntimeHeartbeatError("runtime heartbeat maximum age must be between 0 and 3600 seconds")
    if root.is_symlink() or not root.is_dir():
        raise RuntimeHeartbeatError("runtime heartbeat directory is unavailable")
    root_metadata = root.stat()
    if root_metadata.st_uid != os.geteuid() or root_metadata.st_mode & 0o077:
        raise RuntimeHeartbeatError("runtime heartbeat directory is not private and process-owned")
    path = root / f"{validated_service}.json"
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RuntimeHeartbeatError("runtime heartbeat is unavailable") from exc
    if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= MAX_HEARTBEAT_BYTES:
        raise RuntimeHeartbeatError("runtime heartbeat is not a bounded regular file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        opened_metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened_metadata.st_mode)
            or not 0 < opened_metadata.st_size <= MAX_HEARTBEAT_BYTES
            or opened_metadata.st_uid != os.geteuid()
            or opened_metadata.st_mode & 0o077
        ):
            os.close(descriptor)
            raise RuntimeHeartbeatError("runtime heartbeat opened file is not private, bounded, and process-owned")
        with os.fdopen(descriptor, "rb") as handle:
            payload = handle.read(MAX_HEARTBEAT_BYTES + 1)
    except RuntimeHeartbeatError:
        raise
    except OSError as exc:
        raise RuntimeHeartbeatError("runtime heartbeat cannot be read safely") from exc
    if len(payload) > MAX_HEARTBEAT_BYTES:
        raise RuntimeHeartbeatError("runtime heartbeat exceeds the size limit")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeHeartbeatError("runtime heartbeat is not valid JSON") from exc
    if not isinstance(document, dict) or set(document) != {
        "observed_at_epoch_ms",
        "pid",
        "schema",
        "service",
        "status",
    }:
        raise RuntimeHeartbeatError("runtime heartbeat has an invalid contract")
    observed_at = document.get("observed_at_epoch_ms")
    pid = document.get("pid")
    if (
        document.get("schema") != HEARTBEAT_SCHEMA
        or document.get("service") != validated_service
        or document.get("status") != "ready"
        or not isinstance(observed_at, int)
        or isinstance(observed_at, bool)
        or observed_at <= 0
        or not isinstance(pid, int)
        or isinstance(pid, bool)
        or pid <= 0
    ):
        raise RuntimeHeartbeatError("runtime heartbeat has invalid values")
    age_seconds = clock() - observed_at / 1000
    if age_seconds < -MAX_FUTURE_SKEW_SECONDS or age_seconds > max_age_seconds:
        raise RuntimeHeartbeatError("runtime heartbeat is stale or from the future")
    try:
        process_probe(pid, 0)
    except (ProcessLookupError, PermissionError, OSError) as exc:
        raise RuntimeHeartbeatError("runtime heartbeat process is unavailable") from exc
    return RuntimeHeartbeatStatus(
        service=validated_service,
        pid=pid,
        observed_at_epoch_ms=observed_at,
    )


def run() -> None:
    parser = argparse.ArgumentParser(description="Verify a bounded runtime worker heartbeat")
    parser.add_argument("--service", required=True)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--max-age-seconds", type=float, default=90)
    arguments = parser.parse_args()
    try:
        verify_runtime_heartbeat(
            arguments.service,
            directory=arguments.directory,
            max_age_seconds=arguments.max_age_seconds,
        )
    except RuntimeHeartbeatError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    run()
