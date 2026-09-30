from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import ssl
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from scripts.release_evidence import repository_subject, validate_security_evidence
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from release_evidence import (  # type: ignore[no-redef,import-not-found]
        repository_subject,
        validate_security_evidence,
    )


SCHEMA = "pharma.production-topology-live-probe.v1"
REQUIRED_WORKLOADS = {
    "pharma-api": (3, True),
    "pharma-jobs": (3, True),
    "pharma-parser": (3, True),
    "pharma-ocr": (3, False),
}
UNSAFE_ENVIRONMENT_TOKENS = {"dev", "development", "docker", "kind", "local", "minikube", "test", "testing"}
SHA256 = re.compile(r"[0-9a-f]{64}")
ENVIRONMENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}")
NAMESPACE = re.compile(r"[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?")


class TopologyProbeError(RuntimeError):
    pass


def _canonical_json(document: object) -> bytes:
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 16 * 1024 * 1024:
        raise TopologyProbeError(f"{label} must be a bounded regular JSON file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TopologyProbeError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise TopologyProbeError(f"{label} must be a JSON object")
    return value


def _run_json(kubectl: str, context: str, arguments: list[str]) -> dict[str, Any]:
    command = [kubectl, "--context", context, "--request-timeout=20s", *arguments, "-o", "json"]
    try:
        completed = subprocess.run(  # noqa: S603 - kubectl path and bounded arguments are explicit operator inputs.
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TopologyProbeError(f"kubectl failed for {' '.join(arguments)}") from exc
    if completed.returncode != 0:
        detail = re.sub(r"\s+", " ", completed.stderr).strip()[:500]
        raise TopologyProbeError(f"kubectl rejected {' '.join(arguments)}: {detail or 'no diagnostic'}")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise TopologyProbeError(f"kubectl returned invalid JSON for {' '.join(arguments)}") from exc
    if not isinstance(value, dict):
        raise TopologyProbeError(f"kubectl returned a non-object for {' '.join(arguments)}")
    return value


def _condition_true(conditions: object, condition_type: str) -> bool:
    return isinstance(conditions, list) and any(
        isinstance(item, dict) and item.get("type") == condition_type and item.get("status") == "True"
        for item in conditions
    )


def _endpoint_probe(url: str, *, mcp: bool, ca_file: Path | None) -> dict[str, Any]:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise TopologyProbeError("production entrypoint must be an HTTPS URL without credentials or fragments")
    context = ssl.create_default_context(cafile=str(ca_file) if ca_file is not None else None)
    connection = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=15, context=context)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    try:
        connection.connect()
        socket = connection.sock
        if socket is None:
            raise TopologyProbeError("HTTPS connection did not expose a verified TLS socket")
        certificate = socket.getpeercert(binary_form=True)
        tls_version = socket.version()
        if not certificate or tls_version not in {"TLSv1.2", "TLSv1.3"}:
            raise TopologyProbeError("entrypoint did not negotiate an approved TLS version")
        if mcp:
            body = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": "production-topology-probe",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "topology-probe", "version": "1"},
                    },
                }
            )
            connection.request(
                "POST",
                path,
                body=body,
                headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
            )
        else:
            connection.request("GET", path, headers={"Accept": "text/html"})
        response = connection.getresponse()
        response.read(64 * 1024)
        status_code = response.status
        hsts = response.getheader("Strict-Transport-Security")
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        raise TopologyProbeError(f"HTTPS entrypoint probe failed: {parsed.hostname}") from exc
    finally:
        connection.close()
    if mcp and status_code not in {401, 403}:
        raise TopologyProbeError("unauthenticated MCP request was not rejected")
    if not mcp and status_code != 200:
        raise TopologyProbeError("human workbench entrypoint did not return HTTP 200")
    if not isinstance(hsts, str) or "max-age=" not in hsts.casefold():
        raise TopologyProbeError("production entrypoint did not return HSTS")
    return {
        "url": url,
        "status_code": status_code,
        "tls_version": tls_version,
        "certificate_sha256": hashlib.sha256(certificate).hexdigest(),
        "hsts": True,
        "unauthenticated_rejected": status_code in {401, 403} if mcp else None,
    }


def _subject_document(repo: Path, security_directory: Path) -> dict[str, Any]:
    subject = repository_subject(repo)
    security = validate_security_evidence(security_directory, subject)
    return {
        "git_commit": subject.commit,
        "source_file_count": subject.source_file_count,
        "source_tree_sha256": subject.source_tree_sha256,
        "targets": security.targets,
    }


def _validated_topology(
    topology_report: Path,
    *,
    subject: dict[str, Any],
    environment_kind: str,
    environment_id: str,
) -> dict[str, Any]:
    topology = _load_json(topology_report, "production topology report")
    if (
        topology.get("schema") != "pharma.production-topology-evidence.v1"
        or topology.get("schema_version") != 1
        or topology.get("status") != "passed"
        or topology.get("environment_kind") != environment_kind
        or topology.get("environment_id") != environment_id
        or topology.get("subject") != subject
    ):
        raise TopologyProbeError("production topology report is not bound to this environment and release subject")
    try:
        tested_at = datetime.fromisoformat(str(topology.get("tested_at")))
    except ValueError as exc:
        raise TopologyProbeError("production topology report tested_at is invalid") from exc
    if tested_at.tzinfo is None or abs(datetime.now(UTC) - tested_at.astimezone(UTC)) > timedelta(hours=24):
        raise TopologyProbeError("production topology report is outside the live-probe execution window")
    components = topology.get("components")
    kubernetes_component = components.get("kubernetes") if isinstance(components, dict) else None
    if not isinstance(kubernetes_component, dict) or not isinstance(kubernetes_component.get("version"), str):
        raise TopologyProbeError("production topology Kubernetes component is invalid")
    entrypoints = topology.get("entrypoints")
    if not isinstance(entrypoints, dict):
        raise TopologyProbeError("production topology entrypoints are invalid")
    hosts: set[str] = set()
    for field in ("web_url", "mcp_url"):
        value = entrypoints.get(field)
        parsed = urlsplit(value) if isinstance(value, str) else urlsplit("")
        if (
            parsed.scheme != "https"
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise TopologyProbeError(f"production topology {field} is invalid")
        hosts.add(parsed.hostname.casefold())
    if len(hosts) != 2:
        raise TopologyProbeError("production topology must declare two distinct HTTPS entrypoints")
    return topology


def _workload_observations(
    deployments: dict[str, Any],
    hpas: dict[str, Any],
    pdbs: dict[str, Any],
    *,
    application_digest: str,
    ocr_digest: str,
) -> list[dict[str, Any]]:
    deployment_items = deployments.get("items")
    if not isinstance(deployment_items, list):
        raise TopologyProbeError("Kubernetes deployment inventory is invalid")
    by_name = {
        item.get("metadata", {}).get("name"): item
        for item in deployment_items
        if isinstance(item, dict) and isinstance(item.get("metadata"), dict)
    }
    hpa_items = hpas.get("items")
    if not isinstance(hpa_items, list):
        raise TopologyProbeError("Kubernetes HPA inventory is invalid")
    hpa_names: set[object] = set()
    for item in hpa_items:
        if not isinstance(item, dict):
            raise TopologyProbeError("Kubernetes HPA inventory is invalid")
        spec = item.get("spec")
        target = spec.get("scaleTargetRef") if isinstance(spec, dict) else None
        if not isinstance(target, dict):
            raise TopologyProbeError("Kubernetes HPA target inventory is invalid")
        hpa_names.add(target.get("name"))
    pdb_items = pdbs.get("items")
    if not isinstance(pdb_items, list):
        raise TopologyProbeError("Kubernetes PDB inventory is invalid")
    pdb_names: set[object] = set()
    for item in pdb_items:
        metadata = item.get("metadata") if isinstance(item, dict) else None
        if not isinstance(metadata, dict):
            raise TopologyProbeError("Kubernetes PDB inventory is invalid")
        pdb_names.add(metadata.get("name"))
    observations: list[dict[str, Any]] = []
    for name, (minimum_replicas, hpa_required) in REQUIRED_WORKLOADS.items():
        expected_digest = ocr_digest if name == "pharma-ocr" else application_digest
        item = by_name.get(name)
        if not isinstance(item, dict):
            raise TopologyProbeError(f"required production workload is missing: {name}")
        metadata, spec, status = item.get("metadata"), item.get("spec"), item.get("status")
        if not isinstance(metadata, dict) or not isinstance(spec, dict) or not isinstance(status, dict):
            raise TopologyProbeError(f"production workload metadata is invalid: {name}")
        desired = spec.get("replicas")
        ready = status.get("readyReplicas", 0)
        available = status.get("availableReplicas", 0)
        generation = metadata.get("generation")
        observed_generation = status.get("observedGeneration")
        template = spec.get("template")
        pod_spec = template.get("spec") if isinstance(template, dict) else None
        containers = pod_spec.get("containers") if isinstance(pod_spec, dict) else None
        if not isinstance(containers, list) or any(not isinstance(container, dict) for container in containers):
            raise TopologyProbeError(f"production workload pod template is invalid: {name}")
        images = [container.get("image") for container in containers]
        if (
            not isinstance(desired, int)
            or isinstance(desired, bool)
            or desired < minimum_replicas
            or ready != desired
            or available != desired
            or not isinstance(generation, int)
            or observed_generation != generation
            or not images
            or any(
                not isinstance(image, str) or re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", image) is None
                for image in images
            )
            or not any(image.endswith(f"@sha256:{expected_digest}") for image in images)
            or name not in pdb_names
            or (hpa_required and name not in hpa_names)
        ):
            raise TopologyProbeError(f"production workload is not fully ready and governed: {name}")
        observations.append(
            {
                "name": name,
                "kind": "Deployment",
                "desired_replicas": desired,
                "ready_replicas": ready,
                "available_replicas": available,
                "generation": generation,
                "observed_generation": observed_generation,
                "image_digests": sorted(images),
                "pdb_present": True,
                "hpa_present": name in hpa_names,
            }
        )
    return observations


def collect_live_probe(
    *,
    repo: Path,
    security_directory: Path,
    topology_report: Path,
    environment_kind: str,
    environment_id: str,
    context: str,
    namespace: str,
    kubectl: str,
    ca_file: Path | None,
) -> dict[str, Any]:
    if environment_kind not in {"preproduction", "production"} or ENVIRONMENT_ID.fullmatch(environment_id) is None:
        raise TopologyProbeError("live probe environment identity is invalid")
    tokens = set(re.split(r"[^a-z0-9]+", f"{environment_id} {context}".casefold()))
    if tokens.intersection(UNSAFE_ENVIRONMENT_TOKENS):
        raise TopologyProbeError("live probe refuses local, development, kind, minikube or test environments")
    if NAMESPACE.fullmatch(namespace) is None:
        raise TopologyProbeError("live probe namespace is invalid")
    repo = repo.resolve(strict=True)
    subject = _subject_document(repo, security_directory.resolve(strict=True))
    topology = _validated_topology(
        topology_report.resolve(strict=True),
        subject=subject,
        environment_kind=environment_kind,
        environment_id=environment_id,
    )
    context_document = _run_json(kubectl, context, ["config", "view", "--minify", "--flatten"])
    version_document = _run_json(kubectl, context, ["version"])
    namespace_document = _run_json(kubectl, context, ["get", "namespace", namespace])
    nodes_document = _run_json(kubectl, context, ["get", "nodes"])
    deployments = _run_json(
        kubectl,
        context,
        ["get", "deployments", "-n", namespace, "-l", "app.kubernetes.io/part-of=pharma-intelligence"],
    )
    hpas = _run_json(kubectl, context, ["get", "horizontalpodautoscalers", "-n", namespace])
    pdbs = _run_json(kubectl, context, ["get", "poddisruptionbudgets", "-n", namespace])
    policies = _run_json(kubectl, context, ["get", "networkpolicies", "-n", namespace])
    gateway = _run_json(kubectl, context, ["get", "gateway", "pharma-public", "-n", namespace])
    routes = _run_json(kubectl, context, ["get", "httproutes", "-n", namespace])

    server_version = version_document.get("serverVersion", {}).get("gitVersion")
    if not isinstance(server_version, str) or re.fullmatch(r"v1\.\d+\.\d+", server_version) is None:
        raise TopologyProbeError("Kubernetes server returned an invalid stable version")
    components = topology.get("components")
    kubernetes_component = components.get("kubernetes") if isinstance(components, dict) else None
    expected_version = kubernetes_component.get("version") if isinstance(kubernetes_component, dict) else None
    if server_version.removeprefix("v") != expected_version:
        raise TopologyProbeError("live Kubernetes version differs from the approved topology")

    node_items = nodes_document.get("items")
    if not isinstance(node_items, list):
        raise TopologyProbeError("Kubernetes node inventory is invalid")
    ready_nodes = []
    zones: set[str] = set()
    architectures: set[str] = set()
    for node in node_items:
        if not isinstance(node, dict):
            continue
        spec, metadata, status = node.get("spec"), node.get("metadata"), node.get("status")
        if (
            not isinstance(spec, dict)
            or not isinstance(metadata, dict)
            or not isinstance(status, dict)
            or spec.get("unschedulable") is True
        ):
            continue
        if not _condition_true(status.get("conditions"), "Ready"):
            continue
        labels = metadata.get("labels")
        if not isinstance(labels, dict):
            continue
        zone = labels.get("topology.kubernetes.io/zone")
        architecture = labels.get("kubernetes.io/arch")
        if isinstance(zone, str) and zone:
            zones.add(zone)
        if isinstance(architecture, str) and architecture:
            architectures.add(architecture)
        ready_nodes.append(node)
    if len(ready_nodes) < 3 or len(zones) < 2 or not architectures:
        raise TopologyProbeError("Kubernetes cluster does not prove three ready nodes across two availability zones")

    namespace_metadata = namespace_document.get("metadata")
    namespace_uid = namespace_metadata.get("uid") if isinstance(namespace_metadata, dict) else None
    if not isinstance(namespace_uid, str) or re.fullmatch(r"[0-9a-f-]{36}", namespace_uid) is None:
        raise TopologyProbeError("Kubernetes namespace UID is invalid")
    targets = subject.get("targets")
    if not isinstance(targets, dict):
        raise TopologyProbeError("release subject does not contain digest-bound image targets")
    image_digests: dict[str, str] = {}
    for target_name in ("api", "ocr"):
        target = targets.get(target_name)
        if not isinstance(target, str) or "@sha256:" not in target:
            raise TopologyProbeError(f"release subject does not contain a digest-bound {target_name} image")
        digest = target.rsplit("@sha256:", maxsplit=1)[1]
        if SHA256.fullmatch(digest) is None:
            raise TopologyProbeError(f"release subject {target_name} image digest is invalid")
        image_digests[target_name] = digest
    workload_observations = _workload_observations(
        deployments,
        hpas,
        pdbs,
        application_digest=image_digests["api"],
        ocr_digest=image_digests["ocr"],
    )

    policy_items = policies.get("items")
    if not isinstance(policy_items, list):
        raise TopologyProbeError("Kubernetes NetworkPolicy inventory is invalid")
    default_deny_ingress = False
    default_deny_egress = False
    for policy in policy_items:
        if not isinstance(policy, dict):
            continue
        spec = policy.get("spec")
        if not isinstance(spec, dict) or spec.get("podSelector") != {}:
            continue
        policy_types = spec.get("policyTypes")
        if isinstance(policy_types, list):
            default_deny_ingress = default_deny_ingress or "Ingress" in policy_types
            default_deny_egress = default_deny_egress or "Egress" in policy_types
    if len(policy_items) < 8 or not default_deny_ingress or not default_deny_egress:
        raise TopologyProbeError("Kubernetes namespace lacks the required default-deny network policy posture")

    gateway_spec, gateway_status = gateway.get("spec"), gateway.get("status")
    if not isinstance(gateway_spec, dict) or not isinstance(gateway_status, dict):
        raise TopologyProbeError("Kubernetes Gateway inventory is invalid")
    if not _condition_true(gateway_status.get("conditions"), "Programmed"):
        raise TopologyProbeError("production Gateway is not Programmed")
    listeners = gateway_spec.get("listeners")
    if not isinstance(listeners, list):
        raise TopologyProbeError("Kubernetes Gateway listener inventory is invalid")
    listener_hosts: set[str] = set()
    for listener in listeners:
        if not isinstance(listener, dict):
            raise TopologyProbeError("Kubernetes Gateway listener inventory is invalid")
        if listener.get("protocol") == "HTTPS" and isinstance(listener.get("hostname"), str):
            listener_hosts.add(listener["hostname"])
    entrypoints = topology.get("entrypoints")
    if not isinstance(entrypoints, dict):
        raise TopologyProbeError("approved topology entrypoints are invalid")
    expected_hosts = {urlsplit(str(entrypoints.get(field))).hostname for field in ("web_url", "mcp_url")}
    if None in expected_hosts or listener_hosts != expected_hosts:
        raise TopologyProbeError("live Gateway HTTPS hosts differ from the approved two-entrypoint topology")
    route_items = routes.get("items")
    if not isinstance(route_items, list):
        raise TopologyProbeError("Kubernetes HTTPRoute inventory is invalid")
    route_hosts: set[str] = set()
    for route in route_items:
        if not isinstance(route, dict):
            raise TopologyProbeError("Kubernetes HTTPRoute inventory is invalid")
        route_spec = route.get("spec")
        hostnames = route_spec.get("hostnames") if isinstance(route_spec, dict) else None
        if not isinstance(hostnames, list) or any(not isinstance(host, str) for host in hostnames):
            raise TopologyProbeError("Kubernetes HTTPRoute host inventory is invalid")
        route_hosts.update(hostnames)
    if route_hosts != expected_hosts:
        raise TopologyProbeError("live HTTPRoute hosts differ from the approved two-entrypoint topology")

    web_probe = _endpoint_probe(str(entrypoints["web_url"]), mcp=False, ca_file=ca_file)
    mcp_probe = _endpoint_probe(str(entrypoints["mcp_url"]), mcp=True, ca_file=ca_file)
    return {
        "schema": SCHEMA,
        "schema_version": 1,
        "status": "passed",
        "environment_kind": environment_kind,
        "environment_id": environment_id,
        "tested_at": datetime.now(UTC).isoformat(),
        "subject": subject,
        "topology_report_sha256": _sha256_file(topology_report),
        "kube_context_sha256": hashlib.sha256(_canonical_json(context_document)).hexdigest(),
        "namespace": namespace,
        "namespace_uid": namespace_uid,
        "kubernetes": {
            "server_version": server_version.removeprefix("v"),
            "ready_schedulable_nodes": len(ready_nodes),
            "availability_zones": sorted(zones),
            "node_architectures": sorted(architectures),
        },
        "workloads": workload_observations,
        "gateway": {
            "name": "pharma-public",
            "programmed": True,
            "listener_hosts": sorted(listener_hosts),
            "route_hosts": sorted(route_hosts),
        },
        "network_policy": {
            "count": len(policy_items),
            "default_deny_ingress": default_deny_ingress,
            "default_deny_egress": default_deny_egress,
        },
        "endpoints": {"web": web_probe, "mcp": mcp_probe},
        "credentials_recorded": False,
    }


def _atomic_write(output: Path, payload: bytes, repo: Path) -> None:
    if output.name != "production-topology-live-probe.json":
        raise TopologyProbeError("live probe output filename must be production-topology-live-probe.json")
    parent = output.parent.resolve(strict=True)
    destination = parent / output.name
    resolved_repo = repo.resolve(strict=True)
    if parent == resolved_repo or resolved_repo in parent.parents or destination.exists() or destination.is_symlink():
        raise TopologyProbeError("live probe output must be a new file outside the source repository")
    temporary = parent / f".{output.name}.{os.getpid()}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, destination, follow_symlinks=False)
        directory_descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture fail-closed live production topology evidence")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--security-dir", type=Path, required=True)
    parser.add_argument("--topology-report", type=Path, required=True)
    parser.add_argument("--environment-kind", choices=("preproduction", "production"), required=True)
    parser.add_argument("--environment-id", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--namespace", default="pharma-intelligence")
    parser.add_argument("--kubectl", default="kubectl")
    parser.add_argument("--ca-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(arguments: list[str] | None = None) -> int:
    args = _build_parser().parse_args(arguments)
    try:
        report = collect_live_probe(
            repo=args.repo,
            security_directory=args.security_dir,
            topology_report=args.topology_report,
            environment_kind=args.environment_kind,
            environment_id=args.environment_id,
            context=args.context,
            namespace=args.namespace,
            kubectl=args.kubectl,
            ca_file=args.ca_file,
        )
        payload = (json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
        _atomic_write(args.output, payload, args.repo)
    except (OSError, TopologyProbeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
