from __future__ import annotations

import json
import re
from typing import Any

from pharma_intel.governance.contracts import GovernanceError
from pharma_intel.governance.model_gateway import ModelGatewayError
from pharma_intel.governance.schemas import ExtractionEnvelope, TrialFact


def _profiled_model_text(
    text: str,
    source_profile: str | None,
    *,
    max_string_chars: int = 4000,
) -> tuple[str, dict[str, str] | None]:
    if source_profile is None:
        return text, None
    if source_profile == "pubmed":
        return text, None
    if source_profile != "clinicaltrials_gov":
        raise GovernanceError("Unsupported source governance profile")
    try:
        study = json.loads(text)
        protocol = study["protocolSection"]
        identification = protocol["identificationModule"]
        nct_id = str(identification["nctId"])
        official_title = str(identification.get("officialTitle") or identification["briefTitle"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise GovernanceError("ClinicalTrials.gov source is missing its authoritative identity") from exc
    if re.fullmatch(r"NCT[0-9]{8}", nct_id) is None or not official_title.strip():
        raise GovernanceError("ClinicalTrials.gov source has an invalid authoritative identity")
    module_names = (
        "identificationModule",
        "statusModule",
        "sponsorCollaboratorsModule",
        "conditionsModule",
        "designModule",
        "armsInterventionsModule",
        "outcomesModule",
        "eligibilityModule",
        "contactsLocationsModule",
    )
    profiled_protocol = {name: protocol[name] for name in module_names if name in protocol}
    contacts = profiled_protocol.get("contactsLocationsModule")
    if isinstance(contacts, dict):
        locations = contacts.get("locations")
        if isinstance(locations, list):
            contacts["locations"] = [
                {key: location[key] for key in ("facility", "city", "state", "country", "status") if key in location}
                for location in locations[:10]
                if isinstance(location, dict)
            ]
        contacts.pop("centralContacts", None)
        contacts.pop("overallOfficials", None)
    outcomes = profiled_protocol.get("outcomesModule")
    if isinstance(outcomes, dict):
        for field in ("primaryOutcomes", "secondaryOutcomes", "otherOutcomes"):
            if isinstance(outcomes.get(field), list):
                outcomes[field] = [
                    {
                        key: outcome[key]
                        for key in ("measure", "type", "timeFrame", "description", "unitOfMeasure")
                        if key in outcome
                    }
                    for outcome in outcomes[field][:10]
                    if isinstance(outcome, dict)
                ]
    arms = profiled_protocol.get("armsInterventionsModule")
    if isinstance(arms, dict):
        for field in ("armGroups", "interventions"):
            if isinstance(arms.get(field), list):
                arms[field] = arms[field][:50]
    sponsors = profiled_protocol.get("sponsorCollaboratorsModule")
    if isinstance(sponsors, dict):
        if isinstance(sponsors.get("collaborators"), list):
            sponsors["collaborators"] = [
                {key: collaborator[key] for key in ("name", "class") if key in collaborator}
                for collaborator in sponsors["collaborators"][:10]
                if isinstance(collaborator, dict)
            ]
        lead_sponsor = sponsors.get("leadSponsor")
        if isinstance(lead_sponsor, dict):
            sponsors["leadSponsor"] = {key: lead_sponsor[key] for key in ("name", "class") if key in lead_sponsor}
    eligibility = profiled_protocol.get("eligibilityModule")
    if isinstance(eligibility, dict):
        profiled_protocol["eligibilityModule"] = {
            key: eligibility[key]
            for key in (
                "healthyVolunteers",
                "sex",
                "minimumAge",
                "maximumAge",
                "stdAges",
                "genderBased",
                "samplingMethod",
            )
            if key in eligibility
        }
    profiled = _bound_profile_strings(
        {
            "protocolSection": profiled_protocol,
            "hasResults": bool(study.get("hasResults")),
        },
        max_string_chars,
    )
    return (
        json.dumps(profiled, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        {"registry_id": nct_id, "official_title": official_title},
    )


def _bound_profile_strings(value: Any, max_string_chars: int) -> Any:
    if isinstance(value, str):
        return value[:max_string_chars]
    if isinstance(value, list):
        return [_bound_profile_strings(item, max_string_chars) for item in value]
    if isinstance(value, dict):
        return {key: _bound_profile_strings(item, max_string_chars) for key, item in value.items()}
    return value


def _validate_profiled_response(
    envelope: ExtractionEnvelope,
    source_profile: str | None,
    identity: dict[str, str] | None,
) -> None:
    if source_profile is None:
        return
    if source_profile == "pubmed":
        if any(fact.fact_kind != "claim" for fact in envelope.facts):
            raise ModelGatewayError("PubMed governance may return only claim facts")
        return
    if source_profile != "clinicaltrials_gov" or identity is None:
        raise ModelGatewayError("Source governance profile identity is invalid")
    if len(envelope.facts) != 1 or not isinstance(envelope.facts[0], TrialFact):
        raise ModelGatewayError("ClinicalTrials.gov governance must return exactly one trial fact")
    fact = envelope.facts[0]
    if fact.registry_name.casefold() != "clinicaltrials.gov" or fact.registry_id != identity["registry_id"]:
        raise ModelGatewayError("ClinicalTrials.gov governance changed the authoritative registry identity")
    if fact.official_title != identity["official_title"]:
        raise ModelGatewayError("ClinicalTrials.gov governance changed the authoritative official title")
    if identity["registry_id"] not in fact.trial.external_ids.values():
        raise ModelGatewayError("ClinicalTrials.gov governance omitted the authoritative NCT identifier")


def _enforce_profiled_identity(
    envelope: ExtractionEnvelope,
    source_profile: str | None,
    identity: dict[str, str] | None,
) -> ExtractionEnvelope:
    if source_profile is None:
        return envelope
    if source_profile == "pubmed":
        return envelope
    if source_profile != "clinicaltrials_gov" or identity is None:
        raise ModelGatewayError("Source governance profile identity is invalid")
    if len(envelope.facts) != 1 or not isinstance(envelope.facts[0], TrialFact):
        return envelope
    fact = envelope.facts[0]
    authoritative_trial = fact.trial.model_copy(
        update={
            "name": identity["official_title"],
            "external_ids": {"NCT": identity["registry_id"]},
        }
    )
    authoritative_fact = fact.model_copy(
        update={
            "trial": authoritative_trial,
            "registry_name": "ClinicalTrials.gov",
            "registry_id": identity["registry_id"],
            "official_title": identity["official_title"],
        }
    )
    return envelope.model_copy(update={"facts": [authoritative_fact]})
