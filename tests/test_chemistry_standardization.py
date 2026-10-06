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


def test_tautomer_standardization_does_not_merge_alanine_enantiomers() -> None:
    standardizer = ChemistryStandardizer()
    left = standardizer.standardize_smiles("N[C@@H](C)C(=O)O")
    right = standardizer.standardize_smiles("N[C@H](C)C(=O)O")
    assert "@" in left.isomeric_smiles and "@" in right.isomeric_smiles
    assert left.standard_inchi_key != right.standard_inchi_key


def test_real_reported_conjugated_bond_geometry_survives_tautomer_normalization() -> None:
    # Public ChEMBL483321 structure; this is a method regression, not a runtime special case.
    smiles = "COCC(=O)NC/C=C/c1ccc2ncnc(Nc3ccc(Oc4ccc(C)nc4)c(C)c3)c2c1"
    result = ChemistryStandardizer().standardize_smiles(smiles)
    assert result.standard_inchi_key == "LLVZBTWPGQVVLW-SNAWJCMRSA-N"
    assert "/" in result.isomeric_smiles


def test_unpreservable_isotopic_stereocenter_fails_closed_instead_of_becoming_achiral() -> None:
    with pytest.raises(ChemistryValidationError) as error:
        ChemistryStandardizer().standardize_smiles("[2H][C@@](F)(Cl)C(=O)O")
    assert error.value.code == "stereochemistry_loss"


def test_normalization_policy_changes_invalidate_model_and_official_source_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pharma_intel.config import Settings
    from pharma_intel.governance.chembl import ADAPTER_NAME
    from pharma_intel.governance.policy import governance_policy_sha256
    from pharma_intel.governance.source_policy import deterministic_policy_sha256

    settings = Settings()
    old_model = governance_policy_sha256(settings)
    old_official = deterministic_policy_sha256(ADAPTER_NAME, settings)
    monkeypatch.setattr("pharma_intel.governance.policy.STANDARDIZATION_VERSION", "changed-normalization-policy")
    monkeypatch.setattr("pharma_intel.governance.chembl.STANDARDIZATION_VERSION", "changed-normalization-policy")
    assert governance_policy_sha256(settings) != old_model
    assert deterministic_policy_sha256(ADAPTER_NAME, settings) != old_official


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
