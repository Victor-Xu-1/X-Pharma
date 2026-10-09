ARG DOCKER_LIBRARY_REGISTRY=public.ecr.aws/docker/library
FROM ${DOCKER_LIBRARY_REGISTRY}/node:24.14.0-alpine@sha256:7fddd9ddeae8196abf4a3ef2de34e11f7b1a722119f91f28ddf1e99dcafdf114 AS web-builder

ENV COREPACK_HOME=/opt/corepack
WORKDIR /web
RUN mkdir -p "$COREPACK_HOME" && corepack enable && corepack prepare pnpm@11.7.0 --activate
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    --mount=type=cache,target=/root/.cache/pnpm \
    pnpm install --frozen-lockfile
COPY apps/web ./
COPY docs/openapi.json /docs/openapi.json
RUN pnpm build

FROM web-builder AS web-test
RUN chown -R node:node /web
USER node
CMD ["sh", "-ec", "pnpm api:check && pnpm check && pnpm typecheck && pnpm test && pnpm build"]

FROM ghcr.io/astral-sh/uv:0.11.28@sha256:0f36cb9361a3346885ca3677e3767016687b5a170c1a6b88465ec14aefec90aa AS uv

FROM ${DOCKER_LIBRARY_REGISTRY}/python:3.13.16-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_HTTP_TIMEOUT=300 \
    UV_HTTP_RETRIES=10 \
    UV_CONCURRENT_DOWNLOADS=2
COPY --from=uv /uv /bin/uv
WORKDIR /app
COPY scripts/verify_cpython_tarfile.py scripts/verify_cpython_tls.py scripts/verify_cpython_html.py /tmp/cpython-probes/
RUN python /tmp/cpython-probes/verify_cpython_tarfile.py \
    && python /tmp/cpython-probes/verify_cpython_tls.py \
    && python /tmp/cpython-probes/verify_cpython_html.py \
    && rm -rf /tmp/cpython-probes
COPY pyproject.toml uv.lock README.md .python-version ./
COPY deploy/cpython/downloads.json ./deploy/cpython/downloads.json
COPY LICENSE NOTICE THIRD_PARTY_NOTICES.md ./
COPY licenses ./licenses
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

FROM builder AS test-runner

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean \
    && timeout --foreground --signal=TERM --kill-after=15s 600s \
        apt-get -o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update \
    && DEBIAN_FRONTEND=noninteractive timeout --foreground --signal=TERM --kill-after=15s 600s apt-get \
        -o Acquire::Retries=3 \
        -o Acquire::http::Timeout=30 \
        -o Acquire::https::Timeout=30 \
        install --yes --no-install-recommends git=1:2.47.3-0+deb13u1

COPY alembic.ini ./
COPY Makefile ./
COPY .dockerignore ./
COPY .github/workflows/ci.yml ./.github/workflows/ci.yml
COPY .env.example ./
COPY compose.yaml ./
COPY compose.dev.yaml ./
COPY compose.telemetry.yaml ./
COPY compose.ocr.yaml ./
COPY apps/web ./apps/web
COPY migrations ./migrations
COPY tests ./tests
COPY services ./services
COPY docs ./docs
COPY deploy/api.Dockerfile ./deploy/api.Dockerfile
COPY deploy/security ./deploy/security
COPY deploy/postgres-rdkit.Dockerfile ./deploy/postgres-rdkit.Dockerfile
COPY deploy/commercial ./deploy/commercial
COPY deploy/ingestion ./deploy/ingestion
COPY deploy/kubernetes ./deploy/kubernetes
COPY deploy/ocr ./deploy/ocr
COPY deploy/otel ./deploy/otel
COPY deploy/operations ./deploy/operations
COPY deploy/release ./deploy/release
COPY runbooks ./runbooks
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --dev --no-editable
COPY scripts ./scripts
RUN test -f scripts/capture_ingestion_readiness.py \
    && test -f scripts/capture_production_topology.py \
    && test -f scripts/validate-kubernetes.sh \
    && test -f scripts/verify-automatic-ingestion.sh \
    && test -f scripts/verify-ingestion-cancellation.sh \
    && test -f scripts/verify-pilot-ingestion.sh \
    && test -f scripts/verify-quarantine-workflow.sh \
    && test -f scripts/verify-source-stage-replay.sh \
    && test -f scripts/verify-source-version-replay.sh
RUN groupadd --gid 10001 tester \
    && useradd --uid 10001 --gid tester --create-home tester \
    && chown -R tester:tester /app
USER tester
CMD ["uv", "run", "--no-sync", "pytest", "-m", "not integration"]

FROM ${DOCKER_LIBRARY_REGISTRY}/python:3.13.16-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c

ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY deploy/security/debian13-runtime-packages.lock /tmp/security-packages.lock
COPY deploy/security/install-runtime-security-packages.sh /tmp/install-security-packages.sh
RUN bash /tmp/install-security-packages.sh /tmp/security-packages.lock \
    && rm -f /tmp/security-packages.lock /tmp/install-security-packages.sh \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
USER app
WORKDIR /app
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app deploy/operations ./deploy/operations
COPY --chown=app:app runbooks ./runbooks
COPY --from=web-builder --chown=app:app /web/dist ./web
EXPOSE 8080 8090
CMD ["pharma-gateway"]
