from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RecipeId = Literal["python-dependencies", "frontend-dependencies", "deployment-tools"]
HostReportStatus = Literal["current", "stale", "missing", "invalid", "not_configured"]
EnvironmentProbeStatus = Literal["present", "missing", "mismatch", "blocked", "unverified"]


class EnvironmentProbeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(max_length=80)
    label: str = Field(max_length=120)
    scope: Literal["gateway", "host"]
    status: EnvironmentProbeStatus
    observed: str | None = Field(default=None, max_length=160)
    expected: str | None = Field(default=None, max_length=160)
    detail: str = Field(max_length=500)


class EnvironmentInstallResultRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipe_id: RecipeId
    plan_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    status: Literal["running", "succeeded", "failed"]
    started_at: datetime
    finished_at: datetime | None = None
    exit_code: int | None = None
    detail: str = Field(max_length=500)


class HostEnvironmentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["pharma.environment.host.v1"] = "pharma.environment.host.v1"
    generated_at: datetime
    product_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    clean_source: bool
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    probes: list[EnvironmentProbeRead] = Field(max_length=30)
    disk_free_bytes: int = Field(ge=0)
    disk_total_bytes: int = Field(gt=0)
    latest_install: EnvironmentInstallResultRead | None = None


class EnvironmentRecipeRead(BaseModel):
    id: RecipeId
    label: str
    description: str
    offline_supported: bool
    prerequisites: list[str]


class EnvironmentRead(BaseModel):
    generated_at: datetime
    product_version: str
    environment: str
    runtime: list[EnvironmentProbeRead]
    host_status: HostReportStatus
    host: HostEnvironmentRead | None
    host_detail: str
    recipes: list[EnvironmentRecipeRead]


class EnvironmentPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipe_id: RecipeId
    offline: bool = True


class EnvironmentInstallPlanRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["pharma.environment.install-plan.v1"] = "pharma.environment.install-plan.v1"
    generated_at: datetime
    expires_at: datetime
    product_version: str
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recipe_id: RecipeId
    offline: bool
    commands: list[list[str]] = Field(max_length=5)
    plan_id: str = Field(pattern=r"^[0-9a-f]{64}$")
