ARG DOCKER_LIBRARY_REGISTRY=public.ecr.aws/docker/library
FROM ${DOCKER_LIBRARY_REGISTRY}/node:24.14.0-alpine@sha256:7fddd9ddeae8196abf4a3ef2de34e11f7b1a722119f91f28ddf1e99dcafdf114 AS web-builder

ENV COREPACK_HOME=/opt/corepack
WORKDIR /web
RUN mkdir -p "$COREPACK_HOME" && corepack enable && corepack prepare pnpm@11.7.0 --activate
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store pnpm install --frozen-lockfile
COPY apps/web ./
COPY docs/openapi.json /docs/openapi.json
RUN pnpm build

FROM web-builder AS web-test
RUN chown -R node:node /web
USER node
CMD ["sh", "-ec", "pnpm api:check && pnpm check && pnpm typecheck && pnpm test && pnpm build"]

FROM ghcr.io/astral-sh/uv:0.11.28@sha256:0f36cb9361a3346885ca3677e3767016687b5a170c1a6b88465ec14aefec90aa AS uv

FROM ${DOCKER_LIBRARY_REGISTRY}/python:3.13.14-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91 AS builder

ARG CPYTHON_HTML_PARSER_COMMIT=7933f4bf7131aa4140750f9404f5de0aa2969ced
ARG CPYTHON_HTML_PARSER_SHA256=4274e9112adf3fa57c7f9afa7c9b5c631456b18b7403cc627cc5027d02cdd2ae
ARG CPYTHON_TARFILE_COMMIT=771d12dda5140313db0ac550292987975651bbde
ARG CPYTHON_TARFILE_SHA256=0ad8c3869f9ab172fc5fc539528eb94c44d0745aef15dc8a0f1a773fae3b6c52
LABEL io.pharma.cpython-html-parser-commit=${CPYTHON_HTML_PARSER_COMMIT} \
      io.pharma.cpython-tarfile-commit=${CPYTHON_TARFILE_COMMIT}

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_HTTP_TIMEOUT=300 \
    UV_HTTP_RETRIES=10 \
    UV_CONCURRENT_DOWNLOADS=2
COPY --from=uv /uv /bin/uv
WORKDIR /app
COPY deploy/cpython/html-parser.py /tmp/cpython-html-parser.py
COPY deploy/cpython/tarfile.py /tmp/cpython-tarfile.py
RUN echo "${CPYTHON_HTML_PARSER_SHA256}  /tmp/cpython-html-parser.py" | sha256sum --check --strict \
    && install -m 0644 /tmp/cpython-html-parser.py /usr/local/lib/python3.13/html/parser.py \
    && rm -f /tmp/cpython-html-parser.py \
    && rm -f /usr/local/lib/python3.13/html/__pycache__/parser.*.pyc \
    && python -c "from html.parser import HTMLParser; p=HTMLParser(); p.feed('<!--'); [p.feed('a' * 64) for _ in range(200000)]; p.feed('-->'); p.close()"
RUN echo "${CPYTHON_TARFILE_SHA256}  /tmp/cpython-tarfile.py" | sha256sum --check --strict \
    && install -m 0644 /tmp/cpython-tarfile.py /usr/local/lib/python3.13/tarfile.py \
    && rm -f /tmp/cpython-tarfile.py \
    && rm -f /usr/local/lib/python3.13/__pycache__/tarfile.*.pyc \
    && python -c "import inspect, tarfile; assert 'if not data:' in inspect.getsource(tarfile._Stream.seek); assert 'unfiltered.replace(name=tarinfo.name' in inspect.getsource(tarfile.TarFile.makelink_with_filter)"
COPY pyproject.toml uv.lock README.md ./
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
COPY deploy/cpython ./deploy/cpython
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

FROM ${DOCKER_LIBRARY_REGISTRY}/python:3.13.14-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91

ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder /usr/local/lib/python3.13/html/parser.py /usr/local/lib/python3.13/html/parser.py
COPY --from=builder /usr/local/lib/python3.13/tarfile.py /usr/local/lib/python3.13/tarfile.py
USER app
WORKDIR /app
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app deploy/operations ./deploy/operations
COPY --chown=app:app runbooks ./runbooks
COPY --from=web-builder --chown=app:app /web/dist ./web
EXPOSE 8080 8090
CMD ["pharma-gateway"]
