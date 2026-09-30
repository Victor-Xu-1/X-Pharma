# Contributing to X-Pharma

Use a focused branch and explain the user-visible problem, affected contracts
and validation in each pull request. Preserve existing data and unrelated work.
Contributions are submitted under Apache-2.0; preserve third-party attribution.

## Development and checks

Follow the root README to install locked dependencies. Use a Linux-native
checkout; E-drive WSL users keep source, environments, data, caches and outputs
on the E-drive distribution. `make configure` creates a private development
environment and refuses to overwrite existing credentials.

```bash
make check
uv run pharma-openapi --check
uv build
```

`make check` covers formatting, Ruff, strict mypy, backend tests and coverage,
frontend contract/format/type/test/build gates, operations and deployment
rendering. `kubectl` must be available for Kubernetes rendering.

Run affected real integration gates against isolated environments:

```bash
make database-acceptance
make browser-acceptance
make security-check
```

CI also exercises real PostgreSQL/RDKit, RLS, OpenSearch, SMB, Kubernetes and
Web/MCP protocols. Preserve existing required gates. Provider-dependent LLM
and optional OCR checks need their configured environments; report unrun
checks explicitly instead of substituting historical results.

After changing API schemas:

```bash
uv run pharma-openapi
corepack pnpm@11.7.0 --dir apps/web api:generate
corepack pnpm@11.7.0 --dir apps/web api:check
```

Generated clients have one authority: `docs/openapi.json`. Dependencies have
one lockfile per ecosystem. Released migrations retain their identifiers and
data changes require a reviewed recovery path.

Read [the source guide](docs/codebase-guide.md) before editing. Separate
transport, business rules, persistence and external adapters. Use `product.py`
and the frontend product module for branding; protocol, database and CLI
identifiers are independent from marketing names.

Styles live under `apps/web/src/styles/`; the import order preserves the cascade.
Design tokens have one authority. Verify responsive layouts and accessibility
after UI changes.

Do not commit private configuration, source data, backups, dependency trees,
builds, temporary scripts or debugging screenshots. Reviewed visual regression
baselines are intentional test assets. See [SECURITY.md](SECURITY.md) for reports.
