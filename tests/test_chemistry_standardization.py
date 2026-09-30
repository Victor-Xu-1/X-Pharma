from __future__ import annotations

import pytest

from pharma_intel.chemistry.standardization import STANDARDIZATION_VERSION, ChemistryStandardizer
from pharma_intel.chemistry.types import ChemistryValidationError


def test_standardization_is_deterministic_and_removes_counterion() -> None:
    standardizer = ChemistryStandardizer()

    first = standardizer.standardize_smiles("CC(=O)[O-].[Na+]")
    second = standardizer.standardize_smiles("[Na+].[O-]C(C)=O")

    assert first.canonical_smiles == "CC(=O)O"
    assert second.canonical_smiles == first.canonical_smiles
    assert first.standard_inchi_key == "QTBSBXVTEAMEQO-UHFFFAOYSA-N"
    assert first.molecular_formula == "C2H4O2"
    assert first.standardization_version == STANDARDIZATION_VERSION
    assert first.heavy_atom_count == 4


def test_standardization_preserves_defined_stereochemistry() -> None:
    standardized = ChemistryStandardizer().standardize_smiles("C[C@H](O)F")

    assert "@" in standardized.isomeric_smiles
    assert standardized.canonical_smiles == standardized.isomeric_smiles


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("not-a-smiles", "invalid_smiles"),
        ("*CC", "unsupported_query_atom"),
        ("\x00CC", "invalid_structure_text"),
        ("C" * 20_001, "structure_too_large"),
    ],
)
def test_standardization_rejects_invalid_or_unbounded_inputs(value: str, code: str) -> None:
    with pytest.raises(ChemistryValidationError) as error:
        ChemistryStandardizer().standardize_smiles(value)

    assert error.value.code == code


def test_smarts_normalization_and_limits() -> None:
    standardizer = ChemistryStandardizer()

    assert standardizer.normalize_smarts("c1ccccc1") == "c1ccccc1"
    with pytest.raises(ChemistryValidationError) as error:
        standardizer.normalize_smarts("[invalid")
    assert error.value.code == "invalid_smarts"
