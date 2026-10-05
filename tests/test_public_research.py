from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from pharma_intel.public_research.service import PublicResearchService
from pharma_intel.schemas.public_research import PublicResearchQuery


def _search(topic: str, payload: object, *, status: int = 200, media_type: str = "application/json"):
    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, content=json.dumps(payload).encode(), headers={"content-type": media_type})

    result = PublicResearchService(httpx.MockTransport(respond)).search(PublicResearchQuery(topic=topic, q="EGFR"))
    return result.results[0], seen


def test_target_search_preserves_provider_identity_and_species() -> None:
    result, seen = _search(
        "targets",
        {
            "targets": [
                {
                    "target_chembl_id": "CHEMBL203",
                    "pref_name": "Epidermal growth factor receptor",
                    "organism": "Homo sapiens",
                    "target_type": "SINGLE PROTEIN",
                }
            ],
            "page_meta": {"total_count": 17},
        },
    )
    assert result.status == "available" and result.total == 17
    assert result.records[0].fields["物种"] == "Homo sapiens"
    assert result.records[0].record_id == "CHEMBL203"
    assert result.records[0].url == "https://www.ebi.ac.uk/chembl/explore/target/CHEMBL203"
    assert seen[0].url.host == "www.ebi.ac.uk"
    assert seen[0].url.params["q"] == "EGFR"


def test_keyword_patents_are_explicit_historical_bibliography_not_families_or_legal_claims() -> None:
    result, seen = _search(
        "patents",
        {
            "hitCount": 2046,
            "resultList": {
                "result": [
                    {
                        "id": "US2012041070",
                        "source": "PAT",
                        "title": "EGFR inhibitors",
                        "firstPublicationDate": "2011-09-30",
                    }
                ]
            },
        },
    )
    assert result.records[0].category == "patent_bibliography"
    assert result.records[0].published_on == "2011-09-30"
    assert "历史" in result.scope_note and "法律状态" in result.scope_note
    assert "family_identifier" not in result.records[0].fields
    assert "SRC:PAT" in seen[0].url.params["query"]


@pytest.mark.parametrize(
    ("status", "media", "payload"),
    [
        (403, "text/html", {}),
        (200, "text/html", {}),
        (200, "application/json", {"unexpected": []}),
    ],
)
def test_upstream_failure_or_invalid_contract_is_not_presented_as_empty(
    status: int, media: str, payload: object
) -> None:
    result, _seen = _search("targets", payload, status=status, media_type=media)
    assert result.status == "unavailable" and result.total is None and result.records == []


def test_compound_not_found_is_not_a_claim_that_no_patents_exist() -> None:
    result, _seen = _search("compound_patents", {"Fault": {"Code": "PUGREST.NotFound"}}, status=404)
    assert result.status == "empty" and "化合物" in result.scope_note
    assert result.total is None


def test_official_conditions_return_named_source_terms_not_approved_indications() -> None:
    result, _seen = _search(
        "conditions",
        {
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {"nctId": "NCT07672483", "briefTitle": "Study"},
                        "conditionsModule": {"conditions": ["EGFR-positive solid tumor"]},
                    }
                }
            ],
            "totalCount": 1,
        },
    )
    assert result.records[0].category == "study_condition_label"
    assert "不代表获批" in result.scope_note and result.total is None
    assert result.records[0].url == "https://clinicaltrials.gov/study/NCT07672483"


def test_external_identifiers_cannot_inject_a_provider_url() -> None:
    result, _seen = _search(
        "targets",
        {"targets": [{"target_chembl_id": "../../secrets", "pref_name": "Unknown"}], "page_meta": {"total_count": 1}},
    )
    assert result.status == "unavailable"


@pytest.mark.parametrize("query", ["", " ", "EGFR\ninternal", "x" * 121])
def test_public_query_is_nonempty_bounded_and_rejects_control_characters(query: str) -> None:
    with pytest.raises(ValidationError):
        PublicResearchQuery(topic="targets", q=query)


def test_public_transport_rejects_a_response_larger_than_one_megabyte() -> None:
    def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b" " * (1_048_576 + 1), headers={"content-type": "application/json"})

    result = PublicResearchService(httpx.MockTransport(respond)).search(PublicResearchQuery(topic="targets", q="EGFR"))
    assert result.results[0].status == "unavailable"
