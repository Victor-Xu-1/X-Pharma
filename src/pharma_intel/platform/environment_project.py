from __future__ import annotations

import json
import os
import subprocess
import tomllib
from pathlib import Path

from pharma_intel.platform.environment_compatibility import (
    dependency_mismatches,
    pinned_dependencies,
    version_state,
    versions_equal,
)
from pharma_intel.schemas.environment import EnvironmentProbeRead

_INTERPRETER_PROBE = (
    "import importlib.metadata as m,json,platform; "
    "print(json.dumps({'python':platform.python_version(),"
    "'packages':{d.metadata['Name']:d.version for d in m.distributions() if d.metadata['Name']}}))"
)


def project_python_probe(root: Path) -> dict[str, object] | None:
    executable = root / ".venv/bin/python"
    if (root / ".venv").is_symlink() or not executable.is_file():
        return None
    # A venv legitimately links to its installed WSL interpreter. Reject mounted Windows
    # targets, but do not misreport a Linux-root interpreter as a missing venv.
    if executable.resolve().is_relative_to(Path("/mnt")):
        return None
    try:
        # Fixed code and project-owned interpreter only. No shell, installer or network operation.
        result = subprocess.run(  # noqa: S603
            [str(executable), "-I", "-c", _INTERPRETER_PROBE],
            cwd=root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=5,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if result.returncode or len(result.stdout) > 64 * 1024:
            return None
        payload = json.loads(result.stdout)
        return payload if isinstance(payload, dict) else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def project_dependency_probes(root: Path) -> list[EnvironmentProbeRead]:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    expected = pinned_dependencies(project["dependencies"])
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    locked = {package["name"]: package["version"] for package in lock["package"]}
    lock_errors = dependency_mismatches(expected, locked)
    payload = project_python_probe(root)
    observed_python = payload.get("python") if payload else None
    installed = payload.get("packages") if payload else None
    mismatches = dependency_mismatches(expected, installed) if isinstance(installed, dict) else list(expected)
    probes = [
        EnvironmentProbeRead(
            id="project-python",
            label="项目 .venv 解释器",
            scope="host",
            status=version_state(
                observed_python if isinstance(observed_python, str) else None, project["requires-python"]
            ),
            observed=observed_python if isinstance(observed_python, str) else None,
            expected=project["requires-python"],
            detail="读取当前项目 .venv 的解释器，不用系统 python3 代替。",
        ),
        EnvironmentProbeRead(
            id="python-lock",
            label="Python 锁定依赖",
            scope="host",
            status="mismatch" if lock_errors or mismatches else "present",
            observed=f"{len(expected) - len(mismatches)}/{len(expected)} 项直接依赖匹配",
            expected="pyproject.toml 与 uv.lock 的 Linux 直接依赖一致",
            detail=("缺失或不匹配：" + ", ".join(sorted(set(lock_errors + mismatches))[:8]))
            if lock_errors or mismatches
            else "已逐项核对直接依赖；不代表服务、科学方法或离线安装已验收。",
        ),
    ]
    manifest = json.loads((root / "apps/web/package.json").read_text(encoding="utf-8"))
    frontend_expected = {**manifest["dependencies"], **manifest.get("devDependencies", {})}
    frontend_installed = {}
    for name in frontend_expected:
        target = root / "apps/web/node_modules" / name / "package.json"
        try:
            resolved = target.resolve()
            if not resolved.is_relative_to(root) or resolved.stat().st_size > 256 * 1024:
                continue
            frontend_installed[name] = json.loads(resolved.read_text(encoding="utf-8"))["version"]
        except (OSError, ValueError, KeyError):
            continue
    frontend_errors = sorted(
        name for name, value in frontend_expected.items() if not versions_equal(frontend_installed.get(name), value)
    )
    probes.append(
        EnvironmentProbeRead(
            id="frontend-dependencies",
            label="前端项目依赖",
            scope="host",
            status="mismatch" if frontend_errors else "present",
            observed=f"{len(frontend_expected) - len(frontend_errors)}/{len(frontend_expected)} 项依赖匹配",
            expected="apps/web/package.json 声明的精确版本",
            detail=("缺失或不匹配：" + ", ".join(frontend_errors[:8]))
            if frontend_errors
            else "核对项目本地依赖；冻结锁文件安装及离线冷启动仍需独立验收。",
        )
    )
    return probes
