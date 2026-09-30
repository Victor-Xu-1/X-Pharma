from __future__ import annotations

from pathlib import Path

import pytest

from pharma_intel.ingest import parser_mtls_probe


def test_parser_mtls_probe_runs_real_server_and_rejects_untrusted_clients() -> None:
    report = parser_mtls_probe.probe()

    assert report["status"] == "passed"
    assert report["mutual_tls"] is True
    assert report["valid_client_parse"] is True
    assert report["no_client_certificate_rejected"] is True
    assert report["rogue_client_rejected"] is True
    assert report["untrusted_server_rejected"] is True


def test_parser_mtls_probe_evidence_is_atomic_and_non_overwriting(tmp_path: Path) -> None:
    output = tmp_path / "mtls.json"

    parser_mtls_probe._write_atomic(output, b'{"status":"passed"}\n')

    assert output.stat().st_mode & 0o077 == 0
    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        parser_mtls_probe._write_atomic(output, b"replacement")
