from __future__ import annotations

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
