"""Bounded read-only interpreter evidence for local and approved managed environments."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

_MANAGED_ENVIRONMENT_ROOT = Path("/srv/wsl/envs")
_INTERPRETER_PROBE = (
    "import importlib.metadata as m,json,platform,sys; "
    "print(json.dumps({'python':platform.python_version(),'prefix':sys.prefix,"
    "'packages':{d.metadata['Name']:d.version for d in m.distributions() if d.metadata['Name']}}))"
)


def _project_interpreter(root: Path) -> Path | None:
    local = root / ".venv"
    try:
        managed = local.is_symlink()
        if managed:
            # Permit only this explicit read-only environment indirection. Workspace,
            # report, plan and installer path rules remain unchanged.
            environment = Path(os.path.abspath(local.parent / local.readlink()))
            approved = _MANAGED_ENVIRONMENT_ROOT.absolute()
            if environment == approved or not environment.is_relative_to(approved):
                return None
            if any(candidate.is_symlink() for candidate in (environment, *environment.parents)):
                return None
            metadata = environment.stat()
            if metadata.st_uid != root.stat().st_uid or metadata.st_mode & 0o022:
                return None
        else:
            if any(candidate.is_symlink() for candidate in local.parents):
                return None
            environment = local.absolute()
        configuration = environment / "pyvenv.cfg"
        executable = environment / "bin/python"
        if not configuration.is_file() or configuration.is_symlink() or not executable.is_file():
            return None
        if (environment / "bin").is_symlink() or executable.resolve().is_relative_to(Path("/mnt")):
            return None
        if managed:
            owner = root.stat().st_uid
            for boundary in (_MANAGED_ENVIRONMENT_ROOT, environment / "bin", configuration):
                metadata = boundary.stat()
                if metadata.st_uid != owner or metadata.st_mode & 0o022:
                    return None
        return executable
    except (OSError, RuntimeError, ValueError):
        return None


def project_python_probe(root: Path) -> dict[str, object] | None:
    executable = _project_interpreter(root)
    if executable is None:
        return None
    try:
        # Fixed argv/code, no shell, network or installer; isolated startup also
        # forbids bytecode writes and inherits no provider credentials or preload.
        result = subprocess.run(  # noqa: S603
            [str(executable), "-I", "-B", "-c", _INTERPRETER_PROBE],
            cwd=root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=5,
            check=False,
            env={"PATH": os.defpath, "LANG": "C.UTF-8"},
        )
        if result.returncode or len(result.stdout) > 64 * 1024:
            return None
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            return None
        prefix = payload.get("prefix")
        if not isinstance(prefix, str) or not Path(prefix).is_absolute():
            return None
        if Path(prefix).resolve() != executable.parent.parent.resolve():
            return None
        if not isinstance(payload.get("python"), str) or not isinstance(payload.get("packages"), dict):
            return None
        return payload
    except (OSError, subprocess.TimeoutExpired, RuntimeError, ValueError):
        return None
