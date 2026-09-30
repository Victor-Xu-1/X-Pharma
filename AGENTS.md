# X-Pharma engineering contract

- Use Linux-native storage. In the maintainer's WSL workspace all project source,
  environments, data, caches and outputs remain on the E-drive distribution.
- Keep one implementation per behavior. Add small, explicit modules instead of
  extending large API, query and UI composition files.
- Preserve existing behavior and unrelated edits. Use isolated branches for
  concurrent changes and review the exact diff before committing.
- `pyproject.toml` owns the version and Apache-2.0 metadata. `uv.lock` and
  `apps/web/pnpm-lock.yaml` own dependency resolutions.
- Public branding belongs to `src/pharma_intel/product.py` and
  `apps/web/src/lib/product.ts`. Internal package, CLI, schema and storage names
  remain stable unless a reviewed migration changes them.
- `pharma-openapi` generates the API contract. Frontend clients are generated
  from `docs/openapi.json`; never hand-edit generated output.
- PostgreSQL owns facts, permissions and audit. OpenSearch and knowledge exports
  are projections. Models can write only to the governance staging path.
- Trace affected paths before selecting checks. Preserve required gates and run
  relevant behavior, real database/API/browser and security checks. Report unrun
  provider or infrastructure checks accurately.
- Preserve released migrations and attribution. Third-party licenses and data
  permissions are independent of the first-party Apache-2.0 license.
- Do not commit private environments, data, backups, dependencies, builds or
  machine acceptance evidence. Documentation must describe verified behavior.
- Source publication does not establish commercial production readiness.
