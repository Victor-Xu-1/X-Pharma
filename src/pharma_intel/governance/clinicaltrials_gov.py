from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import ValidationError

from pharma_intel.governance.schemas import (
    Citation,
    EntityReference,
    TrialArmFact,
    TrialDesignFact,
    TrialEligibilityFact,
    TrialFact,
    TrialInterventionFact,
    TrialLocationFact,
    TrialOutcomeFact,
    TrialOutcomeResultFact,
    TrialResultDisclosureFact,
    TrialSponsorFact,
    TrialStatisticalAnalysisFact,
    TrialStatusHistoryFact,
)
from pharma_intel.models import EntityType, TrialResultDisclosureType

ADAPTER_NAME = "clinicaltrials_gov_v2"
ADAPTER_VERSION = "1.0.0"
OFFICIAL_API_ROOT = "https://clinicaltrials.gov/api/v2/studies"
OFFICIAL_STUDY_ROOT = "https://clinicaltrials.gov/study"
_NCT_ID = re.compile(r"NCT[0-9]{8}")
_INTERVENTION_PREFIX = re.compile(r"^[A-Za-z][A-Za-z _-]{0,40}:\s*")


@dataclass(frozen=True)
class ClinicalTrialsGovRecord:
    fact: TrialFact
    source_locator: str
    source_quote: str


def adapter_policy_manifest() -> dict[str, object]:
    return {
        "adapter": ADAPTER_NAME,
        "version": ADAPTER_VERSION,
        "source_schema": "ClinicalTrials.gov API v2 study JSON",
        "fact_kind": "trial",
        "identity_namespace": "clinicaltrials",
        "trusted_fields": [
            "registry identity",
            "study status and phase",
            "conditions",
            "interventions and arms",
            "sponsors and locations",
            "study design and eligibility",
            "registered outcomes and posted result measurements",
        ],
        "excluded_inferences": [
            "drug identity resolution",
            "target attribution",
            "therapy-line inference",
            "qualitative efficacy conclusions",
        ],
        "license": "ClinicalTrials.gov public data",
    }


def is_authorized_clinicaltrials_gov_asset(
    *,
    root_uri: str,
    logical_path: str,
    source_uri: str,
    file_name: str,
    extension: str,
    authorization_scopes: list[str],
) -> bool:
    expected_id = file_name.removesuffix(extension)
    return (
        root_uri == OFFICIAL_API_ROOT
        and extension.casefold() == ".json"
        and _NCT_ID.fullmatch(expected_id) is not None
        and logical_path == f"studies/{expected_id}.json"
        and source_uri == f"{OFFICIAL_STUDY_ROOT}/{expected_id}"
        and "public:clinicaltrials-gov" in authorization_scopes
    )


def parse_clinicaltrials_gov_snapshot(content: bytes) -> ClinicalTrialsGovRecord:
    if not content:
        raise ValueError("ClinicalTrials.gov snapshot is empty")
    try:
        study = json.loads(content)
        if not isinstance(study, dict):
            raise TypeError
        protocol = _mapping(study, "protocolSection")
        identification = _mapping(protocol, "identificationModule")
        status = _mapping(protocol, "statusModule")
        nct_id = _required_text(identification.get("nctId"), 20)
        official_title = _required_text(
            identification.get("officialTitle") or identification.get("briefTitle"),
            2000,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("ClinicalTrials.gov snapshot is missing its authoritative identity") from exc
    if _NCT_ID.fullmatch(nct_id) is None:
        raise ValueError("ClinicalTrials.gov snapshot has an invalid NCT identifier")

    citation_quote = _citation_quote(nct_id, status)
    citation = Citation(quote=citation_quote, locator="protocolSection", confidence=1)
    design_module = _optional_mapping(protocol.get("designModule"))
    arms_module = _optional_mapping(protocol.get("armsInterventionsModule"))
    outcomes_module = _optional_mapping(protocol.get("outcomesModule"))
    sponsors_module = _optional_mapping(protocol.get("sponsorCollaboratorsModule"))
    locations_module = _optional_mapping(protocol.get("contactsLocationsModule"))
    eligibility_module = _optional_mapping(protocol.get("eligibilityModule"))
    conditions_module = _optional_mapping(protocol.get("conditionsModule"))
    results_section = _optional_mapping(study.get("resultsSection"))

    start_date, start_precision = _date_struct(status.get("startDateStruct"))
    completion_date, completion_precision = _date_struct(status.get("completionDateStruct"))
    results_first_posted, _ = _date_struct(status.get("resultsFirstPostDateStruct"))
    last_update_posted, last_update_precision = _date_struct(status.get("lastUpdatePostDateStruct"))
    status_verified, status_verified_precision = _date_value(status.get("statusVerifiedDate"))

    fact_payload: dict[str, Any] = {
        "fact_kind": "trial",
        "trial": EntityReference(
            entity_type=EntityType.CLINICAL_TRIAL,
            name=_bounded_text(official_title, 500),
            external_ids={"clinicaltrials": nct_id},
        ),
        "registry_name": "ClinicalTrials.gov",
        "registry_id": nct_id,
        "official_title": official_title,
        "acronym": _optional_text(identification.get("acronym"), 240),
        "overall_status": _optional_text(status.get("overallStatus"), 120),
        "phases": _string_list(design_module.get("phases"), limit=20, item_limit=80),
        "study_type": _optional_text(design_module.get("studyType"), 120),
        "enrollment": _non_negative_int(_optional_mapping(design_module.get("enrollmentInfo")).get("count")),
        "start_date": start_date,
        "start_date_precision": start_precision,
        "completion_date": completion_date,
        "completion_date_precision": completion_precision,
        "conditions": _string_list(conditions_module.get("conditions"), limit=100, item_limit=500),
        "interventions": _interventions(arms_module),
        "sponsors": _sponsors(sponsors_module),
        "locations": _locations(locations_module),
        "study_design": _study_design(design_module),
        "eligibility": _eligibility(eligibility_module),
        "arms": _arms(arms_module),
        "outcomes": _outcomes(outcomes_module, results_section),
        "status_history": _status_history(
            status.get("overallStatus"),
            status_verified,
            status_verified_precision or last_update_precision,
        ),
        "result_disclosures": _result_disclosures(
            nct_id,
            official_title,
            results_first_posted,
            bool(study.get("hasResults")),
            citation,
        ),
        "results_first_posted": results_first_posted,
        "last_update_posted": last_update_posted,
        "citation": citation,
    }
    try:
        fact = TrialFact.model_validate(fact_payload)
    except ValidationError as exc:
        raise ValueError("ClinicalTrials.gov snapshot does not match the governed trial schema") from exc
    return ClinicalTrialsGovRecord(fact=fact, source_locator="protocolSection", source_quote=citation_quote)


def _mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent[key]
    if not isinstance(value, dict):
        raise TypeError
    return value


def _optional_mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: object, *, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value[:limit] if isinstance(item, dict)]


def _required_text(value: object, limit: int) -> str:
    text = _optional_text(value, limit)
    if text is None:
        raise ValueError("Required text value is missing")
    return text


def _optional_text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return _bounded_text(text, limit) if text else None


def _bounded_text(value: str, limit: int) -> str:
    return value[:limit]


def _string_list(value: object, *, limit: int, item_limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(text for item in value[:limit] if (text := _optional_text(item, item_limit)) is not None))


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, str | int | float):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_struct(value: object) -> tuple[datetime | None, Literal["day", "month", "year"] | None]:
    return _date_value(_optional_mapping(value).get("date"))


def _date_value(value: object) -> tuple[datetime | None, Literal["day", "month", "year"] | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None
    text = value.strip()
    precision: Literal["day", "month", "year"]
    try:
        if re.fullmatch(r"[0-9]{4}", text):
            precision = "year"
            parsed = datetime(int(text), 1, 1, tzinfo=UTC)
        elif re.fullmatch(r"[0-9]{4}-[0-9]{2}", text):
            precision = "month"
            parsed = datetime.fromisoformat(f"{text}-01").replace(tzinfo=UTC)
        else:
            precision = "day"
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            else:
                parsed = parsed.astimezone(UTC)
    except ValueError as exc:
        raise ValueError("ClinicalTrials.gov snapshot contains an invalid date") from exc
    return parsed, precision


def _citation_quote(nct_id: str, status: dict[str, Any]) -> str:
    del status
    # The NCT identifier occurs verbatim in every accepted official snapshot.
    # Keep the quoted evidence literal; structured field provenance is carried
    # by the source locator and immutable source-version checksum.
    return nct_id


def _interventions(module: dict[str, Any]) -> list[TrialInterventionFact]:
    return [
        TrialInterventionFact(
            name=_required_text(item.get("name"), 500),
            type=_optional_text(item.get("type"), 120),
            description=_optional_text(item.get("description"), 8000),
            arm_labels=_string_list(item.get("armGroupLabels"), limit=100, item_limit=500),
            other_names=_string_list(item.get("otherNames"), limit=100, item_limit=500),
        )
        for item in _items(module.get("interventions"), limit=100)
        if _optional_text(item.get("name"), 500) is not None
    ]


def _clean_intervention_name(value: object) -> str | None:
    text = _optional_text(value, 560)
    if text is None:
        return None
    return _INTERVENTION_PREFIX.sub("", text).strip()[:500] or None


def _arms(module: dict[str, Any]) -> list[TrialArmFact]:
    arms: list[TrialArmFact] = []
    for item in _items(module.get("armGroups"), limit=100):
        label = _optional_text(item.get("label"), 500)
        if label is None:
            continue
        raw_intervention_names = item.get("interventionNames")
        intervention_values = raw_intervention_names if isinstance(raw_intervention_names, list) else []
        intervention_names = list(
            dict.fromkeys(
                name for value in intervention_values if (name := _clean_intervention_name(value)) is not None
            )
        )[:100]
        arms.append(
            TrialArmFact(
                label=label,
                type=_optional_text(item.get("type"), 120),
                description=_optional_text(item.get("description"), 8000),
                intervention_names=intervention_names,
            )
        )
    return arms


def _sponsors(module: dict[str, Any]) -> list[TrialSponsorFact]:
    raw = []
    lead = _optional_mapping(module.get("leadSponsor"))
    if lead:
        raw.append(lead)
    raw.extend(_items(module.get("collaborators"), limit=99))
    result: list[TrialSponsorFact] = []
    seen: set[str] = set()
    for item in raw[:100]:
        name = _optional_text(item.get("name"), 500)
        if name is None or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        result.append(
            TrialSponsorFact(
                name=name,
                sponsor_class=_optional_text(item.get("class"), 120),
            )
        )
    return result


def _locations(module: dict[str, Any]) -> list[TrialLocationFact]:
    result: list[TrialLocationFact] = []
    for item in _items(module.get("locations"), limit=2000):
        country = _optional_text(item.get("country"), 160)
        if country is None:
            continue
        result.append(
            TrialLocationFact(
                facility=_optional_text(item.get("facility"), 500),
                city=_optional_text(item.get("city"), 160),
                state=_optional_text(item.get("state"), 160),
                country=country,
                status=_optional_text(item.get("status"), 120),
            )
        )
    return result


def _study_design(module: dict[str, Any]) -> TrialDesignFact:
    design = _optional_mapping(module.get("designInfo"))
    masking = _optional_mapping(design.get("maskingInfo"))
    return TrialDesignFact(
        allocation=_optional_text(design.get("allocation"), 120),
        intervention_model=_optional_text(design.get("interventionModel"), 160),
        intervention_model_description=_optional_text(design.get("interventionModelDescription"), 4000),
        primary_purpose=_optional_text(design.get("primaryPurpose"), 160),
        observational_model=_optional_text(design.get("observationalModel"), 160),
        time_perspective=_optional_text(design.get("timePerspective"), 160),
        masking=_optional_text(masking.get("masking"), 120),
        masking_description=_optional_text(masking.get("maskingDescription"), 4000),
        who_masked=_string_list(masking.get("whoMasked"), limit=20, item_limit=120),
    )


def _eligibility(module: dict[str, Any]) -> TrialEligibilityFact:
    return TrialEligibilityFact(
        minimum_age=_optional_text(module.get("minimumAge"), 80),
        maximum_age=_optional_text(module.get("maximumAge"), 80),
        sex=_optional_text(module.get("sex"), 80),
        gender_based=module.get("genderBased") if isinstance(module.get("genderBased"), bool) else None,
        healthy_volunteers=(
            module.get("healthyVolunteers") if isinstance(module.get("healthyVolunteers"), bool) else None
        ),
        sampling_method=_optional_text(module.get("samplingMethod"), 160),
        criteria=_optional_text(module.get("eligibilityCriteria"), 20_000),
    )


def _protocol_outcomes(module: dict[str, Any]) -> list[TrialOutcomeFact]:
    result: list[TrialOutcomeFact] = []
    for field, outcome_type in (
        ("primaryOutcomes", "PRIMARY"),
        ("secondaryOutcomes", "SECONDARY"),
        ("otherOutcomes", "OTHER"),
    ):
        for item in _items(module.get(field), limit=500 - len(result)):
            measure = _optional_text(item.get("measure"), 1000)
            if measure is None:
                continue
            result.append(
                TrialOutcomeFact(
                    outcome_type=outcome_type,
                    measure=measure,
                    description=_optional_text(item.get("description"), 8000),
                    time_frame=_optional_text(item.get("timeFrame"), 1000),
                )
            )
    return result


def _outcomes(protocol_module: dict[str, Any], results_section: dict[str, Any]) -> list[TrialOutcomeFact]:
    protocol = _protocol_outcomes(protocol_module)
    result_module = _optional_mapping(results_section.get("outcomeMeasuresModule"))
    posted = [
        outcome
        for item in _items(result_module.get("outcomeMeasures"), limit=500)
        if (outcome := _posted_outcome(item)) is not None
    ]
    if not posted:
        return protocol
    posted_keys = {(item.outcome_type, item.measure.casefold()) for item in posted}

    def missing_from_posted(item: TrialOutcomeFact) -> bool:
        return (item.outcome_type, item.measure.casefold()) not in posted_keys

    missing_protocol = [item for item in protocol if missing_from_posted(item)]
    return [*posted, *missing_protocol][:500]


def _posted_outcome(item: dict[str, Any]) -> TrialOutcomeFact | None:
    measure = _optional_text(item.get("title") or item.get("measure"), 1000)
    if measure is None:
        return None
    raw_type = str(item.get("type") or "OTHER").upper()
    outcome_type = raw_type if raw_type in {"PRIMARY", "SECONDARY", "OTHER_PRE_SPECIFIED", "POST_HOC"} else "OTHER"
    group_names = {
        str(group.get("id")): _required_text(group.get("title"), 500)
        for group in _items(item.get("groups"), limit=500)
        if group.get("id") is not None and _optional_text(group.get("title"), 500) is not None
    }
    participant_counts: dict[str, int] = {}
    for denominator in _items(item.get("denoms"), limit=100):
        for count in _items(denominator.get("counts"), limit=500):
            group_id = str(count.get("groupId") or "")
            participants = _non_negative_int(count.get("value"))
            if group_id and participants is not None:
                participant_counts.setdefault(group_id, participants)
    results: list[TrialOutcomeResultFact] = []
    for outcome_class in _items(item.get("classes"), limit=100):
        for category in _items(outcome_class.get("categories"), limit=100):
            for measurement in _items(category.get("measurements"), limit=500):
                group_id = str(measurement.get("groupId") or "")
                value = _optional_text(measurement.get("value"), 500)
                if not group_id or value is None:
                    continue
                results.append(
                    TrialOutcomeResultFact(
                        group_label=group_names.get(group_id, group_id)[:500],
                        value=value,
                        unit=_optional_text(item.get("unitOfMeasure"), 120),
                        participants=participant_counts.get(group_id),
                        dispersion=_optional_text(item.get("dispersionType"), 240),
                        lower_limit=_optional_float(measurement.get("lowerLimit")),
                        upper_limit=_optional_float(measurement.get("upperLimit")),
                    )
                )
    analyses = [
        TrialStatisticalAnalysisFact(
            method=_optional_text(analysis.get("statisticalMethod"), 500),
            p_value=_optional_text(analysis.get("pValue"), 120),
            parameter_type=_optional_text(analysis.get("paramType"), 160),
            parameter_value=_optional_float(analysis.get("paramValue")),
            confidence_interval_percent=_optional_float(analysis.get("ciPctValue")),
            lower_limit=_optional_float(analysis.get("ciLowerLimit")),
            upper_limit=_optional_float(analysis.get("ciUpperLimit")),
            notes=_optional_text(analysis.get("estimateComment") or analysis.get("pValueComment"), 4000),
        )
        for analysis in _items(item.get("analyses"), limit=100)
    ]
    return TrialOutcomeFact(
        outcome_type=outcome_type,
        measure=measure,
        description=_optional_text(item.get("description"), 8000),
        time_frame=_optional_text(item.get("timeFrame"), 1000),
        results=results[:500],
        statistical_analyses=analyses,
    )


def _status_history(
    status: object,
    effective_at: datetime | None,
    precision: Literal["day", "month", "year"] | None,
) -> list[TrialStatusHistoryFact]:
    value = _optional_text(status, 120)
    if value is None or effective_at is None:
        return []
    return [TrialStatusHistoryFact(status=value, effective_at=effective_at, effective_at_precision=precision)]


def _result_disclosures(
    nct_id: str,
    official_title: str,
    posted_at: datetime | None,
    has_results: bool,
    citation: Citation,
) -> list[TrialResultDisclosureFact]:
    if not has_results or posted_at is None:
        return []
    return [
        TrialResultDisclosureFact(
            disclosure_key=f"{nct_id}:registry-results",
            version=1,
            disclosure_type=TrialResultDisclosureType.REGISTRY_RESULT,
            external_id=nct_id,
            title=_bounded_text(f"{official_title} - ClinicalTrials.gov results", 4000),
            disclosed_at=posted_at,
            is_key_result=True,
            citation=citation,
        )
    ]
