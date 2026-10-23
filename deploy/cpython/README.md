# CPython security runtime

The supported runtime is CPython 3.13.16. API builder/runtime and optional OCR
use the same Docker Official Images release, pinned to OCI index SHA-256
`bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c`.
The index's Linux amd64 manifest is
`8fb4cfa1a2616d7b8e0c2175cc6ad68f5729c34ea8488c0b360d2934b7be9024`.
The original registry body was hashed and matched to its content-digest header;
the ECR Public copy was pulled by the same immutable digest.

The official release fixes CVE-2026-19445 and CVE-2026-19553 and incorporates
the earlier standard-library security fixes. See the
[supplier release](https://www.python.org/downloads/release/python-31316/).
The former HTML/tarfile overlays are removed after testing the actual new
standard library; do not copy older files over the fixed runtime.

Builds retain executable TLS hostname, HTML comment-stream and tarfile hardlink
relocation probes under `scripts/verify_cpython_*.py`. They use no network or
business inputs. The tarfile probe covers both `data` and `tar` filters.
First-party probes are Apache-2.0; the installed interpreter remains PSF-2.0,
with attribution retained in `licenses/PSF-2.0.txt`.

## Native Linux x86-64 bootstrap

Pinned uv 0.11.28 predates this Python patch release. `downloads.json` selects
the supported Linux x86-64 GNU distribution from upstream uv metadata at
`00e49e7e762f2ec1f730750df6c9eea581384cf5`, with the original supplier URL and
archive SHA-256. The same digest is published in the 20261003
[Python Build Standalone release](https://github.com/astral-sh/python-build-standalone/releases/tag/20261003).
uv verifies it before extraction; the interpreter and dependencies remain on
the project's Linux/E-drive storage. No installer/tool version changes or
insecure TLS/mirror options are required.

The descriptor is configured by `tool.uv.python-downloads-json-url` and is copied
into the API builder. It is not a second interpreter installer. Explicit native
installation can use `UV_PYTHON_DOWNLOADS=manual`; container builds continue to
disable interpreter downloads because the fixed interpreter is already present.
Cold bootstrap needs supplier access; runtime operation and cached locked installs
do not imply arbitrary online downloads. Other architectures require an existing
compatible interpreter or a reviewed supplier descriptor, not a silent fallback.
