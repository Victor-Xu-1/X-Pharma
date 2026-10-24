from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
LIBRARY = ROOT / "scripts/lib/runtime_restore_resources.sh"
POSTGRES = "sha256:" + "1" * 64
API = "sha256:" + "2" * 64
DRIVER = r"""
set -Eeuo pipefail
source "$1"
runtime_restore_resources_init "${RESTORE_RESOURCE_PROJECT:-fixture}" "${RESTORE_RESOURCE_SUFFIX:-123-456}" "$2" "$3"
finish() {
  local status=$?
  trap - EXIT INT TERM
  if ! runtime_restore_cleanup; then
    echo "cleanup incomplete; retained=$restore_work_dir" >&2
    [[ $status -ne 0 ]] || status=1
  fi
  exit "$status"
}
trap finish EXIT
for index in 0 1 2; do runtime_restore_create_volume "$index" 2.39.4; done
runtime_restore_assert_volume "${restore_volumes[0]}"
postgres=$(runtime_restore_docker 20 create --pull=never --name "${restore_containers[0]}" \
  --label "io.pharma.runtime-restore-owner=$restore_owner" "$2")
probe=$(runtime_restore_docker 20 create --pull=never --name "${restore_containers[1]}" \
  --label "io.pharma.runtime-restore-owner=$restore_owner" "$3" pharma-verify-rls)
printf 'expected\n' > "$restore_work_dir/expected-counts.tsv"
printf 'actual\n' > "$restore_work_dir/actual-counts.tsv"
case "${RESTORE_RESOURCE_ACTION:-preserve}" in
  fail) exit 51 ;;
  unexpected-file) printf 'retained evidence\n' > "$restore_work_dir/unknown.txt" ;;
  symlink-workspace)
    mv -- "$restore_work_dir" "$restore_work_dir-real"
    ln -s "$restore_work_dir-real" "$restore_work_dir"
    ;;
esac
runtime_restore_cleanup preserve
printf 'passed\n'
"""


def run_owner() -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash is not None
    return subprocess.run(  # noqa: S603 - Controlled helper and synthetic transport, never the Docker daemon.
        [bash, "-c", DRIVER, "restore-owner-test", str(LIBRARY), POSTGRES, API],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.fixture
def owned_resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    binary = tmp_path / "bin"
    binary.mkdir()
    docker = binary / "docker"
    docker.write_text(
        '#!/usr/bin/env bash\nexec "$RESTORE_RESOURCE_PYTHON" "$RESTORE_RESOURCE_FIXTURE" "$@"\n',
        encoding="utf-8",
    )
    docker.chmod(0o755)
    state, trace, temporary = tmp_path / "state.json", tmp_path / "trace.jsonl", tmp_path / "temporary"
    temporary.mkdir()
    monkeypatch.setenv("RESTORE_RESOURCE_STATE", str(state))
    monkeypatch.setenv("RESTORE_RESOURCE_TRACE", str(trace))
    monkeypatch.setenv("RESTORE_RESOURCE_PYTHON", sys.executable)
    monkeypatch.setenv("RESTORE_RESOURCE_FIXTURE", str(ROOT / "tests/runtime_restore_fixture.py"))
    monkeypatch.setenv("TMPDIR", str(temporary))
    monkeypatch.setenv("PATH", str(binary) + os.pathsep + os.environ["PATH"])
    return state, trace, temporary


def test_promotes_only_verified_volumes_after_both_temporary_containers_are_removed(
    owned_resources: tuple[Path, Path, Path],
) -> None:
    state, trace, temporary = owned_resources
    result = run_owner()
    assert result.returncode == 0 and result.stdout == "passed\n", result.stderr
    document = json.loads(state.read_text())
    assert not document["containers"] and len(document["volumes"]) == 3
    assert {value["owner"] for value in document["volumes"].values()} != {"foreign"}
    assert not list(temporary.iterdir())
    calls = [json.loads(line) for line in trace.read_text().splitlines()]
    assert ["stop", "--time", "30", "a" * 64] in calls
    assert not any(call[:2] == ["volume", "rm"] for call in calls)
    assert sum(call[:2] == ["rm", "-f"] for call in calls) == 2


def test_failed_verification_rolls_back_only_exact_nonce_owned_resources(
    owned_resources: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    state, _, temporary = owned_resources
    monkeypatch.setenv("RESTORE_RESOURCE_ACTION", "fail")
    result = run_owner()
    assert result.returncode == 51 and "passed" not in result.stdout
    assert json.loads(state.read_text()) == {"containers": {}, "volumes": {}}
    assert not list(temporary.iterdir())


@pytest.mark.parametrize("mode", ["volume-collision", "container-collision", "volume-replaced"])
def test_foreign_name_collision_or_replacement_cannot_be_deleted_or_promoted(
    owned_resources: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    state, trace, _ = owned_resources
    monkeypatch.setenv("RESTORE_RESOURCE_MODE", mode)
    result = run_owner()
    assert result.returncode != 0 and "passed" not in result.stdout
    document = json.loads(state.read_text())
    foreign = [value for resources in document.values() for value in resources.values() if value["owner"] == "foreign"]
    assert foreign
    calls = [json.loads(line) for line in trace.read_text().splitlines()]
    for resource in foreign:
        assert ["rm", "-f", resource.get("id")] not in calls
        assert ["volume", "rm", resource["name"]] not in calls


@pytest.mark.parametrize("mode", ["volume-lost-reply", "container-lost-reply"])
def test_lost_create_reply_still_recovers_only_resources_with_the_private_owner_nonce(
    owned_resources: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    state, _, temporary = owned_resources
    monkeypatch.setenv("RESTORE_RESOURCE_MODE", mode)
    result = run_owner()
    assert result.returncode != 0 and "passed" not in result.stdout
    assert json.loads(state.read_text()) == {"containers": {}, "volumes": {}}
    assert not list(temporary.iterdir())


@pytest.mark.parametrize(
    "mode",
    ["daemon-error", "container-retained", "volume-retained", "container-identity-changed", "volume-identity-changed"],
)
def test_unconfirmed_cleanup_retains_evidence_and_cannot_report_passed(
    owned_resources: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    state, _, temporary = owned_resources
    monkeypatch.setenv("RESTORE_RESOURCE_MODE", mode)
    monkeypatch.setenv("RESTORE_RESOURCE_ACTION", "fail")
    result = run_owner()
    assert result.returncode != 0 and "passed" not in result.stdout
    assert "cleanup incomplete" in result.stderr
    assert list(temporary.iterdir()) and json.loads(state.read_text())["volumes"]


@pytest.mark.parametrize("mode", ["stop-failure", "probe-nonzero"])
def test_failed_graceful_shutdown_or_rls_exit_cannot_promote_data(
    owned_resources: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setenv("RESTORE_RESOURCE_MODE", mode)
    result = run_owner()
    assert result.returncode != 0 and "passed" not in result.stdout
    assert owned_resources[0].is_file()


@pytest.mark.parametrize("action", ["unexpected-file", "symlink-workspace"])
def test_workspace_cleanup_refuses_unknown_content_and_symlink_targets(
    owned_resources: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    _, _, temporary = owned_resources
    monkeypatch.setenv("RESTORE_RESOURCE_ACTION", action)
    result = run_owner()
    assert result.returncode != 0 and "passed" not in result.stdout
    assert "cleanup incomplete" in result.stderr
    assert list(temporary.iterdir())
    if action == "unexpected-file":
        assert list(temporary.glob("*/unknown.txt"))
    else:
        assert any(path.is_symlink() for path in temporary.iterdir())


@pytest.mark.parametrize(
    ("variable", "value"),
    [("RESTORE_RESOURCE_PROJECT", "online;true"), ("RESTORE_RESOURCE_SUFFIX", "1/2"), ("TMPDIR", "/")],
)
def test_unsafe_initial_identity_is_rejected_before_any_docker_call(
    owned_resources: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    _, trace, temporary = owned_resources
    monkeypatch.setenv(variable, value)
    result = run_owner()
    assert result.returncode == 2
    assert not trace.exists() and not list(temporary.iterdir())


@pytest.mark.parametrize("seconds", ["", "0", "-1", "901", "9000", "1s", "2;true"])
def test_operation_bounds_cannot_be_disabled_or_replaced_by_shell_input(
    owned_resources: tuple[Path, Path, Path], seconds: str
) -> None:
    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(  # noqa: S603 - Invalid arguments to the controlled function; no real engine.
        [
            bash,
            "-c",
            'set -Eeuo pipefail; source "$1"; runtime_restore_docker "$2" version',
            "bounds",
            str(LIBRARY),
            seconds,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 2
    assert not owned_resources[1].exists()
