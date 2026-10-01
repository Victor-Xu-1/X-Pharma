from __future__ import annotations

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
