"""Reproduce browser/UI logo sizes from the maintainer-supplied transparent PNG."""

from __future__ import annotations

import argparse
import hashlib
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps" / "web" / "brand" / "X-Pharma.png"
DESTINATION = ROOT / "apps" / "web" / "src" / "assets" / "brand"
SOURCE_SHA256 = "1099f1a295921cc9e229995cd84aced5a2e1022e223bf6140f65d585f7b7d591"
PNG_SIZES = {"logo-128": 128, "favicon-16": 16, "favicon-32": 32, "apple-touch-180": 180}
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64)]


def render_assets(source: Path) -> dict[str, bytes]:
    original = source.read_bytes()
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA256:
        raise ValueError("Logo source does not match the reviewed maintainer-supplied PNG")
    with Image.open(io.BytesIO(original)) as image:
        if image.format != "PNG" or image.mode != "RGBA" or image.size != (1254, 1254):
            raise ValueError("Logo must retain the reviewed square transparent RGBA source")
        result: dict[str, bytes] = {}
        for name, size in PNG_SIZES.items():
            output = io.BytesIO()
            image.resize((size, size), Image.Resampling.LANCZOS).save(output, format="PNG", compress_level=9)
            result[f"X-Pharma-{name}.png"] = output.getvalue()
        output = io.BytesIO()
        image.save(output, format="ICO", sizes=ICO_SIZES)
        result["X-Pharma-favicon.ico"] = output.getvalue()
    return result


def generate_assets(source: Path = SOURCE, destination: Path = DESTINATION, *, check: bool = False) -> None:
    assets = render_assets(source)
    if check:
        stale = [
            name
            for name, content in assets.items()
            if not (destination / name).is_file() or (destination / name).read_bytes() != content
        ]
        if stale:
            raise ValueError(f"Brand assets are missing or stale: {', '.join(stale)}")
        return
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in assets.items():
        (destination / name).write_bytes(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify committed derivatives without modifying files")
    arguments = parser.parse_args()
    generate_assets(check=arguments.check)
    print("X-Pharma brand assets verified" if arguments.check else "X-Pharma brand assets generated")


if __name__ == "__main__":
    main()
