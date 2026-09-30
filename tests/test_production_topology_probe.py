from __future__ import annotations

import json
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from scripts import capture_production_topology as topology_probe

SUBJECT: dict[str, Any] = {
    "git_commit": "a" * 40,
    "source_file_count": 700,
    "source_tree_sha256": "b" * 64,
    "targets": {
        "api": "registry.example/pharma-api@sha256:" + "c" * 64,
        "ocr": "registry.example/pharma-ocr@sha256:" + "d" * 64,
    },
}


def _topology() -> dict[str, Any]:
    return {
        "schema": "pharma.production-topology-evidence.v1",
        "schema_version": 1,
        "status": "passed",
        "environment_kind": "preproduction",
        "environment_id": "preprod-cn-east-1",
        "tested_at": datetime.now(UTC).isoformat(),
        "subject": SUBJECT,
        "components": {"kubernetes": {"version": "1.34.1"}},
        "entrypoints": {
            "web_url": "https://workspace.pharma.example.net/workspace/research",
            "mcp_url": "https://mcp.pharma.example.net/mcp",
        },
    }


def _deployment(name: str) -> dict[str, Any]:
    desired = topology_probe.REQUIRED_WORKLOADS[name][0]
    image = SUBJECT["targets"]["ocr" if name == "pharma-ocr" else "api"]
    return {
        "metadata": {"name": name, "generation": 4},
        "spec": {
            "replicas": desired,
            "template": {"spec": {"containers": [{"name": "application", "image": image}]}},
        },
        "status": {
            "readyReplicas": desired,
            "availableReplicas": desired,
            "observedGeneration": 4,
        },
    }


def _node(name: str, zone: str) -> dict[str, Any]:
    return {
        "metadata": {
            "name": name,
            "labels": {"topology.kubernetes.io/zone": zone, "kubernetes.io/arch": "amd64"},
        },
        "spec": {},
        "status": {"conditions": [{"type": "Ready", "status": "True"}]},
    }


def _documents() -> dict[str, dict[str, Any]]:
    hpa_names = [name for name, (_, required) in topology_probe.REQUIRED_WORKLOADS.items() if required]
    return {
        "context": {"current-context": "customer-preprod"},
        "version": {"serverVersion": {"gitVersion": "v1.34.1"}},
        "namespace": {"metadata": {"uid": "11111111-1111-4111-8111-111111111111"}},
        "nodes": {
            "items": [
                _node("node-a", "cn-east-1a"),
                _node("node-b", "cn-east-1b"),
                _node("node-c", "cn-east-1a"),
            ]
        },
        "deployments": {"items": [_deployment(name) for name in topology_probe.REQUIRED_WORKLOADS]},
        "hpas": {
            "items": [{"spec": {"scaleTargetRef": {"name": name}}} for name in hpa_names],
        },
        "pdbs": {"items": [{"metadata": {"name": name}} for name in topology_probe.REQUIRED_WORKLOADS]},
        "policies": {
            "items": [
                {"spec": {"podSelector": {}, "policyTypes": ["Ingress", "Egress"]}},
                *({"spec": {"podSelector": {"matchLabels": {"ordinal": str(index)}}}} for index in range(7)),
            ]
        },
        "gateway": {
            "spec": {
                "listeners": [
                    {"hostname": "workspace.pharma.example.net", "protocol": "HTTPS"},
                    {"hostname": "mcp.pharma.example.net", "protocol": "HTTPS"},
                ]
            },
            "status": {"conditions": [{"type": "Programmed", "status": "True"}]},
        },
        "routes": {
            "items": [
                {"spec": {"hostnames": ["workspace.pharma.example.net"]}},
                {"spec": {"hostnames": ["mcp.pharma.example.net"]}},
            ]
        },
    }


def _install_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    mutate: str | None = None,
) -> Path:
    documents = _documents()
    if mutate == "single_zone":
        for node in documents["nodes"]["items"]:
            node["metadata"]["labels"]["topology.kubernetes.io/zone"] = "cn-east-1a"
    elif mutate == "mutable_image":
        documents["deployments"]["items"][0]["spec"]["template"]["spec"]["containers"][0]["image"] = (
            "registry.example/pharma-api:latest"
        )
    elif mutate == "ocr_wrong_image":
        ocr = next(item for item in documents["deployments"]["items"] if item["metadata"]["name"] == "pharma-ocr")
        ocr["spec"]["template"]["spec"]["containers"][0]["image"] = SUBJECT["targets"]["api"]
    elif mutate == "missing_pdb":
        documents["pdbs"]["items"].pop()
    elif mutate == "gateway_not_programmed":
        documents["gateway"]["status"]["conditions"][0]["status"] = "False"
    elif mutate == "malformed_template":
        documents["deployments"]["items"][0]["spec"]["template"] = None
    elif mutate == "malformed_hpa":
        documents["hpas"]["items"][0]["spec"]["scaleTargetRef"] = None
    elif mutate == "malformed_pdb":
        documents["pdbs"]["items"][0]["metadata"] = None
    elif mutate == "malformed_listener":
        documents["gateway"]["spec"]["listeners"] = None
    elif mutate == "malformed_route":
        documents["routes"]["items"][0]["spec"] = None

    def fake_run_json(_kubectl: str, _context: str, arguments: list[str]) -> dict[str, Any]:
        joined = " ".join(arguments)
        if arguments[:2] == ["config", "view"]:
            return documents["context"]
        if arguments == ["version"]:
            return documents["version"]
        if arguments[:2] == ["get", "namespace"]:
            return documents["namespace"]
        if arguments == ["get", "nodes"]:
            return documents["nodes"]
        if arguments[:2] == ["get", "deployments"]:
            return documents["deployments"]
        if "horizontalpodautoscalers" in joined:
            return documents["hpas"]
        if "poddisruptionbudgets" in joined:
            return documents["pdbs"]
        if "networkpolicies" in joined:
            return documents["policies"]
        if arguments[:3] == ["get", "gateway", "pharma-public"]:
            return documents["gateway"]
        if "httproutes" in joined:
            return documents["routes"]
        raise AssertionError(f"unexpected kubectl arguments: {arguments}")

    monkeypatch.setattr(topology_probe, "_run_json", fake_run_json)
    monkeypatch.setattr(topology_probe, "_subject_document", lambda _repo, _security: SUBJECT)
    monkeypatch.setattr(
        topology_probe,
        "_validated_topology",
        lambda *_args, **_kwargs: _topology(),
    )
    monkeypatch.setattr(
        topology_probe,
        "_endpoint_probe",
        lambda url, *, mcp, ca_file: {
            "url": url,
            "status_code": 401 if mcp else 200,
            "tls_version": "TLSv1.3",
            "certificate_sha256": ("e" if mcp else "d") * 64,
            "hsts": True,
            "unauthenticated_rejected": True if mcp else None,
        },
    )
    topology_path = tmp_path / "topology.json"
    topology_path.write_text(json.dumps(_topology()), encoding="utf-8")
    return topology_path


def _collect(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, mutate: str | None = None) -> dict[str, Any]:
    topology_path = _install_runtime(monkeypatch, tmp_path, mutate=mutate)
    return topology_probe.collect_live_probe(
        repo=tmp_path,
        security_directory=tmp_path,
        topology_report=topology_path,
        environment_kind="preproduction",
        environment_id="preprod-cn-east-1",
        context="customer-preprod-cn-east-1",
        namespace="pharma-intelligence",
        kubectl="kubectl",
        ca_file=None,
    )


def test_collect_live_probe_binds_ready_multi_az_runtime_and_two_https_entrypoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report = _collect(monkeypatch, tmp_path)
    schema = json.loads(
        (Path(__file__).parents[1] / "deploy" / "release" / "production-topology-live-probe.schema.json").read_text(
            encoding="utf-8"
        )
    )

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(report)
    assert report["status"] == "passed"
    assert len(report["workloads"]) == len(topology_probe.REQUIRED_WORKLOADS)
    assert report["kubernetes"]["ready_schedulable_nodes"] == 3
    assert report["endpoints"]["mcp"]["unauthenticated_rejected"] is True
    assert report["credentials_recorded"] is False


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("single_zone", "three ready nodes across two availability zones"),
        ("mutable_image", "not fully ready and governed"),
        ("ocr_wrong_image", "not fully ready and governed"),
        ("missing_pdb", "not fully ready and governed"),
        ("gateway_not_programmed", "Gateway is not Programmed"),
        ("malformed_template", "pod template is invalid"),
        ("malformed_hpa", "HPA target inventory is invalid"),
        ("malformed_pdb", "PDB inventory is invalid"),
        ("malformed_listener", "Gateway listener inventory is invalid"),
        ("malformed_route", "HTTPRoute host inventory is invalid"),
    ],
)
def test_collect_live_probe_fails_closed_on_unready_or_ungoverned_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    with pytest.raises(topology_probe.TopologyProbeError, match=message):
        _collect(monkeypatch, tmp_path, mutate=mutation)


@pytest.mark.parametrize("identity", ["local-development", "prod-kind-cluster", "customer-test"])
def test_collect_live_probe_refuses_nonproduction_environment_identity(
    tmp_path: Path,
    identity: str,
) -> None:
    with pytest.raises(topology_probe.TopologyProbeError, match="refuses local"):
        topology_probe.collect_live_probe(
            repo=tmp_path,
            security_directory=tmp_path,
            topology_report=tmp_path / "missing.json",
            environment_kind="preproduction",
            environment_id=identity,
            context=identity,
            namespace="pharma-intelligence",
            kubectl="kubectl",
            ca_file=None,
        )


@pytest.mark.parametrize("mutation", ["non_https", "shared_host", "credentials"])
def test_validated_topology_rejects_unsafe_entrypoints(tmp_path: Path, mutation: str) -> None:
    topology = _topology()
    entrypoints = topology["entrypoints"]
    if mutation == "non_https":
        entrypoints["web_url"] = "http://workspace.pharma.example.net/workspace/research"
    elif mutation == "shared_host":
        entrypoints["mcp_url"] = "https://workspace.pharma.example.net/mcp"
    else:
        entrypoints["mcp_url"] = "https://probe:secret@mcp.pharma.example.net/mcp"
    topology_path = tmp_path / "production-topology-report.json"
    topology_path.write_text(json.dumps(topology), encoding="utf-8")

    with pytest.raises(topology_probe.TopologyProbeError, match="entrypoint|mcp_url|web_url"):
        topology_probe._validated_topology(
            topology_path,
            subject=SUBJECT,
            environment_kind="preproduction",
            environment_id="preprod-cn-east-1",
        )


def test_live_probe_atomic_output_is_private_external_and_non_overwriting(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    output_root = tmp_path / "evidence"
    output_root.mkdir()
    output = output_root / "production-topology-live-probe.json"

    topology_probe._atomic_write(output, b'{"status":"passed"}\n', repo)

    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises((FileExistsError, topology_probe.TopologyProbeError)):
        topology_probe._atomic_write(output, b"{}\n", repo)
    with pytest.raises(topology_probe.TopologyProbeError, match="outside"):
        topology_probe._atomic_write(repo / "production-topology-live-probe.json", b"{}\n", repo)


def test_live_probe_is_packaged_and_exposed_by_make() -> None:
    root = Path(__file__).parents[1]
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    dockerfile = (root / "deploy" / "api.Dockerfile").read_text(encoding="utf-8")

    assert "production-topology-live-probe:" in makefile
    assert "scripts/capture_production_topology.py" in makefile
    assert "capture_production_topology.py" in dockerfile
