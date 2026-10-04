from __future__ import annotations

import httpx
import pytest

from pharma_intel.config import Settings
from pharma_intel.ingest.chembl import ChEMBLSourceConnector
from pharma_intel.ingest.clinicaltrials import ClinicalTrialsGovSourceConnector
from pharma_intel.ingest.connectors import ConnectorConfigurationError
from tests.test_chembl_connector import _mechanisms, _molecules, _target
from tests.test_chembl_connector import _source as chembl_source
from tests.test_clinicaltrials_gov_connector import _source as trial_source
from tests.test_clinicaltrials_gov_connector import _study


def test_continuous_trials_resume_after_the_batch_budget() -> None:
    source = trial_source()
    source.routing_rules[0].update(sync_mode="continuous", start_date="2026-07-01", max_records=1, page_size=1)
    observed_tokens: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        token = request.url.params.get("pageToken")
        observed_tokens.append(token)
        number = {None: 1, "page-2": 2, "page-3": 3}[token]
        payload: dict[str, object] = {
            "studies": [_study(f"NCT{number:08d}", updated="2026-07-28", title=f"Study {number}")],
            "totalCount": 3,
        }
        if number < 3:
            payload["nextPageToken"] = f"page-{number + 1}"
        assert request.url.params["filter.advanced"] == "AREA[LastUpdatePostDate]RANGE[2026-07-01,2026-07-31]"
        return httpx.Response(200, json=payload)

    connector = ClinicalTrialsGovSourceConnector(Settings(), transport=httpx.MockTransport(handler))
    collected: list[str] = []
    for _ in range(3):
        batch = connector.discover(source)
        source.connector_cursor = batch.cursor
        collected.extend(item.logical_path for item in batch.objects)

    assert observed_tokens == [None, "page-2", "page-3"]
    assert len(set(collected)) == 3
    assert source.connector_cursor["sync_state"]["window_start"] == "2026-08-01"
    assert source.connector_cursor["sync_state"]["pending"] is True


def test_continuous_chembl_resumes_with_a_stable_mechanism_identifier() -> None:
    source = chembl_source()
    source.routing_rules[0].update(sync_mode="continuous", max_records=1, page_size=1)
    observed_ids: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/target/CHEMBL203.json"):
            return httpx.Response(200, json=_target())
        if request.url.path.endswith("/molecule.json"):
            requested = request.url.params["molecule_chembl_id__in"].split(",")
            return httpx.Response(
                200,
                json={"molecules": [item for item in _molecules() if item["molecule_chembl_id"] in requested]},
            )
        assert request.url.path.endswith("/mechanism.json")
        after = int(request.url.params["mec_id__gt"])
        observed_ids.append(after)
        remaining = [item for item in _mechanisms() if int(str(item["mec_id"])) > after]
        assert request.url.params["order_by"] == "mec_id"
        return httpx.Response(200, json={"mechanisms": remaining[:1], "page_meta": {"total_count": len(remaining)}})

    connector = ChEMBLSourceConnector(Settings(), transport=httpx.MockTransport(handler))
    first = connector.discover(source)
    source.connector_cursor = first.cursor
    second = connector.discover(source)
    source.connector_cursor = second.cursor
    third = connector.discover(source)

    assert observed_ids == [0, 241, 0]
    assert first.objects[0].logical_path.endswith("/241.json")
    assert second.objects[0].logical_path.endswith("/242.json")
    completed_state = second.cursor["sync_state"]
    assert isinstance(completed_state, dict)
    assert completed_state["pending"] is False
    assert third.objects[0].logical_path == first.objects[0].logical_path


def test_checkpoint_cannot_be_reused_for_another_query() -> None:
    source = trial_source()
    source.routing_rules[0].update(sync_mode="continuous", start_date="2026-07-01", max_records=1, page_size=1)
    connector = ClinicalTrialsGovSourceConnector(
        Settings(),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "studies": [_study("NCT00000001", updated="2026-07-01", title="One")],
                    "nextPageToken": "next",
                    "totalCount": 2,
                },
            )
        ),
    )
    source.connector_cursor = connector.discover(source).cursor
    source.routing_rules[0]["query_term"] = "Another query"

    with pytest.raises(ConnectorConfigurationError, match="configuration"):
        connector.discover(source)
