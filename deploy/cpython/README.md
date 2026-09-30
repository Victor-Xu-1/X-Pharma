# CPython security backports

This directory vendors two unmodified CPython 3.13 standard-library files so container builds do not depend on GitHub availability. Docker builds verify their SHA-256 digests before installation and execute regression probes afterward.

| File | Upstream commit | SHA-256 |
|---|---|---|
| `html-parser.py` | `7933f4bf7131aa4140750f9404f5de0aa2969ced` | `4274e9112adf3fa57c7f9afa7c9b5c631456b18b7403cc627cc5027d02cdd2ae` |
| `tarfile.py` | `9c17bace90f88dfba6d0e2fe23c8e7ae35f83955` | `0fd87b49826f745c16e3ee68b2390a206b2dfcfe9a0b1118bd7fcd7c06deaff1` |

The files retain the Python Software Foundation license terms supplied by the pinned official Python base image. Update the file, commit, digest, regression probe and corresponding OpenVEX statement as one reviewed security change.

`scripts/verify_cpython_tarfile.py` checks hardlink relocation using the real installed parser and both `data` and `tar` extraction filters. The 3.13 maintenance backport includes the CVE-2026-82049 fix and its follow-up for filters returning `None`; old streaming EOF and hardlink fallback protections remain present. First-party probe code is Apache-2.0; the two unmodified supplier files retain PSF-2.0 attribution.
