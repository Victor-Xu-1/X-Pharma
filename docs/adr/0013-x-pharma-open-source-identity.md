# ADR 0013: X-Pharma identity and Apache-2.0 publication

Status: accepted, 2026-09-30.

## Decision

The product is X-Pharma and the Python distribution is `x-pharma`.
The public repository is `Victor-Xu-1/x-pharma`. First-party source and
documentation use Apache-2.0. Third-party licenses and data permissions retain
their original scope; CPython attribution accompanies the vendored files.

The public baseline includes the current development implementation and tests.
Private Git history, environments, databases, source data and machine evidence
remain private. Source publication does not establish commercial production
readiness and does not replace the separate offline bundle.

Public branding has backend and frontend authorities; package metadata owns
the version. Existing internal package, CLI, protocol, schema, database and
volume identifiers stay stable, avoiding data migration for a marketing rename.

Styles are split by responsibility with the original cascade preserved.
The development configurator generates independent private credentials and
protects existing files. Containers start the unified gateway used by Compose.

## Verification and consequences

Source/dependency audits, local quality gates, real browser/API smoke and
GitHub CI validate the publication. Dependency changes fix discovered security
issues within compatible package lines. Container, infrastructure and provider
checks retain their actual limitations; previous private reports are not
evidence for a new commit.

Future changes use domain modules and focused reviews. The large API and query
composition files remain known maintenance risks; their full decomposition is
not claimed as part of this publication.
