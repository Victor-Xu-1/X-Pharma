from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from scripts.capture_ingestion_readiness import _validate_readiness
from scripts.release_evidence import ReleaseEvidenceError


def _document() -> dict[str, Any]:
    return {
        "schema": "pharma.ingestion-readiness.v1",
        "schema_version": 1,
        "status": "ready_for_source_registration",
        "production_claim": False,
        "real_source_automatic_ingestion_verified": False,
        "runtime": {
            "checks": [
                {"code": "temporal_enabled", "status": "pass"},
                {"code": "temporal_scheduler_enabled", "status": "pass"},
            ]
        },
        "inventory": {
            "registered_source_count": 0,
            "configuration_ready_source_count": 0,
            "blocked_source_count": 0,
        },
        "connectors": [
            {
                "connector_id": connector_id,
                "incremental": True,
                "replayable": True,
                "immutable_snapshot_required": True,
            }
            for connector_id in (
                "folder-v1",
                "http-manifest-v1",
                "clinicaltrials-gov-v2",
                "pubmed-eutilities-v1",
                "s3-snapshot-v1",
                "sftp-snapshot-v1",
                "smb-snapshot-v1",
            )
        ],
    }


def test_readiness_evidence_accepts_empty_platform_without_claiming_real_ingestion() -> None:
    document = _document()

    assert _validate_readiness(document) is document


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda document: document.update(status="blocked"), "readiness is blocked"),
        (lambda document: document.update(production_claim=True), "production claim"),
        (
            lambda document: document.update(real_source_automatic_ingestion_verified=True),
            "cannot substitute",
        ),
        (
            lambda document: document["inventory"].update(blocked_source_count=1),
            "blocking governance",
        ),
        (
            lambda document: document["connectors"].pop(),
            "connector capabilities",
        ),
        (
            lambda document: document["runtime"]["checks"][0].update(status="fail"),
            "runtime controls",
        ),
    ],
)
def test_readiness_evidence_fails_closed_for_incomplete_controls(
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    document = deepcopy(_document())
    mutation(document)

    with pytest.raises(ReleaseEvidenceError, match=message):
        _validate_readiness(document)
