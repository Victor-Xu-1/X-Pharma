# ADR 0002: Governed knowledge compilation

- Status: Accepted; runtime components refined by ADR 0004
- Date: 2026-07-15

## Context

RAG alone repeatedly reconstructs knowledge from document chunks. A Markdown-only LLM wiki accumulates synthesis, but it does not provide transactional writes, tenant isolation, source licensing, concurrent update safety, structured pharmaceutical measurements or enforceable review workflows.

## Decision

Use a six-layer data model: immutable raw versions, parsed evidence, AI staging, canonical pharmaceutical facts, versioned knowledge pages and reproducible data-delivery projections.

PostgreSQL is authoritative for workflow state, canonical facts, page versions, citations and audit. Existing RAGFlow data is reachable only through an isolated, read-only offline export command; target parsing uses dedicated parsers/PaddleOCR and target evidence retrieval uses OpenSearch. Object storage is authoritative for source bytes. OpenSearch, MCP result projections and Markdown are rebuildable projections.

AI may propose facts and page updates only through a schema-constrained extraction run. Deterministic validation and tenant policy decide whether a proposal is published automatically, routed to review or rejected. Every published statement retains source-version and locator references.

## Consequences

- Knowledge compounds across sources without making generated prose authoritative.
- Obsidian remains useful as a human reader/editor for exported pages, but is not required at runtime.
- Ingestion becomes a durable workflow rather than a filesystem script.
- The system stores more metadata and requires explicit review and conflict policies.
- Search and Markdown can be rebuilt from canonical data after parser or model upgrades.
