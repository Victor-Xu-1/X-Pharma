from __future__ import annotations

import hashlib
import hmac
import math
import os
import re
import ssl
import tempfile
from functools import partial
from pathlib import Path

import anyio
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, Request
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from pharma_intel.ingest.parser_protocol import (
    PARSER_PROTOCOL_VERSION,
    SUPPORTED_DOCUMENT_SUFFIXES,
    ParserResponse,
)
from pharma_intel.ingest.parser_sandbox import ParserSandboxError, ParserSandboxTimeout, parse_document_in_sandbox
from pharma_intel.ingest.parsers import DocumentOcrRequired, DocumentParseError


class ParserServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PARSER_SERVICE_", extra="ignore")

    host: str = "127.0.0.1"
    port: int = Field(default=8070, ge=1, le=65_535)
    token: SecretStr = Field()
    max_file_bytes: int = Field(default=268_435_456, ge=1024, le=1_073_741_824)
    max_text_chars: int = Field(default=50_000_000, ge=1_000, le=200_000_000)
    parser_timeout_seconds: float = Field(default=120, ge=1, le=3600)
    parser_cpu_seconds: int = Field(default=90, ge=1, le=3600)
    parser_memory_bytes: int = Field(default=2_147_483_648, ge=268_435_456, le=17_179_869_184)
    request_chunk_bytes: int = Field(default=1_048_576, ge=4096, le=8_388_608)
    max_concurrent_parses: int = Field(default=1, ge=1, le=32)
    capacity_wait_seconds: float = Field(default=30, ge=0.01, le=300)
    limit_concurrency: int = Field(default=8, ge=1, le=256)
    tls_cert_file: str = ""
    tls_key_file: str = ""
    tls_client_ca_file: str = ""

    def validate_runtime(self) -> None:
        if len(self.token.get_secret_value().encode("utf-8")) < 32:
            raise RuntimeError("PARSER_SERVICE_TOKEN must contain at least 32 bytes")
        if bool(self.tls_cert_file) != bool(self.tls_key_file):
            raise RuntimeError("Parser TLS certificate and key must be configured together")
        if self.tls_client_ca_file and not self.tls_cert_file:
            raise RuntimeError("Parser mTLS client CA requires a TLS server certificate and key")
        if self.tls_client_ca_file and not Path(self.tls_client_ca_file).is_absolute():
            raise RuntimeError("Parser mTLS client CA path must be absolute")


def create_app(settings: ParserServiceSettings) -> FastAPI:
    settings.validate_runtime()
    parse_slots = anyio.Semaphore(settings.max_concurrent_parses)
    app = FastAPI(
        title="Pharma Parser Sandbox",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/health/live")
    def live() -> dict[str, object]:
        return {"status": "ok", "protocol_version": PARSER_PROTOCOL_VERSION}

    @app.get("/health/ready")
    def ready() -> dict[str, object]:
        return {"status": "ready", "protocol_version": PARSER_PROTOCOL_VERSION}

    @app.post("/internal/v1/parse", response_model=ParserResponse)
    async def parse(
        request: Request,
        filename: str = Query(min_length=1, max_length=255),
        max_chars: int = Query(ge=1_000),
        authorization: str = Header(default=""),
        content_length: str = Header(default=""),
        content_type: str = Header(default=""),
        content_encoding: str = Header(default=""),
        x_content_sha256: str = Header(default=""),
    ) -> ParserResponse:
        expected_authorization = f"Bearer {settings.token.get_secret_value()}"
        if not hmac.compare_digest(authorization, expected_authorization):
            raise HTTPException(
                status_code=401,
                detail={"code": "parser_authentication_required", "message": "Parser authentication failed"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        if content_type.partition(";")[0].strip().casefold() != "application/octet-stream":
            raise HTTPException(
                status_code=415,
                detail={"code": "unsupported_media_type", "message": "Parser input must be application/octet-stream"},
            )
        if content_encoding and content_encoding.casefold() != "identity":
            raise HTTPException(
                status_code=415,
                detail={
                    "code": "content_encoding_rejected",
                    "message": "Compressed HTTP request bodies are not accepted",
                },
            )
        size_bytes = _content_length(content_length, settings.max_file_bytes)
        if max_chars > settings.max_text_chars:
            raise HTTPException(
                status_code=413,
                detail={"code": "text_limit_exceeded", "message": "Requested text limit exceeds service policy"},
            )
        suffix = _safe_suffix(filename)
        if re.fullmatch(r"[0-9a-f]{64}", x_content_sha256) is None:
            raise HTTPException(
                status_code=400,
                detail={"code": "source_digest_invalid", "message": "A valid source SHA-256 is required"},
            )

        try:
            with anyio.fail_after(settings.capacity_wait_seconds):
                await parse_slots.acquire()
        except TimeoutError as exc:
            raise HTTPException(
                status_code=429,
                detail={"code": "parser_capacity_exhausted", "message": "Parser capacity is temporarily exhausted"},
                headers={"Retry-After": str(max(1, math.ceil(settings.capacity_wait_seconds)))},
            ) from exc
        try:
            with tempfile.TemporaryDirectory(prefix="pharma-parser-request-") as temporary_directory:
                input_path = Path(temporary_directory) / f"source{suffix}"
                digest = hashlib.sha256()
                received = 0
                descriptor = os.open(input_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
                with os.fdopen(descriptor, "wb") as destination:
                    async for chunk in request.stream():
                        received += len(chunk)
                        if received > size_bytes or received > settings.max_file_bytes:
                            raise HTTPException(
                                status_code=413,
                                detail={
                                    "code": "file_too_large",
                                    "message": "Parser input exceeded its declared limit",
                                },
                            )
                        destination.write(chunk)
                        digest.update(chunk)
                if received != size_bytes:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "code": "content_length_mismatch",
                            "message": "Parser input length did not match Content-Length",
                        },
                    )
                if not hmac.compare_digest(digest.hexdigest(), x_content_sha256):
                    raise HTTPException(
                        status_code=400,
                        detail={"code": "source_digest_mismatch", "message": "Parser input SHA-256 did not match"},
                    )
                try:
                    parsed = await anyio.to_thread.run_sync(
                        partial(
                            parse_document_in_sandbox,
                            input_path,
                            max_chars,
                            source_sha256=x_content_sha256,
                            timeout_seconds=settings.parser_timeout_seconds,
                            memory_bytes=settings.parser_memory_bytes,
                            cpu_seconds=settings.parser_cpu_seconds,
                        )
                    )
                except ParserSandboxTimeout as exc:
                    raise HTTPException(
                        status_code=422,
                        detail={"code": "parser_timeout", "message": str(exc)},
                    ) from exc
                except ParserSandboxError as exc:
                    raise HTTPException(
                        status_code=503,
                        detail={"code": "parser_sandbox_unavailable", "message": str(exc)},
                    ) from exc
                except DocumentOcrRequired as exc:
                    raise HTTPException(
                        status_code=422,
                        detail={"code": "document_ocr_required", "message": str(exc)},
                    ) from exc
                except DocumentParseError as exc:
                    raise HTTPException(
                        status_code=422,
                        detail={"code": "document_parse_rejected", "message": str(exc)},
                    ) from exc
                text_sha256 = hashlib.sha256(parsed.text.encode("utf-8")).hexdigest()
                return ParserResponse(
                    source_sha256=x_content_sha256,
                    text=parsed.text,
                    text_sha256=text_sha256,
                    metadata=parsed.metadata,
                    parser_name=parsed.parser_name,
                    parser_version=parsed.parser_version,
                )
        finally:
            parse_slots.release()

    return app


def _content_length(value: str, max_file_bytes: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=411,
            detail={"code": "content_length_required", "message": "A valid Content-Length is required"},
        ) from exc
    if parsed < 1:
        raise HTTPException(
            status_code=400,
            detail={"code": "empty_input", "message": "Parser input cannot be empty"},
        )
    if parsed > max_file_bytes:
        raise HTTPException(
            status_code=413,
            detail={"code": "file_too_large", "message": "Parser input exceeds service policy"},
        )
    return parsed


def _safe_suffix(filename: str) -> str:
    if "\x00" in filename or "/" in filename or "\\" in filename or Path(filename).name != filename:
        raise HTTPException(
            status_code=400,
            detail={"code": "filename_invalid", "message": "Parser filename is invalid"},
        )
    suffix = Path(filename).suffix.casefold()
    if suffix not in SUPPORTED_DOCUMENT_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail={"code": "document_type_unsupported", "message": "Document type is not supported"},
        )
    return suffix


def run() -> None:
    settings = ParserServiceSettings(token=SecretStr(os.environ.get("PARSER_SERVICE_TOKEN", "")))
    settings.validate_runtime()
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
