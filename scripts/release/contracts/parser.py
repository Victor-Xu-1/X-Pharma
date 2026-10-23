from __future__ import annotations

from pathlib import Path

from scripts.release.contracts.parser_dependencies import parser_document_contracts

PARSER_SANDBOX_SCHEMA = "pharma.local-parser-sandbox-acceptance.v3"


PARSER_SANDBOX_REPORT = "report.json"


PARSER_SANDBOX_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "credentials_recorded",
        "parser_backend",
        "document_count",
        "documents",
        "unauthorized_status",
        "digest_mismatch_status",
        "duration_seconds",
        "infrastructure",
        "capacity",
        "timeout_recovery",
        "adversarial_corpus",
        "mtls",
        "outbound_network_blocked",
    }
)


PARSER_CAPACITY_FIELDS = frozenset(
    {
        "schema_version",
        "generated_at",
        "status",
        "production_claim",
        "max_concurrent_parses",
        "held_request_status",
        "saturated_request_status",
        "saturated_error_code",
        "retry_after_seconds",
        "recovery_request_status",
        "ready_after_status",
    }
)


PARSER_TIMEOUT_RECOVERY_FIELDS = frozenset(
    {
        "schema_version",
        "generated_at",
        "status",
        "production_claim",
        "timeout_observed",
        "child_processes_after_timeout",
        "recovery_parser_name",
        "recovery_text_sha256",
        "duration_seconds",
    }
)


PARSER_ADVERSARIAL_CORPUS_FIELDS = frozenset(
    {
        "schema_version",
        "generated_at",
        "status",
        "production_claim",
        "case_count",
        "cases",
        "recovery_status",
        "ready_after_status",
    }
)


PARSER_ADVERSARIAL_CASE_CONTRACTS = (
    ("office_path_traversal", ".docx"),
    ("office_duplicate_name", ".xlsx"),
    ("office_symbolic_link", ".pptx"),
    ("office_member_fanout", ".docx"),
    ("office_compression_ratio", ".docx"),
    ("office_encrypted", ".docx"),
    ("pdf_encrypted", ".pdf"),
    ("xml_external_entity", ".xml"),
    ("scientific_malformed", ".sdf"),
)


PARSER_DOCUMENT_CONTRACTS = parser_document_contracts(Path(__file__).resolve().parents[3] / "pyproject.toml")


OCR_ACCEPTANCE_SCHEMA = "pharma.local-ocr-acceptance.v1"


OCR_ACCEPTANCE_REPORT = "report.json"


OCR_ACCEPTANCE_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "category",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "credentials_recorded",
        "real_model",
        "real_http",
        "typed_parser_fallback",
        "protocol_version",
        "runtime",
        "model_digests",
        "required_fragments",
        "samples",
        "elapsed_seconds",
    }
)


OCR_ACCEPTANCE_SAMPLES = frozenset({"scan.png", "scan.pdf"})


OCR_ACCEPTANCE_FRAGMENTS = ("EGFR", "靶点", "IC50", "12 nM", "临床二期", "Clinical Phase 2")


OCR_METADATA_FIELDS = frozenset(
    {
        "format",
        "locator_scheme",
        "page_count",
        "line_count",
        "discarded_line_count",
        "mean_confidence",
        "minimum_confidence",
        "detection_model",
        "recognition_model",
        "detection_model_sha256",
        "recognition_model_sha256",
        "paddlepaddle_version",
    }
)
