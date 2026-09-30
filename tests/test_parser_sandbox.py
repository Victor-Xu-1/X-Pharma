from __future__ import annotations

from pathlib import Path

import pytest

from pharma_intel.ingest.parser_sandbox import (
    ParserSandboxError,
    ParserSandboxTimeout,
    parse_document_in_sandbox,
)
from pharma_intel.ingest.parsers import DocumentOcrRequired, DocumentParseError


def test_parser_sandbox_runs_real_isolated_python_process(tmp_path: Path) -> None:
    source = tmp_path / "evidence.md"
    source.write_text("EGFR L858R evidence", encoding="utf-8")

    parsed = parse_document_in_sandbox(source, 100_000, timeout_seconds=20)

    assert parsed.text == "EGFR L858R evidence"
    assert parsed.parser_name == "text"
    assert parsed.metadata == {"encoding": "utf-8-sig"}


def test_parser_sandbox_rejects_symlink_input(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("evidence", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(source)

    with pytest.raises(ParserSandboxError, match="non-symlink"):
        parse_document_in_sandbox(link, 100_000)


def test_parser_sandbox_kills_process_group_after_wall_clock_limit(tmp_path: Path) -> None:
    source = tmp_path / "evidence.md"
    source.write_text("evidence", encoding="utf-8")

    with pytest.raises(ParserSandboxTimeout, match="wall-clock"):
        parse_document_in_sandbox(source, 100_000, timeout_seconds=0.001)


def test_parser_sandbox_preserves_document_rejection(tmp_path: Path) -> None:
    source = tmp_path / "empty.md"
    source.write_text("", encoding="utf-8")

    with pytest.raises(DocumentParseError, match="no extractable text"):
        parse_document_in_sandbox(source, 100_000, timeout_seconds=20)


def test_parser_sandbox_preserves_typed_ocr_requirement(tmp_path: Path) -> None:
    source = tmp_path / "scan.png"
    source.write_bytes(b"validity is checked by OCR preflight")

    with pytest.raises(DocumentOcrRequired, match="requires OCR"):
        parse_document_in_sandbox(source, 100_000, timeout_seconds=20)
