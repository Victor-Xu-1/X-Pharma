from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RegionalRepairEvidence(BaseModel):
    staged_fact_id: str
    source_version_id: str
    source_sha256: str


class RegionalRepairChange(BaseModel):
    program_id: str
    drug_entity_id: str
    old_global_phase: str
    new_global_phase: None = None
    evidence: list[RegionalRepairEvidence]


class RegionalRepairPlan(BaseModel):
    schema_version: Literal["pharma.chembl.regional-projection-repair.v1"] = (
        "pharma.chembl.regional-projection-repair.v1"
    )
    tenant_id: str
    data_source_id: str
    source_scope_digest: str
    source_config_version: int
    changes: list[RegionalRepairChange]
    blocked: dict[str, str]
    plan_sha256: str = Field(default="0" * 64, pattern=r"^[a-f0-9]{64}$")


class RegionalRepairResult(BaseModel):
    schema_version: Literal["pharma.chembl.regional-projection-repair-result.v1"] = (
        "pharma.chembl.regional-projection-repair-result.v1"
    )
    status: Literal["applied", "no_changes"] = "applied"
    data_source_id: str
    plan_sha256: str
    changes_applied: int
    program_ids: list[str]
    blocked: dict[str, str] = Field(default_factory=dict)
    request_id: str
    replayed: bool = False
