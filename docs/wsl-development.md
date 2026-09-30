# WSL development and local operations

## Canonical location

The canonical local checkout is a Linux-native WSL path owned by the current
WSL user:

```text
/srv/wsl/projects/x-pharma
```

Do not develop from a mirrored Windows path or a `/mnt/c` checkout. Windows Explorer may open the same files through the WSL network share, but tools, Git, Docker builds and tests run from WSL.

Docker Desktop may provide the engine through WSL integration. The required invariant is that Docker reports a Linux engine with `overlayfs`, while the repository remains on the Ubuntu ext4 filesystem.

## First setup

Local backups and acceptance evidence are runtime state, not source. After moving the checkout into WSL, preview and then relocate them to a Linux-native directory outside the repository. The command refuses existing targets, preserves all content and leaves ignored links at the conventional paths:

```bash
export PHARMA_REPO="${PHARMA_REPO:-/srv/wsl/projects/x-pharma}"
export PHARMA_RUNTIME_ROOT="${PHARMA_RUNTIME_ROOT:-/srv/wsl/data/x-pharma-runtime}"

pharma-runtime-layout \
  --repository "$PHARMA_REPO" \
  --storage-root "$PHARMA_RUNTIME_ROOT"

pharma-runtime-layout \
  --repository "$PHARMA_REPO" \
  --storage-root "$PHARMA_RUNTIME_ROOT" \
  --apply
```

The runtime root is mode `0700`; its `runtime-layout.json` inventory is mode `0600`. A clean clone does not depend on these workstation links and recreates empty runtime paths when needed.

```bash
cd "/srv/wsl/projects/x-pharma"
cp .env.example .env
chmod 600 .env
mkdir -p data/sources/empty
```

Replace every `replace-*` value in `.env` with a different cryptographically random secret. Keep production secrets in a secret manager; never copy the development `.env` into Kubernetes.

`POSTGRES_RUNTIME_USER`, `POSTGRES_RUNTIME_PASSWORD` and `RUNTIME_DATABASE_URL` are mandatory. Compose has no runtime-database credential fallback: a missing or placeholder value blocks rendering before any service starts. The URL must use the same runtime user, password and database configured elsewhere in `.env`.

The WSL preflight also requires independent values of at least 32 bytes for human sessions, internal service tokens, tenant-context signing, API-key hashing, MCP cursors, billing statements, export manifests and the parser service. Reusing one secret across these trust boundaries is rejected.

Install the project-pinned Linux `kubectl` into the persistent WSL user path, then validate the host boundary. Do not depend on a Windows `.exe` injected by Docker Desktop:

```bash
make wsl-tools
make wsl-check
```

## Start and inspect

```bash
make up-observed
make status
```

`make up` and `make up-observed` call `scripts/up-local.sh`: it holds a single-instance lock, builds PostgreSQL/RDKit only when that image is absent, builds the shared application image exactly once, and then runs Compose with `--no-build`. Each phase has a bounded timeout, so Compose cannot fan out duplicate BuildKit jobs and leave an unbounded background build after a client timeout. Set `FORCE_POSTGRES_BUILD=true` only when intentionally rebuilding the PostgreSQL/RDKit base image.

PostgreSQL checkpoint policy is explicit in Compose rather than relying on image defaults. The base runtime uses `POSTGRES_CHECKPOINT_TIMEOUT` (default `15min`), `POSTGRES_MAX_WAL_SIZE` (default `4GB`) and `POSTGRES_CHECKPOINT_COMPLETION_TARGET` (default `0.9`); production operators must tune these against storage latency, WAL capacity, replica lag and recovery objectives. `compose.dev.yaml` uses the isolated acceptance defaults `30min` and `4GB` so local WSL disk checkpoints do not masquerade as application query failures. These settings do not change the database volume or bypass durability.

AI governance has no local inference profile. Configure an approved third-party OpenAI-compatible HTTPS API in the ignored `.env` with `AI_GOVERNANCE_ENABLED=true`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`, and `AI_ALLOWED_RESPONSE_MODELS_JSON`. The application rejects HTTP, loopback, localhost, embedded URL credentials, query strings, and fragments. Provider credentials must remain outside Git and should be materialized by a secret manager outside development.

Migration, API, worker, parser, projector and MCP all run the exact same application image. `APP_IMAGE_TAG` defaults to `latest` for local development; release automation should set it to an immutable version or commit tag. Do not give these processes separate local images, because that permits schema/code drift. Parser has a separate process/network/security boundary despite sharing the immutable artifact.

The only public local entry points are:

- Human workbench: `http://127.0.0.1:18380/`
- Agent MCP: `http://127.0.0.1:18390/mcp`

PostgreSQL and OpenSearch development ports bind to loopback only. Temporal, Valkey and OpenTelemetry have no public host port.

## Read-only Windows source folders

WSL exposes a mounted Windows `Y:` drive as `/mnt/y` when the drive is connected. Configure:

```dotenv
KNOWLEDGE_SOURCE_ROOT=/mnt/y
SOURCE_ROOTS=/sources/knowledge
```

Compose mounts this root at `/sources/knowledge:ro`. Register only approved subdirectories as data sources. A disconnected drive marks a source unavailable; it must not remove snapshots or canonical records.

For higher ingestion throughput and stronger failure isolation, register the enterprise share with `smb-snapshot-v1` instead of relying on a workstation drive mount. Keep the connector account read-only, require SMB3 encryption, and use S3-compatible object storage only for the platform's immutable snapshots.

## Recover an unresponsive WSL development runtime

Treat a command such as `wsl -l -v` timing out as a Windows WSL service failure, not as an application health failure. First request a normal Docker Desktop quit and wait for it to finish. If Docker reports that it cannot communicate with WSL and both `wsl --shutdown` and distro commands still time out, use an elevated Windows PowerShell only after accepting that in-flight development writes may be interrupted:

```powershell
Restart-Service WslService -Force
```

If the service cannot be restarted cleanly, reboot Windows. Do not use Docker Desktop factory reset, `wsl --unregister`, delete an ext4 VHDX, or run `docker compose down -v`; those actions destroy recoverable runtime state and are not troubleshooting steps.

After WSL returns, verify the substrate before starting the application:

```powershell
wsl -l -v
wsl -d Ubuntu -- bash -lc 'printf "wsl=ready\n"'
```

Then start Docker Desktop and verify from Ubuntu:

```bash
docker info
docker volume ls --format '{{.Name}}' | sort
docker compose -f compose.yaml -f compose.dev.yaml -f compose.telemetry.yaml ps
make up-observed
```

`make up-observed` is idempotent and reuses the existing named database and object-store volumes. Before resuming acceptance, require all Compose health checks to pass and confirm that PostgreSQL migrations, object evidence and the registered data-source inventory are still present. A successful restart is not evidence that an interrupted ingestion or remote model call completed; rerun the bounded acceptance for a new immutable source version.

## Reproducible quality gates

The host path does not need a separately installed Python 3.13 for the main local gate:

```bash
make container-check
```

This builds locked `test-runner` and `web-test` stages from `deploy/api.Dockerfile`, then runs Ruff, strict mypy, OpenAPI drift, backend tests with the coverage gate, Biome, TypeScript, Vitest and the frontend production build.

The backend owns `docs/openapi.json`. The committed TypeScript client under `apps/web/src/lib/generated` is reproducible output, not a second hand-written contract. After an intentional API change, regenerate and verify it from WSL:

```bash
pnpm --dir apps/web api:generate
pnpm --dir apps/web api:check
```

`make frontend-check`, the frontend CI job and the `web-test` container all run the drift check. Business components import stable wrappers from `apps/web/src/lib/contracts`; they do not call verbose generated service methods directly or duplicate response DTOs.

Tests that require real PostgreSQL/RDKit, OpenSearch, MCP or a browser use the running Compose services and dedicated acceptance commands. Container-only unit gates do not replace those integration tests.

Run the untrusted-document boundary and the full ClamAV-to-parser Data Factory chain separately:

```bash
make parser-sandbox-acceptance PARSER_EVIDENCE=manifests/runtime/acceptance-smoke/parser.json
make malware-scan-acceptance MALWARE_EVIDENCE=manifests/runtime/acceptance-smoke/malware-parser.json
```

The parser acceptance also launches a real ephemeral Uvicorn mTLS service and proves that missing client certificates, a rogue client CA and an untrusted server CA are all rejected. It saturates the live Compose parser with a held request, verifies a concurrent request receives bounded `429` backpressure, then proves service recovery; inside the parser container it forces a sandbox wall-clock timeout, verifies the child process group is gone and parses a subsequent document successfully. Generated keys remain in a private temporary directory and are destroyed by the probe.

Before assembling any release candidate, prove the repository has no hidden local dependency:

```bash
make source-reproducibility-acceptance \
  SOURCE_REPRODUCIBILITY_EVIDENCE=manifests/runtime/acceptance-smoke/source-reproducibility.json
```

This exports only committed `HEAD` files into a private temporary tree and runs locked installation, all host quality gates, migration upgrade/downgrade, the final application image build and a non-root network-isolated image smoke test. It never copies the current `.env`, virtual environment, Node modules, caches or ignored files.

PostgreSQL integration-test URLs are guarded before the first connection. Their database name must explicitly contain `test`, `testing`, `integration`, `ci` or `migration`; remote hosts additionally require `TEST_REMOTE_DATABASE_CONFIRMATION=<host>/<database>`. Never point `TEST_DATABASE_URL`, `TEST_CHEMISTRY_*`, `TEST_COMMERCIAL_DATABASE_URL` or `TEST_DB_PROVISION_DATABASE_URL` at the long-lived Compose database. CI creates disposable databases or destroys the whole service after the job.

## Runtime data and secrets

- PostgreSQL, object-store, Markdown and OpenSearch runtime data live in Docker volumes.
- Versioned backups live under `backups/` locally or an approved external backup target; `backups/` is excluded from Git and Docker build contexts.
- The local commercial MCP key is stored outside the repository at `$HOME/.config/pharma-intelligence/agent-gateway.key` with directory mode `0700` and file mode `0600`.
- Never print, commit, archive with source, or place that key in `.env`.

## Backup and restore

Create an atomic local backup and prove it can be restored without touching the
running project:

```bash
make backup
make restore-smoke BACKUP_DIR=backups/runtime-YYYYMMDD-HHMMSS
```

The backup covers the business database, PostgreSQL roles, both Temporal
databases, object evidence and Markdown. The smoke drill validates checksums,
exact table inventory and row counts, Alembic revision, RDKit, RLS and archive
extraction in isolated temporary volumes.

Restore a retained backup only into a clean target whose authoritative Compose
volumes do not exist:

```bash
./scripts/restore-runtime-linux.sh /absolute/path/to/backups/runtime-YYYYMMDD-HHMMSS
```

OpenSearch is rebuilt from PostgreSQL and immutable evidence after restore.
Never run `docker compose down -v` against an environment containing retained
data.

## Security release gate

Run the complete pinned-scanner gate after both release images exist locally:

```bash
make security-check
```

For a production approval, use release mode and attach the reviewed risk record
when the evidence contains upstream-unfixed findings:

```bash
./scripts/run-security-gates.sh --release-mode \
  --risk-acceptance-reference SEC-2026-0042
```

Registry or advisory-service unavailability blocks a release gate. Previously
generated evidence cannot be relabeled for a new image.
