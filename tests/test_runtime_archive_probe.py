from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fixture_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    """Exercise the probe with real tar but controlled transport/identity, not Docker."""
    root = tmp_path / "source"
    scripts = root / "scripts"
    (scripts / "lib").mkdir(parents=True)
    script = scripts / "verify-runtime-archive.sh"
    shutil.copyfile(ROOT / "scripts/verify-runtime-archive.sh", script)
    (scripts / "lib/runtime_archive_container.sh").write_text(
        'source "$ARCHIVE_TEST_LIBRARY"\n'
        "run_runtime_archive() {\n"
        '  case "$1" in\n'
        '    *-write) tar -C "$work/input" -czf - probe.bin ;;\n'
        '    *-list) tar -tzf "$work/archive.tar.gz" ;;\n'
        "    *-extract)\n"
        "      [[ ${ARCHIVE_TEST_FAILURE:-} != extract ]] || return 71\n"
        '      tar -xzf "$work/archive.tar.gz" -C "$work/output"\n'
        '      if [[ ${ARCHIVE_TEST_FAILURE:-} == cleanup ]]; then touch "$work/output/unexpected"; fi ;;\n'
        "    *) return 72 ;;\n"
        "  esac\n"
        "}\n",
        encoding="utf-8",
    )
    binaries = tmp_path / "bin"
    binaries.mkdir()
    trace = tmp_path / "docker.trace"
    for name, body in {
        "docker": 'printf "%s\\n" "$*" >> "$ARCHIVE_TEST_TRACE"\n[[ $1:$2 == image:inspect ]]\n',
        "git": '[[ $1 == -C && $3 == rev-parse && $4 == HEAD ]]\nprintf "%040d\\n" 1\n',
    }.items():
        executable = binaries / name
        executable.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body, encoding="utf-8")
        executable.chmod(0o755)
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    monkeypatch.setenv("PATH", str(binaries) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("TMPDIR", str(temporary))
    monkeypatch.setenv("ARCHIVE_TEST_LIBRARY", str(ROOT / "scripts/lib/runtime_archive_container.sh"))
    monkeypatch.setenv("ARCHIVE_TEST_TRACE", str(trace))
    return script, temporary, trace


def _run(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash is not None
    return subprocess.run(  # noqa: S603 - Only the owned probe and controlled fixtures are executed.
        [bash, str(script), *arguments], capture_output=True, text=True, check=False, timeout=10
    )


@pytest.mark.parametrize(("argument", "code"), [("--help", 0), ("--unknown", 2)])
def test_probe_help_and_invalid_arguments_never_touch_docker(
    fixture_probe: tuple[Path, Path, Path], argument: str, code: int
) -> None:
    script, temporary, trace = fixture_probe
    result = _run(script, argument)
    assert result.returncode == code
    assert not trace.exists() and not list(temporary.iterdir())


def test_probe_publishes_only_after_binary_round_trip_and_fixture_cleanup(
    fixture_probe: tuple[Path, Path, Path],
) -> None:
    script, temporary, trace = fixture_probe
    result = _run(script)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["schema"] == "x-pharma.runtime-archive-contract.v1"
    assert report["status"] == "passed" and report["cleanup_verified"] is True
    assert report["fixture_only"] is True and report["archive_operations"] == 3
    assert report["revision"] == "0" * 39 + "1"
    assert report["image"].startswith("busybox:1.36.1@sha256:")
    assert trace.read_text().count("image inspect ") == 1
    assert not list(temporary.iterdir())


@pytest.mark.parametrize("failure", ["extract", "cleanup"])
def test_probe_failure_retains_only_its_fixture_and_never_publishes_passed(
    fixture_probe: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    script, temporary, _ = fixture_probe
    monkeypatch.setenv("ARCHIVE_TEST_FAILURE", failure)
    result = _run(script)
    assert result.returncode != 0 and not result.stdout
    assert "retained fixture=" in result.stderr
    retained = list(temporary.iterdir())
    assert len(retained) == 1 and retained[0].name.startswith("pharma-archive-contract.")
    if failure == "cleanup":
        assert (retained[0] / "output/unexpected").is_file()
