SHELL := /bin/bash

.PHONY: install lock lint typecheck test frontend-check operations-contract observability-acceptance browser-acceptance browser-acceptance-edge-current browser-acceptance-edge-previous web-vitals-rum-acceptance reference-visual-pair-verify entry-consistency-acceptance record-consistency-acceptance performance-baseline-acceptance database-acceptance commercial-database-acceptance enterprise-database-acceptance sar-database-acceptance company-timeline-database-acceptance entity-resolution-database-acceptance workspace-preferences-database-acceptance migration-roundtrip source-reproducibility-acceptance ingestion-readiness-acceptance ingestion-acceptance automatic-ingestion-acceptance ingestion-cancellation-acceptance source-version-replay-acceptance source-stage-replay-acceptance quarantine-workflow-acceptance malware-scan-acceptance parser-sandbox-acceptance ocr-acceptance s3-source-acceptance sftp-source-acceptance smb-source-acceptance backup-restore-acceptance mcp-anti-extraction-acceptance mcp-async-task-acceptance kubernetes-acceptance security-check production-topology-live-probe production-evidence-handoff production-evidence-handoff-verify production-evidence-handoff-offline-verify production-evidence-batch release-candidate release-audit release-assemble release-verify check container-backend-check container-frontend-check container-check wsl-tools wsl-edge wsl-check up up-observed down migrate migrate-check rls-verify yaml-check compose-check k8s-render search-ensure search-status search-drain search-rebuild status backup restore-smoke

COMPOSE_BASE = docker compose -f compose.yaml -f compose.dev.yaml
COMPOSE_OBSERVED = $(COMPOSE_BASE) -f compose.telemetry.yaml
COMPOSE_LOCAL = docker compose -f compose.yaml -f compose.dev.yaml
BACKEND_TEST_IMAGE = pharma-intelligence-test:local
FRONTEND_TEST_IMAGE = pharma-intelligence-web-test:local
PNPM = corepack $(shell node -p "require('./apps/web/package.json').packageManager")
PYTHON_TOOL_SCRIPTS = scripts/capture_ingestion_readiness.py scripts/capture_local_release_candidate.py scripts/capture_production_topology.py scripts/entry_consistency_probe.py scripts/mcp_anti_extraction_probe.py scripts/mcp_async_task_probe.py scripts/mcp_contract_fingerprint.py scripts/mcp_inspector_probe.py scripts/mcp_sdk_probe.py scripts/record_consistency_probe.py scripts/reference_visual_pair.py scripts/release_evidence.py scripts/source_tree_manifest.py scripts/validate_yaml.py scripts/verify_clean_source.py scripts/verify_local_ocr.py scripts/verify_postgres_migration_roundtrip.py
YAML_CONFIG_PATHS = compose.yaml compose.dev.yaml compose.telemetry.yaml compose.ocr.yaml deploy/kubernetes
PYTHON_TOOL_SCRIPTS += scripts/configure-development.py

install:
	uv sync --locked --dev
	$(PNPM) --dir apps/web install --frozen-lockfile

.PHONY: configure
configure:
	python3 scripts/configure-development.py

lock:
	uv lock --check

lint:
	uv run ruff format --check src services tests migrations $(PYTHON_TOOL_SCRIPTS)
	uv run ruff check src services tests migrations $(PYTHON_TOOL_SCRIPTS)

typecheck:
	uv run mypy src services tests $(PYTHON_TOOL_SCRIPTS)

test:
	uv run pytest -m "not integration" --cov=pharma_intel --cov-report=term-missing --cov-fail-under=80

frontend-check:
	$(PNPM) --dir apps/web api:check
	$(PNPM) --dir apps/web check
	$(PNPM) --dir apps/web typecheck
	$(PNPM) --dir apps/web test
	$(PNPM) --dir apps/web build

operations-contract:
	uv run pharma-operations-verify

observability-acceptance:
	./scripts/verify-local-observability.sh $(if $(OBSERVABILITY_EVIDENCE),--output "$(OBSERVABILITY_EVIDENCE)")

browser-acceptance:
	./scripts/run-browser-acceptance.sh

browser-acceptance-edge-current:
	./scripts/run-browser-acceptance.sh --browser edge-current

browser-acceptance-edge-previous:
	./scripts/run-browser-acceptance.sh --browser edge-previous

web-vitals-rum-acceptance:
	./scripts/verify-web-vitals-rum.sh $(if $(WEB_VITALS_RUM_EVIDENCE),--output "$(WEB_VITALS_RUM_EVIDENCE)")

reference-visual-pair-verify:
	@test -n "$(REFERENCE_VISUAL_PAIR)" || { echo "REFERENCE_VISUAL_PAIR is required" >&2; exit 2; }
	uv run python scripts/reference_visual_pair.py verify --manifest "$(REFERENCE_VISUAL_PAIR)" $(if $(REFERENCE_VISUAL_IMAGE),--reference-image "$(REFERENCE_VISUAL_IMAGE)")

entry-consistency-acceptance:
	./scripts/verify-entry-consistency.sh $(if $(ENTRY_CONSISTENCY_EVIDENCE),--output "$(ENTRY_CONSISTENCY_EVIDENCE)")

record-consistency-acceptance:
	uv run --no-sync python scripts/record_consistency_probe.py --output "$(or $(OUTPUT),manifests/runtime/acceptance-smoke/record-consistency-$(shell date -u +%Y%m%dT%H%M%SZ).json)"

performance-baseline-acceptance:
	./scripts/verify-local-performance.sh $(if $(PERFORMANCE_BASELINE_EVIDENCE),--output "$(PERFORMANCE_BASELINE_EVIDENCE)")

database-acceptance:
	./scripts/verify-local-database.sh $(if $(DATABASE_EVIDENCE),--output "$(DATABASE_EVIDENCE)")

commercial-database-acceptance:
	./scripts/verify-commercial-postgres.sh

enterprise-database-acceptance:
	./scripts/verify-enterprise-postgres.sh

sar-database-acceptance:
	./scripts/verify-sar-postgres.sh

company-timeline-database-acceptance:
	./scripts/verify-company-timeline-postgres.sh

entity-resolution-database-acceptance:
	./scripts/verify-entity-resolution-postgres.sh

workspace-preferences-database-acceptance:
	./scripts/verify-workspace-preferences-postgres.sh

migration-roundtrip:
	uv run python scripts/verify_postgres_migration_roundtrip.py

source-reproducibility-acceptance:
	uv run python scripts/verify_clean_source.py $(if $(SOURCE_REPRODUCIBILITY_EVIDENCE),--output "$(SOURCE_REPRODUCIBILITY_EVIDENCE)")

ingestion-readiness-acceptance:
	@test -n "$(INGESTION_READINESS_EVIDENCE)" || (echo "INGESTION_READINESS_EVIDENCE is required" >&2; exit 2)
	uv run python scripts/capture_ingestion_readiness.py --output "$(INGESTION_READINESS_EVIDENCE)"

ingestion-acceptance:
	@test -n "$(INGESTION_SOURCE_ID)" || { echo "INGESTION_SOURCE_ID is required" >&2; exit 2; }
	./scripts/verify-local-ingestion.sh --source-id "$(INGESTION_SOURCE_ID)" $(if $(INGESTION_EVIDENCE),--output "$(INGESTION_EVIDENCE)")

automatic-ingestion-acceptance:
	@test -n "$(INGESTION_SOURCE_ID)" || { echo "INGESTION_SOURCE_ID is required" >&2; exit 2; }
	./scripts/verify-automatic-ingestion.sh --source-id "$(INGESTION_SOURCE_ID)" $(if $(INGESTION_EVIDENCE),--output "$(INGESTION_EVIDENCE)")

ingestion-cancellation-acceptance:
	./scripts/verify-ingestion-cancellation.sh $(if $(INGESTION_CANCELLATION_EVIDENCE),--output "$(INGESTION_CANCELLATION_EVIDENCE)")

source-version-replay-acceptance:
	./scripts/verify-source-version-replay.sh $(if $(SOURCE_VERSION_REPLAY_EVIDENCE),--output "$(SOURCE_VERSION_REPLAY_EVIDENCE)")

source-stage-replay-acceptance:
	./scripts/verify-source-stage-replay.sh $(if $(SOURCE_STAGE_REPLAY_EVIDENCE),--output "$(SOURCE_STAGE_REPLAY_EVIDENCE)")

quarantine-workflow-acceptance:
	./scripts/verify-quarantine-workflow.sh $(if $(QUARANTINE_WORKFLOW_EVIDENCE),--output "$(QUARANTINE_WORKFLOW_EVIDENCE)")

malware-scan-acceptance:
	./scripts/verify-local-malware.sh $(if $(MALWARE_EVIDENCE),--output "$(MALWARE_EVIDENCE)")

parser-sandbox-acceptance:
	./scripts/verify-local-parser.sh $(if $(PARSER_EVIDENCE),--output "$(PARSER_EVIDENCE)")

ocr-acceptance:
	PYTHONPATH=src:. python3 -m scripts.verify_local_ocr $(if $(OCR_EVIDENCE),--output "$(OCR_EVIDENCE)")

s3-source-acceptance:
	./scripts/run-s3-source-acceptance.sh

sftp-source-acceptance:
	./scripts/run-sftp-source-acceptance.sh

smb-source-acceptance:
	./scripts/run-smb-source-acceptance.sh

backup-restore-acceptance:
	./scripts/verify-local-backup-restore.sh $(if $(BACKUP_RESTORE_EVIDENCE),--output "$(BACKUP_RESTORE_EVIDENCE)")

mcp-anti-extraction-acceptance:
	uv run --no-sync python scripts/mcp_anti_extraction_probe.py --output "$(or $(OUTPUT),manifests/runtime/acceptance-smoke/mcp-anti-extraction-$(shell date -u +%Y%m%dT%H%M%SZ).json)"

mcp-async-task-acceptance:
	@test -n "$(MCP_ASYNC_TASK_EVIDENCE)" || { echo "MCP_ASYNC_TASK_EVIDENCE is required" >&2; exit 2; }
	./scripts/verify-mcp-interoperability.sh --async-task-only --output "$(MCP_ASYNC_TASK_EVIDENCE)"

kubernetes-acceptance:
	./scripts/validate-kubernetes.sh $(if $(KUBERNETES_EVIDENCE),--output "$(KUBERNETES_EVIDENCE)")

security-check:
	./scripts/run-security-gates.sh

production-topology-live-probe:
	@test -n "$(PRODUCTION_TOPOLOGY_REPORT)" || { echo "PRODUCTION_TOPOLOGY_REPORT is required" >&2; exit 2; }
	@test -n "$(PRODUCTION_TOPOLOGY_OUTPUT)" || { echo "PRODUCTION_TOPOLOGY_OUTPUT is required" >&2; exit 2; }
	@test -n "$(PRODUCTION_SECURITY_EVIDENCE)" || { echo "PRODUCTION_SECURITY_EVIDENCE is required" >&2; exit 2; }
	@test -n "$(PRODUCTION_ENVIRONMENT_KIND)" || { echo "PRODUCTION_ENVIRONMENT_KIND is required" >&2; exit 2; }
	@test -n "$(PRODUCTION_ENVIRONMENT_ID)" || { echo "PRODUCTION_ENVIRONMENT_ID is required" >&2; exit 2; }
	@test -n "$(PRODUCTION_KUBE_CONTEXT)" || { echo "PRODUCTION_KUBE_CONTEXT is required" >&2; exit 2; }
	uv run python scripts/capture_production_topology.py \
		--security-dir "$(PRODUCTION_SECURITY_EVIDENCE)" \
		--topology-report "$(PRODUCTION_TOPOLOGY_REPORT)" \
		--environment-kind "$(PRODUCTION_ENVIRONMENT_KIND)" \
		--environment-id "$(PRODUCTION_ENVIRONMENT_ID)" \
		--context "$(PRODUCTION_KUBE_CONTEXT)" \
		--namespace "$(or $(PRODUCTION_NAMESPACE),pharma-intelligence)" \
		$(if $(PRODUCTION_CA_FILE),--ca-file "$(PRODUCTION_CA_FILE)") \
		--output "$(PRODUCTION_TOPOLOGY_OUTPUT)"

production-evidence-handoff:
	@test -n "$(PRODUCTION_HANDOFF_OUTPUT)" || { echo "PRODUCTION_HANDOFF_OUTPUT is required" >&2; exit 2; }
	uv run python scripts/release_evidence.py prepare-production-handoff --output "$(PRODUCTION_HANDOFF_OUTPUT)" \
		$(if $(PRODUCTION_HANDOFF_SIGNING_KEY),--signing-key "$(PRODUCTION_HANDOFF_SIGNING_KEY)" --signing-key-id "$(PRODUCTION_HANDOFF_SIGNING_KEY_ID)")

production-evidence-handoff-verify:
	@test -n "$(PRODUCTION_HANDOFF)" || { echo "PRODUCTION_HANDOFF is required" >&2; exit 2; }
	uv run python scripts/release_evidence.py verify-production-handoff --handoff "$(PRODUCTION_HANDOFF)" \
		$(if $(PRODUCTION_HANDOFF_TRUSTED_PUBLIC_KEY),--trusted-public-key "$(PRODUCTION_HANDOFF_TRUSTED_PUBLIC_KEY)")

production-evidence-handoff-offline-verify:
	@test -n "$(PRODUCTION_HANDOFF)" || { echo "PRODUCTION_HANDOFF is required" >&2; exit 2; }
	@test -n "$(PRODUCTION_HANDOFF_TRUSTED_PUBLIC_KEY)" || { echo "PRODUCTION_HANDOFF_TRUSTED_PUBLIC_KEY is required" >&2; exit 2; }
	uv run python scripts/release_evidence.py verify-production-handoff-offline \
		--handoff "$(PRODUCTION_HANDOFF)" \
		--trusted-public-key "$(PRODUCTION_HANDOFF_TRUSTED_PUBLIC_KEY)"

production-evidence-batch:
	@test -n "$(SECURITY_EVIDENCE)" || { echo "SECURITY_EVIDENCE is required" >&2; exit 2; }
	@test -n "$(PRODUCTION_BATCH_MANIFEST)" || { echo "PRODUCTION_BATCH_MANIFEST is required" >&2; exit 2; }
	@test -n "$(PRODUCTION_BATCH_OUTPUT)" || { echo "PRODUCTION_BATCH_OUTPUT is required" >&2; exit 2; }
	uv run python scripts/release_evidence.py register-production-batch \
		--security-dir "$(SECURITY_EVIDENCE)" \
		--manifest "$(PRODUCTION_BATCH_MANIFEST)" \
		--output "$(PRODUCTION_BATCH_OUTPUT)"

release-candidate:
	@test -n "$(SECURITY_EVIDENCE)" || { echo "SECURITY_EVIDENCE is required" >&2; exit 2; }
	uv run python scripts/capture_local_release_candidate.py \
		--security-dir "$(SECURITY_EVIDENCE)" \
		--level "$(or $(RELEASE_LEVEL),development)" $(if $(MCP_TOKEN_FILE),--token-file "$(MCP_TOKEN_FILE)") $(RELEASE_CANDIDATE_ARGS)

release-audit:
	@test -n "$(RELEASE_LEVEL)" || { echo "RELEASE_LEVEL is required" >&2; exit 2; }
	@test -n "$(SECURITY_EVIDENCE)" || { echo "SECURITY_EVIDENCE is required" >&2; exit 2; }
	uv run python scripts/release_evidence.py audit --level "$(RELEASE_LEVEL)" --security-dir "$(SECURITY_EVIDENCE)" $(RELEASE_STATEMENTS) $(foreach directory,$(RELEASE_STATEMENT_DIRS),--statement-dir "$(directory)") $(if $(RELEASE_TAG),--release-tag "$(RELEASE_TAG)")

release-assemble:
	@test -n "$(RELEASE_LEVEL)" || { echo "RELEASE_LEVEL is required" >&2; exit 2; }
	@test -n "$(SECURITY_EVIDENCE)" || { echo "SECURITY_EVIDENCE is required" >&2; exit 2; }
	@test -n "$(RELEASE_OUTPUT)" || { echo "RELEASE_OUTPUT is required" >&2; exit 2; }
	uv run python scripts/release_evidence.py assemble \
		--level "$(RELEASE_LEVEL)" \
		--security-dir "$(SECURITY_EVIDENCE)" \
		--output "$(RELEASE_OUTPUT)" \
		$(RELEASE_STATEMENTS) $(foreach directory,$(RELEASE_STATEMENT_DIRS),--statement-dir "$(directory)") $(if $(RELEASE_TAG),--release-tag "$(RELEASE_TAG)") $(if $(RELEASE_SIGNING_KEY),--signing-key "$(RELEASE_SIGNING_KEY)") $(if $(RELEASE_SIGNING_KEY_ID),--signing-key-id "$(RELEASE_SIGNING_KEY_ID)")

release-verify:
	@test -n "$(RELEASE_BUNDLE)" || { echo "RELEASE_BUNDLE is required" >&2; exit 2; }
	uv run python scripts/release_evidence.py verify "$(RELEASE_BUNDLE)" $(if $(TRUSTED_PUBLIC_KEY),--trusted-public-key "$(TRUSTED_PUBLIC_KEY)")

check: lint typecheck test frontend-check operations-contract compose-check k8s-render

container-backend-check:
	docker build --target test-runner -f deploy/api.Dockerfile -t $(BACKEND_TEST_IMAGE) .
	docker run --rm $(BACKEND_TEST_IMAGE) sh -ec 'uv run --no-sync ruff format --check src tests migrations $(PYTHON_TOOL_SCRIPTS) && uv run --no-sync ruff check src tests migrations $(PYTHON_TOOL_SCRIPTS) && uv run --no-sync mypy src tests $(PYTHON_TOOL_SCRIPTS) && uv run --no-sync pharma-openapi --check && uv run --no-sync pytest -m "not integration" --cov=pharma_intel --cov-report=term-missing --cov-fail-under=80'

container-frontend-check:
	docker build --target web-test -f deploy/api.Dockerfile -t $(FRONTEND_TEST_IMAGE) .
	docker run --rm $(FRONTEND_TEST_IMAGE)

container-check: container-backend-check container-frontend-check compose-check

wsl-tools:
	./scripts/bootstrap-wsl-tools.sh
	./scripts/bootstrap-wsl-chrome.sh

wsl-edge:
	./scripts/bootstrap-wsl-edge.sh --track current
	./scripts/bootstrap-wsl-edge.sh --track previous

wsl-check:
	./scripts/check-wsl.sh

up-observed:
	./scripts/up-local.sh --observed
up:
	./scripts/up-local.sh
down:
	$(COMPOSE_LOCAL) down

migrate:
	$(COMPOSE_LOCAL) run --rm migrate

migrate-check:
	$(COMPOSE_LOCAL) run --rm migrate alembic check

rls-verify:
	$(COMPOSE_LOCAL) exec -T api pharma-verify-rls

yaml-check:
	uv run python scripts/validate_yaml.py $(YAML_CONFIG_PATHS)

compose-check: yaml-check
	docker compose -f compose.yaml config --quiet
	$(COMPOSE_LOCAL) config --quiet

k8s-render: yaml-check
	kubectl kustomize deploy/kubernetes/base > /dev/null

search-ensure:
	$(COMPOSE_LOCAL) exec -T worker pharma-search ensure

search-status:
	$(COMPOSE_LOCAL) exec -T worker pharma-search status

search-drain:
	$(COMPOSE_LOCAL) exec -T worker pharma-search drain --max-batches 1000

search-rebuild:
	$(COMPOSE_LOCAL) run --rm worker pharma-search rebuild

status:
	./scripts/status.sh

backup:
	./scripts/backup-runtime-linux.sh

restore-smoke:
	@test -n "$(BACKUP_DIR)" || { echo "BACKUP_DIR is required" >&2; exit 2; }
	./scripts/restore-smoke-linux.sh "$(BACKUP_DIR)"
