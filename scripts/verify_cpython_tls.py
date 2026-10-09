"""Probe the installed CPython TLS hostname boundary without network traffic."""

from __future__ import annotations

import ssl


def verify_hostname_requirement() -> None:
    context = ssl.create_default_context()
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise RuntimeError("TLS client verification is not enabled")
    for hostname in (None, ""):
        try:
            context.wrap_bio(ssl.MemoryBIO(), ssl.MemoryBIO(), server_hostname=hostname)
        except ValueError:
            continue
        raise RuntimeError("TLS hostname verification silently accepts a missing server name")
    connection = context.wrap_bio(ssl.MemoryBIO(), ssl.MemoryBIO(), server_hostname="tls-probe.example.test")
    if connection.server_hostname != "tls-probe.example.test":
        raise RuntimeError("TLS client did not retain the explicit verification hostname")


if __name__ == "__main__":
    verify_hostname_requirement()
    print("tls_hostname_requirement=protected")
