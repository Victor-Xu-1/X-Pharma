from __future__ import annotations

import json
from typing import Any, cast

import httpx
import pytest
import respx

from pharma_intel.config import Settings
from pharma_intel.governance.model_gateway import (
    ModelGatewayError,
    OpenAICompatibleExtractionGateway,
    _chat_completions_endpoint,
)
from pharma_intel.governance.schemas import ClaimFact
from pharma_intel.governance.service import _profiled_model_text


def _response_payload() -> dict[str, object]:
    extracted = {
        "document_type": "report",
        "document_summary": "No facts",
        "facts": [],
        "warnings": [],
    }
    return {
        "id": "model-request-123",
        "model": "extractor-2026-07-01",
        "system_fingerprint": "fp_governed",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": json.dumps(extracted)},
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10},
    }


@respx.mock
def test_model_gateway_requires_schema_constrained_output() -> None:
    route = respx.post("https://model.test/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            headers={"X-Request-ID": "gateway-request-456"},
            json=_response_payload(),
        )
    )
    gateway = OpenAICompatibleExtractionGateway(
        Settings(
            ai_base_url="https://model.test",
            ai_api_key="secret",
            ai_model="extractor",
            ai_thinking_mode="disabled",
            ai_include_schema_in_prompt=True,
        )
    )

    result = gateway.extract("Untrusted document text")

    request = route.calls.last.request
    body = json.loads(request.content)
    assert request.headers["authorization"] == "Bearer secret"
    assert body["temperature"] == 0
    assert body["max_completion_tokens"] == 16_384
    assert body["thinking"] == {"type": "disabled"}
    assert "Authoritative JSON Schema:" in body["messages"][0]["content"]
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is False
    assert body["response_format"]["json_schema"]["schema"]["properties"]["facts"]["maxItems"] == 100
    schema = body["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["warnings"]["maxItems"] == 100
    assert "StructureFact" not in schema["$defs"]
    assert "structure" not in schema["properties"]["facts"]["items"]["discriminator"]["mapping"]
    claim_value = schema["$defs"]["ClaimFact"]["properties"]["value"]["anyOf"][0]
    assert claim_value["additionalProperties"] is False
    assert {"value", "unit", "status", "identifier"} <= set(claim_value["properties"])
    claim_variants = schema["$defs"]["ClaimFact"]["oneOf"]
    assert claim_variants[0]["properties"]["value"] == {"type": "null"}
    assert claim_variants[1]["properties"]["object_entity"] == {"type": "null"}
    assert claim_variants[1]["properties"]["value"] == claim_value
    external_ids = schema["$defs"]["EntityReference"]["properties"]["external_ids"]
    assert external_ids["additionalProperties"] is False
    assert {"HGNC", "UniProt", "ChEMBL", "PMID", "PMCID", "DOI"} <= set(external_ids["properties"])
    assert external_ids["properties"]["ChEMBL"] == {
        "type": "string",
        "maxLength": 4000,
        "pattern": r"^CHEMBL[0-9]{1,12}$",
    }
    assert external_ids["properties"]["DrugBank"]["pattern"] == r"^DB[0-9]{5}$"
    assert external_ids["properties"]["patent"]["pattern"] == r"^[A-Za-z]{2}[A-Za-z0-9 -]{1,58}$"
    assert "Return at most 100 highest-value supported facts." in body["messages"][0]["content"]
    assert "at most 4000 characters" in body["messages"][0]["content"]
    assert request.headers["x-client-request-id"]
    assert result.envelope.document_type == "report"
    assert result.input_tokens == 20
    assert result.output_tokens == 10
    assert result.model_name == "extractor-2026-07-01"
    assert result.system_fingerprint == "fp_governed"
    assert result.provider_request_id == "gateway-request-456"
    assert result.finish_reason == "stop"
    assert result.response_sha256 is not None


@respx.mock
def test_model_gateway_supports_prompt_only_providers_and_unwraps_json_fences() -> None:
    payload = _response_payload()
    choices = cast(list[dict[str, Any]], payload["choices"])
    message = cast(dict[str, Any], choices[0]["message"])
    message["content"] = "```json\n" + cast(str, message["content"]) + "\n```"
    route = respx.post("https://model.test/v1/chat/completions").mock(return_value=httpx.Response(200, json=payload))
    gateway = OpenAICompatibleExtractionGateway(
        Settings(
            ai_base_url="https://model.test",
            ai_api_key="secret",
            ai_model="extractor",
            ai_thinking_mode="disabled",
            ai_include_schema_in_prompt=True,
            ai_response_format_mode="prompt_only",
        )
    )

    result = gateway.extract("Untrusted document text")

    request_body = json.loads(route.calls.last.request.content)
    assert "response_format" not in request_body
    assert result.envelope.document_type == "report"


@respx.mock
def test_model_gateway_fails_over_after_bounded_retryable_provider_failure() -> None:
    primary = respx.post("https://primary.test/v1/chat/completions").mock(return_value=httpx.Response(503))
    fallback = respx.post("https://fallback.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_response_payload())
    )
    gateway = OpenAICompatibleExtractionGateway(
        Settings(
            ai_base_url="https://primary.test/v1",
            ai_api_key="primary-secret",
            ai_model="primary-model",
            ai_fallback_providers_json=json.dumps(
                [
                    {
                        "name": "fallback",
                        "base_url": "https://fallback.test/v1",
                        "api_key": "fallback-secret",
                        "model": "fallback-model",
                    }
                ]
            ),
            ai_request_attempts=1,
        )
    )

    result = gateway.extract("Untrusted document text")

    assert primary.called
    assert fallback.called
    assert result.provider_name == "fallback"
    assert json.loads(fallback.calls.last.request.content)["model"] == "fallback-model"
    assert (
        primary.calls.last.request.headers["x-client-request-id"]
        == fallback.calls.last.request.headers["x-client-request-id"]
    )


@respx.mock
def test_model_gateway_fails_over_after_primary_timeout() -> None:
    primary = respx.post("https://primary.test/v1/chat/completions").mock(
        side_effect=httpx.ReadTimeout("primary timed out")
    )
    fallback = respx.post("https://fallback.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_response_payload())
    )
    gateway = OpenAICompatibleExtractionGateway(
        Settings(
            ai_base_url="https://primary.test/v1",
            ai_api_key="primary-secret",
            ai_model="primary-model",
            ai_request_attempts=1,
            ai_fallback_providers_json=json.dumps(
                [
                    {
                        "name": "mimo",
                        "base_url": "https://fallback.test/v1",
                        "api_key": "fallback-secret",
                        "model": "mimo-v2.5",
                        "response_format_mode": "prompt_only",
                        "thinking_mode": "disabled",
                        "include_schema_in_prompt": True,
                        "request_attempts": 1,
                    }
                ]
            ),
        )
    )

    result = gateway.extract("Untrusted document text")

    assert primary.called
    assert fallback.called
    assert result.provider_name == "mimo"
    assert (
        primary.calls.last.request.headers["x-client-request-id"]
        == fallback.calls.last.request.headers["x-client-request-id"]
    )


@respx.mock
def test_model_gateway_applies_fallback_provider_protocol_overrides() -> None:
    primary = respx.post("https://primary.test/v1/chat/completions").mock(return_value=httpx.Response(503))
    fallback = respx.post("https://fallback.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_response_payload())
    )
    gateway = OpenAICompatibleExtractionGateway(
        Settings(
            ai_base_url="https://primary.test/v1",
            ai_api_key="primary-secret",
            ai_model="primary-model",
            ai_response_format_mode="json_object",
            ai_thinking_mode="enabled",
            ai_max_output_tokens_per_segment=512,
            ai_fallback_providers_json=json.dumps(
                [
                    {
                        "name": "fallback",
                        "base_url": "https://fallback.test/v1",
                        "api_key": "fallback-secret",
                        "model": "fallback-model",
                        "response_format_mode": "prompt_only",
                        "thinking_mode": "disabled",
                        "include_schema_in_prompt": True,
                        "max_output_tokens_per_segment": 4096,
                        "request_timeout_seconds": 45,
                        "request_attempts": 1,
                    }
                ]
            ),
            ai_request_attempts=1,
        )
    )

    result = gateway.extract("Untrusted document text")

    primary_body = json.loads(primary.calls.last.request.content)
    fallback_body = json.loads(fallback.calls.last.request.content)
    assert primary_body["response_format"] == {"type": "json_object"}
    assert primary_body["thinking"] == {"type": "enabled"}
    assert primary_body["max_completion_tokens"] == 512
    assert "response_format" not in fallback_body
    assert fallback_body["thinking"] == {"type": "disabled"}
    assert fallback_body["max_completion_tokens"] == 4096
    assert "Authoritative JSON Schema" in fallback_body["messages"][0]["content"]
    assert result.provider_name == "fallback"


@respx.mock
def test_model_gateway_does_not_fail_over_on_non_retryable_provider_rejection() -> None:
    primary = respx.post("https://primary.test/v1/chat/completions").mock(
        return_value=httpx.Response(400, json={"error": "invalid request"})
    )
    fallback = respx.post("https://fallback.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_response_payload())
    )
    gateway = OpenAICompatibleExtractionGateway(
        Settings(
            ai_base_url="https://primary.test/v1",
            ai_api_key="primary-secret",
            ai_model="primary-model",
            ai_fallback_providers_json=json.dumps(
                [
                    {
                        "name": "fallback",
                        "base_url": "https://fallback.test/v1",
                        "api_key": "fallback-secret",
                        "model": "fallback-model",
                    }
                ]
            ),
            ai_request_attempts=1,
        )
    )

    with pytest.raises(ModelGatewayError, match="primary"):
        gateway.extract("Untrusted document text")

    assert primary.called
    assert not fallback.called


@respx.mock
def test_model_gateway_restricts_clinicaltrials_profile_to_one_trial_fact() -> None:
    payload = _response_payload()
    choices = cast(list[dict[str, Any]], payload["choices"])
    message = cast(dict[str, Any], choices[0]["message"])
    message["content"] = json.dumps(
        {
            "document_type": "clinical_trial_registry",
            "document_summary": "ClinicalTrials.gov study",
            "facts": [
                {
                    "fact_kind": "trial",
                    "trial": {
                        "entity_type": "clinical_trial",
                        "name": "Official EGFR study",
                        "external_ids": {"NCT": "NCT00000001"},
                    },
                    "registry_name": "ClinicalTrials.gov",
                    "registry_id": "NCT00000001",
                    "official_title": "Official EGFR study",
                    "startDate": "2006-10",
                    "completionDate": "2014-11-07",
                    "statusHistory": [{"status": "RECRUITING", "effectiveAt": "2006-10"}],
                    "interventions": [
                        {
                            "name": "Study drug",
                            "type": "DRUG",
                            "armGroupLabels": ["Arm A"],
                        }
                    ],
                    "citation": {"quote": "NCT00000001", "confidence": 1},
                }
            ],
            "warnings": [],
        }
    )
    route = respx.post("https://model.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, headers={"X-Request-ID": "profile-request"}, json=payload)
    )
    gateway = OpenAICompatibleExtractionGateway(
        Settings(ai_base_url="https://model.test", ai_api_key="secret", ai_model="extractor")
    )

    result = gateway.extract(
        '{"protocolSection":{"identificationModule":{"nctId":"NCT00000001"}}}',
        fact_kind_allowlist=frozenset({"trial"}),
        max_facts=1,
        source_profile="clinicaltrials_gov",
    )

    body = json.loads(route.calls.last.request.content)
    schema = body["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["facts"]["maxItems"] == 1
    assert schema["properties"]["facts"]["items"]["discriminator"]["mapping"] == {"trial": "#/$defs/TrialFact"}
    assert schema["properties"]["facts"]["items"]["oneOf"] == [{"$ref": "#/$defs/TrialFact"}]
    assert "Emit exactly one trial fact and no other fact kinds" in body["messages"][0]["content"]
    assert "Authoritative JSON Schema:" in body["messages"][0]["content"]
    assert result.envelope.facts[0].fact_kind == "trial"
    assert result.envelope.facts[0].interventions[0].arm_labels == ["Arm A"]
    assert result.envelope.facts[0].start_date is not None
    assert result.envelope.facts[0].start_date.isoformat() == "2006-10-01T00:00:00+00:00"
    assert result.envelope.facts[0].start_date_precision == "month"
    assert result.envelope.facts[0].completion_date is not None
    assert result.envelope.facts[0].completion_date.isoformat() == "2014-11-07T00:00:00+00:00"
    assert result.envelope.facts[0].completion_date_precision == "day"
    assert result.envelope.facts[0].status_history[0].effective_at.isoformat() == "2006-10-01T00:00:00+00:00"
    assert result.envelope.facts[0].status_history[0].effective_at_precision == "month"


@respx.mock
def test_model_gateway_retries_clinicaltrials_boundary_failures_with_compact_variant() -> None:
    first = _response_payload()
    first_choices = cast(list[dict[str, Any]], first["choices"])
    first_choices[0]["finish_reason"] = "length"

    second = _response_payload()
    second_choices = cast(list[dict[str, Any]], second["choices"])
    second_message = second_choices[0]["message"]
    second_message["content"] = json.dumps(
        {
            "document_type": "clinical_trial_registry",
            "document_summary": "ClinicalTrials.gov study",
            "facts": [
                {
                    "fact_kind": "trial",
                    "trial": {
                        "entity_type": "clinical_trial",
                        "name": "EGFR study",
                        "external_ids": {"NCT": "NCT00000001"},
                    },
                    "registry_name": "ClinicalTrials.gov",
                    "registry_id": "NCT00000001",
                    "official_title": "EGFR study",
                    "citation": {"quote": "NCT00000001", "confidence": 1},
                }
            ],
            "warnings": [],
        }
    )
    route = respx.post("https://model.test/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(200, headers={"X-Request-ID": "first"}, json=first),
            httpx.Response(200, headers={"X-Request-ID": "second"}, json=second),
        ]
    )
    gateway = OpenAICompatibleExtractionGateway(
        Settings(ai_base_url="https://model.test", ai_api_key="secret", ai_model="extractor")
    )

    result = gateway.extract(
        '{"protocolSection":{"identificationModule":{"nctId":"NCT00000001"}}}',
        fact_kind_allowlist=frozenset({"trial"}),
        max_facts=1,
        source_profile="clinicaltrials_gov",
    )

    assert route.call_count == 2
    retry_body = json.loads(route.calls.last.request.content)
    assert "Compact recovery mode" in retry_body["messages"][0]["content"]
    assert result.prompt_variant == "clinicaltrials_compact_retry"


@respx.mock
def test_model_gateway_uses_identity_projection_after_repeated_clinicaltrials_filtering() -> None:
    first = _response_payload()
    first_choices = cast(list[dict[str, Any]], first["choices"])
    first_choices[0]["finish_reason"] = "content_filter"

    second = _response_payload()
    second_choices = cast(list[dict[str, Any]], second["choices"])
    second_choices[0]["finish_reason"] = "content_filter"

    third = _response_payload()
    third_choices = cast(list[dict[str, Any]], third["choices"])
    third_message = third_choices[0]["message"]
    third_message["content"] = json.dumps(
        {
            "document_type": "clinical_trial_registry",
            "document_summary": "ClinicalTrials.gov study",
            "facts": [
                {
                    "fact_kind": "trial",
                    "trial": {
                        "entity_type": "clinical_trial",
                        "name": "EGFR study",
                        "external_ids": {"NCT": "NCT00000001"},
                    },
                    "registry_name": "ClinicalTrials.gov",
                    "registry_id": "NCT00000001",
                    "official_title": "EGFR study",
                    "citation": {"quote": "NCT00000001", "confidence": 1},
                }
            ],
            "warnings": [],
        }
    )
    route = respx.post("https://model.test/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(200, json=first),
            httpx.Response(200, json=second),
            httpx.Response(200, json=third),
        ]
    )
    gateway = OpenAICompatibleExtractionGateway(
        Settings(ai_base_url="https://model.test", ai_api_key="secret", ai_model="extractor")
    )

    result = gateway.extract(
        json.dumps(
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT00000001",
                        "briefTitle": "EGFR study",
                        "officialTitle": "EGFR study",
                    },
                    "conditionsModule": {"conditions": ["Sensitive condition"]},
                    "descriptionModule": {"briefSummary": "Long free text that must not be retried"},
                    "eligibilityModule": {"eligibilityCriteria": "Private criteria"},
                }
            }
        ),
        fact_kind_allowlist=frozenset({"trial"}),
        max_facts=1,
        source_profile="clinicaltrials_gov",
    )

    assert route.call_count == 3
    compact_body = json.loads(route.calls[1].request.content)
    identity_body = json.loads(route.calls[2].request.content)
    assert "Compact recovery mode" in compact_body["messages"][0]["content"]
    identity_input = identity_body["messages"][1]["content"]
    assert "NCT00000001" in identity_input
    assert "conditionsModule" not in identity_input
    assert "briefSummary" not in identity_input
    assert "eligibilityCriteria" not in identity_input
    assert result.prompt_variant == "clinicaltrials_identity_retry"


def test_clinicaltrials_profile_input_excludes_sensitive_free_text_and_bounds_collections() -> None:
    source = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT00000001", "briefTitle": "EGFR study"},
            "eligibilityModule": {
                "sex": "ALL",
                "minimumAge": "18 Years",
                "eligibilityCriteria": "sensitive criteria " * 500,
            },
            "contactsLocationsModule": {
                "centralContacts": [{"name": "Private contact", "phone": "555"}],
                "locations": [
                    {"facility": f"Facility {index}", "country": "US", "email": "private@example.com"}
                    for index in range(20)
                ],
            },
            "outcomesModule": {
                "primaryOutcomes": [
                    {"measure": f"Outcome {index}", "description": "description" * 100} for index in range(20)
                ]
            },
        }
    }

    profiled, identity = _profiled_model_text(
        json.dumps(source),
        "clinicaltrials_gov",
        max_string_chars=1200,
    )

    result = json.loads(profiled)
    protocol = result["protocolSection"]
    assert identity == {"registry_id": "NCT00000001", "official_title": "EGFR study"}
    assert "eligibilityCriteria" not in protocol["eligibilityModule"]
    assert "centralContacts" not in protocol["contactsLocationsModule"]
    assert len(protocol["contactsLocationsModule"]["locations"]) == 10
    assert set(protocol["contactsLocationsModule"]["locations"][0]) <= {
        "facility",
        "city",
        "state",
        "country",
        "status",
    }
    assert len(protocol["outcomesModule"]["primaryOutcomes"]) == 10
    assert len(protocol["outcomesModule"]["primaryOutcomes"][0]["description"]) <= 1200


@respx.mock
def test_model_gateway_restricts_pubmed_profile_to_metadata_claims() -> None:
    payload = _response_payload()
    route = respx.post("https://model.test/v1/chat/completions").mock(return_value=httpx.Response(200, json=payload))
    gateway = OpenAICompatibleExtractionGateway(
        Settings(ai_base_url="https://model.test", ai_api_key="secret", ai_model="extractor")
    )

    gateway.extract(
        "# EGFR inhibitor resistance\n\n- Provider: NCBI PubMed\n- PMID: 12345678",
        fact_kind_allowlist=frozenset({"claim"}),
        max_facts=5,
        source_profile="pubmed",
    )

    body = json.loads(route.calls.last.request.content)
    schema = body["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["facts"]["maxItems"] == 5
    assert schema["properties"]["facts"]["items"]["discriminator"]["mapping"] == {"claim": "#/$defs/ClaimFact"}
    assert "do not infer study results" in body["messages"][0]["content"]


@respx.mock
def test_model_gateway_drops_only_malformed_pubmed_claims_with_audit_warning() -> None:
    payload = _response_payload()
    choices = cast(list[dict[str, Any]], payload["choices"])
    message = cast(dict[str, Any], choices[0]["message"])
    content = json.loads(cast(str, message["content"]))
    valid_fact = {
        "fact_kind": "claim",
        "subject": {"entity_type": "target", "name": "EGFR"},
        "predicate": "is_publication_topic",
        "value": {"value": "supported"},
        "citation": {"quote": "EGFR inhibitor resistance", "confidence": 0.9},
    }
    invalid_fact = json.loads(json.dumps(valid_fact))
    invalid_fact["qualifiers"] = ["not", "an", "object"]
    content["facts"] = [invalid_fact, valid_fact]
    message["content"] = json.dumps(content)
    respx.post("https://model.test/v1/chat/completions").mock(return_value=httpx.Response(200, json=payload))
    gateway = OpenAICompatibleExtractionGateway(
        Settings(ai_base_url="https://model.test", ai_api_key="secret", ai_model="extractor")
    )

    result = gateway.extract(
        "# EGFR inhibitor resistance\n\n- Provider: NCBI PubMed\n- PMID: 12345678",
        fact_kind_allowlist=frozenset({"claim"}),
        max_facts=5,
        source_profile="pubmed",
    )

    assert len(result.envelope.facts) == 1
    assert result.envelope.facts[0].fact_kind == "claim"
    assert result.envelope.warnings[-1] == "Dropped 1 malformed PubMed metadata fact(s) before governance staging"


@respx.mock
def test_model_gateway_enables_structure_schema_only_for_explicit_source_representation() -> None:
    route = respx.post("https://model.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_response_payload())
    )
    gateway = OpenAICompatibleExtractionGateway(
        Settings(ai_base_url="https://model.test", ai_api_key="secret", ai_model="extractor")
    )

    gateway.extract("The source reports SMILES: CC for compound A.")

    schema = json.loads(route.calls.last.request.content)["response_format"]["json_schema"]["schema"]
    assert schema["$defs"]["StructureFact"]["properties"]["canonical_smiles"]["maxLength"] == 4000
    assert schema["properties"]["facts"]["items"]["discriminator"]["mapping"]["structure"] == ("#/$defs/StructureFact")


@respx.mock
def test_model_gateway_rejects_structure_fact_without_explicit_source_representation() -> None:
    payload = _response_payload()
    choices = cast(list[dict[str, Any]], payload["choices"])
    message = cast(dict[str, Any], choices[0]["message"])
    content = json.loads(message["content"])
    content["facts"] = [
        {
            "fact_kind": "structure",
            "subject": {"entity_type": "drug", "name": "Compound A", "external_ids": {}},
            "canonical_smiles": "CC",
            "standard_inchi": None,
            "standard_inchi_key": None,
            "molecular_formula": None,
            "citation": {"quote": "Compound A was tested", "locator": None, "confidence": 0.9},
        }
    ]
    message["content"] = json.dumps(content)
    respx.post("https://model.test/v1/chat/completions").mock(return_value=httpx.Response(200, json=payload))
    gateway = OpenAICompatibleExtractionGateway(
        Settings(ai_base_url="https://model.test", ai_api_key="secret", ai_model="extractor")
    )

    with pytest.raises(ModelGatewayError, match="structure facts require"):
        gateway.extract("Compound A was tested without a source-reported chemical representation.")


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://model.example.test", "https://model.example.test/v1/chat/completions"),
        ("https://model.example.test/v1", "https://model.example.test/v1/chat/completions"),
    ],
)
def test_model_gateway_normalizes_openai_service_root_without_duplicate_v1(
    base_url: str,
    expected: str,
) -> None:
    assert _chat_completions_endpoint(base_url) == expected


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}, "finish_reason"),
        ({"usage": {}}, "usage metadata"),
        ({"choices": []}, "exactly one choice"),
    ],
)
@respx.mock
def test_model_gateway_rejects_incomplete_or_unaccounted_responses(
    mutation: dict[str, object],
    message: str,
) -> None:
    payload = _response_payload()
    payload.update(mutation)
    respx.post("https://model.test/v1/chat/completions").mock(return_value=httpx.Response(200, json=payload))
    gateway = OpenAICompatibleExtractionGateway(
        Settings(ai_base_url="https://model.test", ai_api_key="secret", ai_model="extractor")
    )

    with pytest.raises(ModelGatewayError, match=message):
        gateway.extract("Untrusted document text")


@respx.mock
def test_model_gateway_rejects_response_larger_than_configured_limit() -> None:
    respx.post("https://model.test/v1/chat/completions").mock(return_value=httpx.Response(200, content=b"x" * 1025))
    gateway = OpenAICompatibleExtractionGateway(
        Settings(
            ai_base_url="https://model.test",
            ai_api_key="secret",
            ai_model="extractor",
            ai_max_response_bytes=1024,
        )
    )

    with pytest.raises(ModelGatewayError, match="byte limit"):
        gateway.extract("Untrusted document text")


@respx.mock
def test_model_gateway_accepts_omitted_default_dynamic_objects() -> None:
    payload = _response_payload()
    claim: dict[str, Any] = {
        "fact_kind": "claim",
        "subject": {"entity_type": "target", "name": "EGFR"},
        "predicate": "has_evidence",
        "value": {"value": "supported"},
        "citation": {"quote": "EGFR evidence", "confidence": 0.9},
    }
    choices = cast(list[dict[str, Any]], payload["choices"])
    message = cast(dict[str, Any], choices[0]["message"])
    content = json.loads(message["content"])
    content["facts"] = [claim]
    message["content"] = json.dumps(content)
    respx.post("https://model.test/v1/chat/completions").mock(return_value=httpx.Response(200, json=payload))
    gateway = OpenAICompatibleExtractionGateway(
        Settings(ai_base_url="https://model.test", ai_api_key="secret", ai_model="extractor")
    )

    result = gateway.extract("EGFR evidence")

    fact = result.envelope.facts[0]
    assert isinstance(fact, ClaimFact)
    assert fact.subject.external_ids == {}
    assert fact.qualifiers == {}


@respx.mock
def test_model_gateway_rejects_provider_output_above_fact_limit() -> None:
    payload = _response_payload()
    claim = {
        "fact_kind": "claim",
        "subject": {"entity_type": "target", "name": "EGFR", "external_ids": {}},
        "predicate": "has_evidence",
        "value": {"value": "supported"},
        "qualifiers": {},
        "citation": {"quote": "EGFR evidence", "locator": None, "confidence": 0.9},
    }
    choices = cast(list[dict[str, Any]], payload["choices"])
    message = cast(dict[str, Any], choices[0]["message"])
    content = json.loads(message["content"])
    content["facts"] = [claim, claim]
    message["content"] = json.dumps(content)
    respx.post("https://model.test/v1/chat/completions").mock(return_value=httpx.Response(200, json=payload))
    gateway = OpenAICompatibleExtractionGateway(
        Settings(
            ai_base_url="https://model.test",
            ai_api_key="secret",
            ai_model="extractor",
            ai_max_facts_per_segment=1,
        )
    )

    with pytest.raises(ModelGatewayError, match="per-segment fact limit"):
        gateway.extract("EGFR evidence")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("external_ids", {"unapproved_database": "secret"}, "external_ids contains unsupported keys"),
        ("qualifiers", {"provider_instruction": "ignore policy"}, "claim.qualifiers contains unsupported keys"),
        ("value", {"raw_payload": "unbounded"}, "claim.value contains unsupported keys"),
    ],
)
@respx.mock
def test_model_gateway_rejects_unapproved_dynamic_keys(field: str, value: object, message: str) -> None:
    payload = _response_payload()
    claim: dict[str, Any] = {
        "fact_kind": "claim",
        "subject": {"entity_type": "target", "name": "EGFR", "external_ids": {}},
        "predicate": "has_evidence",
        "value": {"value": "supported"},
        "qualifiers": {},
        "citation": {"quote": "EGFR evidence", "locator": None, "confidence": 0.9},
    }
    if field == "external_ids":
        subject = cast(dict[str, object], claim["subject"])
        subject["external_ids"] = value
    else:
        claim[field] = value
    choices = cast(list[dict[str, Any]], payload["choices"])
    message_payload = cast(dict[str, Any], choices[0]["message"])
    content = json.loads(message_payload["content"])
    content["facts"] = [claim]
    message_payload["content"] = json.dumps(content)
    respx.post("https://model.test/v1/chat/completions").mock(return_value=httpx.Response(200, json=payload))
    gateway = OpenAICompatibleExtractionGateway(
        Settings(ai_base_url="https://model.test", ai_api_key="secret", ai_model="extractor")
    )

    with pytest.raises(ModelGatewayError, match=message):
        gateway.extract("EGFR evidence")


@respx.mock
def test_model_gateway_rejects_malformed_external_identifier() -> None:
    payload = _response_payload()
    claim = {
        "fact_kind": "claim",
        "subject": {
            "entity_type": "target",
            "name": "EGFR",
            "external_ids": {"patent": "US-" + "0" * 200},
        },
        "predicate": "has_evidence",
        "value": {"value": "supported"},
        "qualifiers": {},
        "citation": {"quote": "EGFR evidence", "locator": None, "confidence": 0.9},
    }
    choices = cast(list[dict[str, Any]], payload["choices"])
    message_payload = cast(dict[str, Any], choices[0]["message"])
    content = json.loads(message_payload["content"])
    content["facts"] = [claim]
    message_payload["content"] = json.dumps(content)
    respx.post("https://model.test/v1/chat/completions").mock(return_value=httpx.Response(200, json=payload))
    gateway = OpenAICompatibleExtractionGateway(
        Settings(ai_base_url="https://model.test", ai_api_key="secret", ai_model="extractor")
    )

    with pytest.raises(ModelGatewayError, match="invalid patent identifier"):
        gateway.extract("EGFR evidence")


@respx.mock
def test_model_gateway_rejects_unapproved_response_model() -> None:
    respx.post("https://model.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_response_payload())
    )
    gateway = OpenAICompatibleExtractionGateway(
        Settings(
            ai_base_url="https://model.test",
            ai_api_key="secret",
            ai_model="approved-alias",
            ai_allowed_response_models_json='["approved-model-2026-07"]',
        )
    )

    with pytest.raises(ModelGatewayError, match="approved model allowlist"):
        gateway.extract("Untrusted document text")


@respx.mock
def test_model_gateway_retries_rate_limit_with_one_stable_client_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = respx.post("https://model.test/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(200, json=_response_payload()),
        ]
    )
    delays: list[float] = []
    monkeypatch.setattr("pharma_intel.governance.model_gateway.time.sleep", delays.append)
    gateway = OpenAICompatibleExtractionGateway(
        Settings(ai_base_url="https://model.test", ai_api_key="secret", ai_model="extractor")
    )

    result = gateway.extract("Untrusted document text")

    request_ids = [call.request.headers["x-client-request-id"] for call in route.calls]
    assert result.provider_request_id == "model-request-123"
    assert len(route.calls) == 2
    assert len(set(request_ids)) == 1
    assert delays == [2.0]


@pytest.mark.parametrize(
    "base_url",
    (
        "http://model.vendor.example/v1",
        "https://localhost/v1",
        "https://127.0.0.1:8443/v1",
    ),
)
def test_model_gateway_rejects_local_or_non_tls_transport(base_url: str) -> None:
    with pytest.raises(ModelGatewayError, match="HTTPS remote API root"):
        OpenAICompatibleExtractionGateway(
            Settings(
                ai_base_url=base_url,
                ai_api_key="secret",
                ai_model="extractor",
            )
        )
