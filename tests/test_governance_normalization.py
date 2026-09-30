from __future__ import annotations

import pytest

from pharma_intel.chemistry.types import ChemistryValidationError
from pharma_intel.governance.normalization import FactNormalizer
from pharma_intel.governance.schemas import Citation, EntityReference, StructureFact
from pharma_intel.models import EntityType


def _structure_fact(
    smiles: str,
    *,
    standard_inchi_key: str | None = None,
    molecular_formula: str | None = None,
) -> StructureFact:
    return StructureFact(
        fact_kind="structure",
        subject=EntityReference(entity_type=EntityType.DRUG, name="Compound A"),
        canonical_smiles=smiles,
        standard_inchi_key=standard_inchi_key,
        molecular_formula=molecular_formula,
        citation=Citation(quote=f"Compound A has SMILES {smiles}.", confidence=0.99),
    )


def test_structure_fact_is_standardized_and_raw_model_payload_is_preserved() -> None:
    prepared = FactNormalizer().prepare(_structure_fact("[Na+].[O-]C(C)=O"))

    assert prepared.hard_reject is False
    assert prepared.normalization_conflict is False
    assert prepared.raw_payload["canonical_smiles"] == "[Na+].[O-]C(C)=O"
    assert prepared.raw_payload["standard_inchi_key"] is None
    assert prepared.payload["canonical_smiles"] == "CC(=O)O"
    assert prepared.payload["standard_inchi_key"] == "QTBSBXVTEAMEQO-UHFFFAOYSA-N"
    assert prepared.payload["molecular_formula"] == "C2H4O2"
    assert prepared.normalization_version == prepared.payload["standardization_version"]


def test_model_identifier_mismatch_is_a_reviewable_conflict() -> None:
    prepared = FactNormalizer().prepare(
        _structure_fact(
            "CCO",
            standard_inchi_key="ABCDEFGHIJKLMN-ABCDEFGHIJ-A",
            molecular_formula="C3H8O",
        )
    )

    assert prepared.hard_reject is False
    assert prepared.normalization_conflict is True
    assert prepared.raw_payload["standard_inchi_key"] == "ABCDEFGHIJKLMN-ABCDEFGHIJ-A"
    assert prepared.payload["standard_inchi_key"] == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    assert {finding["field"] for finding in prepared.quality_findings} == {
        "standard_inchi_key",
        "molecular_formula",
    }


def test_invalid_structure_is_hard_rejected_without_fabricated_identifiers() -> None:
    prepared = FactNormalizer().prepare(_structure_fact("not-a-smiles"))

    assert prepared.hard_reject is True
    assert prepared.normalization_version is None
    assert prepared.payload == prepared.raw_payload
    assert prepared.quality_findings[0]["code"] == "invalid_smiles"


def test_publish_boundary_detects_normalized_payload_tampering() -> None:
    normalizer = FactNormalizer()
    prepared = normalizer.prepare(_structure_fact("CCO"))
    tampered = {**prepared.payload, "molecular_formula": "C3H8O"}

    with pytest.raises(ChemistryValidationError, match="molecular_formula"):
        normalizer.verify_structure_payload(tampered)
