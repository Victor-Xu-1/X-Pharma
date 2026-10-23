from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _verify(build: str, available: set[int]) -> None:
    source = Path(__file__).parents[1] / "services" / "ocr" / "verify_opencv.py"
    spec = importlib.util.spec_from_file_location("ocr_opencv_probe", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cv2 = SimpleNamespace(
        CAP_FFMPEG=1900,
        CAP_GSTREAMER=1800,
        videoio_registry=SimpleNamespace(hasBackend=available.__contains__),
    )
    module.verify_video_backends(cv2, build)


@pytest.mark.parametrize("build", ["Video I/O:\n    DC1394: NO\n", "FFMPEG: NO\nGStreamer: NO\n"])
def test_disabled_video_backends_are_checked_by_the_runtime_registry(build: str) -> None:
    _verify(build, set())


@pytest.mark.parametrize("available", [{1900}, {1800}, {1900, 1800}])
def test_available_video_backends_fail_even_when_build_text_says_no(available: set[int]) -> None:
    with pytest.raises(AssertionError, match="Unexpected video backend"):
        _verify("FFMPEG: NO\nGStreamer: NO\n", available)


@pytest.mark.parametrize("build", ["FFMPEG: YES\n", "GStreamer: YES\n"])
def test_enabled_build_metadata_fails_even_when_runtime_registry_is_unavailable(build: str) -> None:
    with pytest.raises(AssertionError, match="build status"):
        _verify(build, set())
