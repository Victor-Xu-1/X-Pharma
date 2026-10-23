from __future__ import annotations

import tomllib
from importlib.metadata import version
from io import BytesIO
from pathlib import Path

import pytest
from packaging.version import Version
from pypdf import PdfReader, PdfWriter
from pypdf.constants import PageLabelStyle
from reportlab.pdfgen.canvas import Canvas

from pharma_intel.ingest.parsers import parse_document
from scripts.release.contracts.parser import PARSER_DOCUMENT_CONTRACTS


def test_pdf_security_release_is_consistent_across_parser_and_optional_ocr() -> None:
    root = Path(__file__).parents[1]
    manifest = tomllib.loads((root / "pyproject.toml").read_text())
    installed = version("pypdf")
    # October's audited resource-consumption fixes supersede the September floor.
    assert Version(installed) >= Version("6.21.2")
    pin = f"pypdf=={installed}"
    assert pin in manifest["project"]["dependencies"]
    assert pin in (root / "services/ocr/requirements.in").read_text().splitlines()
    assert f"{pin} \\" in (root / "services/ocr/requirements.lock").read_text()


def test_real_pdf_output_matches_the_source_bound_release_contract(tmp_path: Path) -> None:
    document = tmp_path / "source.pdf"
    canvas = Canvas(str(document))
    canvas.drawString(50, 750, "Original evidence remains readable")
    canvas.save()
    parsed = parse_document(document, 10_000)
    assert (parsed.parser_name, parsed.parser_version) == PARSER_DOCUMENT_CONTRACTS[".pdf"]
    assert "Original evidence remains readable" in parsed.text
    assert "[[page:1]]" in parsed.text
    assert parsed.metadata["page_count"] == 1


@pytest.mark.parametrize("style", [PageLabelStyle.UPPERCASE_LETTER, PageLabelStyle.LOWERCASE_LETTER])
@pytest.mark.parametrize("start", [13_312, 13_313])
def test_real_pdf_page_labels_bound_allocation_and_preserve_valid_labels(style: PageLabelStyle, start: int) -> None:
    # Use a tiny, valid PDF and a bounded boundary value, not a memory-exhaustion payload.
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.set_page_label(0, 0, style=style, start=start)
    document = BytesIO()
    writer.write(document)
    document.seek(0)
    reader = PdfReader(document, strict=True)
    if start == 13_313:
        assert reader.page_labels == ["1"]
    else:
        character = "Z" if style == PageLabelStyle.UPPERCASE_LETTER else "z"
        assert reader.page_labels == [character * 512]
