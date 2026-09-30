# ADR 0006: Browser RDKit is a display-only boundary

- Status: Accepted
- Date: 2026-07-16
- Scope: Human chemistry workbench molecular depictions
- Depends on: ADR 0001 and ADR 0004

## Context

The human workbench needs inspectable two-dimensional molecular drawings. The governed chemical record, normalization, exact/substructure/similarity semantics and commercial Agent results already use PostgreSQL 18 with the RDKit cartridge and the server RDKit 2026.03.3 runtime. Reimplementing those decisions in a browser runtime would create two chemical authorities and expose version-dependent divergence.

The official `@rdkit/rdkit` browser package currently has a different release cadence from the server runtime. Its generated Emscripten loader also contains Node compatibility branches that bundlers externalize for a browser build.

## Decision

1. Pin `@rdkit/rdkit` exactly and bundle its JavaScript and WASM assets with the Web application. A CDN or unversioned runtime is not permitted.
2. Use browser RDKit only to draw a server-governed canonical SMILES. It cannot normalize, persist, compare, fingerprint, authorize or bill a structure.
3. Keep PostgreSQL/RDKit and the domain service authoritative for canonical SMILES, InChI/InChIKey, properties, search semantics and version metadata.
4. Lazy-load the browser runtime when a depiction approaches the viewport. Reuse one module instance and explicitly delete every Emscripten molecule object.
5. Render the returned SVG through an encoded image URL rather than injecting markup into the document.
6. Treat initialization timeout or rejected SMILES as a visible depiction failure without changing the governed result.
7. Qualify every browser RDKit upgrade with component tests, a production bundle build and a real Chromium test that loads the emitted WASM and verifies a non-empty drawing.

## Consequences

- Human users can inspect structures without weakening the chemical data contract.
- A browser package version difference cannot alter stored or Agent-visible chemical facts.
- The Web artifact carries an additional compressed WASM payload, but it is not downloaded on login or unrelated views.
- Vite may report externalized Node compatibility branches from the generated loader. This is accepted only while the real browser acceptance test proves the browser branch loads without `fs` or `crypto` at runtime.
