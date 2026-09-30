from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.verify_clean_source import (
    CleanSourceError,
    Tooling,
    _command_plan,
    _package_manager,
    _sanitized_environment,
    _validate_source_hygiene,
    _write_report,
)


def test_clean_source_plan_covers_locked_install_test_build_and_migration_rollback() -> None:
    tooling = Tooling(corepack="/tools/corepack", docker="/tools/docker", make="/tools/make", uv="/tools/uv")
    plan = _command_plan(
        tooling,
        "pnpm@11.7.0",
        "pharma-clean-source:commit-pid",
        migration_env_file=".migration.env",
        migration_port=35432,
    )

    assert [item.label for item in plan] == [
        "locked Python installation",
        "locked frontend installation",
        "quality, tests, build and manifest rendering",
        "PostgreSQL migration upgrade and rollback",
        "production application image build",
        "non-root runtime image smoke",
    ]
    assert plan[0].command == ("/tools/uv", "sync", "--locked", "--dev")
    assert "--frozen-lockfile" in plan[1].command
    assert plan[2].command == ("/tools/make", "check")
    assert plan[3].command == (
        "/tools/uv",
        "run",
        "python",
        "scripts/verify_postgres_migration_roundtrip.py",
        "--env-file",
        ".migration.env",
        "--port",
        "35432",
    )
    assert plan[4].command[-1] == "."
    assert plan[5].command[-3:-1] == ("python", "-c")
    assert "os.getuid() == 10001" in plan[5].command[-1]
    assert "'/health/live'" in plan[5].command[-1]
    assert all(item.timeout_seconds > 0 for item in plan)


def test_clean_source_requires_an_exact_pnpm_contract(tmp_path: Path) -> None:
    package_directory = tmp_path / "apps/web"
    package_directory.mkdir(parents=True)
    package = package_directory / "package.json"
    package.write_text(json.dumps({"packageManager": "pnpm@11.7.0"}), encoding="utf-8")

    assert _package_manager(tmp_path) == "pnpm@11.7.0"

    package.write_text(json.dumps({"packageManager": "pnpm@latest"}), encoding="utf-8")
    with pytest.raises(CleanSourceError, match="exact pnpm"):
        _package_manager(tmp_path)


def test_clean_source_environment_drops_credentials_and_parent_project_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "DATABASE_URL",
        "NODE_OPTIONS",
        "NODE_PATH",
        "PYTHONHOME",
        "PYTHONPATH",
        "TEST_MCP_ACCESS_TOKEN",
        "UV_PROJECT_ENVIRONMENT",
        "VIRTUAL_ENV",
    ):
        monkeypatch.setenv(name, "must-not-propagate")

    environment = _sanitized_environment()

    assert all(name not in environment for name in ("DATABASE_URL", "TEST_MCP_ACCESS_TOKEN", "VIRTUAL_ENV"))
    assert environment["CI"] == "true"
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"


def test_clean_source_report_is_private_atomic_and_non_overwriting(tmp_path: Path) -> None:
    output = tmp_path / "evidence" / "report.json"
    _write_report(output, {"status": "passed"})

    assert json.loads(output.read_text(encoding="utf-8")) == {"status": "passed"}
    assert output.stat().st_mode & 0o777 == 0o600
    assert not list(output.parent.glob("*.tmp"))
    with pytest.raises(CleanSourceError, match="refusing to overwrite"):
        _write_report(output, {"status": "changed"})


def test_clean_source_cli_help_runs_directly() -> None:
    root = Path(__file__).parents[1]
    completed = subprocess.run(  # noqa: S603 - interpreter and repository script are controlled.
        [sys.executable, "scripts/verify_clean_source.py", "--help"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "committed source only" in " ".join(completed.stdout.split())


@pytest.mark.parametrize(
    ("relative_path", "content", "message"),
    [
        (
            "docs/local.md",
            "cd " + "/".join(("", "home", "alice", "pharma-intelligence-platform")) + "\n",
            "personal platform path",
        ),
        (
            "docs/windows.md",
            "\\".join(("C:", "Users", "Alice", "work", "pharma-intelligence-runtime", "evidence")) + "\n",
            "personal platform path",
        ),
        (
            "manifests/acceptance/stale.json",
            "{}\n",
            "historical runtime evidence",
        ),
        (
            "apps/web/dist/index.html",
            "generated\n",
            "generated local state",
        ),
    ],
)
def test_clean_source_rejects_nonportable_or_generated_committed_state(
    tmp_path: Path,
    relative_path: str,
    content: str,
    message: str,
) -> None:
    source = tmp_path / "source"
    candidate = source / relative_path
    candidate.parent.mkdir(parents=True)
    candidate.write_text(content, encoding="utf-8")

    with pytest.raises(CleanSourceError, match=message):
        _validate_source_hygiene(source)


def test_clean_source_hygiene_accepts_portable_runtime_variables(tmp_path: Path) -> None:
    source = tmp_path / "source"
    document = source / "docs" / "operations.md"
    document.parent.mkdir(parents=True)
    document.write_text(
        'PHARMA_REPO="${PHARMA_REPO:-$HOME/pharma-intelligence-platform}"\n',
        encoding="utf-8",
    )

    _validate_source_hygiene(source)
