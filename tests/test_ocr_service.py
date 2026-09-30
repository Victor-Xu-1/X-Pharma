from __future__ import annotations

import hashlib
import importlib.metadata
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from services.ocr.service import OcrSettings, _directory_digest, create_app

TOKEN = "test-ocr-service-token-123456789012345"  # noqa: S105


class Result:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.json = {"res": payload}


class Engine:
    def __init__(self, results: list[object]) -> None:
        self.results = results
        self.calls = 0

    def predict(self, _path: Path) -> list[object]:
        self.calls += 1
        return self.results


def _settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> OcrSettings:
    detection = tmp_path / "detection"
    recognition = tmp_path / "recognition"
    detection.mkdir()
    recognition.mkdir()
    (detection / "inference.json").write_text("detection", encoding="utf-8")
    (recognition / "inference.json").write_text("recognition", encoding="utf-8")
    versions = {"paddleocr": "3.5.0", "paddlepaddle": "3.3.1"}
    monkeypatch.setattr(importlib.metadata, "version", versions.__getitem__)
    return OcrSettings(
        _env_file=None,
        token=TOKEN,
        detection_model_dir=detection,
        recognition_model_dir=recognition,
        detection_model_sha256=_directory_digest(detection),
        recognition_model_sha256=_directory_digest(recognition),
        max_file_bytes=1_048_576,
        max_text_chars=100_000,
        max_page_pixels=10_000_000,
    )


def _png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (320, 120), "white").save(output, format="PNG")
    return output.getvalue()


def _headers(payload: bytes, *, token: str = TOKEN) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Content-Length": str(len(payload)),
        "X-Content-SHA256": hashlib.sha256(payload).hexdigest(),
    }


def _valid_result() -> Result:
    return Result(
        {
            "page_index": 0,
            "rec_texts": ["EGFR 靶点 活性 IC50 12 nM", "discarded"],
            "rec_scores": [0.97, 0.2],
            "rec_boxes": [[10, 20, 300, 50], [10, 60, 100, 90]],
        }
    )


@pytest.mark.parametrize("actual_format", ["MPEG", "GIF", "PPM", "JPEG"])
def test_ocr_service_rejects_formats_masquerading_as_png_before_the_engine(
    actual_format: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if actual_format == "MPEG":
        # Pillow identifies MPEG metadata without decoding it; verify() alone accepts this stream.
        payload = b"\x00\x00\x01\xb3" + ((320 << 12) | 120).to_bytes(3, "big") + b"\x00" * 16
    else:
        output = BytesIO()
        Image.new("RGB", (320, 120), "white").save(output, format=actual_format)
        payload = output.getvalue()
    with Image.open(BytesIO(payload)) as identified:
        assert identified.format == actual_format
    engine = Engine([_valid_result()])
    client = TestClient(create_app(_settings(tmp_path, monkeypatch), engine))
    response = client.post(
        "/internal/v1/parse",
        params={"filename": "renamed.png", "max_chars": 100_000},
        headers=_headers(payload),
        content=payload,
    )
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "document_format_mismatch"
    assert engine.calls == 0


@pytest.mark.parametrize(
    "suffix, actual_format", [("png", "PNG"), ("jpg", "JPEG"), ("jpeg", "JPEG"), ("tif", "TIFF"), ("tiff", "TIFF")]
)
def test_ocr_service_preserves_supported_still_image_formats(
    suffix: str, actual_format: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = BytesIO()
    Image.new("RGB", (320, 120), "white").save(output, format=actual_format)
    payload = output.getvalue()
    engine = Engine([_valid_result()])
    client = TestClient(create_app(_settings(tmp_path, monkeypatch), engine))
    response = client.post(
        "/internal/v1/parse",
        params={"filename": f"scan.{suffix}", "max_chars": 100_000},
        headers=_headers(payload),
        content=payload,
    )
    assert response.status_code == 200
    assert engine.calls == 1


def test_ocr_service_returns_governed_text_locators_and_model_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path, monkeypatch)
    payload = _png()
    client = TestClient(create_app(settings, Engine([_valid_result()])))

    response = client.post(
        "/internal/v1/parse",
        params={"filename": "scan.png", "max_chars": 100_000},
        headers=_headers(payload),
        content=payload,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["parser_name"] == "paddleocr"
    assert result["parser_version"] == "3.5.0"
    assert result["source_sha256"] == hashlib.sha256(payload).hexdigest()
    assert "[[page:1]]" in result["text"]
    assert "[[region:10,20,300,50;confidence:0.9700]]" in result["text"]
    assert "EGFR 靶点 活性 IC50 12 nM" in result["text"]
    assert "discarded" not in result["text"]
    assert result["metadata"]["locator_scheme"] == "page-region-v1"
    assert result["metadata"]["discarded_line_count"] == 1
    assert result["metadata"]["detection_model_sha256"] == settings.detection_model_sha256


def test_ocr_service_rejects_authentication_digest_and_invalid_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path, monkeypatch)
    client = TestClient(create_app(settings, Engine([_valid_result()])))
    payload = _png()

    unauthorized = client.post(
        "/internal/v1/parse",
        params={"filename": "scan.png", "max_chars": 100_000},
        headers=_headers(payload, token="wrong"),  # noqa: S106 - intentional rejection fixture.
        content=payload,
    )
    bad_headers = _headers(payload)
    bad_headers["X-Content-SHA256"] = "0" * 64
    digest_mismatch = client.post(
        "/internal/v1/parse",
        params={"filename": "scan.png", "max_chars": 100_000},
        headers=bad_headers,
        content=payload,
    )
    invalid = b"not an image"
    invalid_image = client.post(
        "/internal/v1/parse",
        params={"filename": "scan.png", "max_chars": 100_000},
        headers=_headers(invalid),
        content=invalid,
    )

    assert unauthorized.status_code == 401
    assert digest_mismatch.json()["detail"]["code"] == "source_digest_mismatch"
    assert invalid_image.status_code == 422
    assert invalid_image.json()["detail"]["message"] == "Image is invalid"


def test_ocr_service_does_not_expose_engine_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path, monkeypatch)
    client = TestClient(create_app(settings, Engine([object()])))
    payload = _png()

    response = client.post(
        "/internal/v1/parse",
        params={"filename": "scan.png", "max_chars": 100_000},
        headers=_headers(payload),
        content=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "document_ocr_rejected",
        "message": "OCR engine rejected the document",
    }


def test_ocr_service_rejects_model_digest_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path, monkeypatch)
    (settings.detection_model_dir / "inference.json").write_text("tampered", encoding="utf-8")

    with pytest.raises(RuntimeError, match="digest does not match"):
        create_app(settings, Engine([_valid_result()]))


@pytest.mark.parametrize(
    ("text", "score"),
    [("unsafe\x00text", 0.9), ("typed incorrectly", "0.9"), ("boolean confidence", True)],
)
def test_ocr_service_rejects_malformed_engine_scalar_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    text: str,
    score: object,
) -> None:
    settings = _settings(tmp_path, monkeypatch)
    result = Result(
        {
            "page_index": 0,
            "rec_texts": [text],
            "rec_scores": [score],
            "rec_boxes": [[10, 20, 300, 50]],
        }
    )
    client = TestClient(create_app(settings, Engine([result])))
    payload = _png()

    response = client.post(
        "/internal/v1/parse",
        params={"filename": "scan.png", "max_chars": 100_000},
        headers=_headers(payload),
        content=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "OCR engine rejected the document"
