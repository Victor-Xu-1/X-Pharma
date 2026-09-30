from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from pharma_intel.config import Settings
from pharma_intel.ingest.connectors import (
    CLINICALTRIALS_GOV_STUDIES_URL,
    ClinicalTrialsGovSourceConnector,
    ConnectorConfigurationError,
    ConnectorTransportError,
)
from pharma_intel.models import DataSource, DataSourceType


def _study(nct_id: str, *, updated: str, title: str) -> dict[str, object]:
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": nct_id,
                "briefTitle": title,
                "officialTitle": title,
            },
            "statusModule": {
                "overallStatus": "RECRUITING",
                "studyFirstPostDateStruct": {"date": "2025-01-01", "type": "ACTUAL"},
                "lastUpdatePostDateStruct": {"date": updated, "type": "ACTUAL"},
            },
        },
        "hasResults": False,
    }


def _source() -> DataSource:
    return DataSource(
        id="clinicaltrials-gov-source",
        tenant_id="tenant-1",
        name="ClinicalTrials.gov EGFR",
        source_type=DataSourceType.CLINICALTRIALS_GOV,
        root_uri=CLINICALTRIALS_GOV_STUDIES_URL,
        owner="Clinical Data Operations",
        data_classification="public",
        authorization_scopes=["public:clinicaltrials-gov"],
        dataset_key="clinical_trials",
        include_globs=["studies/*.json"],
        exclude_globs=[],
        routing_rules=[{"query_term": "EGFR", "max_records": 2, "page_size": 1}],
        stable_seconds=0,
        max_file_bytes=1_000_000,
        scan_interval_seconds=86_400,
        expected_freshness_seconds=172_800,
        rate_limit_per_minute=100_000,
    )


def test_clinicaltrials_gov_connector_paginates_hashes_and_materializes() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page_token = request.url.params.get("pageToken")
        if page_token is None:
            payload = {
                "studies": [_study("NCT00000001", updated="2026-07-28", title="First EGFR study")],
                "nextPageToken": "page-2",
                "totalCount": 7801,
            }
        else:
            payload = {
                "studies": [_study("NCT00000002", updated="2026-07-29", title="Second EGFR study")],
                "totalCount": 7801,
            }
        return httpx.Response(200, headers={"content-type": "application/json"}, json=payload)

    connector = ClinicalTrialsGovSourceConnector(
        Settings(source_http_connect_timeout_seconds=2, source_http_read_timeout_seconds=2),
        transport=httpx.MockTransport(handler),
    )
    batch = connector.discover(_source())

    assert [item.logical_path for item in batch.objects] == [
        "studies/NCT00000001.json",
        "studies/NCT00000002.json",
    ]
    assert batch.cursor["object_count"] == 2
    assert batch.cursor["reported_total_count"] == 7801
    assert len(str(batch.cursor["inventory_sha256"])) == 64
    assert requests[0].url.params["query.term"] == "EGFR"
    assert requests[0].url.params["pageSize"] == "1"
    assert requests[0].url.params["sort"] == "LastUpdatePostDate:desc"
    assert requests[1].url.params["pageToken"] == "page-2"
    assert batch.cursor["sort"] == "LastUpdatePostDate:desc"

    first = batch.objects[0]
    assert first.modified_at == datetime(2026, 7, 28, tzinfo=UTC)
    assert first.source_uri == "https://clinicaltrials.gov/study/NCT00000001"
    with connector.materialize(first) as snapshot:
        parsed = json.loads(snapshot.read_text(encoding="utf-8"))
        assert parsed["protocolSection"]["identificationModule"]["nctId"] == "NCT00000001"
        snapshot_path = snapshot
    assert not snapshot_path.exists()


def test_clinicaltrials_gov_connector_rejects_untrusted_configuration() -> None:
    connector = ClinicalTrialsGovSourceConnector(Settings())
    source = _source()
    source.root_uri = "https://example.test/api/v2/studies"
    source.credential_ref = "env://UNEXPECTED"
    source.data_classification = "confidential"
    source.authorization_scopes = []
    source.stable_seconds = 30
    source.routing_rules = []

    errors = connector.validate_configuration(source)

    assert errors == [
        f"ClinicalTrials.gov sources must use {CLINICALTRIALS_GOV_STUDIES_URL}",
        "ClinicalTrials.gov sources do not accept connector credentials",
        "ClinicalTrials.gov sources must use the public data classification",
        "ClinicalTrials.gov sources require authorization scope public:clinicaltrials-gov",
        "ClinicalTrials.gov sources require stable_seconds=0",
        "ClinicalTrials.gov sources require exactly one routing rule",
    ]

    invalid_cursor = _source()
    invalid_cursor.connector_cursor = {
        "schema_version": "1.0",
        "kind": "clinicaltrials_gov",
        "inventory_sha256": "not-a-sha256",
        "object_count": True,
        "reported_total_count": 1,
    }
    assert connector.validate_configuration(invalid_cursor) == ["ClinicalTrials.gov connector cursor is invalid"]


def test_clinicaltrials_gov_connector_preserves_safe_transport_diagnostics() -> None:
    connector = ClinicalTrialsGovSourceConnector(
        Settings(),
        transport=httpx.MockTransport(lambda _request: (_ for _ in ()).throw(httpx.ConnectTimeout("upstream timeout"))),
    )

    with pytest.raises(ConnectorTransportError, match=r"ClinicalTrials.gov request failed \(ConnectTimeout\)"):
        connector.discover(_source())


def test_clinicaltrials_gov_connector_rejects_malformed_official_payload() -> None:
    connector = ClinicalTrialsGovSourceConnector(
        Settings(),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json={"studies": [{"protocolSection": {}}]},
            )
        ),
    )

    try:
        connector.discover(_source())
    except ConnectorConfigurationError as exc:
        assert str(exc) == "ClinicalTrials.gov study is missing required identifiers"
    else:
        raise AssertionError("Malformed official payload must fail closed")
