from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _bash(helper: str, script: str, tmp_path: Path, **values: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("bash")
    assert executable is not None
    root = Path(__file__).parents[1]
    return subprocess.run(  # noqa: S603 - fixed repository helpers; external font/daemon metadata is controlled.
        [executable, "-c", script],
        cwd=root,
        env={**os.environ, "HELPER": str(root / helper), "STATE": str(tmp_path / "state"), **values},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


@pytest.mark.parametrize("profile", ["expected", "fallback"])
def test_browser_font_profile_does_not_silently_capture_fallback_typefaces(tmp_path: Path, profile: str) -> None:
    result = _bash(
        "scripts/lib/browser_fonts.sh",
        """
set -euo pipefail
source "$HELPER"
fc-match() {
  if [[ "$PROFILE" == expected ]]; then printf '%s' "$2";
  else printf '%s' 'Liberation Sans'; fi
}
verify_browser_fonts
""",
        tmp_path,
        PROFILE=profile,
    )
    if profile == "expected":
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode == 1
        assert "Required browser font is missing" in result.stderr
        assert "fonts-noto-cjk=1:20230817+repack1-3" in result.stderr


@pytest.mark.parametrize("mode", ["recover", "stopped", "never-ready", "daemon-hangs", "invalid-budget"])
def test_browser_health_wait_requires_real_healthy_state_with_a_bounded_deadline(tmp_path: Path, mode: str) -> None:
    binaries = tmp_path / "bin"
    binaries.mkdir()
    docker = binaries / "docker"
    docker.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$MODE" == daemon-hangs ]]; then exec sleep 30;
elif [[ "$MODE" == stopped ]]; then printf '%s' 'false unhealthy';
elif [[ "$MODE" == never-ready ]]; then printf '%s' 'true unhealthy';
elif [[ -f "$STATE" ]]; then printf '%s' 'true healthy';
else touch "$STATE"; printf '%s' 'true unhealthy'; fi
"""
    )
    docker.chmod(0o700)
    result = _bash(
        "scripts/lib/browser_runtime_health.sh",
        """
set -euo pipefail
source "$HELPER"
if [[ "$MODE" == invalid-budget ]]; then budget=0;
elif [[ "$MODE" == recover ]]; then budget=5;
else budget=1; fi
wait_for_browser_container_healthy task-owned-api api "$budget"
""",
        tmp_path,
        MODE=mode,
        PATH=f"{binaries}{os.pathsep}{os.environ['PATH']}",
    )
    if mode == "recover":
        assert result.returncode == 0, result.stderr
    elif mode == "invalid-budget":
        assert result.returncode == 2
    else:
        assert result.returncode == 1
        assert "did not become healthy" in result.stderr


def test_real_browser_entry_loads_helpers_before_crossing_the_docker_boundary(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    binaries = tmp_path / "bin"
    binaries.mkdir()
    scripts = {
        "fc-match": '#!/usr/bin/env bash\nprintf "%s" "$2"\n',
        "docker": '#!/usr/bin/env bash\nprintf "owned docker boundary reached\\n" >&2\nexit 73\n',
        "test-chrome": '#!/usr/bin/env bash\nprintf "%s\\n" "'
        + json.loads((root / "apps/web/e2e/visual-baselines/manifest.json").read_text(encoding="utf-8"))["browser"]
        + '"\n',
    }
    for name, body in scripts.items():
        executable = binaries / name
        executable.write_text(body)
        executable.chmod(0o700)
    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(  # noqa: S603 - fixed production entry; only Docker/font boundaries are fixtures.
        [bash, str(root / "scripts/run-browser-acceptance.sh")],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{binaries}{os.pathsep}{os.environ['PATH']}",
            "COMPOSE_FILE": "owned-fixture",
            "E2E_BROWSER_EXECUTABLE": str(binaries / "test-chrome"),
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 73, result.stderr
    assert "owned docker boundary reached" in result.stderr
    assert "unbound variable" not in result.stderr
