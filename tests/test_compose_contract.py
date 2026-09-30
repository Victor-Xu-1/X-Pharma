from __future__ import annotations

import tomllib
from pathlib import Path

import yaml


def test_runtime_contract_prohibits_local_llm_services_and_overlays() -> None:
    root = Path(__file__).parents[1]
    compose = yaml.safe_load((root / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert not (root / "compose.model.yaml").exists()
    assert not (root / "scripts/configure_local_model.py").exists()
    assert "model-gateway" not in services
    for service in services.values():
        image = str(service.get("image", "")).casefold()
        assert "vllm" not in image
        assert "ollama" not in image


def test_postgres_checkpoint_policy_is_explicit_and_overridable() -> None:
    root = Path(__file__).parents[1]
    runtime = yaml.safe_load((root / "compose.yaml").read_text(encoding="utf-8"))["services"]["postgres"]
    development = yaml.safe_load((root / "compose.dev.yaml").read_text(encoding="utf-8"))["services"]["postgres"]

    assert runtime["command"] == [
        "postgres",
        "-c",
        "checkpoint_timeout=${POSTGRES_CHECKPOINT_TIMEOUT:-15min}",
        "-c",
        "max_wal_size=${POSTGRES_MAX_WAL_SIZE:-4GB}",
        "-c",
        "checkpoint_completion_target=${POSTGRES_CHECKPOINT_COMPLETION_TARGET:-0.9}",
    ]
    assert development["command"] == [
        "postgres",
        "-c",
        "checkpoint_timeout=${POSTGRES_ACCEPTANCE_CHECKPOINT_TIMEOUT:-30min}",
        "-c",
        "max_wal_size=${POSTGRES_ACCEPTANCE_MAX_WAL_SIZE:-4GB}",
        "-c",
        "checkpoint_completion_target=${POSTGRES_CHECKPOINT_COMPLETION_TARGET:-0.9}",
    ]


def test_python_dependency_contract_prohibits_local_inference_runtimes() -> None:
    root = Path(__file__).parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    prohibited = {
        "ctransformers",
        "llama-cpp-python",
        "ollama",
        "sentence-transformers",
        "torch",
        "transformers",
        "vllm",
    }

    direct_dependencies = {
        dependency.split("[", 1)[0].split("=", 1)[0].casefold() for dependency in project["project"]["dependencies"]
    }
    locked_packages = {package["name"].casefold() for package in lock["package"]}

    assert prohibited.isdisjoint(direct_dependencies)
    assert prohibited.isdisjoint(locked_packages)


def test_application_processes_share_one_immutable_build_contract() -> None:
    compose_path = Path(__file__).parents[1] / "compose.yaml"
    document = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    application_services = (
        "migrate",
        "api",
        "worker",
        "parser",
    )
    services = document["services"]
    image_names = {services[name]["image"] for name in application_services}
    build_contracts = {
        (services[name]["build"]["context"], services[name]["build"]["dockerfile"]) for name in application_services
    }

    assert image_names == {"pharma-intelligence-api:${APP_IMAGE_TAG:-latest}"}
    assert build_contracts == {(".", "deploy/api.Dockerfile")}

    continuous = {
        name
        for name, service in services.items()
        if service.get("image") == "pharma-intelligence-api:${APP_IMAGE_TAG:-latest}"
        and service.get("restart") == "unless-stopped"
    }
    assert continuous == {"api", "worker", "parser"}


def test_telemetry_overlay_does_not_resurrect_retired_application_services() -> None:
    root = Path(__file__).parents[1]
    services = yaml.safe_load((root / "compose.telemetry.yaml").read_text(encoding="utf-8"))["services"]

    assert set(services) == {"otel-collector", "api", "worker"}


def test_telemetry_overlay_uses_baked_config_for_wsl_compatibility() -> None:
    root = Path(__file__).parents[1]
    collector = yaml.safe_load((root / "compose.telemetry.yaml").read_text(encoding="utf-8"))["services"][
        "otel-collector"
    ]

    assert collector["command"] == ["--config=/etc/otelcol-contrib/collector.dev.yaml"]
    assert collector["image"] == "pharma-intelligence-otel:dev"
    assert collector["build"]["dockerfile"] == "deploy/otel/Dockerfile"
    assert "volumes" not in collector


def test_local_telemetry_debug_exporters_write_directly_to_container_stdout() -> None:
    root = Path(__file__).parents[1]
    config = yaml.safe_load((root / "deploy" / "otel" / "collector.dev.yaml").read_text(encoding="utf-8"))

    exporters = config["exporters"]
    for name in ("debug/traces", "debug/operational_metrics"):
        assert exporters[name]["use_internal_logger"] is False
        assert exporters[name]["output_paths"] == ["stdout"]


def test_local_startup_removes_retired_service_containers_without_deleting_volumes() -> None:
    source = (Path(__file__).parents[1] / "scripts/up-local.sh").read_text(encoding="utf-8")

    assert "up -d --no-build --remove-orphans" in source
    assert "down -v" not in source


def test_isolated_mcp_acceptance_probes_use_the_unified_gateway_process() -> None:
    root = Path(__file__).parents[1]
    for path in (
        root / "scripts/mcp_anti_extraction_probe.py",
        root / "scripts/mcp_async_task_probe.py",
        root / "scripts/record_consistency_probe.py",
    ):
        source = path.read_text(encoding="utf-8")
        assert '_start_service("pharma-gateway"' in source
        assert '_start_service("pharma-mcp"' not in source
    anti_extraction = (root / "scripts/mcp_anti_extraction_probe.py").read_text(encoding="utf-8")
    assert 'for service in ("postgres", "api")' in anti_extraction


def test_application_image_system_package_downloads_are_pinned_and_bounded() -> None:
    dockerfile = Path(__file__).parents[1] / "deploy/api.Dockerfile"
    source = dockerfile.read_text(encoding="utf-8")

    assert "git=1:2.47.3-0+deb13u1" in source
    assert source.count("Acquire::Retries=3") >= 2
    assert source.count("Acquire::http::Timeout=30") >= 2
    assert source.count("Acquire::https::Timeout=30") >= 2
    assert "--mount=type=cache,target=/var/cache/apt,sharing=locked" in source
    assert "--mount=type=cache,target=/var/lib/apt/lists,sharing=locked" in source
    assert source.count("timeout --foreground --signal=TERM --kill-after=15s 600s") == 2


def test_backend_test_image_contains_every_repository_contract_used_by_tests() -> None:
    root = Path(__file__).parents[1]
    source = (root / "deploy/api.Dockerfile").read_text(encoding="utf-8")
    dockerignore = (root / ".dockerignore").read_text(encoding="utf-8")

    for copy_contract in (
        "COPY apps/web ./apps/web",
        "COPY compose.telemetry.yaml ./",
        "COPY deploy/postgres-rdkit.Dockerfile ./deploy/postgres-rdkit.Dockerfile",
        "scripts/validate-kubernetes.sh",
    ):
        assert copy_contract in source
    assert "!apps/web/playwright.config.ts" in dockerignore


def test_ingestion_worker_requires_digest_pinned_clamav() -> None:
    compose_path = Path(__file__).parents[1] / "compose.yaml"
    services = yaml.safe_load(compose_path.read_text(encoding="utf-8"))["services"]

    assert services["clamav"]["image"] == (
        "clamav/clamav:1.4@sha256:e7ead98e7e07231b151bce988e0cfb0a3b46e6e7046d9dd44fd838c0df724a03"
    )
    assert services["worker"]["environment"]["MALWARE_SCAN_ENABLED"] == "true"
    assert services["worker"]["environment"]["CLAMAV_HOST"] == "clamav"
    assert services["worker"]["depends_on"]["clamav"]["condition"] == "service_healthy"
    assert services["api"]["environment"]["MALWARE_SCAN_ENABLED"] == "true"
    assert services["api"]["environment"]["CLAMAV_HOST"] == "clamav"
    assert services["api"]["environment"]["TEMPORAL_ENABLED"] == "true"
    assert services["api"]["environment"]["TEMPORAL_ADDRESS"] == "temporal:7233"


def test_ingestion_scheduler_controls_are_explicit_in_the_runtime_contract() -> None:
    compose_path = Path(__file__).parents[1] / "compose.yaml"
    worker = yaml.safe_load(compose_path.read_text(encoding="utf-8"))["services"]["worker"]
    environment = worker["environment"]

    assert environment["TEMPORAL_ENABLED"] == "true"
    assert environment["TEMPORAL_NAMESPACE"] == "${TEMPORAL_NAMESPACE:-default}"
    assert environment["TEMPORAL_TASK_QUEUE"] == "${TEMPORAL_TASK_QUEUE:-pharma-data-factory}"
    assert environment["TEMPORAL_WORKER_ENABLED"] == "${TEMPORAL_WORKER_ENABLED:-true}"
    assert environment["TEMPORAL_SCHEDULER_ENABLED"] == "${TEMPORAL_SCHEDULER_ENABLED:-true}"
    assert environment["TEMPORAL_SCHEDULER_POLL_SECONDS"] == "${TEMPORAL_SCHEDULER_POLL_SECONDS:-30}"
    assert environment["TEMPORAL_MAX_CONCURRENT_ACTIVITIES"] == "${TEMPORAL_MAX_CONCURRENT_ACTIVITIES:-20}"


def test_parser_service_is_internal_resource_bounded_and_secret_minimized() -> None:
    compose_path = Path(__file__).parents[1] / "compose.yaml"
    document = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = document["services"]
    parser = services["parser"]
    worker = services["worker"]

    assert document["networks"]["parser-sandbox"]["internal"] is True
    assert parser["networks"] == ["parser-sandbox"]
    assert worker["networks"] == ["default", "parser-sandbox"]
    assert "env_file" not in parser
    assert set(parser["environment"]) == {
        "PARSER_SERVICE_HOST",
        "PARSER_SERVICE_PORT",
        "PARSER_SERVICE_TOKEN",
        "PARSER_SERVICE_MAX_FILE_BYTES",
        "PARSER_SERVICE_MAX_TEXT_CHARS",
        "PARSER_SERVICE_PARSER_TIMEOUT_SECONDS",
        "PARSER_SERVICE_PARSER_CPU_SECONDS",
        "PARSER_SERVICE_PARSER_MEMORY_BYTES",
        "PARSER_SERVICE_MAX_CONCURRENT_PARSES",
        "PARSER_SERVICE_CAPACITY_WAIT_SECONDS",
        "PARSER_SERVICE_LIMIT_CONCURRENCY",
    }
    assert parser["read_only"] is True
    assert parser["pids_limit"] == 64
    assert parser["cap_drop"] == ["ALL"]
    assert worker["environment"]["PARSER_BACKEND"] == "service"
    assert worker["environment"]["PARSER_SERVICE_URL"] == "http://parser:8070"
    assert worker["depends_on"]["parser"]["condition"] == "service_healthy"
    assert services["api"]["environment"]["PARSER_BACKEND"] == "service"
    assert services["api"]["environment"]["PARSER_SERVICE_URL"] == "http://parser:8070"


def test_gateway_unifies_human_api_and_mcp_traffic_in_one_process() -> None:
    compose_path = Path(__file__).parents[1] / "compose.yaml"
    services = yaml.safe_load(compose_path.read_text(encoding="utf-8"))["services"]
    gateway = services["api"]

    assert gateway["command"] == ["pharma-gateway"]
    assert gateway["ports"] == [
        "127.0.0.1:${WEB_PORT:-18380}:8080",
        "127.0.0.1:${MCP_PORT:-18390}:8080",
    ]
    assert gateway["environment"]["MCP_PORT"] == "8080"
    assert gateway["environment"]["AGENT_API_BASE_URL"] == "http://127.0.0.1:8080"
    assert gateway["environment"]["PUBLIC_BASE_URL"] == "http://127.0.0.1:${WEB_PORT:-18380}"
    assert gateway["environment"]["MCP_AUTH_ISSUER_URL"] == "http://127.0.0.1:${WEB_PORT:-18380}"
    assert gateway["healthcheck"]["test"] == ["CMD", "pharma-gateway-health"]
    assert "mcp" not in services


def test_background_capabilities_run_in_one_health_checked_jobs_process() -> None:
    compose_path = Path(__file__).parents[1] / "compose.yaml"
    services = yaml.safe_load(compose_path.read_text(encoding="utf-8"))["services"]
    jobs = services["worker"]

    assert jobs["command"] == ["pharma-jobs"]
    assert jobs["healthcheck"]["test"] == ["CMD", "pharma-jobs-health"]
    assert jobs["healthcheck"]["retries"] >= 3
    assert jobs["read_only"] is True
    assert jobs["environment"]["TEMPORAL_WORKER_ENABLED"] == "${TEMPORAL_WORKER_ENABLED:-true}"
    assert jobs["environment"]["TEMPORAL_SCHEDULER_ENABLED"] == "${TEMPORAL_SCHEDULER_ENABLED:-true}"
    assert jobs["environment"]["SEARCH_PROJECTION_ENABLED"] == "true"
    assert (
        jobs["environment"]["SEARCH_ALLOW_NON_AUTHORITATIVE_PROJECTION"]
        == "${SEARCH_ALLOW_NON_AUTHORITATIVE_PROJECTION:-false}"
    )
    assert jobs["environment"]["MONITORING_ENABLED"] == "true"
    assert "PHARMA_RUNTIME_HEARTBEAT_SERVICE" not in jobs["environment"]
    assert {"search-projector", "search-maintenance", "monitoring-worker", "billing-provider"}.isdisjoint(services)


def test_search_operations_target_the_unified_jobs_service() -> None:
    source = (Path(__file__).parents[1] / "Makefile").read_text(encoding="utf-8")

    for command in (
        "$(COMPOSE_LOCAL) exec -T worker pharma-search ensure",
        "$(COMPOSE_LOCAL) exec -T worker pharma-search status",
        "$(COMPOSE_LOCAL) exec -T worker pharma-search drain --max-batches 1000",
        "$(COMPOSE_LOCAL) run --rm worker pharma-search rebuild",
    ):
        assert command in source
    assert "search-projector pharma-search" not in source


def test_optional_ocr_profile_is_private_pinned_bounded_and_secret_minimized() -> None:
    root = Path(__file__).parents[1]
    document = yaml.safe_load((root / "compose.ocr.yaml").read_text(encoding="utf-8"))
    dockerfile = (root / "services/ocr/Dockerfile").read_text(encoding="utf-8")
    ocr = document["services"]["ocr"]
    worker = document["services"]["worker"]

    assert document["networks"]["ocr-sandbox"]["internal"] is True
    assert ocr["networks"] == ["ocr-sandbox"]
    assert ocr["image"] == "pharma-intelligence-ocr:3.5.0-paddle3.3.1"
    assert ocr["build"] == {
        "context": ".",
        "dockerfile": "services/ocr/Dockerfile",
        "args": {
            "DOCKER_LIBRARY_REGISTRY": "${DOCKER_LIBRARY_REGISTRY:-public.ecr.aws/docker/library}",
            "OCR_PYPI_INDEX_URL": "${OCR_PYPI_INDEX_URL:-https://pypi.org/simple}",
        },
    }
    assert "python:3.13.14-slim@sha256:9662417aace5ae7b" in dockerfile
    assert "libgl1 libglib2.0-0t64 libgomp1" in dockerfile
    assert "CPYTHON_HTML_PARSER_COMMIT=7933f4bf7131aa4140750f9404f5de0aa2969ced" in dockerfile
    assert "CPYTHON_TARFILE_COMMIT=9c17bace90f88dfba6d0e2fe23c8e7ae35f83955" in dockerfile
    assert "COPY deploy/cpython/html-parser.py" in dockerfile
    assert "COPY deploy/cpython/tarfile.py" in dockerfile
    assert dockerfile.count("sha256sum --check --strict") == 2
    assert "rm -rf /var/lib/apt/lists/*" in dockerfile
    assert "env_file" not in ocr
    assert "ports" not in ocr
    assert ocr["read_only"] is True
    assert ocr["cap_drop"] == ["ALL"]
    assert ocr["pids_limit"] == 128
    assert ocr["environment"]["OCR_SERVICE_PADDLEOCR_VERSION"] == "3.5.0"
    assert ocr["environment"]["OCR_SERVICE_PADDLEPADDLE_VERSION"] == "3.3.1"
    assert ocr["environment"]["OCR_SERVICE_DETECTION_MODEL_SHA256"] == (
        "ec4f33f2eaedab78202156d61c79e2b81c020d2007a0336aa3777bb44a5a5ad0"
    )
    assert ocr["environment"]["OCR_SERVICE_RECOGNITION_MODEL_SHA256"] == (
        "02369df6f07caf77a9892b0d598b4fa71a831e31b087aa8d727d34ef5cee3a8f"
    )
    assert worker["environment"]["OCR_BACKEND"] == "service"
    assert worker["environment"]["OCR_SERVICE_URL"] == "http://ocr:8071"
    assert worker["depends_on"]["ocr"] == {"condition": "service_healthy"}
    assert worker["networks"] == ["default", "parser-sandbox", "ocr-sandbox"]
