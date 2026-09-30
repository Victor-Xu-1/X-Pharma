from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pharma_intel.ingest import cli


class FakeSession:
    def __init__(self, scalar_rows: list[Any]) -> None:
        self.scalar_rows = scalar_rows

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def scalars(self, _statement: object) -> list[Any]:
        return self.scalar_rows


def test_scan_registered_sources_counts_partial_scan_as_failure(monkeypatch: Any) -> None:
    source = SimpleNamespace(id="source-1", name="Controlled source")
    sessions = iter(
        [
            FakeSession(["tenant-1"]),
            FakeSession([source]),
            FakeSession([]),
        ]
    )

    class PartialDataFactory:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def scan_source(self, _source_id: str, _workflow_id: str) -> SimpleNamespace:
            return SimpleNamespace(state="partial", version_ids=[])

    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(cli, "get_session_factory", lambda: lambda: next(sessions))
    monkeypatch.setattr(cli, "set_tenant_context", lambda *_args: None)
    monkeypatch.setattr(cli, "build_object_store", lambda _settings: object())
    monkeypatch.setattr(cli, "DataFactoryService", PartialDataFactory)

    assert cli.scan_registered_sources() == {
        "sources": 1,
        "versions": 0,
        "failed_sources": 1,
        "failed_versions": 0,
    }


def test_scan_registered_sources_isolates_version_failures(monkeypatch: Any) -> None:
    source = SimpleNamespace(id="source-1", name="Controlled source")
    sessions = iter([FakeSession(["tenant-1"]), FakeSession([source]), FakeSession([])])
    processed: list[str] = []

    class IsolatingDataFactory:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def scan_source(self, _source_id: str, _workflow_id: str) -> SimpleNamespace:
            return SimpleNamespace(state="succeeded", version_ids=["bad-version", "good-version"])

        def process_version(self, version_id: str, *, from_stage: str) -> SimpleNamespace:
            assert from_stage == "auto"
            processed.append(version_id)
            if version_id == "bad-version":
                raise ValueError("controlled model failure")
            return SimpleNamespace(error=None)

    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(cli, "get_session_factory", lambda: lambda: next(sessions))
    monkeypatch.setattr(cli, "set_tenant_context", lambda *_args: None)
    monkeypatch.setattr(cli, "build_object_store", lambda _settings: object())
    monkeypatch.setattr(cli, "DataFactoryService", IsolatingDataFactory)

    assert cli.scan_registered_sources() == {
        "sources": 1,
        "versions": 2,
        "failed_sources": 0,
        "failed_versions": 1,
    }
    assert processed == ["bad-version", "good-version"]
