from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from sqlalchemy.engine import URL

from scripts.mcp_anti_extraction_probe import (
    REPORT_SCHEMA,
    ProbeRejected,
    _atomic_write,
    _exception_tree_matches,
    _require_local_postgres,
)


def test_anti_extraction_report_schema_preserves_local_production_boundary() -> None:
    assert REPORT_SCHEMA == "pharma.mcp-anti-extraction-acceptance.v1"


def test_anti_extraction_probe_refuses_non_loopback_database() -> None:
    test_password = "-".join(("not", "a", "real", "secret"))
    with pytest.raises(RuntimeError, match="non-loopback"):
        _require_local_postgres(
            URL.create(
                "postgresql+psycopg",
                username="runtime",
                password=test_password,
                host="database.example.com",
                database="pharma",
            )
        )


def test_anti_extraction_report_is_private_atomic_and_non_overwriting(tmp_path: Path) -> None:
    output = tmp_path / "anti-extraction.json"
    document = {
        "status": "passed",
        "production_claim": False,
        "credentials_recorded": False,
    }
    _atomic_write(output, document)

    assert json.loads(output.read_text(encoding="utf-8")) == document
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        _atomic_write(output, document)


def test_anti_extraction_probe_recognizes_nested_transport_and_rejection_errors() -> None:
    nested = ExceptionGroup("transport", [ExceptionGroup("request", [ProbeRejected("denied")])])

    assert _exception_tree_matches(nested, (ProbeRejected,)) is True
    assert _exception_tree_matches(nested, (ValueError,)) is False
