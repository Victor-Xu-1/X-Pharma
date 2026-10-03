from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.core import SHA256_PATTERN
from scripts.release.contracts.platform import (
    KUBERNETES_CLAMAV_HA_FIELDS,
    KUBERNETES_CLUSTER_TOPOLOGY_FIELDS,
    KUBERNETES_DOWNLOAD_FIELDS,
    KUBERNETES_DOWNLOADS,
    KUBERNETES_VALIDATION_FIELDS,
    KUBERNETES_VALIDATION_REPORT,
    KUBERNETES_VALIDATION_SCHEMA,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


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
