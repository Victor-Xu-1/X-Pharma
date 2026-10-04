from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest

from pharma_intel.config import Settings
from pharma_intel.ingest.chembl import CHEMBL_API_ROOT, ChEMBLSourceConnector
from pharma_intel.ingest.clinicaltrials import ClinicalTrialsGovSourceConnector
from pharma_intel.ingest.connectors import ConnectorTransportError
from tests.test_chembl_connector import _source as chembl_source
from tests.test_chembl_connector import _target
from tests.test_clinicaltrials_gov_connector import _source as trials_source


@pytest.mark.parametrize("kind", ["clinicaltrials_gov", "chembl"])
@pytest.mark.parametrize("declared_length", [False, True])
def test_official_api_stops_stream_before_parsing_an_oversized_body(kind: str, declared_length: bool) -> None:
    reads: list[int] = []
    closed: list[bool] = []
    payload: dict[str, object] = (
        {"studies": [], "padding": "x" * 5000}
        if kind == "clinicaltrials_gov"
        else {
            **_target(),
            "padding": "x" * 5000,
        }
    )
    content = json.dumps(payload).encode()

    class MeasuredStream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            for index, chunk in enumerate((content[:1024], content[1024:2048], content[2048:])):
                reads.append(index)
                yield chunk

        def close(self) -> None:
            closed.append(True)

    headers = {"content-type": "application/json"}
    if declared_length:
        headers["content-length"] = str(len(content))
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            headers=headers,
            stream=MeasuredStream(),
        )
    )
    settings = Settings(source_http_max_api_response_bytes=1024)
    message = "Content-Length exceeds the declared limit" if declared_length else "configured safety limit"
    with pytest.raises(ConnectorTransportError, match=message):
        if kind == "clinicaltrials_gov":
            ClinicalTrialsGovSourceConnector(settings, transport).discover(trials_source())
        else:
            ChEMBLSourceConnector(settings, transport)._request_json(
                chembl_source(),
                f"{CHEMBL_API_ROOT}target/CHEMBL203.json",
                {},
                "ChEMBL target",
                maximum_bytes=1_000_000,
            )
    assert reads == ([] if declared_length else [0, 1])
    assert closed == [True]
