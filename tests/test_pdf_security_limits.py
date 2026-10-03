from __future__ import annotations

import tomllib
from importlib.metadata import version
from io import BytesIO
from pathlib import Path

import pytest
from packaging.version import Version
from pypdf import PdfReader, PdfWriter
from pypdf.constants import PageLabelStyle


def test_pdf_security_release_is_consistent_across_parser_and_optional_ocr() -> None:
    root = Path(__file__).parents[1]
    manifest = tomllib.loads((root / "pyproject.toml").read_text())
    installed = version("pypdf")
    # The audited September advisories require at least this upstream patch set.
    assert Version(installed) >= Version("6.19.0")
    pin = f"pypdf=={installed}"
    assert pin in manifest["project"]["dependencies"]
    assert pin in (root / "services/ocr/requirements.in").read_text().splitlines()
    assert f"{pin} \\" in (root / "services/ocr/requirements.lock").read_text()


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
