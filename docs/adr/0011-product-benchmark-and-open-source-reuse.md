# ADR 0011: Product benchmark and open-source reuse boundary

- Status: Accepted
- Date: 2026-07-22
- Scope: Public product benchmarking, Web modules and reuse policy
- Refines: ADR 0004

## Context

The external workbench is benchmarked against mature pharmaceutical intelligence products, including the publicly observable NextPharma workbench. A product benchmark is useful for information architecture, interaction density and workflow coverage, but public browser assets cannot establish the private backend architecture and do not grant a right to copy proprietary source code, data, visual assets or terminology.

An inspection of the public `https://nextpharma.pharmcube.com/drugde/index` document and its CDN bundles on 2026-07-22 confirmed these frontend signals:

- hashed route chunks plus a `chunk-vendors` bundle and CDN-prefetched CSS/JavaScript;
- Vue/Vuex, Axios, Element, Ant Design Vue, Lodash and Day.js signatures in the public vendor bundle;
- Swiper and SheetJS/XLSX signatures in the application bundle;
- a domain navigation shell, dense multi-dimensional filters, export affordances and route-level code splitting;
- Alibaba Cloud CAPTCHA loaded at the authentication boundary.

These signals describe the public frontend only. They provide no reliable evidence for the database, search engine, workflow system, data model, authorization service or deployment topology behind the product.

## Decision

1. Preserve the locked React/TypeScript architecture. Do not rewrite the platform in Vue or mix Element and Ant Design component systems merely to resemble the benchmark.
2. Reuse mature open-source engines at bounded interfaces:
   - TanStack Query for server state and generated OpenAPI transport contracts;
   - TanStack Table and Virtual for dense, virtualized result grids;
   - Apache ECharts 6.1.0, imported by module with the SVG renderer, for governed timelines, trends and analytical views;
   - RDKit/RDKit.js and Mol* for chemistry and structural biology display boundaries;
   - Temporal, Apache Tika, PaddleOCR, OpenSearch, PostgreSQL/RDKit, Kafka, Debezium and ClickHouse according to ADR 0004 and the approved production profile.
3. Keep export generation on the server behind authorization, audit, quotas and anti-extraction controls. A browser spreadsheet library must not become an unrestricted data-export path.
4. Reproduce product capabilities and interaction principles, not source code or visual assets. New code must use documented public APIs, compatible licenses and repository-owned design tokens.
5. Record every added runtime dependency with an exact version, license, security review, bundle impact, rollback path and real-path tests. A library is adopted only when it removes meaningful custom implementation or supplies a qualified domain engine.
6. Treat pharmaceutical source content and normalized records as licensed data. Open-source software does not make third-party data reusable.

## Consequences

- The workbench can reach commercial information density without inheriting a legacy Vue stack or multiple overlapping component libraries.
- Apache ECharts becomes the single charting engine; custom canvas/SVG chart implementations are not allowed without a measured gap and a follow-up ADR.
- Public bundle fingerprints remain benchmark evidence, not backend facts and not a dependency manifest to clone.
- Backend and data-platform choices continue to be justified by canonical consistency, provenance, scale, security and operating requirements rather than visual similarity.
