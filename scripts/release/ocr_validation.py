from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.core import SHA256_PATTERN
from scripts.release.contracts.parser import (
    OCR_ACCEPTANCE_FIELDS,
    OCR_ACCEPTANCE_FRAGMENTS,
    OCR_ACCEPTANCE_REPORT,
    OCR_ACCEPTANCE_SAMPLES,
    OCR_ACCEPTANCE_SCHEMA,
    OCR_METADATA_FIELDS,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_ocr_acceptance_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("OCR acceptance attachments are invalid")
    reports = [item for item in raw_attachments if isinstance(item, dict) and item.get("path") == OCR_ACCEPTANCE_REPORT]
    if len(reports) != 1:
        raise ReleaseEvidenceError("OCR acceptance requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / OCR_ACCEPTANCE_REPORT, "OCR acceptance report")
    if (
        set(report) != OCR_ACCEPTANCE_FIELDS
        or report.get("schema") != OCR_ACCEPTANCE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("category") != "ocr_acceptance"
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl-real-pp-ocr"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
        or report.get("real_model") is not True
        or report.get("real_http") is not True
        or report.get("typed_parser_fallback") is not True
        or report.get("protocol_version") != 1
    ):
        raise ReleaseEvidenceError("OCR acceptance report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "OCR statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "OCR generated_at")
    maximum_age_hours = policy.categories["ocr"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("OCR acceptance report is outside the allowed evidence window")
    if report.get("runtime") != {"paddleocr": "3.5.0", "paddlepaddle": "3.3.1"}:
        raise ReleaseEvidenceError("OCR runtime version contract is invalid")
    model_digests = report.get("model_digests")
    if (
        not isinstance(model_digests, dict)
        or set(model_digests) != {"PP-OCRv5_server_det", "PP-OCRv5_server_rec"}
        or any(
            not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None for value in model_digests.values()
        )
    ):
        raise ReleaseEvidenceError("OCR model digest contract is invalid")
    if report.get("required_fragments") != list(OCR_ACCEPTANCE_FRAGMENTS):
        raise ReleaseEvidenceError("OCR required text contract is invalid")
    samples = report.get("samples")
    if not isinstance(samples, dict) or set(samples) != OCR_ACCEPTANCE_SAMPLES:
        raise ReleaseEvidenceError("OCR sample inventory is incomplete")
    for filename, sample in samples.items():
        if not isinstance(sample, dict) or set(sample) != {
            "source_sha256",
            "text_sha256",
            "recognized_text",
            "metadata",
            "parser_name",
            "parser_version",
        }:
            raise ReleaseEvidenceError(f"OCR sample contract is invalid: {filename}")
        recognized_text = sample.get("recognized_text")
        canonical_text = "".join(recognized_text.split()) if isinstance(recognized_text, str) else ""
        if (
            not isinstance(sample.get("source_sha256"), str)
            or SHA256_PATTERN.fullmatch(sample["source_sha256"]) is None
            or not isinstance(sample.get("text_sha256"), str)
            or SHA256_PATTERN.fullmatch(sample["text_sha256"]) is None
            or not isinstance(recognized_text, str)
            or not 0 < len(recognized_text) <= 20_000
            or any("".join(fragment.split()) not in canonical_text for fragment in OCR_ACCEPTANCE_FRAGMENTS)
            or sample.get("parser_name") != "paddleocr"
            or sample.get("parser_version") != "3.5.0"
        ):
            raise ReleaseEvidenceError(f"OCR sample result is invalid: {filename}")
        metadata = sample.get("metadata")
        if not isinstance(metadata, dict) or set(metadata) != OCR_METADATA_FIELDS:
            raise ReleaseEvidenceError(f"OCR provenance metadata is invalid: {filename}")
        integer_fields = ("page_count", "line_count", "discarded_line_count")
        if any(
            not isinstance(metadata.get(field), int) or isinstance(metadata[field], bool) for field in integer_fields
        ):
            raise ReleaseEvidenceError(f"OCR provenance metadata is invalid: {filename}")
        mean_confidence = metadata.get("mean_confidence")
        minimum_confidence = metadata.get("minimum_confidence")
        if (
            metadata.get("format") != "OCR text"
            or metadata.get("locator_scheme") != "page-region-v1"
            or metadata["page_count"] < 1
            or metadata["line_count"] < 1
            or metadata["discarded_line_count"] < 0
            or not isinstance(mean_confidence, int | float)
            or isinstance(mean_confidence, bool)
            or not 0 <= mean_confidence <= 1
            or not isinstance(minimum_confidence, int | float)
            or isinstance(minimum_confidence, bool)
            or not 0 <= minimum_confidence <= mean_confidence
            or metadata.get("detection_model") != "PP-OCRv5_server_det"
            or metadata.get("recognition_model") != "PP-OCRv5_server_rec"
            or metadata.get("detection_model_sha256") != model_digests["PP-OCRv5_server_det"]
            or metadata.get("recognition_model_sha256") != model_digests["PP-OCRv5_server_rec"]
            or metadata.get("paddlepaddle_version") != "3.3.1"
        ):
            raise ReleaseEvidenceError(f"OCR provenance metadata is invalid: {filename}")
    duration = report.get("elapsed_seconds")
    if not isinstance(duration, int | float) or isinstance(duration, bool) or not 0 < duration <= 600:
        raise ReleaseEvidenceError("OCR acceptance duration is invalid")
