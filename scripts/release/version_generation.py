"""Use the existing generators, then reject any unrelated automatic changes."""

from __future__ import annotations

import json
import subprocess
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from scripts.release.version_manifest import read_state

VERSION_PATHS = frozenset(
    {
        "pyproject.toml",
        "uv.lock",
        "apps/web/package.json",
        "docs/openapi.json",
        "apps/web/src/lib/generated/core/OpenAPI.ts",
        "docs/project-overview.html",
    }
)


def command(root: Path, args: Sequence[str], *, timeout: int = 120) -> str:
    return subprocess.run(  # noqa: S603 -- typed argument list, never a shell command
        args, cwd=root, capture_output=True, text=True, timeout=timeout, check=True
    ).stdout.strip()


def unchanged_dependencies(before: dict[str, Any], after: dict[str, Any]) -> None:
    for document in (before, after):
        packages = [item for item in document["package"] if item["name"] == "x-pharma"]
        if len(packages) != 1 or packages[0].get("source") != {"editable": "."}:
            raise ValueError("Missing authoritative root package in uv.lock")
        packages[0]["version"] = "<product-version>"
    if before != after:
        raise ValueError("Version generation changed dependency resolution")


def generate_mirrors(root: Path) -> None:
    before_lock = tomllib.loads((root / "uv.lock").read_text())
    before_contract = json.loads((root / "docs/openapi.json").read_text())
    command(root, ["uv", "lock", "--offline"])
    unchanged_dependencies(before_lock, tomllib.loads((root / "uv.lock").read_text()))
    command(root, ["uv", "sync", "--locked", "--offline", "--dev"], timeout=180)
    command(root, ["uv", "run", "--locked", "--offline", "pharma-openapi"])
    after_contract = json.loads((root / "docs/openapi.json").read_text())
    before_contract["info"]["version"] = read_state(root).version
    if before_contract != after_contract:
        raise ValueError("Version generation changed an API schema")
    # Corepack resolves packageManager from its working directory, before pnpm interprets --dir.
    # Refresh the importer metadata explicitly and offline, rather than pnpm's implicit pre-run install.
    command(root / "apps/web", ["corepack", "pnpm", "install", "--frozen-lockfile", "--offline"], timeout=180)
    command(root / "apps/web", ["corepack", "pnpm", "api:generate"])
    command(root, ["uv", "run", "--locked", "--offline", "python", "scripts/project_overview.py"])
    command(root, ["uv", "run", "--locked", "--offline", "pharma-openapi", "--check"])
    command(root / "apps/web", ["corepack", "pnpm", "api:check"])
    command(root, ["git", "diff", "--check"])
    changed = set(command(root, ["git", "diff", "--name-only"]).splitlines())
    untracked = command(root, ["git", "ls-files", "--others", "--exclude-standard"])
    if not changed or not changed <= VERSION_PATHS or untracked:
        raise ValueError("Automatic version changes escaped the owned file allowlist")
