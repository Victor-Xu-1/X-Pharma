from __future__ import annotations

CLEAN_SOURCE_SCHEMA = "pharma.clean-source-reproducibility.v1"


CLEAN_SOURCE_REPORT = "report.json"


PERFORMANCE_BASELINE_SCHEMA = "pharma.local-performance-baseline.v1"


PERFORMANCE_BASELINE_REPORT = "report.json"


ANTI_EXTRACTION_BASELINE_SCHEMA = "pharma.mcp-anti-extraction-acceptance.v1"


ANTI_EXTRACTION_BASELINE_REPORT = "report.json"


ANTI_EXTRACTION_BASELINE_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "controlled_fixture",
        "credentials_recorded",
        "auth_profile",
        "production_oidc_covered",
        "protocol_version",
        "scenarios",
        "database",
        "cleanup",
        "assertions",
        "duration_seconds",
    }
)


ANTI_EXTRACTION_BASELINE_SCENARIOS = {
    "normal_billed_query": "passed",
    "deep_pagination": "bounded-and-tamper-denied",
    "alphabet_partition_across_clients": "denied",
    "numeric_partition": "denied",
    "network_rotation": "denied",
    "credential_rotation": "denied",
    "unauthorized_export": "denied",
    "credential_after_revocation": "denied",
    "human_risk_console": "passed",
}


ANTI_EXTRACTION_BASELINE_ASSERTIONS = frozenset(
    {
        "normal_mcp_query_settled",
        "deep_pagination_continuation_withheld",
        "tampered_pagination_cursor_denied",
        "alphabet_partition_cross_client_denied",
        "numeric_partition_denied",
        "network_rotation_denied",
        "credential_rotation_denied",
        "unauthorized_export_denied",
        "risk_events_visible_to_human_operator",
        "credential_revocation_enforced",
        "no_active_reservations_after",
        "no_unauthorized_export_created",
        "isolated_database_destroyed",
        "credentials_absent_from_report",
    }
)


CLEAN_SOURCE_CHECKS = frozenset(
    {
        "backend_and_frontend_tests",
        "clean_source_manifest_matches",
        "committed_source_only",
        "compose_and_kubernetes_render",
        "frontend_production_build",
        "historical_runtime_evidence_excluded",
        "locked_installation",
        "migration_database_isolated",
        "migration_upgrade_and_rollback",
        "portable_source_paths",
        "runtime_image_build",
        "runtime_image_non_root",
        "runtime_image_smoke",
        "temporary_database_removed",
        "temporary_image_tag_removed",
        "temporary_source_removed",
    }
)


CLEAN_SOURCE_COMMANDS = (
    "locked Python installation",
    "locked frontend installation",
    "quality, tests, build and manifest rendering",
    "PostgreSQL migration upgrade and rollback",
    "production application image build",
    "non-root runtime image smoke",
)


PERFORMANCE_BASELINE_ASSERTIONS = frozenset(
    {
        "all_mixed_requests_succeeded",
        "both_public_entries_exercised",
        "sustained_duration_reached",
        "peak_concurrency_exceeds_sustained",
        "one_unique_settlement_per_mcp_success",
        "settlement_delta_matches_mcp_successes",
        "charged_and_consumed_deltas_match",
        "no_load_reservation_leak",
        "no_final_reservation_leak",
        "web_p95_within_local_threshold",
        "mcp_p95_within_local_threshold",
        "protocol_baseline_negotiated",
    }
)


PERFORMANCE_RACE_ASSERTIONS = frozenset(
    {
        "one_durable_settlement",
        "racing_requests_do_not_create_unexpected_errors",
        "terminal_replay_is_marked",
        "no_reservation_leak",
    }
)


SECURITY_REQUIRED_FILES = frozenset(
    {
        "api.cdx.json",
        "api.grype-gate.json",
        "api.grype.json",
        "api.syft.json",
        "audit-requirements.txt",
        "evidence-manifest.json",
        "gitleaks.json",
        "ocr.cdx.json",
        "ocr.grype-gate.json",
        "ocr.grype.json",
        "ocr.syft.json",
        "pip-audit.json",
        "pnpm-audit.json",
        "postgres.cdx.json",
        "postgres.grype-gate.json",
        "postgres.grype.json",
        "postgres.syft.json",
        "semgrep.json",
        "source.cdx.json",
        "source.syft.json",
    }
)
