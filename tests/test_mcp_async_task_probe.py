from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

import pytest

from scripts.mcp_async_task_probe import (
    REPORT_SCHEMA,
    _atomic_write,
    _exception_messages,
    _manifest_digest,
    _tamper_cursor,
)


def test_async_task_report_schema_preserves_isolated_scope() -> None:
    assert REPORT_SCHEMA == "pharma.mcp-async-task-interoperability.v1"


def test_async_task_cursor_tamper_changes_only_signature_payload() -> None:
    cursor = "signed-cursor-A"

    tampered = _tamper_cursor(cursor)

    assert tampered != cursor
    assert tampered[:-1] == cursor[:-1]


def test_async_task_manifest_digest_requires_authority_binding() -> None:
    manifest: dict[str, Any] = {
        "schema": "pharma.data-export-envelope.v1",
        "payload": {
            "dataset": "entities",
            "record_count": 2,
            "authority": "PostgreSQL tenant authority store",
        },
    }

    assert len(_manifest_digest(manifest, "test client")) == 64
    manifest["payload"]["record_count"] = 3
    with pytest.raises(RuntimeError, match="authority dataset"):
        _manifest_digest(manifest, "test client")


def test_async_task_exception_messages_preserve_nested_rejection_detail() -> None:
    nested = ExceptionGroup("transport", [ExceptionGroup("request", [RuntimeError("cursor signature invalid")])])

    assert _exception_messages(nested) == ["cursor signature invalid"]


def test_async_task_evidence_is_private_atomic_and_non_overwriting(tmp_path: Path) -> None:
    output = tmp_path / "mcp-async-task.json"
    document = {"status": "passed", "credentials_recorded": False}

    _atomic_write(output, document)

    assert json.loads(output.read_text(encoding="utf-8")) == document
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        _atomic_write(output, document)
