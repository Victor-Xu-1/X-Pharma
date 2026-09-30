# CPython security backports

This directory vendors two unmodified CPython 3.13 standard-library files so container builds do not depend on GitHub availability. Docker builds verify their SHA-256 digests before installation and execute regression probes afterward.

| File | Upstream commit | SHA-256 |
|---|---|---|
| `html-parser.py` | `7933f4bf7131aa4140750f9404f5de0aa2969ced` | `4274e9112adf3fa57c7f9afa7c9b5c631456b18b7403cc627cc5027d02cdd2ae` |
| `tarfile.py` | `771d12dda5140313db0ac550292987975651bbde` | `0ad8c3869f9ab172fc5fc539528eb94c44d0745aef15dc8a0f1a773fae3b6c52` |

The files retain the Python Software Foundation license terms supplied by the pinned official Python base image. Update the file, commit, digest, regression probe and corresponding OpenVEX statement as one reviewed security change.
