from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


class ChemistryError(RuntimeError):
    pass


class ChemistryValidationError(ChemistryError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ChemistryBackendUnavailable(ChemistryError):
    pass


@dataclass(frozen=True, slots=True)
class StandardizedStructure:
    input_structure: str
    input_format: Literal["smiles"]
    canonical_smiles: str
    isomeric_smiles: str
    standard_inchi: str
    standard_inchi_key: str
    molecular_formula: str
    molecular_weight: float
    exact_mass: float
    atom_count: int
    heavy_atom_count: int
    standardization_version: str


@dataclass(frozen=True, slots=True)
class ChemistrySearchHit:
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
    similarity: float | None = None


@dataclass(frozen=True, slots=True)
class ChemistrySearchResult:
    mode: Literal["exact", "substructure", "similarity"]
    normalized_query: str
    hits: tuple[ChemistrySearchHit, ...]
    as_of: datetime
    standardization_version: str | None = None
    fingerprint_version: str | None = None
    similarity_threshold: float | None = None
