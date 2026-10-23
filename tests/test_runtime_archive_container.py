from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

LIBRARY = Path(__file__).parents[1] / "scripts/lib/runtime_archive_container.sh"
NAME = "pharma-backup-archive-123-456-object-write"
IDENTITY = "a" * 64


def run_archive(name: str = NAME, arguments: list[str] | None = None) -> subprocess.CompletedProcess[bytes]:
    bash = shutil.which("bash")
    assert bash is not None
    return subprocess.run(  # noqa: S603 - Only the owned function and fixed synthetic stream are exercised.
        [
            bash,
            "-c",
            'set -Eeuo pipefail; source "$1"; shift; run_runtime_archive "$@"',
            "archive-test",
            str(LIBRARY),
            name,
            *(arguments if arguments is not None else ["--", "tar", "-czf", "-", "-C", "/source", "."]),
        ],
        input=b"controlled engineering archive stream\x00\xff\n",
        capture_output=True,
        check=False,
        timeout=5,
    )


@pytest.fixture
def archive_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    directory = tmp_path / "bin"
    directory.mkdir()
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    state = tmp_path / "container-state"
    trace = tmp_path / "docker-argv"
    docker = directory / "docker"
    docker.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$ARCHIVE_TEST_TRACE"
case "$1" in
  create)
    case "${ARCHIVE_TEST_MODE:-normal}" in
      create-fail) exit 51 ;;
      collision) printf 'foreign\\n' > "$ARCHIVE_TEST_STATE"; exit 125 ;;
    esac
    printf 'owned\\n' > "$ARCHIVE_TEST_STATE"
    printf '%s\\n' "$ARCHIVE_TEST_ID" ;;
  start)
    [[ ${ARCHIVE_TEST_MODE:-normal} != start-fail ]] || exit 52
    cat ;;
  inspect)
    case "${ARCHIVE_TEST_MODE:-normal}" in
      nonzero) printf 'exited 7\\n' ;;
      running) printf 'running 0\\n' ;;
      *) printf 'exited 0\\n' ;;
    esac ;;
  container)
    [[ $2 == ls ]]
    [[ ${ARCHIVE_TEST_MODE:-normal} != daemon-error ]] || exit 19
    if [[ -f "$ARCHIVE_TEST_STATE" && $(<"$ARCHIVE_TEST_STATE") == owned ]]; then
      printf '%s %s\\n' "$ARCHIVE_TEST_ID" "$ARCHIVE_TEST_NAME"
    fi ;;
  rm)
    [[ ${ARCHIVE_TEST_MODE:-normal} != retained ]] || exit 9
    [[ $* == "rm -f $ARCHIVE_TEST_ID" ]]
    rm -- "$ARCHIVE_TEST_STATE" ;;
  *) exit 99 ;;
esac
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    timeout = directory / "timeout"
    timeout.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
[[ $1 == --kill-after=2s ]]
shift 2
if [[ ${ARCHIVE_TEST_MODE:-normal} == start-timeout && $1 == docker && $2 == start ]]; then exit 124; fi
exec "$@"
""",
        encoding="utf-8",
    )
    timeout.chmod(0o755)
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("TMPDIR", str(temporary))
    monkeypatch.setenv("ARCHIVE_TEST_TRACE", str(trace))
    monkeypatch.setenv("ARCHIVE_TEST_STATE", str(state))
    monkeypatch.setenv("ARCHIVE_TEST_ID", IDENTITY)
    monkeypatch.setenv("ARCHIVE_TEST_NAME", NAME)
    return state, trace, temporary


def test_archive_preserves_the_binary_stream_and_only_succeeds_after_owned_cleanup(
    archive_runtime: tuple[Path, Path, Path],
) -> None:
    state, trace, temporary = archive_runtime
    result = run_archive()
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout == b"controlled engineering archive stream\x00\xff\n"
    assert not state.exists() and not list(temporary.iterdir())
    calls = trace.read_text().splitlines()
    assert calls[0].startswith("create --pull=never --network none --read-only --interactive --name " + NAME)
    assert "--label io.pharma.archive-owner=pharma-archive." in calls[0]
    assert "--rm" not in calls[0]
    assert calls[1] == f"start --attach --interactive {IDENTITY}"
    assert calls[2].startswith("inspect ") and IDENTITY in calls[2]
    assert calls[3].startswith("container ls ")
    assert calls[4] == f"rm -f {IDENTITY}"
    assert calls[5].startswith("container ls ")


@pytest.mark.parametrize("mode", ["create-fail", "start-fail", "nonzero", "running", "start-timeout"])
def test_failed_execution_never_publishes_success_and_cleans_only_the_owned_container(
    archive_runtime: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    state, trace, temporary = archive_runtime
    monkeypatch.setenv("ARCHIVE_TEST_MODE", mode)
    result = run_archive()
    assert result.returncode != 0
    assert not state.exists() and not list(temporary.iterdir())
    if mode == "create-fail":
        assert "rm -f" not in trace.read_text()


def test_existing_name_collision_cannot_remove_a_foreign_container(
    archive_runtime: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    state, trace, temporary = archive_runtime
    monkeypatch.setenv("ARCHIVE_TEST_MODE", "collision")
    assert run_archive().returncode == 125
    assert state.read_text().strip() == "foreign"
    assert "rm -f" not in trace.read_text()
    assert not list(temporary.iterdir())


@pytest.mark.parametrize("mode", ["daemon-error", "retained"])
def test_unconfirmed_cleanup_retains_the_private_work_directory_and_fails_closed(
    archive_runtime: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    state, _, temporary = archive_runtime
    monkeypatch.setenv("ARCHIVE_TEST_MODE", mode)
    result = run_archive()
    assert result.returncode != 0
    assert state.is_file() and len(list(temporary.iterdir())) == 1
    assert b"cleanup is incomplete" in result.stderr


@pytest.mark.parametrize("name", ["x-pharma-architecture-api-1", "pharma-backup-archive-1-2-object-write;true", ""])
def test_formal_or_malformed_names_are_rejected_before_docker(
    archive_runtime: tuple[Path, Path, Path], name: str
) -> None:
    _, trace, temporary = archive_runtime
    assert run_archive(name).returncode == 2
    assert not trace.exists() and not list(temporary.iterdir())


def test_every_archive_docker_operation_has_a_kill_bound_and_no_automatic_removal() -> None:
    source = LIBRARY.read_text()
    calls = [line.strip() for line in source.splitlines() if " docker " in line]
    assert len(calls) == 6
    assert all("timeout --kill-after=2s " in line for line in calls)
    assert "20s docker create --pull=never --network none --read-only --interactive" in source
    assert "120s docker start --attach --interactive" in source
    assert "--rm" not in source


@pytest.mark.parametrize("arguments", [["--network", "host", "--", "tar"], ["--", "sh", "-c", "true"], ["--mount"]])
def test_caller_cannot_override_owned_docker_options_or_replace_the_archive_command(
    archive_runtime: tuple[Path, Path, Path], arguments: list[str]
) -> None:
    _, trace, temporary = archive_runtime
    assert run_archive(arguments=arguments).returncode == 2
    assert not trace.exists() and not list(temporary.iterdir())


def test_filesystem_root_cannot_be_used_as_the_cleanup_parent(
    archive_runtime: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, trace, temporary = archive_runtime
    monkeypatch.setenv("TMPDIR", "/")
    assert run_archive().returncode == 2
    assert not trace.exists() and not list(temporary.iterdir())


@pytest.mark.parametrize("script", ["backup-runtime-linux.sh", "restore-smoke-linux.sh"])
def test_backup_and_isolated_restore_share_the_one_bounded_archive_owner(script: str) -> None:
    source = (LIBRARY.parents[1] / script).read_text()
    assert source.count('source "$root/scripts/lib/runtime_archive_container.sh"') == 1
    assert source.count("run_runtime_archive ") == 2
    assert "--rm" not in source
    assert "busybox:" not in source
