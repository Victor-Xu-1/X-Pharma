from __future__ import annotations

import hashlib
import hmac
import importlib.metadata
import logging
import math
import os
import re
import ssl
import stat
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol, cast

import anyio
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, Request
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from pypdf import PdfReader

OCR_PROTOCOL_VERSION = 1
SUPPORTED_SUFFIXES = frozenset({".jpeg", ".jpg", ".pdf", ".png", ".tif", ".tiff"})
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
LOGGER = logging.getLogger("pharma_ocr")


class OcrSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OCR_SERVICE_", extra="ignore")

    host: str = "127.0.0.1"
    port: int = Field(default=8071, ge=1, le=65_535)
    token: SecretStr
    max_file_bytes: int = Field(default=268_435_456, ge=1024, le=1_073_741_824)
    max_text_chars: int = Field(default=50_000_000, ge=1000, le=200_000_000)
    max_pages: int = Field(default=100, ge=1, le=10_000)
    max_page_pixels: int = Field(default=100_000_000, ge=1_000_000, le=500_000_000)
    max_lines: int = Field(default=1_000_000, ge=1, le=10_000_000)
    min_confidence: float = Field(default=0.5, ge=0, le=1)
    max_concurrent_requests: int = Field(default=1, ge=1, le=8)
    limit_concurrency: int = Field(default=4, ge=1, le=64)
    detection_model_dir: Path
    recognition_model_dir: Path
    detection_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recognition_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    paddleocr_version: str = "3.5.0"
    paddlepaddle_version: str = "3.3.1"
    tls_cert_file: str = ""
    tls_key_file: str = ""
    tls_client_ca_file: str = ""

    def validate_runtime(self) -> None:
        if len(self.token.get_secret_value().encode("utf-8")) < 32:
            raise RuntimeError("OCR_SERVICE_TOKEN must contain at least 32 bytes")
        if bool(self.tls_cert_file) != bool(self.tls_key_file):
            raise RuntimeError("OCR TLS certificate and key must be configured together")
        if self.tls_client_ca_file and not self.tls_cert_file:
            raise RuntimeError("OCR mTLS client CA requires a TLS server certificate and key")
        for label, path, expected in (
            ("detection", self.detection_model_dir, self.detection_model_sha256),
            ("recognition", self.recognition_model_dir, self.recognition_model_sha256),
        ):
            if not path.is_absolute() or not path.is_dir() or path.is_symlink():
                raise RuntimeError(f"OCR {label} model directory is unavailable")
            if _directory_digest(path) != expected:
                raise RuntimeError(f"OCR {label} model directory digest does not match policy")
        installed = {
            "paddleocr": importlib.metadata.version("paddleocr"),
            "paddlepaddle": importlib.metadata.version("paddlepaddle"),
        }
        if installed != {
            "paddleocr": self.paddleocr_version,
            "paddlepaddle": self.paddlepaddle_version,
        }:
            raise RuntimeError(f"OCR runtime version drift detected: {installed}")


class OcrResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: int = Field(default=OCR_PROTOCOL_VERSION, ge=1, le=OCR_PROTOCOL_VERSION)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text: str
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    metadata: dict[str, Any]
    parser_name: str = "paddleocr"
    parser_version: str


class OcrEngine(Protocol):
    def predict(self, path: Path) -> Iterable[object]: ...


class PaddleOcrEngine:
    def __init__(self, settings: OcrSettings) -> None:
        from paddleocr import PaddleOCR  # type: ignore[import-not-found]  # PaddleOCR does not publish PEP 561 data.

        self.pipeline = PaddleOCR(
            text_detection_model_dir=str(settings.detection_model_dir),
            text_recognition_model_dir=str(settings.recognition_model_dir),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )

    def predict(self, path: Path) -> Iterable[object]:
        return cast(Iterable[object], self.pipeline.predict(str(path)))


def create_app(settings: OcrSettings, engine: OcrEngine | None = None) -> FastAPI:
    settings.validate_runtime()
    selected_engine = engine or PaddleOcrEngine(settings)
    request_slots = anyio.Semaphore(settings.max_concurrent_requests)
    app = FastAPI(title="Pharma OCR Sandbox", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health/live")
    def live() -> dict[str, object]:
        return {"status": "ok", "protocol_version": OCR_PROTOCOL_VERSION}

    @app.get("/health/ready")
    def ready() -> dict[str, object]:
        return {
            "status": "ready",
            "protocol_version": OCR_PROTOCOL_VERSION,
            "paddleocr_version": settings.paddleocr_version,
            "paddlepaddle_version": settings.paddlepaddle_version,
        }

    @app.post("/internal/v1/parse", response_model=OcrResponse)
    async def parse(
        request: Request,
        filename: str = Query(min_length=1, max_length=255),
        max_chars: int = Query(ge=1000),
        authorization: str = Header(default=""),
        content_length: str = Header(default=""),
        content_type: str = Header(default=""),
        content_encoding: str = Header(default=""),
        x_content_sha256: str = Header(default=""),
    ) -> OcrResponse:
        _authorize(settings, authorization)
        if content_type.partition(";")[0].strip().casefold() != "application/octet-stream":
            raise _http_error(415, "unsupported_media_type", "OCR input must be application/octet-stream")
        if content_encoding and content_encoding.casefold() != "identity":
            raise _http_error(415, "content_encoding_rejected", "Compressed HTTP request bodies are not accepted")
        size_bytes = _content_length(content_length, settings.max_file_bytes)
        if max_chars > settings.max_text_chars:
            raise _http_error(413, "text_limit_exceeded", "Requested text limit exceeds OCR service policy")
        suffix = _safe_suffix(filename)
        if SHA256_PATTERN.fullmatch(x_content_sha256) is None:
            raise _http_error(400, "source_digest_invalid", "A valid source SHA-256 is required")
        try:
            request_slots.acquire_nowait()
        except anyio.WouldBlock as exc:
            raise HTTPException(
                status_code=429,
                detail={"code": "ocr_capacity_exhausted", "message": "OCR capacity is temporarily exhausted"},
                headers={"Retry-After": "2"},
            ) from exc
        try:
            with tempfile.TemporaryDirectory(prefix="pharma-ocr-request-") as temporary_directory:
                input_path = Path(temporary_directory) / f"source{suffix}"
                await _receive(request, input_path, size_bytes, settings.max_file_bytes, x_content_sha256)
                _preflight(input_path, settings)
                try:
                    text, metadata = await anyio.to_thread.run_sync(
                        lambda: _render_results(selected_engine.predict(input_path), settings, max_chars)
                    )
                except HTTPException:
                    raise
                except Exception as exc:
                    LOGGER.exception("OCR engine rejected a document")
                    raise _http_error(
                        422,
                        "document_ocr_rejected",
                        "OCR engine rejected the document",
                    ) from exc
                return OcrResponse(
                    source_sha256=x_content_sha256,
                    text=text,
                    text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    metadata=metadata,
                    parser_version=settings.paddleocr_version,
                )
        finally:
            request_slots.release()

    return app


def _authorize(settings: OcrSettings, authorization: str) -> None:
    expected = f"Bearer {settings.token.get_secret_value()}"
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=401,
            detail={"code": "ocr_authentication_required", "message": "OCR authentication failed"},
            headers={"WWW-Authenticate": "Bearer"},
        )


def _content_length(value: str, maximum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise _http_error(411, "content_length_required", "A valid Content-Length is required") from exc
    if parsed < 1:
        raise _http_error(400, "empty_input", "OCR input cannot be empty")
    if parsed > maximum:
        raise _http_error(413, "file_too_large", "OCR input exceeds service policy")
    return parsed


def _safe_suffix(filename: str) -> str:
    if "\x00" in filename or "/" in filename or "\\" in filename or Path(filename).name != filename:
        raise _http_error(400, "filename_invalid", "OCR filename is invalid")
    suffix = Path(filename).suffix.casefold()
    if suffix not in SUPPORTED_SUFFIXES:
        raise _http_error(415, "document_type_unsupported", "Document type is not supported by OCR")
    return suffix


async def _receive(request: Request, path: Path, declared: int, maximum: int, expected_digest: str) -> None:
    digest = hashlib.sha256()
    received = 0
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(descriptor, "wb") as destination:
        async for chunk in request.stream():
            received += len(chunk)
            if received > declared or received > maximum:
                raise _http_error(413, "file_too_large", "OCR input exceeded its declared limit")
            destination.write(chunk)
            digest.update(chunk)
    if received != declared:
        raise _http_error(400, "content_length_mismatch", "OCR input length did not match Content-Length")
    if not hmac.compare_digest(digest.hexdigest(), expected_digest):
        raise _http_error(400, "source_digest_mismatch", "OCR input SHA-256 did not match")


def _preflight(path: Path, settings: OcrSettings) -> None:
    if path.suffix.casefold() == ".pdf":
        try:
            reader = PdfReader(path, strict=True)
        except Exception as exc:
            raise _http_error(422, "document_ocr_rejected", "PDF is invalid") from exc
        if reader.is_encrypted:
            raise _http_error(422, "document_ocr_rejected", "Encrypted PDF requires a decryption workflow")
        if not 1 <= len(reader.pages) <= settings.max_pages:
            raise _http_error(422, "document_ocr_rejected", "PDF page count exceeds OCR policy")
        return
    try:
        with Image.open(path) as image:
            image.verify()
            width, height = image.size
    except (OSError, UnidentifiedImageError) as exc:
        raise _http_error(422, "document_ocr_rejected", "Image is invalid") from exc
    if width < 1 or height < 1 or width * height > settings.max_page_pixels:
        raise _http_error(422, "document_ocr_rejected", "Image pixel count exceeds OCR policy")


def _render_results(
    results: Iterable[object],
    settings: OcrSettings,
    max_chars: int,
) -> tuple[str, dict[str, object]]:
    parts: list[str] = []
    length = 0
    lines = 0
    discarded = 0
    scores: list[float] = []
    page_numbers: set[int] = set()
    current_page: int | None = None

    def add(value: str) -> None:
        nonlocal length
        addition = len(value) + (1 if parts else 0)
        if length + addition > max_chars:
            raise ValueError("OCR output exceeds the configured text limit")
        parts.append(value)
        length += addition

    for result in results:
        payload = getattr(result, "json", None)
        if not isinstance(payload, dict) or not isinstance(payload.get("res"), dict):
            raise ValueError("OCR engine returned an invalid result")
        content = payload["res"]
        page_index = content.get("page_index")
        page_number = 1 if page_index is None else _bounded_int(page_index, 0, settings.max_pages - 1) + 1
        page_numbers.add(page_number)
        texts = content.get("rec_texts")
        raw_scores = content.get("rec_scores")
        boxes = content.get("rec_boxes")
        if not isinstance(texts, list) or not isinstance(raw_scores, list) or not isinstance(boxes, list):
            raise ValueError("OCR engine result arrays are missing")
        if len(texts) != len(raw_scores) or len(texts) != len(boxes):
            raise ValueError("OCR engine result arrays have inconsistent lengths")
        for text, raw_score, raw_box in zip(texts, raw_scores, boxes, strict=True):
            if not isinstance(text, str) or not text.strip():
                discarded += 1
                continue
            if any(not character.isprintable() for character in text):
                raise ValueError("OCR recognized text contains control characters")
            if isinstance(raw_score, bool) or not isinstance(raw_score, int | float):
                raise ValueError("OCR confidence has an invalid type")
            score = float(raw_score)
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("OCR confidence is outside the valid range")
            if score < settings.min_confidence:
                discarded += 1
                continue
            box = _box(raw_box, settings.max_page_pixels)
            if current_page != page_number:
                add(f"[[page:{page_number}]]")
                current_page = page_number
            add(f"[[region:{','.join(map(str, box))};confidence:{score:.4f}]]")
            add(text.strip())
            lines += 1
            scores.append(score)
            if lines > settings.max_lines:
                raise ValueError("OCR line count exceeds policy")
    if not scores:
        raise ValueError("OCR produced no text above the confidence threshold")
    metadata: dict[str, object] = {
        "format": "OCR text",
        "locator_scheme": "page-region-v1",
        "page_count": len(page_numbers),
        "line_count": lines,
        "discarded_line_count": discarded,
        "mean_confidence": round(sum(scores) / len(scores), 6),
        "minimum_confidence": round(min(scores), 6),
        "detection_model": "PP-OCRv5_server_det",
        "recognition_model": "PP-OCRv5_server_rec",
        "detection_model_sha256": settings.detection_model_sha256,
        "recognition_model_sha256": settings.recognition_model_sha256,
        "paddlepaddle_version": settings.paddlepaddle_version,
    }
    return "\n".join(parts), metadata


def _box(value: object, maximum_pixels: int) -> tuple[int, int, int, int]:
    if not isinstance(value, list | tuple) or len(value) != 4:
        raise ValueError("OCR region box is invalid")
    x1, y1, x2, y2 = (_bounded_int(item, 0, maximum_pixels) for item in value)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("OCR region box has invalid geometry")
    return x1, y1, x2, y2


def _bounded_int(value: object, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("OCR integer field is invalid")
    parsed = int(value)
    if parsed != value:
        raise ValueError("OCR integer field is invalid")
    if parsed < minimum or parsed > maximum:
        raise ValueError("OCR integer field is outside policy")
    return parsed


def _directory_digest(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
    file_count = 0
    for path in files:
        relative = path.relative_to(root).as_posix()
        entry = path.lstat()
        if stat.S_ISDIR(entry.st_mode):
            continue
        if not stat.S_ISREG(entry.st_mode) or path.is_symlink():
            raise RuntimeError("OCR model directory contains a non-regular entry")
        file_digest = _file_digest(path)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\n")
        file_count += 1
    if not file_count:
        raise RuntimeError("OCR model directory is empty")
    return digest.hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def run() -> None:
    settings = OcrSettings()
    home = Path(os.environ["HOME"]) if "HOME" in os.environ else Path(tempfile.gettempdir()) / "ocr-home"
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        access_log=False,
        server_header=False,
        timeout_keep_alive=5,
        limit_concurrency=settings.limit_concurrency,
        ssl_certfile=settings.tls_cert_file or None,
        ssl_keyfile=settings.tls_key_file or None,
        ssl_cert_reqs=ssl.CERT_REQUIRED if settings.tls_client_ca_file else ssl.CERT_NONE,
        ssl_ca_certs=settings.tls_client_ca_file or None,
    )


if __name__ == "__main__":
    run()
