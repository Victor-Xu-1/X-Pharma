# ADR 0004: Locked open-source technology baseline

- Status: Accepted target architecture
- Date: 2026-07-16
- Scope: Application runtime, data platform, ingestion, AI, security, operations and scale profile
- Refines: ADR 0001, ADR 0002 and ADR 0003
- Commercial MCP controls: ADR 0005

## Context

The platform needs one stable engineering direction for subsequent work. A list of interchangeable products is not sufficient: it allows each implementation task to introduce another database, workflow engine, Agent framework or UI stack, eventually producing duplicated semantics and an unmaintainable deployment.

The repository started with Python 3.11-compatible code, PostgreSQL 16 and a RAGFlow evidence adapter, without the required OpenSearch, RDKit, Kafka, ClickHouse or Iceberg projections. OpenSearch 3.7 entity/evidence/knowledge projections have since been implemented behind the same domain boundary; the remaining target-stack gaps are tracked in `docs/commercial-readiness.md`. Architectural decisions and current verification evidence must remain distinct.

## Decision

### Architecture style

Use a modular monolith for domain and application logic, with separately deployable Web, Domain API/BFF, MCP gateway, ingestion workers and projection workers. Split a bounded context into a separate service only for measured capacity, isolation, compliance or team-ownership reasons and only through another ADR.

There are exactly two public entrances:

1. Human Web Workbench.
2. Remote MCP Gateway.

Both call the same application use cases and authorization policy. PostgreSQL is the canonical system of record. Search, chemistry, analytics, lakehouse, knowledge pages and Markdown are derived or historical projections with explicit rebuild procedures.

### Core commercial stack

- Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, psycopg 3 and Alembic.
- Official MCP Python SDK over Streamable HTTP; an internal REST/OpenAPI contract for Web and protocol adapters.
- React 19, TypeScript 7, Vite 8, Biome 2, TanStack Query/Table/Virtual, Radix UI primitives and Apache ECharts.
- PostgreSQL 18 plus the RDKit PostgreSQL cartridge and RDKit Python libraries.
- A platform-owned PostgreSQL append-only usage/reservation/settlement ledger for Core Commercial MCP billing; Valkey is acceleration only.
- OpenSearch 3.x for full-text, facets, autocomplete, hybrid retrieval and evidence indexes.
- Temporal 1.x for every durable ingestion and governance workflow.
- ClamAV 1.4 LTS over the clamd INSTREAM protocol for mandatory post-snapshot, pre-parser malware scanning; production fails closed when scanning cannot complete.
- S3 as the object protocol; Ceph RGW is the self-hosted open-source reference.
- Valkey for cache, session coordination and rate limiting only.
- Keycloak as the self-hosted OIDC reference and OpenBao for secrets; compatible enterprise services may replace them behind the same protocols.
- Kubernetes Gateway API with Envoy Gateway, Kubernetes/Kustomize/Argo CD, and an OpenTelemetry/Prometheus/Grafana/Loki/Tempo observability stack.

### Ingestion and AI

- Apache Tika and libmagic provide broad type and metadata fallback.
- Format-specific parsers preserve page, slide, table, cell and structure locators.
- PaddleOCR 3.x is the OCR/layout baseline; production model artifacts are pinned and evaluated.
- RDKit parses supported chemical formats; Gemmi parses PDB/mmCIF. Unsupported formats remain registered assets.
- Model access goes through platform-owned provider adapters. LLM, embedding and reranking inference are supplied only by approved third-party HTTPS APIs; local inference runtimes, bundled model weights and implicit local fallback are prohibited. Model selection is deployment configuration governed by pharmaceutical gold-set quality, data-transfer policy, SLA and cost evidence.
- LangChain, LlamaIndex and Dify are not core runtime dependencies. Model outputs use versioned Pydantic/JSON Schema contracts and cannot write canonical records directly.

### Scale production profile

Before operating at the GOAL design envelope, add:

- Apache Kafka 4.x and Debezium 3.x for durable projection event distribution from the transactional outbox.
- ClickHouse for high-concurrency analytical projections.
- Parquet and Apache Iceberg format v2 on S3 for open, replayable historical data.
- OpenMeter v1 GA or later as a qualified, replaceable metering/subscription projection; the current pre-GA line is not a production authority.

These systems remain downstream of PostgreSQL and do not change Web, MCP or domain event semantics.

### Explicit exclusions

- RAGFlow is absent from the runtime. A bounded, read-only offline export command is retained only for historical migration; direct parsers plus OpenSearch own all new evidence processing and retrieval.
- Obsidian is an optional Markdown client. LLM-Wiki contributes a compilation pattern only.
- Do not add a standalone vector database, graph database, GraphQL API, second workflow engine or premature microservice topology without measured evidence and an ADR.
- MinIO is not the production object-store reference. Existing third-party use is isolated until migration.

## Version policy

`GOAL.md` locks major version lines and protocols. Python and Node packages are pinned in lockfiles; images are pinned by digest. Security patches can advance after automated and real integration checks. Major upgrades, license changes, database migrations or protocol incompatibilities require an ADR and rollback plan.

TypeScript 7.0 has no stable programmatic compiler API. The Web baseline therefore uses the `tsc` CLI for type checking and Biome 2 for compiler-independent formatting and linting. Any development-only tool that still requires the compiler API must be isolated, pinned and compatibility-tested; it cannot silently downgrade the application's type-checking baseline.

The Web OpenAPI client is generated with a pinned compiler-independent generator and committed for reproducible builds. CI recreates it from `docs/openapi.json` and rejects byte-level drift. A platform transport adapter owns same-origin credentials, CSRF, 401 session events, diagnostic request IDs and cancellation; feature-level contract wrappers keep generated operation names out of UI components. TanStack Query owns remote server state and retries only bounded transient failures, while mutations are never retried implicitly. TanStack Table and Virtual own client-side table state and bounded viewport rendering; semantic table markup, deterministic column dimensions, server-side result limits and authorization remain mandatory.

The target version lines are not claims that the current code has completed migration. Current-to-target gaps remain release work and are tracked in `docs/commercial-readiness.md`.

## Consequences

- Follow-up work has one default stack and cannot introduce competing infrastructure without review.
- The platform avoids RAGFlow's duplicate application/database/object/search topology while preserving a read-only offline migration path for existing evidence.
- OpenSearch serves text and vector retrieval together; PostgreSQL/RDKit owns chemistry and canonical facts; ClickHouse/Iceberg only serve scale projections.
- The full target has more infrastructure than the current repository, so implementation must proceed by tested capability slices rather than a one-step rewrite.
- The local runtime now uses Python 3.13.14 with pinned uv 0.11.28 and one `uv.lock`, plus PostgreSQL 18.4 with a source-verified RDKit 2026.03.3 cartridge, tested preserved-volume rollback, versioned structure authority and real exact/substructure/similarity domain queries. Chemistry capacity qualification, managed HA/PITR, and OpenSearch production-scale qualification remain commercial-release work.
- The PostgreSQL MCP usage ledger, entitlement, immutable result/byte/compute rate card, reservation/settlement and initial anti-extraction controls defined by ADR 0005 are implemented. Cross-client risk, approved bulk export and external billing/ERP integration remain commercial-release work; OAuth/audit alone is never treated as a substitute.
- License scanning and legal review remain mandatory even for open-source components, especially copyleft or source-available dependencies.
