from __future__ import annotations

INGESTION_READINESS_EVIDENCE_SCHEMA = "pharma.ingestion-platform-readiness-evidence.v1"


INGESTION_READINESS_SCHEMA = "pharma.ingestion-readiness.v1"


INGESTION_READINESS_REPORT = "report.json"


INGESTION_PILOT_SCHEMA = "pharma.ingestion-pilot-evidence.v2"


INGESTION_PILOT_REPORT = "ingestion-report.json"


AUTOMATIC_INGESTION_SCHEMA = "pharma.automatic-ingestion-evidence.v4"


AUTOMATIC_INGESTION_REPORT = "automatic-ingestion-report.json"


INGESTION_PILOT_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "source_id",
        "source_type",
        "dataset_key",
        "license_id",
        "source_files",
        "versions",
        "governance",
        "runs",
        "search",
        "source_content_created_by_test",
    }
)


AUTOMATIC_INGESTION_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "source_id",
        "source_type",
        "dataset_key",
        "license_id",
        "trigger",
        "workflow",
        "versions",
        "governance",
        "search",
    }
)


INGESTION_SOURCE_FIELDS = frozenset(
    {
        "schema_version",
        "source_id",
        "source_type",
        "connector_id",
        "authoritative_inventory",
        "discovered",
        "stable",
        "oversized",
        "excluded",
        "error_count",
        "configuration_error_count",
    }
)


INGESTION_SOURCE_CONNECTORS = {
    "folder": "folder-v1",
    "http_manifest": "http-manifest-v1",
    "s3_snapshot": "s3-snapshot-v1",
    "sftp_snapshot": "sftp-snapshot-v1",
    "smb_snapshot": "smb-snapshot-v1",
}


INGESTION_READINESS_CONNECTOR_IDS = frozenset(INGESTION_SOURCE_CONNECTORS.values())


INGESTION_COUNTER_FIELDS = frozenset({"discovered", "unchanged", "unstable", "excluded", "failed"})


INGESTION_GOVERNANCE_FIELDS = frozenset(
    {
        "configured_model",
        "extraction_runs",
        "successful_extraction_runs",
        "failed_extraction_runs",
        "configured_model_runs",
        "input_tokens",
        "output_tokens",
        "segments",
        "accounted_segments",
        "staged_facts",
        "quote_verified_facts",
    }
)


INGESTION_READINESS_SERVICES = frozenset({"postgres", "opensearch", "temporal", "parser", "clamav", "worker"})
