from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from pharma_intel.operations_contract import OperationsContractError, verify_operations_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "deploy/operations/operations-contract.yaml"


def _mutated_contract(tmp_path: Path, mutate: Callable[[dict[str, Any]], None]) -> Path:
    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    mutate(document)
    output = tmp_path / "operations-contract.yaml"
    output.write_text(yaml.safe_dump(document), encoding="utf-8")
    return output


def test_operations_contract_covers_services_slos_alerts_and_responsibilities() -> None:
    report = verify_operations_contract(CONTRACT, ROOT)
    assert report["status"] == "passed"
    assert report["service_count"] == 10
    assert report["objective_count"] == report["alert_count"] == 13
    assert report["production_claim"] is False
    assert "http.server.duration" in cast(list[str], report["metrics"])
    assert "pharma.mcp.commercial.calls" in cast(list[str], report["metrics"])
    assert "pharma.web.vitals.duration" in cast(list[str], report["metrics"])
    assert "pharma.web.vitals.cls" in cast(list[str], report["metrics"])
    assert "runbooks/incident-response.md" in cast(list[str], report["runbooks"])

    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    clamav_objective = next(item for item in document["objectives"] if item["id"] == "clamav-scan-availability")
    assert clamav_objective["indicator"] == {
        "metric": "pharma.ingestion.operations",
        "measurement": "success_ratio",
        "filters": {"operation": "scan"},
    }
    clamav_alert = next(item for item in document["alerts"] if item["id"] == "clamav-scan-unavailable")
    assert clamav_alert["objective"] == clamav_objective["id"]
    workspace_objectives = {
        item["id"]: item["indicator"] for item in document["objectives"] if item["id"].startswith("workspace-")
    }
    assert workspace_objectives == {
        "workspace-cls": {
            "metric": "pharma.web.vitals.cls",
            "measurement": "p75_ratio",
            "filters": {"web_vital.name": "cls"},
        },
        "workspace-inp": {
            "metric": "pharma.web.vitals.duration",
            "measurement": "p75_milliseconds",
            "filters": {"web_vital.name": "inp"},
        },
        "workspace-lcp": {
            "metric": "pharma.web.vitals.duration",
            "measurement": "p75_milliseconds",
            "filters": {"web_vital.name": "lcp"},
        },
        "workspace-ttfb": {
            "metric": "pharma.web.vitals.duration",
            "measurement": "p75_milliseconds",
            "filters": {"web_vital.name": "ttfb"},
        },
    }


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda document: document["objectives"][0]["indicator"].update(metric="unknown.metric"), "unknown metric"),
        (lambda document: document["alerts"].pop(), "Objectives without alerts"),
        (lambda document: document["alerts"][0].update(runbook="../outside.md"), "unsafe runbook"),
        (lambda document: document["responsibilities"].pop("on_call"), "missing responsibilities"),
    ],
)
def test_operations_contract_rejects_incomplete_or_unsafe_semantics(
    tmp_path: Path,
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    contract = _mutated_contract(tmp_path, mutation)
    with pytest.raises(OperationsContractError, match=message):
        verify_operations_contract(contract, ROOT)
