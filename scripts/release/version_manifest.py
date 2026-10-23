"""The product counter and its mirrors; dependency/protocol versions are independent."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

REVISION = re.compile(r"[0-9a-f]{40}")
VERSION = re.compile(r"(0|[1-9][0-9]*)\.([0-9])\.(0|[1-9][0-9]?)")


def advance_version(current: str, count: int) -> str:
    match = VERSION.fullmatch(current)
    if match is None:
        raise ValueError("Invalid product counter version; minor must be <10 and patch <100")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("Invalid merged PR count")
    major, minor, patch = map(int, match.groups())
    major, remainder = divmod(major * 1000 + minor * 100 + patch + count, 1000)
    minor, patch = divmod(remainder, 100)
    return f"{major}.{minor}.{patch}"


@dataclass(frozen=True)
class VersionState:
    version: str
    processed_through: str


def read_state(root: Path) -> VersionState:
    project = tomllib.loads((root / "pyproject.toml").read_text())
    current = project["project"]["version"]
    cursor = project["tool"]["x-pharma"]["versioning"]["processed-through"]
    if not isinstance(current, str) or not isinstance(cursor, str) or REVISION.fullmatch(cursor) is None:
        raise ValueError("Invalid product version or processed revision")
    advance_version(current, 0)
    return VersionState(current, cursor)


def _replace_assignment(source: str, section: str, key: str, before: str, after: str) -> str:
    lines = source.splitlines(keepends=True)
    selected = False
    replaced = 0
    pattern = re.compile(rf'^(\s*{re.escape(key)}\s*=\s*"){re.escape(before)}("[^\n]*)(\n?)$')
    for index, line in enumerate(lines):
        if line.startswith("["):
            selected = line.strip() == f"[{section}]"
        if selected and (match := pattern.fullmatch(line)) is not None:
            lines[index] = f"{match[1]}{after}{match[2]}{match[3]}"
            replaced += 1
    if replaced != 1:
        raise ValueError(f"Expected exactly one {section}.{key} assignment")
    return "".join(lines)


def update_manifests(root: Path, through: str, count: int) -> str:
    if REVISION.fullmatch(through) is None:
        raise ValueError("Invalid target revision")
    state = read_state(root)
    updated_version = advance_version(state.version, count)
    web_path = root / "apps/web/package.json"
    web = json.loads(web_path.read_text())
    if not isinstance(web, dict) or web.get("version") != state.version:
        raise ValueError("Web product version mirror differs from pyproject.toml")
    if count == 0:
        return updated_version
    manifest_path = root / "pyproject.toml"
    source = _replace_assignment(manifest_path.read_text(), "project", "version", state.version, updated_version)
    source = _replace_assignment(
        source, "tool.x-pharma.versioning", "processed-through", state.processed_through, through
    )
    web["version"] = updated_version
    # This is an unpublished working tree until generation, verification and normal push all succeed.
    manifest_path.write_text(source)
    web_path.write_text(json.dumps(web, indent=2, ensure_ascii=False) + "\n")
    return updated_version
