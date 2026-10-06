from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from pharma_intel.chemistry.standardization import ChemistryStandardizer
from pharma_intel.chemistry.types import ChemistryValidationError, StandardizedStructure
from pharma_intel.governance.schemas import ExtractedFact, StructureFact


@dataclass(frozen=True, slots=True)
class PreparedFact:
    fact: ExtractedFact
    raw_payload: dict[str, Any]
    payload: dict[str, Any]
    normalization_version: str | None
    quality_findings: tuple[dict[str, Any], ...] = ()
    hard_reject: bool = False
    normalization_conflict: bool = False


class FactNormalizer:
    """Converts untrusted reported facts into deterministic, publishable payloads."""

    def __init__(self, standardizer: ChemistryStandardizer | None = None) -> None:
        self.standardizer = standardizer or ChemistryStandardizer()

    def prepare(self, fact: ExtractedFact) -> PreparedFact:
        raw_payload = fact.model_dump(mode="json")
        if not isinstance(fact, StructureFact):
            return PreparedFact(fact=fact, raw_payload=raw_payload, payload=raw_payload, normalization_version=None)

        try:
            standardized = self.standardizer.standardize_smiles(fact.canonical_smiles)
        except ChemistryValidationError as exc:
            return PreparedFact(
                fact=fact,
                raw_payload=raw_payload,
                payload=raw_payload,
                normalization_version=None,
                quality_findings=(
                    {
                        "code": exc.code,
                        "severity": "error",
                        "message": str(exc),
                        "field": "canonical_smiles",
                    },
                ),
                hard_reject=True,
            )

        payload = {
            **raw_payload,
            "canonical_smiles": standardized.canonical_smiles,
            "isomeric_smiles": standardized.isomeric_smiles,
            "standard_inchi": standardized.standard_inchi,
            "standard_inchi_key": standardized.standard_inchi_key,
            "molecular_formula": standardized.molecular_formula,
            "molecular_weight": standardized.molecular_weight,
            "exact_mass": standardized.exact_mass,
            "atom_count": standardized.atom_count,
            "heavy_atom_count": standardized.heavy_atom_count,
            "standardization_version": standardized.standardization_version,
        }
        findings = tuple(self._reported_authority_mismatches(raw_payload, payload))
        return PreparedFact(
            fact=fact,
            raw_payload=raw_payload,
            payload=payload,
            normalization_version=standardized.standardization_version,
            quality_findings=findings,
            normalization_conflict=bool(findings),
        )

    def verify_structure_payload(self, payload: dict[str, Any]) -> StandardizedStructure:
        smiles = payload.get("canonical_smiles")
        if not isinstance(smiles, str):
            raise ChemistryValidationError(
                "structure_payload_integrity_error",
                "Normalized structure payload is missing canonical SMILES",
            )
        standardized = self.standardizer.standardize_smiles(smiles)
        expected: dict[str, str | float | int] = {
            "canonical_smiles": standardized.canonical_smiles,
            "isomeric_smiles": standardized.isomeric_smiles,
            "standard_inchi": standardized.standard_inchi,
            "standard_inchi_key": standardized.standard_inchi_key,
            "molecular_formula": standardized.molecular_formula,
            "molecular_weight": standardized.molecular_weight,
            "exact_mass": standardized.exact_mass,
            "atom_count": standardized.atom_count,
            "heavy_atom_count": standardized.heavy_atom_count,
            "standardization_version": standardized.standardization_version,
        }
        for field, expected_value in expected.items():
            if not _equivalent(payload.get(field), expected_value):
                raise ChemistryValidationError(
                    "structure_payload_integrity_error",
                    f"Normalized structure field {field} does not match the current RDKit authority",
                )
        return standardized

    @staticmethod
    def _reported_authority_mismatches(
        raw_payload: dict[str, Any],
        normalized_payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for field in ("standard_inchi", "standard_inchi_key", "molecular_formula"):
            model_value = raw_payload.get(field)
            if model_value is None or _equivalent(model_value, normalized_payload[field]):
                continue
            findings.append(
                {
                    "code": "structure_authority_mismatch",
                    "severity": "error",
                    "message": f"Supplied {field} does not match the RDKit-derived value",
                    "field": field,
                    "model_value": _display_value(model_value),
                    "derived_value": _display_value(normalized_payload[field]),
                }
            )
        return findings


def _equivalent(value: object, expected: object) -> bool:
    if isinstance(expected, float):
        return (
            isinstance(value, int | float)
            and not isinstance(value, bool)
            and math.isclose(float(value), expected, rel_tol=0, abs_tol=1e-6)
        )
    return value == expected


def _display_value(value: object) -> object:
    if isinstance(value, str) and len(value) > 500:
        return value[:497] + "..."
    return value
