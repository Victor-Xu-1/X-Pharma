from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from pharma_intel.platform.environment_recipes import manifest_digest, pnpm_release
from pharma_intel.schemas.environment import (
    EnvironmentInstallResultRead,
    EnvironmentProbeRead,
    EnvironmentProbeStatus,
    HostEnvironmentRead,
)


def workspace_path(path: Path) -> Path:
    expanded = path.expanduser().absolute()
    if any(candidate.is_symlink() for candidate in (expanded, *expanded.parents)):
        raise ValueError("Managed workspace paths cannot traverse symbolic links")
    resolved = expanded.resolve()
    if not resolved.is_relative_to(Path("/srv/wsl")) or resolved == Path("/srv/wsl"):
        raise ValueError("Environment management only operates inside the approved /srv/wsl workspace")
    return resolved


def command_output(command: list[str], *, cwd: Path | None = None) -> str | None:
    probes = (
        ["git", "rev-parse", "HEAD"],
        ["git", "status", "--porcelain"],
        ["python3", "--version"],
        ["uv", "--version"],
        ["node", "--version"],
        ["corepack", "--version"],
        ["pnpm", "--version"],
        ["docker", "version", "--format", "{{.Server.Version}}"],
        ["docker", "compose", "version", "--short"],
        ["kubectl", "version", "--client", "-o", "json"],
    )
    cached_pnpm_probe = (
        len(command) == 3
        and command[0] == "corepack"
        and bool(re.fullmatch(r"pnpm@\d+\.\d+\.\d+", command[1]))
        and command[2] == "--version"
    )
    if command not in probes and not cached_pnpm_probe:
        raise ValueError("Only predefined read-only version and source probes are accepted")
    try:
        environment = {**os.environ, "COREPACK_ENABLE_NETWORK": "0", "COREPACK_ENABLE_AUTO_PIN": "0"}
        # The complete argv is matched above; no caller-supplied flags or shell expansion are accepted.
        result = subprocess.run(command, cwd=cwd, capture_output=True, timeout=5, check=False, env=environment)  # noqa: S603
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode or len(result.stdout) > 64 * 1024:
        return None
    return result.stdout.decode("utf-8", "replace").strip()


def source_identity(root: Path) -> tuple[str, bool]:
    revision = command_output(["git", "rev-parse", "HEAD"], cwd=root)
    state = command_output(["git", "status", "--porcelain"], cwd=root)
    if revision is None or not re.fullmatch(r"[0-9a-f]{40}", revision) or state is None:
        raise ValueError("An identifiable Git source checkout is required")
    return revision, state == ""


def detect_host(root: Path, *, latest_install: EnvironmentInstallResultRead | None = None) -> HostEnvironmentRead:
    root = workspace_path(root)
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    manager = pnpm_release(root)
    revision, clean = source_identity(root)
    probes = [
        EnvironmentProbeRead(
            id="operating-system",
            label="操作系统",
            scope="host",
            status="present" if platform.system() == "Linux" else "blocked",
            observed=platform.system(),
            expected="Linux",
            detail="检测实际主机，不使用网关容器版本代替。",
        )
    ]
    declarations = (
        ("python", "Python", ["python3", "--version"], None),
        ("uv", "uv", ["uv", "--version"], None),
        ("node", "Node.js", ["node", "--version"], None),
        ("corepack", "Corepack", ["corepack", "--version"], None),
        ("pnpm", "pnpm（项目缓存版本）", ["corepack", manager, "--version"], manager),
        ("docker", "Docker Engine", ["docker", "version", "--format", "{{.Server.Version}}"], None),
        ("compose", "Docker Compose", ["docker", "compose", "version", "--short"], None),
        ("kubectl", "kubectl", ["kubectl", "version", "--client", "-o", "json"], None),
    )
    for key, label, command, expected in declarations:
        executable = shutil.which(command[0])
        observed = command_output(command) if executable else None
        state: EnvironmentProbeStatus = "present" if observed else "blocked" if executable else "missing"
        if key == "kubectl" and observed:
            try:
                observed = str(json.loads(observed)["clientVersion"]["gitVersion"])
            except (ValueError, KeyError, TypeError):
                observed, state = None, "blocked"
        if key == "pnpm" and observed and observed != manager.removeprefix("pnpm@"):
            state = "mismatch"
        probes.append(
            EnvironmentProbeRead(
                id=key,
                label=label,
                scope="host",
                status=state,
                observed=observed[:160] if observed else None,
                expected=expected,
                detail="只读版本检查；缺失或超时不会触发自动下载安装。",
            )
        )
    disk = shutil.disk_usage(root)
    return HostEnvironmentRead(
        generated_at=datetime.now(UTC),
        product_version=version,
        revision=revision,
        clean_source=clean,
        manifest_sha256=manifest_digest(root),
        probes=probes,
        disk_free_bytes=disk.free,
        disk_total_bytes=disk.total,
        latest_install=latest_install,
    )
