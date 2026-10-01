from __future__ import annotations

RECORD_CONSISTENCY_SCHEMA = "pharma.record-consistency-acceptance.v1"


RECORD_CONSISTENCY_REPORT = "report.json"


RECORD_CONSISTENCY_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "controlled_fixture",
        "credentials_recorded",
        "activity_id",
        "target_id",
        "provenance_id",
        "source_version_id",
        "source_document_id",
        "source_locator",
        "activity_sha256",
        "provenance_sha256",
        "export_row_sha256",
        "web_operations",
        "mcp_tools",
        "mcp_protocol_version",
        "billed_operations",
        "unique_settlements",
        "export_dataset",
        "export_record_count",
        "export_manifest_verified",
        "same_authority_identifiers",
        "same_source_version",
        "same_source_locator",
        "cleanup",
    }
)


RECORD_CONSISTENCY_WEB_OPERATIONS = frozenset({"get_bioactivities", "get_record_provenance"})


RECORD_CONSISTENCY_MCP_TOOLS = frozenset(
    {
        "get_bioactivity_landscape",
        "get_record_provenance",
        "create_data_export",
        "get_data_export",
        "read_data_export",
    }
)


DATABASE_ACCEPTANCE_SCHEMA = "pharma.local-database-acceptance.v1"


DATABASE_ACCEPTANCE_REPORT = "report.json"


DATABASE_ACCEPTANCE_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "credentials_recorded",
        "database",
        "rls",
        "runtime_hygiene",
        "search",
        "hybrid_search",
        "duration_seconds",
    }
)
