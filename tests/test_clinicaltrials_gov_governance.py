from __future__ import annotations

import json

from pharma_intel.governance.schemas import ExtractionEnvelope, TrialFact
from pharma_intel.governance.service import (
    _enforce_profiled_identity,
    _profiled_model_text,
    _validate_profiled_response,
)


def _trial_envelope(*, registry_id: str = "NCT00000001", title: str = "Official EGFR study") -> ExtractionEnvelope:
    return ExtractionEnvelope.model_validate(
        {
            "document_type": "clinical_trial_registry",
            "document_summary": "Official study",
            "facts": [
                {
                    "fact_kind": "trial",
                    "trial": {
                        "entity_type": "clinical_trial",
                        "name": title,
                        "external_ids": {"NCT": registry_id},
                    },
                    "registry_name": "ClinicalTrials.gov",
                    "registry_id": registry_id,
                    "official_title": title,
                    "citation": {"quote": registry_id, "confidence": 1},
                }
            ],
            "warnings": [],
        }
    )


def test_clinicaltrials_profile_is_bounded_and_preserves_authoritative_identity() -> None:
    source = {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT00000001",
                "officialTitle": "Official EGFR study",
                "briefTitle": "Brief study",
            },
            "statusModule": {"overallStatus": "RECRUITING"},
            "contactsLocationsModule": {
                "locations": [{"facility": f"Site {index}", "country": "China"} for index in range(40)]
            },
            "outcomesModule": {"primaryOutcomes": [{"measure": f"Outcome {index}"} for index in range(40)]},
            "eligibilityModule": {"eligibilityCriteria": "x" * 10_000},
            "referencesModule": {"references": [{"pmid": str(index)} for index in range(100)]},
        },
        "resultsSection": {"largePayload": "x" * 100_000},
        "hasResults": True,
    }

    model_text, identity = _profiled_model_text(
        json.dumps(source, separators=(",", ":")),
        "clinicaltrials_gov",
    )
    profiled = json.loads(model_text)

    assert identity == {"registry_id": "NCT00000001", "official_title": "Official EGFR study"}
    assert len(profiled["protocolSection"]["contactsLocationsModule"]["locations"]) == 10
    assert len(profiled["protocolSection"]["outcomesModule"]["primaryOutcomes"]) == 10
    assert "eligibilityCriteria" not in profiled["protocolSection"]["eligibilityModule"]
    assert "referencesModule" not in profiled["protocolSection"]
    assert "resultsSection" not in profiled


def test_clinicaltrials_profile_enforces_authoritative_identity_before_validation() -> None:
    identity = {"registry_id": "NCT00000001", "official_title": "Official EGFR study"}

    corrected = _enforce_profiled_identity(
        _trial_envelope(registry_id="NCT00000002", title="Hallucinated title"),
        "clinicaltrials_gov",
        identity,
    )
    _validate_profiled_response(corrected, "clinicaltrials_gov", identity)
    fact = corrected.facts[0]
    assert isinstance(fact, TrialFact)
    assert fact.registry_id == "NCT00000001"
    assert fact.official_title == "Official EGFR study"
    assert fact.trial.name == "Official EGFR study"
    assert fact.trial.external_ids == {"NCT": "NCT00000001"}
