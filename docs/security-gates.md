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
   PostgreSQL/RDKit image is rebuilt whenever the relative paths/content of its
   Dockerfile, shared Debian package lock or installer change (or its provenance
   label is absent), then reused only while those three inputs are unchanged.
   The existing source-manifest implementation owns this selected-input hash;
   missing, duplicate, escaping or symlinked inputs fail closed. Build inputs and resulting digests enter the manifest;
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

Application and optional OCR images use the same digest-pinned official CPython
3.13.16 runtime, including the supplier fixes for CVE-2026-19445 and CVE-2026-19553.
TLS hostname, HTML streaming-comment and tarfile hardlink-relocation probes execute
against the installed standard library during builds. Superseded local HTML/tarfile
overlays and their old Python VEX entries are removed; no new TLS finding is ignored.
The supplier digest and native-bootstrap descriptor are documented in
[the CPython runtime contract](../deploy/cpython/README.md).
The untrusted HTML ingestion path continues to select `lxml` explicitly. Original
scanner thresholds, fixed-vulnerability failure and complete inventories remain.

### PDF parser dependency boundary

The main parser and optional OCR service pin pypdf 6.21.1 consistently, covering
the October 2026 resource-consumption advisories and the earlier upstream
[alphabetical page-label allocation fix](https://github.com/py-pdf/pypdf/security/advisories/GHSA-w23x-9jrw-r45c).
The Python lock and independently isolated OCR hash lock are regenerated by their
declared tools; these findings are not exempted through VEX or audit ignores.
`tests/test_pdf_security_limits.py` uses tiny real PDF documents to verify the
valid 512-character boundary and safe handling beyond it, plus agreement between
both dependency pins and the installed parser. Strict PDF parsing, sandbox
resource limits and the actual parser/OCR HTTP regressions remain required.
This dependency version is independent of X-Pharma's product version, whose sole
authority is [`pyproject.toml`](../pyproject.toml). Product PR-merge counting follows
[the contribution policy](../CONTRIBUTING.md#product-version-counter), not the
dependency, protocol or migration version.

### October dependency security baseline

The API/SDK/exporters use the coherent OpenTelemetry 1.45.1 family and its
0.66b1 instrumentation/semantic conventions, rather than independently upgrading
one instrumentation package. The project and separate OCR hash lock use certifi
2026.10.19 and Pillow 13.0.0; the development audit toolchain constrains pip to
26.2.0. Vite is pinned to 8.3.3 because the 8.3.2 release still falls in the
affected range for [the Windows editor-launch advisory](https://github.com/advisories/GHSA-587h-7wmj-h5pm).
Vitest stays on the 4.1 series at 4.1.12 to fix both
[manual mock injection](https://github.com/advisories/GHSA-qxg6-89mg-rqv8) and
[Windows redirect traversal](https://github.com/advisories/GHSA-xp26-3454-mjgp)
without adopting an unrelated major-version change.
These are dependency versions, not manual product-version changes.

Both package ecosystems retain their original frozen-lock and vulnerability
gates. OCR hashes are generated with the declared uv command and release cutoff;
image-format matching, strict PDF parsing, real zero/source precision, TLS
verification and source/identity boundaries remain unchanged. Focused dependency,
parser, OCR HTTP, logo and telemetry checks do not replace the original seven
automatic CI jobs, image SBOM scanning, deployment or actual browser acceptance.

### PostgreSQL image util-linux patch family

The reviewed Debian lock includes all nine installed util-linux binary packages
at the trixie 2.41.5-0+deb13u1 patch level for
[CVE-2026-53612](https://security-tracker.debian.org/tracker/CVE-2026-53612),
[CVE-2026-53613](https://security-tracker.debian.org/tracker/CVE-2026-53613),
[CVE-2026-53614](https://security-tracker.debian.org/tracker/CVE-2026-53614) and
[CVE-2026-53615](https://security-tracker.debian.org/tracker/CVE-2026-53615).
bsdutils and login preserve their distinct Debian epochs/version prefixes.
The existing installer upgrades only already installed packages and refuses
downgrades; it does not add mount utilities to smaller images. No scanner
finding is waived. PostgreSQL/RDKit runtime, non-root entrypoint, real SQL,
fresh restore and image vulnerability checks remain separate release gates.

### OCR transitive media-library reachability

The authentication dependency is pinned to PyJWT 2.15.0 for
[CVE-2026-101918](https://github.com/advisories/GHSA-42vr-xj54-vc7v).
The dependency's pre-verification parser must return a controlled `DecodeError`
for a deeply nested untrusted payload, rather than a raw `RecursionError`.
`tests/test_security_boundary.py` captures this regression; human OIDC, MCP OIDC,
DPoP and signed internal-token paths remain part of the affected regression set.

The pinned OpenCV contribution wheel bundles FFmpeg 5.1.4. Its vulnerable library
is retained in the complete SBOM and raw scan inventory; a VEX `not_affected`
statement is not a binary patch or a claim of zero vulnerabilities. The OCR API
has no video, audio, stream URL, DASH, subtitle or muxing input. Authentication,
bounded input, SHA-256 and generated local paths precede inference. Pillow's
decoded format must exactly match the allowed PNG/JPEG/TIFF extension; PDFs use
strict `PdfReader` preflight. Merely calling Pillow `verify()` was insufficient:
a real MPEG sequence header renamed to PNG reached the engine before this fix.

`tests/test_ocr_service.py` uses the real HTTP handler and Pillow parser to reject
that MPEG input, GIF, PPM and JPEG disguised as PNG with HTTP 415 and zero engine
calls. Separate tests preserve all five supported still-image suffixes. The
engine boundary is isolated in these tests; they do not claim model-inference
quality or a real-model acceptance run.

The reviewed findings recorded individually in `deploy/security/ocr.openvex.json` are:

| Finding | Affected upstream path | OCR reachability |
| --- | --- | --- |
| [CVE-2026-70628](https://security-tracker.debian.org/tracker/CVE-2026-70628) | DVB subtitle parser / WTV input | No subtitle or video input |
| [CVE-2026-70632](https://security-tracker.debian.org/tracker/CVE-2026-70632) | CineForm HD decoder / AVI input | No video decoding input |
| [CVE-2026-75142](https://www.cve.org/CVERecord?id=CVE-2026-75142) | MPEG-PS muxer | No video muxing or encoding operation |
| [CVE-2026-75146](https://www.cve.org/CVERecord?id=CVE-2026-75146) | DASH live-manifest demuxer | No stream manifest or input URL |

Any relaxation of the input-format contract, or addition of video/audio,
subtitles, streaming or encoding, invalidates these reachability statements and
requires dependency remediation plus new real-path security acceptance. Do not
generalize them to another use of OpenCV or FFmpeg.

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
