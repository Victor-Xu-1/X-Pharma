from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import socket
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from PIL import Image, ImageDraw, ImageFont

from pharma_intel.ingest.parser_client import (
    InProcessDocumentParser,
    OcrFallbackDocumentParser,
    ParserServiceClient,
)
from services.ocr.service import OcrSettings, PaddleOcrEngine, _directory_digest, create_app

TOKEN = "local-ocr-acceptance-token-123456789012345"  # noqa: S105
EXPECTED_FRAGMENTS = ("EGFR", "靶点", "IC50", "12 nM", "临床二期", "Clinical Phase 2")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real PP-OCRv5 service acceptance checks")
    parser.add_argument(
        "--model-root",
        type=Path,
        default=Path.home() / ".paddlex" / "official_models",
    )
    parser.add_argument(
        "--font",
        type=Path,
        default=Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    detection = (args.model_root / "PP-OCRv5_server_det").resolve(strict=True)
    recognition = (args.model_root / "PP-OCRv5_server_rec").resolve(strict=True)
    if not args.font.is_absolute() or not args.font.is_file() or args.font.is_symlink():
        raise RuntimeError("Acceptance font must be an absolute regular file")
    settings = OcrSettings(
        _env_file=None,
        token=TOKEN,
        detection_model_dir=detection,
        recognition_model_dir=recognition,
        detection_model_sha256=_directory_digest(detection),
        recognition_model_sha256=_directory_digest(recognition),
        paddleocr_version="3.5.0",
        paddlepaddle_version="3.3.1",
    )
    started = time.perf_counter()
    app = create_app(settings, PaddleOcrEngine(settings))
    image = _scan_image(args.font)
    samples = {"scan.png": _encode(image, "PNG"), "scan.pdf": _encode(image, "PDF")}
    results: dict[str, object] = {}
    with _serve(app) as service_url:
        parser = OcrFallbackDocumentParser(
            InProcessDocumentParser(),
            ParserServiceClient(
                service_url,
                TOKEN,
                connect_timeout_seconds=5,
                request_timeout_seconds=120,
                max_file_bytes=settings.max_file_bytes,
                verify=False,
                service_name="isolated OCR",
                emit_ocr_required=False,
            ),
        )
        with tempfile.TemporaryDirectory(prefix="pharma-ocr-acceptance-") as temporary_directory:
            root = Path(temporary_directory)
            for filename, payload in samples.items():
                source = root / filename
                source.write_bytes(payload)
                result = parser.parse(source, 100_000)
                text = " ".join(result.text.split())
                canonical_text = "".join(text.split())
                missing = [
                    fragment for fragment in EXPECTED_FRAGMENTS if "".join(fragment.split()) not in canonical_text
                ]
                if missing:
                    raise RuntimeError(f"OCR acceptance text is missing required fragments: {missing}; text={text!r}")
                if result.metadata["locator_scheme"] != "page-region-v1":
                    raise RuntimeError("OCR acceptance response has no page-region provenance")
                results[filename] = {
                    "source_sha256": hashlib.sha256(payload).hexdigest(),
                    "text_sha256": hashlib.sha256(result.text.encode("utf-8")).hexdigest(),
                    "recognized_text": text,
                    "metadata": result.metadata,
                    "parser_name": result.parser_name,
                    "parser_version": result.parser_version,
                }
    report = {
        "schema": "pharma.local-ocr-acceptance.v1",
        "schema_version": 1,
        "category": "ocr_acceptance",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "environment": "local-wsl-real-pp-ocr",
        "production_claim": False,
        "credentials_recorded": False,
        "real_model": True,
        "real_http": True,
        "typed_parser_fallback": True,
        "protocol_version": 1,
        "runtime": {
            "paddleocr": importlib.metadata.version("paddleocr"),
            "paddlepaddle": importlib.metadata.version("paddlepaddle"),
        },
        "model_digests": {
            "PP-OCRv5_server_det": settings.detection_model_sha256,
            "PP-OCRv5_server_rec": settings.recognition_model_sha256,
        },
        "required_fragments": list(EXPECTED_FRAGMENTS),
        "samples": results,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        _write_atomic(args.output, rendered)
    print(rendered, end="")
    return 0


def _scan_image(font_path: Path) -> Image.Image:
    image = Image.new("RGB", (1500, 340), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), 56)
    draw.text((60, 55), "EGFR 靶点 活性 IC50 12 nM", font=font, fill="black")
    draw.text((60, 180), "临床二期 Clinical Phase 2", font=font, fill="black")
    return image


def _encode(image: Image.Image, output_format: str) -> bytes:
    output = BytesIO()
    image.save(output, format=output_format, resolution=150)
    return output.getvalue()


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.chmod(0o640)
    temporary_path.replace(path)


@contextmanager
def _serve(app: Any) -> Iterator[str]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
    config = uvicorn.Config(app, host="127.0.0.1", port=port, access_log=False, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="ocr-acceptance-server", daemon=True)
    thread.start()
    service_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{service_url}/health/ready", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        server.should_exit = True
        thread.join(timeout=10)
        raise RuntimeError("OCR acceptance HTTP service did not become ready")
    try:
        yield service_url
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        if thread.is_alive():
            raise RuntimeError("OCR acceptance HTTP service did not stop")


if __name__ == "__main__":
    raise SystemExit(main())
