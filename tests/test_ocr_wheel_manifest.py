from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from services.ocr.wheel_manifest import wheel_manifest


def test_built_wheels_keep_the_complete_lock_versions_and_content_hashes(tmp_path: Path) -> None:
    lock = tmp_path / "runtime.lock"
    lock.write_text(
        "# verified upstream inputs\nOpenCV_Contrib_Python==4.10.0.84 \\\n    --hash=sha256:source\nnumpy==2.3.5\n"
    )
    wheel = tmp_path / "opencv_contrib_python-4.10.0.84-cp313-cp313-linux_x86_64.whl"
    wheel.write_bytes(b"controlled source-built wheel")
    numpy = tmp_path / "numpy-2.3.5-cp313-cp313-linux_x86_64.whl"
    numpy.write_bytes(b"controlled upstream wheel")
    output = wheel_manifest(lock, tmp_path)
    assert output.splitlines() == [
        f"numpy==2.3.5 --hash=sha256:{hashlib.sha256(numpy.read_bytes()).hexdigest()}",
        f"opencv-contrib-python==4.10.0.84 --hash=sha256:{hashlib.sha256(wheel.read_bytes()).hexdigest()}",
    ]
    first = output
    wheel.write_bytes(b"changed bytes")
    assert wheel_manifest(lock, tmp_path) != first


@pytest.mark.parametrize("filename", ["other-1.0-py3-none-any.whl", "example-2.0-py3-none-any.whl"])
def test_wheel_manifest_rejects_unexpected_or_wrong_versions(tmp_path: Path, filename: str) -> None:
    lock = tmp_path / "runtime.lock"
    lock.write_text("example==1.0\n")
    (tmp_path / filename).write_bytes(b"wrong wheel")
    with pytest.raises(ValueError, match="Unexpected"):
        wheel_manifest(lock, tmp_path)


@pytest.mark.parametrize("content", ["", "example==1.0\n", "example>=1.0\n", "example==1.0\nexample==1.0\n"])
def test_wheel_manifest_rejects_empty_missing_or_ambiguous_lock(tmp_path: Path, content: str) -> None:
    lock = tmp_path / "runtime.lock"
    lock.write_text(content)
    with pytest.raises(ValueError):
        wheel_manifest(lock, tmp_path)


def test_wheel_manifest_rejects_symlinks_and_duplicate_distributions(tmp_path: Path) -> None:
    lock = tmp_path / "runtime.lock"
    lock.write_text("example==1.0\n")
    target = tmp_path / "target"
    target.write_bytes(b"outside wheel")
    linked = tmp_path / "example-1.0-py3-none-any.whl"
    linked.symlink_to(target)
    with pytest.raises(ValueError, match="regular"):
        wheel_manifest(lock, tmp_path)
    linked.unlink()
    linked.write_bytes(b"first")
    (tmp_path / "example-1.0-cp313-cp313-linux_x86_64.whl").write_bytes(b"second")
    with pytest.raises(ValueError, match="duplicate"):
        wheel_manifest(lock, tmp_path)


def test_ocr_image_source_build_keeps_hashes_and_runs_real_media_probes() -> None:
    root = Path(__file__).parents[1]
    dockerfile = (root / "services/ocr/Dockerfile").read_text()
    build = (root / "services/ocr/opencv-build.sh").read_text()
    assert "--no-binary=opencv-contrib-python" in build
    assert "--require-hashes --no-deps --no-build-isolation" in build
    assert "-DWITH_FFMPEG=OFF" in build and "-DWITH_GSTREAMER=OFF" in build
    assert "--no-index --no-deps --require-hashes" in dockerfile
    assert "python -m pip check" in dockerfile and "python /tmp/verify-opencv.py" in dockerfile
    assert "from=wheel-builder,source=/wheelhouse" in dockerfile
