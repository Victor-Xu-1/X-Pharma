from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).parents[1]
BASE = ROOT / "deploy/kubernetes/base"


def _documents(name: str) -> list[dict[str, Any]]:
    return [item for item in yaml.safe_load_all((BASE / name).read_text(encoding="utf-8")) if item]


def _by_name(name: str) -> dict[str, dict[str, Any]]:
    return {item["metadata"]["name"]: item for item in _documents(name)}


def _named_kind(name: str, resource_name: str, kind: str) -> dict[str, Any]:
    return next(item for item in _documents(name) if item["metadata"]["name"] == resource_name and item["kind"] == kind)


def _container(deployment: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], deployment["spec"]["template"]["spec"]["containers"][0])


def _secret_refs(container: dict[str, Any]) -> set[str]:
    return {item["secretRef"]["name"] for item in container.get("envFrom", []) if "secretRef" in item}


def test_kubernetes_base_fails_closed_until_production_values_are_replaced() -> None:
    data = yaml.safe_load((BASE / "config-map.yaml").read_text(encoding="utf-8"))["data"]

    assert data["MCP_TRUSTED_PROXY_CIDRS"] == "REPLACE_WITH_EXACT_TRUSTED_PROXY_CIDRS"
    assert data["MCP_REQUIRE_TOKEN_CONFIRMATION"] == "true"  # noqa: S105
    assert data["MCP_DPOP_REQUIRED"] == "true"
    assert data["DOCUMENT_PROCESSING_CREDENTIALS_REQUIRED"] == "false"
    assert data["PARSER_SERVICE_CA_CERTS"] == "/etc/pharma-parser-server-ca/ca.crt"
    assert data["OCR_SERVICE_CA_CERTS"] == "/etc/pharma-ocr-server-ca/ca.crt"
    assert data["SEARCH_SEMANTIC_ENABLED"] == "true"
    assert data["SEARCH_EMBEDDING_MODEL"] == "REPLACE_WITH_APPROVED_REMOTE_EMBEDDING_MODEL"
    assert data["AI_RESPONSE_FORMAT_MODE"] == "json_schema"
    assert data["JOBS_SUPERVISOR_POLL_SECONDS"] == "0.5"
    assert data["JOBS_SHUTDOWN_TIMEOUT_SECONDS"] == "100"


def test_kubernetes_has_two_business_workloads_and_one_isolated_parsing_line() -> None:
    deployments = _by_name("deployments.yaml")
    parser = _named_kind("parser.yaml", "pharma-parser", "Deployment")
    ocr = _named_kind("ocr.yaml", "pharma-ocr", "Deployment")

    assert set(deployments) == {"pharma-api", "pharma-jobs"}
    assert _container(deployments["pharma-api"])["command"] == ["pharma-gateway"]
    assert _container(deployments["pharma-jobs"])["command"] == ["pharma-jobs"]
    assert _container(parser)["command"] == ["pharma-parser-service"]
    assert _container(ocr)["image"] == "ghcr.io/replace-org/pharma-intelligence-ocr:3.5.0-paddle3.3.1"

    for deployment in (*deployments.values(), parser, ocr):
        pod = deployment["spec"]["template"]["spec"]
        assert pod["automountServiceAccountToken"] is False
        assert _container(deployment)["securityContext"]["readOnlyRootFilesystem"] is True


def test_unified_gateway_serves_web_api_and_remote_mcp_from_one_service() -> None:
    gateway = _by_name("deployments.yaml")["pharma-api"]
    container = _container(gateway)
    environment = {item["name"]: item["value"] for item in container["env"]}

    assert gateway["spec"]["replicas"] == 3
    assert container["command"] == ["pharma-gateway"]
    assert container["ports"] == [{"name": "http", "containerPort": 8080}]
    assert environment == {"MCP_PORT": "8080", "AGENT_API_BASE_URL": "http://127.0.0.1:8080"}
    for probe_name in ("startupProbe", "readinessProbe"):
        assert container[probe_name]["exec"]["command"] == ["pharma-gateway-health"]
    assert container["livenessProbe"]["httpGet"] == {"path": "/health/live", "port": "http"}
    assert set(_by_name("services.yaml")) == {"pharma-api"}

    routes = {item["metadata"]["name"]: item for item in _documents("gateway.yaml") if item["kind"] == "HTTPRoute"}
    assert set(routes) == {"pharma-workspace", "pharma-mcp"}
    for route in routes.values():
        assert route["spec"]["rules"][0]["backendRefs"] == [{"name": "pharma-api", "port": 8080}]


def test_unified_jobs_enables_all_background_roles_with_one_pid_health_contract() -> None:
    jobs = _by_name("deployments.yaml")["pharma-jobs"]
    pod = jobs["spec"]["template"]["spec"]
    container = _container(jobs)
    environment = {item["name"]: item["value"] for item in container["env"]}

    assert jobs["spec"]["replicas"] == 3
    assert container["command"] == ["pharma-jobs"]
    assert environment == {
        "DOCUMENT_PROCESSING_CREDENTIALS_REQUIRED": "true",
        "TEMPORAL_WORKER_ENABLED": "true",
        "TEMPORAL_SCHEDULER_ENABLED": "true",
        "SEARCH_PROJECTION_ENABLED": "true",
        "MONITORING_ENABLED": "true",
        "BILLING_PROVIDER_ENABLED": "true",
        "BILLING_PROVIDER_NAME": "approved-erp",
        "BILLING_PROVIDER_BASE_URL": "https://billing.example.com",
    }
    assert "PHARMA_RUNTIME_HEARTBEAT_SERVICE" not in environment
    for probe_name in ("startupProbe", "readinessProbe", "livenessProbe"):
        assert container[probe_name]["exec"]["command"] == ["pharma-jobs-health"]
    assert _secret_refs(container) == {
        "pharma-platform-secrets",
        "pharma-document-processing-secrets",
        "pharma-embedding-secrets",
        "pharma-opensearch-jobs-secrets",
        "pharma-billing-provider-secrets",
    }
    assert {mount["mountPath"] for mount in container["volumeMounts"]} >= {
        "/sources/enterprise",
        "/data/markdown-wiki",
        "/etc/pharma-parser-server-ca",
        "/etc/pharma-parser-client-tls",
        "/etc/pharma-ocr-server-ca",
        "/etc/pharma-ocr-client-tls",
    }
    assert {volume["name"] for volume in pod["volumes"]} >= {
        "source",
        "compiled-wiki",
        "parser-server-ca",
        "parser-client-tls",
        "ocr-server-ca",
        "ocr-client-tls",
    }


def test_external_secrets_match_unified_process_ownership() -> None:
    external = _by_name("external-secrets.yaml")
    deployments = _by_name("deployments.yaml")
    query = external["pharma-opensearch-query-secrets"]
    jobs_search = external["pharma-opensearch-jobs-secrets"]
    billing = external["pharma-billing-provider-secrets"]

    assert query["spec"]["data"] == [
        {
            "secretKey": "OPENSEARCH_USERNAME",
            "remoteRef": {"key": "production/opensearch/query", "property": "username"},
        },
        {
            "secretKey": "OPENSEARCH_PASSWORD",
            "remoteRef": {"key": "production/opensearch/query", "property": "password"},
        },
    ]
    assert jobs_search["spec"]["data"] == [
        {
            "secretKey": "OPENSEARCH_USERNAME",
            "remoteRef": {"key": "production/opensearch/jobs", "property": "username"},
        },
        {
            "secretKey": "OPENSEARCH_PASSWORD",
            "remoteRef": {"key": "production/opensearch/jobs", "property": "password"},
        },
    ]
    assert billing["spec"]["data"] == [
        {
            "secretKey": "BILLING_PROVIDER_API_TOKEN",
            "remoteRef": {"key": "production/billing-provider", "property": "api_token"},
        }
    ]
    assert "dataFrom" not in billing["spec"]
    assert "template" not in billing["spec"]["target"]
    assert _secret_refs(_container(deployments["pharma-api"])) >= {
        "pharma-opensearch-query-secrets",
        "pharma-embedding-secrets",
    }
    assert _secret_refs(_container(deployments["pharma-jobs"])) >= {
        "pharma-opensearch-jobs-secrets",
        "pharma-embedding-secrets",
        "pharma-billing-provider-secrets",
    }


def test_scaling_and_disruption_contracts_target_only_current_workloads() -> None:
    autoscalers = _by_name("autoscaling.yaml")
    budgets = _by_name("disruption-budgets.yaml")

    assert set(autoscalers) == {"pharma-api", "pharma-jobs", "pharma-parser", "pharma-clamav"}
    assert set(budgets) == {"pharma-api", "pharma-jobs", "pharma-parser", "pharma-clamav", "pharma-ocr"}
    for name in ("pharma-api", "pharma-jobs", "pharma-parser"):
        assert autoscalers[name]["spec"]["scaleTargetRef"] == {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "name": name,
        }
        assert autoscalers[name]["spec"]["minReplicas"] == 3
        assert budgets[name]["spec"]["maxUnavailable"] == 1


def test_network_policies_route_untrusted_documents_only_from_unified_jobs() -> None:
    policies = _by_name("network-policies.yaml")

    assert "allow-mcp-ingress" not in policies
    assert "allow-billing-provider-egress" not in policies
    workspace = policies["allow-workspace-ingress"]
    assert workspace["spec"]["podSelector"] == {"matchLabels": {"app.kubernetes.io/name": "pharma-api"}}
    for name, port in (
        ("allow-clamav-ingress", 3310),
        ("allow-parser-ingress", 8070),
        ("allow-ocr-ingress", 8071),
    ):
        rule = policies[name]["spec"]["ingress"][0]
        assert rule == {
            "from": [{"podSelector": {"matchLabels": {"app.kubernetes.io/name": "pharma-jobs"}}}],
            "ports": [{"protocol": "TCP", "port": port}],
        }
    exclusions = policies["allow-platform-service-egress"]["spec"]["podSelector"]["matchExpressions"]
    assert {
        "key": "app.kubernetes.io/name",
        "operator": "NotIn",
        "values": ["pharma-parser", "pharma-ocr", "pharma-clamav"],
    } in exclusions


def test_clamav_is_private_pinned_and_persistent() -> None:
    resources = _documents("clamav.yaml")
    statefulset = next(item for item in resources if item["kind"] == "StatefulSet")
    container = _container(statefulset)

    assert statefulset["spec"]["replicas"] == 2
    assert statefulset["spec"]["persistentVolumeClaimRetentionPolicy"] == {
        "whenDeleted": "Retain",
        "whenScaled": "Retain",
    }
    assert container["image"] == (
        "clamav/clamav:1.4@sha256:e7ead98e7e07231b151bce988e0cfb0a3b46e6e7046d9dd44fd838c0df724a03"
    )
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert statefulset["spec"]["volumeClaimTemplates"][0]["metadata"]["name"] == "signatures"


def test_parser_is_secret_minimized_and_mtls_isolated() -> None:
    parser = _named_kind("parser.yaml", "pharma-parser", "Deployment")
    pod = parser["spec"]["template"]["spec"]
    container = _container(parser)
    environment = {item["name"]: item for item in container["env"]}

    assert parser["spec"]["replicas"] == 3
    assert "envFrom" not in container
    assert environment["PARSER_SERVICE_TOKEN"]["valueFrom"]["secretKeyRef"] == {
        "name": "pharma-document-processing-secrets",
        "key": "PARSER_SERVICE_TOKEN",
    }
    for probe_name in ("startupProbe", "readinessProbe", "livenessProbe"):
        assert container[probe_name]["tcpSocket"] == {"port": "https"}
    assert {volume["name"] for volume in pod["volumes"]} >= {
        "parser-server-tls",
        "parser-client-ca",
    }


def test_ocr_is_secret_minimized_and_model_pinned() -> None:
    ocr = _named_kind("ocr.yaml", "pharma-ocr", "Deployment")
    container = _container(ocr)
    environment = {item["name"]: item for item in container["env"]}

    assert ocr["spec"]["replicas"] == 3
    assert "envFrom" not in container
    assert environment["OCR_SERVICE_TOKEN"]["valueFrom"]["secretKeyRef"] == {
        "name": "pharma-document-processing-secrets",
        "key": "OCR_SERVICE_TOKEN",
    }
    assert environment["OCR_SERVICE_DETECTION_MODEL_SHA256"]["value"] == (
        "ec4f33f2eaedab78202156d61c79e2b81c020d2007a0336aa3777bb44a5a5ad0"
    )
    assert environment["OCR_SERVICE_RECOGNITION_MODEL_SHA256"]["value"] == (
        "02369df6f07caf77a9892b0d598b4fa71a831e31b087aa8d727d34ef5cee3a8f"
    )
    for probe_name in ("startupProbe", "readinessProbe", "livenessProbe"):
        assert container[probe_name]["tcpSocket"] == {"port": "https"}
