"""Prove the actual shared coverage configuration measures child Python work."""

import json
import os
import subprocess
import sys
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _fixture(tmp_path: Path) -> Path:
    (tmp_path / "coverage_fixture.py").write_text(
        "def parent_only():\n    return 'parent'\n\ndef child_only():\n    return 'child'\n", encoding="utf-8"
    )
    test = tmp_path / "test_coverage_fixture.py"
    test.write_text(
        "import subprocess\nimport sys\nfrom coverage_fixture import parent_only\n\n"
        "def test_parent_and_child():\n"
        "    assert parent_only() == 'parent'\n"
        "    subprocess.run([sys.executable, '-c', "
        "\"from coverage_fixture import child_only; assert child_only() == 'child'\"], check=True)\n",
        encoding="utf-8",
    )
    return test


def _environment(tmp_path: Path) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith(("COV_CORE_", "COVERAGE_"))}
    environment.update(COVERAGE_FILE=str(tmp_path / ".coverage"), PYTHONPATH=str(tmp_path), PYTEST_ADDOPTS="")
    return environment


def test_shared_coverage_measures_and_combines_parent_and_child(tmp_path: Path) -> None:
    test = _fixture(tmp_path)
    report = tmp_path / "coverage.json"
    completed = subprocess.run(  # noqa: S603 - fixed interpreter, generated literal fixture and shared config only.
        [
            sys.executable,
            "-m",
            "pytest",
            str(test),
            "--noconftest",
            "-c",
            str(CONFIG),
            f"--cov-config={CONFIG}",
            "--cov=coverage_fixture",
            f"--cov-report=json:{report}",
            "--cov-fail-under=100",
            "-q",
        ],
        cwd=tmp_path,
        env=_environment(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    measurements = json.loads(report.read_text(encoding="utf-8"))["files"]
    assert len(measurements) == 1
    filename, measured = next(iter(measurements.items()))
    assert Path(filename).name == "coverage_fixture.py"
    assert measured["executed_lines"] == [1, 2, 4, 5]
    assert measured["missing_lines"] == []
    assert measured["summary"]["covered_lines"] == measured["summary"]["num_statements"] == 4
