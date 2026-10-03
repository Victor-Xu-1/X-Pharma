from __future__ import annotations

MCP_INTEROPERABILITY_TOOL_COUNT = 28


MCP_SENDER_CONSTRAINT_SCHEMA = "pharma.mcp-sender-constraint-evidence.v2"


MCP_SENDER_CONSTRAINT_REPORT = "mcp-sender-constraint-report.json"


MCP_SENDER_CONSTRAINT_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "status",
        "environment_kind",
        "environment_id",
        "tested_at",
        "subject",
        "idp_issuer_url",
        "resource_server_url",
        "clients",
        "checks",
        "replay_store",
        "references",
    }
)


MCP_ASYNC_TASK_SCHEMA = "pharma.mcp-async-task-interoperability.v1"


MCP_ASYNC_TASK_REPORT = "report.json"


MCP_ASYNC_TASK_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "controlled_fixture",
        "credentials_recorded",
        "protocol_version",
        "client_count",
        "clients",
        "same_authority_record_set",
        "database",
        "assertions",
        "cleanup",
    }
)


MCP_ASYNC_TASK_CLIENT_FIELDS = frozenset(
    {
        "client",
        "client_version",
        "tasks_created",
        "completed_tasks",
        "cancelled_tasks",
        "result_pages",
        "unique_records",
        "entity_ids_sha256",
        "manifest_sha256",
        "tampered_cursor_rejected",
        "recovered_after_error",
        "settlement_created",
        "credentials_recorded",
        "status",
    }
)


MCP_ASYNC_TASK_ASSERTIONS = frozenset(
    {
        "two_independent_clients",
        "approval_gated_task_created",
        "task_status_read",
        "task_cancellation",
        "bounded_export_completed",
        "signed_manifest_verified",
        "result_pagination",
        "tampered_cursor_rejected",
        "error_recovery",
        "one_settlement_per_completed_export",
        "zero_active_reservations",
        "isolated_runtime_destroyed",
    }
)


MCP_INTEROPERABILITY_SCHEMA = "pharma.mcp-interoperability-acceptance.v3"


MCP_INTEROPERABILITY_REPORT = "report.json"


MCP_INTEROPERABILITY_WORKFLOW_ASSERTIONS = {
    "capability_discovery": True,
    "cost_estimation": True,
    "entity_pagination": True,
    "tampered_cursor_rejection": True,
    "error_recovery": True,
    "target_profile": True,
    "competitive_pipeline": True,
    "evidence_search": True,
    "usage_accounting": True,
    "export_lifecycle_discovered": True,
    "export_execution_evidence_category": "mcp_async_tasks",
}


MCP_INTEROPERABILITY_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "created_at",
        "status",
        "environment",
        "production_claim",
        "credentials_recorded",
        "client",
        "client_count",
        "clients",
        "inspector_version",
        "python_sdk_version",
        "protocol_version",
        "billed_calls",
        "pageable_cursor_tools",
        "query_sha256",
        "target_id",
        "tool_contract_sha256",
        "tools",
        "usage_settlements",
        "pagination_pages",
        "pagination_unique_entities",
        "pagination_entity_ids_sha256",
        "invalid_cursor_rejected",
        "recovered_after_error",
        "competitive_program_items",
        "cross_domain_tool",
        "workflow_assertions",
    }
)


MCP_COMMERCIAL_SCHEMA = "pharma.mcp-commercial-acceptance.v2"


MCP_COMMERCIAL_REPORT = "report.json"


MCP_COMMERCIAL_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "status",
        "environment",
        "production_claim",
        "credentials_recorded",
        "started_at",
        "finished_at",
        "protocol_version",
        "requests",
        "latency_ms",
        "billing",
        "assertions",
        "errors",
        "resilience",
    }
)


MCP_COMMERCIAL_ASSERTIONS = frozenset(
    {
        "all_requests_succeeded",
        "one_unique_settlement_per_success",
        "ledger_delta_covers_successes",
        "no_active_reservations_after_run",
        "protocol_baseline_negotiated",
    }
)


MCP_COMMERCIAL_RESILIENCE_ASSERTIONS = frozenset(
    {
        "idempotent_replay_reuses_settlement",
        "idempotency_argument_conflict_rejected",
        "domain_failure_rejected",
        "insufficient_budget_rejected",
        "cancellation_was_requested",
        "timeout_was_observed",
        "timeout_reached_a_durable_terminal_state",
        "settlement_delta_matches_durable_successes",
        "charged_and_consumed_deltas_match",
        "no_active_reservations_after_failures",
        "reserved_units_returned_to_zero",
        "balance_identity_holds",
        "protocol_baseline_negotiated",
    }
)


MCP_SENDER_CONSTRAINT_CHECKS = frozenset(
    {
        "access_token_signature",
        "ath_binding",
        "bearer_rejected",
        "htm_binding",
        "htu_binding",
        "iat_window",
        "jkt_binding",
        "jti_replay_rejected",
        "key_rotation",
        "replay_store_fail_closed",
        "token_revocation",
    }
)
