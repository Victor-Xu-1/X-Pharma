# ADR 0010: Governed human workbench separation

- Status: Accepted
- Date: 2026-07-20

## Context

The human application serves two materially different audiences. External and research users need dense pharmaceutical information discovery, while internal operators manage sources, AI governance, commercial controls, accounts and audit. Mixing both domains in one navigation weakens information architecture, exposes implementation concepts to customers and increases the chance that a protected view starts privileged requests before authorization is resolved.

The product boundary still permits only two public entrances: one human Web application and one Agent MCP gateway. Creating a separate administration domain, identity system or public portal would violate that boundary and duplicate session, authorization and deployment concerns.

## Decision

The human Web application remains one same-origin product and one public product entrance. It exposes two explicitly routed workbenches with independent HTML documents, React roots and feature dependency graphs:

- `/workspace/research` is the pharmaceutical information workbench. It contains overview, intelligence and chemical search, target profiles, source evidence, compiled knowledge, monitoring and comparison collections.
- `/workspace/internal` is the internal operations workbench. It contains automated data sources, ingestion runs, AI governance, commercial controls, enterprise accounts and audit.

Both workbenches share only the same OIDC or local development session, generated OpenAPI client, domain services, tenant context, audit model and deliberately generic UI primitives. Their HTML entry files, React application roots, navigation trees, page headers, default views and feature components are separate. The research entry cannot import internal feature modules and the internal entry cannot import research feature modules. Neither workbench renders an in-product switch to the other. Operators enter the internal route directly; research users enter the research route directly. Viewer may use only the research workbench; Analyst may use internal ingestion-read and governance capabilities; Admin may use every internal capability. Page-level server scopes remain authoritative and the client must reject an inaccessible workbench or view before mounting its data component.

The root path is an alias of the research login only. It never infers or loads an internal view from query parameters. A view from one workbench supplied to the other workbench entry fails closed to that entry's default view.

The Vite multi-page build emits `research.html` and `internal.html`; FastAPI serves each stable route from its matching document before the static root mount. Runtime evidence records each document marker and SHA-256 and rejects identical workbench documents. No new port, hostname, cookie scope, backend service or public entry is introduced. Real Google Chrome acceptance must cover both routes on desktop and mobile.

## Consequences

- Customer-facing navigation no longer exposes ingestion, governance, billing or account administration.
- Internal operators have a focused operational space without creating a third product entrance.
- URL routing and role tests become part of the security boundary and release evidence contract.
- An internal-only feature cannot enter the research JavaScript dependency graph through a shared runtime router.
- Cross-workbench navigation is intentionally absent from the product UI; direct route access repeats authorization checks.
- Backend scopes and RLS remain mandatory; client separation is defense in depth, not the authority layer.
