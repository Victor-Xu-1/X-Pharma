from __future__ import annotations

import pytest

from pharma_intel.program_semantics import chembl_maximum_phase


@pytest.mark.parametrize(
    ("source_phase", "expected"),
    [
        (0, "preclinical"),
        (0.5, "early_phase_1"),
        (1, "phase_1"),
        (2, "phase_2"),
        (3, "phase_3"),
        (4, "approved"),
        (-1, "unknown"),
        (None, "unknown"),
    ],
)
def test_chembl_maximum_phase_preserves_upstream_stage_meaning(source_phase: float | None, expected: str) -> None:
    assert chembl_maximum_phase(source_phase) == expected


@pytest.mark.parametrize("source_phase", [-2, 0.2, 1.5, 5])
def test_chembl_phase_never_rounds_or_invents_an_unsupported_stage(source_phase: float) -> None:
    with pytest.raises(ValueError, match="Unsupported ChEMBL maximum phase"):
        chembl_maximum_phase(source_phase)
