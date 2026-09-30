from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from pharma_intel.migration.ragflow_export import (
    MigrationDataset,
    RagflowMigrationError,
    ReadOnlyRagflowMigrationClient,
    export_queries,
)


@respx.mock
def test_offline_export_remaps_private_dataset_ids_and_writes_restricted_snapshot(tmp_path: Path) -> None:
    route = respx.post("https://ragflow.example.test/api/v1/retrieval").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "chunks": [
                        {
                            "content": "Evidence",
                            "document_id": "doc-1",
                            "document_name": "paper.pdf",
                            "dataset_id": "private-dataset-1",
                            "similarity": 0.91,
                            "positions": [[1, 2, 3, 4, 5]],
                            "document_metadata": {"source": "Y:/paper.pdf"},
                        }
                    ]
                },
            },
        )
    )
    output = tmp_path / "ragflow-export.json"
    client = ReadOnlyRagflowMigrationClient("https://ragflow.example.test", "migration-key")

    document = export_queries(
        client,
        [MigrationDataset("literature", "private-dataset-1")],
        ["EGFR"],
        limit=10,
        output=output,
    )

    assert document["record_count"] == 1
    assert document["records"][0]["dataset_key"] == "literature"
    assert "private-dataset-1" not in output.read_text(encoding="utf-8")
    assert output.stat().st_mode & 0o777 == 0o600
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer migration-key"
    assert json.loads(request.content)["dataset_ids"] == ["private-dataset-1"]


@respx.mock
def test_offline_export_rejects_unapproved_dataset_and_does_not_leave_output(tmp_path: Path) -> None:
    respx.post("https://ragflow.example.test/api/v1/retrieval").mock(
        return_value=httpx.Response(
            200,
            json={"code": 0, "data": {"chunks": [{"dataset_id": "outside-dataset", "content": "x"}]}},
        )
    )
    output = tmp_path / "rejected.json"
    client = ReadOnlyRagflowMigrationClient("https://ragflow.example.test", "migration-key")

    with pytest.raises(RagflowMigrationError, match="outside the approved"):
        export_queries(
            client,
            [MigrationDataset("literature", "private-dataset-1")],
            ["KRAS"],
            limit=10,
            output=output,
        )

    assert not output.exists()


@pytest.mark.parametrize(
    "base_url",
    [
        "http://ragflow.example.test",
        "https://user:password@ragflow.example.test",
        "https://ragflow.example.test?token=secret",
    ],
)
def test_offline_export_rejects_unsafe_endpoints(base_url: str) -> None:
    with pytest.raises(RagflowMigrationError):
        ReadOnlyRagflowMigrationClient(base_url, "migration-key")


def test_offline_export_requires_key_and_never_overwrites(tmp_path: Path) -> None:
    with pytest.raises(RagflowMigrationError, match="not configured"):
        ReadOnlyRagflowMigrationClient("http://127.0.0.1:9380", "")

    output = tmp_path / "existing.json"
    output.write_text("preserve", encoding="utf-8")

    class EmptyClient:
        base_url = "http://127.0.0.1:9380"

        @staticmethod
        def retrieve(_query: str, _dataset_ids: list[str], _limit: int) -> list[dict[str, object]]:
            return []

    with pytest.raises(RagflowMigrationError, match="already exists"):
        export_queries(
            EmptyClient(),  # type: ignore[arg-type]
            [MigrationDataset("literature", "dataset-1")],
            ["EGFR"],
            limit=10,
            output=output,
        )

    assert output.read_text(encoding="utf-8") == "preserve"


@pytest.mark.parametrize(
    "chunks, message",
    [
        (["not-an-object"], "invalid chunk"),
        ([{"dataset_id": "dataset-1"}, {"dataset_id": "dataset-1"}], "requested chunk limit"),
    ],
)
@respx.mock
def test_offline_export_rejects_malformed_or_excess_provider_results(
    tmp_path: Path,
    chunks: list[object],
    message: str,
) -> None:
    respx.post("https://ragflow.example.test/api/v1/retrieval").mock(
        return_value=httpx.Response(200, json={"code": 0, "data": {"chunks": chunks}})
    )
    client = ReadOnlyRagflowMigrationClient("https://ragflow.example.test", "migration-key")
    with pytest.raises(RagflowMigrationError, match=message):
        export_queries(
            client,
            [MigrationDataset("literature", "dataset-1")],
            ["EGFR"],
            limit=1,
            output=tmp_path / "rejected.json",
        )
