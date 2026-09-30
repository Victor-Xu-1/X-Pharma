from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
import threading
import time
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfWriter

from pharma_intel.config import get_settings
from pharma_intel.ingest.parser_sandbox import ParserSandboxTimeout, parse_document_in_sandbox


def _request_headers(payload: bytes, token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Length": str(len(payload)),
        "Content-Type": "application/octet-stream",
        "X-Content-SHA256": hashlib.sha256(payload).hexdigest(),
    }


def probe_capacity_recovery() -> dict[str, object]:
    settings = get_settings()
    if settings.parser_backend != "service":
        raise RuntimeError("Parser capacity acceptance requires PARSER_BACKEND=service")
    payload = b"bounded parser capacity evidence"
    stream_started = threading.Event()
    release_stream = threading.Event()
    first_result: dict[str, Any] = {}

    def held_content() -> Iterator[bytes]:
        stream_started.set()
        if not release_stream.wait(timeout=10):
            raise RuntimeError("Timed out while holding the parser capacity probe stream")
        yield payload

    def run_first_request() -> None:
        try:
            with httpx.Client(timeout=15, trust_env=False) as client:
                response = client.post(
                    f"{settings.parser_service_url.rstrip('/')}/internal/v1/parse",
                    params={"filename": "capacity-held.md", "max_chars": 100_000},
                    headers=_request_headers(payload, settings.parser_service_token),
                    content=held_content(),
                )
            first_result["status"] = response.status_code
        except BaseException as exc:  # pragma: no cover - surfaced in the controlling thread.
            first_result["error"] = f"{type(exc).__name__}: {exc}"

    thread = threading.Thread(target=run_first_request, name="parser-capacity-held-request", daemon=True)
    thread.start()
    if not stream_started.wait(timeout=5):
        raise RuntimeError("The held parser request did not start")
    time.sleep(0.25)
    try:
        with httpx.Client(timeout=10, trust_env=False) as client:
            saturated = client.post(
                f"{settings.parser_service_url.rstrip('/')}/internal/v1/parse",
                params={"filename": "capacity-rejected.md", "max_chars": 100_000},
                headers=_request_headers(payload, settings.parser_service_token),
                content=payload,
            )
    finally:
        release_stream.set()
    thread.join(timeout=15)
    if thread.is_alive():
        raise RuntimeError("The held parser request did not terminate")
    if "error" in first_result:
        raise RuntimeError(f"The held parser request failed: {first_result['error']}")

    with httpx.Client(timeout=10, trust_env=False) as client:
        recovered = client.post(
            f"{settings.parser_service_url.rstrip('/')}/internal/v1/parse",
            params={"filename": "capacity-recovered.md", "max_chars": 100_000},
            headers=_request_headers(payload, settings.parser_service_token),
            content=payload,
        )
        ready = client.get(f"{settings.parser_service_url.rstrip('/')}/health/ready")
    saturated_detail = saturated.json().get("detail", {}) if saturated.content else {}
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "production_claim": False,
        "max_concurrent_parses": 1,
        "held_request_status": first_result.get("status"),
        "saturated_request_status": saturated.status_code,
        "saturated_error_code": saturated_detail.get("code") if isinstance(saturated_detail, dict) else None,
        "retry_after_seconds": saturated.headers.get("Retry-After"),
        "recovery_request_status": recovered.status_code,
        "ready_after_status": ready.status_code,
    }
    if (
        report["held_request_status"] != 200
        or report["saturated_request_status"] != 429
        or report["saturated_error_code"] != "parser_capacity_exhausted"
        or report["retry_after_seconds"] != "1"
        or report["recovery_request_status"] != 200
        or report["ready_after_status"] != 200
    ):
        raise RuntimeError(f"Parser capacity and recovery acceptance failed: {report}")
    return report


def _direct_child_pids(parent_pid: int) -> list[int]:
    children: list[int] = []
    for status_path in Path("/proc").glob("[0-9]*/status"):
        try:
            fields = {
                key: value.strip()
                for line in status_path.read_text(encoding="utf-8").splitlines()
                if ":" in line
                for key, value in [line.split(":", 1)]
            }
            if int(fields.get("PPid", "-1")) == parent_pid:
                children.append(int(status_path.parent.name))
        except (OSError, ValueError):
            continue
    return sorted(children)


def probe_timeout_recovery() -> dict[str, object]:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="pharma-parser-resilience-") as temporary_directory:
        source = Path(temporary_directory) / "timeout.md"
        source.write_text("parser timeout and recovery evidence", encoding="utf-8")
        timeout_observed = False
        try:
            parse_document_in_sandbox(source, 100_000, timeout_seconds=0.001)
        except ParserSandboxTimeout:
            timeout_observed = True
        child_pids = _direct_child_pids(os.getpid())
        recovered = parse_document_in_sandbox(source, 100_000, timeout_seconds=20)
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "production_claim": False,
        "timeout_observed": timeout_observed,
        "child_processes_after_timeout": len(child_pids),
        "recovery_parser_name": recovered.parser_name,
        "recovery_text_sha256": hashlib.sha256(recovered.text.encode("utf-8")).hexdigest(),
        "duration_seconds": round(time.perf_counter() - started, 6),
    }
    if not timeout_observed or child_pids or recovered.parser_name != "text":
        raise RuntimeError(f"Parser timeout process cleanup or recovery failed: {report}")
    return report


def _write_office_archive(path: Path, members: list[tuple[zipfile.ZipInfo | str, bytes]]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members:
            archive.writestr(name, payload)


def _mark_zip_members_encrypted(path: Path) -> None:
    payload = bytearray(path.read_bytes())
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        cursor = 0
        while (cursor := payload.find(signature, cursor)) >= 0:
            flags = int.from_bytes(payload[cursor + flag_offset : cursor + flag_offset + 2], "little")
            payload[cursor + flag_offset : cursor + flag_offset + 2] = (flags | 1).to_bytes(2, "little")
            cursor += len(signature)
    path.write_bytes(payload)


def _adversarial_documents(root: Path) -> list[tuple[str, Path]]:
    traversal = root / "office-path-traversal.docx"
    _write_office_archive(traversal, [("../escape.xml", b"unsafe")])

    duplicate = root / "office-duplicate-name.xlsx"
    _write_office_archive(duplicate, [("xl/workbook.xml", b"one"), ("XL/WORKBOOK.XML", b"two")])

    symlink = root / "office-symbolic-link.pptx"
    symlink_member = zipfile.ZipInfo("ppt/slides/link.xml")
    symlink_member.create_system = 3
    symlink_member.external_attr = (stat.S_IFLNK | 0o777) << 16
    _write_office_archive(symlink, [(symlink_member, b"ppt/slides/slide1.xml")])

    fanout = root / "office-member-fanout.docx"
    _write_office_archive(fanout, [(f"word/item-{index}.xml", b"") for index in range(4097)])

    expansion = root / "office-compression-ratio.docx"
    _write_office_archive(expansion, [("word/document.xml", b"A" * (1024 * 1024 + 1))])

    encrypted_office = root / "office-encrypted.docx"
    _write_office_archive(encrypted_office, [("word/document.xml", b"encrypted")])
    _mark_zip_members_encrypted(encrypted_office)

    encrypted_pdf = root / "pdf-encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("adversarial-corpus-password")
    with encrypted_pdf.open("wb") as handle:
        writer.write(handle)

    xml_entity = root / "xml-external-entity.xml"
    xml_entity.write_text(
        '<?xml version="1.0"?><!DOCTYPE article [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        "<article><body><p>&xxe;</p></body></article>",
        encoding="utf-8",
    )

    malformed_sdf = root / "scientific-malformed.sdf"
    malformed_sdf.write_text("malformed scientific structure\n$$$$\n", encoding="utf-8")

    return [
        ("office_path_traversal", traversal),
        ("office_duplicate_name", duplicate),
        ("office_symbolic_link", symlink),
        ("office_member_fanout", fanout),
        ("office_compression_ratio", expansion),
        ("office_encrypted", encrypted_office),
        ("pdf_encrypted", encrypted_pdf),
        ("xml_external_entity", xml_entity),
        ("scientific_malformed", malformed_sdf),
    ]


def probe_adversarial_corpus() -> dict[str, object]:
    settings = get_settings()
    if settings.parser_backend != "service":
        raise RuntimeError("Adversarial corpus acceptance requires PARSER_BACKEND=service")
    base_url = settings.parser_service_url.rstrip("/")
    cases: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="pharma-parser-adversarial-") as temporary_directory:
        documents = _adversarial_documents(Path(temporary_directory))
        with httpx.Client(timeout=30, trust_env=False) as client:
            for name, path in documents:
                payload = path.read_bytes()
                response = client.post(
                    f"{base_url}/internal/v1/parse",
                    params={"filename": path.name, "max_chars": 100_000},
                    headers=_request_headers(payload, settings.parser_service_token),
                    content=payload,
                )
                detail = response.json().get("detail", {}) if response.content else {}
                cases.append(
                    {
                        "name": name,
                        "suffix": path.suffix,
                        "status": response.status_code,
                        "error_code": detail.get("code") if isinstance(detail, dict) else None,
                    }
                )
            recovery_payload = b"parser adversarial corpus recovery evidence"
            recovered = client.post(
                f"{base_url}/internal/v1/parse",
                params={"filename": "adversarial-recovery.md", "max_chars": 100_000},
                headers=_request_headers(recovery_payload, settings.parser_service_token),
                content=recovery_payload,
            )
            ready = client.get(f"{base_url}/health/ready")

    report = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "production_claim": False,
        "case_count": len(cases),
        "cases": cases,
        "recovery_status": recovered.status_code,
        "ready_after_status": ready.status_code,
    }
    if (
        len(cases) != 9
        or any(case["status"] != 422 or case["error_code"] != "document_parse_rejected" for case in cases)
        or recovered.status_code != 200
        or ready.status_code != 200
    ):
        raise RuntimeError(f"Parser adversarial corpus acceptance failed: {report}")
    return report


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("capacity", "timeout", "corpus"))
    arguments = parser.parse_args()
    if arguments.mode == "capacity":
        report = probe_capacity_recovery()
    elif arguments.mode == "timeout":
        report = probe_timeout_recovery()
    else:
        report = probe_adversarial_corpus()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    run()
