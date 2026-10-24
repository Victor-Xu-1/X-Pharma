from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

LIBRARY = Path(__file__).parents[1] / "scripts/lib/restore_smoke_resources.sh"


def _cleanup(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash is not None
    return subprocess.run(  # noqa: S603 - Controlled local helper and argument vector, not shell interpolation.
        [
            bash,
            "-c",
            'set -euo pipefail; source "$1"; shift; restore_smoke_cleanup "$@"',
            "restore-cleanup",
            str(LIBRARY),
            *arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )


@pytest.fixture
def isolated_resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], Path, Path]:
    workspace = tmp_path / "pharma-restore-smoke.ABC123"
    workspace.mkdir()
    (workspace / "expected-counts.tsv").write_text("controlled fixture\n", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("must remain\n", encoding="utf-8")
    container = "pharma-restore-smoke-123-456"
    volumes = [f"pharma-restore-smoke-{kind}-123-456" for kind in ("postgres", "object", "markdown")]
    arguments = [str(tmp_path), str(workspace), container, container + "-rls", *volumes]
    directory = tmp_path / "bin"
    directory.mkdir()
    docker = directory / "docker"
    docker.write_text(
        """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$RESTORE_TEST_TRACE"
case "$1:$2" in
  rm:-f|volume:rm)
    if [[ ${RESTORE_TEST_MODE:-normal} == missing ]]; then exit 1; fi ;;
  container:ls)
    case "${RESTORE_TEST_MODE:-normal}" in
      daemon-error) exit 9 ;;
      container-retained) printf '%s\\n' "$RESTORE_TEST_CONTAINER" ;;
      *) printf 'unrelated-online-container\\n' ;;
    esac ;;
  volume:ls)
    if [[ ${RESTORE_TEST_MODE:-normal} == volume-retained ]]; then
      printf '%s\\n' "$RESTORE_TEST_VOLUME"
    else
      printf 'unrelated-authority-volume\\n'
    fi ;;
  *) exit 99 ;;
esac
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    trace = tmp_path / "docker.log"
    monkeypatch.setenv("RESTORE_TEST_TRACE", str(trace))
    monkeypatch.setenv("RESTORE_TEST_CONTAINER", container)
    monkeypatch.setenv("RESTORE_TEST_VOLUME", volumes[0])
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ["PATH"])
    return arguments, workspace, trace


@pytest.mark.parametrize("mode", ["normal", "missing"])
def test_removes_only_exact_run_resources_after_proving_they_are_absent(
    isolated_resources: tuple[list[str], Path, Path], monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    arguments, workspace, trace = isolated_resources
    monkeypatch.setenv("RESTORE_TEST_MODE", mode)
    result = _cleanup(arguments)
    assert result.returncode == 0, result.stderr
    assert not workspace.exists()
    assert (workspace.parent / "outside.txt").read_text(encoding="utf-8") == "must remain\n"
    calls = trace.read_text(encoding="utf-8").splitlines()
    assert calls[0] == f"rm -f {arguments[3]} {arguments[2]}"
    assert calls[2] == "volume rm " + " ".join(arguments[4:])
    assert len(calls) == 4


@pytest.mark.parametrize("mode", ["daemon-error", "container-retained", "volume-retained"])
def test_failed_cleanup_retains_workspace_and_never_reports_success(
    isolated_resources: tuple[list[str], Path, Path], monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    arguments, workspace, trace = isolated_resources
    monkeypatch.setenv("RESTORE_TEST_MODE", mode)
    result = _cleanup(arguments)
    assert result.returncode == 1
    assert workspace.is_dir()
    assert (workspace.parent / "outside.txt").is_file()
    if mode != "volume-retained":
        assert "volume rm " not in trace.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "unsafe",
    [
        "parent-root",
        "workspace-root",
        "online-container",
        "online-probe",
        "online-volume",
        "duplicate-volume",
        "parent-alias",
        "wrong-directory",
    ],
)
def test_rejects_unsafe_cleanup_targets_before_any_docker_or_deletion(
    isolated_resources: tuple[list[str], Path, Path], unsafe: str
) -> None:
    arguments, workspace, trace = isolated_resources
    values = arguments.copy()
    if unsafe == "parent-root":
        values[0] = "/"
    elif unsafe == "workspace-root":
        values[1] = "/"
    elif unsafe == "online-container":
        values[2] = "x-pharma-architecture-postgres-1"
    elif unsafe == "online-probe":
        values[3] = "x-pharma-architecture-api-1"
    elif unsafe == "online-volume":
        values[4] = "pharma_postgres18_data"
    elif unsafe == "duplicate-volume":
        values[5] = values[4]
    elif unsafe == "parent-alias":
        values[0] += "/."
    else:
        other = workspace.parent / "not-owned"
        other.mkdir()
        values[1] = str(other)
    result = _cleanup(values)
    assert result.returncode == 2
    assert workspace.is_dir()
    assert not trace.exists()
    assert (workspace.parent / "outside.txt").is_file()


def test_rejects_a_symlinked_workspace_without_touching_the_target(
    isolated_resources: tuple[list[str], Path, Path],
) -> None:
    arguments, workspace, trace = isolated_resources
    link = workspace.parent / "pharma-restore-smoke.DEF456"
    link.symlink_to(workspace, target_is_directory=True)
    arguments[1] = str(link)
    result = _cleanup(arguments)
    assert result.returncode == 2
    assert workspace.is_dir() and link.is_symlink()
    assert not trace.exists()


def test_timeout_cannot_be_misread_as_an_empty_resource_inventory(
    isolated_resources: tuple[list[str], Path, Path],
) -> None:
    arguments, workspace, trace = isolated_resources
    timeout = workspace.parent / "bin/timeout"
    timeout.write_text("#!/bin/sh\nexit 124\n", encoding="utf-8")
    timeout.chmod(0o755)
    result = _cleanup(arguments)
    assert result.returncode == 1
    assert workspace.is_dir()
    assert not trace.exists()


def test_all_docker_cleanup_calls_have_explicit_failure_bounds() -> None:
    calls = [line.strip() for line in LIBRARY.read_text(encoding="utf-8").splitlines() if " docker " in line]
    assert len(calls) == 4
    assert all("timeout --kill-after=2s " in line for line in calls)
    assert "15s docker rm -f" in calls[0]
    assert "5s docker container ls" in calls[1]
    assert "10s docker volume rm" in calls[2]
    assert "5s docker volume ls" in calls[3]
