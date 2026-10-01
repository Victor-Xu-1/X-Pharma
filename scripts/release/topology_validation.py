from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from scripts.release.contracts.core import ENVIRONMENT_ID_PATTERN, SHA256_PATTERN, UUID_PATTERN
from scripts.release.contracts.topology import (
    PRODUCTION_TOPOLOGY_COMPONENT_FIELDS,
    PRODUCTION_TOPOLOGY_COMPONENTS,
    PRODUCTION_TOPOLOGY_FIELDS,
    PRODUCTION_TOPOLOGY_HPA_WORKLOADS,
    PRODUCTION_TOPOLOGY_LIVE_FIELDS,
    PRODUCTION_TOPOLOGY_LIVE_REPORT,
    PRODUCTION_TOPOLOGY_LIVE_SCHEMA,
    PRODUCTION_TOPOLOGY_REPORT,
    PRODUCTION_TOPOLOGY_REQUIRED_WORKLOADS,
    PRODUCTION_TOPOLOGY_SCHEMA,
)
from scripts.release.io import _load_json_object, _parse_timestamp, _sha256_file
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


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
