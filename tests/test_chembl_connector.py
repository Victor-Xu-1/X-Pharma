from __future__ import annotations

import json

import httpx
import pytest

from pharma_intel.config import Settings
from pharma_intel.ingest.chembl import (
    CHEMBL_API_ROOT,
    ChEMBLSourceConnector,
)
from pharma_intel.ingest.connectors import ConnectorTransportError
from pharma_intel.models import DataSource, DataSourceType


def _source() -> DataSource:
    return DataSource(
        id="chembl-source",
        tenant_id="tenant-1",
        name="ChEMBL EGFR",
        source_type=DataSourceType.CHEMBL,
        root_uri=CHEMBL_API_ROOT,
        owner="Public Biomedical Data Operations",
        data_classification="public",
        authorization_scopes=["public:chembl"],
        dataset_key="chembl",
        include_globs=["mechanisms/*.json"],
        exclude_globs=[],
        routing_rules=[{"target_chembl_id": "CHEMBL203", "max_records": 2, "page_size": 2}],
        stable_seconds=0,
        max_file_bytes=1_000_000,
        scan_interval_seconds=86_400,
        expected_freshness_seconds=604_800,
        rate_limit_per_minute=60,
    )


def _target() -> dict[str, object]:
    return {
        "target_chembl_id": "CHEMBL203",
        "pref_name": "Epidermal growth factor receptor",
        "target_type": "SINGLE PROTEIN",
        "organism": "Homo sapiens",
        "target_components": [
            {
                "accession": "P00533",
                "target_component_synonyms": [{"component_synonym": "EGFR", "syn_type": "GENE_SYMBOL"}],
            }
        ],
    }


def _mechanisms() -> list[dict[str, object]]:
    return [
        {
            "mec_id": 241,
            "target_chembl_id": "CHEMBL203",
            "molecule_chembl_id": "CHEMBL1201827",
            "action_type": "INHIBITOR",
            "mechanism_of_action": "Epidermal growth factor receptor erbB1 inhibitor",
            "max_phase": 4,
            "direct_interaction": 1,
            "molecular_mechanism": 1,
            "mechanism_refs": [],
        },
        {
            "mec_id": 242,
            "target_chembl_id": "CHEMBL203",
            "molecule_chembl_id": "CHEMBL25",
            "action_type": "INHIBITOR",
            "mechanism_of_action": "EGFR inhibitor",
            "max_phase": 3,
            "direct_interaction": 1,
            "molecular_mechanism": 1,
            "mechanism_refs": [],
        },
    ]


def _molecules() -> list[dict[str, object]]:
    return [
        {
            "molecule_chembl_id": "CHEMBL1201827",
            "pref_name": "PANITUMUMAB",
            "molecule_type": "Antibody",
            "max_phase": 4.0,
        },
        {
            "molecule_chembl_id": "CHEMBL25",
            "pref_name": "IMATINIB",
            "molecule_type": "Small molecule",
            "max_phase": 3.0,
        },
    ]


def test_chembl_connector_fetches_bounded_mechanisms_and_materializes_citations() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/target/CHEMBL203.json"):
            payload = _target()
        elif request.url.path.endswith("/mechanism.json"):
            payload = {"mechanisms": _mechanisms(), "page_meta": {"total_count": 2}}
        elif request.url.path.endswith("/molecule.json"):
            requested = set(request.url.params["molecule_chembl_id__in"].split(","))
            payload = {"molecules": [item for item in _molecules() if item["molecule_chembl_id"] in requested]}
        else:
            raise AssertionError(f"unexpected ChEMBL request: {request.url}")
        return httpx.Response(
            200,
            headers={"content-type": "application/json; charset=utf-8"},
            content=json.dumps(payload).encode(),
        )

    connector = ChEMBLSourceConnector(Settings(), transport=httpx.MockTransport(handler))
    batch = connector.discover(_source())

    assert [item.logical_path for item in batch.objects] == [
        "mechanisms/CHEMBL203/241.json",
        "mechanisms/CHEMBL203/242.json",
    ]
    assert batch.cursor["object_count"] == 2
    assert batch.cursor["reported_total_count"] == 2
    assert len(requests) == 3
    assert requests[1].url.params["target_chembl_id"] == "CHEMBL203"
    with connector.materialize(batch.objects[0]) as snapshot:
        document = json.loads(snapshot.read_text(encoding="utf-8"))
    assert document["provider"] == "ChEMBL"
    assert document["molecule"]["pref_name"] == "PANITUMUMAB"
    assert document["target"]["gene_symbol"] == "EGFR"
    assert document["target"]["uniprot_accession"] == "P00533"
    assert document["citation"]["locator"] == "mechanism:241"
    assert "mechanism_of_action=Epidermal growth factor receptor erbB1 inhibitor" in document["citation"]["quote"]
    assert snapshot.exists() is False


def test_chembl_connector_fails_closed_on_transport_and_configuration_errors() -> None:
    connector = ChEMBLSourceConnector(
        Settings(),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(429, headers={"content-type": "application/json"})
        ),
    )
    with pytest.raises(ConnectorTransportError, match="ChEMBL target request returned HTTP 429"):
        connector.discover(_source())

    invalid = _source()
    invalid.root_uri = "https://example.test/"
    invalid.authorization_scopes = []
    invalid.data_classification = "internal"
    invalid.stable_seconds = 1
    invalid.rate_limit_per_minute = 61
    invalid.routing_rules = []
    assert connector.validate_configuration(invalid) == [
        f"ChEMBL sources must use {CHEMBL_API_ROOT}",
        "ChEMBL sources must use the public data classification",
        "ChEMBL sources require authorization scope public:chembl",
        "ChEMBL sources require stable_seconds=0",
        "ChEMBL sources cannot exceed 60 requests per minute",
        "ChEMBL sources require exactly one routing rule",
    ]


def test_chembl_connector_rejects_duplicate_mechanism_ids() -> None:
    duplicated = _mechanisms()
    duplicated[1]["mec_id"] = duplicated[0]["mec_id"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/target/CHEMBL203.json"):
            payload = _target()
        elif request.url.path.endswith("/mechanism.json"):
            payload = {"mechanisms": duplicated, "page_meta": {"total_count": 2}}
        else:
            raise AssertionError(request.url)
        return httpx.Response(200, headers={"content-type": "application/json"}, json=payload)

    connector = ChEMBLSourceConnector(Settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(ConnectorTransportError, match="duplicate mec_id"):
        connector.discover(_source())
