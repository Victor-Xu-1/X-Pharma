from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from pharma_intel.governance.schemas import ActivityFact, Citation, EntityReference, StrictModel, StructureFact


class ChemblStructure(StrictModel):
    canonical_smiles: str = Field(min_length=1, max_length=20_000)
    standard_inchi: str | None = Field(default=None, max_length=40_000)
    standard_inchi_key: str | None = Field(default=None, pattern=r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
    molecular_formula: str | None = Field(default=None, max_length=200)


class ChemblActivity(StrictModel):
    activity_id: int = Field(gt=0, strict=True)
    assay_chembl_id: str = Field(pattern=r"^CHEMBL[0-9]+$")
    molecule_chembl_id: str = Field(pattern=r"^CHEMBL[0-9]+$")
    target_chembl_id: str = Field(pattern=r"^CHEMBL[0-9]+$")
    assay_type: str | None = Field(default=None, max_length=80)
    type: str = Field(min_length=1, max_length=80)
    relation: Literal["=", "<", "<=", ">", ">=", "~"]
    value: str = Field(min_length=1, max_length=120)
    units: str | None = Field(default=None, max_length=40)
    standard_type: str | None = Field(default=None, max_length=80)
    standard_relation: Literal["=", "<", "<=", ">", ">=", "~"] | None = None
    standard_value: float | None = Field(default=None, allow_inf_nan=False)
    standard_units: str | None = Field(default=None, max_length=40)
    document_chembl_id: str | None = Field(default=None, pattern=r"^CHEMBL[0-9]+$")

    @field_validator("standard_value", mode="before")
    @classmethod
    def reject_boolean_measurement(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("A boolean is not a numerical ChEMBL standard measurement")
        return value


class ChemblActivityCoverage(StrictModel):
    requested: bool = False
    reported_total: int = Field(default=0, ge=0)
    fetched: int = Field(default=0, ge=0, le=10)
    excluded: int = Field(default=0, ge=0, le=10)
    limit: int = Field(default=10, ge=1, le=10)

    @model_validator(mode="after")
    def counts_are_consistent(self) -> ChemblActivityCoverage:
        if self.excluded > self.fetched or self.fetched > min(self.reported_total, self.limit):
            raise ValueError("ChEMBL activity coverage counts are inconsistent")
        if not self.requested and (self.fetched or self.reported_total or self.excluded):
            raise ValueError("Unrequested activity enrichment cannot contain observations")
        return self


def enrichment_facts(
    *,
    compound: EntityReference,
    target: EntityReference,
    structure: ChemblStructure | None,
    activities: list[ChemblActivity],
) -> list[StructureFact | ActivityFact]:
    result: list[StructureFact | ActivityFact] = []
    if structure is not None:
        result.append(
            StructureFact(
                fact_kind="structure",
                subject=compound,
                **structure.model_dump(),
                citation=Citation(
                    locator=f"molecule:{compound.external_ids['chembl']}:molecule_structures",
                    quote=(
                        f"molecule_chembl_id={compound.external_ids['chembl']}; "
                        f"canonical_smiles={structure.canonical_smiles}"
                    )[:4000],
                    confidence=1,
                ),
            )
        )
    for activity in activities:
        if (
            activity.molecule_chembl_id != compound.external_ids["chembl"]
            or activity.target_chembl_id != target.external_ids["chembl"]
        ):
            raise ValueError("ChEMBL activity scope differs from snapshot compound or target")
        result.append(
            ActivityFact(
                fact_kind="activity",
                compound=compound,
                target=target,
                assay_name=f"{activity.assay_chembl_id} · activity {activity.activity_id}",
                assay_type=activity.assay_type,
                reported_type=activity.type,
                reported_relation=activity.relation,
                reported_value=activity.value,
                reported_units=activity.units,
                standard_value=(
                    activity.standard_value
                    if activity.standard_type == activity.type
                    and activity.standard_relation == activity.relation
                    and activity.standard_units is not None
                    else None
                ),
                standard_units=(
                    activity.standard_units
                    if activity.standard_type == activity.type and activity.standard_relation == activity.relation
                    else None
                ),
                citation=Citation(
                    locator=f"activity:{activity.activity_id}",
                    quote=(
                        f"activity_id={activity.activity_id}; assay_chembl_id={activity.assay_chembl_id}; "
                        f"molecule_chembl_id={activity.molecule_chembl_id}; "
                        f"target_chembl_id={activity.target_chembl_id}; "
                        f"type={activity.type}; relation={activity.relation}; value={activity.value}; "
                        f"units={activity.units}; document_chembl_id={activity.document_chembl_id}; "
                        f"standard_type={activity.standard_type}; standard_relation={activity.standard_relation}; "
                        f"standard_value={activity.standard_value}; standard_units={activity.standard_units}"
                    ),
                    confidence=1,
                ),
            )
        )
    return result
