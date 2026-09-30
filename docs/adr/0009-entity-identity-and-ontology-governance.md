# ADR 0009: Governed entity identity and ontology mapping

- Status: Accepted
- Date: 2026-07-18

## Context

Pharmaceutical records arrive from documents, licensed feeds and human curation with inconsistent names and identifiers. Name-only deduplication can merge different targets, compounds or programs, while unrestricted AI merging can silently corrupt activity, structure, clinical and competitive-landscape facts. A production platform also needs reproducible terminology versions instead of mutable free-text tags.

## Decision

PostgreSQL owns entity identity. Each entity has tenant-scoped identifiers with explicit namespace normalization, trust classification, provenance and review status. HGNC, UniProt, Ensembl, ChEMBL, DrugBank, PubChem CID, ClinicalTrials.gov, DOI, EFO, MeSH and patent identifiers are recognized namespaces; unknown namespaces remain usable but are never treated as trusted identity evidence.

AI ingestion resolves an exact, non-conflicting trusted identifier automatically. A trusted-identifier conflict or an ambiguous name creates a separate entity plus an `entity_resolution_case`; it never overwrites or destructively merges canonical data. Candidate scores are evidence for review, not merge authority.

An approved case creates a reversible canonical link. Decisions are append-only and record the reviewer, action, notes and timestamp. Revert removes the active canonical link while retaining the decision history. Cycles and cross-type links are rejected.

Ontology terms are immutable by `(ontology_name, ontology_version, term_id)`. Re-registering identical content is idempotent; changed content under the same version is rejected. Entity mappings are typed, confidence-scored, source-aware and reviewable. A mapping cannot connect an ontology term to a different entity type.

Web and MCP return the same canonical entity ID and governed identifiers through the shared domain API. Identity review remains a human workspace operation and is not exposed as an Agent mutation tool.

## Consequences

- Same-name records can coexist until their identity is proven.
- Stable identifiers and ontology versions become explicit query and migration contracts.
- AI can accelerate ingestion without gaining destructive merge authority.
- Search and knowledge projections must use canonical IDs and can be rebuilt after a resolution decision.
- Operators must monitor pending high-risk cases and periodically import approved ontology versions.
