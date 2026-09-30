from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.record_consistency_probe import _atomic_write, _canonical, _same


def test_canonical_requires_every_governed_field() -> None:
    with pytest.raises(RuntimeError, match="omitted fields"):
        _canonical({"id": "activity-1"}, ("id", "source_version_id"), "activity")


def test_same_rejects_cross_entry_field_drift() -> None:
    with pytest.raises(RuntimeError, match="drifted fields"):
        _same(
            {"id": "activity-1", "source_document_id": "document-1"},
            {"id": "activity-1", "source_document_id": "document-2"},
            ("id", "source_document_id"),
            "Web/MCP activity",
        )


def test_atomic_evidence_write_is_private_and_cannot_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "record-consistency.json"
    _atomic_write(output, {"status": "passed"})

    assert json.loads(output.read_text(encoding="utf-8")) == {"status": "passed"}
    assert output.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        _atomic_write(output, {"status": "changed"})
