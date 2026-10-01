from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class TargetEvidenceRead(BaseModel):
    id: str
    source_system: str
    source_record_id: str
    target_entity_id: str
    target_name: str
    disease_entity_id: str | None = None
    disease_name: str | None = None
    evidence_type: Literal[
        "genetic_association",
        "expression",
        "functional",
        "translational",
        "biomarker",
        "safety",
    ]
    direction: Literal["supports", "opposes", "neutral", "unknown"]
    study_name: str | None = None
    population: str | None = None
    tissue: str | None = None
    variant: str | None = None
    effect_size: float | None = None
    effect_unit: str | None = None
    p_value: float | None = None
    sample_size: int | None = None
    summary: str
    observed_at: datetime | None = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    source_document_id: str | None = None
