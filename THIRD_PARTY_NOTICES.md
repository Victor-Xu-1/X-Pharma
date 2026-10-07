# Third-party notices

Apache-2.0 applies to X-Pharma's first-party source and documentation. Third-party
software, images, models, data and services retain their own licenses. Versions
are recorded in `uv.lock`, `apps/web/pnpm-lock.yaml`, the OCR lockfile and pinned
deployment manifests. Review these licenses when distributing binaries/images.

## Included upstream source

`deploy/cpython/html-parser.py` and `deploy/cpython/tarfile.py` are unmodified
CPython security backports. Official commits, SHA-256 digests and probes are
documented in [deploy/cpython/README.md](deploy/cpython/README.md). The complete
upstream license and historical notices are included in
[licenses/PSF-2.0.txt](licenses/PSF-2.0.txt). Preserve their attribution.

The generated TypeScript client comes from X-Pharma's OpenAPI schema using
openapi-typescript-codegen. The installed generator retains its own license.

## Installed dependencies and components

Python and frontend libraries are installed rather than vendored. These include
FastAPI, SQLAlchemy, Pydantic, MCP, React, TanStack, ECharts, RDKit, Gemmi, Ketcher,
Paramiko, lxml, OpenTelemetry and document parsers. Their license metadata and
license files remain inside installed distributions and must be retained when
redistributing those dependencies.

Knowledge document rendering uses `react-markdown` and `remark-gfm` from the
unified/remark community under MIT. Exact versions are pinned in the frontend
lockfile. Retain their installed license files when redistributing this renderer;
X-Pharma's Apache-2.0 license does not replace these upstream licenses.

Docker/Kubernetes components include PostgreSQL/RDKit, OpenSearch, Temporal,
Valkey, ClamAV, OpenTelemetry and optional OCR. These programs and their bundled
dependencies retain their upstream identities and licenses. Source licensing
does not replace those obligations. SBOM and image checks are defined by
`scripts/run-security-gates.sh`.

Models, chemical databases, source documents, trial/patent material and API
credentials are not included in the public source repository. Record applicable
permissions, use, geography and delivery channels before ingestion or export.
Software permissions do not imply access or redistribution rights for data.
