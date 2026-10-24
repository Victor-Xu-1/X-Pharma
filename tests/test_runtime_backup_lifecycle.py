"""Fresh-backup writer/workspace ownership, with no business Docker access."""

from __future__ import annotations

import json
import os
import select
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from tests.runtime_backup_fixture import IDS

ROOT = Path(__file__).parents[1]


@pytest.fixture
def controlled_transport(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir()
    for tool in ("docker", "systemctl", "systemd-run"):
        executable = directory / tool
        executable.write_text(
            '#!/usr/bin/env bash\nexec "$BACKUP_FIXTURE_PYTHON" "$BACKUP_FIXTURE_SCRIPT" ' + tool + ' "$@"\n',
            encoding="utf-8",
        )
        executable.chmod(0o755)
    parent = tmp_path / "private-temp"
    parent.mkdir()
    monkeypatch.setenv("TMPDIR", str(parent))
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("BACKUP_FIXTURE_PYTHON", sys.executable)
    monkeypatch.setenv("BACKUP_FIXTURE_SCRIPT", str(ROOT / "tests/runtime_backup_fixture.py"))
    monkeypatch.setenv("BACKUP_FIXTURE_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("BACKUP_FIXTURE_TRACE", str(tmp_path / "trace.json"))
    return parent


def run_owner(action: str, *, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash is not None
    source = shlex.quote(str(ROOT / "scripts/lib/runtime_backup_lifecycle.sh"))
    return subprocess.run(  # noqa: S603 - Actual owned library, synthetic management commands only.
        [
            bash,
            "-c",
            f'set -Eeuo pipefail; umask 077; source {source}; runtime_backup_lifecycle_init "$TMPDIR"; {action}',
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def read_transport(parent: Path) -> tuple[dict[str, Any], list[list[str]]]:
    state_path, trace_path = parent.parent / "state.json", parent.parent / "trace.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    trace = json.loads(trace_path.read_text()) if trace_path.exists() else []
    return state, trace


def test_fresh_backup_has_one_bounded_lifecycle_before_report_publication() -> None:
    source = (ROOT / "scripts/verify-local-backup-restore.sh").read_text(encoding="utf-8")
    assert 'source "$root/scripts/lib/runtime_backup_lifecycle.sh"' in source
    assert 'runtime_backup_quiesce "$project_name"' in source
    assert source.index("runtime_backup_lifecycle_cleanup ||") < source.index(
        'python3 "$root/scripts/lib/runtime_backup_report.py"'
    )
    assert "trap cleanup EXIT INT TERM" not in source
    assert "rm -rf" not in source


def test_configured_non_tmp_parent_is_cleaned_and_cleanup_is_idempotent(controlled_transport: Path) -> None:
    result = run_owner("runtime_backup_lifecycle_cleanup; runtime_backup_lifecycle_cleanup")
    assert result.returncode == 0, result.stderr
    assert not list(controlled_transport.iterdir())
    assert read_transport(controlled_transport) == ({}, [])


def test_verified_resume_and_watchdog_cancellation_precede_clean_success(controlled_transport: Path) -> None:
    result = run_owner(
        "runtime_backup_quiesce x-pharma-controlled; runtime_backup_resume; runtime_backup_lifecycle_cleanup"
    )
    assert result.returncode == 0, result.stderr
    state, trace = read_transport(controlled_transport)
    assert state["paused"] == {identity: False for identity in IDS.values()}
    assert state["watchdog"] is False
    pause = next(index for index, entry in enumerate(trace) if entry[:2] == ["docker", "pause"])
    watchdog = next(index for index, entry in enumerate(trace) if entry[0] == "systemd-run")
    assert watchdog < pause
    assert "30s" in trace[watchdog] and "--on-active=10m" in trace[watchdog]
    assert not list(controlled_transport.iterdir())


@pytest.mark.parametrize("exit_action,code", [("exit 17", 17), ("kill -INT $$", 130), ("kill -TERM $$", 143)])
def test_exit_and_signals_restore_owned_writers_and_preserve_failure(
    controlled_transport: Path,
    exit_action: str,
    code: int,
) -> None:
    result = run_owner("runtime_backup_quiesce x-pharma-controlled; " + exit_action)
    assert result.returncode == code, result.stderr
    state, _ = read_transport(controlled_transport)
    assert all(value is False for value in state["paused"].values())
    assert state["watchdog"] is False
    assert not list(controlled_transport.iterdir())


def test_partial_pause_failure_still_recovers_only_the_attempted_writer_set(
    controlled_transport: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BACKUP_FIXTURE_MODE", "partial-pause")
    result = run_owner("runtime_backup_quiesce x-pharma-controlled")
    assert result.returncode != 0
    state, trace = read_transport(controlled_transport)
    assert state["paused"] == {IDS["api"]: False}
    unpaused = [entry[-1] for entry in trace if entry[:2] == ["docker", "unpause"]]
    assert unpaused == [IDS["api"]]
    assert state["watchdog"] is False
    assert not list(controlled_transport.iterdir())


@pytest.mark.parametrize(
    "mode", ["inspect-failure", "replaced", "unpause-failure", "unpause-retained", "stop-failure", "timer-unknown"]
)
def test_unknown_or_failed_resume_retains_evidence_and_cannot_pass(
    controlled_transport: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    monkeypatch.setenv("BACKUP_FIXTURE_MODE", mode)
    result = run_owner(
        "runtime_backup_quiesce x-pharma-controlled; runtime_backup_lifecycle_cleanup; printf UNEXPECTED_SUCCESS"
    )
    assert result.returncode != 0 and "UNEXPECTED_SUCCESS" not in result.stdout
    state, trace = read_transport(controlled_transport)
    workspaces = list(controlled_transport.iterdir())
    assert len(workspaces) == 1 and (workspaces[0] / "writers.txt").is_file()
    if mode in {"inspect-failure", "replaced", "unpause-failure", "unpause-retained"}:
        assert state["watchdog"] is True
        assert not any(entry[:3] == ["systemctl", "--user", "stop"] for entry in trace)
    if mode == "replaced":
        assert not any(entry[:2] == ["docker", "unpause"] and entry[-1] == IDS["api"] for entry in trace)


@pytest.mark.parametrize("mode", ["inventory-failure", "already-paused", "duplicate", "arm-failure"])
def test_preflight_or_watchdog_failure_never_pauses_any_writer(
    controlled_transport: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    monkeypatch.setenv("BACKUP_FIXTURE_MODE", mode)
    result = run_owner("runtime_backup_quiesce x-pharma-controlled")
    assert result.returncode != 0
    _, trace = read_transport(controlled_transport)
    assert not any(entry[:2] in (["docker", "pause"], ["docker", "unpause"]) for entry in trace)
    assert not list(controlled_transport.iterdir())


@pytest.mark.parametrize("entry", ["unknown.txt", ".hidden", "nested"])
def test_unknown_files_and_directories_are_retained_not_recursively_removed(
    controlled_transport: Path, entry: str
) -> None:
    action = (
        'mkdir "$backup_lifecycle_work/nested"'
        if entry == "nested"
        else f'printf keep > "$backup_lifecycle_work/{entry}"'
    )
    result = run_owner(action + "; runtime_backup_lifecycle_cleanup")
    assert result.returncode != 0
    workspaces = list(controlled_transport.iterdir())
    assert len(workspaces) == 1 and (workspaces[0] / entry).exists()


def test_symlinked_known_file_cannot_delete_its_target(controlled_transport: Path) -> None:
    target = controlled_transport.parent / "foreign.txt"
    target.write_text("must remain", encoding="utf-8")
    result = run_owner(
        f'ln -s {shlex.quote(str(target))} "$backup_lifecycle_work/restore.json"; runtime_backup_lifecycle_cleanup'
    )
    assert result.returncode != 0
    assert target.read_text() == "must remain"
    assert len(list(controlled_transport.iterdir())) == 1


def test_replaced_workspace_inode_is_not_adopted_or_deleted(controlled_transport: Path) -> None:
    result = run_owner(
        'mv "$backup_lifecycle_work" "$backup_lifecycle_work.retained"; '
        'mkdir "$backup_lifecycle_work"; printf keep > "$backup_lifecycle_work/restore.json"; '
        "runtime_backup_lifecycle_cleanup"
    )
    assert result.returncode != 0
    workspaces = list(controlled_transport.iterdir())
    assert len(workspaces) == 2
    assert any(
        (path / "restore.json").read_text() == "keep" for path in workspaces if (path / "restore.json").is_file()
    )


def test_real_timeout_terminates_a_hung_controlled_transport(
    controlled_transport: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BACKUP_FIXTURE_MODE", "hang")
    started = time.monotonic()
    result = run_owner("runtime_backup_docker 1 inspect --format fixture " + IDS["api"], timeout=5)
    assert result.returncode == 124
    assert time.monotonic() - started < 4
    assert not list(controlled_transport.iterdir())


def test_concurrent_acceptance_cannot_share_the_same_authority_lock(controlled_transport: Path) -> None:
    bash = shutil.which("bash")
    assert bash is not None
    source = shlex.quote(str(ROOT / "scripts/lib/runtime_backup_lifecycle.sh"))
    program = (
        f'set -Eeuo pipefail; umask 077; source {source}; runtime_backup_lifecycle_init "$TMPDIR"; '
        "printf 'LOCK_READY\\n'; read -r release"
    )
    with subprocess.Popen(  # noqa: S603 - Actual flock ownership, private fixture directory only.
        [bash, "-c", program],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as owner:
        assert owner.stdout is not None
        try:
            assert select.select([owner.stdout], [], [], 5)[0], "first acceptance failed to acquire its private lock"
            assert owner.stdout.readline().strip() == "LOCK_READY"
            result = run_owner("printf UNEXPECTED_SUCCESS")
            assert result.returncode != 0 and "UNEXPECTED_SUCCESS" not in result.stdout
            assert "Another fresh-backup acceptance" in result.stderr
            assert len(list(controlled_transport.iterdir())) == 1
        finally:
            _, errors = owner.communicate("release\n", timeout=5)
        assert owner.returncode == 0, errors
    assert not list(controlled_transport.iterdir())
    assert run_owner("runtime_backup_lifecycle_cleanup").returncode == 0
