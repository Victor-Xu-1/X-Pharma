from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class ChemistrySavedSearchQuery(BaseModel):
    """Versioned saved-search payload; the structure stays server-side, not in a URL."""

    mode: Literal["exact", "substructure", "similarity"]
    query: str = Field(min_length=1, max_length=20_000)
    threshold: float = Field(default=0.5, ge=0, le=1)
    limit: int = Field(default=20, ge=1, le=100)


class BioactivityRead(BaseModel):
    id: str
    compound_entity_id: str
    target_entity_id: str | None
    assay_id: str
    standard_type: str | None
    standard_relation: str | None
    standard_value: float | None
    standard_units: str | None
    pchembl_value: float | None
    reported_type: str
    reported_relation: str
    reported_value: str
    reported_units: str | None
    source_system: str
    source_activity_id: str
    source_document_id: str | None = None


class SarActivityRead(BaseModel):
    id: str
    compound_entity_id: str
    compound_name: str
    target_entity_id: str
    assay_id: str
    assay_type: str | None
    assay_format: str | None
    organism: str | None
    cell_line: str | None
    standard_type: str | None
    standard_relation: str | None
    standard_value: float | None
    standard_units: str | None
    pchembl_value: float | None
    comparison_group: str
    comparable: bool
    comparability_reasons: list[str] = Field(default_factory=list)
    potency_rank: int | None = None
    delta_pchembl: float | None = None
    canonical_smiles: str | None = None
    standard_inchi_key: str | None = None
    validity_comment: str | None = None
    source_system: str
    source_activity_id: str
    source_document_id: str | None = None


class SarComparisonResult(BaseModel):
    items: list[SarActivityRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)
    as_of: datetime | None = None
    warnings: list[str] = Field(default_factory=list)


class CompoundStructureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_id: str
    canonical_smiles: str
    isomeric_smiles: str | None
    standard_inchi: str | None
    standard_inchi_key: str
    molecular_formula: str | None
    molecular_weight: float | None
    exact_mass: float | None
    structure_version: str
    standardization_version: str
    fingerprint_version: str


class ChemistrySearchRequest(BaseModel):
    mode: Literal["exact", "substructure", "similarity"]
    query: str = Field(min_length=1, max_length=20_000)
    threshold: float = Field(default=0.5, ge=0, le=1)
    limit: int = Field(default=20, ge=1, le=100)


class ChemistrySearchHitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_id: str
    entity_name: str
    canonical_smiles: str
    isomeric_smiles: str | None
    standard_inchi: str | None
    standard_inchi_key: str
    molecular_formula: str | None
    molecular_weight: float | None
    exact_mass: float | None
    structure_version: str
    standardization_version: str
    fingerprint_version: str
    updated_at: datetime
    similarity: float | None


class ChemistrySearchRead(BaseModel):
    mode: Literal["exact", "substructure", "similarity"]
    normalized_query: str
    items: list[ChemistrySearchHitRead]
    count: int
    as_of: datetime
    standardization_version: str | None
    fingerprint_version: str | None
    similarity_threshold: float | None


class AgentChemistrySearchRead(ChemistrySearchRead):
    limit: int
    page_depth: int
    next_cursor: str | None
