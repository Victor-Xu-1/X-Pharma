from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import pharma_intel.openapi_contract as openapi_contract
from pharma_intel.openapi_contract import OPENAPI_CONTRACT_VERSION, render_contract


def test_openapi_release_contract_is_current() -> None:
    contract_path = Path(__file__).parents[1] / "docs" / "openapi.json"

    assert contract_path.read_bytes() == render_contract()
    assert OPENAPI_CONTRACT_VERSION == "3.1.2"


def test_openapi_excludes_retired_fixed_research_artifact_contract() -> None:
    contract = json.loads(render_contract())

    assert all(not path.startswith("/api/v1/research-bundles") for path in contract["paths"])
    schemas = contract["components"]["schemas"]
    assert "ResearchBundleCreate" not in schemas
    assert "ResearchBundleRead" not in schemas


def test_openapi_cli_writes_atomically_and_detects_contract_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "nested" / "openapi.json"
    monkeypatch.setattr(sys, "argv", ["pharma-openapi", "--output", str(output)])

    openapi_contract.run()

    assert output.read_bytes() == render_contract()
    assert not output.with_suffix(".json.tmp").exists()

    monkeypatch.setattr(sys, "argv", ["pharma-openapi", "--output", str(output), "--check"])
    openapi_contract.run()

    output.write_text("{}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="2"):
        openapi_contract.run()


def test_openapi_renderer_rejects_unexpected_specification_version(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnexpectedVersionApp:
        @staticmethod
        def openapi() -> dict[str, str]:
            return {"openapi": "3.0.3"}

    monkeypatch.setattr(openapi_contract, "app", UnexpectedVersionApp())

    with pytest.raises(RuntimeError, match="Expected OpenAPI 3.1.2, got 3.0.3"):
        render_contract()
