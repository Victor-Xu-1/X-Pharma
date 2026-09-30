from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.capture_local_release_candidate import (
    _assert_secret_absent,
    _gate_specs,
    _mcp_environment,
    _prepare_local_runtime,
    _read_token_file,
    _relative_command_path,
)
from scripts.release_evidence import ReleaseEvidenceError


def test_release_candidate_prepares_observed_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], Path, bool]] = []
    docker = "/usr/bin/docker"
    monkeypatch.setattr(shutil, "which", lambda name: docker if name == "docker" else None)

    def fake_run(command: list[str], *, cwd: Path, check: bool) -> subprocess.CompletedProcess[str]:
        calls.append((command, cwd, check))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    _prepare_local_runtime(tmp_path)

    assert calls == [
        (
            [
                docker,
                "compose",
                "-f",
                "compose.yaml",
                "-f",
                "compose.dev.yaml",
                "-f",
                "compose.telemetry.yaml",
                "up",
                "-d",
                "--no-build",
                "--force-recreate",
                "--wait",
                "--wait-timeout",
                "300",
            ],
            tmp_path,
            False,
        )
    ]


def test_release_candidate_deploys_the_observed_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    docker = "/usr/bin/docker"
    monkeypatch.setattr(shutil, "which", lambda name: docker if name == "docker" else None)

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    _prepare_local_runtime(tmp_path)

    assert calls == [
        [
            docker,
            "compose",
            "-f",
            "compose.yaml",
            "-f",
            "compose.dev.yaml",
            "-f",
            "compose.telemetry.yaml",
            "up",
            "-d",
            "--no-build",
            "--force-recreate",
            "--wait",
            "--wait-timeout",
            "300",
        ]
    ]


def test_release_candidate_rejects_runtime_deployment_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 17),
    )

    with pytest.raises(ReleaseEvidenceError, match="deploy the scanned images"):
        _prepare_local_runtime(tmp_path)


def test_token_file_requires_private_current_user_owned_regular_file(tmp_path: Path) -> None:
    token_path = tmp_path / "token"
    token_path.write_text("t" * 64 + "\n", encoding="utf-8")
    token_path.chmod(0o600)

    assert _read_token_file(token_path) == "t" * 64

    token_path.chmod(0o640)
    with pytest.raises(ReleaseEvidenceError, match="0600"):
        _read_token_file(token_path)


def test_token_file_rejects_symlinks_and_whitespace(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("t" * 64 + "\n", encoding="utf-8")
    target.chmod(0o600)
    symlink = tmp_path / "token-link"
    symlink.symlink_to(target)

    with pytest.raises(ReleaseEvidenceError, match="regular file"):
        _read_token_file(symlink)

    target.write_text("prefix secret with spaces" * 3, encoding="utf-8")
    with pytest.raises(ReleaseEvidenceError, match="non-whitespace"):
        _read_token_file(target)


def test_secret_scanner_detects_a_token_across_read_chunks(tmp_path: Path) -> None:
    token = "s" * 64
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "report.json").write_bytes(b"x" * (64 * 1024 - 20) + token.encode() + b"tail")

    with pytest.raises(ReleaseEvidenceError, match="attempted to record"):
        _assert_secret_absent(evidence, token)

    (evidence / "report.json").write_text('{"status":"passed"}\n', encoding="utf-8")
    _assert_secret_absent(evidence, token)


def test_mcp_environment_restores_the_callers_process_state(monkeypatch: pytest.MonkeyPatch) -> None:
    original = "original-value"
    temporary = "temporary-value"
    monkeypatch.setenv("TEST_MCP_ACCESS_TOKEN", original)

    with _mcp_environment(temporary):
        assert os.environ["TEST_MCP_ACCESS_TOKEN"] == temporary

    assert os.environ["TEST_MCP_ACCESS_TOKEN"] == original


def test_runtime_command_path_preserves_external_runtime_symlink_boundary(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    logical_runtime = repo / "manifests" / "runtime"
    external_runtime = tmp_path / "runtime"
    logical_runtime.parent.mkdir(parents=True)
    external_runtime.mkdir()
    logical_runtime.symlink_to(external_runtime, target_is_directory=True)
    candidate = external_runtime / "release-candidates" / "candidate" / "report.json"

    assert _relative_command_path(candidate, repo) == "manifests/runtime/release-candidates/candidate/report.json"

    with pytest.raises(ReleaseEvidenceError, match="configured runtime directory"):
        _relative_command_path(tmp_path / "untrusted" / "report.json", repo)


def test_development_gate_specs_cover_both_product_entries_without_secret_arguments(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    candidate = repo / "manifests" / "runtime" / "release-candidates" / "candidate"
    specs = _gate_specs(
        repo,
        candidate,
        level="development",
        ingestion_source_id=None,
        include_kubernetes=False,
        mcp_requests=40,
        mcp_concurrency=8,
    )

    assert {spec.category for spec in specs} == {
        "quality",
        "source_reproducibility",
        "database",
        "browser",
        "entry_consistency",
        "record_consistency",
        "anti_extraction_baseline",
        "mcp_protocol",
        "mcp_async_tasks",
        "mcp_commercial",
        "performance_baseline",
        "operations_contract",
        "parser_sandbox",
        "ocr",
        "ingestion_readiness",
        "runtime",
    }
    assert all("TEST_MCP_ACCESS_TOKEN" not in argument for spec in specs for argument in spec.command)
    assert all(str(Path.home()) not in argument for spec in specs for argument in spec.command)
    assert {spec.category for spec in specs if spec.requires_mcp_token} == {
        "entry_consistency",
        "mcp_protocol",
        "mcp_commercial",
        "performance_baseline",
        "operations_contract",
    }
    operations = next(spec for spec in specs if spec.category == "operations_contract")
    assert operations.command[0] == "./scripts/verify-local-observability.sh"
    assert operations.attachments == (candidate / "operations_contract" / "report.json",)
    protocol = next(spec for spec in specs if spec.category == "mcp_protocol")
    assert protocol.command[0] == "./scripts/verify-mcp-interoperability.sh"
    async_tasks = next(spec for spec in specs if spec.category == "mcp_async_tasks")
    assert async_tasks.command[:2] == ("./scripts/verify-mcp-interoperability.sh", "--async-task-only")
    assert async_tasks.requires_mcp_token is False
    reproducibility = next(spec for spec in specs if spec.category == "source_reproducibility")
    assert reproducibility.command[:4] == ("uv", "run", "python", "scripts/verify_clean_source.py")
    assert reproducibility.attachments == (candidate / "source_reproducibility" / "report.json",)
    readiness = next(spec for spec in specs if spec.category == "ingestion_readiness")
    assert readiness.command[:4] == ("uv", "run", "python", "scripts/capture_ingestion_readiness.py")
    assert readiness.attachments == (candidate / "ingestion_readiness" / "report.json",)
    ocr = next(spec for spec in specs if spec.category == "ocr")
    assert ocr.command[:3] == ("python3", "-m", "scripts.verify_local_ocr")
    assert ocr.attachments == (candidate / "ocr" / "report.json",)
    record_consistency = next(spec for spec in specs if spec.category == "record_consistency")
    assert record_consistency.command[:5] == (
        "uv",
        "run",
        "--no-sync",
        "python",
        "scripts/record_consistency_probe.py",
    )
    assert record_consistency.requires_mcp_token is False
    anti_extraction = next(spec for spec in specs if spec.category == "anti_extraction_baseline")
    assert anti_extraction.command[:5] == (
        "uv",
        "run",
        "--no-sync",
        "python",
        "scripts/mcp_anti_extraction_probe.py",
    )
    assert anti_extraction.requires_mcp_token is False
    runtime = next(spec for spec in specs if spec.category == "runtime")
    assert runtime.command == (
        "./scripts/status.sh",
        "--output",
        "manifests/runtime/release-candidates/candidate/runtime/report.json",
    )
    assert runtime.attachments == (candidate / "runtime" / "report.json",)


def test_hardened_development_gate_specs_add_restore_and_real_api_server_validation(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    candidate = repo / "manifests" / "runtime" / "release-candidates" / "candidate"
    specs = _gate_specs(
        repo,
        candidate,
        level="development",
        ingestion_source_id=None,
        include_kubernetes=True,
        include_backup_restore=True,
        mcp_requests=40,
        mcp_concurrency=8,
    )

    categories = [spec.category for spec in specs]
    assert categories.count("backup_restore") == 1
    assert categories.count("kubernetes") == 1
    assert categories.index("backup_restore") < categories.index("runtime")
    assert categories.index("runtime") < categories.index("kubernetes")
    assert next(spec for spec in specs if spec.category == "backup_restore").attachments == (
        candidate / "backup_restore" / "report.json",
    )
    assert "--quiesce-runtime" in next(spec for spec in specs if spec.category == "backup_restore").command
    assert next(spec for spec in specs if spec.category == "kubernetes").attachments == (
        candidate / "kubernetes" / "report.json",
    )


def test_pilot_gate_specs_require_real_ingestion_and_isolated_restore(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    candidate = repo / "manifests" / "runtime" / "release-candidates" / "candidate"
    source_id = "0b1db158-0dad-4195-9f0d-7f03f818cf40"
    specs = _gate_specs(
        repo,
        candidate,
        level="pilot",
        ingestion_source_id=source_id,
        include_kubernetes=False,
        mcp_requests=40,
        mcp_concurrency=8,
    )

    assert {spec.category for spec in specs} == {
        "quality",
        "source_reproducibility",
        "database",
        "browser",
        "entry_consistency",
        "record_consistency",
        "anti_extraction_baseline",
        "mcp_protocol",
        "mcp_async_tasks",
        "mcp_commercial",
        "performance_baseline",
        "operations_contract",
        "parser_sandbox",
        "ocr",
        "ingestion_readiness",
        "ingestion_pilot",
        "backup_restore",
        "runtime",
    }
    ingestion = next(spec for spec in specs if spec.category == "ingestion_pilot")
    assert source_id in ingestion.command
    assert ingestion.command[0] == "./scripts/verify-pilot-ingestion.sh"
    assert ingestion.command[-2:] == ("--automatic-timeout-seconds", "900")
    assert {path.name for path in ingestion.attachments} == {
        "automatic-ingestion-report.json",
        "ingestion-report.json",
    }
    assert all(path.parent == candidate / "ingestion_pilot" for path in ingestion.attachments)
    assert all("/ingestion_pilot/" in argument for argument in ingestion.command if argument.endswith(".json"))
    assert all("source-empty" not in argument for spec in specs for argument in spec.command)
    assert "--quiesce-runtime" in next(spec for spec in specs if spec.category == "backup_restore").command


def test_release_candidate_cli_help_runs_directly() -> None:
    root = Path(__file__).parents[1]
    completed = subprocess.run(  # noqa: S603 - interpreter and repository script are controlled.
        [sys.executable, "scripts/capture_local_release_candidate.py", "--help"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "without making a production claim" in " ".join(completed.stdout.split())


def test_make_release_candidate_uses_the_cli_token_contract() -> None:
    root = Path(__file__).parents[1]
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    target = makefile.split("release-candidate:", maxsplit=1)[1].split("release-audit:", maxsplit=1)[0]

    assert "--token-file" in target
    assert "--mcp-token-file" not in target
