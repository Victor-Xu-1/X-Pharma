"""Bind release parser expectations to the candidate's authoritative dependencies."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import cast

_PARSERS = {
    ".html": ("beautifulsoup4+lxml", "beautifulsoup4"),
    ".docx": ("python-docx", "python-docx"),
    ".pptx": ("python-pptx", "python-pptx"),
    ".xlsx": ("openpyxl", "openpyxl"),
    ".pdf": ("pypdf", "pypdf"),
    ".sdf": ("rdkit-sdf", "rdkit"),
    ".mol": ("rdkit-mol", "rdkit"),
    ".pdb": ("gemmi-pdb", "gemmi"),
    ".cif": ("gemmi-mmcif", "gemmi"),
    ".mmcif": ("gemmi-mmcif", "gemmi"),
}


def _exact_pin(dependencies: list[str], distribution: str) -> str:
    name = re.escape(distribution)
    candidates = [entry for entry in dependencies if re.match(rf"{name}(?=[^A-Za-z0-9_.-]|$)", entry, re.IGNORECASE)]
    if len(candidates) != 1:
        raise ValueError(f"Parser dependency {distribution} requires one canonical exact version pin")
    match = re.fullmatch(rf"{name}==([0-9][A-Za-z0-9.!+_-]*)", candidates[0], re.IGNORECASE)
    if match is None:
        raise ValueError(f"Parser dependency {distribution} requires one canonical exact version pin")
    return match.group(1)


def parser_document_contracts(manifest: Path) -> dict[str, tuple[str, str]]:
    """Never let an installed library or submitted report choose its own expected version."""
    document = tomllib.loads(manifest.read_text(encoding="utf-8"))
    project = document.get("project")
    declared = project.get("dependencies") if isinstance(project, dict) else None
    if not isinstance(declared, list) or not all(isinstance(entry, str) for entry in declared):
        raise ValueError("Parser contracts require the project's canonical dependency list")
    dependencies = cast(list[str], declared)
    versions = {name: _exact_pin(dependencies, name) for name in sorted({entry[1] for entry in _PARSERS.values()})}
    return {
        ".md": ("text", "1"),
        **{suffix: (name, versions[distribution]) for suffix, (name, distribution) in _PARSERS.items()},
    }
