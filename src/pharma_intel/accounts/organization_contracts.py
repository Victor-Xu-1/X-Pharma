from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from pharma_intel.models.enums import UserRole


class OrganizationRead(BaseModel):
    tenant_id: str
    name: str
    slug: str
    role: UserRole
    active: bool
    selected: bool


class OrganizationSwitch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_id: UUID


class OrganizationJoin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invitation_code: SecretStr = Field(min_length=20, max_length=2048)
    confirmed: Literal[True]


class InvitationAcceptance(OrganizationJoin):
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=8, max_length=200)


class OidcInvitationStart(BaseModel):
    authorization_url: str
