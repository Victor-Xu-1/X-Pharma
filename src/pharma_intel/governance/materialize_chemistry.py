from __future__ import annotations

import hashlib
from typing import Any, cast

from sqlalchemy import select

from pharma_intel.chemistry.types import ChemistryValidationError
from pharma_intel.governance.contracts import SCHEMA_VERSION, GovernanceError
from pharma_intel.governance.fact_identity import _authority_value_matches, _projection
from pharma_intel.governance.materialization_context import MaterializationContext
from pharma_intel.models import (
    ActivityMeasurement,
    Assay,
    CompoundStructure,
    DataSourceType,
    MeasurementRelation,
    StagedFact,
)


def materialize_structure(
    context: MaterializationContext, staged: StagedFact, payload: dict[str, Any]
) -> list[dict[str, str]]:
    try:
        standardized = context.normalizer.verify_structure_payload(payload)
    except ChemistryValidationError as exc:
        raise GovernanceError(f"Structure payload failed authority verification: {exc}") from exc
    if staged.normalization_version != standardized.standardization_version:
        raise GovernanceError("Staged structure normalization version does not match its governed payload")

    entity = context._entity(cast(dict[str, Any], payload["subject"]), staged.source_document_id)
    inchi_key = standardized.standard_inchi_key
    structure = context.session.scalar(
        select(CompoundStructure).where(
            CompoundStructure.tenant_id == context.tenant_id,
            CompoundStructure.standard_inchi_key == inchi_key,
        )
    )
    if structure is None:
        structure = CompoundStructure(
            tenant_id=context.tenant_id,
            entity_id=entity.id,
            canonical_smiles=standardized.canonical_smiles,
            isomeric_smiles=standardized.isomeric_smiles,
            standard_inchi=standardized.standard_inchi,
            standard_inchi_key=inchi_key,
            molecular_formula=standardized.molecular_formula,
            molecular_weight=standardized.molecular_weight,
            exact_mass=standardized.exact_mass,
            structure_version=f"ai-governed/{SCHEMA_VERSION}",
            standardization_version=standardized.standardization_version,
        )
        context.session.add(structure)
    elif structure.entity_id != entity.id:
        raise GovernanceError("InChIKey is already assigned to another normalized entity")
    else:
        authoritative_fields: dict[str, str | float] = {
            "canonical_smiles": standardized.canonical_smiles,
            "isomeric_smiles": standardized.isomeric_smiles,
            "standard_inchi": standardized.standard_inchi,
            "molecular_formula": standardized.molecular_formula,
            "molecular_weight": standardized.molecular_weight,
            "exact_mass": standardized.exact_mass,
        }
        for field, expected in authoritative_fields.items():
            current = getattr(structure, field)
            if current is not None and not _authority_value_matches(current, expected):
                raise GovernanceError(f"Existing structure field {field} conflicts with the RDKit authority")
            if current is None:
                setattr(structure, field, expected)
        structure.standardization_version = standardized.standardization_version
    context.session.flush()
    return [_projection("compound_structure", structure.id)]


def materialize_activity(
    context: MaterializationContext, staged: StagedFact, payload: dict[str, Any]
) -> list[dict[str, str]]:
    compound = context._entity(cast(dict[str, Any], payload["compound"]), staged.source_document_id)
    target = context._entity(cast(dict[str, Any], payload["target"]), staged.source_document_id)
    source_system = (
        "chembl"
        if context._source_type_for_document(staged.source_document_id) == DataSourceType.CHEMBL
        else "governed_ai"
    )
    assay_identity = hashlib.sha256(
        f"{staged.source_document_id}:{str(payload['assay_name']).casefold()}".encode()
    ).hexdigest()
    assay = context.session.scalar(
        select(Assay).where(
            Assay.tenant_id == context.tenant_id,
            Assay.source_system == source_system,
            Assay.source_assay_id == assay_identity,
        )
    )
    if assay is None:
        assay = Assay(
            tenant_id=context.tenant_id,
            source_system=source_system,
            source_assay_id=assay_identity,
            target_entity_id=target.id,
            assay_type=cast(str | None, payload.get("assay_type")),
            description=str(payload["assay_name"]),
            source_document_id=staged.source_document_id,
        )
        context.session.add(assay)
        context.session.flush()
    activity = context.session.scalar(
        select(ActivityMeasurement).where(
            ActivityMeasurement.tenant_id == context.tenant_id,
            ActivityMeasurement.source_system == source_system,
            ActivityMeasurement.source_activity_id == staged.fact_key,
        )
    )
    relation = MeasurementRelation(str(payload["reported_relation"]))
    if activity is None:
        activity = ActivityMeasurement(
            tenant_id=context.tenant_id,
            source_system=source_system,
            source_activity_id=staged.fact_key,
            assay_id=assay.id,
            compound_entity_id=compound.id,
            target_entity_id=target.id,
            reported_type=str(payload["reported_type"]),
            reported_relation=relation,
            reported_value=str(payload["reported_value"]),
        )
        context.session.add(activity)
    activity.assay_id = assay.id
    activity.reported_type = str(payload["reported_type"])
    activity.reported_relation = relation
    activity.reported_value = str(payload["reported_value"])
    activity.reported_units = cast(str | None, payload.get("reported_units"))
    activity.standard_type = str(payload["reported_type"]) if payload.get("standard_value") is not None else None
    activity.standard_relation = relation if payload.get("standard_value") is not None else None
    activity.standard_value = cast(float | None, payload.get("standard_value"))
    activity.standard_units = cast(str | None, payload.get("standard_units"))
    activity.qualifiers = {"staged_fact_id": staged.id, "evidence_claim_pending": True}
    context._relationship(compound, "has_target", target, staged)
    context.session.flush()
    return [_projection("assay", assay.id), _projection("activity_measurement", activity.id)]
