# ADR 0001: Structured platform core with replaceable RAG

Status: Accepted; RAGFlow runtime retired under ADR 0004 and commercial MCP ledger refined by ADR 0005

## Context

The product must support precise pharmaceutical filters, bioactivity calculations, chemical structure search, competitive landscapes and governed Agent data access for many users. A document-only RAG system cannot enforce measurement semantics, temporal history, entity identity or reproducible aggregation.

## Decision

Use PostgreSQL as the system of record, RDKit for chemical search, OpenSearch for full-text/facets and object storage for immutable evidence. Historical RAGFlow access is restricted to an offline, read-only export command and is absent from the target runtime defined by ADR 0004. Expose all domain capabilities through one authorization and audit service used by both the human application and MCP gateway.

PostgreSQL also owns the append-only MCP subscription, entitlement, usage reservation/settlement and adjustment ledger defined by ADR 0005. Gateway counters and external billing products are projections or accelerators, not commercial authorities.

PostgreSQL, object storage and the isolated RAGFlow offline export utility are implemented. OpenSearch 3.7 entity/evidence projections, facets, autocomplete and rebuildable aliases are also implemented; production-scale relevance, capacity and recovery evidence remains a commercial-release gate. PostgreSQL 18 / RDKit exact, substructure and similarity domain queries, materialized fingerprints, tenant RLS and paid MCP compute settlement are implemented and real-database tested; production chemistry relevance and capacity qualification remain release gates.

## Consequences

- Existing RAGFlow data can be inventoried and exported offline but is not the master database.
- More ingestion and normalization work is required before broad coverage is credible.
- Agent answers can be grounded in deterministic domain queries and source citations.
- The offline RAGFlow export utility and embedding models can be removed or replaced without migrating canonical business data.
