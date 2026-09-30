# ADR 0003: Public MCP gateway over an internal OpenAPI domain API

- Status: Accepted target architecture
- Date: 2026-07-16
- Commercial controls refined by: ADR 0005

## Context

The product permits exactly two public entrances: the human Web workbench and one Agent gateway. Agents need semantic capability discovery, typed data tools, stable evidence resources, authorization and bounded large-result retrieval. The Web application, workers and protocol adapters also need a deterministic service contract that is independent of any Agent framework.

Publishing both a general REST API and an MCP server as separate products would create a third entrance, duplicate authorization and documentation, and allow the two contracts to drift. Using MCP as the only internal service protocol would make ordinary application integration, code generation and contract testing unnecessarily difficult.

## Decision

1. The only public Agent protocol is remote MCP over Streamable HTTP. The current target baseline is the stable MCP `2025-11-25` specification, pinned per release and protected as an OAuth resource server.
2. Domain application services expose a versioned internal HTTPS API described by OpenAPI `3.1.2` or a later compatibility-tested version. It is reachable only inside the trusted service boundary and is not a public product entrance.
3. The MCP gateway and Web BFF call the same application use cases and authorization policy. Neither protocol adapter may query PostgreSQL, OpenSearch, RDKit or any migration adapter directly.
4. MCP capabilities are layered into discovery/disambiguation, domain query, evidence/quality and bounded bulk or asynchronous data retrieval.
5. The platform contract ends at governed data, evidence, provenance and quality metadata. Agent reasoning, workflow orchestration and downstream artifacts such as reports or presentations are outside the platform boundary.
6. MCP schemas, OpenAPI schemas and domain models have explicit versions and contract tests. Shared semantics are generated from or checked against one canonical schema source; protocol-specific metadata remains in the adapter layer.
7. Adding a public partner REST API in the future requires an explicit product decision, threat model, compatibility policy and update to `GOAL.md`; it cannot appear as an undocumented route.
8. Production MCP data access passes through the commercial entitlement, metering reservation and anti-extraction policy defined by ADR 0005 before invoking the shared application use case. The internal OpenAPI API cannot be exposed to bypass those controls.

## Consequences

- Agent clients receive protocol-native tool and resource discovery without exposing the internal topology.
- Web and Agent results share one data, authorization, audit and error model.
- The MCP contract remains reusable across Agent products because it does not prescribe what an Agent must create from the data.
- Internal services remain straightforward to test, generate clients for and evolve independently of MCP SDK changes.
- The platform must maintain two protocol adapters and verify that schemas do not drift.
- MCP specification and SDK upgrades require compatibility and interoperability testing before release.
