from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
from pathlib import Path


def _set_limit(limit: int, soft: int, hard: int | None = None) -> None:
    current_soft, current_hard = resource.getrlimit(limit)
    requested_hard = soft if hard is None else hard
    if current_hard != resource.RLIM_INFINITY:
        requested_hard = min(requested_hard, current_hard)
    requested_soft = min(soft, requested_hard)
    resource.setrlimit(limit, (requested_soft, requested_hard))


def _apply_limits(*, memory_bytes: int, cpu_seconds: int, output_bytes: int) -> None:
    os.umask(0o077)
    _set_limit(resource.RLIMIT_CORE, 0)
    _set_limit(resource.RLIMIT_AS, memory_bytes)
    _set_limit(resource.RLIMIT_CPU, cpu_seconds, cpu_seconds + 1)
    _set_limit(resource.RLIMIT_FSIZE, output_bytes)
    _set_limit(resource.RLIMIT_NOFILE, 128)
    try:
        os.nice(5)
    except OSError:
        pass


def _safe_message(value: object) -> str:
    text = str(value)
    return "".join(character if character.isprintable() else "?" for character in text)[:1000]


def _write_envelope(path: Path, payload: dict[str, object]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--max-chars", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--cpu-seconds", type=int, required=True)
    parser.add_argument("--output-bytes", type=int, required=True)
    args = parser.parse_args()
    _apply_limits(memory_bytes=args.memory_bytes, cpu_seconds=args.cpu_seconds, output_bytes=args.output_bytes)

    from pharma_intel.ingest.parser_protocol import PARSER_PROTOCOL_VERSION
    from pharma_intel.ingest.parsers import DocumentOcrRequired, DocumentParseError, parse_document

    try:
        parsed = parse_document(args.input, args.max_chars)
        text_sha256 = hashlib.sha256(parsed.text.encode("utf-8")).hexdigest()
        envelope: dict[str, object] = {
            "protocol_version": PARSER_PROTOCOL_VERSION,
            "status": "succeeded",
            "result": {
                "protocol_version": PARSER_PROTOCOL_VERSION,
                "source_sha256": args.source_sha256,
                "text": parsed.text,
                "text_sha256": text_sha256,
                "metadata": parsed.metadata,
                "parser_name": parsed.parser_name,
                "parser_version": parsed.parser_version,
            },
        }
        exit_code = 0
    except DocumentOcrRequired as exc:
        envelope = {
            "protocol_version": PARSER_PROTOCOL_VERSION,
            "status": "rejected",
            "error_code": "document_ocr_required",
            "error_message": _safe_message(exc),
        }
        exit_code = 2
    except DocumentParseError as exc:
        envelope = {
            "protocol_version": PARSER_PROTOCOL_VERSION,
            "status": "rejected",
            "error_code": "document_parse_rejected",
            "error_message": _safe_message(exc),
        }
        exit_code = 2
    except BaseException:
        envelope = {
            "protocol_version": PARSER_PROTOCOL_VERSION,
            "status": "failed",
            "error_code": "parser_process_failed",
            "error_message": "The isolated parser process failed",
        }
        exit_code = 3
    _write_envelope(args.output, envelope)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
