"""Verify the OCR image keeps still-image operations and contains no FFmpeg."""

from __future__ import annotations

import ast
import importlib.metadata
import re
from pathlib import Path
from typing import Any


def verify_video_backends(cv2: Any, build: str) -> None:
    # 4.10 omits disabled backend lines entirely. Query the real registry instead
    # of treating a missing display label as either proof of safety or failure.
    for label, backend in (("FFMPEG", cv2.CAP_FFMPEG), ("GStreamer", cv2.CAP_GSTREAMER)):
        assert not cv2.videoio_registry.hasBackend(backend), f"Unexpected video backend: {label}"
        status = re.search(rf"^\s*{label}:\s*(\S+)", build, re.MULTILINE)
        assert status is None or status[1] == "NO", f"Unexpected {label} build status"


def verify() -> None:
    import cv2  # type: ignore[import-not-found]
    import numpy as np

    assert importlib.metadata.version("opencv-contrib-python") == "4.10.0.84"
    build = cv2.getBuildInformation()
    verify_video_backends(cv2, build)
    for distribution in importlib.metadata.distributions():
        for item in distribution.files or []:
            name = Path(str(item)).name.lower()
            assert not name.startswith(("libavcodec", "libavformat", "libavutil", "libswscale", "libswresample")), name
    sample = np.zeros((24, 32, 3), dtype=np.uint8)
    sample[3:15, 4:18] = 200
    for suffix in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
        success, encoded = cv2.imencode(suffix, sample)
        assert success
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        assert decoded is not None and decoded.shape == sample.shape
    gray = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
    assert cv2.resize(gray, (16, 12)).shape == (12, 16)
    points = np.array([[0, 0], [31, 0], [31, 23], [0, 23]], dtype=np.float32)
    transform = cv2.getPerspectiveTransform(points, points)
    assert cv2.warpPerspective(sample, transform, (32, 24)).shape == sample.shape
    assert cv2.findContours(gray, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0]
    # Check every symbol referenced by the existing locked PaddleX package, without downloading models.
    distribution = importlib.metadata.distribution("paddlex")
    symbols: set[str] = set()
    for item in distribution.files or []:
        if not str(item).endswith(".py"):
            continue
        source = distribution.locate_file(item)
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "cv2":
                symbols.add(node.attr)
    assert symbols and all(hasattr(cv2, symbol) for symbol in symbols), sorted(symbols)
    from paddleocr import PaddleOCR  # type: ignore[import-not-found]

    assert callable(PaddleOCR)
    print(f"ocr_opencv=passed formats=5 ffmpeg=false paddlex_symbols={len(symbols)} models_downloaded=0")


if __name__ == "__main__":
    verify()
