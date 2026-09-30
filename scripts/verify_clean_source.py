from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from scripts.release_evidence import ReleaseEvidenceError, repository_subject
    from scripts.source_tree_manifest import build_source_tree_manifest
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from release_evidence import ReleaseEvidenceError, repository_subject  # type: ignore[no-redef,import-not-found]
    from source_tree_manifest import build_source_tree_manifest  # type: ignore[no-redef,import-not-found]

PACKAGE_MANAGER_PATTERN = re.compile(r"pnpm@[0-9]+(?:\.[0-9]+){2}")
POSTGRES_IMAGE = "pharma-postgres-rdkit:18.4-2026.03.3"
FORBIDDEN_GENERATED_PARTS = frozenset(
    {
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "htmlcov",
        "node_modules",
        "playwright-report",
        "test-results",
    }
)
FORBIDDEN_SOURCE_PREFIXES = (PurePosixPath("manifests/acceptance"),)
PERSONAL_PLATFORM_PATH_PATTERNS = (
    re.compile(rb"/home/[A-Za-z0-9._-]+/pharma-intelligence-(?:platform|runtime)(?:[/\s\"']|$)"),
    re.compile(
        rb"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s]+[\\/]+[^\r\n]*pharma-intelligence-(?:platform|runtime)",
        re.IGNORECASE,
    ),
)
MAX_HYGIENE_SCAN_BYTES = 4 * 1024 * 1024
REQUIRED_SOURCE_FILES = (
    ".env.example",
    "GOAL.md",
    "Makefile",
    "README.md",
    "alembic.ini",
    "apps/web/package.json",
    "apps/web/pnpm-lock.yaml",
    "compose.yaml",
    "deploy/api.Dockerfile",
    "deploy/kubernetes/base/kustomization.yaml",
    "pyproject.toml",
    "uv.lock",
)


class CleanSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Tooling:
    corepack: str
    docker: str
    make: str
    uv: str


@dataclass(frozen=True)
class CommandSpec:
    label: str
    command: tuple[str, ...]
    timeout_seconds: int


def _resolve_tooling() -> Tooling:
    resolved: dict[str, str] = {}
    for executable in ("corepack", "docker", "make", "uv"):
        path = shutil.which(executable)
        if path is None:
            raise CleanSourceError(f"required executable is unavailable: {executable}")
        resolved[executable] = path
    return Tooling(**resolved)


def _package_manager(source: Path) -> str:
    try:
        document = json.loads((source / "apps/web/package.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CleanSourceError("cannot read the frontend package-manager contract") from exc
    value = document.get("packageManager") if isinstance(document, dict) else None
    if not isinstance(value, str) or not PACKAGE_MANAGER_PATTERN.fullmatch(value):
        raise CleanSourceError("frontend packageManager must pin an exact pnpm version")
    return value


def _command_plan(
    tooling: Tooling,
    package_manager: str,
    image_tag: str,
    *,
    migration_env_file: str,
    migration_port: int,
) -> tuple[CommandSpec, ...]:
    return (
        CommandSpec("locked Python installation", (tooling.uv, "sync", "--locked", "--dev"), 300),
        CommandSpec(
            "locked frontend installation",
            (tooling.corepack, package_manager, "--dir", "apps/web", "install", "--frozen-lockfile"),
            300,
        ),
        CommandSpec("quality, tests, build and manifest rendering", (tooling.make, "check"), 900),
        CommandSpec(
            "PostgreSQL migration upgrade and rollback",
            (
                tooling.uv,
                "run",
                "python",
                "scripts/verify_postgres_migration_roundtrip.py",
                "--env-file",
                migration_env_file,
                "--port",
                str(migration_port),
            ),
            600,
        ),
        CommandSpec(
            "production application image build",
            (
                tooling.docker,
                "build",
                "--pull=false",
                "-f",
                "deploy/api.Dockerfile",
                "-t",
                image_tag,
                ".",
            ),
            1200,
        ),
        CommandSpec(
            "non-root runtime image smoke",
            (
                tooling.docker,
                "run",
                "--rm",
                "--read-only",
                "--tmpfs",
                "/tmp",  # noqa: S108 - this is an isolated container tmpfs, not a host temporary path.
                "--network",
                "none",
                image_tag,
                "python",
                "-c",
                (
                    "import os; from pharma_intel.api import app; "
                    "assert os.getuid() == 10001; "
                    "assert any(route.path == '/health/live' for route in app.routes)"
                ),
            ),
            180,
        ),
    )


def _sanitized_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in (
        "DATABASE_URL",
        "NODE_OPTIONS",
        "NODE_PATH",
        "PYTHONHOME",
        "PYTHONPATH",
        "TEST_MCP_ACCESS_TOKEN",
        "UV_PROJECT_ENVIRONMENT",
        "VIRTUAL_ENV",
    ):
        environment.pop(name, None)
    environment["CI"] = "true"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _run_checked(spec: CommandSpec, source: Path, environment: dict[str, str]) -> dict[str, int | str]:
    print(f"[clean-source] {spec.label}", flush=True)
    started = time.monotonic()
    try:
        completed = subprocess.run(  # noqa: S603 - every command is assembled from resolved tools and constants.
            spec.command,
            cwd=source,
            env=environment,
            check=False,
            timeout=spec.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise CleanSourceError(f"{spec.label} exceeded {spec.timeout_seconds} seconds") from exc
    except OSError as exc:
        raise CleanSourceError(f"cannot execute {spec.label}") from exc
    duration_ms = round((time.monotonic() - started) * 1000)
    if completed.returncode != 0:
        raise CleanSourceError(f"{spec.label} failed with exit code {completed.returncode}")
    return {"label": spec.label, "duration_ms": duration_ms, "exit_code": 0}


def _extract_committed_source(repo: Path, destination: Path) -> None:
    archive = destination.parent / "source.tar"
    git = shutil.which("git")
    if git is None:
        raise CleanSourceError("required executable is unavailable: git")
    try:
        subprocess.run(  # noqa: S603 - Git executable and immutable archive arguments are controlled.
            [git, "-C", str(repo), "archive", "--format=tar", "--output", str(archive), "HEAD"],
            check=True,
            capture_output=True,
            timeout=120,
        )
        with tarfile.open(archive, mode="r:") as handle:
            for member in handle.getmembers():
                relative = PurePosixPath(member.name)
                if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                    raise CleanSourceError("Git archive contains an unsafe path")
                if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise CleanSourceError("Git archive contains a non-regular source entry")
            handle.extractall(destination, filter="data")
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, tarfile.TarError) as exc:
        raise CleanSourceError("cannot extract the committed source archive") from exc
    finally:
        archive.unlink(missing_ok=True)


def _prepare_source(source: Path) -> None:
    missing = [relative for relative in REQUIRED_SOURCE_FILES if not (source / relative).is_file()]
    if missing:
        raise CleanSourceError(f"committed source is missing required files: {', '.join(missing)}")
    shutil.copyfile(source / ".env.example", source / ".env")
    (source / ".env").chmod(0o600)
    (source / "data/sources/empty").mkdir(parents=True)


def _validate_source_hygiene(source: Path) -> None:
    for candidate in source.rglob("*"):
        relative = PurePosixPath(candidate.relative_to(source).as_posix())
        if any(relative == prefix or prefix in relative.parents for prefix in FORBIDDEN_SOURCE_PREFIXES):
            raise CleanSourceError(f"committed source contains historical runtime evidence: {relative}")
        if any(part in FORBIDDEN_GENERATED_PARTS for part in relative.parts):
            raise CleanSourceError(f"committed source contains generated local state: {relative}")
        if not candidate.is_file() or candidate.stat().st_size > MAX_HYGIENE_SCAN_BYTES:
            continue
        try:
            payload = candidate.read_bytes()
        except OSError as exc:
            raise CleanSourceError(f"cannot inspect committed source file: {relative}") from exc
        if b"\x00" in payload:
            continue
        if any(pattern.search(payload) for pattern in PERSONAL_PLATFORM_PATH_PATTERNS):
            raise CleanSourceError(f"committed source contains a personal platform path: {relative}")


@contextmanager
def _temporary_postgres(docker: str, source: Path) -> Iterator[tuple[int, str]]:
    container_name = f"pharma-clean-postgres-{os.getpid()}-{secrets.token_hex(4)}"
    password = secrets.token_urlsafe(32)
    env_file = source / ".clean-source-migration.env"
    env_file.write_text(
        f"POSTGRES_DB=postgres\nPOSTGRES_USER=postgres\nPOSTGRES_PASSWORD={password}\n",
        encoding="utf-8",
    )
    env_file.chmod(0o600)
    started = False
    try:
        image = subprocess.run(  # noqa: S603 - Docker executable and pinned image reference are controlled.
            [docker, "image", "inspect", POSTGRES_IMAGE],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
        if image.returncode != 0:
            raise CleanSourceError(f"required PostgreSQL/RDKit image is unavailable: {POSTGRES_IMAGE}")
        created = subprocess.run(  # noqa: S603 - arguments contain no secret; the private env file supplies it.
            [
                docker,
                "run",
                "--detach",
                "--name",
                container_name,
                "--env-file",
                str(env_file),
                "--publish",
                "127.0.0.1::5432",
                "--health-cmd",
                "pg_isready -U postgres -d postgres",
                "--health-interval",
                "1s",
                "--health-timeout",
                "3s",
                "--health-retries",
                "90",
                "--security-opt",
                "no-new-privileges:true",
                POSTGRES_IMAGE,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if created.returncode != 0:
            raise CleanSourceError("cannot start isolated clean-source PostgreSQL/RDKit")
        started = True
        port_result = subprocess.run(  # noqa: S603 - Docker executable and generated container name are controlled.
            [docker, "port", container_name, "5432/tcp"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        match = re.fullmatch(r"127\.0\.0\.1:([0-9]{1,5})\s*", port_result.stdout)
        if match is None or not 1 <= int(match.group(1)) <= 65535:
            raise CleanSourceError("isolated PostgreSQL/RDKit has an invalid loopback port")
        port = int(match.group(1))
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            health = subprocess.run(  # noqa: S603 - Docker executable and generated container name are controlled.
                [docker, "inspect", "--format", "{{.State.Health.Status}}", container_name],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if health.returncode == 0 and health.stdout.strip() == "healthy":
                break
            time.sleep(1)
        else:
            raise CleanSourceError("isolated clean-source PostgreSQL/RDKit did not become healthy")
        yield port, env_file.name
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise CleanSourceError("isolated clean-source PostgreSQL/RDKit failed") from exc
    finally:
        env_file.unlink(missing_ok=True)
        if started:
            try:
                removed = subprocess.run(  # noqa: S603 - only the generated temporary container is removed.
                    [docker, "rm", "--force", container_name],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=120,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise CleanSourceError("cannot remove isolated clean-source PostgreSQL/RDKit") from exc
            if removed.returncode != 0:
                raise CleanSourceError("cannot remove isolated clean-source PostgreSQL/RDKit")


def _inspect_image(docker: str, image_tag: str) -> tuple[str, str]:
    try:
        completed = subprocess.run(  # noqa: S603 - Docker executable and generated image tag are controlled.
            [docker, "image", "inspect", image_tag],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        documents: Any = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise CleanSourceError("cannot inspect the clean-source application image") from exc
    if not isinstance(documents, list) or len(documents) != 1 or not isinstance(documents[0], dict):
        raise CleanSourceError("Docker returned an invalid image inspection document")
    image = documents[0]
    config = image.get("Config")
    image_id = image.get("Id")
    user = config.get("User") if isinstance(config, dict) else None
    if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise CleanSourceError("clean-source image has an invalid immutable digest")
    if user != "app":
        raise CleanSourceError("clean-source runtime image must use the non-root app user")
    return image_id, user


def _remove_image(docker: str, image_tag: str) -> None:
    subprocess.run(  # noqa: S603 - only the unique temporary image tag is removed.
        [docker, "image", "rm", image_tag],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=120,
    )


def _write_report(path: Path, report: dict[str, object]) -> None:
    resolved = path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if resolved.exists() or resolved.is_symlink():
        raise CleanSourceError(f"refusing to overwrite clean-source evidence: {resolved}")
    temporary = resolved.with_name(f".{resolved.name}.{os.getpid()}.tmp")
    payload = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, resolved)
    finally:
        temporary.unlink(missing_ok=True)


def execute(repo: Path, output: Path | None) -> dict[str, object]:
    resolved_repo = repo.resolve(strict=True)
    subject = repository_subject(resolved_repo)
    tooling = _resolve_tooling()
    image_tag = f"pharma-clean-source:{subject.commit[:12]}-{os.getpid()}"
    command_results: list[dict[str, int | str]] = []
    image_id = ""
    image_user = ""
    image_built = False

    try:
        with tempfile.TemporaryDirectory(prefix="pharma-clean-source-") as temporary:
            source = Path(temporary) / "source"
            source.mkdir(mode=0o700)
            _extract_committed_source(resolved_repo, source)
            extracted = build_source_tree_manifest(source)
            if extracted.file_count != subject.source_file_count or extracted.sha256 != subject.source_tree_sha256:
                raise CleanSourceError("clean-source archive does not match the release source-tree manifest")
            _validate_source_hygiene(source)
            _prepare_source(source)
            package_manager = _package_manager(source)
            environment = _sanitized_environment()
            with _temporary_postgres(tooling.docker, source) as (migration_port, migration_env_file):
                for spec in _command_plan(
                    tooling,
                    package_manager,
                    image_tag,
                    migration_env_file=migration_env_file,
                    migration_port=migration_port,
                ):
                    command_results.append(_run_checked(spec, source, environment))
                    if spec.label == "production application image build":
                        image_built = True
                image_id, image_user = _inspect_image(tooling.docker, image_tag)
    finally:
        if image_built:
            _remove_image(tooling.docker, image_tag)

    report: dict[str, object] = {
        "schema": "pharma.clean-source-reproducibility.v1",
        "schema_version": 1,
        "status": "passed",
        "generated_at": datetime.now(UTC).isoformat(),
        "subject": {
            "git_commit": subject.commit,
            "source_file_count": subject.source_file_count,
            "source_tree_sha256": subject.source_tree_sha256,
        },
        "checks": {
            "committed_source_only": True,
            "clean_source_manifest_matches": True,
            "portable_source_paths": True,
            "historical_runtime_evidence_excluded": True,
            "locked_installation": True,
            "backend_and_frontend_tests": True,
            "frontend_production_build": True,
            "compose_and_kubernetes_render": True,
            "migration_upgrade_and_rollback": True,
            "migration_database_isolated": True,
            "runtime_image_build": True,
            "runtime_image_non_root": image_user == "app",
            "runtime_image_smoke": True,
            "temporary_source_removed": True,
            "temporary_database_removed": True,
            "temporary_image_tag_removed": True,
        },
        "application_image_digest": image_id,
        "application_image_user": image_user,
        "commands": command_results,
    }
    if output is not None:
        _write_report(output, report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify locked install, test, build and migration rollback from committed source only"
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    return parser


def main(arguments: list[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    try:
        report = execute(args.repo, args.output)
    except (CleanSourceError, ReleaseEvidenceError, OSError) as exc:
        print(f"clean-source verification failed: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "git_commit": report["subject"]["git_commit"],  # type: ignore[index]
                "application_image_digest": report["application_image_digest"],
                "commands": len(report["commands"]),  # type: ignore[arg-type]
                "output": str(args.output) if args.output is not None else None,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
