from __future__ import annotations

import re
from pathlib import Path

import pytest

from pharma_intel.ingest.parser_resilience_probe import _adversarial_documents, probe_timeout_recovery
from pharma_intel.ingest.parsers import DocumentParseError, parse_document


def test_parser_timeout_probe_kills_child_and_recovers() -> None:
    report = probe_timeout_recovery()

    assert report["status"] == "passed"
    assert report["production_claim"] is False
    assert report["timeout_observed"] is True
    assert report["child_processes_after_timeout"] == 0
    assert report["recovery_parser_name"] == "text"
    assert re.fullmatch(r"[0-9a-f]{64}", str(report["recovery_text_sha256"]))


def test_adversarial_corpus_is_ephemeral_complete_and_rejected(tmp_path: Path) -> None:
    documents = _adversarial_documents(tmp_path)

    assert [name for name, _ in documents] == [
        "office_path_traversal",
        "office_duplicate_name",
        "office_symbolic_link",
        "office_member_fanout",
        "office_compression_ratio",
        "office_encrypted",
        "pdf_encrypted",
        "xml_external_entity",
        "scientific_malformed",
    ]
    for _, path in documents:
        with pytest.raises(DocumentParseError):
            parse_document(path, 100_000)
