from __future__ import annotations

import ast
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("environment", ["development", "production"])
def test_preflight_executes_the_actual_python_payload_without_docker(environment: str) -> None:
    command = next(
        line.strip()
        for line in (ROOT / "scripts/lib/browser_projection_mode.sh").read_text().splitlines()
        if "docker compose exec -T api python3" in line
    )
    arguments = shlex.split(command)
    assert arguments[:7] == ["docker", "compose", "exec", "-T", "api", "python3", "-c"]
    assert len(arguments) == 8, "python -c must receive the actual guard, not an accidental extra argument"
    payload = arguments[7]
    ast.parse(payload)
    fixture = (
        "import sys, types; "
        "config = types.ModuleType('pharma_intel.config'); "
        f"config.get_settings = lambda: types.SimpleNamespace(app_env={environment!r}); "
        "sys.modules['pharma_intel.config'] = config; "
        f"exec({payload!r})"
    )
    result = subprocess.run(  # noqa: S603 - executes only the checked repository guard with an isolated settings fixture.
        [sys.executable, "-c", fixture],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if environment == "production":
        assert result.returncode != 0
        assert "cannot run against production" in result.stderr
    else:
        assert result.returncode == 0, result.stderr


def test_api_acceptance_mode_has_a_strict_false_default() -> None:
    import yaml

    document = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    expected = "${SEARCH_ALLOW_NON_AUTHORITATIVE_PROJECTION:-false}"
    assert document["services"]["api"]["environment"].get("SEARCH_ALLOW_NON_AUTHORITATIVE_PROJECTION") == expected


def test_browser_driver_switches_api_before_temporary_aliases_and_restores_both_services() -> None:
    script = (ROOT / "scripts/run-browser-acceptance.sh").read_text(encoding="utf-8")
    assert 'source "$ROOT_DIR/scripts/lib/browser_projection_mode.sh"' in script
    assert script.index("assert_browser_projection_environment") < script.index("tenant_record=$(")
    assert script.index("enter_browser_projection_mode") < script.index('--build-id "browser-$run_id"')
    assert 'restore_browser_projection_runtime "$run_id"' in script


@pytest.mark.parametrize("scenario", ["enter", "restore", "rebuild-fails", "production"])
def test_projection_mode_switch_is_scoped_and_restores_strictness(tmp_path: Path, scenario: str) -> None:
    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(  # noqa: S603 - only isolated shell functions emulate Docker; no daemon is used.
        [
            bash,
            "-c",
            """
set -euo pipefail
source "$HELPER"
docker() {
  printf '%s|%s\n' "${SEARCH_ALLOW_NON_AUTHORITATIVE_PROJECTION:-unset}" "$*" >> "$STATE"
  if [[ "$*" == *"exec -T api python3"* && "$SCENARIO" == production ]]; then return 2; fi
  if [[ "$*" == *"run --rm --no-deps worker pharma-search rebuild"* && "$SCENARIO" == rebuild-fails ]]; then
    return 1
  fi
  if [[ "$*" == "compose ps -q api" ]]; then printf '%s\n' owned-api; fi
}
wait_for_browser_container_healthy() { printf 'health|%s\n' "$*" >> "$STATE"; }
wait_for_worker_healthy() { printf 'health|worker\n' >> "$STATE"; }
case "$SCENARIO" in
  enter) enter_browser_projection_mode ;;
  production) assert_browser_projection_environment ;;
  *) restore_browser_projection_runtime 20261010120000-12345 ;;
esac
""",
        ],
        cwd=ROOT,
        env={
            **os.environ,
            "HELPER": str(ROOT / "scripts/lib/browser_projection_mode.sh"),
            "STATE": str(tmp_path / "mode.log"),
            "SCENARIO": scenario,
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    log = (tmp_path / "mode.log").read_text(encoding="utf-8")
    if scenario == "enter":
        assert result.returncode == 0, result.stderr
        assert "true|compose up -d --no-deps --force-recreate api" in log
        assert "worker" not in log
        assert "health|owned-api api 30" in log
    elif scenario == "production":
        assert result.returncode != 0
        assert "compose up" not in log
    else:
        assert "false|compose up -d --no-deps --force-recreate api worker" in log
        assert (result.returncode == 0) == (scenario == "restore")
        if scenario == "rebuild-fails":
            assert "health|" not in log
