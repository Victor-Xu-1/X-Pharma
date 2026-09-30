from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image
from PIL.IcoImagePlugin import IcoImageFile

from scripts.generate_brand_assets import DESTINATION, ICO_SIZES, PNG_SIZES, SOURCE, generate_assets, render_assets


def test_committed_brand_assets_reproduce_the_supplied_logo() -> None:
    generate_assets(check=True)
    for name, size in PNG_SIZES.items():
        with Image.open(DESTINATION / f"X-Pharma-{name}.png") as image:
            assert image.size == (size, size)
            assert image.mode == "RGBA"
            pixel = image.getpixel((0, 0))
            assert isinstance(pixel, tuple) and pixel[3] == 0


def test_browser_ico_contains_real_small_and_high_density_sizes() -> None:
    with Image.open(io.BytesIO(render_assets(SOURCE)["X-Pharma-favicon.ico"])) as image:
        assert image.format == "ICO"
        assert isinstance(image, IcoImageFile)
        assert image.ico.sizes() == set(ICO_SIZES)


def test_brand_check_rejects_stale_derivatives_without_overwriting_them(tmp_path: Path) -> None:
    generate_assets(destination=tmp_path)
    icon = tmp_path / "X-Pharma-favicon-16.png"
    icon.write_bytes(b"stale")
    with pytest.raises(ValueError, match="missing or stale"):
        generate_assets(destination=tmp_path, check=True)
    assert icon.read_bytes() == b"stale"


def test_brand_generator_rejects_an_unreviewed_source(tmp_path: Path) -> None:
    unexpected = tmp_path / "unreviewed.png"
    unexpected.write_bytes(b"unreviewed image")
    with pytest.raises(ValueError, match="reviewed maintainer-supplied PNG"):
        render_assets(unexpected)
