"""Source-bound discovery and immutable browser evidence IO, without a service dependency."""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

from scripts.browser_cases import mapping
from scripts.browser_phases import Phase, create_manifest, manifest_cases, partition

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps/web"


def load(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Browser evidence file is missing, unsafe or oversized")
    return mapping(json.loads(path.read_text(encoding="utf-8")))


def save(path: Path, value: dict[str, object]) -> None:
    if not path.parent.is_dir():
        raise ValueError("Browser evidence parent directory must already exist")
    descriptor, name = tempfile.mkstemp(prefix=".browser-evidence-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)


def validate_destination(path: Path) -> None:
    """Fail before browsers start; never replace immutable publication with a silent fallback."""
    if path.exists() or path.is_symlink():
        raise FileExistsError(path)
    if not path.parent.is_dir():
        raise ValueError("Browser evidence parent directory must already exist")
    with tempfile.TemporaryDirectory(prefix=".browser-evidence-check-", dir=path.parent) as temporary:
        try:
            save(Path(temporary) / "probe.json", {"scope": "output-readiness-only"})
        except OSError as error:
            raise ValueError(
                "Browser evidence requires a filesystem supporting atomic exclusive publication"
            ) from error


def source_revision() -> str:
    git = shutil.which("git")
    if git is None:
        raise ValueError("Git is required to bind browser source identity")
    revision = subprocess.run(  # noqa: S603  # Fixed read-only Git commands, no caller shell.
        [git, "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True, timeout=15
    ).stdout.strip()
    dirty = subprocess.run(  # noqa: S603
        [git, "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    ).stdout
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None or dirty:
        raise ValueError("Browser execution evidence requires one clean, exact source revision")
    return revision


def playwright_command() -> list[str]:
    manager = load(WEB / "package.json").get("packageManager")
    if not isinstance(manager, str) or re.fullmatch(r"pnpm@\d+\.\d+\.\d+", manager) is None:
        raise ValueError("The original exact package-manager pin is required")
    corepack = shutil.which("corepack")
    if corepack is None:
        raise ValueError("Corepack is required")
    return [corepack, manager, "--dir", str(WEB), "exec", "playwright", "test"]


def discover() -> dict[str, object]:
    revision = source_revision()
    with tempfile.TemporaryDirectory(prefix="x-pharma-browser-discovery-") as temporary:
        output = Path(temporary) / "discovery.json"
        environment = dict(os.environ)
        # An owned file is the sole reporter channel, not an implicit stdout fallback.
        environment["PLAYWRIGHT_JSON_OUTPUT_FILE"] = str(output)
        execute([*playwright_command(), "--list", "--reporter=json"], environment, 60)
        if source_revision() != revision:
            raise ValueError("Browser source changed during original case discovery")
        return create_manifest(load(output), revision)


def phase_arguments(manifest: dict[str, object], phase: Phase) -> list[str]:
    cases = partition(manifest_cases(manifest), phase)
    arguments = []
    for filename in sorted({case.file for case in cases.values()}):
        path = WEB / "e2e" / filename
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to((WEB / "e2e").resolve()):
            raise ValueError("Browser phase cannot execute outside the original test directory")
        arguments.append(re.escape(f"e2e/{filename}") + "$")
    if not arguments:
        raise ValueError("A browser execution phase cannot be empty")
    return arguments


def stop_group(process: subprocess.Popen[bytes]) -> None:
    """Only groups started by this runner with start_new_session=True are accepted."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def execute(command: list[str], environment: dict[str, str], timeout: int) -> None:
    process = subprocess.Popen(  # noqa: S603  # Validated fixed executable/arguments, isolated owned process group.
        command, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, start_new_session=True
    )
    try:
        code = process.wait(timeout=timeout)
        if code:
            raise subprocess.CalledProcessError(code, command)
    finally:
        stop_group(process)
