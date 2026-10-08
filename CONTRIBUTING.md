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

## Product version counter

`pyproject.toml` is the only product-version authority. Do not manually increment
product versions in feature PRs. Every merged PR targeting `main` adds one PATCH;
PATCH carries at 100 and MINOR carries at 10. For example, `v0.1.99` becomes
`v0.2.0`, and `v0.9.99` becomes `v1.0.0`. This is a merge-count policy, not a claim
that a numeric carry implies an incompatible API or schema migration.

The prospective baseline is `0.1.0` at main commit
`02dca0ce8ad7e2519b2d50419e7369318a76039b`. Historical merged PRs before that
baseline are not counted. The enabling PR itself is the first new increment.
`.github/workflows/product-version.yml` serializes reconciliation on main pushes.
An offset fifteen-minute scheduled reconciliation also catches delayed or
suppressed notifications, including merges performed with `GITHUB_TOKEN`.
GitHub scheduler latency is not a release/version propagation SLA.
It reads the processed first-parent cursor in `tool.x-pharma.versioning`, obtains
GitHub's actual merged PR receipts, and counts each PR once, including merge,
squash and rebase methods. A latest queued run reconciles the whole unprocessed
range, so coalesced notifications do not lose increments. Direct commits and
the automation's own metadata commit do not count as PRs.

The automation uses the existing uv/OpenAPI/Web-client/project-overview generators
to synchronize installed metadata, `uv.lock`, Web package metadata and generated
mirrors. It rejects dependency-resolution or API-schema changes and writes only
the explicit version-file allowlist. Its normal fast-forward push never forces
or rewrites another merge. Permissions are limited to repository contents,
read-only PR metadata and dispatching the existing CI workflow; no secret other
than the ephemeral `GITHUB_TOKEN` is required. It never creates a version PR or
recursively increments itself.

GitHub-token pushes do not automatically trigger push CI. The reconciler explicitly
dispatches `ci.yml` for the resulting main head when no existing run
exists. All six original gates still apply to the final version commit. A version
increment is not a release, automatic deployment, tag, production approval, or
permission to skip exact-commit backup, rollback and postdeploy acceptance.

If generation, API access, permissions, CI dispatch or a concurrent push fails,
the workflow fails visibly without resetting/forcing main. Inspect its job and
the current main head, then rerun `product-version` on `main` through Actions or
`gh workflow run product-version.yml --ref main`. The cursor prevents duplicate
increments, including recovery after the version commit was pushed but CI dispatch
failed.

An existing failed/cancelled CI run is retained and never silently retried by
scheduled version reconciliation. Diagnose that run and explicitly rerun the
failed CI gate after its cause is resolved; do not use version automation as
a repeating test-retry loop.

No unrelated global suite is needed for local iteration:

```bash
uv run pytest tests/test_product_versioning.py tests/test_product_version_workflow.py
```

Existing required automatic CI remains unchanged. If branch protection later
prohibits the bot's narrow main write, resolve that policy explicitly; never
disable protection or use a bypass token to conceal the failure.

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
