from __future__ import annotations

import hashlib
import json
from typing import Any, cast

from pharma_intel.governance.contracts import GovernanceError
from pharma_intel.governance.normalization import PreparedFact
from pharma_intel.governance.schemas import (
    ActivityFact,
    ClaimFact,
    DealFact,
    EpidemiologyFact,
    ExtractedFact,
    NewsFact,
    PatentFact,
    ProgramFact,
    RegulatoryFact,
    StructureFact,
    TargetEvidenceFact,
    TargetProfileFact,
    TrialFact,
)
from pharma_intel.models import Entity, ProgramTargetRole


def _hash_json(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _prepared_fact_key(prepared: PreparedFact) -> str:
    if isinstance(prepared.fact, StructureFact):
        inchi_key = prepared.payload.get("standard_inchi_key")
        if isinstance(inchi_key, str) and inchi_key:
            return _hash_identity({"kind": "structure", "standard_inchi_key": inchi_key})
    return _fact_key(prepared.fact)


def _fact_key(fact: ExtractedFact) -> str:
    return _hash_identity(_fact_identity(fact))


def _hash_identity(identity: dict[str, Any]) -> str:
    encoded = json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _fact_identity(fact: ExtractedFact) -> dict[str, Any]:
    if isinstance(fact, ClaimFact):
        return {
            "kind": fact.fact_kind,
            "subject": _entity_identity(fact.subject.model_dump(mode="json")),
            "predicate": fact.predicate,
            "qualifier_keys": sorted(fact.qualifiers),
        }
    if isinstance(fact, TargetProfileFact):
        return {"kind": fact.fact_kind, "subject": _entity_identity(fact.subject.model_dump(mode="json"))}
    if isinstance(fact, TargetEvidenceFact):
        return {
            "kind": fact.fact_kind,
            "record_identifier": fact.record_identifier.casefold(),
            "target": _entity_identity(fact.target.model_dump(mode="json")),
        }
    if isinstance(fact, StructureFact):
        return {
            "kind": fact.fact_kind,
            "subject": _entity_identity(fact.subject.model_dump(mode="json")),
            "reported_smiles": fact.canonical_smiles.strip(),
        }
    if isinstance(fact, ActivityFact):
        return {
            "kind": fact.fact_kind,
            "compound": _entity_identity(fact.compound.model_dump(mode="json")),
            "target": _entity_identity(fact.target.model_dump(mode="json")),
            "assay_name": fact.assay_name.casefold(),
            "reported_type": fact.reported_type.casefold(),
        }
    if isinstance(fact, ProgramFact):
        program_payload = fact.model_dump(mode="json")
        targets = list(program_payload.get("targets") or [])
        if program_payload.get("target") is not None:
            targets = [
                {
                    "role": ProgramTargetRole.PRIMARY.value,
                    "entity": program_payload["target"],
                }
            ]
        organizations = list(program_payload.get("organizations") or [])
        if program_payload.get("organization") is not None and not organizations:
            organizations = [
                {
                    "role": "originator",
                    "entity": program_payload["organization"],
                }
            ]
        return {
            "kind": fact.fact_kind,
            "drug": _entity_identity(fact.drug.model_dump(mode="json")),
            "targets": [
                {
                    "role": str(item["role"]),
                    "entity": _entity_identity(item["entity"]),
                }
                for item in targets
            ],
            "indication": _entity_identity(fact.indication.model_dump(mode="json")) if fact.indication else None,
            "organizations": [
                {
                    "role": str(item["role"]),
                    "entity": _entity_identity(item["entity"]),
                }
                for item in organizations
            ],
        }
    if isinstance(fact, TrialFact):
        return {"kind": fact.fact_kind, "registry": fact.registry_name.casefold(), "id": fact.registry_id.casefold()}
    if isinstance(fact, PatentFact):
        return {"kind": fact.fact_kind, "family": fact.family_identifier.casefold()}
    if isinstance(fact, DealFact):
        return {"kind": fact.fact_kind, "deal": _entity_identity(fact.deal.model_dump(mode="json"))}
    if isinstance(fact, RegulatoryFact):
        return {
            "kind": fact.fact_kind,
            "agency": fact.agency.casefold(),
            "event_identifier": fact.event_identifier.casefold(),
        }
    if isinstance(fact, EpidemiologyFact):
        return {
            "kind": fact.fact_kind,
            "observation_identifier": fact.observation_identifier.casefold(),
            "disease": _entity_identity(fact.disease.model_dump(mode="json")),
        }
    if isinstance(fact, NewsFact):
        return {"kind": fact.fact_kind, "event_identifier": fact.event_identifier.casefold()}
    raise TypeError(f"Unsupported fact type: {type(fact).__name__}")


def _entity_identity(reference: dict[str, Any]) -> dict[str, Any]:
    external_ids = reference.get("external_ids") or {}
    return {
        "entity_type": str(reference["entity_type"]),
        "name": " ".join(str(reference["name"]).casefold().split()),
        "external_ids": dict(sorted(external_ids.items())),
    }


def _reference_matches_entity(reference: object, entity: Entity) -> bool:
    if not isinstance(reference, dict):
        return False
    if str(reference.get("entity_type")) != entity.entity_type.value:
        return False
    name = " ".join(str(reference.get("name") or "").casefold().split())
    if name and name == entity.normalized_name:
        return True
    supplied_ids = reference.get("external_ids")
    if not isinstance(supplied_ids, dict):
        return False
    return any(entity.external_ids.get(str(key)) == str(value) for key, value in supplied_ids.items())


def _authority_value_matches(current: object, expected: str | float) -> bool:
    if isinstance(expected, float):
        return (
            isinstance(current, int | float)
            and not isinstance(current, bool)
            and abs(float(current) - expected) <= 1e-6
        )
    return current == expected


def _primary_subject(payload: dict[str, Any]) -> dict[str, Any]:
    for key in (
        "subject",
        "compound",
        "drug",
        "trial",
        "patent",
        "deal",
        "disease",
        "publisher",
    ):
        value = payload.get(key)
        if isinstance(value, dict):
            return cast(dict[str, Any], value)
    raise GovernanceError("Extracted fact does not have a primary subject")


def _payload_without_citation(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "citation"}


def _projection(resource_type: str, resource_id: str) -> dict[str, str]:
    return {"resource_type": resource_type, "resource_id": resource_id}
