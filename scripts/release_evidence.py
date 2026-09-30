from __future__ import annotations

import argparse
import base64
import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, TypeGuard
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

try:
    from scripts.source_tree_manifest import build_source_tree_manifest
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from source_tree_manifest import build_source_tree_manifest  # type: ignore[no-redef,import-not-found]

STATEMENT_SCHEMA = "pharma.release-gate-statement.v1"
BUNDLE_SCHEMA = "pharma.release-evidence-bundle.v1"
SIGNATURE_SCHEMA = "pharma.release-evidence-signature.v1"
GOAL_COMPLETION_MATRIX_SCHEMA = "pharma.goal-completion-matrix.v1"
GOAL_COMPLETION_AUDIT_SCHEMA = "pharma.goal-completion-audit.v1"
GOAL_DOCUMENT_VERSION = "1.9.9"
MCP_INTEROPERABILITY_TOOL_COUNT = 28
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40,64}")
CATEGORY_PATTERN = re.compile(r"[a-z][a-z0-9_]{1,63}")
GOAL_REQUIREMENT_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]+\.[a-z][a-z0-9_]+")
IMAGE_PATTERN = re.compile(r".+@sha256:([0-9a-f]{64})")
MAX_CAPTURE_LOG_BYTES = 64 * 1024 * 1024
MCP_SENDER_CONSTRAINT_SCHEMA = "pharma.mcp-sender-constraint-evidence.v2"
MCP_SENDER_CONSTRAINT_REPORT = "mcp-sender-constraint-report.json"
PRODUCTION_TOPOLOGY_SCHEMA = "pharma.production-topology-evidence.v1"
PRODUCTION_TOPOLOGY_REPORT = "production-topology-report.json"
PRODUCTION_TOPOLOGY_LIVE_SCHEMA = "pharma.production-topology-live-probe.v1"
PRODUCTION_TOPOLOGY_LIVE_REPORT = "production-topology-live-probe.json"
PRODUCTION_TOPOLOGY_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "status",
        "environment_kind",
        "environment_id",
        "tested_at",
        "subject",
        "profile",
        "entrypoints",
        "components",
        "event_projection",
        "authority",
        "resilience",
        "migration",
        "references",
    }
)
PRODUCTION_TOPOLOGY_COMPONENTS = frozenset(
    {
        "python",
        "postgresql",
        "rdkit",
        "opensearch",
        "object_storage",
        "temporal",
        "valkey",
        "identity",
        "secrets",
        "gateway",
        "kubernetes",
        "observability",
    }
)
PRODUCTION_TOPOLOGY_COMPONENT_FIELDS = frozenset({"version", "deployment_reference", "replicas", "managed_or_ha"})
PRODUCTION_TOPOLOGY_LIVE_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "status",
        "environment_kind",
        "environment_id",
        "tested_at",
        "subject",
        "topology_report_sha256",
        "kube_context_sha256",
        "namespace",
        "namespace_uid",
        "kubernetes",
        "workloads",
        "gateway",
        "network_policy",
        "endpoints",
        "credentials_recorded",
    }
)
PRODUCTION_TOPOLOGY_REQUIRED_WORKLOADS = frozenset(
    {
        "pharma-api",
        "pharma-jobs",
        "pharma-parser",
        "pharma-ocr",
    }
)
PRODUCTION_TOPOLOGY_HPA_WORKLOADS = frozenset(
    {
        "pharma-api",
        "pharma-jobs",
        "pharma-parser",
    }
)
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
PRODUCTION_GATE_SCHEMA = "pharma.production-gate-evidence.v2"
PRODUCTION_GATE_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "category",
        "status",
        "environment_kind",
        "environment_id",
        "tested_at",
        "subject",
        "checks",
        "executor",
        "artifacts",
        "approvals",
    }
)
PRODUCTION_ARTIFACT_FIELDS = frozenset({"name", "path", "size", "sha256", "reference"})
PRODUCTION_APPROVAL_FIELDS = frozenset(
    {"role", "reference", "organization", "approved_at", "artifact_path", "artifact_size", "artifact_sha256"}
)
PRODUCTION_INTAKE_SCHEMA = "pharma.production-evidence-intake.v1"
PRODUCTION_INTAKE_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "category",
        "environment_kind",
        "environment_id",
        "tested_at",
        "checks",
        "executor",
        "artifacts",
        "approvals",
    }
)
PRODUCTION_INTAKE_ARTIFACT_FIELDS = frozenset({"name", "source_path", "destination", "reference"})
PRODUCTION_INTAKE_APPROVAL_FIELDS = frozenset(
    {"role", "source_path", "destination", "reference", "organization", "approved_at"}
)
PRODUCTION_HANDOFF_SCHEMA = "pharma.production-evidence-handoff.v2"
PRODUCTION_HANDOFF_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "production_claim",
        "subject",
        "policy_sha256",
        "categories",
        "files",
        "signature",
    }
)
PRODUCTION_HANDOFF_SUBJECT_FIELDS = frozenset({"git_commit", "source_file_count", "source_tree_sha256"})
PRODUCTION_HANDOFF_CATEGORY_FIELDS = frozenset({"category", "requirements"})
PRODUCTION_HANDOFF_FILE_FIELDS = frozenset({"path", "size", "sha256"})
PRODUCTION_HANDOFF_SIGNATURE_FIELDS = frozenset({"present", "key_id", "public_key_sha256"})
PRODUCTION_BATCH_INTAKE_SCHEMA = "pharma.production-evidence-batch-intake.v1"
PRODUCTION_BATCH_INTAKE_FIELDS = frozenset({"schema", "schema_version", "requests"})
PRODUCTION_BATCH_ENTRY_FIELDS = frozenset({"category", "request_path"})
PRODUCTION_BATCH_MANIFEST_SCHEMA = "pharma.production-evidence-batch.v1"
PRODUCTION_BATCH_MANIFEST_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "production_claim",
        "subject",
        "security_manifest_sha256",
        "categories",
    }
)
PRODUCTION_BATCH_CATEGORY_FIELDS = frozenset({"category", "statement", "statement_sha256"})
MAX_PRODUCTION_BATCH_CATEGORIES = 64
MAX_RELEASE_STATEMENTS = 128
MAX_PRODUCTION_EVIDENCE_FILE_BYTES = 1024 * 1024 * 1024
MAX_PRODUCTION_EVIDENCE_TOTAL_BYTES = 4 * 1024 * 1024 * 1024
MAX_PRODUCTION_INTAKE_BYTES = 1024 * 1024
GOAL_MATRIX_FIELDS = frozenset(
    {"schema", "schema_version", "goal_document_id", "goal_version", "section", "requirements"}
)
GOAL_REQUIREMENT_FIELDS = frozenset(
    {
        "id",
        "ordinal",
        "group",
        "title",
        "baseline_categories",
        "production_categories",
        "requires_release_security",
        "requires_signed_git_tag",
        "requires_bundle_signature",
    }
)
GOAL_SECTION_19_REQUIREMENTS = (
    ("product_data.capability_uat", "product_data"),
    ("product_data.internal_operations", "product_data"),
    ("product_data.licensed_coverage", "product_data"),
    ("product_data.automatic_source_lifecycle", "product_data"),
    ("product_data.cross_entry_traceability", "product_data"),
    ("human_agent.browser_workflows", "human_agent"),
    ("human_agent.workbench_isolation", "human_agent"),
    ("human_agent.remote_mcp_gateway", "human_agent"),
    ("human_agent.mcp_interoperability", "human_agent"),
    ("human_agent.financial_traceability", "human_agent"),
    ("human_agent.anti_extraction", "human_agent"),
    ("human_agent.real_target_cross_domain", "human_agent"),
    ("human_agent.web_mcp_consistency", "human_agent"),
    ("security.external_services", "security_reliability_operations"),
    ("security.approved_capacity", "security_reliability_operations"),
    ("security.penetration_supply_chain", "security_reliability_operations"),
    ("security.risk_billing_drills", "security_reliability_operations"),
    ("security.recovery_rpo_rto", "security_reliability_operations"),
    ("security.operating_model", "security_reliability_operations"),
    ("engineering.production_topology", "engineering_delivery"),
    ("engineering.clean_clone_lifecycle", "engineering_delivery"),
    ("engineering.contract_consistency", "engineering_delivery"),
    ("engineering.release_evidence_bundle", "engineering_delivery"),
    ("engineering.repository_hygiene", "engineering_delivery"),
)
CLEAN_SOURCE_SCHEMA = "pharma.clean-source-reproducibility.v1"
CLEAN_SOURCE_REPORT = "report.json"
PERFORMANCE_BASELINE_SCHEMA = "pharma.local-performance-baseline.v1"
PERFORMANCE_BASELINE_REPORT = "report.json"
BROWSER_ACCEPTANCE_SCHEMA = "pharma.browser-acceptance.v9"
BROWSER_ACCEPTANCE_REPORT = "report.json"
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
BACKUP_RESTORE_SCHEMA = "pharma.local-backup-restore-acceptance.v1"
BACKUP_RESTORE_REPORT = "report.json"
BACKUP_RESTORE_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "credentials_recorded",
        "backup_reference",
        "backup_manifest_sha256",
        "backup_checksums_sha256",
        "authority_artifacts",
        "authority_bytes",
        "tables_verified",
        "alembic_head",
        "rdkit_version",
        "temporal_databases_restored",
        "rls_probe",
        "archives_verified",
        "main_runtime_modified",
        "duration_seconds",
        "sensitive_backup_embedded",
    }
)
KUBERNETES_VALIDATION_SCHEMA = "pharma.local-kubernetes-validation.v3"
KUBERNETES_VALIDATION_REPORT = "report.json"
KUBERNETES_VALIDATION_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "credentials_recorded",
        "controlled_cluster",
        "cluster",
        "kind_version",
        "kubernetes_server_version",
        "kind_node_image",
        "cluster_topology",
        "server_side_dry_run",
        "clamav_ha",
        "production_crd_sets",
        "cluster_cleanup",
        "duration_seconds",
        "download_transport",
        "asset_cache",
        "downloads",
    }
)
KUBERNETES_DOWNLOAD_FIELDS = frozenset({"version", "sha256"})
KUBERNETES_CLUSTER_TOPOLOGY_FIELDS = frozenset({"control_plane_nodes", "worker_nodes", "worker_zones"})
KUBERNETES_CLAMAV_HA_FIELDS = frozenset(
    {
        "image",
        "live_image_reference",
        "live_image_pull_policy",
        "source_image_digest_verified",
        "workload",
        "replicas_requested",
        "ready_replicas_before",
        "ready_replicas_after",
        "ready_endpoints_before",
        "ready_endpoints_after",
        "minimum_ready_endpoints_during_replacement",
        "distinct_nodes_before",
        "distinct_nodes_after",
        "distinct_zones_before",
        "distinct_zones_after",
        "placement_identity_preserved",
        "distinct_pvcs",
        "pvc_identity_preserved",
        "persistent_marker_preserved",
        "signature_freshness",
        "clean_scan",
        "eicar_blocked",
        "replacement_pod_uid_changed",
    }
)
KUBERNETES_DOWNLOADS = frozenset({"envoy_gateway", "external_secrets", "opentelemetry_operator"})
ENTRY_CONSISTENCY_SCHEMA = "pharma.entry-consistency-acceptance.v1"
ENTRY_CONSISTENCY_REPORT = "report.json"
ENTRY_CONSISTENCY_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "credentials_recorded",
        "entity_id",
        "canonical_entity_sha256",
        "fields_compared",
        "web_operations",
        "mcp_tools",
        "mcp_protocol_version",
        "mcp_billed_calls",
        "unique_settlements",
        "same_tenant_fixture",
        "same_filtered_facts",
        "temporary_accounts_after",
        "temporary_entities_after",
    }
)
ENTRY_CONSISTENCY_ENTITY_FIELDS = (
    "id",
    "entity_type",
    "name",
    "description",
    "external_ids",
    "attributes",
    "review_status",
    "canonical_entity_id",
    "identity_identifiers",
    "created_at",
    "updated_at",
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
OBSERVABILITY_ACCEPTANCE_SCHEMA = "pharma.local-observability-acceptance.v1"
OBSERVABILITY_ACCEPTANCE_REPORT = "report.json"
OBSERVABILITY_ACCEPTANCE_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "credentials_recorded",
        "collector_protocol",
        "observed_metrics",
        "contract",
        "commercial_probe",
    }
)
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
PARSER_DOCUMENT_CONTRACTS = {
    ".md": ("text", "1"),
    ".html": ("beautifulsoup4+lxml", "4.15.0"),
    ".docx": ("python-docx", "1.2.0"),
    ".pptx": ("python-pptx", "1.0.2"),
    ".xlsx": ("openpyxl", "3.1.5"),
    ".pdf": ("pypdf", "6.14.2"),
    ".sdf": ("rdkit-sdf", "2026.3.3"),
    ".mol": ("rdkit-mol", "2026.3.3"),
    ".pdb": ("gemmi-pdb", "0.7.5"),
    ".cif": ("gemmi-mmcif", "0.7.5"),
    ".mmcif": ("gemmi-mmcif", "0.7.5"),
}
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
RUNTIME_ACCEPTANCE_SCHEMA_V1 = "pharma.local-runtime-acceptance.v1"
RUNTIME_ACCEPTANCE_SCHEMA_V2 = "pharma.local-runtime-acceptance.v2"
RUNTIME_ACCEPTANCE_SCHEMA = "pharma.local-runtime-acceptance.v3"
RUNTIME_ACCEPTANCE_REPORT = "report.json"
RUNTIME_ACCEPTANCE_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "credentials_recorded",
        "compose_profile",
        "services",
        "entrypoints",
        "database",
        "search",
        "runtime_hygiene",
        "main_runtime_modified",
        "duration_seconds",
    }
)
RUNTIME_SERVICES = (
    "postgres",
    "redis",
    "opensearch",
    "temporal",
    "clamav",
    "parser",
    "api",
    "worker",
    "otel-collector",
)
RUNTIME_APPLICATION_SERVICES = frozenset({"parser", "api", "worker"})
UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
INGESTION_READINESS_SERVICES = frozenset({"postgres", "opensearch", "temporal", "parser", "clamav", "worker"})
BROWSER_ACCEPTANCE_SCENARIOS = frozenset(
    {
        "accessibility",
        "authenticated_navigation",
        "billing_dispute",
        "browser_quality",
        "web_vitals_rum",
        "chemistry",
        "chemistry_real_api",
        "comparison_export",
        "data_lifecycle",
        "domain_export",
        "result_pagination",
        "result_to_comparison",
        "cross_page_comparison",
        "deal_entity_query",
        "deal_asset_attribute_query",
        "deal_asset_multiselect_query",
        "deal_full_result_landscape",
        "deal_asset_correctness",
        "patent_result_correctness",
        "enterprise_administration",
        "external_login",
        "internal_login",
        "internal_workbench",
        "ingestion_replay",
        "loading_empty_error_recovery",
        "master_data_rollback",
        "monitoring",
        "permission_boundary",
        "real_permission_boundary",
        "real_target_dossier",
        "pipeline_intelligence",
        "pipeline_cross_domain_signals",
        "pipeline_cross_domain_navigation",
        "pipeline_dense_results",
        "pipeline_relationship_correctness",
        "clinical_full_result_landscape",
        "clinical_result_dense_fields",
        "clinical_normalized_drug_or",
        "clinical_role_correctness",
        "clinical_linked_program_correctness",
        "publication_governance",
        "public_login",
        "quality_operations",
        "quarantine_governance",
        "reflow_keyboard",
        "regulatory_intelligence",
        "regulatory_result_correctness",
        "regulatory_subscription",
        "saved_search_maintenance",
        "epidemiology_news_subscription",
        "news_result_correctness",
        "epidemiology_trend_correctness",
        "research_workbench",
        "initial_load_boundary",
        "session_recovery",
        "stable_deep_link",
        "table_preference_server_continuity",
        "query_cancellation",
        "professional_query_state_matrix",
        "professional_error_permission_matrix",
        "explorer_quick_detail_continuity",
        "knowledge_research_continuity",
        "evidence_research_continuity",
        "workspace_isolation",
    }
)
ENVIRONMENT_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{2,119}")
REFERENCE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/#@-]{2,499}")
UNITS_PATTERN = re.compile(r"[0-9]+\.[0-9]{8}")
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


class ReleaseEvidenceError(ValueError):
    pass


def _rename_noreplace(source: Path, destination: Path) -> None:
    """Atomically publish a WSL evidence path without replacing an existing target."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
    except (AttributeError, OSError) as exc:
        raise ReleaseEvidenceError("Linux renameat2 is required for no-overwrite evidence publication") from exc
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise ReleaseEvidenceError(f"refusing to overwrite evidence: {destination}")
    raise ReleaseEvidenceError(f"cannot publish evidence at {destination}: {os.strerror(error_number)}")


@dataclass(frozen=True)
class RepositorySubject:
    commit: str
    source_file_count: int
    source_tree_sha256: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class SecurityEvidence:
    directory: Path
    manifest_sha256: str
    generated_at: datetime
    targets: dict[str, str]
    release_mode: bool
    risk_acceptance_reference: str


@dataclass(frozen=True)
class PolicyLevel:
    required_categories: frozenset[str]
    require_release_security: bool
    require_signed_git_tag: bool
    require_bundle_signature: bool
    security_max_age_hours: int


@dataclass(frozen=True)
class ProductionEvidenceContract:
    report_name: str
    checks: frozenset[str]
    approval_roles: frozenset[str]
    minimum_artifacts: int
    require_independent_executor: bool


@dataclass(frozen=True)
class EvidencePolicy:
    path: Path
    categories: dict[str, int]
    levels: dict[str, PolicyLevel]
    production_contracts: dict[str, ProductionEvidenceContract]


@dataclass(frozen=True)
class GoalRequirement:
    identifier: str
    ordinal: int
    group: str
    title: str
    baseline_categories: frozenset[str]
    production_categories: frozenset[str]
    requires_release_security: bool
    requires_signed_git_tag: bool
    requires_bundle_signature: bool


@dataclass(frozen=True)
class GoalCompletionMatrix:
    path: Path
    goal_document_id: str
    goal_version: str
    section: int
    requirements: tuple[GoalRequirement, ...]


def _canonical_json(document: object) -> bytes:
    return (json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ReleaseEvidenceError(f"cannot read evidence file: {path}") from exc
    return digest.hexdigest()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise ReleaseEvidenceError(f"refusing to overwrite evidence: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _rename_noreplace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ReleaseEvidenceError(f"{label} must be a regular file: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseEvidenceError(f"invalid {label}: {path}") from exc
    if not isinstance(document, dict):
        raise ReleaseEvidenceError(f"{label} must contain a JSON object: {path}")
    return document


def _parse_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ReleaseEvidenceError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseEvidenceError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ReleaseEvidenceError(f"{label} must include a timezone")
    return parsed.astimezone(UTC)


def _git(repo: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    executable = shutil.which("git")
    if executable is None:
        raise ReleaseEvidenceError("git executable is unavailable")
    try:
        return subprocess.run(  # noqa: S603 - executable is resolved and arguments are never passed to a shell.
            [executable, "-C", str(repo), *arguments],
            check=check,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = ""
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            detail = exc.stderr.decode(errors="replace").strip()
        raise ReleaseEvidenceError(f"git command failed{f': {detail}' if detail else ''}") from exc


def repository_subject(repo: Path) -> RepositorySubject:
    try:
        resolved_repo = repo.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("repository does not exist") from exc
    if not resolved_repo.is_dir():
        raise ReleaseEvidenceError("repository must be a directory")

    root = Path(_git(resolved_repo, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve()
    if root != resolved_repo:
        raise ReleaseEvidenceError(f"repository argument must be the Git root: {root}")
    status_output = _git(root, "-c", "core.quotepath=false", "status", "--porcelain=v1", "--untracked-files=all").stdout
    if status_output:
        raise ReleaseEvidenceError("release evidence requires a clean Git worktree")
    commit = _git(root, "rev-parse", "--verify", "HEAD").stdout.decode().strip()
    if not COMMIT_PATTERN.fullmatch(commit):
        raise ReleaseEvidenceError("repository HEAD is not a valid immutable commit")

    tracked = [item for item in _git(root, "ls-files", "-z").stdout.split(b"\0") if item]
    with tempfile.TemporaryDirectory(prefix="pharma-release-source-") as temporary:
        staging = Path(temporary)
        for raw_path in tracked:
            try:
                relative_text = raw_path.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ReleaseEvidenceError("tracked file path is not UTF-8") from exc
            relative = PurePosixPath(relative_text)
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise ReleaseEvidenceError(f"unsafe tracked file path: {relative_text}")
            source = root.joinpath(*relative.parts)
            try:
                mode = source.lstat().st_mode
            except OSError as exc:
                raise ReleaseEvidenceError(f"cannot inspect tracked file: {relative_text}") from exc
            if stat.S_ISLNK(mode):
                raise ReleaseEvidenceError(f"release source does not accept symbolic links: {relative_text}")
            if not stat.S_ISREG(mode):
                raise ReleaseEvidenceError(f"tracked path is not a regular file: {relative_text}")
            destination = staging.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        tree = build_source_tree_manifest(staging)
    tags = tuple(sorted(_git(root, "tag", "--points-at", "HEAD").stdout.decode().splitlines()))
    return RepositorySubject(commit, tree.file_count, tree.sha256, tags)


def load_policy(path: Path) -> EvidencePolicy:
    resolved = path.resolve()
    document = _load_json_object(resolved, "release evidence policy")
    if document.get("schema_version") != 1:
        raise ReleaseEvidenceError("unsupported release evidence policy schema")
    raw_categories = document.get("categories")
    raw_levels = document.get("levels")
    raw_security_age = document.get("security_max_age_hours")
    raw_production_contracts = document.get("production_evidence_contracts", {})
    if (
        not isinstance(raw_categories, dict)
        or not isinstance(raw_levels, dict)
        or not isinstance(raw_security_age, dict)
        or not isinstance(raw_production_contracts, dict)
    ):
        raise ReleaseEvidenceError("release evidence policy sections are invalid")
    categories: dict[str, int] = {}
    for name, configuration in raw_categories.items():
        if not isinstance(name, str) or not CATEGORY_PATTERN.fullmatch(name) or not isinstance(configuration, dict):
            raise ReleaseEvidenceError("release evidence policy contains an invalid category")
        maximum_age = configuration.get("max_age_hours")
        if not isinstance(maximum_age, int) or isinstance(maximum_age, bool) or maximum_age <= 0:
            raise ReleaseEvidenceError(f"category {name} has an invalid maximum age")
        categories[name] = maximum_age
    production_contracts: dict[str, ProductionEvidenceContract] = {}
    for category, configuration in raw_production_contracts.items():
        if not isinstance(category, str) or category not in categories or not isinstance(configuration, dict):
            raise ReleaseEvidenceError("release evidence policy contains an invalid production contract")
        report_name = configuration.get("report_name")
        checks = configuration.get("checks")
        approval_roles = configuration.get("approval_roles")
        minimum_artifacts = configuration.get("minimum_artifacts")
        require_independent_executor = configuration.get("require_independent_executor")
        if (
            not isinstance(report_name, str)
            or PurePosixPath(report_name).name != report_name
            or not report_name.endswith(".json")
            or not isinstance(checks, list)
            or not checks
            or not all(isinstance(item, str) and CATEGORY_PATTERN.fullmatch(item) for item in checks)
            or len(set(checks)) != len(checks)
            or not isinstance(approval_roles, list)
            or not approval_roles
            or not all(isinstance(item, str) and CATEGORY_PATTERN.fullmatch(item) for item in approval_roles)
            or len(set(approval_roles)) != len(approval_roles)
            or not isinstance(minimum_artifacts, int)
            or isinstance(minimum_artifacts, bool)
            or not 1 <= minimum_artifacts <= 100
            or not isinstance(require_independent_executor, bool)
        ):
            raise ReleaseEvidenceError(f"production evidence contract {category} is invalid")
        production_contracts[category] = ProductionEvidenceContract(
            report_name=report_name,
            checks=frozenset(checks),
            approval_roles=frozenset(approval_roles),
            minimum_artifacts=minimum_artifacts,
            require_independent_executor=require_independent_executor,
        )
    levels: dict[str, PolicyLevel] = {}
    for level_name, configuration in raw_levels.items():
        if not isinstance(level_name, str) or not isinstance(configuration, dict):
            raise ReleaseEvidenceError("release evidence policy contains an invalid level")
        required = configuration.get("required_categories")
        security_age = raw_security_age.get(level_name)
        if (
            not isinstance(required, list)
            or not all(isinstance(item, str) and item in categories for item in required)
            or len(set(required)) != len(required)
            or not isinstance(security_age, int)
            or isinstance(security_age, bool)
            or security_age <= 0
        ):
            raise ReleaseEvidenceError(f"release evidence policy level {level_name} is invalid")
        boolean_names = ("require_release_security", "require_signed_git_tag", "require_bundle_signature")
        if not all(isinstance(configuration.get(name), bool) for name in boolean_names):
            raise ReleaseEvidenceError(f"release evidence policy level {level_name} has invalid booleans")
        levels[level_name] = PolicyLevel(
            required_categories=frozenset(required),
            require_release_security=configuration["require_release_security"],
            require_signed_git_tag=configuration["require_signed_git_tag"],
            require_bundle_signature=configuration["require_bundle_signature"],
            security_max_age_hours=security_age,
        )
    production_categories = levels.get("production")
    if production_contracts and (
        production_categories is None or not production_contracts.keys() <= production_categories.required_categories
    ):
        raise ReleaseEvidenceError("production evidence contracts must map to required production categories")
    return EvidencePolicy(resolved, categories, levels, production_contracts)


def _goal_categories(value: object, *, label: str, policy: EvidencePolicy) -> frozenset[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and CATEGORY_PATTERN.fullmatch(item) for item in value)
        or len(set(value)) != len(value)
    ):
        raise ReleaseEvidenceError(f"{label} must be a non-empty unique category list")
    categories = frozenset(value)
    unknown = categories - policy.categories.keys()
    if unknown:
        raise ReleaseEvidenceError(f"{label} contains unknown categories: {', '.join(sorted(unknown))}")
    return categories


def load_goal_completion_matrix(path: Path, policy: EvidencePolicy) -> GoalCompletionMatrix:
    resolved = path.resolve()
    document = _load_json_object(resolved, "GOAL completion matrix")
    if set(document) != GOAL_MATRIX_FIELDS:
        raise ReleaseEvidenceError("GOAL completion matrix fields are invalid")
    if (
        document.get("schema") != GOAL_COMPLETION_MATRIX_SCHEMA
        or document.get("schema_version") != 1
        or document.get("goal_document_id") != "PIP-GOAL-001"
        or document.get("goal_version") != GOAL_DOCUMENT_VERSION
        or document.get("section") != 19
    ):
        raise ReleaseEvidenceError("GOAL completion matrix identity is invalid")
    raw_requirements = document.get("requirements")
    if not isinstance(raw_requirements, list) or len(raw_requirements) != len(GOAL_SECTION_19_REQUIREMENTS):
        raise ReleaseEvidenceError(
            f"GOAL completion matrix must contain exactly {len(GOAL_SECTION_19_REQUIREMENTS)} requirements"
        )
    pilot = policy.levels.get("pilot")
    production = policy.levels.get("production")
    if pilot is None or production is None:
        raise ReleaseEvidenceError("GOAL completion matrix requires pilot and production policy levels")

    requirements: list[GoalRequirement] = []
    for index, raw_requirement in enumerate(raw_requirements, start=1):
        if not isinstance(raw_requirement, dict) or set(raw_requirement) != GOAL_REQUIREMENT_FIELDS:
            raise ReleaseEvidenceError(f"GOAL requirement {index} fields are invalid")
        identifier = raw_requirement.get("id")
        ordinal = raw_requirement.get("ordinal")
        group = raw_requirement.get("group")
        title = raw_requirement.get("title")
        expected_identifier, expected_group = GOAL_SECTION_19_REQUIREMENTS[index - 1]
        if (
            not isinstance(identifier, str)
            or GOAL_REQUIREMENT_ID_PATTERN.fullmatch(identifier) is None
            or identifier != expected_identifier
            or ordinal != index
            or group != expected_group
            or not isinstance(title, str)
            or title != title.strip()
            or not 4 <= len(title) <= 120
        ):
            raise ReleaseEvidenceError(f"GOAL requirement {index} identity is invalid")
        requires_release_security = raw_requirement.get("requires_release_security")
        requires_signed_git_tag = raw_requirement.get("requires_signed_git_tag")
        requires_bundle_signature = raw_requirement.get("requires_bundle_signature")
        if not (
            isinstance(requires_release_security, bool)
            and isinstance(requires_signed_git_tag, bool)
            and isinstance(requires_bundle_signature, bool)
        ):
            raise ReleaseEvidenceError(f"GOAL requirement {identifier} controls are invalid")
        baseline_categories = _goal_categories(
            raw_requirement.get("baseline_categories"), label=f"GOAL requirement {identifier} baseline", policy=policy
        )
        production_categories = _goal_categories(
            raw_requirement.get("production_categories"),
            label=f"GOAL requirement {identifier} production",
            policy=policy,
        )
        if not baseline_categories <= pilot.required_categories:
            raise ReleaseEvidenceError(f"GOAL requirement {identifier} baseline is not required by pilot policy")
        if not production_categories <= production.required_categories:
            raise ReleaseEvidenceError(f"GOAL requirement {identifier} production evidence is not required by policy")
        requirements.append(
            GoalRequirement(
                identifier=identifier,
                ordinal=index,
                group=group,
                title=title,
                baseline_categories=baseline_categories,
                production_categories=production_categories,
                requires_release_security=requires_release_security,
                requires_signed_git_tag=requires_signed_git_tag,
                requires_bundle_signature=requires_bundle_signature,
            )
        )

    release_bundle = next(
        requirement for requirement in requirements if requirement.identifier == "engineering.release_evidence_bundle"
    )
    if (
        release_bundle.baseline_categories != pilot.required_categories
        or release_bundle.production_categories != production.required_categories
        or not release_bundle.requires_release_security
        or not release_bundle.requires_signed_git_tag
        or not release_bundle.requires_bundle_signature
    ):
        raise ReleaseEvidenceError("GOAL release evidence bundle requirement must cover the complete release policy")
    return GoalCompletionMatrix(
        path=resolved,
        goal_document_id="PIP-GOAL-001",
        goal_version=GOAL_DOCUMENT_VERSION,
        section=19,
        requirements=tuple(requirements),
    )


def _repository_goal_matrix_contract(
    repo: Path, policy: EvidencePolicy, level_name: str
) -> tuple[GoalCompletionMatrix | None, Path | None]:
    matrix_path = policy.path.with_name("goal-section-19-matrix.json")
    schema_path = policy.path.with_name("goal-section-19-matrix.schema.json")
    if not matrix_path.exists() and not schema_path.exists():
        if level_name == "production" and (repo / "GOAL.md").is_file():
            raise ReleaseEvidenceError("authoritative GOAL completion matrix is missing from the repository")
        return None, None
    if matrix_path.is_symlink() or schema_path.is_symlink() or not matrix_path.is_file() or not schema_path.is_file():
        raise ReleaseEvidenceError("GOAL completion matrix and schema must both be regular files")
    schema = _load_json_object(schema_path, "GOAL completion matrix schema")
    if (
        schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
    ):
        raise ReleaseEvidenceError("GOAL completion matrix schema contract is invalid")
    return load_goal_completion_matrix(matrix_path, policy), schema_path.resolve()


def _require_authoritative_production_policy(
    repo: Path,
    policy: EvidencePolicy,
    level_name: str,
) -> None:
    if level_name != "production":
        return
    try:
        expected = (repo.resolve(strict=True) / "deploy" / "release" / "evidence-policy.json").resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("authoritative production evidence policy is missing from the repository") from exc
    if policy.path != expected:
        raise ReleaseEvidenceError("production releases require the committed authoritative evidence policy")


def collect_release_statements(
    statements: list[Path],
    statement_directories: list[Path],
) -> list[Path]:
    collected: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path, *, require_standard_name: bool = False) -> None:
        if path.is_symlink():
            raise ReleaseEvidenceError(f"release gate statement cannot be a symbolic link: {path}")
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise ReleaseEvidenceError(f"release gate statement does not exist: {path}") from exc
        if not resolved.is_file() or (require_standard_name and resolved.name != "gate-statement.json"):
            raise ReleaseEvidenceError(f"release gate statement path is invalid: {path}")
        if resolved in seen:
            raise ReleaseEvidenceError(f"duplicate release gate statement path: {resolved}")
        if len(collected) >= MAX_RELEASE_STATEMENTS:
            raise ReleaseEvidenceError(f"release statement count exceeds {MAX_RELEASE_STATEMENTS}")
        seen.add(resolved)
        collected.append(resolved)

    for statement in statements:
        add(statement)
    for raw_directory in statement_directories:
        if raw_directory.is_symlink():
            raise ReleaseEvidenceError(f"release statement directory cannot be a symbolic link: {raw_directory}")
        try:
            directory = raw_directory.resolve(strict=True)
        except OSError as exc:
            raise ReleaseEvidenceError(f"release statement directory does not exist: {raw_directory}") from exc
        if not directory.is_dir():
            raise ReleaseEvidenceError(f"release statement directory is invalid: {raw_directory}")
        discovered = 0
        discovered_categories: dict[str, Path] = {}
        for category_directory in sorted(directory.iterdir(), key=lambda item: item.name):
            if category_directory.is_symlink():
                raise ReleaseEvidenceError(
                    f"release statement category directory cannot be a symbolic link: {category_directory}"
                )
            if not category_directory.is_dir() or CATEGORY_PATTERN.fullmatch(category_directory.name) is None:
                continue
            candidate = category_directory / "gate-statement.json"
            if candidate.exists() or candidate.is_symlink():
                add(candidate, require_standard_name=True)
                discovered += 1
                discovered_categories[category_directory.name] = candidate.resolve(strict=True)
        if discovered == 0:
            raise ReleaseEvidenceError(f"release statement directory contains no category statements: {directory}")
        batch_manifest_path = directory / "batch-manifest.json"
        if batch_manifest_path.exists() or batch_manifest_path.is_symlink():
            _validate_production_batch_directory(batch_manifest_path, discovered_categories)
    return collected


def _validate_production_batch_directory(
    manifest_path: Path,
    statements: dict[str, Path],
) -> None:
    if manifest_path.is_symlink():
        raise ReleaseEvidenceError("production evidence batch manifest cannot be a symbolic link")
    document = _load_json_object(manifest_path, "production evidence batch manifest")
    categories = document.get("categories")
    if (
        set(document) != PRODUCTION_BATCH_MANIFEST_FIELDS
        or document.get("schema") != PRODUCTION_BATCH_MANIFEST_SCHEMA
        or document.get("schema_version") != 1
        or document.get("status") != "registered"
        or document.get("production_claim") is not False
        or not isinstance(categories, list)
        or not 1 <= len(categories) <= MAX_PRODUCTION_BATCH_CATEGORIES
        or not isinstance(document.get("subject"), dict)
        or not isinstance(document.get("security_manifest_sha256"), str)
        or SHA256_PATTERN.fullmatch(document["security_manifest_sha256"]) is None
    ):
        raise ReleaseEvidenceError("production evidence batch manifest has an invalid registered contract")
    _parse_timestamp(document.get("generated_at"), "production evidence batch generated_at")
    batch_subject = document["subject"]
    batch_security_sha256 = document["security_manifest_sha256"]
    declared: set[str] = set()
    for item in categories:
        if not isinstance(item, dict) or set(item) != PRODUCTION_BATCH_CATEGORY_FIELDS:
            raise ReleaseEvidenceError("production evidence batch manifest contains an invalid category")
        category = item.get("category")
        statement = item.get("statement")
        digest = item.get("statement_sha256")
        if (
            not isinstance(category, str)
            or category in declared
            or category not in statements
            or statement != f"{category}/gate-statement.json"
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
            or _sha256_file(statements[category]) != digest
        ):
            raise ReleaseEvidenceError("production evidence batch manifest statement binding is invalid")
        statement_document = _load_json_object(statements[category], f"{category} production gate statement")
        if (
            statement_document.get("category") != category
            or statement_document.get("subject") != batch_subject
            or statement_document.get("security_manifest_sha256") != batch_security_sha256
        ):
            raise ReleaseEvidenceError("production evidence batch manifest release binding is invalid")
        declared.add(category)
    if declared != set(statements):
        raise ReleaseEvidenceError("production evidence batch manifest does not cover every category statement")


def validate_security_evidence(
    directory: Path,
    subject: RepositorySubject,
    *,
    maximum_age_hours: int | None = None,
) -> SecurityEvidence:
    try:
        resolved = directory.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("security evidence directory does not exist") from exc
    if not resolved.is_dir() or directory.is_symlink():
        raise ReleaseEvidenceError("security evidence must be a regular directory")
    present_files: set[str] = set()
    for candidate in resolved.rglob("*"):
        if candidate.is_symlink():
            raise ReleaseEvidenceError(f"security evidence contains a symbolic link: {candidate}")
        if not candidate.is_dir() and not candidate.is_file():
            raise ReleaseEvidenceError(f"security evidence contains a non-regular entry: {candidate}")
        if candidate.is_file():
            present_files.add(candidate.relative_to(resolved).as_posix())
    if missing_files := sorted(SECURITY_REQUIRED_FILES - present_files):
        raise ReleaseEvidenceError(f"security evidence is incomplete: {', '.join(missing_files)}")
    if unexpected_files := sorted(present_files - SECURITY_REQUIRED_FILES):
        raise ReleaseEvidenceError(f"security evidence contains unexpected files: {', '.join(unexpected_files)}")
    manifest_path = resolved / "evidence-manifest.json"
    manifest = _load_json_object(manifest_path, "security evidence manifest")
    if manifest.get("schema_version") != 1:
        raise ReleaseEvidenceError("unsupported security evidence manifest schema")
    if manifest.get("git_commit") != subject.commit or manifest.get("git_worktree_state") != "clean":
        raise ReleaseEvidenceError("security evidence is not bound to the current clean commit")
    if (
        manifest.get("source_file_count") != subject.source_file_count
        or manifest.get("source_tree_sha256") != subject.source_tree_sha256
    ):
        raise ReleaseEvidenceError("security evidence source tree differs from the current commit")
    generated_at = _parse_timestamp(manifest.get("generated_at"), "security evidence generated_at")
    now = datetime.now(UTC)
    if generated_at > now + timedelta(minutes=5):
        raise ReleaseEvidenceError("security evidence timestamp is in the future")
    if maximum_age_hours is not None and now - generated_at > timedelta(hours=maximum_age_hours):
        raise ReleaseEvidenceError("security evidence is older than the release policy permits")
    raw_targets = manifest.get("targets")
    if not isinstance(raw_targets, dict) or not raw_targets:
        raise ReleaseEvidenceError("security evidence does not identify scanned image targets")
    targets: dict[str, str] = {}
    for name, image in raw_targets.items():
        if not isinstance(name, str) or not isinstance(image, str) or not IMAGE_PATTERN.fullmatch(image):
            raise ReleaseEvidenceError("security evidence contains an invalid image target")
        targets[name] = image
    policies = manifest.get("policies")
    if not isinstance(policies, dict) or not isinstance(policies.get("release_mode"), bool):
        raise ReleaseEvidenceError("security evidence policies are invalid")
    unresolved = policies.get("unresolved_high_critical")
    if not isinstance(unresolved, dict) or not unresolved:
        raise ReleaseEvidenceError("security unresolved vulnerability inventory is invalid")
    unresolved_total = 0
    for count in unresolved.values():
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ReleaseEvidenceError("security unresolved vulnerability inventory is invalid")
        unresolved_total += count
    risk_reference = policies.get("risk_acceptance_reference", "")
    if not isinstance(risk_reference, str):
        raise ReleaseEvidenceError("security risk acceptance reference is invalid")
    if policies["release_mode"] and unresolved_total > 0 and not risk_reference.strip():
        raise ReleaseEvidenceError("release security evidence lacks a risk acceptance reference")
    return SecurityEvidence(
        directory=resolved,
        manifest_sha256=_sha256_file(manifest_path),
        generated_at=generated_at,
        targets=targets,
        release_mode=policies["release_mode"],
        risk_acceptance_reference=risk_reference,
    )


def _subject_document(subject: RepositorySubject, targets: dict[str, str]) -> dict[str, object]:
    return {
        "git_commit": subject.commit,
        "source_file_count": subject.source_file_count,
        "source_tree_sha256": subject.source_tree_sha256,
        "targets": dict(sorted(targets.items())),
    }


def _expected_relative_attachment(path: Path, parent: Path) -> str:
    try:
        relative = path.resolve(strict=False).relative_to(parent.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ReleaseEvidenceError("capture attachments must be regular files below the statement directory") from exc
    relative_path = relative.as_posix()
    if not relative.parts or relative_path == "gate-statement.json" or ".." in relative.parts:
        raise ReleaseEvidenceError(f"unsafe capture attachment path: {relative_path}")
    return relative_path


def _relative_attachment(path: Path, parent: Path) -> str:
    relative_path = _expected_relative_attachment(path, parent)
    if path.is_symlink() or not path.is_file():
        raise ReleaseEvidenceError(f"capture attachment must be a regular file: {path}")
    return relative_path


def _prepare_log_attachment(path: Path, statement_parent: Path, output: Path) -> Path:
    statement_parent.mkdir(parents=True, exist_ok=True)
    parent = statement_parent.resolve(strict=True)
    candidate = path.resolve(strict=False)
    try:
        relative = candidate.relative_to(parent)
    except ValueError as exc:
        raise ReleaseEvidenceError("capture log must be below the statement directory") from exc
    if not relative.parts or ".." in relative.parts or candidate == output.resolve(strict=False):
        raise ReleaseEvidenceError("capture log path is unsafe")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate = candidate.resolve(strict=False)
    try:
        candidate.relative_to(parent)
    except ValueError as exc:
        raise ReleaseEvidenceError("capture log parent escaped the statement directory") from exc
    if candidate.exists() or candidate.is_symlink():
        raise ReleaseEvidenceError(f"refusing to overwrite capture log: {candidate}")
    return candidate


def _open_capture_log(path: Path) -> BinaryIO:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    return os.fdopen(descriptor, "wb")


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def _run_gate_command(command: list[str], repo: Path, log_handle: BinaryIO | None) -> int:
    if log_handle is None:
        completed = subprocess.run(  # noqa: S603 - operator argv is executed without a shell.
            command, cwd=repo, check=False
        )
        return completed.returncode

    process = subprocess.Popen(  # noqa: S603 - operator argv is executed without a shell.
        command,
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    assert process.stdout is not None
    written = 0
    try:
        while chunk := process.stdout.read(64 * 1024):
            written += len(chunk)
            if written > MAX_CAPTURE_LOG_BYTES:
                _kill_process_group(process)
                raise ReleaseEvidenceError(f"capture log exceeds the {MAX_CAPTURE_LOG_BYTES}-byte safety limit")
            log_handle.write(chunk)
        return process.wait()
    except BaseException:
        _kill_process_group(process)
        raise
    finally:
        process.stdout.close()


def capture_gate(
    *,
    repo: Path,
    policy_path: Path,
    category: str,
    security_directory: Path,
    output: Path,
    command: list[str],
    attachments: list[Path],
    log_attachment: Path | None = None,
) -> tuple[dict[str, Any], int]:
    policy = load_policy(policy_path)
    if category not in policy.categories:
        raise ReleaseEvidenceError(f"unknown release evidence category: {category}")
    if not command:
        raise ReleaseEvidenceError("capture requires a command after --")
    if output.exists() or output.is_symlink():
        raise ReleaseEvidenceError(f"refusing to overwrite evidence: {output}")
    subject_before = repository_subject(repo)
    security = validate_security_evidence(security_directory, subject_before)
    output.parent.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(UTC)
    started_clock = time.monotonic()
    capture_log: Path | None = None
    log_handle: BinaryIO | None = None
    try:
        if log_attachment is not None:
            capture_log = _prepare_log_attachment(log_attachment, output.parent, output)
            log_handle = _open_capture_log(capture_log)
        exit_code = _run_gate_command(command, repo, log_handle)
    except OSError as exc:
        raise ReleaseEvidenceError(f"cannot execute release gate command: {command[0]}") from exc
    finally:
        if log_handle is not None:
            log_handle.flush()
            os.fsync(log_handle.fileno())
            log_handle.close()
    finished_at = datetime.now(UTC)
    subject_after = repository_subject(repo)
    if subject_after != subject_before:
        raise ReleaseEvidenceError("repository subject changed while the release gate was running")
    attachment_documents: list[dict[str, object]] = []
    attachment_paths: set[str] = set()
    for attachment in attachments:
        relative_path = _expected_relative_attachment(attachment, output.parent)
        if relative_path in attachment_paths:
            raise ReleaseEvidenceError(f"duplicate capture attachment: {relative_path}")
        attachment_paths.add(relative_path)
        if not attachment.exists() and not attachment.is_symlink() and exit_code != 0:
            continue
        _relative_attachment(attachment, output.parent)
        attachment_documents.append(
            {
                "path": relative_path,
                "size": attachment.stat().st_size,
                "sha256": _sha256_file(attachment),
            }
        )
    missing_attachments = sorted(
        _expected_relative_attachment(attachment, output.parent)
        for attachment in attachments
        if not attachment.exists() and not attachment.is_symlink()
    )
    if capture_log is not None:
        relative_path = _relative_attachment(capture_log, output.parent)
        if relative_path in attachment_paths:
            raise ReleaseEvidenceError(f"duplicate capture attachment: {relative_path}")
        attachment_documents.append(
            {
                "path": relative_path,
                "size": capture_log.stat().st_size,
                "sha256": _sha256_file(capture_log),
            }
        )
    statement: dict[str, Any] = {
        "schema": STATEMENT_SCHEMA,
        "schema_version": 1,
        "generated_at": finished_at.isoformat(),
        "category": category,
        "status": "passed" if exit_code == 0 else "failed",
        "subject": _subject_document(subject_before, security.targets),
        "security_manifest_sha256": security.manifest_sha256,
        "execution": {
            "argv": command,
            "argv_sha256": _sha256_bytes("\0".join(command).encode()),
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round(time.monotonic() - started_clock, 6),
            "exit_code": exit_code,
        },
        "log_attachment": _relative_attachment(capture_log, output.parent) if capture_log else None,
        "missing_attachments": missing_attachments,
        "attachments": sorted(attachment_documents, key=lambda item: str(item["path"])),
    }
    if exit_code == 0:
        _validate_specialized_evidence(output, category, statement, policy=policy)
    _atomic_write(output, _canonical_json(statement))
    return statement, exit_code


def _production_intake_destination(
    value: object,
    *,
    category: str,
    approval: bool,
) -> PurePosixPath:
    if not isinstance(value, str) or not value or len(value) > 240 or "\\" in value or "\0" in value:
        raise ReleaseEvidenceError("production evidence destination path is invalid")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or "." in relative.parts
        or ".." in relative.parts
        or relative.as_posix() != value
        or value in {"gate-statement.json", "production-evidence-report.json"}
    ):
        raise ReleaseEvidenceError("production evidence destination path is unsafe")
    if approval:
        if len(relative.parts) < 2 or relative.parts[0] != "approvals":
            raise ReleaseEvidenceError("production approval destinations must be below approvals/")
    elif not (len(relative.parts) >= 2 and relative.parts[0] == "artifacts") and not (
        (category == "mcp_sender_constraint" and value == MCP_SENDER_CONSTRAINT_REPORT)
        or (
            category == "production_topology" and value in {PRODUCTION_TOPOLOGY_REPORT, PRODUCTION_TOPOLOGY_LIVE_REPORT}
        )
    ):
        raise ReleaseEvidenceError("production artifact destinations must be below artifacts/")
    return relative


def _external_evidence_source(value: object, *, repo: Path, request: Path) -> Path:
    if not isinstance(value, str) or not value or len(value) > 4096 or "\0" in value:
        raise ReleaseEvidenceError("production evidence source path is invalid")
    source = Path(value)
    if not source.is_absolute() or source.is_symlink():
        raise ReleaseEvidenceError("production evidence sources must be absolute regular files, not symbolic links")
    try:
        resolved = source.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError(f"production evidence source does not exist: {source}") from exc
    if not resolved.is_file() or resolved == request:
        raise ReleaseEvidenceError(f"production evidence source is not an independent regular file: {source}")
    if resolved == repo or repo in resolved.parents:
        raise ReleaseEvidenceError("production evidence sources must be outside the source repository")
    return resolved


def _copy_external_evidence(source: Path, destination: Path) -> tuple[int, str]:
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    source_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    destination_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        source_descriptor = os.open(source, source_flags)
    except OSError as exc:
        raise ReleaseEvidenceError(f"cannot open production evidence source: {source}") from exc
    try:
        before = os.fstat(source_descriptor)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_PRODUCTION_EVIDENCE_FILE_BYTES:
            raise ReleaseEvidenceError(
                f"production evidence source must be non-empty and no larger than "
                f"{MAX_PRODUCTION_EVIDENCE_FILE_BYTES} bytes: {source}"
            )
        try:
            destination_descriptor = os.open(destination, destination_flags, 0o600)
        except OSError as exc:
            raise ReleaseEvidenceError(f"cannot create production evidence attachment: {destination}") from exc
        digest = hashlib.sha256()
        copied = 0
        try:
            while chunk := os.read(source_descriptor, 1024 * 1024):
                copied += len(chunk)
                if copied > MAX_PRODUCTION_EVIDENCE_FILE_BYTES:
                    raise ReleaseEvidenceError(f"production evidence source exceeded its size limit: {source}")
                digest.update(chunk)
                view = memoryview(chunk)
                while view:
                    written = os.write(destination_descriptor, view)
                    if written <= 0:
                        raise ReleaseEvidenceError(f"cannot write production evidence attachment: {destination}")
                    view = view[written:]
            os.fsync(destination_descriptor)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        finally:
            os.close(destination_descriptor)
        after = os.fstat(source_descriptor)
        identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if identity_before != identity_after or copied != before.st_size:
            destination.unlink(missing_ok=True)
            raise ReleaseEvidenceError(f"production evidence source changed while it was copied: {source}")
        return copied, digest.hexdigest()
    finally:
        os.close(source_descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _valid_production_reference(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and len(value) <= 200 and REFERENCE_PATTERN.fullmatch(value) is not None


def register_production_evidence(
    *,
    repo: Path,
    policy_path: Path,
    security_directory: Path,
    request_path: Path,
    output: Path,
) -> dict[str, Any]:
    try:
        repo = repo.resolve(strict=True)
        request = request_path.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("production evidence repository or intake request does not exist") from exc
    policy = load_policy(policy_path)
    if request_path.is_symlink() or not request.is_file():
        raise ReleaseEvidenceError("production evidence intake request must be a regular file")
    request_size = request.stat().st_size
    if not 0 < request_size <= MAX_PRODUCTION_INTAKE_BYTES:
        raise ReleaseEvidenceError(
            "production evidence intake request must be non-empty and no larger than "
            f"{MAX_PRODUCTION_INTAKE_BYTES} bytes"
        )
    if request == repo or repo in request.parents:
        raise ReleaseEvidenceError("production evidence intake request must be outside the source repository")
    document = _load_json_object(request, "production evidence intake request")
    category = document.get("category")
    if (
        set(document) != PRODUCTION_INTAKE_FIELDS
        or document.get("schema") != PRODUCTION_INTAKE_SCHEMA
        or document.get("schema_version") != 1
        or not isinstance(category, str)
        or category not in policy.production_contracts
    ):
        raise ReleaseEvidenceError("production evidence intake request has an invalid schema or category")
    contract = policy.production_contracts[category]
    checks = document.get("checks")
    if (
        not isinstance(checks, list)
        or not all(isinstance(item, str) for item in checks)
        or len(checks) != len(set(checks))
        or set(checks) != contract.checks
    ):
        raise ReleaseEvidenceError("production evidence intake must acknowledge every contracted check exactly once")
    artifacts = document.get("artifacts")
    approvals = document.get("approvals")
    if (
        not isinstance(artifacts, list)
        or not contract.minimum_artifacts <= len(artifacts) <= 100
        or not isinstance(approvals, list)
        or not 1 <= len(approvals) <= 100
    ):
        raise ReleaseEvidenceError("production evidence intake has an invalid artifact or approval count")
    executor = document.get("executor")
    environment_id = document.get("environment_id")
    if (
        document.get("environment_kind") not in {"preproduction", "production"}
        or not isinstance(environment_id, str)
        or ENVIRONMENT_ID_PATTERN.fullmatch(environment_id) is None
    ):
        raise ReleaseEvidenceError("production evidence intake environment is invalid")
    environment_tokens = set(re.split(r"[^a-z0-9]+", environment_id.casefold()))
    if environment_tokens.intersection({"dev", "development", "local", "test", "testing"}):
        raise ReleaseEvidenceError("production evidence intake identifies a local or development environment")
    tested_at = _parse_timestamp(document.get("tested_at"), "production evidence intake tested_at")
    if (
        not isinstance(executor, dict)
        or set(executor) != {"organization", "team", "independent"}
        or not _valid_production_reference(executor.get("organization"))
        or not _valid_production_reference(executor.get("team"))
        or not isinstance(executor.get("independent"), bool)
        or (contract.require_independent_executor and executor.get("independent") is not True)
    ):
        raise ReleaseEvidenceError("production evidence intake executor is invalid")

    subject_before = repository_subject(repo)
    security = validate_security_evidence(security_directory, subject_before)
    try:
        output_parent = output.parent.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("production evidence output parent does not exist") from exc
    resolved_output = output_parent / output.name
    if (
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", output.name) is None
        or resolved_output.exists()
        or resolved_output.is_symlink()
    ):
        raise ReleaseEvidenceError(f"refusing to overwrite production evidence: {output}")
    if output_parent == repo or repo in output_parent.parents:
        raise ReleaseEvidenceError("production evidence output must be outside the source repository")

    started_at = datetime.now(UTC)
    started_clock = time.monotonic()
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.intake-", dir=output_parent))
    seen_destinations: set[str] = {contract.report_name, "gate-statement.json"}
    seen_sources: set[Path] = set()
    total_bytes = 0
    artifact_documents: list[dict[str, object]] = []
    approval_documents: list[dict[str, object]] = []
    try:
        artifact_names: set[str] = set()
        for item in artifacts:
            if not isinstance(item, dict) or set(item) != PRODUCTION_INTAKE_ARTIFACT_FIELDS:
                raise ReleaseEvidenceError("production evidence intake contains an invalid artifact")
            name = item.get("name")
            reference = item.get("reference")
            if (
                not _valid_production_reference(name)
                or name in artifact_names
                or not _valid_production_reference(reference)
            ):
                raise ReleaseEvidenceError("production evidence intake contains an invalid artifact identity")
            relative = _production_intake_destination(item.get("destination"), category=category, approval=False)
            destination_text = relative.as_posix()
            if destination_text in seen_destinations:
                raise ReleaseEvidenceError("production evidence intake contains a duplicate destination")
            source = _external_evidence_source(item.get("source_path"), repo=repo, request=request)
            if source in seen_sources:
                raise ReleaseEvidenceError("production evidence intake cannot reuse one source file")
            size, digest = _copy_external_evidence(source, staging.joinpath(*relative.parts))
            total_bytes += size
            if total_bytes > MAX_PRODUCTION_EVIDENCE_TOTAL_BYTES:
                raise ReleaseEvidenceError("production evidence intake exceeds its total size limit")
            artifact_names.add(name)
            seen_destinations.add(destination_text)
            seen_sources.add(source)
            artifact_documents.append(
                {"name": name, "path": destination_text, "size": size, "sha256": digest, "reference": reference}
            )

        approval_roles: set[str] = set()
        for item in approvals:
            if not isinstance(item, dict) or set(item) != PRODUCTION_INTAKE_APPROVAL_FIELDS:
                raise ReleaseEvidenceError("production evidence intake contains an invalid approval")
            role = item.get("role")
            reference = item.get("reference")
            organization = item.get("organization")
            approved_at = item.get("approved_at")
            if (
                not isinstance(role, str)
                or CATEGORY_PATTERN.fullmatch(role) is None
                or role in approval_roles
                or not _valid_production_reference(reference)
                or not _valid_production_reference(organization)
            ):
                raise ReleaseEvidenceError("production evidence intake contains an invalid approval identity")
            approval_time = _parse_timestamp(approved_at, f"production intake {role} approved_at")
            if approval_time < tested_at - timedelta(minutes=5):
                raise ReleaseEvidenceError(f"production intake {role} approval predates the tested evidence")
            relative = _production_intake_destination(item.get("destination"), category=category, approval=True)
            destination_text = relative.as_posix()
            if destination_text in seen_destinations:
                raise ReleaseEvidenceError("production evidence intake contains a duplicate destination")
            source = _external_evidence_source(item.get("source_path"), repo=repo, request=request)
            if source in seen_sources:
                raise ReleaseEvidenceError("production evidence intake cannot reuse one source file")
            size, digest = _copy_external_evidence(source, staging.joinpath(*relative.parts))
            total_bytes += size
            if total_bytes > MAX_PRODUCTION_EVIDENCE_TOTAL_BYTES:
                raise ReleaseEvidenceError("production evidence intake exceeds its total size limit")
            approval_roles.add(role)
            seen_destinations.add(destination_text)
            seen_sources.add(source)
            approval_documents.append(
                {
                    "role": role,
                    "reference": reference,
                    "organization": organization,
                    "approved_at": approved_at,
                    "artifact_path": destination_text,
                    "artifact_size": size,
                    "artifact_sha256": digest,
                }
            )
        if not contract.approval_roles <= approval_roles:
            raise ReleaseEvidenceError("production evidence intake is missing required approval roles")

        report = {
            "schema": PRODUCTION_GATE_SCHEMA,
            "schema_version": 2,
            "category": category,
            "status": "passed",
            "environment_kind": document.get("environment_kind"),
            "environment_id": document.get("environment_id"),
            "tested_at": document.get("tested_at"),
            "subject": _subject_document(subject_before, security.targets),
            "checks": {name: True for name in sorted(contract.checks)},
            "executor": executor,
            "artifacts": artifact_documents,
            "approvals": approval_documents,
        }
        report_path = staging / contract.report_name
        _atomic_write(report_path, _canonical_json(report))
        finished_at = datetime.now(UTC)
        command = ["release-evidence", "register-production", category]
        attachment_documents = [
            {"path": path.relative_to(staging).as_posix(), "size": path.stat().st_size, "sha256": _sha256_file(path)}
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        ]
        statement: dict[str, Any] = {
            "schema": STATEMENT_SCHEMA,
            "schema_version": 1,
            "generated_at": finished_at.isoformat(),
            "category": category,
            "status": "passed",
            "subject": _subject_document(subject_before, security.targets),
            "security_manifest_sha256": security.manifest_sha256,
            "execution": {
                "argv": command,
                "argv_sha256": _sha256_bytes("\0".join(command).encode()),
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": round(time.monotonic() - started_clock, 6),
                "exit_code": 0,
            },
            "log_attachment": None,
            "missing_attachments": [],
            "attachments": attachment_documents,
        }
        statement_path = staging / "gate-statement.json"
        _validate_specialized_evidence(statement_path, category, statement, policy=policy)
        if repository_subject(repo) != subject_before:
            raise ReleaseEvidenceError("repository subject changed while registering production evidence")
        if validate_security_evidence(security_directory, subject_before) != security:
            raise ReleaseEvidenceError("security evidence changed while registering production evidence")
        _atomic_write(statement_path, _canonical_json(statement))
        for directory in sorted((path for path in staging.rglob("*") if path.is_dir()), reverse=True):
            _fsync_directory(directory)
        _fsync_directory(staging)
        _rename_noreplace(staging, resolved_output)
        _fsync_directory(output_parent)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        "schema_version": 1,
        "status": "registered",
        "category": category,
        "statement": str(resolved_output / "gate-statement.json"),
        "attachment_count": len(artifact_documents) + len(approval_documents) + 1,
        "total_attachment_bytes": total_bytes + (resolved_output / contract.report_name).stat().st_size,
        "production_claim": False,
    }


def _statement_category(
    path: Path,
    *,
    policy: EvidencePolicy,
    subject: RepositorySubject,
    security: SecurityEvidence,
) -> tuple[str, dict[str, Any]]:
    statement = _load_json_object(path, "release gate statement")
    if statement.get("schema") != STATEMENT_SCHEMA or statement.get("schema_version") != 1:
        raise ReleaseEvidenceError(f"unsupported release gate statement schema: {path}")
    category = statement.get("category")
    if not isinstance(category, str) or category not in policy.categories:
        raise ReleaseEvidenceError(f"release gate statement has an unknown category: {path}")
    if statement.get("status") != "passed":
        raise ReleaseEvidenceError(f"release gate statement did not pass: {category}")
    execution = statement.get("execution")
    if not isinstance(execution, dict) or execution.get("exit_code") != 0:
        raise ReleaseEvidenceError(f"release gate statement has an invalid execution result: {category}")
    if statement.get("subject") != _subject_document(subject, security.targets):
        raise ReleaseEvidenceError(f"release gate statement subject differs from the release: {category}")
    if statement.get("security_manifest_sha256") != security.manifest_sha256:
        raise ReleaseEvidenceError(f"release gate statement uses different security evidence: {category}")
    generated_at = _parse_timestamp(statement.get("generated_at"), f"{category} generated_at")
    now = datetime.now(UTC)
    if generated_at > now + timedelta(minutes=5):
        raise ReleaseEvidenceError(f"release gate statement timestamp is in the future: {category}")
    if now - generated_at > timedelta(hours=policy.categories[category]):
        raise ReleaseEvidenceError(f"release gate statement is stale: {category}")
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError(f"release gate statement attachments are invalid: {category}")
    missing_attachments = statement.get("missing_attachments", [])
    if not isinstance(missing_attachments, list) or missing_attachments:
        raise ReleaseEvidenceError(f"passed release gate statement has missing attachments: {category}")
    seen: set[str] = set()
    for raw_attachment in raw_attachments:
        if not isinstance(raw_attachment, dict):
            raise ReleaseEvidenceError(f"release gate statement attachment is invalid: {category}")
        relative_text = raw_attachment.get("path")
        relative = PurePosixPath(relative_text) if isinstance(relative_text, str) else PurePosixPath("/")
        if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative_text in seen:
            raise ReleaseEvidenceError(f"release gate statement attachment path is unsafe: {category}")
        seen.add(str(relative_text))
        attachment = path.parent.joinpath(*relative.parts)
        if attachment.is_symlink() or not attachment.is_file():
            raise ReleaseEvidenceError(f"release gate statement attachment is missing: {relative_text}")
        size = raw_attachment.get("size")
        sha256 = raw_attachment.get("sha256")
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or attachment.stat().st_size != size
            or not isinstance(sha256, str)
            or not SHA256_PATTERN.fullmatch(sha256)
            or _sha256_file(attachment) != sha256
        ):
            raise ReleaseEvidenceError(f"release gate statement attachment was modified: {relative_text}")
    _validate_specialized_evidence(path, category, statement, policy=policy)
    return category, statement


def _validate_production_gate_evidence(
    statement_path: Path,
    category: str,
    statement: dict[str, Any],
    *,
    contract: ProductionEvidenceContract,
    maximum_age_hours: int,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError(f"{category} production evidence attachments are invalid")
    attachment_inventory: dict[str, tuple[int, str]] = {}
    for raw_attachment in raw_attachments:
        if not isinstance(raw_attachment, dict):
            raise ReleaseEvidenceError(f"{category} production evidence contains invalid attachment metadata")
        relative_text = raw_attachment.get("path")
        relative = PurePosixPath(relative_text) if isinstance(relative_text, str) else PurePosixPath("/")
        size = raw_attachment.get("size")
        digest = raw_attachment.get("sha256")
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 1
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
            or relative_text in attachment_inventory
        ):
            raise ReleaseEvidenceError(f"{category} production evidence contains invalid attachment metadata")
        attachment_path = statement_path.parent.joinpath(*relative.parts)
        if (
            attachment_path.is_symlink()
            or not attachment_path.is_file()
            or attachment_path.stat().st_size != size
            or _sha256_file(attachment_path) != digest
        ):
            raise ReleaseEvidenceError(f"{category} production evidence attachment is missing or modified")
        attachment_inventory[str(relative_text)] = (size, digest)
    report_metadata = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == contract.report_name
    ]
    if len(report_metadata) != 1:
        raise ReleaseEvidenceError(
            f"{category} production evidence requires exactly one {contract.report_name} attachment"
        )
    report = _load_json_object(statement_path.parent / contract.report_name, f"{category} production report")
    environment_kind = report.get("environment_kind")
    environment_id = report.get("environment_id")
    if (
        set(report) != PRODUCTION_GATE_FIELDS
        or report.get("schema") != PRODUCTION_GATE_SCHEMA
        or report.get("schema_version") != 2
        or report.get("category") != category
        or report.get("status") != "passed"
        or environment_kind not in {"preproduction", "production"}
        or not isinstance(environment_id, str)
        or ENVIRONMENT_ID_PATTERN.fullmatch(environment_id) is None
    ):
        raise ReleaseEvidenceError(f"{category} report is not approved production-environment evidence")
    environment_tokens = set(re.split(r"[^a-z0-9]+", environment_id.casefold()))
    if environment_tokens.intersection({"dev", "development", "local", "test", "testing"}):
        raise ReleaseEvidenceError(f"{category} report identifies a local or development environment")
    if report.get("subject") != statement.get("subject"):
        raise ReleaseEvidenceError(f"{category} report is not bound to the release subject")
    statement_time = _parse_timestamp(statement.get("generated_at"), f"{category} statement generated_at")
    tested_at = _parse_timestamp(report.get("tested_at"), f"{category} tested_at")
    if tested_at > statement_time + timedelta(minutes=5) or statement_time - tested_at > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError(f"{category} report is outside the allowed evidence window")
    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or set(checks) != contract.checks
        or not all(value is True for value in checks.values())
    ):
        raise ReleaseEvidenceError(f"{category} report did not pass every contracted check")
    executor = report.get("executor")
    if (
        not isinstance(executor, dict)
        or set(executor) != {"organization", "team", "independent"}
        or not _valid_production_reference(executor.get("organization"))
        or not _valid_production_reference(executor.get("team"))
        or not isinstance(executor.get("independent"), bool)
        or (contract.require_independent_executor and executor.get("independent") is not True)
    ):
        raise ReleaseEvidenceError(f"{category} report has an invalid or non-independent executor")
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list) or not contract.minimum_artifacts <= len(artifacts) <= 100:
        raise ReleaseEvidenceError(f"{category} report has insufficient bounded artifacts")
    artifact_names: set[str] = set()
    referenced_attachment_paths: set[str] = {contract.report_name}
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) != PRODUCTION_ARTIFACT_FIELDS:
            raise ReleaseEvidenceError(f"{category} report contains an invalid artifact")
        name = artifact.get("name")
        path = artifact.get("path")
        size = artifact.get("size")
        digest = artifact.get("sha256")
        reference = artifact.get("reference")
        if (
            not _valid_production_reference(name)
            or name in artifact_names
            or not isinstance(path, str)
            or path == contract.report_name
            or path in referenced_attachment_paths
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 1
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
            or not _valid_production_reference(reference)
            or attachment_inventory.get(path) != (size, digest)
        ):
            raise ReleaseEvidenceError(f"{category} report contains an invalid, unbound or duplicate artifact")
        artifact_names.add(name)
        referenced_attachment_paths.add(path)
    approvals = report.get("approvals")
    if not isinstance(approvals, list) or not contract.approval_roles <= {
        item.get("role") for item in approvals if isinstance(item, dict) and isinstance(item.get("role"), str)
    }:
        raise ReleaseEvidenceError(f"{category} report is missing required approval roles")
    approval_roles: set[str] = set()
    for approval in approvals:
        if not isinstance(approval, dict) or set(approval) != PRODUCTION_APPROVAL_FIELDS:
            raise ReleaseEvidenceError(f"{category} report contains an invalid approval")
        role = approval.get("role")
        reference = approval.get("reference")
        organization = approval.get("organization")
        artifact_path = approval.get("artifact_path")
        artifact_size = approval.get("artifact_size")
        artifact_sha256 = approval.get("artifact_sha256")
        if (
            not isinstance(role, str)
            or CATEGORY_PATTERN.fullmatch(role) is None
            or role in approval_roles
            or not _valid_production_reference(reference)
            or not _valid_production_reference(organization)
            or not isinstance(artifact_path, str)
            or artifact_path == contract.report_name
            or artifact_path in referenced_attachment_paths
            or not isinstance(artifact_size, int)
            or isinstance(artifact_size, bool)
            or artifact_size < 1
            or not isinstance(artifact_sha256, str)
            or SHA256_PATTERN.fullmatch(artifact_sha256) is None
            or attachment_inventory.get(artifact_path) != (artifact_size, artifact_sha256)
        ):
            raise ReleaseEvidenceError(f"{category} report contains an invalid, unbound or duplicate approval")
        approved_at = _parse_timestamp(approval.get("approved_at"), f"{category} {role} approved_at")
        if approved_at < tested_at - timedelta(minutes=5):
            raise ReleaseEvidenceError(f"{category} {role} approval predates the tested evidence")
        if approved_at > statement_time + timedelta(minutes=5):
            raise ReleaseEvidenceError(f"{category} report contains a future approval")
        approval_roles.add(role)
        referenced_attachment_paths.add(artifact_path)
    if referenced_attachment_paths != set(attachment_inventory):
        raise ReleaseEvidenceError(f"{category} production evidence contains unreferenced attachments")


def _validate_clean_source_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("clean-source evidence attachments are invalid")
    report_metadata = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == CLEAN_SOURCE_REPORT
    ]
    if len(report_metadata) != 1:
        raise ReleaseEvidenceError(f"clean-source evidence requires exactly one {CLEAN_SOURCE_REPORT} attachment")
    report = _load_json_object(statement_path.parent / CLEAN_SOURCE_REPORT, "clean-source report")
    if (
        report.get("schema") != CLEAN_SOURCE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
    ):
        raise ReleaseEvidenceError("clean-source report has an invalid schema or status")

    statement_subject = statement.get("subject")
    report_subject = report.get("subject")
    if not isinstance(statement_subject, dict) or not isinstance(report_subject, dict):
        raise ReleaseEvidenceError("clean-source report subject is invalid")
    expected_subject = {
        "git_commit": statement_subject.get("git_commit"),
        "source_file_count": statement_subject.get("source_file_count"),
        "source_tree_sha256": statement_subject.get("source_tree_sha256"),
    }
    if report_subject != expected_subject:
        raise ReleaseEvidenceError("clean-source report is not bound to the release source")
    if (
        not isinstance(expected_subject["git_commit"], str)
        or COMMIT_PATTERN.fullmatch(expected_subject["git_commit"]) is None
        or not isinstance(expected_subject["source_file_count"], int)
        or isinstance(expected_subject["source_file_count"], bool)
        or expected_subject["source_file_count"] < 1
        or not isinstance(expected_subject["source_tree_sha256"], str)
        or SHA256_PATTERN.fullmatch(expected_subject["source_tree_sha256"]) is None
    ):
        raise ReleaseEvidenceError("clean-source report contains an invalid source identity")

    statement_time = _parse_timestamp(statement.get("generated_at"), "clean-source statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "clean-source report generated_at")
    maximum_age_hours = policy.categories["source_reproducibility"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("clean-source report is outside the allowed evidence window")

    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or set(checks) != CLEAN_SOURCE_CHECKS
        or not all(value is True for value in checks.values())
    ):
        raise ReleaseEvidenceError("clean-source report did not pass every contracted check")
    image_digest = report.get("application_image_digest")
    if (
        not isinstance(image_digest, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest) is None
        or report.get("application_image_user") != "app"
    ):
        raise ReleaseEvidenceError("clean-source report has an invalid non-root image result")

    commands = report.get("commands")
    if not isinstance(commands, list) or len(commands) != len(CLEAN_SOURCE_COMMANDS):
        raise ReleaseEvidenceError("clean-source report has an incomplete command inventory")
    labels: list[str] = []
    for command in commands:
        if not isinstance(command, dict):
            raise ReleaseEvidenceError("clean-source report has an invalid command result")
        label = command.get("label")
        duration_ms = command.get("duration_ms")
        if (
            not isinstance(label, str)
            or command.get("exit_code") != 0
            or not isinstance(duration_ms, int)
            or isinstance(duration_ms, bool)
            or duration_ms < 0
            or duration_ms > 3_600_000
        ):
            raise ReleaseEvidenceError("clean-source report has an invalid command result")
        labels.append(label)
    if tuple(labels) != CLEAN_SOURCE_COMMANDS:
        raise ReleaseEvidenceError("clean-source report command inventory does not match the contract")


def _validate_browser_acceptance_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("browser acceptance attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == BROWSER_ACCEPTANCE_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("browser acceptance requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / BROWSER_ACCEPTANCE_REPORT, "browser acceptance report")
    base_url = report.get("base_url")
    parsed_base_url = urlsplit(base_url) if isinstance(base_url, str) else urlsplit("")
    browser = report.get("browser")
    supported_browsers = {
        ("chrome", "Google Chrome"),
        ("msedge", "Microsoft Edge"),
    }
    reflow = report.get("reflow")
    if (
        report.get("schema") != BROWSER_ACCEPTANCE_SCHEMA
        or report.get("schema_version") != 9
        or report.get("status") != "passed"
        or report.get("production_claim") is not False
        or report.get("environment_kind") != "local-controlled-browser"
        or report.get("credentials_recorded") is not False
        or report.get("temporary_accounts_after") != 0
        or report.get("temporary_entities_after") != 0
        or report.get("temporary_chemistry_fixtures_after") != 0
        or not isinstance(reflow, dict)
        or reflow.get("scope") != "effective-css-viewport-equivalent"
        or reflow.get("css_widths") != [320, 360, 720]
        or reflow.get("system_zoom_verified") is not False
        or parsed_base_url.scheme not in {"http", "https"}
        or parsed_base_url.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed_base_url.username is not None
        or parsed_base_url.password is not None
        or parsed_base_url.query
        or parsed_base_url.fragment
        or not isinstance(browser, dict)
        or (browser.get("channel"), browser.get("product")) not in supported_browsers
        or not isinstance(browser.get("version"), str)
        or re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}", browser["version"]) is None
    ):
        raise ReleaseEvidenceError("browser acceptance report has an invalid scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "browser acceptance statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "browser acceptance generated_at")
    maximum_age_hours = policy.categories["browser"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("browser acceptance report is outside the allowed evidence window")
    scenarios = report.get("scenarios")
    if (
        not isinstance(scenarios, dict)
        or set(scenarios) != BROWSER_ACCEPTANCE_SCENARIOS
        or not all(value is True for value in scenarios.values())
    ):
        raise ReleaseEvidenceError("browser acceptance did not pass every contracted scenario")
    tests = report.get("tests")
    test_project_keys = {"desktop_1440", "desktop_1920", "tablet_1024", "mobile_390"}
    if not isinstance(tests, dict) or set(tests) != {"total", "failed", *test_project_keys}:
        raise ReleaseEvidenceError("browser acceptance test inventory is invalid")
    total = tests.get("total")
    project_counts: list[int] = []
    for key in sorted(test_project_keys):
        value = tests.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ReleaseEvidenceError("browser acceptance test inventory is incomplete")
        project_counts.append(value)
    if (
        not isinstance(total, int)
        or isinstance(total, bool)
        or any(value < 9 for value in project_counts)
        or len(set(project_counts)) != 1
        or total != sum(project_counts)
        or tests.get("failed") != 0
        or not isinstance(report.get("duration_ms"), int)
        or isinstance(report.get("duration_ms"), bool)
        or report["duration_ms"] < 1
    ):
        raise ReleaseEvidenceError("browser acceptance test inventory is incomplete")
    performance = report.get("performance")
    if (
        not isinstance(performance, dict)
        or set(performance) != {"scope", "thresholds", "projects"}
        or performance.get("scope") != "local-controlled-navigation"
        or performance.get("thresholds") != {"lcp_ms": 2500, "inp_ms": 200, "cls": 0.1}
        or not isinstance(performance.get("projects"), dict)
        or set(performance["projects"]) != test_project_keys
    ):
        raise ReleaseEvidenceError("browser acceptance performance evidence is invalid")
    for metrics in performance["projects"].values():
        if not isinstance(metrics, dict) or set(metrics) != {"cls", "inp_ms", "interaction_count", "lcp_ms"}:
            raise ReleaseEvidenceError("browser acceptance performance metrics are invalid")
        cls = metrics.get("cls")
        inp_ms = metrics.get("inp_ms")
        interaction_count = metrics.get("interaction_count")
        lcp_ms = metrics.get("lcp_ms")
        if (
            not isinstance(cls, int | float)
            or isinstance(cls, bool)
            or not 0 <= cls <= 0.1
            or not isinstance(inp_ms, int | float)
            or isinstance(inp_ms, bool)
            or not 0 <= inp_ms <= 200
            or not isinstance(interaction_count, int)
            or isinstance(interaction_count, bool)
            or interaction_count < 1
            or not isinstance(lcp_ms, int | float)
            or isinstance(lcp_ms, bool)
            or not 0 < lcp_ms <= 2500
        ):
            raise ReleaseEvidenceError("browser acceptance performance budget failed")
    visual = report.get("visual_regression")
    expected_viewports = {
        "desktop_1440": ("desktop-1440", 1440, 900),
        "desktop_1920": ("desktop-1920", 1920, 1080),
        "tablet_1024": ("tablet-1024", 1024, 768),
        "mobile_390": ("mobile-390", 390, 844),
    }
    if (
        not isinstance(visual, dict)
        or set(visual) != {"baseline_kind", "comparison", "max_diff_pixel_ratio", "projects"}
        or visual.get("baseline_kind") != "repository-owned-controlled-workbench-states"
        or visual.get("comparison") != "pixel"
        or visual.get("max_diff_pixel_ratio") != 0.001
        or not isinstance(visual.get("projects"), dict)
        or set(visual["projects"]) != test_project_keys
    ):
        raise ReleaseEvidenceError("browser acceptance visual regression evidence is invalid")
    for key, expected_viewport in expected_viewports.items():
        baseline = visual["projects"].get(key)
        if (
            not isinstance(baseline, dict)
            or set(baseline) != {"project", "width", "height", "baselines"}
            or (baseline.get("project"), baseline.get("width"), baseline.get("height")) != expected_viewport
            or not isinstance(baseline.get("baselines"), dict)
            or set(baseline["baselines"])
            != {"no_result", "dense_results", "trial_outcomes", "patent_timeline", "deal_rights"}
        ):
            raise ReleaseEvidenceError("browser acceptance visual baseline inventory is invalid")
        for state, capture in (
            ("no_result", "full-page"),
            ("dense_results", "table-shell"),
            ("trial_outcomes", "dossier-section"),
            ("patent_timeline", "dossier-section"),
            ("deal_rights", "dossier-section"),
        ):
            state_baseline = baseline["baselines"].get(state)
            if (
                not isinstance(state_baseline, dict)
                or set(state_baseline) != {"capture", "sha256"}
                or state_baseline.get("capture") != capture
                or not isinstance(state_baseline.get("sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", state_baseline["sha256"]) is None
            ):
                raise ReleaseEvidenceError("browser acceptance visual baseline inventory is invalid")


def _validate_performance_baseline_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("performance baseline attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == PERFORMANCE_BASELINE_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("performance baseline requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / PERFORMANCE_BASELINE_REPORT, "performance baseline report")
    if (
        report.get("schema") != PERFORMANCE_BASELINE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("production_claim") is not False
        or report.get("environment_kind") != "local-controlled-baseline"
        or report.get("credentials_recorded") is not False
        or report.get("temporary_users_after") != 0
        or report.get("temporary_human_role") != "viewer"
    ):
        raise ReleaseEvidenceError("performance baseline report has an invalid scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "performance baseline statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "performance baseline generated_at")
    maximum_age_hours = policy.categories["performance_baseline"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("performance baseline is outside the allowed evidence window")
    assertions = report.get("assertions")
    if (
        not isinstance(assertions, dict)
        or set(assertions) != PERFORMANCE_BASELINE_ASSERTIONS
        or not all(value is True for value in assertions.values())
    ):
        raise ReleaseEvidenceError("performance baseline did not pass every mixed-load assertion")
    phases = report.get("phases")
    if not isinstance(phases, list) or len(phases) != 2:
        raise ReleaseEvidenceError("performance baseline phase inventory is incomplete")
    by_name = {phase.get("name"): phase for phase in phases if isinstance(phase, dict)}
    if set(by_name) != {"sustained", "peak"}:
        raise ReleaseEvidenceError("performance baseline phase inventory is incomplete")
    for name, phase in by_name.items():
        requested = phase.get("requested")
        completed = phase.get("completed")
        concurrency = phase.get("concurrency")
        web_completed = phase.get("web_completed")
        mcp_completed = phase.get("mcp_completed")
        if (
            not isinstance(requested, int)
            or isinstance(requested, bool)
            or requested < 2
            or completed != requested
            or phase.get("failed") != 0
            or phase.get("errors") != []
            or not isinstance(concurrency, int)
            or isinstance(concurrency, bool)
            or concurrency < 2
            or not isinstance(web_completed, int)
            or isinstance(web_completed, bool)
            or web_completed < 1
            or not isinstance(mcp_completed, int)
            or isinstance(mcp_completed, bool)
            or mcp_completed < 1
            or web_completed + mcp_completed != completed
            or phase.get("unique_mcp_settlements") != mcp_completed
        ):
            raise ReleaseEvidenceError(f"performance baseline {name} phase is incomplete")
    if by_name["peak"]["concurrency"] <= by_name["sustained"]["concurrency"]:
        raise ReleaseEvidenceError("performance baseline peak does not exceed sustained concurrency")
    aggregate = report.get("aggregate")
    if not isinstance(aggregate, dict):
        raise ReleaseEvidenceError("performance baseline aggregate is invalid")
    mcp_completed = aggregate.get("mcp_completed")
    expected_web_completed = sum(int(phase["web_completed"]) for phase in by_name.values())
    expected_mcp_completed = sum(int(phase["mcp_completed"]) for phase in by_name.values())
    charged_units = aggregate.get("charged_units_delta")
    consumed_units = aggregate.get("consumed_units_delta")
    thresholds = report.get("thresholds")
    web_latency = aggregate.get("web_latency_ms")
    mcp_latency = aggregate.get("mcp_latency_ms")
    if (
        not isinstance(mcp_completed, int)
        or isinstance(mcp_completed, bool)
        or mcp_completed < 1
        or aggregate.get("web_completed") != expected_web_completed
        or mcp_completed != expected_mcp_completed
        or aggregate.get("settlement_delta") != mcp_completed
        or not isinstance(charged_units, str)
        or UNITS_PATTERN.fullmatch(charged_units) is None
        or charged_units == "0.00000000"
        or charged_units != consumed_units
        or aggregate.get("active_reservations_after_load") != 0
        or aggregate.get("active_reservations_final") != 0
        or not isinstance(thresholds, dict)
        or not isinstance(web_latency, dict)
        or not isinstance(mcp_latency, dict)
        or not isinstance(thresholds.get("web_p95_ms"), int | float)
        or isinstance(thresholds.get("web_p95_ms"), bool)
        or not isinstance(thresholds.get("mcp_p95_ms"), int | float)
        or isinstance(thresholds.get("mcp_p95_ms"), bool)
        or not isinstance(web_latency.get("p95"), int | float)
        or isinstance(web_latency.get("p95"), bool)
        or not isinstance(mcp_latency.get("p95"), int | float)
        or isinstance(mcp_latency.get("p95"), bool)
        or web_latency["p95"] > thresholds["web_p95_ms"]
        or mcp_latency["p95"] > thresholds["mcp_p95_ms"]
    ):
        raise ReleaseEvidenceError("performance baseline metering aggregate is inconsistent")
    race = report.get("concurrent_idempotency")
    if not isinstance(race, dict):
        raise ReleaseEvidenceError("performance baseline concurrent idempotency evidence is incomplete")
    race_assertions = race.get("assertions")
    if (
        not isinstance(race_assertions, dict)
        or set(race_assertions) != PERFORMANCE_RACE_ASSERTIONS
        or not all(value is True for value in race_assertions.values())
        or race.get("settlement_delta") != 1
        or race.get("unique_settlements") != 1
        or race.get("active_reservations_after") != 0
    ):
        raise ReleaseEvidenceError("performance baseline concurrent idempotency evidence is incomplete")
    failure = report.get("failure_injection")
    failure_assertions = failure.get("assertions") if isinstance(failure, dict) else None
    if (
        not isinstance(failure_assertions, dict)
        or not failure_assertions
        or not all(value is True for value in failure_assertions.values())
    ):
        raise ReleaseEvidenceError("performance baseline failure injection evidence is incomplete")
    coverage = report.get("coverage")
    gaps = report.get("production_gaps")
    if (
        not isinstance(coverage, dict)
        or coverage.get("long_running") is not False
        or coverage.get("target_infrastructure_faults") is not False
        or coverage.get("production_approvals") is not False
        or not isinstance(gaps, list)
        or len(gaps) < 3
        or not all(isinstance(gap, str) and gap for gap in gaps)
    ):
        raise ReleaseEvidenceError("performance baseline does not preserve its production boundary")


def _validate_ingestion_readiness_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("ingestion readiness attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == INGESTION_READINESS_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("ingestion readiness requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / INGESTION_READINESS_REPORT, "ingestion readiness report")
    readiness = report.get("readiness")
    services = report.get("services")
    if (
        report.get("schema") != INGESTION_READINESS_EVIDENCE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl"
        or report.get("production_claim") is not False
        or report.get("real_source_automatic_ingestion_verified") is not False
        or not isinstance(readiness, dict)
        or not isinstance(services, list)
    ):
        raise ReleaseEvidenceError("ingestion readiness report has an invalid scope or status")
    service_names = {service.get("service") for service in services if isinstance(service, dict)}
    if (
        service_names != INGESTION_READINESS_SERVICES
        or len(services) != len(INGESTION_READINESS_SERVICES)
        or any(
            not isinstance(service, dict)
            or service.get("running") is not True
            or service.get("health") not in {"healthy", "not-configured"}
            for service in services
        )
    ):
        raise ReleaseEvidenceError("ingestion readiness required services are incomplete")
    inventory = readiness.get("inventory")
    connectors = readiness.get("connectors")
    runtime = readiness.get("runtime")
    checks = runtime.get("checks") if isinstance(runtime, dict) else None
    connector_ids = (
        {connector.get("connector_id") for connector in connectors if isinstance(connector, dict)}
        if isinstance(connectors, list)
        else set()
    )
    if (
        readiness.get("schema") != INGESTION_READINESS_SCHEMA
        or readiness.get("schema_version") != 1
        or readiness.get("status") not in {"ready_for_source_registration", "ready_for_ingestion"}
        or readiness.get("production_claim") is not False
        or readiness.get("real_source_automatic_ingestion_verified") is not False
        or not isinstance(inventory, dict)
        or inventory.get("blocked_source_count") != 0
        or not isinstance(connectors, list)
        or len(connectors) != len(INGESTION_READINESS_CONNECTOR_IDS)
        or connector_ids != INGESTION_READINESS_CONNECTOR_IDS
        or any(
            not isinstance(connector, dict)
            or connector.get("incremental") is not True
            or connector.get("replayable") is not True
            or connector.get("immutable_snapshot_required") is not True
            for connector in connectors
        )
        or not isinstance(checks, list)
        or any(not isinstance(check, dict) or check.get("status") != "pass" for check in checks)
    ):
        raise ReleaseEvidenceError("ingestion readiness platform controls are incomplete")
    statement_time = _parse_timestamp(statement.get("generated_at"), "ingestion readiness statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "ingestion readiness generated_at")
    maximum_age_hours = policy.categories["ingestion_readiness"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("ingestion readiness report is outside the allowed evidence window")


def _ingestion_nonnegative_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_ingestion_source_inventory(
    inventory: object,
    *,
    source_id: str,
    source_type: str,
) -> None:
    if not isinstance(inventory, dict) or set(inventory) != INGESTION_SOURCE_FIELDS:
        raise ReleaseEvidenceError("pilot ingestion source inventory is invalid")
    numeric_fields = ("discovered", "stable", "oversized", "excluded", "error_count", "configuration_error_count")
    if (
        inventory.get("schema_version") != 1
        or inventory.get("source_id") != source_id
        or inventory.get("source_type") != source_type
        or inventory.get("connector_id") != INGESTION_SOURCE_CONNECTORS[source_type]
        or not isinstance(inventory.get("authoritative_inventory"), bool)
        or any(not _ingestion_nonnegative_integer(inventory.get(name)) for name in numeric_fields)
        or inventory.get("oversized") != 0
        or inventory.get("error_count") != 0
        or inventory.get("configuration_error_count") != 0
        or inventory.get("discovered", 0) < 1
        or inventory.get("stable", 0) < 1
        or inventory.get("stable", 0) > inventory.get("discovered", 0)
    ):
        raise ReleaseEvidenceError("pilot ingestion source inventory is incomplete or unhealthy")


def _validate_ingestion_counters(counters: object, *, idempotent: bool) -> None:
    if (
        not isinstance(counters, dict)
        or set(counters) != INGESTION_COUNTER_FIELDS
        or any(not _ingestion_nonnegative_integer(counters.get(name)) for name in INGESTION_COUNTER_FIELDS)
        or counters.get("failed") != 0
        or counters.get("unstable") != 0
        or (idempotent and counters.get("discovered") != 0)
        or (idempotent and counters.get("unchanged", 0) < 1)
    ):
        raise ReleaseEvidenceError("pilot ingestion run counters are invalid or not idempotent")


def _validate_ingestion_versions(versions: object, *, idempotence_field: bool) -> tuple[int, int]:
    expected_fields = {
        "current",
        "traceable",
        "malware_scanned",
        "processed",
        "governable",
        "governed",
        "projected",
        "failed",
    }
    if idempotence_field:
        expected_fields.add("idempotent_second_scan")
    if not isinstance(versions, dict) or set(versions) != expected_fields:
        raise ReleaseEvidenceError("pilot ingestion version inventory is invalid")
    current = versions.get("current")
    governable = versions.get("governable")
    if (
        not isinstance(current, int)
        or isinstance(current, bool)
        or current < 1
        or not isinstance(governable, int)
        or isinstance(governable, bool)
        or not 1 <= governable <= current
        or any(versions.get(name) != current for name in ("traceable", "malware_scanned", "processed"))
        or any(versions.get(name) != governable for name in ("governed", "projected"))
        or versions.get("failed") != 0
        or (idempotence_field and versions.get("idempotent_second_scan") is not True)
    ):
        raise ReleaseEvidenceError("pilot ingestion versions are not fully governed and traceable")
    return current, governable


def _validate_ingestion_governance(governance: object, *, governable_versions: int) -> None:
    if not isinstance(governance, dict) or set(governance) != INGESTION_GOVERNANCE_FIELDS:
        raise ReleaseEvidenceError("pilot ingestion AI governance accounting is invalid")
    configured_model = governance.get("configured_model")
    numeric_fields = INGESTION_GOVERNANCE_FIELDS - {"configured_model"}
    if (
        not isinstance(configured_model, str)
        or not 1 <= len(configured_model) <= 160
        or any(not _ingestion_nonnegative_integer(governance.get(name)) for name in numeric_fields)
    ):
        raise ReleaseEvidenceError("pilot ingestion AI governance metadata is invalid")
    extraction_runs = governance["extraction_runs"]
    staged_facts = governance["staged_facts"]
    if (
        extraction_runs < governable_versions
        or governance["successful_extraction_runs"] != extraction_runs
        or governance["configured_model_runs"] != extraction_runs
        or governance["failed_extraction_runs"] != 0
        or governance["input_tokens"] < 1
        or governance["output_tokens"] < 1
        or governance["segments"] < 1
        or governance["accounted_segments"] != governance["segments"]
        or staged_facts < 1
        or not 1 <= governance["quote_verified_facts"] <= staged_facts
    ):
        raise ReleaseEvidenceError("pilot ingestion AI governance is incomplete or unaccounted")


def _validate_ingestion_search(search: object) -> None:
    cluster = search.get("cluster") if isinstance(search, dict) else None
    deliveries = search.get("deliveries") if isinstance(search, dict) else None
    if (
        not isinstance(search, dict)
        or set(search) != {"cluster", "deliveries"}
        or not isinstance(cluster, dict)
        or set(cluster) != {"aliases", "available", "cluster_name", "cluster_status", "error", "version"}
        or cluster.get("available") is not True
        or cluster.get("cluster_name") != "pharma-search"
        or cluster.get("cluster_status") != "green"
        or cluster.get("error") is not None
        or cluster.get("version") != "3.7.0"
        or not isinstance(cluster.get("aliases"), dict)
        or set(cluster["aliases"]) != {"entities", "evidence", "knowledge"}
        or not isinstance(deliveries, dict)
        or set(deliveries) != {"dead", "processing", "retry", "succeeded"}
        or any(deliveries.get(name) != 0 for name in ("dead", "processing", "retry"))
        or not _ingestion_nonnegative_integer(deliveries.get("succeeded"))
    ):
        raise ReleaseEvidenceError("pilot ingestion OpenSearch projection evidence is invalid")
    for name, aliases in cluster["aliases"].items():
        if (
            not isinstance(aliases, list)
            or len(aliases) != 1
            or not isinstance(aliases[0], str)
            or not aliases[0].startswith(f"pharma-{name}-v2-")
        ):
            raise ReleaseEvidenceError(f"pilot ingestion OpenSearch alias is invalid: {name}")


def _validate_ingestion_pilot_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    expected_reports = {INGESTION_PILOT_REPORT, AUTOMATIC_INGESTION_REPORT}
    attachment_paths = (
        [item.get("path") for item in raw_attachments if isinstance(item, dict)]
        if isinstance(raw_attachments, list)
        else []
    )
    log_attachment = statement.get("log_attachment")
    expected_attachments = set(expected_reports)
    if log_attachment is not None:
        if not isinstance(log_attachment, str):
            raise ReleaseEvidenceError("pilot ingestion capture log attachment is invalid")
        expected_attachments.add(log_attachment)
    if (
        not isinstance(raw_attachments, list)
        or len(attachment_paths) != len(expected_attachments)
        or set(attachment_paths) != expected_attachments
    ):
        raise ReleaseEvidenceError("pilot ingestion requires exactly two governed report attachments")
    manual = _load_json_object(statement_path.parent / INGESTION_PILOT_REPORT, "pilot ingestion report")
    automatic = _load_json_object(
        statement_path.parent / AUTOMATIC_INGESTION_REPORT,
        "automatic ingestion report",
    )
    if (
        set(manual) != INGESTION_PILOT_FIELDS
        or manual.get("schema") != INGESTION_PILOT_SCHEMA
        or manual.get("schema_version") != 2
        or manual.get("status") != "passed"
        or manual.get("environment") != "local-wsl"
        or manual.get("production_claim") is not False
        or manual.get("source_content_created_by_test") is not False
        or set(automatic) != AUTOMATIC_INGESTION_FIELDS
        or automatic.get("schema") != AUTOMATIC_INGESTION_SCHEMA
        or automatic.get("schema_version") != 4
        or automatic.get("status") != "passed"
        or automatic.get("environment") != "local-wsl"
        or automatic.get("production_claim") is not False
    ):
        raise ReleaseEvidenceError("pilot ingestion reports have an invalid schema, scope or status")
    source_id = manual.get("source_id")
    source_type = manual.get("source_type")
    dataset_key = manual.get("dataset_key")
    license_id = manual.get("license_id")
    if (
        not isinstance(source_id, str)
        or UUID_PATTERN.fullmatch(source_id) is None
        or source_type not in INGESTION_SOURCE_CONNECTORS
        or not isinstance(dataset_key, str)
        or re.fullmatch(r"[A-Za-z0-9._-]{1,80}", dataset_key) is None
        or not isinstance(license_id, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,119}", license_id) is None
        or any(
            automatic.get(name) != manual.get(name)
            for name in ("source_id", "source_type", "dataset_key", "license_id")
        )
    ):
        raise ReleaseEvidenceError("pilot ingestion reports do not identify the same licensed real source")
    _validate_ingestion_source_inventory(manual.get("source_files"), source_id=source_id, source_type=source_type)
    manual_versions, manual_governable = _validate_ingestion_versions(manual.get("versions"), idempotence_field=True)
    _validate_ingestion_governance(manual.get("governance"), governable_versions=manual_governable)
    runs = manual.get("runs")
    if not isinstance(runs, list) or len(runs) != 2:
        raise ReleaseEvidenceError("pilot ingestion report must contain exactly two manual acceptance runs")
    run_ids: set[str] = set()
    for index, run in enumerate(runs):
        run_id = run.get("id") if isinstance(run, dict) else None
        if (
            not isinstance(run, dict)
            or set(run) != {"id", "state", "counters"}
            or not isinstance(run_id, str)
            or UUID_PATTERN.fullmatch(run_id) is None
            or run_id in run_ids
            or run.get("state") != "SUCCEEDED"
        ):
            raise ReleaseEvidenceError("pilot ingestion manual run identity or state is invalid")
        _validate_ingestion_counters(run.get("counters"), idempotent=index == 1)
        run_ids.add(run_id)
    _validate_ingestion_search(manual.get("search"))

    trigger = automatic.get("trigger")
    if (
        not isinstance(trigger, dict)
        or set(trigger)
        != {
            "mode",
            "outcome",
            "manual_trigger_used",
            "source_schedule_mutated",
            "source_content_created_by_test",
            "scan_interval_seconds",
            "initial_due_in_seconds",
            "observed_elapsed_seconds",
            "baseline_versions",
            "observed_versions",
            "new_versions",
            "baseline_run_id",
            "baseline_run_created_at",
            "observed_run_created_at",
            "policy_sha256",
            "baseline_policy_runs",
            "observed_policy_runs",
        }
        or trigger.get("mode") != "temporal-scheduler"
        or trigger.get("outcome") not in {"new_version", "policy_reprocess", "unchanged"}
        or trigger.get("manual_trigger_used") is not False
        or trigger.get("source_schedule_mutated") is not False
        or trigger.get("source_content_created_by_test") is not False
        or not isinstance(trigger.get("scan_interval_seconds"), int)
        or isinstance(trigger.get("scan_interval_seconds"), bool)
        or not 10 <= trigger["scan_interval_seconds"] <= 86_400
        or not _ingestion_nonnegative_integer(trigger.get("initial_due_in_seconds"))
        or trigger["initial_due_in_seconds"] > 86_400
        or not _ingestion_nonnegative_integer(trigger.get("observed_elapsed_seconds"))
        or trigger["observed_elapsed_seconds"] > 86_400
        or not _ingestion_nonnegative_integer(trigger.get("baseline_versions"))
        or not _ingestion_nonnegative_integer(trigger.get("observed_versions"))
        or not _ingestion_nonnegative_integer(trigger.get("new_versions"))
        or trigger["observed_versions"] - trigger["baseline_versions"] != trigger["new_versions"]
        or not isinstance(trigger.get("baseline_run_id"), str)
        or UUID_PATTERN.fullmatch(trigger["baseline_run_id"]) is None
        or not isinstance(trigger.get("policy_sha256"), str)
        or SHA256_PATTERN.fullmatch(trigger["policy_sha256"]) is None
        or not _ingestion_nonnegative_integer(trigger.get("baseline_policy_runs"))
        or not _ingestion_nonnegative_integer(trigger.get("observed_policy_runs"))
        or trigger["observed_policy_runs"] < trigger["baseline_policy_runs"]
    ):
        raise ReleaseEvidenceError("automatic ingestion was not observed through an unchanged Temporal schedule")
    baseline_run_time = _parse_timestamp(
        trigger.get("baseline_run_created_at"), "automatic ingestion baseline run created_at"
    )
    observed_run_time = _parse_timestamp(
        trigger.get("observed_run_created_at"), "automatic ingestion observed run created_at"
    )
    workflow = automatic.get("workflow")
    workflow_id = workflow.get("workflow_id") if isinstance(workflow, dict) else None
    automatic_run_id = workflow.get("run_id") if isinstance(workflow, dict) else None
    if (
        not isinstance(workflow, dict)
        or set(workflow) != {"run_id", "workflow_id", "state", "counters"}
        or not isinstance(automatic_run_id, str)
        or UUID_PATTERN.fullmatch(automatic_run_id) is None
        or automatic_run_id in run_ids
        or not isinstance(workflow_id, str)
        or not workflow_id.startswith(f"source-ingest-{source_id}-")
        or workflow.get("state") != "SUCCEEDED"
    ):
        raise ReleaseEvidenceError("automatic ingestion workflow identity or state is invalid")
    if (observed_run_time, automatic_run_id) <= (baseline_run_time, trigger["baseline_run_id"]):
        raise ReleaseEvidenceError("automatic ingestion workflow is not newer than the captured scheduler watermark")
    unchanged_outcome = trigger["outcome"] == "unchanged"
    _validate_ingestion_counters(workflow.get("counters"), idempotent=unchanged_outcome)
    counters = workflow.get("counters")
    if not isinstance(counters, dict):
        raise ReleaseEvidenceError("automatic ingestion counters are invalid")
    if unchanged_outcome:
        if (
            trigger["new_versions"] != 0
            or trigger["observed_policy_runs"] != trigger["baseline_policy_runs"]
            or trigger["observed_versions"] < 1
            or counters.get("discovered") != 0
            or counters.get("unchanged", 0) < 1
        ):
            raise ReleaseEvidenceError("automatic ingestion did not prove unchanged-source idempotence")
    elif trigger["outcome"] == "policy_reprocess":
        if (
            trigger["new_versions"] != 0
            or trigger["observed_policy_runs"] <= trigger["baseline_policy_runs"]
            or counters.get("discovered", 0) < 1
        ):
            raise ReleaseEvidenceError("automatic ingestion did not prove current-policy source reprocessing")
    elif (
        trigger["new_versions"] < 1
        or trigger["observed_policy_runs"] <= trigger["baseline_policy_runs"]
        or counters.get("discovered", 0) < 1
    ):
        raise ReleaseEvidenceError("automatic ingestion did not discover and govern a new source version")
    automatic_versions, automatic_governable = _validate_ingestion_versions(
        automatic.get("versions"), idempotence_field=False
    )
    _validate_ingestion_governance(automatic.get("governance"), governable_versions=automatic_governable)
    if automatic_versions != manual_versions or automatic_governable != manual_governable:
        raise ReleaseEvidenceError("manual idempotence scans changed the automatically governed source inventory")
    if automatic.get("governance") != manual.get("governance"):
        raise ReleaseEvidenceError("manual idempotence scans changed AI governance accounting")
    _validate_ingestion_search(automatic.get("search"))

    statement_time = _parse_timestamp(statement.get("generated_at"), "pilot ingestion statement generated_at")
    manual_time = _parse_timestamp(manual.get("generated_at"), "pilot ingestion generated_at")
    automatic_time = _parse_timestamp(automatic.get("generated_at"), "automatic ingestion generated_at")
    maximum_age_hours = policy.categories["ingestion_pilot"] if policy is not None else 168
    if (
        observed_run_time > automatic_time
        or automatic_time > manual_time
        or manual_time > statement_time + timedelta(minutes=5)
        or statement_time - automatic_time > timedelta(hours=maximum_age_hours)
    ):
        raise ReleaseEvidenceError("pilot ingestion reports are outside the allowed evidence window or order")


def _validate_record_consistency_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("record consistency attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == RECORD_CONSISTENCY_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("record consistency requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / RECORD_CONSISTENCY_REPORT, "record consistency report")
    if (
        set(report) != RECORD_CONSISTENCY_FIELDS
        or report.get("schema") != RECORD_CONSISTENCY_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl-isolated-postgresql"
        or report.get("production_claim") is not False
        or report.get("controlled_fixture") is not True
        or report.get("credentials_recorded") is not False
    ):
        raise ReleaseEvidenceError("record consistency report has an invalid scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "record consistency statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "record consistency generated_at")
    maximum_age_hours = policy.categories["record_consistency"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("record consistency report is outside the allowed evidence window")
    identity_fields = (
        "activity_id",
        "target_id",
        "provenance_id",
        "source_version_id",
        "source_document_id",
    )
    if any(
        not isinstance(report.get(field), str) or UUID_PATTERN.fullmatch(report[field]) is None
        for field in identity_fields
    ):
        raise ReleaseEvidenceError("record consistency authority identifiers are invalid")
    digest_fields = ("activity_sha256", "provenance_sha256", "export_row_sha256")
    if any(
        not isinstance(report.get(field), str) or SHA256_PATTERN.fullmatch(report[field]) is None
        for field in digest_fields
    ):
        raise ReleaseEvidenceError("record consistency canonical digests are invalid")
    source_locator = report.get("source_locator")
    if not isinstance(source_locator, str) or not 1 <= len(source_locator) <= 500:
        raise ReleaseEvidenceError("record consistency source locator is invalid")
    web_operations = report.get("web_operations")
    mcp_tools = report.get("mcp_tools")
    if (
        not isinstance(web_operations, list)
        or len(web_operations) != len(RECORD_CONSISTENCY_WEB_OPERATIONS)
        or set(web_operations) != RECORD_CONSISTENCY_WEB_OPERATIONS
        or not isinstance(mcp_tools, list)
        or len(mcp_tools) != len(RECORD_CONSISTENCY_MCP_TOOLS)
        or set(mcp_tools) != RECORD_CONSISTENCY_MCP_TOOLS
        or report.get("mcp_protocol_version") != "2025-11-25"
    ):
        raise ReleaseEvidenceError("record consistency protocol operation inventory is incomplete")
    if (
        report.get("billed_operations") != 3
        or report.get("unique_settlements") != 3
        or report.get("export_dataset") != "fact_provenance"
        or report.get("export_record_count") != 1
        or report.get("export_manifest_verified") is not True
        or report.get("same_authority_identifiers") is not True
        or report.get("same_source_version") is not True
        or report.get("same_source_locator") is not True
    ):
        raise ReleaseEvidenceError("record consistency authority or commercial assertions are incomplete")
    cleanup = report.get("cleanup")
    if cleanup != {"api_stopped": True, "mcp_stopped": True, "database_dropped": True}:
        raise ReleaseEvidenceError("record consistency isolated runtime cleanup is incomplete")


def _validate_mcp_async_task_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("MCP async task attachments are invalid")
    reports = [item for item in raw_attachments if isinstance(item, dict) and item.get("path") == MCP_ASYNC_TASK_REPORT]
    if len(reports) != 1:
        raise ReleaseEvidenceError("MCP async task evidence requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / MCP_ASYNC_TASK_REPORT, "MCP async task report")
    if (
        set(report) != MCP_ASYNC_TASK_FIELDS
        or report.get("schema") != MCP_ASYNC_TASK_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl-isolated-postgresql-object-store"
        or report.get("production_claim") is not False
        or report.get("controlled_fixture") is not True
        or report.get("credentials_recorded") is not False
        or report.get("protocol_version") != "2025-11-25"
        or report.get("client_count") != 2
        or report.get("same_authority_record_set") is not True
    ):
        raise ReleaseEvidenceError("MCP async task report has an invalid scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "MCP async task statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "MCP async task generated_at")
    maximum_age_hours = policy.categories["mcp_async_tasks"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("MCP async task report is outside the allowed evidence window")

    clients = report.get("clients")
    if not isinstance(clients, list) or len(clients) != 2 or not all(isinstance(item, dict) for item in clients):
        raise ReleaseEvidenceError("MCP async task client inventory is invalid")
    expected_clients = {"MCP Inspector", "Python MCP SDK"}
    client_names = {item.get("client") for item in clients}
    if client_names != expected_clients:
        raise ReleaseEvidenceError("MCP async task evidence omitted an independent client")
    authority_digests: set[str] = set()
    for client in clients:
        if (
            set(client) != MCP_ASYNC_TASK_CLIENT_FIELDS
            or client.get("status") != "passed"
            or client.get("tasks_created") != 2
            or client.get("completed_tasks") != 1
            or client.get("cancelled_tasks") != 1
            or client.get("result_pages") != 2
            or client.get("unique_records") != 2
            or client.get("tampered_cursor_rejected") is not True
            or client.get("recovered_after_error") is not True
            or client.get("settlement_created") is not True
            or client.get("credentials_recorded") is not False
        ):
            raise ReleaseEvidenceError("MCP async task client workflow is incomplete")
        version = client.get("client_version")
        if not isinstance(version, str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
            raise ReleaseEvidenceError("MCP async task client version is invalid")
        for field in ("entity_ids_sha256", "manifest_sha256"):
            value = client.get(field)
            if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
                raise ReleaseEvidenceError("MCP async task client digest is invalid")
        authority_digests.add(client["entity_ids_sha256"])
    if len(authority_digests) != 1:
        raise ReleaseEvidenceError("MCP async task clients returned different authority record sets")

    if report.get("database") != {
        "tasks": 4,
        "completed_tasks": 2,
        "cancelled_tasks": 2,
        "settlements": 2,
        "signed_completed_tasks": 2,
        "active_reservations_after": 0,
    }:
        raise ReleaseEvidenceError("MCP async task accounting evidence is incomplete")
    assertions = report.get("assertions")
    if (
        not isinstance(assertions, dict)
        or set(assertions) != MCP_ASYNC_TASK_ASSERTIONS
        or any(value is not True for value in assertions.values())
    ):
        raise ReleaseEvidenceError("MCP async task assertions are incomplete")
    if report.get("cleanup") != {
        "api_stopped": True,
        "mcp_stopped": True,
        "database_dropped": True,
        "temporary_object_store_destroyed": True,
    }:
        raise ReleaseEvidenceError("MCP async task isolated runtime cleanup is incomplete")


def _validate_anti_extraction_baseline_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("anti-extraction baseline attachments are invalid")
    reports = [
        item
        for item in raw_attachments
        if isinstance(item, dict) and item.get("path") == ANTI_EXTRACTION_BASELINE_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("anti-extraction baseline requires exactly one report.json attachment")
    report = _load_json_object(
        statement_path.parent / ANTI_EXTRACTION_BASELINE_REPORT,
        "anti-extraction baseline report",
    )
    if (
        set(report) != ANTI_EXTRACTION_BASELINE_FIELDS
        or report.get("schema") != ANTI_EXTRACTION_BASELINE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl-isolated-postgresql"
        or report.get("production_claim") is not False
        or report.get("controlled_fixture") is not True
        or report.get("credentials_recorded") is not False
        or report.get("auth_profile") != "isolated-database-api-key"
        or report.get("production_oidc_covered") is not False
        or report.get("protocol_version") != "2025-11-25"
    ):
        raise ReleaseEvidenceError("anti-extraction baseline report has an invalid scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "anti-extraction statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "anti-extraction generated_at")
    maximum_age_hours = policy.categories["anti_extraction_baseline"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("anti-extraction baseline report is outside the allowed evidence window")
    if report.get("scenarios") != ANTI_EXTRACTION_BASELINE_SCENARIOS:
        raise ReleaseEvidenceError("anti-extraction baseline scenario inventory is incomplete")
    assertions = report.get("assertions")
    if (
        not isinstance(assertions, dict)
        or set(assertions) != ANTI_EXTRACTION_BASELINE_ASSERTIONS
        or not all(value is True for value in assertions.values())
    ):
        raise ReleaseEvidenceError("anti-extraction baseline assertions are incomplete")
    database = report.get("database")
    expected_database_fields = {
        "durable_denial_reason_count",
        "successful_settlement_count",
        "active_reservations_after",
        "unauthorized_export_jobs_created",
        "credential_revocation_audit_events",
        "raw_partition_values_persisted",
        "raw_correlation_values_persisted",
    }
    settlements = database.get("successful_settlement_count") if isinstance(database, dict) else None
    if (
        not isinstance(database, dict)
        or set(database) != expected_database_fields
        or database.get("durable_denial_reason_count") != 4
        or not isinstance(settlements, int)
        or isinstance(settlements, bool)
        or settlements < 9
        or database.get("active_reservations_after") != 0
        or database.get("unauthorized_export_jobs_created") != 0
        or database.get("credential_revocation_audit_events") != 1
        or database.get("raw_partition_values_persisted") is not False
        or database.get("raw_correlation_values_persisted") is not False
    ):
        raise ReleaseEvidenceError("anti-extraction baseline durable database evidence is incomplete")
    if report.get("cleanup") != {"api_stopped": True, "mcp_stopped": True, "database_dropped": True}:
        raise ReleaseEvidenceError("anti-extraction baseline isolated runtime cleanup is incomplete")
    duration = report.get("duration_seconds")
    if not isinstance(duration, int | float) or isinstance(duration, bool) or not 0 < duration <= 600:
        raise ReleaseEvidenceError("anti-extraction baseline duration is invalid")


def _validate_backup_restore_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("backup restore attachments are invalid")
    reports = [item for item in raw_attachments if isinstance(item, dict) and item.get("path") == BACKUP_RESTORE_REPORT]
    if len(reports) != 1:
        raise ReleaseEvidenceError("backup restore evidence requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / BACKUP_RESTORE_REPORT, "backup restore report")
    if (
        set(report) != BACKUP_RESTORE_FIELDS
        or report.get("schema") != BACKUP_RESTORE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
    ):
        raise ReleaseEvidenceError("backup restore report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "backup restore statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "backup restore generated_at")
    maximum_age_hours = policy.categories["backup_restore"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("backup restore report is outside the allowed evidence window")
    reference_text = report.get("backup_reference")
    reference = PurePosixPath(reference_text) if isinstance(reference_text, str) else PurePosixPath("/")
    if (
        reference.is_absolute()
        or ".." in reference.parts
        or len(reference.parts) < 3
        or reference.parts[:2] != ("backups", "release-candidates")
    ):
        raise ReleaseEvidenceError("backup restore authority reference is unsafe")
    if any(
        not isinstance(report.get(field), str) or SHA256_PATTERN.fullmatch(report[field]) is None
        for field in ("backup_manifest_sha256", "backup_checksums_sha256")
    ):
        raise ReleaseEvidenceError("backup restore authority digests are invalid")
    integer_minimums = {
        "authority_artifacts": 6,
        "authority_bytes": 1,
        "tables_verified": 1,
    }
    if any(
        not isinstance(report.get(field), int) or isinstance(report[field], bool) or report[field] < minimum
        for field, minimum in integer_minimums.items()
    ):
        raise ReleaseEvidenceError("backup restore authority inventory is incomplete")
    if (
        report.get("alembic_head") != "5d7e1a3c9b24"
        or report.get("rdkit_version") != "4.8.0"
        or report.get("temporal_databases_restored") != 2
        or report.get("rls_probe") != "passed"
        or report.get("archives_verified") != 2
        or report.get("main_runtime_modified") is not False
        or report.get("sensitive_backup_embedded") is not False
    ):
        raise ReleaseEvidenceError("backup restore authority assertions are incomplete")
    duration = report.get("duration_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 0 < duration <= 3600:
        raise ReleaseEvidenceError("backup restore duration is invalid")


def _validate_kubernetes_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("Kubernetes validation attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == KUBERNETES_VALIDATION_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("Kubernetes validation requires exactly one report.json attachment")
    report = _load_json_object(
        statement_path.parent / KUBERNETES_VALIDATION_REPORT,
        "Kubernetes validation report",
    )
    if (
        set(report) != KUBERNETES_VALIDATION_FIELDS
        or report.get("schema") != KUBERNETES_VALIDATION_SCHEMA
        or report.get("schema_version") != 3
        or report.get("status") != "passed"
        or report.get("environment") != "local-isolated-kind"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
        or report.get("controlled_cluster") is not True
    ):
        raise ReleaseEvidenceError("Kubernetes validation report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "Kubernetes statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "Kubernetes generated_at")
    maximum_age_hours = policy.categories["kubernetes"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("Kubernetes validation report is outside the allowed evidence window")
    cluster = report.get("cluster")
    server_version = report.get("kubernetes_server_version")
    node_image = report.get("kind_node_image")
    if (
        not isinstance(cluster, str)
        or re.fullmatch(r"[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?", cluster) is None
        or report.get("kind_version") != "0.31.0"
        or not isinstance(server_version, str)
        or re.fullmatch(r"v1\.35\.0(?:[-+][A-Za-z0-9._-]+)?", server_version) is None
        or not isinstance(node_image, str)
        or re.fullmatch(r"kindest/node:v1\.35\.0@sha256:[0-9a-f]{64}", node_image) is None
    ):
        raise ReleaseEvidenceError("Kubernetes validation target or pinned runtime is invalid")
    cluster_topology = report.get("cluster_topology")
    if (
        not isinstance(cluster_topology, dict)
        or set(cluster_topology) != KUBERNETES_CLUSTER_TOPOLOGY_FIELDS
        or cluster_topology.get("control_plane_nodes") != 1
        or cluster_topology.get("worker_nodes") != 2
        or cluster_topology.get("worker_zones") != 2
    ):
        raise ReleaseEvidenceError("Kubernetes validation cluster topology is incomplete")
    if (
        report.get("server_side_dry_run") != "passed"
        or report.get("production_crd_sets") != 3
        or report.get("cluster_cleanup") != "passed"
    ):
        raise ReleaseEvidenceError("Kubernetes API-server validation or cleanup is incomplete")
    clamav_ha = report.get("clamav_ha")
    if (
        not isinstance(clamav_ha, dict)
        or set(clamav_ha) != KUBERNETES_CLAMAV_HA_FIELDS
        or not isinstance(clamav_ha.get("image"), str)
        or re.fullmatch(r"clamav/clamav:1\.4@sha256:[0-9a-f]{64}", clamav_ha["image"]) is None
        or clamav_ha.get("live_image_reference") != "clamav/clamav:1.4"
        or clamav_ha.get("live_image_pull_policy") != "Never"
        or clamav_ha.get("source_image_digest_verified") is not True
        or clamav_ha.get("workload") != "StatefulSet"
        or clamav_ha.get("replicas_requested") != 2
        or clamav_ha.get("ready_replicas_before") != 2
        or clamav_ha.get("ready_replicas_after") != 2
        or clamav_ha.get("ready_endpoints_before") != 2
        or clamav_ha.get("ready_endpoints_after") != 2
        or not isinstance(clamav_ha.get("minimum_ready_endpoints_during_replacement"), int)
        or isinstance(clamav_ha.get("minimum_ready_endpoints_during_replacement"), bool)
        or not 1 <= clamav_ha["minimum_ready_endpoints_during_replacement"] <= 2
        or clamav_ha.get("distinct_nodes_before") != 2
        or clamav_ha.get("distinct_nodes_after") != 2
        or clamav_ha.get("distinct_zones_before") != 2
        or clamav_ha.get("distinct_zones_after") != 2
        or clamav_ha.get("placement_identity_preserved") is not True
        or clamav_ha.get("distinct_pvcs") != 2
        or clamav_ha.get("pvc_identity_preserved") is not True
        or clamav_ha.get("persistent_marker_preserved") is not True
        or clamav_ha.get("signature_freshness") != "passed"
        or clamav_ha.get("clean_scan") != "passed"
        or clamav_ha.get("eicar_blocked") is not True
        or clamav_ha.get("replacement_pod_uid_changed") is not True
    ):
        raise ReleaseEvidenceError("Kubernetes ClamAV high-availability evidence is incomplete")
    duration = report.get("duration_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 0 < duration <= 1800:
        raise ReleaseEvidenceError("Kubernetes validation duration is invalid")
    if report.get("download_transport") not in {
        "sha256-verified-content-cache",
        "sha256-verified-https+content-cache",
        "sha256-verified-https-mirror+content-cache",
    }:
        raise ReleaseEvidenceError("Kubernetes validation download transport is invalid")
    asset_cache = report.get("asset_cache")
    if (
        not isinstance(asset_cache, dict)
        or set(asset_cache) != {"content_addressed", "hits", "misses"}
        or asset_cache.get("content_addressed") is not True
        or not isinstance(asset_cache.get("hits"), int)
        or isinstance(asset_cache.get("hits"), bool)
        or asset_cache["hits"] < 0
        or not isinstance(asset_cache.get("misses"), int)
        or isinstance(asset_cache.get("misses"), bool)
        or asset_cache["misses"] < 0
        or asset_cache["hits"] + asset_cache["misses"] != 4
    ):
        raise ReleaseEvidenceError("Kubernetes validation content-addressed cache evidence is invalid")
    downloads = report.get("downloads")
    if not isinstance(downloads, dict) or set(downloads) != KUBERNETES_DOWNLOADS:
        raise ReleaseEvidenceError("Kubernetes validation dependency inventory is incomplete")
    for name, dependency in downloads.items():
        if (
            not isinstance(dependency, dict)
            or set(dependency) != KUBERNETES_DOWNLOAD_FIELDS
            or not isinstance(dependency.get("version"), str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", dependency["version"]) is None
            or not isinstance(dependency.get("sha256"), str)
            or SHA256_PATTERN.fullmatch(dependency["sha256"]) is None
        ):
            raise ReleaseEvidenceError(f"Kubernetes validation dependency metadata is invalid: {name}")


def _validate_entry_consistency_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("entry consistency attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == ENTRY_CONSISTENCY_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("entry consistency requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / ENTRY_CONSISTENCY_REPORT, "entry consistency report")
    if (
        set(report) != ENTRY_CONSISTENCY_FIELDS
        or report.get("schema") != ENTRY_CONSISTENCY_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl-controlled-fixture"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
    ):
        raise ReleaseEvidenceError("entry consistency report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "entry consistency statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "entry consistency generated_at")
    maximum_age_hours = policy.categories["entry_consistency"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("entry consistency report is outside the allowed evidence window")
    entity_id = report.get("entity_id")
    digest = report.get("canonical_entity_sha256")
    if (
        not isinstance(entity_id, str)
        or UUID_PATTERN.fullmatch(entity_id) is None
        or not isinstance(digest, str)
        or SHA256_PATTERN.fullmatch(digest) is None
    ):
        raise ReleaseEvidenceError("entry consistency fixture identity is invalid")
    if (
        report.get("fields_compared") != list(ENTRY_CONSISTENCY_ENTITY_FIELDS)
        or report.get("web_operations") != ["create_entity", "get_entity", "search_entities"]
        or report.get("mcp_tools") != ["get_entity", "search_entities"]
        or report.get("mcp_protocol_version") != "2025-11-25"
        or report.get("mcp_billed_calls") != 2
        or report.get("unique_settlements") != 2
        or report.get("same_tenant_fixture") is not True
        or report.get("same_filtered_facts") is not True
        or report.get("temporary_accounts_after") != 0
        or report.get("temporary_entities_after") != 0
    ):
        raise ReleaseEvidenceError("entry consistency Web, MCP, billing, or cleanup assertions are incomplete")


def _validate_mcp_interoperability_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("MCP interoperability attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == MCP_INTEROPERABILITY_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("MCP interoperability requires exactly one report.json attachment")
    report = _load_json_object(
        statement_path.parent / MCP_INTEROPERABILITY_REPORT,
        "MCP interoperability report",
    )
    if (
        set(report) != MCP_INTEROPERABILITY_FIELDS
        or report.get("schema") != MCP_INTEROPERABILITY_SCHEMA
        or report.get("schema_version") != 3
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl-controlled-fixture"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
        or report.get("client") != "MCP Inspector + Python MCP SDK"
        or report.get("client_count") != 2
    ):
        raise ReleaseEvidenceError("MCP interoperability report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "MCP interoperability statement generated_at")
    report_time = _parse_timestamp(report.get("created_at"), "MCP interoperability created_at")
    maximum_age_hours = policy.categories["mcp_protocol"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("MCP interoperability report is outside the allowed evidence window")
    query_digest = report.get("query_sha256")
    contract_digest = report.get("tool_contract_sha256")
    pagination_digest = report.get("pagination_entity_ids_sha256")
    target_id = report.get("target_id")
    if (
        not isinstance(query_digest, str)
        or SHA256_PATTERN.fullmatch(query_digest) is None
        or not isinstance(contract_digest, str)
        or SHA256_PATTERN.fullmatch(contract_digest) is None
        or not isinstance(pagination_digest, str)
        or SHA256_PATTERN.fullmatch(pagination_digest) is None
        or not isinstance(target_id, str)
        or UUID_PATTERN.fullmatch(target_id) is None
        or report.get("inspector_version") != "0.22.0"
        or report.get("python_sdk_version") != "1.28.1"
        or report.get("protocol_version") != "2025-11-25"
        or report.get("tools") != MCP_INTEROPERABILITY_TOOL_COUNT
        or report.get("pageable_cursor_tools") != 16
        or report.get("billed_calls") != 10
        or report.get("pagination_pages") != 2
        or report.get("pagination_unique_entities") != 2
        or report.get("invalid_cursor_rejected") is not True
        or report.get("recovered_after_error") is not True
        or not isinstance(report.get("competitive_program_items"), int)
        or isinstance(report.get("competitive_program_items"), bool)
        or report["competitive_program_items"] < 1
        or report.get("cross_domain_tool") != "get_competitive_pipeline"
        or report.get("workflow_assertions") != MCP_INTEROPERABILITY_WORKFLOW_ASSERTIONS
    ):
        raise ReleaseEvidenceError("MCP interoperability protocol or tool contract is invalid")
    clients = report.get("clients")
    if not isinstance(clients, list) or len(clients) != 2:
        raise ReleaseEvidenceError("MCP interoperability client inventory is incomplete")
    clients_by_name = {
        client.get("client"): client
        for client in clients
        if isinstance(client, dict) and isinstance(client.get("client"), str)
    }
    if set(clients_by_name) != {"MCP Inspector", "Python MCP SDK"}:
        raise ReleaseEvidenceError("MCP interoperability client inventory is incomplete")
    inspector = clients_by_name["MCP Inspector"]
    sdk = clients_by_name["Python MCP SDK"]
    if set(inspector) != {
        "billed_calls",
        "client",
        "pageable_cursor_tools",
        "query_sha256",
        "status",
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
    } or set(sdk) != {
        "billed_calls",
        "client",
        "client_version",
        "protocol_version",
        "query_sha256",
        "server_name",
        "server_version",
        "status",
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
    }:
        raise ReleaseEvidenceError("MCP interoperability client report fields are invalid")
    for client in (inspector, sdk):
        if (
            client.get("status") != "passed"
            or client.get("query_sha256") != query_digest
            or client.get("target_id") != target_id
            or client.get("tool_contract_sha256") != contract_digest
            or client.get("tools") != MCP_INTEROPERABILITY_TOOL_COUNT
            or client.get("billed_calls") != 5
            or client.get("pagination_pages") != 2
            or client.get("pagination_unique_entities") != 2
            or client.get("pagination_entity_ids_sha256") != pagination_digest
            or client.get("invalid_cursor_rejected") is not True
            or client.get("recovered_after_error") is not True
            or not isinstance(client.get("competitive_program_items"), int)
            or isinstance(client.get("competitive_program_items"), bool)
            or client["competitive_program_items"] < 1
            or client.get("cross_domain_tool") != "get_competitive_pipeline"
            or not isinstance(client.get("usage_settlements"), int)
            or isinstance(client.get("usage_settlements"), bool)
            or client["usage_settlements"] < 5
        ):
            raise ReleaseEvidenceError("MCP interoperability clients did not prove the same billed contract")
    if (
        inspector.get("pageable_cursor_tools") != 16
        or sdk.get("client_version") != "1.28.1"
        or sdk.get("server_name") != "Pharma Intelligence"
        or sdk.get("server_version") != "1.28.1"
        or sdk.get("protocol_version") != "2025-11-25"
        or report.get("usage_settlements") != max(inspector["usage_settlements"], sdk["usage_settlements"])
    ):
        raise ReleaseEvidenceError("MCP interoperability version or settlement evidence is inconsistent")


def _validate_mcp_commercial_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("MCP commercial attachments are invalid")
    reports = [item for item in raw_attachments if isinstance(item, dict) and item.get("path") == MCP_COMMERCIAL_REPORT]
    if len(reports) != 1:
        raise ReleaseEvidenceError("MCP commercial evidence requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / MCP_COMMERCIAL_REPORT, "MCP commercial report")
    if (
        set(report) != MCP_COMMERCIAL_FIELDS
        or report.get("schema") != MCP_COMMERCIAL_SCHEMA
        or report.get("schema_version") != "2.0"
        or report.get("status") != "passed"
        or report.get("environment") != "local-or-ci-controlled-baseline"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
        or report.get("protocol_version") != "2025-11-25"
    ):
        raise ReleaseEvidenceError("MCP commercial report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "MCP commercial statement generated_at")
    started_at = _parse_timestamp(report.get("started_at"), "MCP commercial started_at")
    finished_at = _parse_timestamp(report.get("finished_at"), "MCP commercial finished_at")
    maximum_age_hours = policy.categories["mcp_commercial"] if policy is not None else 168
    if (
        started_at > finished_at
        or finished_at > statement_time + timedelta(minutes=5)
        or statement_time - finished_at > timedelta(hours=maximum_age_hours)
    ):
        raise ReleaseEvidenceError("MCP commercial report is outside the allowed evidence window")
    assertions = report.get("assertions")
    if (
        not isinstance(assertions, dict)
        or set(assertions) != MCP_COMMERCIAL_ASSERTIONS
        or not all(value is True for value in assertions.values())
    ):
        raise ReleaseEvidenceError("MCP commercial baseline assertions are incomplete")
    requests = report.get("requests")
    if not isinstance(requests, dict) or set(requests) != {
        "requested",
        "completed",
        "failed",
        "concurrency",
        "duration_seconds",
        "throughput_rps",
    }:
        raise ReleaseEvidenceError("MCP commercial request inventory is invalid")
    requested = requests.get("requested")
    concurrency = requests.get("concurrency")
    duration = requests.get("duration_seconds")
    throughput = requests.get("throughput_rps")
    if (
        not isinstance(requested, int)
        or isinstance(requested, bool)
        or not 1 <= requested <= 1000
        or requests.get("completed") != requested
        or requests.get("failed") != 0
        or not isinstance(concurrency, int)
        or isinstance(concurrency, bool)
        or not 1 <= concurrency <= min(requested, 50)
        or not isinstance(duration, int | float)
        or isinstance(duration, bool)
        or not 0 < duration <= 600
        or not isinstance(throughput, int | float)
        or isinstance(throughput, bool)
        or throughput <= 0
    ):
        raise ReleaseEvidenceError("MCP commercial request results are incomplete")
    latency = report.get("latency_ms")
    if not isinstance(latency, dict) or set(latency) != {"minimum", "p50", "p95", "p99", "maximum"}:
        raise ReleaseEvidenceError("MCP commercial latency inventory is invalid")
    latency_names = ("minimum", "p50", "p95", "p99", "maximum")
    raw_latency_values = [latency.get(name) for name in latency_names]
    if any(not isinstance(value, int | float) or isinstance(value, bool) or value < 0 for value in raw_latency_values):
        raise ReleaseEvidenceError("MCP commercial latency contract failed")
    latency_values = [float(latency[name]) for name in latency_names]
    if latency_values != sorted(latency_values) or latency_values[2] > 2000:
        raise ReleaseEvidenceError("MCP commercial latency contract failed")
    billing = report.get("billing")
    if not isinstance(billing, dict) or set(billing) != {
        "settlements_before",
        "settlements_after",
        "settlement_delta",
        "unique_settlement_ids",
        "active_reservations_after",
    }:
        raise ReleaseEvidenceError("MCP commercial billing inventory is invalid")
    if (
        not isinstance(billing.get("settlements_before"), int)
        or isinstance(billing.get("settlements_before"), bool)
        or not isinstance(billing.get("settlements_after"), int)
        or isinstance(billing.get("settlements_after"), bool)
        or billing["settlements_after"] - billing["settlements_before"] != billing.get("settlement_delta")
        or not isinstance(billing.get("settlement_delta"), int)
        or isinstance(billing.get("settlement_delta"), bool)
        or billing["settlement_delta"] < requested
        or billing.get("unique_settlement_ids") != requested
        or billing.get("active_reservations_after") != 0
    ):
        raise ReleaseEvidenceError("MCP commercial settlement evidence is inconsistent")
    if report.get("errors") != []:
        raise ReleaseEvidenceError("MCP commercial report contains request failures")
    resilience = report.get("resilience")
    if not isinstance(resilience, dict) or set(resilience) != {
        "idempotency",
        "failure_release",
        "cancellation",
        "timeout",
        "reconciliation",
        "assertions",
    }:
        raise ReleaseEvidenceError("MCP commercial resilience inventory is invalid")
    resilience_assertions = resilience.get("assertions")
    if (
        not isinstance(resilience_assertions, dict)
        or set(resilience_assertions) != MCP_COMMERCIAL_RESILIENCE_ASSERTIONS
        or not all(value is True for value in resilience_assertions.values())
    ):
        raise ReleaseEvidenceError("MCP commercial resilience assertions are incomplete")
    idempotency = resilience.get("idempotency")
    failure_release = resilience.get("failure_release")
    reconciliation = resilience.get("reconciliation")
    if (
        idempotency != {"same_settlement": True, "replay_flag": True, "argument_conflict_rejected": True}
        or not isinstance(failure_release, dict)
        or failure_release
        != {
            "domain_failure_rejected": True,
            "budget_failure_rejected": True,
            "active_reservations_after": 0,
            "reserved_units_after": "0E-8",
        }
        or not isinstance(reconciliation, dict)
        or set(reconciliation)
        != {"settlement_delta", "charged_units_delta", "consumed_units_delta", "balance_identity_holds"}
        or reconciliation.get("balance_identity_holds") is not True
        or not isinstance(reconciliation.get("settlement_delta"), int)
        or isinstance(reconciliation.get("settlement_delta"), bool)
        or not 1 <= reconciliation["settlement_delta"] <= 3
        or not isinstance(reconciliation.get("charged_units_delta"), str)
        or UNITS_PATTERN.fullmatch(reconciliation["charged_units_delta"]) is None
        or reconciliation.get("consumed_units_delta") != reconciliation["charged_units_delta"]
    ):
        raise ReleaseEvidenceError("MCP commercial durable accounting evidence is inconsistent")
    cancellation = resilience.get("cancellation")
    timeout = resilience.get("timeout")
    if (
        not isinstance(cancellation, dict)
        or cancellation.get("cancellation_requested") is not True
        or cancellation.get("outcome") not in {"cancelled", "settled"}
        or not isinstance(timeout, dict)
        or timeout.get("timeout_observed") is not True
        or timeout.get("outcome") not in {"released", "replay_settled"}
        or not isinstance(timeout.get("reserved_retries"), int)
        or isinstance(timeout.get("reserved_retries"), bool)
        or timeout["reserved_retries"] < 0
        or not isinstance(timeout.get("recovery_seconds"), int | float)
        or isinstance(timeout.get("recovery_seconds"), bool)
        or not 0 < timeout["recovery_seconds"] <= 10
    ):
        raise ReleaseEvidenceError("MCP commercial cancellation or timeout evidence is incomplete")
    if cancellation["outcome"] == "cancelled":
        if set(cancellation) != {"cancellation_requested", "outcome"}:
            raise ReleaseEvidenceError("MCP commercial cancellation evidence has invalid fields")
    elif (
        set(cancellation) != {"cancellation_requested", "outcome", "settlement_id"}
        or not isinstance(cancellation.get("settlement_id"), str)
        or UUID_PATTERN.fullmatch(cancellation["settlement_id"]) is None
    ):
        raise ReleaseEvidenceError("MCP commercial settled cancellation evidence is invalid")
    if timeout["outcome"] == "released":
        if (
            set(timeout)
            != {"timeout_observed", "outcome", "replay_rejected_as_released", "reserved_retries", "recovery_seconds"}
            or timeout.get("replay_rejected_as_released") is not True
        ):
            raise ReleaseEvidenceError("MCP commercial released timeout evidence is invalid")
    elif (
        set(timeout)
        != {
            "timeout_observed",
            "outcome",
            "settlement_id",
            "same_settlement",
            "replay_flag",
            "reserved_retries",
            "recovery_seconds",
        }
        or not isinstance(timeout.get("settlement_id"), str)
        or UUID_PATTERN.fullmatch(timeout["settlement_id"]) is None
        or timeout.get("same_settlement") is not True
        or timeout.get("replay_flag") is not True
    ):
        raise ReleaseEvidenceError("MCP commercial settled timeout evidence is invalid")


def _validate_database_acceptance_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("database acceptance attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == DATABASE_ACCEPTANCE_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("database acceptance requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / DATABASE_ACCEPTANCE_REPORT, "database acceptance report")
    if (
        set(report) != DATABASE_ACCEPTANCE_FIELDS
        or report.get("schema") != DATABASE_ACCEPTANCE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
    ):
        raise ReleaseEvidenceError("database acceptance report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "database statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "database generated_at")
    maximum_age_hours = policy.categories["database"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("database acceptance report is outside the allowed evidence window")
    database = report.get("database")
    if (
        not isinstance(database, dict)
        or set(database) != {"postgresql_version", "rdkit_version", "alembic_head", "migration_drift"}
        or not isinstance(database.get("postgresql_version"), str)
        or not database["postgresql_version"].startswith("18.4 ")
        or database.get("rdkit_version") != "4.8.0"
        or database.get("alembic_head") != "5d7e1a3c9b24"
        or database.get("migration_drift") is not False
    ):
        raise ReleaseEvidenceError("database authority version or migration evidence is invalid")
    rls = report.get("rls")
    if (
        not isinstance(rls, dict)
        or set(rls)
        != {
            "bypass_rls",
            "forged_context_rows",
            "no_context_rows",
            "passed",
            "runtime_role",
            "signed_context_rows",
            "signed_context_valid",
            "superuser",
        }
        or rls.get("passed") is not True
        or rls.get("runtime_role") != "pharma_runtime"
        or rls.get("superuser") is not False
        or rls.get("bypass_rls") is not False
        or rls.get("no_context_rows") != 0
        or rls.get("forged_context_rows") != 0
        or isinstance(rls.get("signed_context_rows"), bool)
        or not isinstance(rls.get("signed_context_rows"), int)
        or rls["signed_context_rows"] < 0
        or rls.get("signed_context_valid") is not True
    ):
        raise ReleaseEvidenceError("database signed tenant RLS evidence is incomplete")
    hygiene = report.get("runtime_hygiene")
    if hygiene != {"schema_version": 1, "status": "passed", "finding_count": 0, "findings": []}:
        raise ReleaseEvidenceError("database persistent runtime hygiene evidence is incomplete")
    search = report.get("search")
    cluster = search.get("cluster") if isinstance(search, dict) else None
    deliveries = search.get("deliveries") if isinstance(search, dict) else None
    if not isinstance(search, dict) or set(search) != {"cluster", "deliveries"}:
        raise ReleaseEvidenceError("database OpenSearch evidence is invalid")
    if (
        not isinstance(cluster, dict)
        or set(cluster) != {"aliases", "available", "cluster_name", "cluster_status", "error", "version"}
        or cluster.get("available") is not True
        or cluster.get("cluster_name") != "pharma-search"
        or cluster.get("cluster_status") != "green"
        or cluster.get("error") is not None
        or cluster.get("version") != "3.7.0"
    ):
        raise ReleaseEvidenceError("database OpenSearch cluster evidence is invalid")
    aliases = cluster.get("aliases")
    if not isinstance(aliases, dict) or set(aliases) != {"entities", "evidence", "knowledge"}:
        raise ReleaseEvidenceError("database OpenSearch alias inventory is invalid")
    for name, values in aliases.items():
        if (
            not isinstance(values, list)
            or len(values) != 1
            or not isinstance(values[0], str)
            or not values[0].startswith(f"pharma-{name}-v2-")
        ):
            raise ReleaseEvidenceError(f"database OpenSearch alias is invalid: {name}")
    if (
        not isinstance(deliveries, dict)
        or set(deliveries) != {"dead", "processing", "retry", "succeeded"}
        or any(deliveries.get(name) != 0 for name in ("dead", "processing", "retry"))
        or not isinstance(deliveries.get("succeeded"), int)
        or isinstance(deliveries.get("succeeded"), bool)
        or deliveries["succeeded"] < 0
    ):
        raise ReleaseEvidenceError("database OpenSearch delivery queue evidence is invalid")
    if report.get("hybrid_search") != {
        "status": "passed",
        "protocol": "OpenSearch 3.x native hybrid query and normalization pipeline",
        "index_schema_version": 2,
        "embedding_fixture": "deterministic-controlled-test-vector",
        "production_embedding_model_verified": False,
    }:
        raise ReleaseEvidenceError("database local hybrid-search evidence is incomplete")
    duration = report.get("duration_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 0 < duration <= 120:
        raise ReleaseEvidenceError("database acceptance duration is invalid")


def _validate_observability_acceptance_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("observability acceptance attachments are invalid")
    reports = [
        item
        for item in raw_attachments
        if isinstance(item, dict) and item.get("path") == OBSERVABILITY_ACCEPTANCE_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("observability acceptance requires exactly one report.json attachment")
    report = _load_json_object(
        statement_path.parent / OBSERVABILITY_ACCEPTANCE_REPORT,
        "observability acceptance report",
    )
    if (
        set(report) != OBSERVABILITY_ACCEPTANCE_FIELDS
        or report.get("schema") != OBSERVABILITY_ACCEPTANCE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
        or report.get("collector_protocol") != "OTLP-gRPC"
    ):
        raise ReleaseEvidenceError("observability acceptance report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "observability statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "observability generated_at")
    maximum_age_hours = policy.categories["operations_contract"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("observability acceptance report is outside the allowed evidence window")
    if report.get("observed_metrics") != [
        "pharma.mcp.commercial.calls",
        "pharma.mcp.commercial.duration",
    ]:
        raise ReleaseEvidenceError("observability commercial metric inventory is incomplete")
    if report.get("contract") != {"services": 9, "objectives": 9, "alerts": 9}:
        raise ReleaseEvidenceError("observability operations contract inventory is incomplete")
    probe = report.get("commercial_probe")
    if (
        not isinstance(probe, dict)
        or set(probe) != {"requests", "unique_settlements", "active_reservations_after", "p95_ms"}
        or probe.get("requests") != 4
        or probe.get("unique_settlements") != 4
        or probe.get("active_reservations_after") != 0
        or not isinstance(probe.get("p95_ms"), int | float)
        or isinstance(probe.get("p95_ms"), bool)
        or not 0 <= probe["p95_ms"] <= 2000
    ):
        raise ReleaseEvidenceError("observability billed OTLP probe evidence is incomplete")


def _validate_parser_sandbox_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("parser sandbox attachments are invalid")
    reports = [item for item in raw_attachments if isinstance(item, dict) and item.get("path") == PARSER_SANDBOX_REPORT]
    if len(reports) != 1:
        raise ReleaseEvidenceError("parser sandbox requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / PARSER_SANDBOX_REPORT, "parser sandbox report")
    if (
        set(report) != PARSER_SANDBOX_FIELDS
        or report.get("schema") != PARSER_SANDBOX_SCHEMA
        or report.get("schema_version") != 3
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl-isolated-parser"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
        or report.get("parser_backend") != "service"
        or report.get("document_count") != 11
        or report.get("unauthorized_status") != 401
        or report.get("digest_mismatch_status") != 400
        or report.get("outbound_network_blocked") is not True
    ):
        raise ReleaseEvidenceError("parser sandbox report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "parser sandbox statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "parser sandbox generated_at")
    maximum_age_hours = policy.categories["parser_sandbox"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("parser sandbox report is outside the allowed evidence window")
    documents = report.get("documents")
    if not isinstance(documents, list) or len(documents) != len(PARSER_DOCUMENT_CONTRACTS):
        raise ReleaseEvidenceError("parser sandbox document inventory is incomplete")
    documents_by_suffix = {
        document.get("suffix"): document
        for document in documents
        if isinstance(document, dict) and isinstance(document.get("suffix"), str)
    }
    if set(documents_by_suffix) != set(PARSER_DOCUMENT_CONTRACTS):
        raise ReleaseEvidenceError("parser sandbox document inventory is incomplete")
    for suffix, (parser_name, parser_version) in PARSER_DOCUMENT_CONTRACTS.items():
        document = documents_by_suffix[suffix]
        metadata_keys = document.get("metadata_keys")
        digest = document.get("text_sha256")
        if (
            set(document) != {"suffix", "parser_name", "parser_version", "metadata_keys", "text_sha256"}
            or document.get("parser_name") != parser_name
            or document.get("parser_version") != parser_version
            or not isinstance(metadata_keys, list)
            or not metadata_keys
            or metadata_keys != sorted(set(metadata_keys))
            or any(not isinstance(name, str) or not name for name in metadata_keys)
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
        ):
            raise ReleaseEvidenceError(f"parser sandbox document contract is invalid: {suffix}")
    infrastructure = report.get("infrastructure")
    expected_secret_scope = [
        "PARSER_SERVICE_HOST",
        "PARSER_SERVICE_LIMIT_CONCURRENCY",
        "PARSER_SERVICE_MAX_CONCURRENT_PARSES",
        "PARSER_SERVICE_MAX_FILE_BYTES",
        "PARSER_SERVICE_MAX_TEXT_CHARS",
        "PARSER_SERVICE_PARSER_CPU_SECONDS",
        "PARSER_SERVICE_PARSER_MEMORY_BYTES",
        "PARSER_SERVICE_PARSER_TIMEOUT_SECONDS",
        "PARSER_SERVICE_PORT",
        "PARSER_SERVICE_TOKEN",
    ]
    if (
        not isinstance(infrastructure, dict)
        or set(infrastructure)
        != {
            "capabilities_dropped",
            "memory_limit_bytes",
            "nano_cpus",
            "network_internal",
            "network_member_roles",
            "parser_secret_scope",
            "pids_limit",
            "read_only_root_filesystem",
        }
        or infrastructure.get("capabilities_dropped") != ["ALL"]
        or infrastructure.get("memory_limit_bytes") != 3 * 1024**3
        or infrastructure.get("nano_cpus") != 2_000_000_000
        or infrastructure.get("network_internal") is not True
        or infrastructure.get("network_member_roles") != ["parser", "worker"]
        or infrastructure.get("parser_secret_scope") != expected_secret_scope
        or infrastructure.get("pids_limit") != 64
        or infrastructure.get("read_only_root_filesystem") is not True
    ):
        raise ReleaseEvidenceError("parser sandbox container isolation evidence is incomplete")
    capacity = report.get("capacity")
    if (
        not isinstance(capacity, dict)
        or set(capacity) != PARSER_CAPACITY_FIELDS
        or capacity.get("schema_version") != 1
        or capacity.get("status") != "passed"
        or capacity.get("production_claim") is not False
        or capacity.get("max_concurrent_parses") != 1
        or capacity.get("held_request_status") != 200
        or capacity.get("saturated_request_status") != 429
        or capacity.get("saturated_error_code") != "parser_capacity_exhausted"
        or capacity.get("retry_after_seconds") != "1"
        or capacity.get("recovery_request_status") != 200
        or capacity.get("ready_after_status") != 200
    ):
        raise ReleaseEvidenceError("parser sandbox capacity and recovery evidence is incomplete")
    capacity_time = _parse_timestamp(capacity.get("generated_at"), "parser sandbox capacity generated_at")
    if capacity_time > report_time + timedelta(minutes=5) or report_time - capacity_time > timedelta(hours=1):
        raise ReleaseEvidenceError("parser sandbox capacity evidence is outside the report window")
    timeout_recovery = report.get("timeout_recovery")
    if (
        not isinstance(timeout_recovery, dict)
        or set(timeout_recovery) != PARSER_TIMEOUT_RECOVERY_FIELDS
        or timeout_recovery.get("schema_version") != 1
        or timeout_recovery.get("status") != "passed"
        or timeout_recovery.get("production_claim") is not False
        or timeout_recovery.get("timeout_observed") is not True
        or timeout_recovery.get("child_processes_after_timeout") != 0
        or timeout_recovery.get("recovery_parser_name") != "text"
        or not isinstance(timeout_recovery.get("recovery_text_sha256"), str)
        or SHA256_PATTERN.fullmatch(timeout_recovery["recovery_text_sha256"]) is None
    ):
        raise ReleaseEvidenceError("parser sandbox timeout cleanup and recovery evidence is incomplete")
    timeout_time = _parse_timestamp(timeout_recovery.get("generated_at"), "parser sandbox timeout generated_at")
    timeout_duration = timeout_recovery.get("duration_seconds")
    if (
        timeout_time > report_time + timedelta(minutes=5)
        or report_time - timeout_time > timedelta(hours=1)
        or not isinstance(timeout_duration, int | float)
        or isinstance(timeout_duration, bool)
        or not 0 < timeout_duration <= 30
    ):
        raise ReleaseEvidenceError("parser sandbox timeout recovery timing is invalid")
    adversarial_corpus = report.get("adversarial_corpus")
    corpus_cases = adversarial_corpus.get("cases") if isinstance(adversarial_corpus, dict) else None
    if (
        not isinstance(adversarial_corpus, dict)
        or set(adversarial_corpus) != PARSER_ADVERSARIAL_CORPUS_FIELDS
        or adversarial_corpus.get("schema_version") != 1
        or adversarial_corpus.get("status") != "passed"
        or adversarial_corpus.get("production_claim") is not False
        or adversarial_corpus.get("case_count") != len(PARSER_ADVERSARIAL_CASE_CONTRACTS)
        or adversarial_corpus.get("recovery_status") != 200
        or adversarial_corpus.get("ready_after_status") != 200
        or not isinstance(corpus_cases, list)
        or len(corpus_cases) != len(PARSER_ADVERSARIAL_CASE_CONTRACTS)
        or [(case.get("name"), case.get("suffix")) for case in corpus_cases if isinstance(case, dict)]
        != list(PARSER_ADVERSARIAL_CASE_CONTRACTS)
        or any(
            not isinstance(case, dict)
            or set(case) != {"name", "suffix", "status", "error_code"}
            or case.get("status") != 422
            or case.get("error_code") != "document_parse_rejected"
            for case in corpus_cases
        )
    ):
        raise ReleaseEvidenceError("parser sandbox adversarial corpus evidence is incomplete")
    corpus_time = _parse_timestamp(
        adversarial_corpus.get("generated_at"),
        "parser sandbox adversarial corpus generated_at",
    )
    if corpus_time > report_time + timedelta(minutes=5) or report_time - corpus_time > timedelta(hours=1):
        raise ReleaseEvidenceError("parser sandbox adversarial corpus evidence is outside the report window")
    mtls = report.get("mtls")
    if (
        not isinstance(mtls, dict)
        or set(mtls)
        != {
            "schema_version",
            "status",
            "generated_at",
            "production_claim",
            "mutual_tls",
            "valid_client_parse",
            "no_client_certificate_rejected",
            "rogue_client_rejected",
            "untrusted_server_rejected",
            "client_certificate_sha256",
            "server_certificate_sha256",
            "duration_seconds",
        }
        or mtls.get("schema_version") != 1
        or mtls.get("status") != "passed"
        or mtls.get("production_claim") is not False
        or mtls.get("mutual_tls") is not True
        or mtls.get("valid_client_parse") is not True
        or mtls.get("no_client_certificate_rejected") is not True
        or mtls.get("rogue_client_rejected") is not True
        or mtls.get("untrusted_server_rejected") is not True
    ):
        raise ReleaseEvidenceError("parser sandbox mutual TLS evidence is incomplete")
    mtls_time = _parse_timestamp(mtls.get("generated_at"), "parser sandbox mTLS generated_at")
    if mtls_time > report_time + timedelta(minutes=5) or report_time - mtls_time > timedelta(hours=1):
        raise ReleaseEvidenceError("parser sandbox mutual TLS evidence is outside the report window")
    if any(
        not isinstance(mtls.get(field), str) or SHA256_PATTERN.fullmatch(mtls[field]) is None
        for field in ("client_certificate_sha256", "server_certificate_sha256")
    ):
        raise ReleaseEvidenceError("parser sandbox certificate digests are invalid")
    mtls_duration = mtls.get("duration_seconds")
    if not isinstance(mtls_duration, int | float) or isinstance(mtls_duration, bool) or not 0 < mtls_duration <= 60:
        raise ReleaseEvidenceError("parser sandbox mutual TLS duration is invalid")
    duration = report.get("duration_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 0 < duration <= 180:
        raise ReleaseEvidenceError("parser sandbox duration is invalid")


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


def _validate_runtime_acceptance_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("runtime acceptance attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == RUNTIME_ACCEPTANCE_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("runtime acceptance requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / RUNTIME_ACCEPTANCE_REPORT, "runtime acceptance report")
    schema = report.get("schema")
    schema_version = report.get("schema_version")
    if (
        set(report) != RUNTIME_ACCEPTANCE_FIELDS
        or not (
            (schema == RUNTIME_ACCEPTANCE_SCHEMA_V1 and schema_version == 1)
            or (schema == RUNTIME_ACCEPTANCE_SCHEMA_V2 and schema_version == 2)
            or (schema == RUNTIME_ACCEPTANCE_SCHEMA and schema_version == 3)
        )
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
        or report.get("compose_profile") != "compose+dev+telemetry"
        or report.get("main_runtime_modified") is not False
    ):
        raise ReleaseEvidenceError("runtime acceptance report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "runtime statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "runtime generated_at")
    maximum_age_hours = policy.categories["runtime"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("runtime acceptance report is outside the allowed evidence window")
    services = report.get("services")
    if not isinstance(services, list) or len(services) != len(RUNTIME_SERVICES):
        raise ReleaseEvidenceError("runtime service inventory is incomplete")
    services_by_name = {
        service.get("service"): service
        for service in services
        if isinstance(service, dict) and isinstance(service.get("service"), str)
    }
    if set(services_by_name) != set(RUNTIME_SERVICES):
        raise ReleaseEvidenceError("runtime service inventory is incomplete")
    for name, service in services_by_name.items():
        expected_health = {"healthy", "none"} if name == "otel-collector" else {"healthy"}
        if (
            set(service) != {"service", "state", "health", "image_id"}
            or service.get("state") != "running"
            or service.get("health") not in expected_health
            or not isinstance(service.get("image_id"), str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", service["image_id"]) is None
        ):
            raise ReleaseEvidenceError(f"runtime service is not healthy: {name}")
    subject = statement.get("subject")
    targets = subject.get("targets") if isinstance(subject, dict) else None
    api_target = targets.get("api") if isinstance(targets, dict) else None
    postgres_target = targets.get("postgres") if isinstance(targets, dict) else None
    if (
        not isinstance(api_target, str)
        or "@" not in api_target
        or not isinstance(postgres_target, str)
        or "@" not in postgres_target
    ):
        raise ReleaseEvidenceError("runtime statement image subjects are invalid")
    expected_api_image = api_target.rsplit("@", maxsplit=1)[1]
    expected_postgres_image = postgres_target.rsplit("@", maxsplit=1)[1]
    if (
        any(services_by_name[name].get("image_id") != expected_api_image for name in RUNTIME_APPLICATION_SERVICES)
        or services_by_name["postgres"].get("image_id") != expected_postgres_image
    ):
        raise ReleaseEvidenceError("runtime containers do not run the security-scanned release images")
    legacy_entrypoints: dict[str, Any] = {
        "web": {"url": "http://127.0.0.1:18380", "liveness": "passed", "readiness": "passed"},
        "mcp": {"url": "http://127.0.0.1:18390/mcp", "unauthenticated_status": 401},
        "parser": {"backend": "service", "readiness": "passed"},
    }
    workbench_result = {
        "get_status": 200,
        "head_status": 200,
        "content_type": "text/html",
        "security_headers": "passed",
        "spa_shell": "passed",
    }
    current_entrypoints: dict[str, Any] = {
        **legacy_entrypoints,
        "web": {
            **legacy_entrypoints["web"],
            "workbenches": {
                "research": {"path": "/workspace/research", **workbench_result},
                "internal": {"path": "/workspace/internal", **workbench_result},
            },
        },
    }
    entrypoints = report.get("entrypoints")
    if schema_version == 1:
        if entrypoints != legacy_entrypoints:
            raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
    elif schema_version == 2:
        if entrypoints != current_entrypoints:
            raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
    else:
        if not isinstance(entrypoints, dict) or set(entrypoints) != {"web", "mcp", "parser"}:
            raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
        web = entrypoints.get("web")
        if not isinstance(web, dict) or set(web) != {"url", "liveness", "readiness", "workbenches"}:
            raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
        workbenches = web.get("workbenches")
        if not isinstance(workbenches, dict) or set(workbenches) != {"research", "internal"}:
            raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
        document_hashes: set[str] = set()
        for workbench in ("research", "internal"):
            evidence = workbenches.get(workbench)
            expected = {
                "path": f"/workspace/{workbench}",
                **workbench_result,
                "entry_document": f"{workbench}.html",
                "workbench_marker": workbench,
            }
            if not isinstance(evidence, dict) or set(evidence) != {*expected, "document_sha256"}:
                raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
            if any(evidence.get(key) != value for key, value in expected.items()):
                raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
            document_hash = evidence.get("document_sha256")
            if not isinstance(document_hash, str) or re.fullmatch(r"[0-9a-f]{64}", document_hash) is None:
                raise ReleaseEvidenceError("runtime entrypoint document digest is invalid")
            document_hashes.add(document_hash)
        if len(document_hashes) != 2:
            raise ReleaseEvidenceError("runtime workbench documents are not distinct")
        if {key: value for key, value in entrypoints.items() if key != "web"} != {
            "mcp": legacy_entrypoints["mcp"],
            "parser": legacy_entrypoints["parser"],
        } or any(web.get(key) != legacy_entrypoints["web"][key] for key in ("url", "liveness", "readiness")):
            raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
    database = report.get("database")
    if (
        not isinstance(database, dict)
        or set(database) != {"alembic_head", "postgresql_version", "rdkit_version"}
        or database.get("alembic_head") != "5d7e1a3c9b24"
        or not isinstance(database.get("postgresql_version"), str)
        or not database["postgresql_version"].startswith("18.4 ")
        or database.get("rdkit_version") != "4.8.0"
    ):
        raise ReleaseEvidenceError("runtime database authority evidence is invalid")
    search = report.get("search")
    cluster = search.get("cluster") if isinstance(search, dict) else None
    deliveries = search.get("deliveries") if isinstance(search, dict) else None
    if (
        not isinstance(search, dict)
        or set(search) != {"cluster", "deliveries"}
        or not isinstance(cluster, dict)
        or cluster.get("available") is not True
        or cluster.get("cluster_name") != "pharma-search"
        or cluster.get("cluster_status") != "green"
        or cluster.get("error") is not None
        or cluster.get("version") != "3.7.0"
        or not isinstance(cluster.get("aliases"), dict)
        or set(cluster["aliases"]) != {"entities", "evidence", "knowledge"}
        or not isinstance(deliveries, dict)
        or set(deliveries) != {"dead", "processing", "retry", "succeeded"}
        or any(deliveries.get(name) != 0 for name in ("dead", "processing", "retry"))
        or not isinstance(deliveries.get("succeeded"), int)
        or isinstance(deliveries.get("succeeded"), bool)
        or deliveries["succeeded"] < 0
    ):
        raise ReleaseEvidenceError("runtime OpenSearch projection evidence is invalid")
    if report.get("runtime_hygiene") != {
        "schema_version": 1,
        "status": "passed",
        "finding_count": 0,
        "findings": [],
    }:
        raise ReleaseEvidenceError("runtime persistent data hygiene evidence is incomplete")
    duration = report.get("duration_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 0 < duration <= 180:
        raise ReleaseEvidenceError("runtime acceptance duration is invalid")


def _validate_production_topology_live_probe(
    *,
    statement_path: Path,
    statement: dict[str, Any],
    topology_report: dict[str, Any],
    topology_path: Path,
) -> None:
    raw_attachments = statement.get("attachments")
    probe_metadata = (
        [
            item
            for item in raw_attachments
            if isinstance(item, dict) and item.get("path") == PRODUCTION_TOPOLOGY_LIVE_REPORT
        ]
        if isinstance(raw_attachments, list)
        else []
    )
    if len(probe_metadata) != 1:
        raise ReleaseEvidenceError(
            f"production topology evidence requires exactly one {PRODUCTION_TOPOLOGY_LIVE_REPORT} attachment"
        )
    probe_path = statement_path.parent / PRODUCTION_TOPOLOGY_LIVE_REPORT
    probe = _load_json_object(probe_path, "production topology live probe")
    if (
        set(probe) != PRODUCTION_TOPOLOGY_LIVE_FIELDS
        or probe.get("schema") != PRODUCTION_TOPOLOGY_LIVE_SCHEMA
        or probe.get("schema_version") != 1
        or probe.get("status") != "passed"
        or probe.get("environment_kind") != topology_report.get("environment_kind")
        or probe.get("environment_id") != topology_report.get("environment_id")
        or probe.get("subject") != statement.get("subject")
        or probe.get("topology_report_sha256") != _sha256_file(topology_path)
        or not isinstance(probe.get("kube_context_sha256"), str)
        or SHA256_PATTERN.fullmatch(probe["kube_context_sha256"]) is None
        or not isinstance(probe.get("namespace"), str)
        or re.fullmatch(r"[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?", probe["namespace"]) is None
        or not isinstance(probe.get("namespace_uid"), str)
        or UUID_PATTERN.fullmatch(probe["namespace_uid"]) is None
        or probe.get("credentials_recorded") is not False
    ):
        raise ReleaseEvidenceError("production topology live probe is not bound to the approved deployment")
    topology_time = _parse_timestamp(topology_report.get("tested_at"), "production topology tested_at")
    probe_time = _parse_timestamp(probe.get("tested_at"), "production topology live probe tested_at")
    statement_time = _parse_timestamp(statement.get("generated_at"), "production topology statement generated_at")
    if (
        probe_time < topology_time - timedelta(minutes=5)
        or probe_time - topology_time > timedelta(hours=1)
        or probe_time > statement_time + timedelta(minutes=5)
    ):
        raise ReleaseEvidenceError("production topology live probe is outside the deployment observation window")

    kubernetes = probe.get("kubernetes")
    expected_kubernetes_fields = {
        "server_version",
        "ready_schedulable_nodes",
        "availability_zones",
        "node_architectures",
    }
    expected_kubernetes_version = topology_report.get("components", {}).get("kubernetes", {}).get("version")
    if (
        not isinstance(kubernetes, dict)
        or set(kubernetes) != expected_kubernetes_fields
        or kubernetes.get("server_version") != expected_kubernetes_version
        or not isinstance(kubernetes.get("ready_schedulable_nodes"), int)
        or isinstance(kubernetes.get("ready_schedulable_nodes"), bool)
        or kubernetes["ready_schedulable_nodes"] < 3
        or not isinstance(kubernetes.get("availability_zones"), list)
        or len(kubernetes["availability_zones"]) < 2
        or len(kubernetes["availability_zones"]) != len(set(kubernetes["availability_zones"]))
        or any(not isinstance(item, str) or not item for item in kubernetes["availability_zones"])
        or not isinstance(kubernetes.get("node_architectures"), list)
        or not kubernetes["node_architectures"]
        or not set(kubernetes["node_architectures"]) <= {"amd64", "arm64"}
    ):
        raise ReleaseEvidenceError("production topology live Kubernetes observation is incomplete")

    workloads = probe.get("workloads")
    workload_fields = {
        "name",
        "kind",
        "desired_replicas",
        "ready_replicas",
        "available_replicas",
        "generation",
        "observed_generation",
        "image_digests",
        "pdb_present",
        "hpa_present",
    }
    if not isinstance(workloads, list) or len(workloads) != len(PRODUCTION_TOPOLOGY_REQUIRED_WORKLOADS):
        raise ReleaseEvidenceError("production topology live workload inventory is incomplete")
    observed_workloads: set[str] = set()
    application_target = statement.get("subject", {}).get("targets", {}).get("api")
    application_digest = (
        application_target.rsplit("@sha256:", maxsplit=1)[1]
        if isinstance(application_target, str) and "@sha256:" in application_target
        else ""
    )
    ocr_target = statement.get("subject", {}).get("targets", {}).get("ocr")
    ocr_digest = (
        ocr_target.rsplit("@sha256:", maxsplit=1)[1] if isinstance(ocr_target, str) and "@sha256:" in ocr_target else ""
    )
    for workload in workloads:
        name = workload.get("name") if isinstance(workload, dict) else None
        expected_digest = ocr_digest if name == "pharma-ocr" else application_digest
        images = workload.get("image_digests") if isinstance(workload, dict) else None
        desired = workload.get("desired_replicas") if isinstance(workload, dict) else None
        if (
            not isinstance(workload, dict)
            or set(workload) != workload_fields
            or not isinstance(name, str)
            or name in observed_workloads
            or name not in PRODUCTION_TOPOLOGY_REQUIRED_WORKLOADS
            or workload.get("kind") != "Deployment"
            or not isinstance(desired, int)
            or isinstance(desired, bool)
            or desired < 2
            or workload.get("ready_replicas") != desired
            or workload.get("available_replicas") != desired
            or not isinstance(workload.get("generation"), int)
            or isinstance(workload.get("generation"), bool)
            or workload["generation"] < 1
            or workload.get("observed_generation") != workload["generation"]
            or not isinstance(images, list)
            or not images
            or len(images) != len(set(images))
            or any(
                not isinstance(image, str) or re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", image) is None
                for image in images
            )
            or not any(image.endswith(f"@sha256:{expected_digest}") for image in images)
            or workload.get("pdb_present") is not True
            or (name in PRODUCTION_TOPOLOGY_HPA_WORKLOADS and workload.get("hpa_present") is not True)
            or not isinstance(workload.get("hpa_present"), bool)
        ):
            raise ReleaseEvidenceError(f"production topology live workload is not ready and governed: {name}")
        observed_workloads.add(name)
    if observed_workloads != PRODUCTION_TOPOLOGY_REQUIRED_WORKLOADS:
        raise ReleaseEvidenceError("production topology live workload inventory is incomplete")

    entrypoints = topology_report.get("entrypoints")
    web_url = entrypoints.get("web_url") if isinstance(entrypoints, dict) else None
    mcp_url = entrypoints.get("mcp_url") if isinstance(entrypoints, dict) else None
    expected_hosts = {
        urlsplit(value).hostname
        for value in (web_url, mcp_url)
        if isinstance(value, str) and urlsplit(value).hostname is not None
    }
    gateway = probe.get("gateway")
    if (
        not isinstance(gateway, dict)
        or set(gateway) != {"name", "programmed", "listener_hosts", "route_hosts"}
        or gateway.get("name") != "pharma-public"
        or gateway.get("programmed") is not True
        or set(gateway.get("listener_hosts", [])) != expected_hosts
        or set(gateway.get("route_hosts", [])) != expected_hosts
        or len(gateway.get("listener_hosts", [])) != 2
        or len(gateway.get("route_hosts", [])) != 2
    ):
        raise ReleaseEvidenceError("production topology live Gateway observation is invalid")
    network_policy = probe.get("network_policy")
    if (
        not isinstance(network_policy, dict)
        or set(network_policy) != {"count", "default_deny_ingress", "default_deny_egress"}
        or not isinstance(network_policy.get("count"), int)
        or isinstance(network_policy.get("count"), bool)
        or network_policy["count"] < 8
        or network_policy.get("default_deny_ingress") is not True
        or network_policy.get("default_deny_egress") is not True
    ):
        raise ReleaseEvidenceError("production topology live network-policy posture is invalid")

    endpoints = probe.get("endpoints")
    if not isinstance(endpoints, dict) or set(endpoints) != {"web", "mcp"}:
        raise ReleaseEvidenceError("production topology live endpoint observations are invalid")
    endpoint_fields = {
        "url",
        "status_code",
        "tls_version",
        "certificate_sha256",
        "hsts",
        "unauthenticated_rejected",
    }
    for name, expected_url in (("web", web_url), ("mcp", mcp_url)):
        endpoint = endpoints.get(name)
        if (
            not isinstance(endpoint, dict)
            or set(endpoint) != endpoint_fields
            or endpoint.get("url") != expected_url
            or endpoint.get("tls_version") not in {"TLSv1.2", "TLSv1.3"}
            or not isinstance(endpoint.get("certificate_sha256"), str)
            or SHA256_PATTERN.fullmatch(endpoint["certificate_sha256"]) is None
            or endpoint.get("hsts") is not True
            or (name == "web" and endpoint.get("status_code") != 200)
            or (name == "web" and endpoint.get("unauthenticated_rejected") is not None)
            or (name == "mcp" and endpoint.get("status_code") not in {401, 403})
            or (name == "mcp" and endpoint.get("unauthenticated_rejected") is not True)
        ):
            raise ReleaseEvidenceError(f"production topology live {name} endpoint observation is invalid")


def _validate_production_topology_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("production topology evidence attachments are invalid")
    report_metadata = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == PRODUCTION_TOPOLOGY_REPORT
    ]
    if len(report_metadata) != 1:
        raise ReleaseEvidenceError(
            f"production topology evidence requires exactly one {PRODUCTION_TOPOLOGY_REPORT} attachment"
        )
    report_path = statement_path.parent / PRODUCTION_TOPOLOGY_REPORT
    report = _load_json_object(report_path, "production topology report")
    environment_id = report.get("environment_id")
    if (
        set(report) != PRODUCTION_TOPOLOGY_FIELDS
        or report.get("schema") != PRODUCTION_TOPOLOGY_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment_kind") not in {"preproduction", "production"}
        or not isinstance(environment_id, str)
        or ENVIRONMENT_ID_PATTERN.fullmatch(environment_id) is None
        or report.get("profile") not in {"core_commercial", "scale_production"}
    ):
        raise ReleaseEvidenceError("production topology report is not approved environment evidence")
    environment_tokens = set(re.split(r"[^a-z0-9]+", environment_id.casefold()))
    if environment_tokens.intersection({"dev", "development", "local", "test", "testing"}):
        raise ReleaseEvidenceError("production topology report identifies a local or development environment")
    if report.get("subject") != statement.get("subject"):
        raise ReleaseEvidenceError("production topology report is not bound to the release subject")
    statement_time = _parse_timestamp(statement.get("generated_at"), "production topology statement generated_at")
    tested_at = _parse_timestamp(report.get("tested_at"), "production topology tested_at")
    if tested_at > statement_time + timedelta(minutes=5) or statement_time - tested_at > timedelta(hours=24):
        raise ReleaseEvidenceError("production topology report is outside the allowed execution window")

    entrypoints = report.get("entrypoints")
    if not isinstance(entrypoints, dict) or set(entrypoints) != {"public_entry_count", "web_url", "mcp_url"}:
        raise ReleaseEvidenceError("production topology entrypoint contract is invalid")
    endpoint_hosts: set[str] = set()
    for field in ("web_url", "mcp_url"):
        value = entrypoints.get(field)
        parsed = urlsplit(value) if isinstance(value, str) else urlsplit("")
        hostname = parsed.hostname.casefold() if parsed.hostname else ""
        if (
            parsed.scheme != "https"
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or hostname == "localhost"
            or hostname.endswith((".localhost", ".test", ".invalid", ".example"))
        ):
            raise ReleaseEvidenceError(f"production topology has an invalid {field}")
        endpoint_hosts.add(hostname)
    if entrypoints.get("public_entry_count") != 2 or len(endpoint_hosts) != 2:
        raise ReleaseEvidenceError("production topology must expose exactly two distinct public entrypoints")

    components = report.get("components")
    if not isinstance(components, dict) or set(components) != PRODUCTION_TOPOLOGY_COMPONENTS:
        raise ReleaseEvidenceError("production topology component inventory is incomplete")
    version_patterns = {
        "python": r"3\.13\.\d+",
        "postgresql": r"(?:17|18)\.\d+(?:\.\d+)?",
        "rdkit": r"2026\.03(?:\.\d+)?",
        "opensearch": r"3\.7(?:\.\d+)?",
        "temporal": r"1\.\d+(?:\.\d+)?",
        "valkey": r"9\.\d+(?:\.\d+)?",
        "kubernetes": r"1\.\d+\.\d+",
    }
    minimum_replicas = {
        "python": 2,
        "postgresql": 2,
        "rdkit": 2,
        "opensearch": 3,
        "object_storage": 2,
        "temporal": 3,
        "valkey": 3,
        "identity": 2,
        "secrets": 3,
        "gateway": 2,
        "kubernetes": 3,
        "observability": 2,
    }
    for name, raw_component in components.items():
        if not isinstance(raw_component, dict) or set(raw_component) != PRODUCTION_TOPOLOGY_COMPONENT_FIELDS:
            raise ReleaseEvidenceError(f"production topology component is invalid: {name}")
        version = raw_component.get("version")
        deployment_reference = raw_component.get("deployment_reference")
        replicas = raw_component.get("replicas")
        if (
            not isinstance(version, str)
            or not 1 <= len(version) <= 80
            or (name in version_patterns and re.fullmatch(version_patterns[name], version) is None)
            or not isinstance(deployment_reference, str)
            or not 3 <= len(deployment_reference) <= 300
            or not isinstance(replicas, int)
            or isinstance(replicas, bool)
            or replicas < minimum_replicas[name]
            or raw_component.get("managed_or_ha") is not True
        ):
            raise ReleaseEvidenceError(f"production topology component does not meet the baseline: {name}")

    event_projection = report.get("event_projection")
    expected_event_fields = {
        "mode",
        "kafka_version",
        "debezium_version",
        "clickhouse_enabled",
        "iceberg_enabled",
    }
    if not isinstance(event_projection, dict) or set(event_projection) != expected_event_fields:
        raise ReleaseEvidenceError("production topology event projection profile is invalid")
    if report["profile"] == "core_commercial":
        if event_projection != {
            "mode": "transactional_outbox",
            "kafka_version": None,
            "debezium_version": None,
            "clickhouse_enabled": False,
            "iceberg_enabled": False,
        }:
            raise ReleaseEvidenceError("core commercial topology must use the bounded transactional outbox profile")
    elif (
        event_projection.get("mode") != "kafka_cdc"
        or not isinstance(event_projection.get("kafka_version"), str)
        or re.fullmatch(r"4\.\d+(?:\.\d+)?", event_projection["kafka_version"]) is None
        or not isinstance(event_projection.get("debezium_version"), str)
        or re.fullmatch(r"3\.\d+(?:\.\d+)?", event_projection["debezium_version"]) is None
        or event_projection.get("clickhouse_enabled") is not True
        or event_projection.get("iceberg_enabled") is not True
    ):
        raise ReleaseEvidenceError("scale production topology does not meet the event data baseline")

    if report.get("authority") != {
        "canonical_store": "postgresql",
        "chemical_authority": "postgresql_rdkit",
        "search_role": "derived_projection",
        "object_role": "immutable_evidence",
        "metering_authority": "postgresql_append_only_ledger",
        "web_direct_database_access": False,
        "mcp_direct_database_access": False,
    }:
        raise ReleaseEvidenceError("production topology authority boundaries are invalid")
    resilience = report.get("resilience")
    expected_resilience = {
        "multi_az",
        "postgres_pitr",
        "object_versioning",
        "object_lock",
        "opensearch_replicas",
        "temporal_ha",
        "valkey_ha",
        "kubernetes_pdb_hpa",
        "gitops_rollback",
        "central_observability",
    }
    if (
        not isinstance(resilience, dict)
        or set(resilience) != expected_resilience
        or any(value is not True for value in resilience.values())
    ):
        raise ReleaseEvidenceError("production topology resilience controls are incomplete")

    migration = report.get("migration")
    expected_migration_fields = {
        "postgresql16_critical_path",
        "postgresql17_adr_reference",
        "ragflow_critical_path",
        "ragflow_exit_plan_reference",
        "ragflow_adapter_removal_criteria",
        "legacy_profile_isolated",
    }
    if not isinstance(migration, dict) or set(migration) != expected_migration_fields:
        raise ReleaseEvidenceError("production topology migration boundary is invalid")
    postgres_version = components["postgresql"]["version"]
    postgres17_adr = migration.get("postgresql17_adr_reference")
    if (
        migration.get("postgresql16_critical_path") is not False
        or migration.get("ragflow_critical_path") is not False
        or migration.get("legacy_profile_isolated") is not True
        or not isinstance(migration.get("ragflow_exit_plan_reference"), str)
        or not 3 <= len(migration["ragflow_exit_plan_reference"]) <= 200
        or not isinstance(migration.get("ragflow_adapter_removal_criteria"), str)
        or not 3 <= len(migration["ragflow_adapter_removal_criteria"]) <= 500
        or (postgres_version.startswith("17.") and (not isinstance(postgres17_adr, str) or len(postgres17_adr) < 3))
        or (postgres_version.startswith("18.") and postgres17_adr is not None)
    ):
        raise ReleaseEvidenceError("production topology contains an unapproved legacy critical path")
    references = report.get("references")
    expected_references = {"architecture_approval", "deployment_inventory", "version_matrix", "ragflow_exit_plan"}
    if (
        not isinstance(references, dict)
        or set(references) != expected_references
        or any(not isinstance(value, str) or not 3 <= len(value) <= 200 for value in references.values())
        or references.get("ragflow_exit_plan") != migration.get("ragflow_exit_plan_reference")
    ):
        raise ReleaseEvidenceError("production topology references are incomplete or inconsistent")

    _validate_production_topology_live_probe(
        statement_path=statement_path,
        statement=statement,
        topology_report=report,
        topology_path=report_path,
    )

    if policy is None:
        raise ReleaseEvidenceError("production topology policy contract is missing")
    contract = policy.production_contracts.get("production_topology")
    if contract is None:
        raise ReleaseEvidenceError("production topology production contract is missing")
    production_report = _load_json_object(
        statement_path.parent / contract.report_name, "production topology gate report"
    )
    artifacts = production_report.get("artifacts")
    if (
        production_report.get("environment_kind") != report.get("environment_kind")
        or production_report.get("environment_id") != report.get("environment_id")
        or production_report.get("tested_at") != report.get("tested_at")
        or not isinstance(artifacts, list)
        or {
            artifact.get("path")
            for artifact in artifacts
            if isinstance(artifact, dict)
            and artifact.get("path") in {PRODUCTION_TOPOLOGY_REPORT, PRODUCTION_TOPOLOGY_LIVE_REPORT}
        }
        != {PRODUCTION_TOPOLOGY_REPORT, PRODUCTION_TOPOLOGY_LIVE_REPORT}
    ):
        raise ReleaseEvidenceError("production topology report is not bound as a production artifact")


def _validate_specialized_evidence(
    statement_path: Path,
    category: str,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None = None,
) -> None:
    if category == "source_reproducibility":
        _validate_clean_source_evidence(statement_path, statement, policy=policy)
        return
    if category == "browser":
        _validate_browser_acceptance_evidence(statement_path, statement, policy=policy)
        return
    if category == "performance_baseline":
        _validate_performance_baseline_evidence(statement_path, statement, policy=policy)
        return
    if category == "ingestion_readiness":
        _validate_ingestion_readiness_evidence(statement_path, statement, policy=policy)
        return
    if category == "ingestion_pilot":
        _validate_ingestion_pilot_evidence(statement_path, statement, policy=policy)
        return
    if category == "record_consistency":
        _validate_record_consistency_evidence(statement_path, statement, policy=policy)
        return
    if category == "anti_extraction_baseline":
        _validate_anti_extraction_baseline_evidence(statement_path, statement, policy=policy)
        return
    if category == "backup_restore":
        _validate_backup_restore_evidence(statement_path, statement, policy=policy)
        return
    if category == "kubernetes":
        _validate_kubernetes_evidence(statement_path, statement, policy=policy)
        return
    if category == "entry_consistency":
        _validate_entry_consistency_evidence(statement_path, statement, policy=policy)
        return
    if category == "mcp_protocol":
        _validate_mcp_interoperability_evidence(statement_path, statement, policy=policy)
        return
    if category == "mcp_async_tasks":
        _validate_mcp_async_task_evidence(statement_path, statement, policy=policy)
        return
    if category == "mcp_commercial":
        _validate_mcp_commercial_evidence(statement_path, statement, policy=policy)
        return
    if category == "database":
        _validate_database_acceptance_evidence(statement_path, statement, policy=policy)
        return
    if category == "operations_contract":
        _validate_observability_acceptance_evidence(statement_path, statement, policy=policy)
        return
    if category == "parser_sandbox":
        _validate_parser_sandbox_evidence(statement_path, statement, policy=policy)
        return
    if category == "ocr":
        _validate_ocr_acceptance_evidence(statement_path, statement, policy=policy)
        return
    if category == "runtime":
        _validate_runtime_acceptance_evidence(statement_path, statement, policy=policy)
        return
    if policy is not None and (contract := policy.production_contracts.get(category)) is not None:
        _validate_production_gate_evidence(
            statement_path,
            category,
            statement,
            contract=contract,
            maximum_age_hours=policy.categories[category],
        )
    if category == "production_topology":
        _validate_production_topology_evidence(statement_path, statement, policy=policy)
        return
    if category != "mcp_sender_constraint":
        return
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("MCP sender-constraint evidence attachments are invalid")
    report_metadata = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == MCP_SENDER_CONSTRAINT_REPORT
    ]
    if len(report_metadata) != 1:
        raise ReleaseEvidenceError(
            f"MCP sender-constraint evidence requires exactly one {MCP_SENDER_CONSTRAINT_REPORT} attachment"
        )
    report_path = statement_path.parent / MCP_SENDER_CONSTRAINT_REPORT
    report = _load_json_object(report_path, "MCP sender-constraint report")
    environment_id = report.get("environment_id")
    if (
        set(report) != MCP_SENDER_CONSTRAINT_FIELDS
        or report.get("schema") != MCP_SENDER_CONSTRAINT_SCHEMA
        or report.get("schema_version") != 2
        or report.get("status") != "passed"
        or report.get("environment_kind") not in {"preproduction", "production"}
        or not isinstance(environment_id, str)
        or ENVIRONMENT_ID_PATTERN.fullmatch(environment_id) is None
    ):
        raise ReleaseEvidenceError("MCP sender-constraint report is not approved environment evidence")
    environment_tokens = set(re.split(r"[^a-z0-9]+", environment_id.casefold()))
    if environment_tokens.intersection({"dev", "development", "local", "test", "testing"}):
        raise ReleaseEvidenceError("MCP sender-constraint report identifies a local or development environment")
    if report.get("subject") != statement.get("subject"):
        raise ReleaseEvidenceError("MCP sender-constraint report is not bound to the release subject")
    if policy is not None:
        contract = policy.production_contracts.get(category)
        if contract is None:
            raise ReleaseEvidenceError("MCP sender-constraint production contract is missing")
        production_report = _load_json_object(
            statement_path.parent / contract.report_name,
            "MCP sender-constraint production report",
        )
        artifacts = production_report.get("artifacts")
        if (
            not isinstance(artifacts, list)
            or sum(
                1
                for artifact in artifacts
                if isinstance(artifact, dict) and artifact.get("path") == MCP_SENDER_CONSTRAINT_REPORT
            )
            != 1
        ):
            raise ReleaseEvidenceError("MCP sender-constraint report is not bound as a production artifact")
    statement_time = _parse_timestamp(statement.get("generated_at"), "MCP sender-constraint statement generated_at")
    tested_at = _parse_timestamp(report.get("tested_at"), "MCP sender-constraint tested_at")
    if tested_at > statement_time + timedelta(minutes=5) or statement_time - tested_at > timedelta(hours=24):
        raise ReleaseEvidenceError("MCP sender-constraint report is outside the allowed execution window")
    for field in ("idp_issuer_url", "resource_server_url"):
        value = report.get(field)
        parsed = urlsplit(value) if isinstance(value, str) else urlsplit("")
        hostname = parsed.hostname.casefold() if parsed.hostname else ""
        if (
            parsed.scheme != "https"
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or hostname == "localhost"
            or hostname.endswith((".localhost", ".test", ".invalid", ".example"))
        ):
            raise ReleaseEvidenceError(f"MCP sender-constraint report has an invalid {field}")
    clients = report.get("clients")
    if not isinstance(clients, list) or len(clients) < 2:
        raise ReleaseEvidenceError("MCP sender-constraint report requires at least two clients")
    client_identities: set[tuple[str, str]] = set()
    for client in clients:
        if not isinstance(client, dict) or set(client) != {"name", "version", "dpop_supported"}:
            raise ReleaseEvidenceError("MCP sender-constraint report has an invalid client")
        name = client.get("name")
        version = client.get("version")
        if (
            not isinstance(name, str)
            or not 1 <= len(name) <= 120
            or not isinstance(version, str)
            or not 1 <= len(version) <= 80
            or client.get("dpop_supported") is not True
        ):
            raise ReleaseEvidenceError("MCP sender-constraint report has an invalid client")
        client_identities.add((name, version))
    if len(client_identities) < 2:
        raise ReleaseEvidenceError("MCP sender-constraint report clients are not independent")
    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or set(checks) != MCP_SENDER_CONSTRAINT_CHECKS
        or not all(value is True for value in checks.values())
    ):
        raise ReleaseEvidenceError("MCP sender-constraint report did not pass every required check")
    replay_store = report.get("replay_store")
    if not isinstance(replay_store, dict) or replay_store != {
        "failure_mode": "fail_closed",
        "shared": True,
        "tls": True,
    }:
        raise ReleaseEvidenceError("MCP sender-constraint replay-store evidence is incomplete")
    references = report.get("references")
    expected_references = {"gateway_change", "idp_change", "security_approval"}
    if (
        not isinstance(references, dict)
        or set(references) != expected_references
        or any(not isinstance(value, str) or not 3 <= len(value) <= 200 for value in references.values())
    ):
        raise ReleaseEvidenceError("MCP sender-constraint approval references are incomplete")


def _check_release_tag(repo: Path, subject: RepositorySubject, release_tag: str | None, required: bool) -> str | None:
    if release_tag is not None:
        valid_reference = _git(repo, "check-ref-format", f"refs/tags/{release_tag}", check=False)
        if valid_reference.returncode != 0:
            raise ReleaseEvidenceError("release tag is not a valid Git reference")
    if not required:
        if release_tag is not None and release_tag not in subject.tags:
            raise ReleaseEvidenceError("release tag does not point at the current commit")
        return release_tag
    if not release_tag or release_tag not in subject.tags:
        raise ReleaseEvidenceError("production evidence requires a release tag at the current commit")
    tag_type = _git(repo, "cat-file", "-t", f"refs/tags/{release_tag}").stdout.decode().strip()
    if tag_type != "tag":
        raise ReleaseEvidenceError("production evidence requires an annotated signed Git tag")
    verification = _git(repo, "verify-tag", "--", release_tag, check=False)
    if verification.returncode != 0:
        raise ReleaseEvidenceError("production evidence requires a cryptographically verified Git tag")
    return release_tag


def _load_signing_key(path: Path) -> Ed25519PrivateKey:
    if path.is_symlink() or not path.is_file():
        raise ReleaseEvidenceError("release signing key must be a regular PEM file")
    if path.stat().st_mode & 0o077:
        raise ReleaseEvidenceError("release signing key permissions must not allow group or other access")
    password_text = os.environ.get("RELEASE_SIGNING_KEY_PASSWORD")
    password = password_text.encode() if password_text else None
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=password)
    except (OSError, ValueError, TypeError) as exc:
        raise ReleaseEvidenceError("cannot load release signing key") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ReleaseEvidenceError("release signing key must use Ed25519")
    return key


def _load_public_key(path: Path) -> Ed25519PublicKey:
    if path.is_symlink() or not path.is_file():
        raise ReleaseEvidenceError("trusted release public key must be a regular PEM file")
    try:
        key = serialization.load_pem_public_key(path.read_bytes())
    except (OSError, ValueError, TypeError) as exc:
        raise ReleaseEvidenceError("cannot load trusted release public key") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise ReleaseEvidenceError("trusted release public key must use Ed25519")
    return key


def _public_key_fingerprint(key: Ed25519PublicKey) -> str:
    encoded = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return _sha256_bytes(encoded)


def _copy_regular_tree(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_symlink():
            raise ReleaseEvidenceError(f"evidence tree contains a symbolic link: {relative}")
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        else:
            raise ReleaseEvidenceError(f"evidence tree contains a non-regular entry: {relative}")


def _payload_inventory(root: Path) -> list[dict[str, object]]:
    inventory: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ReleaseEvidenceError(f"release bundle contains a symbolic link: {path.relative_to(root)}")
        if path.is_file():
            inventory.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )
    return inventory


def assemble_bundle(
    *,
    repo: Path,
    policy_path: Path,
    level_name: str,
    security_directory: Path,
    statements: list[Path],
    output: Path,
    release_tag: str | None = None,
    signing_key_path: Path | None = None,
    signing_key_id: str | None = None,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    if level_name not in policy.levels:
        raise ReleaseEvidenceError(f"unknown release evidence level: {level_name}")
    _require_authoritative_production_policy(repo, policy, level_name)
    level = policy.levels[level_name]
    if output.exists() or output.is_symlink():
        raise ReleaseEvidenceError(f"refusing to overwrite release bundle: {output}")
    subject = repository_subject(repo)
    matrix, matrix_schema_path = _repository_goal_matrix_contract(repo, policy, level_name)
    security = validate_security_evidence(
        security_directory,
        subject,
        maximum_age_hours=level.security_max_age_hours,
    )
    if level.require_release_security and not security.release_mode:
        raise ReleaseEvidenceError("production evidence requires a security gate run in release mode")
    release_tag = _check_release_tag(repo, subject, release_tag, level.require_signed_git_tag)
    if level.require_bundle_signature and signing_key_path is None:
        raise ReleaseEvidenceError("production evidence requires an Ed25519 bundle signature")
    if signing_key_path is not None and not signing_key_id:
        raise ReleaseEvidenceError("a stable signing key ID is required with --signing-key")
    if signing_key_id is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}", signing_key_id):
        raise ReleaseEvidenceError("release signing key ID is invalid")

    validated: dict[str, tuple[Path, dict[str, Any]]] = {}
    for statement_path in statements:
        category, statement = _statement_category(
            statement_path.resolve(), policy=policy, subject=subject, security=security
        )
        if category in validated:
            raise ReleaseEvidenceError(f"duplicate release gate category: {category}")
        validated[category] = (statement_path.resolve(), statement)
    missing = sorted(level.required_categories - validated.keys())
    if missing:
        raise ReleaseEvidenceError(f"missing required {level_name} evidence categories: {', '.join(missing)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        policy_destination = staging / "policy" / "evidence-policy.json"
        policy_destination.parent.mkdir(parents=True)
        shutil.copyfile(policy.path, policy_destination)
        if matrix is not None and matrix_schema_path is not None:
            shutil.copyfile(matrix.path, staging / "policy" / matrix.path.name)
            shutil.copyfile(matrix_schema_path, staging / "policy" / matrix_schema_path.name)
        _copy_regular_tree(security.directory, staging / "evidence" / "security")
        statement_index: dict[str, str] = {}
        for category, (statement_path, statement) in sorted(validated.items()):
            category_root = staging / "evidence" / category
            category_root.mkdir(parents=True)
            destination_statement = category_root / "gate-statement.json"
            shutil.copyfile(statement_path, destination_statement)
            statement_index[category] = destination_statement.relative_to(staging).as_posix()
            for raw_attachment in statement["attachments"]:
                relative = PurePosixPath(raw_attachment["path"])
                source = statement_path.parent.joinpath(*relative.parts)
                destination = category_root.joinpath(*relative.parts)
                if destination == destination_statement:
                    raise ReleaseEvidenceError(f"attachment collides with bundled statement: {category}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)

        inventory = _payload_inventory(staging)
        generated_at = datetime.now(UTC).isoformat()
        manifest: dict[str, Any] = {
            "schema": BUNDLE_SCHEMA,
            "schema_version": 1,
            "generated_at": generated_at,
            "release_level": level_name,
            "gate_status": "evidence_complete",
            "approval_status": "pending_deployment_approval",
            "production_claim": False,
            "release_tag": release_tag,
            "subject": _subject_document(subject, security.targets),
            "security": {
                "manifest_sha256": security.manifest_sha256,
                "generated_at": security.generated_at.isoformat(),
                "release_mode": security.release_mode,
                "risk_acceptance_reference": security.risk_acceptance_reference,
            },
            "policy": {
                "sha256": _sha256_file(policy_destination),
                "required_categories": sorted(level.required_categories),
            },
            "statements": statement_index,
            "files": inventory,
            "signature": {
                "required": level.require_bundle_signature,
                "present": signing_key_path is not None,
                "key_id": signing_key_id,
            },
        }
        if matrix is not None:
            manifest["goal_section_19"] = goal_completion_audit(
                matrix,
                present_categories=set(validated),
                release_security_verified=security.release_mode,
                signed_git_tag_verified=level.require_signed_git_tag,
                bundle_signature_verified=signing_key_path is not None,
                release_level=level_name,
                release_eligible=True,
            )
        manifest_payload = _canonical_json(manifest)
        (staging / "release-manifest.json").write_bytes(manifest_payload)
        signer: Ed25519PrivateKey | None = None
        if signing_key_path is not None:
            signer = _load_signing_key(signing_key_path)
            public_key = signer.public_key()
            signature_document = {
                "schema": SIGNATURE_SCHEMA,
                "schema_version": 1,
                "algorithm": "Ed25519",
                "key_id": signing_key_id,
                "public_key_sha256": _public_key_fingerprint(public_key),
                "manifest_sha256": _sha256_bytes(manifest_payload),
                "signature": base64.b64encode(signer.sign(manifest_payload)).decode("ascii"),
            }
            (staging / "release-manifest.sig.json").write_bytes(_canonical_json(signature_document))
        checksum_lines = [
            f"{item['sha256']}  {item['path']}" for item in _payload_inventory(staging) if item["path"] != "SHA256SUMS"
        ]
        (staging / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
        verified = _verify_bundle(staging, signer.public_key() if signer is not None else None)
        if repository_subject(repo) != subject:
            raise ReleaseEvidenceError("repository subject changed while assembling the release bundle")
        for directory in [staging, *[path for path in staging.rglob("*") if path.is_dir()]]:
            directory.chmod(0o700)
        for file_path in [path for path in staging.rglob("*") if path.is_file()]:
            file_path.chmod(0o600)
        _rename_noreplace(staging, output)
        return verified
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _safe_checksum_path(value: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ReleaseEvidenceError(f"unsafe checksum path: {value}")
    return relative


def _validate_bundled_semantics(root: Path, manifest: dict[str, Any]) -> tuple[str, PolicyLevel]:
    level_name = manifest.get("release_level")
    if not isinstance(level_name, str):
        raise ReleaseEvidenceError("release manifest level is invalid")
    policy_path = root / "policy" / "evidence-policy.json"
    policy = load_policy(policy_path)
    if level_name not in policy.levels:
        raise ReleaseEvidenceError("release manifest level is absent from its bundled policy")
    level = policy.levels[level_name]
    policy_metadata = manifest.get("policy")
    if (
        not isinstance(policy_metadata, dict)
        or policy_metadata.get("sha256") != _sha256_file(policy_path)
        or policy_metadata.get("required_categories") != sorted(level.required_categories)
    ):
        raise ReleaseEvidenceError("release manifest policy binding is invalid")
    if (
        manifest.get("gate_status") != "evidence_complete"
        or manifest.get("approval_status") != "pending_deployment_approval"
        or manifest.get("production_claim") is not False
    ):
        raise ReleaseEvidenceError("release manifest makes an invalid approval claim")
    subject = manifest.get("subject")
    if not isinstance(subject, dict):
        raise ReleaseEvidenceError("release manifest subject is invalid")
    commit = subject.get("git_commit")
    source_count = subject.get("source_file_count")
    source_sha256 = subject.get("source_tree_sha256")
    targets = subject.get("targets")
    if (
        not isinstance(commit, str)
        or not COMMIT_PATTERN.fullmatch(commit)
        or not isinstance(source_count, int)
        or isinstance(source_count, bool)
        or source_count <= 0
        or not isinstance(source_sha256, str)
        or not SHA256_PATTERN.fullmatch(source_sha256)
        or not isinstance(targets, dict)
        or not targets
        or not all(
            isinstance(name, str) and isinstance(image, str) and IMAGE_PATTERN.fullmatch(image)
            for name, image in targets.items()
        )
    ):
        raise ReleaseEvidenceError("release manifest subject is invalid")

    generated_at = _parse_timestamp(manifest.get("generated_at"), "release bundle generated_at")
    if generated_at > datetime.now(UTC) + timedelta(minutes=5):
        raise ReleaseEvidenceError("release bundle timestamp is in the future")
    security_root = root / "evidence" / "security"
    security_files = {path.relative_to(security_root).as_posix() for path in security_root.rglob("*") if path.is_file()}
    if security_files != SECURITY_REQUIRED_FILES:
        raise ReleaseEvidenceError("bundled security evidence inventory is incomplete or unexpected")
    security_metadata = manifest.get("security")
    security_manifest_path = security_root / "evidence-manifest.json"
    security_manifest = _load_json_object(security_manifest_path, "bundled security evidence manifest")
    if not isinstance(security_metadata, dict):
        raise ReleaseEvidenceError("release manifest security binding is invalid")
    security_sha256 = _sha256_file(security_manifest_path)
    security_policies = security_manifest.get("policies")
    unresolved = security_policies.get("unresolved_high_critical") if isinstance(security_policies, dict) else None
    release_mode = security_policies.get("release_mode") if isinstance(security_policies, dict) else None
    risk_reference = security_policies.get("risk_acceptance_reference") if isinstance(security_policies, dict) else None
    if (
        security_manifest.get("schema_version") != 1
        or not isinstance(release_mode, bool)
        or not isinstance(risk_reference, str)
        or not isinstance(unresolved, dict)
        or not unresolved
        or not all(
            isinstance(count, int) and not isinstance(count, bool) and count >= 0 for count in unresolved.values()
        )
    ):
        raise ReleaseEvidenceError("bundled security evidence policies are invalid")
    if release_mode and sum(unresolved.values()) > 0 and not risk_reference.strip():
        raise ReleaseEvidenceError("bundled release security evidence lacks a risk acceptance reference")
    security_generated_at = _parse_timestamp(security_manifest.get("generated_at"), "bundled security generated_at")
    if security_generated_at > generated_at + timedelta(minutes=5) or generated_at - security_generated_at > timedelta(
        hours=level.security_max_age_hours
    ):
        raise ReleaseEvidenceError("bundled security evidence is outside its evidence window")
    if (
        security_metadata.get("manifest_sha256") != security_sha256
        or security_manifest.get("git_commit") != commit
        or security_manifest.get("git_worktree_state") != "clean"
        or security_manifest.get("source_file_count") != source_count
        or security_manifest.get("source_tree_sha256") != source_sha256
        or security_manifest.get("targets") != targets
        or not isinstance(security_policies, dict)
        or security_metadata.get("release_mode") != security_policies.get("release_mode")
        or security_metadata.get("risk_acceptance_reference") != security_policies.get("risk_acceptance_reference")
        or _parse_timestamp(security_metadata.get("generated_at"), "release security generated_at")
        != security_generated_at
    ):
        raise ReleaseEvidenceError("release manifest security binding is invalid")
    if level.require_release_security and security_metadata.get("release_mode") is not True:
        raise ReleaseEvidenceError("production bundle does not contain release-mode security evidence")

    statement_index = manifest.get("statements")
    if not isinstance(statement_index, dict):
        raise ReleaseEvidenceError("release manifest statement index is invalid")
    if not level.required_categories.issubset(statement_index):
        raise ReleaseEvidenceError("release manifest omits required evidence categories")
    for category, relative_text in statement_index.items():
        if category not in policy.categories or relative_text != f"evidence/{category}/gate-statement.json":
            raise ReleaseEvidenceError("release manifest statement index is invalid")
        statement_path = root.joinpath(*PurePosixPath(relative_text).parts)
        statement = _load_json_object(statement_path, f"bundled {category} statement")
        execution = statement.get("execution")
        if (
            statement.get("schema") != STATEMENT_SCHEMA
            or statement.get("schema_version") != 1
            or statement.get("category") != category
            or statement.get("status") != "passed"
            or statement.get("subject") != subject
            or statement.get("security_manifest_sha256") != security_sha256
            or not isinstance(execution, dict)
            or execution.get("exit_code") != 0
        ):
            raise ReleaseEvidenceError(f"bundled release statement is invalid: {category}")
        statement_time = _parse_timestamp(statement.get("generated_at"), f"bundled {category} generated_at")
        if statement_time > generated_at + timedelta(minutes=5) or generated_at - statement_time > timedelta(
            hours=policy.categories[category]
        ):
            raise ReleaseEvidenceError(f"bundled release statement is outside its evidence window: {category}")
        raw_attachments = statement.get("attachments")
        if not isinstance(raw_attachments, list):
            raise ReleaseEvidenceError(f"bundled release statement attachments are invalid: {category}")
        for attachment_metadata in raw_attachments:
            if not isinstance(attachment_metadata, dict):
                raise ReleaseEvidenceError(f"bundled release statement attachment is invalid: {category}")
            attachment_text = attachment_metadata.get("path")
            if not isinstance(attachment_text, str):
                raise ReleaseEvidenceError(f"bundled release statement attachment is invalid: {category}")
            attachment_relative = _safe_checksum_path(attachment_text)
            attachment = statement_path.parent.joinpath(*attachment_relative.parts)
            if (
                attachment.is_symlink()
                or not attachment.is_file()
                or attachment_metadata.get("size") != attachment.stat().st_size
                or attachment_metadata.get("sha256") != _sha256_file(attachment)
            ):
                raise ReleaseEvidenceError(f"bundled release statement attachment was modified: {category}")
        _validate_specialized_evidence(statement_path, category, statement, policy=policy)
    if level.require_signed_git_tag and not isinstance(manifest.get("release_tag"), str):
        raise ReleaseEvidenceError("production bundle does not identify its verified Git tag")
    return level_name, level


def _verify_bundle(root: Path, trusted_key: Ed25519PublicKey | None) -> dict[str, Any]:
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("release bundle does not exist") from exc
    if not resolved.is_dir() or root.is_symlink():
        raise ReleaseEvidenceError("release bundle must be a regular directory")
    for path in resolved.rglob("*"):
        if path.is_symlink():
            raise ReleaseEvidenceError(f"release bundle contains a symbolic link: {path.relative_to(resolved)}")
        if not path.is_dir() and not path.is_file():
            raise ReleaseEvidenceError(f"release bundle contains a non-regular entry: {path.relative_to(resolved)}")
    checksum_path = resolved / "SHA256SUMS"
    if not checksum_path.is_file():
        raise ReleaseEvidenceError("release bundle is missing SHA256SUMS")
    checksums: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise ReleaseEvidenceError("release bundle contains an invalid checksum line")
        digest, relative_text = match.groups()
        relative = _safe_checksum_path(relative_text)
        normalized = relative.as_posix()
        if normalized in checksums or normalized == "SHA256SUMS":
            raise ReleaseEvidenceError(f"duplicate or recursive checksum entry: {normalized}")
        checksums[normalized] = digest
    actual_files = {
        path.relative_to(resolved).as_posix()
        for path in resolved.rglob("*")
        if path.is_file() and path != checksum_path
    }
    if set(checksums) != actual_files:
        raise ReleaseEvidenceError("release bundle checksum inventory differs from its files")
    for relative_text, expected in checksums.items():
        if _sha256_file(resolved.joinpath(*PurePosixPath(relative_text).parts)) != expected:
            raise ReleaseEvidenceError(f"release bundle file digest mismatch: {relative_text}")

    manifest_path = resolved / "release-manifest.json"
    manifest = _load_json_object(manifest_path, "release bundle manifest")
    if manifest.get("schema") != BUNDLE_SCHEMA or manifest.get("schema_version") != 1:
        raise ReleaseEvidenceError("unsupported release bundle schema")
    raw_inventory = manifest.get("files")
    if not isinstance(raw_inventory, list):
        raise ReleaseEvidenceError("release bundle payload inventory is invalid")
    manifest_inventory: dict[str, tuple[int, str]] = {}
    for item in raw_inventory:
        if not isinstance(item, dict):
            raise ReleaseEvidenceError("release bundle payload entry is invalid")
        relative_text = item.get("path")
        size = item.get("size")
        digest = item.get("sha256")
        if (
            not isinstance(relative_text, str)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(digest, str)
            or not SHA256_PATTERN.fullmatch(digest)
        ):
            raise ReleaseEvidenceError("release bundle payload entry is invalid")
        normalized_path = _safe_checksum_path(relative_text).as_posix()
        if normalized_path in manifest_inventory:
            raise ReleaseEvidenceError(f"duplicate release bundle payload entry: {normalized_path}")
        manifest_inventory[normalized_path] = (size, digest)
    control_files = {"release-manifest.json", "release-manifest.sig.json", "SHA256SUMS"}
    payload_files = actual_files - control_files
    if set(manifest_inventory) != payload_files:
        raise ReleaseEvidenceError("release manifest payload inventory differs from bundled evidence")
    for relative_text, (expected_size, expected_digest) in manifest_inventory.items():
        path = resolved.joinpath(*PurePosixPath(relative_text).parts)
        if path.stat().st_size != expected_size or checksums.get(relative_text) != expected_digest:
            raise ReleaseEvidenceError(f"release manifest payload metadata mismatch: {relative_text}")

    level_name, level = _validate_bundled_semantics(resolved, manifest)

    signature_metadata = manifest.get("signature")
    if not isinstance(signature_metadata, dict):
        raise ReleaseEvidenceError("release manifest signature policy is invalid")
    signature_required = signature_metadata.get("required")
    signature_present = signature_metadata.get("present")
    if not isinstance(signature_required, bool) or not isinstance(signature_present, bool):
        raise ReleaseEvidenceError("release manifest signature policy is invalid")
    if signature_required != level.require_bundle_signature:
        raise ReleaseEvidenceError("release manifest signature requirement differs from policy")
    signature_path = resolved / "release-manifest.sig.json"
    if signature_present != signature_path.is_file():
        raise ReleaseEvidenceError("release bundle signature presence differs from its manifest")
    if signature_required and not signature_present:
        raise ReleaseEvidenceError("release bundle requires a signature")
    if signature_present:
        if trusted_key is None:
            raise ReleaseEvidenceError("a trusted Ed25519 public key is required to verify this bundle")
        signature_document = _load_json_object(signature_path, "release bundle signature")
        if (
            signature_document.get("schema") != SIGNATURE_SCHEMA
            or signature_document.get("schema_version") != 1
            or signature_document.get("algorithm") != "Ed25519"
            or signature_document.get("key_id") != signature_metadata.get("key_id")
            or signature_document.get("public_key_sha256") != _public_key_fingerprint(trusted_key)
        ):
            raise ReleaseEvidenceError("release bundle signature metadata is invalid")
        manifest_payload = manifest_path.read_bytes()
        if signature_document.get("manifest_sha256") != _sha256_bytes(manifest_payload):
            raise ReleaseEvidenceError("release bundle signature references a different manifest")
        encoded_signature = signature_document.get("signature")
        if not isinstance(encoded_signature, str):
            raise ReleaseEvidenceError("release bundle signature is invalid")
        try:
            signature = base64.b64decode(encoded_signature, validate=True)
            trusted_key.verify(signature, manifest_payload)
        except (ValueError, InvalidSignature) as exc:
            raise ReleaseEvidenceError("release bundle signature verification failed") from exc
    if level_name == "production" and not signature_present:
        raise ReleaseEvidenceError("production release bundle is unsigned")
    bundled_policy = load_policy(resolved / "policy" / "evidence-policy.json")
    matrix, _ = _repository_goal_matrix_contract(resolved, bundled_policy, level_name)
    declared_goal = manifest.get("goal_section_19")
    goal_result: dict[str, Any] | None = None
    if matrix is None:
        if declared_goal is not None:
            raise ReleaseEvidenceError("release manifest declares GOAL status without a bundled matrix")
    else:
        statements = manifest.get("statements")
        security = manifest.get("security")
        if not isinstance(statements, dict) or not isinstance(security, dict):
            raise ReleaseEvidenceError("release manifest GOAL inputs are invalid")
        goal_result = goal_completion_audit(
            matrix,
            present_categories=set(statements),
            release_security_verified=security.get("release_mode") is True,
            signed_git_tag_verified=level.require_signed_git_tag and isinstance(manifest.get("release_tag"), str),
            bundle_signature_verified=signature_present,
            release_level=level_name,
            release_eligible=True,
        )
        if declared_goal != goal_result:
            raise ReleaseEvidenceError("release manifest GOAL completion status is invalid")
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "passed",
        "release_level": level_name,
        "git_commit": manifest.get("subject", {}).get("git_commit")
        if isinstance(manifest.get("subject"), dict)
        else None,
        "files_verified": len(actual_files),
        "signature_verified": signature_present,
        "production_claim": False,
    }
    if goal_result is not None:
        result["goal_section_19"] = goal_result
    return result


def verify_bundle(bundle: Path, trusted_public_key: Path | None = None) -> dict[str, Any]:
    key = _load_public_key(trusted_public_key) if trusted_public_key is not None else None
    return _verify_bundle(bundle, key)


def goal_completion_audit(
    matrix: GoalCompletionMatrix,
    *,
    present_categories: set[str],
    release_security_verified: bool,
    signed_git_tag_verified: bool,
    bundle_signature_verified: bool,
    release_level: str,
    release_eligible: bool,
) -> dict[str, Any]:
    requirement_results: list[dict[str, Any]] = []
    counts = {"proven": 0, "baseline_only": 0, "missing": 0}
    for requirement in matrix.requirements:
        missing_baseline = sorted(requirement.baseline_categories - present_categories)
        missing_production = sorted(requirement.production_categories - present_categories)
        missing_controls: list[str] = []
        if requirement.requires_release_security and not release_security_verified:
            missing_controls.append("release_security")
        if requirement.requires_signed_git_tag and not signed_git_tag_verified:
            missing_controls.append("signed_git_tag")
        if requirement.requires_bundle_signature and not bundle_signature_verified:
            missing_controls.append("bundle_signature")
        if not missing_production and not missing_controls:
            status = "proven"
        elif not missing_baseline:
            status = "baseline_only"
        else:
            status = "missing"
        counts[status] += 1
        requirement_results.append(
            {
                "id": requirement.identifier,
                "ordinal": requirement.ordinal,
                "group": requirement.group,
                "title": requirement.title,
                "status": status,
                "missing_baseline_categories": missing_baseline,
                "missing_production_categories": missing_production,
                "missing_production_controls": missing_controls,
            }
        )
    production_complete = (
        release_level == "production" and release_eligible and counts["proven"] == len(matrix.requirements)
    )
    return {
        "schema": GOAL_COMPLETION_AUDIT_SCHEMA,
        "schema_version": 1,
        "goal_document_id": matrix.goal_document_id,
        "goal_version": matrix.goal_version,
        "section": matrix.section,
        "matrix_sha256": _sha256_file(matrix.path),
        "requirement_count": len(matrix.requirements),
        "proven_count": counts["proven"],
        "baseline_only_count": counts["baseline_only"],
        "missing_count": counts["missing"],
        "production_complete": production_complete,
        "requirements": requirement_results,
    }


def audit_release(
    *,
    repo: Path,
    policy_path: Path,
    level_name: str,
    security_directory: Path,
    statements: list[Path],
    release_tag: str | None,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    if level_name not in policy.levels:
        raise ReleaseEvidenceError(f"unknown release evidence level: {level_name}")
    _require_authoritative_production_policy(repo, policy, level_name)
    level = policy.levels[level_name]
    subject = repository_subject(repo)
    matrix, _ = _repository_goal_matrix_contract(repo, policy, level_name)
    security = validate_security_evidence(
        security_directory,
        subject,
        maximum_age_hours=level.security_max_age_hours,
    )
    categories: set[str] = set()
    blockers: list[str] = []
    for statement_path in statements:
        try:
            category, _ = _statement_category(
                statement_path.resolve(), policy=policy, subject=subject, security=security
            )
            if category in categories:
                blockers.append(f"duplicate evidence category: {category}")
            categories.add(category)
        except ReleaseEvidenceError as exc:
            blockers.append(str(exc))
    missing = sorted(level.required_categories - categories)
    blockers.extend(f"missing evidence category: {category}" for category in missing)
    if level.require_release_security and not security.release_mode:
        blockers.append("security evidence was not generated in release mode")
    signed_git_tag_verified = False
    try:
        _check_release_tag(repo, subject, release_tag, level.require_signed_git_tag)
    except ReleaseEvidenceError as exc:
        blockers.append(str(exc))
    if release_tag is not None:
        try:
            _check_release_tag(repo, subject, release_tag, True)
            signed_git_tag_verified = True
        except ReleaseEvidenceError:
            pass
    if level.require_bundle_signature:
        blockers.append("production assembly requires an external Ed25519 signing key")
    result: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "release_level": level_name,
        "status": "eligible" if not blockers else "blocked",
        "subject": _subject_document(subject, security.targets),
        "present_categories": sorted(categories),
        "missing_categories": missing,
        "blockers": blockers,
        "production_claim": False,
    }
    if matrix is not None:
        result["goal_section_19"] = goal_completion_audit(
            matrix,
            present_categories=categories,
            release_security_verified=security.release_mode,
            signed_git_tag_verified=signed_git_tag_verified,
            bundle_signature_verified=False,
            release_level=level_name,
            release_eligible=not blockers,
        )
    return result


def production_evidence_requirements(*, policy_path: Path, category: str) -> dict[str, Any]:
    policy = load_policy(policy_path)
    contract = policy.production_contracts.get(category)
    if contract is None:
        raise ReleaseEvidenceError(f"category does not accept external production evidence: {category}")
    detail_reports: list[dict[str, str]] = []
    if category == "mcp_sender_constraint":
        detail_reports.append(
            {
                "path": MCP_SENDER_CONSTRAINT_REPORT,
                "schema": MCP_SENDER_CONSTRAINT_SCHEMA,
                "schema_file": "deploy/release/mcp-sender-constraint-report.schema.json",
            }
        )
    elif category == "production_topology":
        detail_reports.extend(
            [
                {
                    "path": PRODUCTION_TOPOLOGY_REPORT,
                    "schema": PRODUCTION_TOPOLOGY_SCHEMA,
                    "schema_file": "deploy/release/production-topology-report.schema.json",
                },
                {
                    "path": PRODUCTION_TOPOLOGY_LIVE_REPORT,
                    "schema": PRODUCTION_TOPOLOGY_LIVE_SCHEMA,
                    "schema_file": "deploy/release/production-topology-live-probe.schema.json",
                },
            ]
        )
    return {
        "schema": "pharma.production-evidence-requirements.v2",
        "schema_version": 2,
        "category": category,
        "max_age_hours": policy.categories[category],
        "checks": sorted(contract.checks),
        "approval_roles": sorted(contract.approval_roles),
        "minimum_artifacts": contract.minimum_artifacts,
        "require_independent_executor": contract.require_independent_executor,
        "intake_schema": "deploy/release/production-evidence-intake.schema.json",
        "report_schema": "deploy/release/production-evidence-report.schema.json",
        "detail_reports": detail_reports,
        "production_claim": False,
    }


def _external_directory_output(repo: Path, output: Path, label: str) -> tuple[Path, Path]:
    try:
        resolved_repo = repo.resolve(strict=True)
        output_parent = output.parent.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError(f"{label} repository or output parent does not exist") from exc
    resolved_output = output_parent / output.name
    if (
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", output.name) is None
        or resolved_output.exists()
        or resolved_output.is_symlink()
    ):
        raise ReleaseEvidenceError(f"refusing to overwrite {label}: {output}")
    if output_parent == resolved_repo or resolved_repo in output_parent.parents:
        raise ReleaseEvidenceError(f"{label} output must be outside the source repository")
    return resolved_repo, resolved_output


def prepare_production_evidence_handoff(
    *,
    repo: Path,
    policy_path: Path,
    output: Path,
    signing_key_path: Path | None = None,
    signing_key_id: str | None = None,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    _require_authoritative_production_policy(repo, policy, "production")
    resolved_repo, resolved_output = _external_directory_output(repo, output, "production handoff")
    if signing_key_path is None and signing_key_id is not None:
        raise ReleaseEvidenceError("production handoff signing key id requires a signing key")
    if signing_key_path is not None and not signing_key_id:
        raise ReleaseEvidenceError("production handoff signing key id is required")
    if signing_key_id is not None and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}", signing_key_id) is None:
        raise ReleaseEvidenceError("production handoff signing key id is invalid")
    signer = _load_signing_key(signing_key_path) if signing_key_path is not None else None
    subject = repository_subject(resolved_repo)
    matrix, matrix_schema_path = _repository_goal_matrix_contract(resolved_repo, policy, "production")
    schema_names = (
        "mcp-sender-constraint-report.schema.json",
        "production-evidence-batch-intake.schema.json",
        "production-evidence-batch-manifest.schema.json",
        "production-evidence-handoff-manifest.schema.json",
        "production-evidence-intake.schema.json",
        "production-evidence-report.schema.json",
        "production-topology-live-probe.schema.json",
        "production-topology-report.schema.json",
    )
    schema_sources = [resolved_repo / "deploy" / "release" / name for name in schema_names]
    if any(path.is_symlink() or not path.is_file() for path in schema_sources):
        raise ReleaseEvidenceError("production handoff schemas are missing from the committed repository")
    try:
        policy_payload = policy.path.read_bytes()
        schema_payloads = {source.name: source.read_bytes() for source in schema_sources}
        matrix_payload = matrix.path.read_bytes() if matrix is not None else None
        matrix_schema_payload = matrix_schema_path.read_bytes() if matrix_schema_path is not None else None
    except OSError as exc:
        raise ReleaseEvidenceError("cannot read the committed production handoff contracts") from exc

    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.handoff-", dir=resolved_output.parent))
    try:
        _atomic_write(staging / "policy" / "evidence-policy.json", policy_payload)
        if (
            matrix is not None
            and matrix_schema_path is not None
            and matrix_payload is not None
            and matrix_schema_payload is not None
        ):
            _atomic_write(staging / "policy" / matrix.path.name, matrix_payload)
            _atomic_write(staging / "policy" / matrix_schema_path.name, matrix_schema_payload)
        for name, payload in schema_payloads.items():
            _atomic_write(staging / "schemas" / name, payload)
        categories: list[dict[str, object]] = []
        for category in sorted(policy.production_contracts):
            requirement_path = staging / "requirements" / f"{category}.json"
            requirements = production_evidence_requirements(policy_path=policy.path, category=category)
            _atomic_write(requirement_path, _canonical_json(requirements))
            categories.append(
                {
                    "category": category,
                    "requirements": requirement_path.relative_to(staging).as_posix(),
                }
            )
        inventory = _payload_inventory(staging)
        manifest = {
            "schema": PRODUCTION_HANDOFF_SCHEMA,
            "schema_version": 2,
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "requirements_only",
            "production_claim": False,
            "subject": {
                "git_commit": subject.commit,
                "source_file_count": subject.source_file_count,
                "source_tree_sha256": subject.source_tree_sha256,
            },
            "policy_sha256": _sha256_bytes(policy_payload),
            "categories": categories,
            "files": inventory,
            "signature": {
                "present": signer is not None,
                "key_id": signing_key_id,
                "public_key_sha256": _public_key_fingerprint(signer.public_key()) if signer is not None else None,
            },
        }
        manifest_payload = _canonical_json(manifest)
        _atomic_write(staging / "handoff-manifest.json", manifest_payload)
        if signer is not None:
            signature_document = {
                "schema": SIGNATURE_SCHEMA,
                "schema_version": 1,
                "algorithm": "Ed25519",
                "key_id": signing_key_id,
                "public_key_sha256": _public_key_fingerprint(signer.public_key()),
                "manifest_sha256": _sha256_bytes(manifest_payload),
                "signature": base64.b64encode(signer.sign(manifest_payload)).decode("ascii"),
            }
            _atomic_write(staging / "handoff-manifest.sig.json", _canonical_json(signature_document))
        if repository_subject(resolved_repo) != subject:
            raise ReleaseEvidenceError("repository subject changed while preparing the production handoff")
        for directory in sorted((path for path in staging.rglob("*") if path.is_dir()), reverse=True):
            directory.chmod(0o700)
            _fsync_directory(directory)
        staging.chmod(0o700)
        _fsync_directory(staging)
        _rename_noreplace(staging, resolved_output)
        _fsync_directory(resolved_output.parent)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        "schema_version": 2,
        "status": "prepared",
        "output": str(resolved_output),
        "category_count": len(categories),
        "signature_present": signer is not None,
        "production_claim": False,
    }


def verify_production_evidence_handoff(
    *,
    repo: Path,
    policy_path: Path,
    handoff: Path,
    trusted_public_key: Path | None = None,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    _require_authoritative_production_policy(repo, policy, "production")
    subject = repository_subject(repo)
    if handoff.is_symlink():
        raise ReleaseEvidenceError("production handoff cannot be a symbolic link")
    try:
        root = handoff.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("production handoff does not exist") from exc
    if not root.is_dir():
        raise ReleaseEvidenceError("production handoff must be a directory")
    manifest_path = root / "handoff-manifest.json"
    manifest = _load_json_object(manifest_path, "production handoff manifest")
    categories = manifest.get("categories")
    files = manifest.get("files")
    expected_subject = {
        "git_commit": subject.commit,
        "source_file_count": subject.source_file_count,
        "source_tree_sha256": subject.source_tree_sha256,
    }
    if (
        set(manifest) != PRODUCTION_HANDOFF_FIELDS
        or manifest.get("schema") != PRODUCTION_HANDOFF_SCHEMA
        or manifest.get("schema_version") != 2
        or manifest.get("status") != "requirements_only"
        or manifest.get("production_claim") is not False
        or manifest.get("subject") != expected_subject
        or manifest.get("policy_sha256") != _sha256_file(policy.path)
        or not isinstance(categories, list)
        or not isinstance(files, list)
    ):
        raise ReleaseEvidenceError("production handoff manifest has an invalid contract or source binding")
    _parse_timestamp(manifest.get("generated_at"), "production handoff generated_at")

    declared_categories: set[str] = set()
    for item in categories:
        if not isinstance(item, dict) or set(item) != PRODUCTION_HANDOFF_CATEGORY_FIELDS:
            raise ReleaseEvidenceError("production handoff contains an invalid category requirement")
        category = item.get("category")
        requirements_path = item.get("requirements")
        if (
            not isinstance(category, str)
            or category in declared_categories
            or category not in policy.production_contracts
            or not isinstance(requirements_path, str)
            or requirements_path != f"requirements/{category}.json"
        ):
            raise ReleaseEvidenceError("production handoff category binding is invalid")
        expected_requirements = production_evidence_requirements(policy_path=policy.path, category=category)
        actual_requirements = _load_json_object(root / requirements_path, f"{category} production requirements")
        if actual_requirements != expected_requirements:
            raise ReleaseEvidenceError("production handoff requirements differ from the authoritative policy")
        declared_categories.add(category)
    if declared_categories != set(policy.production_contracts):
        raise ReleaseEvidenceError("production handoff does not cover every external production category")

    actual_files: dict[str, tuple[int, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ReleaseEvidenceError(f"production handoff contains a symbolic link: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ReleaseEvidenceError(f"production handoff contains a non-regular entry: {relative}")
        if path not in {manifest_path, root / "handoff-manifest.sig.json"}:
            actual_files[relative] = (path.stat().st_size, _sha256_file(path))
    declared_files: dict[str, tuple[int, str]] = {}
    for item in files:
        if not isinstance(item, dict) or set(item) != PRODUCTION_HANDOFF_FILE_FIELDS:
            raise ReleaseEvidenceError("production handoff contains invalid file metadata")
        raw_path = item.get("path")
        size = item.get("size")
        digest = item.get("sha256")
        if not isinstance(raw_path, str):
            raise ReleaseEvidenceError("production handoff contains invalid file metadata")
        relative_path = PurePosixPath(raw_path)
        if (
            relative_path.is_absolute()
            or not relative_path.parts
            or ".." in relative_path.parts
            or relative_path.as_posix() != raw_path
            or raw_path == "handoff-manifest.json"
            or raw_path in declared_files
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size <= 0
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
        ):
            raise ReleaseEvidenceError("production handoff contains invalid file metadata")
        declared_files[raw_path] = (size, digest)
    if declared_files != actual_files:
        raise ReleaseEvidenceError("production handoff file inventory is incomplete or has a digest mismatch")
    copied_policy = root / "policy" / "evidence-policy.json"
    if _sha256_file(copied_policy) != _sha256_file(policy.path):
        raise ReleaseEvidenceError("production handoff policy snapshot differs from the authoritative policy")
    load_policy(copied_policy)
    source_matrix, source_matrix_schema = _repository_goal_matrix_contract(repo, policy, "production")
    copied_matrix, copied_matrix_schema = _repository_goal_matrix_contract(
        root, load_policy(copied_policy), "production"
    )
    if (source_matrix is None) != (copied_matrix is None):
        raise ReleaseEvidenceError("production handoff GOAL matrix snapshot is incomplete")
    if source_matrix is not None and copied_matrix is not None:
        if (
            _sha256_file(source_matrix.path) != _sha256_file(copied_matrix.path)
            or source_matrix_schema is None
            or copied_matrix_schema is None
            or _sha256_file(source_matrix_schema) != _sha256_file(copied_matrix_schema)
        ):
            raise ReleaseEvidenceError("production handoff GOAL matrix differs from the authoritative repository")
    for name in (
        "mcp-sender-constraint-report.schema.json",
        "production-evidence-batch-intake.schema.json",
        "production-evidence-batch-manifest.schema.json",
        "production-evidence-handoff-manifest.schema.json",
        "production-evidence-intake.schema.json",
        "production-evidence-report.schema.json",
        "production-topology-live-probe.schema.json",
        "production-topology-report.schema.json",
    ):
        if _sha256_file(root / "schemas" / name) != _sha256_file(repo / "deploy" / "release" / name):
            raise ReleaseEvidenceError("production handoff schema snapshot differs from the authoritative repository")
    signature_verified = _verify_production_handoff_signature(
        root=root,
        manifest=manifest,
        trusted_public_key=trusted_public_key,
    )
    return {
        "schema_version": 2,
        "status": "passed",
        "handoff": str(root),
        "category_count": len(declared_categories),
        "files_verified": len(declared_files),
        "signature_verified": signature_verified,
        "production_claim": False,
    }


def _verify_production_handoff_signature(
    *,
    root: Path,
    manifest: dict[str, Any],
    trusted_public_key: Path | None,
) -> bool:
    metadata = manifest.get("signature")
    if not isinstance(metadata, dict) or set(metadata) != PRODUCTION_HANDOFF_SIGNATURE_FIELDS:
        raise ReleaseEvidenceError("production handoff signature metadata is invalid")
    present = metadata.get("present")
    key_id = metadata.get("key_id")
    fingerprint = metadata.get("public_key_sha256")
    signature_path = root / "handoff-manifest.sig.json"
    if not isinstance(present, bool) or present != signature_path.is_file():
        raise ReleaseEvidenceError("production handoff signature presence differs from its manifest")
    if not present:
        if key_id is not None or fingerprint is not None:
            raise ReleaseEvidenceError("unsigned production handoff contains signing metadata")
        return False
    if (
        not isinstance(key_id, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}", key_id) is None
        or not isinstance(fingerprint, str)
        or SHA256_PATTERN.fullmatch(fingerprint) is None
    ):
        raise ReleaseEvidenceError("production handoff signature metadata is invalid")
    if trusted_public_key is None:
        raise ReleaseEvidenceError("a trusted Ed25519 public key is required to verify this handoff")
    trusted_key = _load_public_key(trusted_public_key)
    signature_document = _load_json_object(signature_path, "production handoff signature")
    manifest_payload = (root / "handoff-manifest.json").read_bytes()
    if (
        signature_document.get("schema") != SIGNATURE_SCHEMA
        or signature_document.get("schema_version") != 1
        or signature_document.get("algorithm") != "Ed25519"
        or signature_document.get("key_id") != key_id
        or signature_document.get("public_key_sha256") != fingerprint
        or fingerprint != _public_key_fingerprint(trusted_key)
        or signature_document.get("manifest_sha256") != _sha256_bytes(manifest_payload)
    ):
        raise ReleaseEvidenceError("production handoff signature metadata is invalid")
    encoded_signature = signature_document.get("signature")
    if not isinstance(encoded_signature, str):
        raise ReleaseEvidenceError("production handoff signature is invalid")
    try:
        trusted_key.verify(base64.b64decode(encoded_signature, validate=True), manifest_payload)
    except (ValueError, InvalidSignature) as exc:
        raise ReleaseEvidenceError("production handoff signature verification failed") from exc
    return True


def verify_production_evidence_handoff_offline(
    *,
    handoff: Path,
    trusted_public_key: Path,
) -> dict[str, Any]:
    if handoff.is_symlink():
        raise ReleaseEvidenceError("production handoff cannot be a symbolic link")
    try:
        root = handoff.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("production handoff does not exist") from exc
    if not root.is_dir():
        raise ReleaseEvidenceError("production handoff must be a directory")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ReleaseEvidenceError(f"production handoff contains a symbolic link: {path.relative_to(root)}")
        if not path.is_dir() and not path.is_file():
            raise ReleaseEvidenceError(f"production handoff contains a non-regular entry: {path.relative_to(root)}")
    manifest = _load_json_object(root / "handoff-manifest.json", "production handoff manifest")
    if (
        set(manifest) != PRODUCTION_HANDOFF_FIELDS
        or manifest.get("schema") != PRODUCTION_HANDOFF_SCHEMA
        or manifest.get("schema_version") != 2
        or manifest.get("status") != "requirements_only"
        or manifest.get("production_claim") is not False
    ):
        raise ReleaseEvidenceError("production handoff manifest is invalid")
    subject = manifest.get("subject")
    if (
        not isinstance(subject, dict)
        or set(subject) != PRODUCTION_HANDOFF_SUBJECT_FIELDS
        or not isinstance(subject.get("git_commit"), str)
        or COMMIT_PATTERN.fullmatch(subject["git_commit"]) is None
        or not isinstance(subject.get("source_file_count"), int)
        or isinstance(subject.get("source_file_count"), bool)
        or subject["source_file_count"] <= 0
        or not isinstance(subject.get("source_tree_sha256"), str)
        or SHA256_PATTERN.fullmatch(subject["source_tree_sha256"]) is None
    ):
        raise ReleaseEvidenceError("production handoff subject is invalid")
    _parse_timestamp(manifest.get("generated_at"), "production handoff generated_at")
    policy_path = root / "policy" / "evidence-policy.json"
    if manifest.get("policy_sha256") != _sha256_file(policy_path):
        raise ReleaseEvidenceError("production handoff policy digest is invalid")
    policy = load_policy(policy_path)
    _repository_goal_matrix_contract(root, policy, "production")
    categories = manifest.get("categories")
    if not isinstance(categories, list):
        raise ReleaseEvidenceError("production handoff categories are invalid")
    declared_categories: set[str] = set()
    for item in categories:
        if not isinstance(item, dict) or set(item) != PRODUCTION_HANDOFF_CATEGORY_FIELDS:
            raise ReleaseEvidenceError("production handoff contains an invalid category requirement")
        category = item.get("category")
        requirement_path = item.get("requirements")
        if (
            not isinstance(category, str)
            or category in declared_categories
            or category not in policy.production_contracts
            or requirement_path != f"requirements/{category}.json"
        ):
            raise ReleaseEvidenceError("production handoff category binding is invalid")
        expected = production_evidence_requirements(policy_path=policy_path, category=category)
        if _load_json_object(root / requirement_path, f"{category} production requirements") != expected:
            raise ReleaseEvidenceError("production handoff requirements differ from its bundled policy")
        declared_categories.add(category)
    if declared_categories != set(policy.production_contracts):
        raise ReleaseEvidenceError("production handoff does not cover every external production category")
    manifest_path = root / "handoff-manifest.json"
    signature_path = root / "handoff-manifest.sig.json"
    actual_files = {
        path.relative_to(root).as_posix(): (path.stat().st_size, _sha256_file(path))
        for path in sorted(root.rglob("*"))
        if path.is_file() and path not in {manifest_path, signature_path}
    }
    declared_files: dict[str, tuple[int, str]] = {}
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ReleaseEvidenceError("production handoff file inventory is invalid")
    for item in files:
        if not isinstance(item, dict) or set(item) != PRODUCTION_HANDOFF_FILE_FIELDS:
            raise ReleaseEvidenceError("production handoff contains invalid file metadata")
        raw_path, size, digest = item.get("path"), item.get("size"), item.get("sha256")
        if (
            not isinstance(raw_path, str)
            or _safe_checksum_path(raw_path).as_posix() != raw_path
            or raw_path in declared_files
            or raw_path in {"handoff-manifest.json", "handoff-manifest.sig.json"}
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size <= 0
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
        ):
            raise ReleaseEvidenceError("production handoff contains invalid file metadata")
        declared_files[raw_path] = (size, digest)
    if declared_files != actual_files:
        raise ReleaseEvidenceError("production handoff file inventory is incomplete or has a digest mismatch")
    if not _verify_production_handoff_signature(
        root=root,
        manifest=manifest,
        trusted_public_key=trusted_public_key,
    ):
        raise ReleaseEvidenceError("offline production handoff verification requires a signature")
    return {
        "schema_version": 2,
        "status": "passed",
        "handoff": str(root),
        "category_count": len(declared_categories),
        "files_verified": len(declared_files),
        "signature_verified": True,
        "production_claim": False,
    }


def register_production_evidence_batch(
    *,
    repo: Path,
    policy_path: Path,
    security_directory: Path,
    manifest_path: Path,
    output: Path,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    _require_authoritative_production_policy(repo, policy, "production")
    resolved_repo, resolved_output = _external_directory_output(repo, output, "production evidence batch")
    try:
        manifest = manifest_path.resolve(strict=True)
    except OSError as exc:
        raise ReleaseEvidenceError("production evidence batch manifest does not exist") from exc
    if manifest_path.is_symlink() or not manifest.is_file():
        raise ReleaseEvidenceError("production evidence batch manifest must be a regular file")
    if manifest == resolved_repo or resolved_repo in manifest.parents:
        raise ReleaseEvidenceError("production evidence batch manifest must be outside the source repository")
    manifest_size = manifest.stat().st_size
    if not 0 < manifest_size <= MAX_PRODUCTION_INTAKE_BYTES:
        raise ReleaseEvidenceError("production evidence batch manifest has an invalid size")
    document = _load_json_object(manifest, "production evidence batch manifest")
    entries = document.get("requests")
    if (
        set(document) != PRODUCTION_BATCH_INTAKE_FIELDS
        or document.get("schema") != PRODUCTION_BATCH_INTAKE_SCHEMA
        or document.get("schema_version") != 1
        or not isinstance(entries, list)
        or not 1 <= len(entries) <= MAX_PRODUCTION_BATCH_CATEGORIES
    ):
        raise ReleaseEvidenceError("production evidence batch manifest has an invalid schema")

    request_paths: dict[str, Path] = {}
    seen_requests: set[Path] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != PRODUCTION_BATCH_ENTRY_FIELDS:
            raise ReleaseEvidenceError("production evidence batch contains an invalid request entry")
        category = entry.get("category")
        if not isinstance(category, str) or category not in policy.production_contracts or category in request_paths:
            raise ReleaseEvidenceError("production evidence batch contains an invalid or duplicate category")
        request = _external_evidence_source(entry.get("request_path"), repo=resolved_repo, request=manifest)
        if request in seen_requests:
            raise ReleaseEvidenceError("production evidence batch cannot reuse one intake request")
        request_document = _load_json_object(request, f"{category} production evidence intake request")
        if request_document.get("category") != category or request_document.get("schema") != PRODUCTION_INTAKE_SCHEMA:
            raise ReleaseEvidenceError("production evidence batch entry does not match its intake request")
        request_paths[category] = request
        seen_requests.add(request)
    expected_categories = set(policy.production_contracts)
    if set(request_paths) != expected_categories:
        missing = ", ".join(sorted(expected_categories - request_paths.keys()))
        raise ReleaseEvidenceError(f"production evidence batch is incomplete; missing categories: {missing}")

    subject = repository_subject(resolved_repo)
    level = policy.levels["production"]
    security = validate_security_evidence(
        security_directory,
        subject,
        maximum_age_hours=level.security_max_age_hours,
    )
    if not security.release_mode:
        raise ReleaseEvidenceError("production evidence batch requires release-mode security evidence")

    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.batch-", dir=resolved_output.parent))
    category_documents: list[dict[str, object]] = []
    try:
        for category, request in sorted(request_paths.items()):
            category_output = staging / category
            register_production_evidence(
                repo=resolved_repo,
                policy_path=policy.path,
                security_directory=security.directory,
                request_path=request,
                output=category_output,
            )
            statement = category_output / "gate-statement.json"
            validated_category, _ = _statement_category(
                statement,
                policy=policy,
                subject=subject,
                security=security,
            )
            if validated_category != category:
                raise ReleaseEvidenceError("registered production category differs from its batch entry")
            category_documents.append(
                {
                    "category": category,
                    "statement": statement.relative_to(staging).as_posix(),
                    "statement_sha256": _sha256_file(statement),
                }
            )
        batch_manifest = {
            "schema": PRODUCTION_BATCH_MANIFEST_SCHEMA,
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "registered",
            "production_claim": False,
            "subject": _subject_document(subject, security.targets),
            "security_manifest_sha256": security.manifest_sha256,
            "categories": category_documents,
        }
        _atomic_write(staging / "batch-manifest.json", _canonical_json(batch_manifest))
        if repository_subject(resolved_repo) != subject:
            raise ReleaseEvidenceError("repository subject changed while registering production evidence batch")
        if (
            validate_security_evidence(
                security.directory,
                subject,
                maximum_age_hours=level.security_max_age_hours,
            )
            != security
        ):
            raise ReleaseEvidenceError("security evidence changed while registering production evidence batch")
        for directory in sorted((path for path in staging.rglob("*") if path.is_dir()), reverse=True):
            directory.chmod(0o700)
            _fsync_directory(directory)
        staging.chmod(0o700)
        _fsync_directory(staging)
        _rename_noreplace(staging, resolved_output)
        _fsync_directory(resolved_output.parent)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        "schema_version": 1,
        "status": "registered",
        "output": str(resolved_output),
        "category_count": len(category_documents),
        "production_claim": False,
    }


def _default_policy(repo: Path) -> Path:
    return repo / "deploy" / "release" / "evidence-policy.json"


def _add_repository_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--policy", type=Path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture, assemble and verify release evidence")
    commands = parser.add_subparsers(dest="action", required=True)

    capture_parser = commands.add_parser(
        "capture", help="Run one gate and bind its result to the current release subject"
    )
    _add_repository_arguments(capture_parser)
    capture_parser.add_argument("--category", required=True)
    capture_parser.add_argument("--security-dir", type=Path, required=True)
    capture_parser.add_argument("--output", type=Path, required=True)
    capture_parser.add_argument("--attachment", type=Path, action="append", default=[])
    capture_parser.add_argument("--log-attachment", type=Path)
    capture_parser.add_argument("command", nargs=argparse.REMAINDER)

    register_parser = commands.add_parser(
        "register-production",
        help="Atomically bind real external production artifacts and approvals to the current release subject",
    )
    _add_repository_arguments(register_parser)
    register_parser.add_argument("--security-dir", type=Path, required=True)
    register_parser.add_argument("--request", type=Path, required=True)
    register_parser.add_argument("--output", type=Path, required=True)

    requirements_parser = commands.add_parser(
        "production-requirements",
        help="Print the exact checks, approvals and artifact threshold for one production category",
    )
    _add_repository_arguments(requirements_parser)
    requirements_parser.add_argument("--category", required=True)
    requirements_parser.add_argument("--output", type=Path)

    handoff_parser = commands.add_parser(
        "prepare-production-handoff",
        help="Atomically publish the authoritative external production evidence requirements",
    )
    _add_repository_arguments(handoff_parser)
    handoff_parser.add_argument("--output", type=Path, required=True)
    handoff_parser.add_argument("--signing-key", type=Path)
    handoff_parser.add_argument("--signing-key-id")

    handoff_verify_parser = commands.add_parser(
        "verify-production-handoff",
        help="Verify a requirements handoff against the current committed production policy",
    )
    _add_repository_arguments(handoff_verify_parser)
    handoff_verify_parser.add_argument("--handoff", type=Path, required=True)
    handoff_verify_parser.add_argument("--trusted-public-key", type=Path)

    handoff_offline_parser = commands.add_parser(
        "verify-production-handoff-offline",
        help="Verify a signed requirements handoff without a source repository",
    )
    handoff_offline_parser.add_argument("--handoff", type=Path, required=True)
    handoff_offline_parser.add_argument("--trusted-public-key", type=Path, required=True)

    batch_parser = commands.add_parser(
        "register-production-batch",
        help="Atomically register every external production evidence category",
    )
    _add_repository_arguments(batch_parser)
    batch_parser.add_argument("--security-dir", type=Path, required=True)
    batch_parser.add_argument("--manifest", type=Path, required=True)
    batch_parser.add_argument("--output", type=Path, required=True)

    assemble_parser = commands.add_parser("assemble", help="Create a checksummed release evidence directory")
    _add_repository_arguments(assemble_parser)
    assemble_parser.add_argument("--level", required=True)
    assemble_parser.add_argument("--security-dir", type=Path, required=True)
    assemble_parser.add_argument("--statement", type=Path, action="append", default=[])
    assemble_parser.add_argument("--statement-dir", type=Path, action="append", default=[])
    assemble_parser.add_argument("--output", type=Path, required=True)
    assemble_parser.add_argument("--release-tag")
    assemble_parser.add_argument("--signing-key", type=Path)
    assemble_parser.add_argument("--signing-key-id")

    audit_parser = commands.add_parser("audit", help="Report missing or invalid release evidence without assembling")
    _add_repository_arguments(audit_parser)
    audit_parser.add_argument("--level", required=True)
    audit_parser.add_argument("--security-dir", type=Path, required=True)
    audit_parser.add_argument("--statement", type=Path, action="append", default=[])
    audit_parser.add_argument("--statement-dir", type=Path, action="append", default=[])
    audit_parser.add_argument("--release-tag")
    audit_parser.add_argument("--output", type=Path)

    verify_parser = commands.add_parser("verify", help="Verify a release evidence directory offline")
    verify_parser.add_argument("bundle", type=Path)
    verify_parser.add_argument("--trusted-public-key", type=Path)
    verify_parser.add_argument("--output", type=Path)
    return parser


def main(arguments: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(arguments)
    try:
        if args.action == "capture":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            command = list(args.command)
            if command and command[0] == "--":
                command = command[1:]
            statement, exit_code = capture_gate(
                repo=repo,
                policy_path=policy,
                category=args.category,
                security_directory=args.security_dir,
                output=args.output,
                command=command,
                attachments=args.attachment,
                log_attachment=args.log_attachment,
            )
            print(json.dumps(statement, ensure_ascii=False, sort_keys=True))
            return exit_code
        if args.action == "register-production":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = register_production_evidence(
                repo=repo,
                policy_path=policy,
                security_directory=args.security_dir,
                request_path=args.request,
                output=args.output,
            )
        elif args.action == "production-requirements":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = production_evidence_requirements(policy_path=policy, category=args.category)
            if args.output is not None:
                _atomic_write(args.output, _canonical_json(result))
        elif args.action == "prepare-production-handoff":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = prepare_production_evidence_handoff(
                repo=repo,
                policy_path=policy,
                output=args.output,
                signing_key_path=args.signing_key,
                signing_key_id=args.signing_key_id,
            )
        elif args.action == "verify-production-handoff":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = verify_production_evidence_handoff(
                repo=repo,
                policy_path=policy,
                handoff=args.handoff,
                trusted_public_key=args.trusted_public_key,
            )
        elif args.action == "verify-production-handoff-offline":
            result = verify_production_evidence_handoff_offline(
                handoff=args.handoff,
                trusted_public_key=args.trusted_public_key,
            )
        elif args.action == "register-production-batch":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = register_production_evidence_batch(
                repo=repo,
                policy_path=policy,
                security_directory=args.security_dir,
                manifest_path=args.manifest,
                output=args.output,
            )
        elif args.action == "assemble":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = assemble_bundle(
                repo=repo,
                policy_path=policy,
                level_name=args.level,
                security_directory=args.security_dir,
                statements=collect_release_statements(args.statement, args.statement_dir),
                output=args.output,
                release_tag=args.release_tag,
                signing_key_path=args.signing_key,
                signing_key_id=args.signing_key_id,
            )
        elif args.action == "audit":
            repo = args.repo.resolve()
            policy = (args.policy or _default_policy(repo)).resolve()
            result = audit_release(
                repo=repo,
                policy_path=policy,
                level_name=args.level,
                security_directory=args.security_dir,
                statements=collect_release_statements(args.statement, args.statement_dir),
                release_tag=args.release_tag,
            )
            if args.output is not None:
                _atomic_write(args.output, _canonical_json(result))
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0 if result["status"] == "eligible" else 3
        else:
            result = verify_bundle(args.bundle, args.trusted_public_key)
            if args.output is not None:
                _atomic_write(args.output, _canonical_json(result))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except ReleaseEvidenceError as exc:
        print(f"release evidence error: {exc}", file=sys.stderr)
        return 2


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
