# Security and software-supply-chain gates

`scripts/run-security-gates.sh` is the WSL and release security entry point. It produces
machine-readable evidence under `manifests/runtime/security/` and fails the build
when any mandatory gate fails.

Unfixed operating-system findings and the production approval boundary are tracked in
[the image vulnerability risk register](security-risk-register.md).

The gate performs these checks:

1. Stages only Git deliverables, excluding ignored local data, credentials, caches,
   and runtime evidence. The manifest binds the staged file paths and contents to a
   deterministic SHA-256 and records both `HEAD` and the worktree state.
2. Refuses `--release-mode` before scanning unless `HEAD` exists and the worktree,
   including non-ignored untracked files, is clean.
3. Builds the application image from that staged source tree, stamps the exact commit
   and source-tree SHA-256 into OCI labels, and verifies both before scanning. The
   PostgreSQL/RDKit image is rebuilt whenever its self-contained pinned Dockerfile
   SHA-256 changes (or its provenance label is absent), then reused while that build
   definition is unchanged. Both build inputs and resulting digests enter the manifest;
   an unrelated mutable local tag is not accepted as current evidence.
4. Scans the staged source tree with Gitleaks. False positives are accepted only as
   exact, reviewed fingerprints in `.gitleaksignore`.
5. Runs Semgrep registry rules for Python, TypeScript, Docker, and Kubernetes over
   application and deployment surfaces. The gate reparses machine output and rejects
   every parser, rule, timeout, or internal scan error even when the scanner process
   returns zero. Generated Alembic migrations are excluded
   from Semgrep because their static SQL produces false positives; real migration,
   RLS, and RDKit contract tests remain mandatory.
6. Audits locked Python and Node dependencies with `pip-audit` and `pnpm audit`. The
   Python advisory query uses a 60-second request timeout and at most three observable,
   backed-off attempts; exhaustion still fails closed and never reuses a prior report.
7. Generates CycloneDX and native Syft SBOMs for source, the application image, and
   the PostgreSQL/RDKit image. Image scans use bounded, read-only `docker save`
   archives instead of granting the scanner access to the Docker socket. Syft update
   checks are disabled because scanner identity is already digest-pinned; each
   containerized scanner has a ten-minute hard timeout and fails closed.
8. Runs Grype over both image SBOMs, retains the complete vulnerability inventory,
   and blocks every unsuppressed High or Critical finding for which an upstream fix
   exists. Unfixed and distribution `wont-fix` findings remain counted in the
   evidence manifest and require a release risk-acceptance reference. VEX statements
   must identify one package and vulnerability and include a reproducible remediation
   record.

The scanner images and immutable digests are declared in
`deploy/security/versions.env`. Updating a scanner requires reviewing its upstream
release, changing both tag and digest, and rerunning the complete gate.

On a constrained build network, `APT_HTTP_PROXY` may name a credential-free HTTP
proxy used only while building the PostgreSQL/RDKit stage. The gate also passes this
value through Docker's predefined `HTTP_PROXY` and `HTTPS_PROXY` build arguments so
the verified RDKit archive and CMake `FetchContent` dependencies use the same
controlled route. Docker excludes these predefined proxy arguments from image
history and cache keys, and the APT configuration is removed in the builder stage.
APT still validates repository Release/package signatures, fails when any index
cannot be updated, and enforces bounded network and wall-clock timeouts. Proxy
credentials are deliberately unsupported.

The application image carries official CPython 3.13 backports for
`CVE-2026-15308`, `CVE-2026-11940`, and `CVE-2026-11972`, verified by SHA-256
during the image build. The corresponding OpenVEX statements are in
`deploy/security/api.openvex.json`. The untrusted HTML ingestion path also selects
`lxml` explicitly.

Run locally; the gate performs deterministic target image builds itself:

```bash
make security-check
```

A release approval run also supplies the security review ticket or signed risk record:

```bash
./scripts/run-security-gates.sh --release-mode \
  --risk-acceptance-reference SEC-2026-0042
```

Release mode verifies the worktree before and after scanning, cannot run from a dirty or
unborn Git worktree, and cannot skip dependency audits. An unavailable scanner registry,
package advisory service, or pinned scanner image blocks approval; it is not a
reason to silently reuse stale evidence.

Do not edit generated reports. Preserve the entire evidence directory with the
release image digests and deployment approval record.
