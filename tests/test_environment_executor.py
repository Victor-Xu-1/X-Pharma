from __future__ import annotations

import fcntl
import hashlib
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pharma_intel.platform import environment_executor as executor
from pharma_intel.platform.environment_recipes import create_plan, manifest_digest, plan_digest
from tests.test_environment_plans import host_report

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in (
        "pyproject.toml",
        "uv.lock",
        "apps/web/package.json",
        "apps/web/pnpm-lock.yaml",
        "deploy/kubernetes/platform/versions.env",
        "scripts/bootstrap-wsl-tools.sh",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"packageManager":"pnpm@11.7.0"}' if name.endswith("package.json") else "fixture", encoding="utf-8"
        )
    monkeypatch.setattr(executor, "workspace_path", lambda path: path)
    monkeypatch.setattr(executor, "source_identity", lambda _root: ("a" * 40, True))
    return tmp_path


def plan_for(root: Path):
    host = host_report().model_copy(update={"manifest_sha256": manifest_digest(root)})
    return create_plan(host, recipe_id="frontend-dependencies", offline=True, package_manager="pnpm@11.7.0")


def test_valid_plan_and_changed_source_are_distinguished(source: Path) -> None:
    plan = plan_for(source)
    executor.validate_install_plan(source, plan)
    (source / "uv.lock").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="Source changed"):
        executor.validate_install_plan(source, plan)


def test_self_consistent_tampered_commands_still_cannot_execute(source: Path) -> None:
    plan = plan_for(source).model_copy(update={"commands": [["bash", "-c", "not-permitted"]]})
    plan = plan.model_copy(update={"plan_id": plan_digest(plan.model_dump(mode="json", exclude={"plan_id"}))})
    with pytest.raises(ValueError, match="allowlisted"):
        executor.validate_install_plan(source, plan)
    with pytest.raises(ValueError, match="approved"):
        executor.run_install_command(["bash", "-c", "not-permitted"], source, {}, source / "log")


def test_expired_plan_is_rejected_without_starting_a_process(source: Path) -> None:
    plan = plan_for(source).model_copy(update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)})
    with pytest.raises(ValueError, match="expired"):
        executor.validate_install_plan(source, plan)


def test_execution_records_failure_and_refuses_replay(source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(executor, "run_install_command", lambda *_args: 23)
    plan = plan_for(source)
    state = source / "state"
    result = executor.execute_install_plan(source, plan, state)
    assert result.status == "failed" and result.exit_code == 23
    assert result.finished_at is not None
    assert json.loads((state / "latest-install.json").read_text())["status"] == "failed"
    with pytest.raises(ValueError, match="already executed"):
        executor.execute_install_plan(source, plan, state)


def test_interrupted_installation_is_not_reported_as_running_forever(source: Path) -> None:
    from pharma_intel.schemas.environment import EnvironmentInstallResultRead

    state = source / "state"
    state.mkdir()
    running = EnvironmentInstallResultRead(
        recipe_id="deployment-tools",
        plan_id="a" * 64,
        status="running",
        started_at=datetime.now(UTC),
        detail="Installation started",
    )
    executor.write_install_state(state / "latest-install.json", running)
    observed = executor.read_install_result(state)
    assert observed is not None and observed.status == "failed"
    assert "interrupted" in observed.detail
    assert json.loads((state / "latest-install.json").read_text())["status"] == "running"
    with (state / "installation.lock").open("wb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = executor.read_install_result(state)
        assert active is not None and active.status == "running"


def test_installer_inherits_lock_until_its_process_exits(source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, object] = {}

    def capture_process(*_args: object, **kwargs: object) -> None:
        observed.update(kwargs)
        raise OSError("process fixture")

    monkeypatch.setattr(executor.subprocess, "Popen", capture_process)
    with (source / "installation.lock").open("wb") as lock:
        with pytest.raises(OSError, match="process fixture"):
            executor.run_install_command(
                ["bash", "scripts/bootstrap-wsl-tools.sh"], source, {}, source / "log", lock.fileno()
            )
        assert observed["pass_fds"] == (lock.fileno(),)


def offline_tool_fixture(tmp_path: Path) -> tuple[Path, dict[str, str], str]:
    root = tmp_path / "root"
    (root / "scripts").mkdir(parents=True)
    (root / "deploy/kubernetes/platform").mkdir(parents=True)
    (root / "scripts/bootstrap-wsl-tools.sh").write_bytes((ROOT / "scripts/bootstrap-wsl-tools.sh").read_bytes())
    artifact = b'#!/bin/sh\nprintf \'{"clientVersion":{"gitVersion":"v1.35.0"}}\\n\'\n'
    digest = hashlib.sha256(artifact).hexdigest()
    (root / "deploy/kubernetes/platform/versions.env").write_text(
        f"KUBERNETES_VALIDATION_VERSION=1.35.0\nKUBECTL_LINUX_AMD64_SHA256={digest}\n", encoding="ascii"
    )
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / f"{digest}.kubectl").write_bytes(artifact)
    (cache / f"{digest}.kubectl").chmod(0o700)
    import os

    environment = {
        **os.environ,
        "PHARMA_WSL_OFFLINE": "true",
        "PHARMA_WSL_BIN_DIR": str(tmp_path / "bin"),
        "PHARMA_WSL_ARTIFACT_CACHE": str(cache),
    }
    return root, environment, digest


def test_offline_installer_uses_the_verified_cached_artifact(tmp_path: Path) -> None:
    root, environment, digest = offline_tool_fixture(tmp_path)
    result = subprocess.run(
        ["/bin/bash", "scripts/bootstrap-wsl-tools.sh"],
        cwd=root,
        env=environment,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    installed = tmp_path / "bin/kubectl"
    assert hashlib.sha256(installed.read_bytes()).hexdigest() == digest
    assert b"verified cached" in result.stdout


def test_offline_installer_rejects_corruption_without_overwriting_it(tmp_path: Path) -> None:
    root, environment, digest = offline_tool_fixture(tmp_path)
    cached = tmp_path / f"cache/{digest}.kubectl"
    cached.write_bytes(b"corrupt")
    result = subprocess.run(
        ["/bin/bash", "scripts/bootstrap-wsl-tools.sh"],
        cwd=root,
        env=environment,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert b"failed pinned digest" in result.stderr
    assert cached.read_bytes() == b"corrupt"
    assert not (tmp_path / "bin/kubectl").exists()


def test_offline_installer_never_downloads_a_missing_artifact(tmp_path: Path) -> None:
    root, environment, digest = offline_tool_fixture(tmp_path)
    (tmp_path / f"cache/{digest}.kubectl").unlink()
    result = subprocess.run(
        ["/bin/bash", "scripts/bootstrap-wsl-tools.sh"],
        cwd=root,
        env=environment,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert b"no network download was attempted" in result.stderr
    assert not (tmp_path / "bin/kubectl").exists()
