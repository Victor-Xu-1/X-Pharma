from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import cast

import pytest

from scripts.release.contracts.parser import PARSER_DOCUMENT_CONTRACTS
from scripts.release.contracts.parser_dependencies import parser_document_contracts

SOURCE_MANIFEST = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _source_dependencies() -> list[str]:
    return cast(list[str], tomllib.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))["project"]["dependencies"])


@pytest.mark.parametrize(
    ("suffix", "parser_name", "distribution"),
    [
        (".html", "beautifulsoup4+lxml", "beautifulsoup4"),
        (".docx", "python-docx", "python-docx"),
        (".pptx", "python-pptx", "python-pptx"),
        (".xlsx", "openpyxl", "openpyxl"),
        (".pdf", "pypdf", "pypdf"),
        (".sdf", "rdkit-sdf", "rdkit"),
        (".mol", "rdkit-mol", "rdkit"),
        (".pdb", "gemmi-pdb", "gemmi"),
        (".cif", "gemmi-mmcif", "gemmi"),
        (".mmcif", "gemmi-mmcif", "gemmi"),
    ],
)
def test_parser_release_contract_matches_the_authoritative_source_pin(
    suffix: str, parser_name: str, distribution: str
) -> None:
    source_pin = next(
        declaration.removeprefix(f"{distribution}==")
        for declaration in _source_dependencies()
        if declaration.startswith(f"{distribution}==")
    )
    assert PARSER_DOCUMENT_CONTRACTS[suffix] == (parser_name, source_pin)


@pytest.mark.parametrize(
    "pdf_declarations",
    [
        [],
        ["pypdf>=6.21.2"],
        ["pypdf==6.21.*"],
        ["pypdf[crypto]==6.21.2"],
        ["pypdf==6.21.2", "pypdf==6.21.2"],
        ["pypdf==6.21.2", "pypdf>=6.0"],
    ],
)
def test_release_contract_rejects_missing_unfixed_and_ambiguous_pdf_pins(
    tmp_path: Path, pdf_declarations: list[str]
) -> None:
    dependencies = [entry for entry in _source_dependencies() if not entry.startswith("pypdf==")]
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(f"[project]\ndependencies = {json.dumps(dependencies + pdf_declarations)}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="pypdf.*canonical exact version pin"):
        parser_document_contracts(manifest)


@pytest.mark.parametrize(
    "content", ["[project]\n", '[project]\ndependencies = "pypdf==6.21.2"\n', "[project]\ndependencies = [42]\n"]
)
def test_release_contract_rejects_invalid_dependency_metadata(tmp_path: Path, content: str) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="canonical dependency list"):
        parser_document_contracts(manifest)


def test_release_contract_retains_internal_text_version_and_ignores_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert parser_document_contracts(SOURCE_MANIFEST) == PARSER_DOCUMENT_CONTRACTS
    assert PARSER_DOCUMENT_CONTRACTS[".md"] == ("text", "1")
