from __future__ import annotations

import fcntl
import os
import selectors
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from pharma_intel import __version__
from pharma_intel.platform.environment_host import source_identity, workspace_path
from pharma_intel.platform.environment_recipes import (
    RECIPES,
    manifest_digest,
    plan_digest,
    pnpm_release,
    recipe_commands,
)
from pharma_intel.schemas.environment import EnvironmentInstallPlanRead, EnvironmentInstallResultRead

MAX_LOG_BYTES = 1024 * 1024
INSTALL_SECONDS = 600


def validate_install_plan(root: Path, plan: EnvironmentInstallPlanRead, *, now: datetime | None = None) -> None:
    workspace_path(root)
    at = now or datetime.now(UTC)
    if plan.generated_at.tzinfo is None or plan.expires_at.tzinfo is None:
        raise ValueError("Installation plan times must include a timezone")
    if (
        plan.generated_at > at
        or plan.expires_at <= at
        or (plan.expires_at - plan.generated_at).total_seconds() > 86_400
    ):
        raise ValueError("Installation plan is expired or has invalid bounds")
    if plan.product_version != __version__ or plan.plan_id != plan_digest(
        plan.model_dump(mode="json", exclude={"plan_id"})
    ):
        raise ValueError("Installation plan identity or checksum is invalid")
    revision, clean = source_identity(root)
    if not clean or revision != plan.revision or manifest_digest(root) != plan.manifest_sha256:
        raise ValueError("Source changed since detection; regenerate the plan from clean source")
    expected = recipe_commands(plan.recipe_id, offline=plan.offline, package_manager=pnpm_release(root))
    if plan.commands != expected:
        raise ValueError("Commands differ from the allowlisted recipe")


def write_install_state(path: Path, result: EnvironmentInstallResultRead) -> None:
    temporary = path.with_suffix(".partial")
    if path.is_symlink() or temporary.is_symlink():
        raise ValueError("Installation state cannot be a symbolic link")
    if path.exists():
        if path.stat().st_size > 256 * 1024:
            raise ValueError("An unrelated installation output was preserved")
        EnvironmentInstallResultRead.model_validate_json(path.read_bytes())
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(result.model_dump_json(indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def read_install_result(state_root: Path) -> EnvironmentInstallResultRead | None:
    state_root = workspace_path(state_root)
    path = state_root / "latest-install.json"
    if path.is_symlink():
        raise ValueError("Installation state cannot be a symbolic link")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 256 * 1024:
        raise ValueError("Invalid installation state was preserved")
    result = EnvironmentInstallResultRead.model_validate_json(path.read_bytes())
    if result.status != "running":
        return result
    lock_path = state_root / "installation.lock"
    try:
        descriptor = os.open(lock_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        descriptor = None
    if descriptor is not None:
        with os.fdopen(descriptor, "rb") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return result
    # Inspection does not rewrite the original journal or pretend interrupted work completed.
    return result.model_copy(
        update={
            "status": "failed",
            "detail": (
                "Installation was interrupted; no active installer holds the lock. "
                "Review private logs before a new plan."
            ),
        }
    )


def terminate_install(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    except ProcessLookupError:
        process.wait(timeout=5)


def run_install_command(
    command: list[str], root: Path, environment: dict[str, str], log_path: Path, lock_descriptor: int | None = None
) -> int:
    manager = pnpm_release(root)
    allowed = [
        argv
        for recipe in RECIPES
        for offline in (False, True)
        for argv in recipe_commands(recipe.id, offline=offline, package_manager=manager)
    ]
    if command not in allowed:
        raise ValueError("Command does not match any approved installation recipe")
    # Complete argv is independently allowlisted; no shell, arbitrary flags or external commands are accepted.
    process = subprocess.Popen(  # noqa: S603
        command,
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        pass_fds=(lock_descriptor,) if lock_descriptor is not None else (),
    )
    if process.stdout is None:
        terminate_install(process)
        raise ValueError("Installer output channel is unavailable")
    deadline, written = time.monotonic() + INSTALL_SECONDS, 0
    try:
        with selectors.DefaultSelector() as selector, log_path.open("xb") as log:
            log_path.chmod(0o600)
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                if time.monotonic() > deadline:
                    raise ValueError("Installation timed out; its process group was stopped")
                for key, _ in selector.select(timeout=0.5):
                    chunk = os.read(key.fd, 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    written += len(chunk)
                    if written > MAX_LOG_BYTES:
                        raise ValueError("Installation exceeded its bounded log budget")
                    log.write(chunk)
            return process.wait(timeout=max(1, deadline - time.monotonic()))
    finally:
        terminate_install(process)
        process.stdout.close()


def execute_install_plan(
    root: Path, plan: EnvironmentInstallPlanRead, state_root: Path
) -> EnvironmentInstallResultRead:
    root, state_root = workspace_path(root), workspace_path(state_root)
    validate_install_plan(root, plan)
    for managed_path in (
        "/srv/wsl/tmp",
        "/srv/wsl/cache/uv",
        "/srv/wsl/cache/npm",
        "/srv/wsl/cache/x-pharma/corepack",
        "/srv/wsl/envs/x-pharma-tools/bin",
        "/srv/wsl/envs/x-pharma-environment/bin",
        "/srv/wsl/cache/x-pharma/environment/artifacts",
    ):
        workspace_path(Path(managed_path))
    state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = state_root / "installation.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "wb") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another installation is active; no competing operation was started") from exc
        validate_install_plan(root, plan)
        job = state_root / plan.plan_id
        if job.exists():
            raise ValueError("This installation plan was already executed; generate a new plan instead of replaying it")
        job.mkdir(mode=0o700)
        result = EnvironmentInstallResultRead(
            recipe_id=plan.recipe_id,
            plan_id=plan.plan_id,
            revision=plan.revision,
            manifest_sha256=plan.manifest_sha256,
            status="running",
            started_at=datetime.now(UTC),
            detail="Host-side allowlisted installation started",
        )
        state_file = state_root / "latest-install.json"
        write_install_state(state_file, result)
        environment = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR"}
        }
        environment.update(
            TMPDIR="/srv/wsl/tmp",
            UV_CACHE_DIR="/srv/wsl/cache/uv",
            UV_PYTHON_DOWNLOADS="never",
            npm_config_cache="/srv/wsl/cache/npm",
            XDG_CACHE_HOME="/srv/wsl/cache/x-pharma",
            PNPM_HOME="/srv/wsl/envs/x-pharma-tools/bin",
            COREPACK_HOME="/srv/wsl/cache/x-pharma/corepack",
            COREPACK_ENABLE_NETWORK="0" if plan.offline else "1",
            COREPACK_ENABLE_AUTO_PIN="0",
            PHARMA_WSL_BIN_DIR="/srv/wsl/envs/x-pharma-environment/bin",
            PHARMA_WSL_ARTIFACT_CACHE="/srv/wsl/cache/x-pharma/environment/artifacts",
            PHARMA_WSL_OFFLINE="true" if plan.offline else "false",
        )
        try:
            for index, command in enumerate(plan.commands):
                code = run_install_command(command, root, environment, job / f"step-{index + 1}.log", lock.fileno())
                if code:
                    result = result.model_copy(
                        update={
                            "status": "failed",
                            "exit_code": code,
                            "detail": "Installer failed; review the private host-side step log",
                        }
                    )
                    break
            else:
                result = result.model_copy(
                    update={
                        "status": "succeeded",
                        "exit_code": 0,
                        "detail": "Allowlisted installation completed; run host detection again to confirm versions",
                    }
                )
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            result = result.model_copy(
                update={
                    "status": "failed",
                    "exit_code": None,
                    "detail": str(exc)[:500]
                    if isinstance(exc, ValueError)
                    else "Installer could not execute; review host-side diagnostics",
                }
            )
        result = result.model_copy(update={"finished_at": datetime.now(UTC)})
        write_install_state(state_file, result)
        write_install_state(job / "result.json", result)
        return result
