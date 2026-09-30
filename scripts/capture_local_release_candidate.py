from __future__ import annotations

import argparse
import errno
import json
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

try:
    from scripts.release_evidence import (
        ReleaseEvidenceError,
        _atomic_write,
        _canonical_json,
        assemble_bundle,
        audit_release,
        capture_gate,
        load_policy,
        repository_subject,
    )
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from release_evidence import (  # type: ignore[no-redef,import-not-found]
        ReleaseEvidenceError,
        _atomic_write,
        _canonical_json,
        assemble_bundle,
        audit_release,
        capture_gate,
        load_policy,
        repository_subject,
    )


@dataclass(frozen=True)
class GateSpec:
    category: str
    command: tuple[str, ...]
    attachments: tuple[Path, ...] = ()
    requires_mcp_token: bool = False


def _relative_command_path(path: Path, repo: Path) -> str:
    resolved_repo = repo.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(resolved_repo).as_posix()
    except ValueError:
        logical_runtime = resolved_repo / "manifests" / "runtime"
        resolved_runtime = logical_runtime.resolve()
        try:
            runtime_relative = resolved_path.relative_to(resolved_runtime)
        except ValueError as exc:
            raise ReleaseEvidenceError("candidate evidence must remain below the configured runtime directory") from exc
        return (Path("manifests") / "runtime" / runtime_relative).as_posix()


def _read_token_file(path: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.EISDIR}:
            raise ReleaseEvidenceError("MCP acceptance token must be a regular file") from exc
        raise ReleaseEvidenceError("cannot read MCP acceptance token file") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ReleaseEvidenceError("MCP acceptance token must be a regular file")
        if metadata.st_uid != os.getuid():
            raise ReleaseEvidenceError("MCP acceptance token must be owned by the current WSL user")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ReleaseEvidenceError("MCP acceptance token permissions must be 0600 or stricter")
        if metadata.st_size < 32 or metadata.st_size > 8192:
            raise ReleaseEvidenceError("MCP acceptance token file has an invalid size")
        with os.fdopen(descriptor, encoding="utf-8") as handle:
            descriptor = -1
            raw = handle.read(8193)
    except (OSError, UnicodeError) as exc:
        raise ReleaseEvidenceError("cannot read MCP acceptance token file") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    token = raw.strip()
    if not token or any(character.isspace() for character in token):
        raise ReleaseEvidenceError("MCP acceptance token must contain one non-whitespace value")
    return token


def _assert_secret_absent(root: Path, secret: str) -> None:
    needle = secret.encode()
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            raise ReleaseEvidenceError("MCP evidence contains an unsafe non-regular artifact")
        trailing = b""
        with path.open("rb") as handle:
            while chunk := handle.read(64 * 1024):
                inspected = trailing + chunk
                if needle in inspected:
                    raise ReleaseEvidenceError("MCP evidence attempted to record the acceptance token")
                trailing = inspected[-(len(needle) - 1) :]


@contextmanager
def _mcp_environment(token: str | None) -> Iterator[None]:
    name = "TEST_MCP_ACCESS_TOKEN"
    previous = os.environ.get(name)
    try:
        if token is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = token
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def _gate_specs(
    repo: Path,
    candidate_root: Path,
    *,
    level: str,
    ingestion_source_id: str | None,
    include_kubernetes: bool,
    mcp_requests: int,
    mcp_concurrency: int,
    automatic_ingestion_timeout: int = 900,
    include_backup_restore: bool = False,
) -> list[GateSpec]:
    def report(category: str) -> Path:
        return candidate_root / category / "report.json"

    def relative(path: Path) -> str:
        return _relative_command_path(path, repo)

    specs = [
        GateSpec("quality", ("make", "check")),
        GateSpec(
            "source_reproducibility",
            (
                "uv",
                "run",
                "python",
                "scripts/verify_clean_source.py",
                "--output",
                relative(report("source_reproducibility")),
            ),
            (report("source_reproducibility"),),
        ),
        GateSpec(
            "database",
            ("./scripts/verify-local-database.sh", "--output", relative(report("database"))),
            (report("database"),),
        ),
        GateSpec(
            "browser",
            ("./scripts/run-browser-acceptance.sh", "--output", relative(report("browser"))),
            (report("browser"),),
        ),
        GateSpec(
            "entry_consistency",
            (
                "./scripts/verify-entry-consistency.sh",
                "--output",
                relative(report("entry_consistency")),
            ),
            (report("entry_consistency"),),
            True,
        ),
        GateSpec(
            "record_consistency",
            (
                "uv",
                "run",
                "--no-sync",
                "python",
                "scripts/record_consistency_probe.py",
                "--output",
                relative(report("record_consistency")),
            ),
            (report("record_consistency"),),
        ),
        GateSpec(
            "anti_extraction_baseline",
            (
                "uv",
                "run",
                "--no-sync",
                "python",
                "scripts/mcp_anti_extraction_probe.py",
                "--output",
                relative(report("anti_extraction_baseline")),
            ),
            (report("anti_extraction_baseline"),),
        ),
        GateSpec(
            "mcp_protocol",
            (
                "./scripts/verify-mcp-interoperability.sh",
                "--output",
                relative(report("mcp_protocol")),
            ),
            (report("mcp_protocol"),),
            True,
        ),
        GateSpec(
            "mcp_async_tasks",
            (
                "./scripts/verify-mcp-interoperability.sh",
                "--async-task-only",
                "--output",
                relative(report("mcp_async_tasks")),
            ),
            (report("mcp_async_tasks"),),
        ),
        GateSpec(
            "mcp_commercial",
            (
                "uv",
                "run",
                "pharma-mcp-load",
                "--requests",
                str(mcp_requests),
                "--concurrency",
                str(mcp_concurrency),
                "--max-p95-ms",
                "2000",
                "--output",
                relative(report("mcp_commercial")),
            ),
            (report("mcp_commercial"),),
            True,
        ),
        GateSpec(
            "performance_baseline",
            (
                "./scripts/verify-local-performance.sh",
                "--output",
                relative(report("performance_baseline")),
            ),
            (report("performance_baseline"),),
            True,
        ),
        GateSpec(
            "operations_contract",
            (
                "./scripts/verify-local-observability.sh",
                "--output",
                relative(report("operations_contract")),
            ),
            (report("operations_contract"),),
            True,
        ),
        GateSpec(
            "parser_sandbox",
            ("./scripts/verify-local-parser.sh", "--output", relative(report("parser_sandbox"))),
            (report("parser_sandbox"),),
        ),
        GateSpec(
            "ocr",
            (
                "python3",
                "-m",
                "scripts.verify_local_ocr",
                "--output",
                relative(report("ocr")),
            ),
            (report("ocr"),),
        ),
        GateSpec(
            "ingestion_readiness",
            (
                "uv",
                "run",
                "python",
                "scripts/capture_ingestion_readiness.py",
                "--output",
                relative(report("ingestion_readiness")),
            ),
            (report("ingestion_readiness"),),
        ),
        GateSpec(
            "runtime",
            ("./scripts/status.sh", "--output", relative(report("runtime"))),
            (report("runtime"),),
        ),
    ]
    if level == "pilot":
        assert ingestion_source_id is not None
        ingestion_root = candidate_root / "ingestion_pilot"
        specs[-1:-1] = [
            GateSpec(
                "ingestion_pilot",
                (
                    "./scripts/verify-pilot-ingestion.sh",
                    "--source-id",
                    ingestion_source_id,
                    "--ingestion-output",
                    relative(ingestion_root / "ingestion-report.json"),
                    "--automatic-output",
                    relative(ingestion_root / "automatic-ingestion-report.json"),
                    "--automatic-timeout-seconds",
                    str(automatic_ingestion_timeout),
                ),
                (
                    ingestion_root / "ingestion-report.json",
                    ingestion_root / "automatic-ingestion-report.json",
                ),
            )
        ]
    if level == "pilot" or include_backup_restore:
        specs[-1:-1] = [
            GateSpec(
                "backup_restore",
                (
                    "./scripts/verify-local-backup-restore.sh",
                    "--output",
                    relative(report("backup_restore")),
                    "--quiesce-runtime",
                ),
                (report("backup_restore"),),
            )
        ]
    if include_kubernetes:
        specs.append(
            GateSpec(
                "kubernetes",
                (
                    "./scripts/validate-kubernetes.sh",
                    "--output",
                    relative(report("kubernetes")),
                ),
                (report("kubernetes"),),
            )
        )
    return specs


def _prepare_local_runtime(repo: Path) -> None:
    docker = shutil.which("docker")
    if docker is None:
        raise ReleaseEvidenceError("docker is required to deploy the scanned images")
    compose_files = [
        "-f",
        "compose.yaml",
        "-f",
        "compose.dev.yaml",
        "-f",
        "compose.telemetry.yaml",
    ]
    completed = subprocess.run(  # noqa: S603 - repository script and arguments are fixed.
        [
            docker,
            "compose",
            *compose_files,
            "up",
            "-d",
            "--no-build",
            "--force-recreate",
            "--wait",
            "--wait-timeout",
            "300",
        ],
        cwd=repo,
        check=False,
    )
    if completed.returncode != 0:
        raise ReleaseEvidenceError("failed to deploy the scanned images to the local runtime")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture a governed local WSL release candidate without making a production claim"
    )
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--security-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--level", default="development")
    parser.add_argument("--ingestion-source-id")
    parser.add_argument(
        "--token-file",
        type=Path,
        default=Path.home() / ".config" / "pharma-intelligence" / "agent-gateway.key",
    )
    parser.add_argument("--include-kubernetes", action="store_true")
    parser.add_argument("--include-backup-restore", action="store_true")
    parser.add_argument("--mcp-requests", type=int, default=40)
    parser.add_argument("--mcp-concurrency", type=int, default=8)
    parser.add_argument("--automatic-ingestion-timeout", type=int, default=900)
    parser.add_argument("--no-assemble", action="store_true")
    return parser


def execute(arguments: list[str] | None = None) -> tuple[dict[str, object], int]:
    args = _parser().parse_args(arguments)
    repo = args.repo.resolve()
    subject = repository_subject(repo)
    policy_path = (args.policy or repo / "deploy" / "release" / "evidence-policy.json").resolve()
    security_directory = args.security_dir.resolve()
    policy = load_policy(policy_path)
    if args.level not in policy.levels:
        raise ReleaseEvidenceError(f"unknown release evidence level: {args.level}")
    if args.level not in {"development", "pilot"}:
        raise ReleaseEvidenceError("local release candidates only support development or pilot evidence")
    if args.level == "pilot" and not args.ingestion_source_id:
        raise ReleaseEvidenceError("pilot candidates require --ingestion-source-id for a registered real source")
    if args.ingestion_source_id:
        try:
            parsed_source_id = UUID(args.ingestion_source_id)
        except ValueError as exc:
            raise ReleaseEvidenceError("--ingestion-source-id must be a UUID") from exc
        if str(parsed_source_id) != args.ingestion_source_id.lower():
            raise ReleaseEvidenceError("--ingestion-source-id must use canonical UUID syntax")
    if args.level == "development" and args.ingestion_source_id:
        raise ReleaseEvidenceError("--ingestion-source-id is only valid for a pilot candidate")
    if args.mcp_requests < 1 or args.mcp_requests > 1000:
        raise ReleaseEvidenceError("--mcp-requests must be between 1 and 1000")
    if args.mcp_concurrency < 1 or args.mcp_concurrency > min(args.mcp_requests, 50):
        raise ReleaseEvidenceError("--mcp-concurrency must be between 1 and min(requests, 50)")
    if not 60 <= args.automatic_ingestion_timeout <= 86400:
        raise ReleaseEvidenceError("--automatic-ingestion-timeout must be between 60 and 86400")

    runtime_root = (repo / "manifests" / "runtime" / "release-candidates").resolve()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    candidate_root = (
        args.output_root.resolve() if args.output_root is not None else runtime_root / f"{stamp}-{subject.commit[:12]}"
    )
    if candidate_root == runtime_root:
        raise ReleaseEvidenceError("release candidate output cannot be the release-candidates root")
    try:
        candidate_root.relative_to(runtime_root)
    except ValueError as exc:
        raise ReleaseEvidenceError(
            "release candidate output must be below manifests/runtime/release-candidates"
        ) from exc
    if candidate_root.exists() or candidate_root.is_symlink():
        raise ReleaseEvidenceError(f"refusing to overwrite release candidate: {candidate_root}")
    _prepare_local_runtime(repo)
    specs = _gate_specs(
        repo,
        candidate_root,
        level=args.level,
        ingestion_source_id=args.ingestion_source_id,
        include_kubernetes=args.include_kubernetes,
        mcp_requests=args.mcp_requests,
        mcp_concurrency=args.mcp_concurrency,
        automatic_ingestion_timeout=args.automatic_ingestion_timeout,
        include_backup_restore=args.include_backup_restore,
    )
    token_file = args.token_file.expanduser()
    if not token_file.is_absolute():
        token_file = repo / token_file
    token = _read_token_file(token_file) if any(spec.requires_mcp_token for spec in specs) else None
    candidate_root.mkdir(parents=True, mode=0o700)
    candidate_root.chmod(0o700)
    statements: list[Path] = []
    gate_results: dict[str, object] = {}
    capture_errors: list[str] = []

    for spec in specs:
        category_root = candidate_root / spec.category
        statement_path = category_root / "gate-statement.json"
        log_path = category_root / "command.log"
        try:
            with _mcp_environment(token if spec.requires_mcp_token else None):
                statement, exit_code = capture_gate(
                    repo=repo,
                    policy_path=policy_path,
                    category=spec.category,
                    security_directory=security_directory,
                    output=statement_path,
                    command=list(spec.command),
                    attachments=list(spec.attachments),
                    log_attachment=log_path,
                )
            if spec.requires_mcp_token and token is not None:
                try:
                    _assert_secret_absent(category_root, token)
                except ReleaseEvidenceError:
                    shutil.rmtree(category_root)
                    raise
            statements.append(statement_path)
            gate_results[spec.category] = {
                "status": statement["status"],
                "exit_code": exit_code,
                "statement": _relative_command_path(statement_path, repo),
            }
        except ReleaseEvidenceError as exc:
            message = f"{spec.category}: {exc}"
            capture_errors.append(message)
            gate_results[spec.category] = {"status": "capture_error", "error": str(exc)}

    audit = audit_release(
        repo=repo,
        policy_path=policy_path,
        level_name=args.level,
        security_directory=security_directory,
        statements=statements,
        release_tag=None,
    )
    if capture_errors:
        audit["blockers"] = [*audit["blockers"], *capture_errors]
        audit["status"] = "blocked"
    audit_path = candidate_root / "audit.json"
    _atomic_write(audit_path, _canonical_json(audit))

    bundle_path: Path | None = None
    if audit["status"] == "eligible" and not args.no_assemble:
        bundle_path = candidate_root / "bundle"
        assemble_bundle(
            repo=repo,
            policy_path=policy_path,
            level_name=args.level,
            security_directory=security_directory,
            statements=statements,
            output=bundle_path,
        )

    summary: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": audit["status"],
        "release_level": args.level,
        "production_claim": False,
        "git_commit": subject.commit,
        "candidate_root": _relative_command_path(candidate_root, repo),
        "security_directory": _relative_command_path(security_directory, repo),
        "gates": gate_results,
        "audit": _relative_command_path(audit_path, repo),
        "bundle": _relative_command_path(bundle_path, repo) if bundle_path is not None else None,
    }
    _atomic_write(candidate_root / "candidate-summary.json", _canonical_json(summary))
    return summary, 0 if audit["status"] == "eligible" else 3


def main(arguments: list[str] | None = None) -> int:
    try:
        summary, exit_code = execute(arguments)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return exit_code
    except ReleaseEvidenceError as exc:
        print(f"release candidate error: {exc}", file=sys.stderr)
        return 2


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
