from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pharma_intel.api_key_lifecycle import MANAGED_API_KEY_SCOPES
from pharma_intel.models.enums import (
    UserRole,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)

from .accounts import (
    _validate_human_display_name,
)


class EnterpriseTenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    slug: str
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime


class EnterpriseOverviewRead(BaseModel):
    tenant: EnterpriseTenantRead
    user_count: int
    active_user_count: int
    admin_count: int
    group_count: int
    active_group_count: int
    dataset_count: int
    active_source_count: int
    audit_event_count_24h: int


class EnterpriseLLMProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    base_url: str
    model: str
    priority: int
    version: int
    active: bool
    api_key_configured: bool = True
    api_key_fingerprint: str
    response_format_mode: Literal["json_schema", "json_object", "prompt_only"]
    thinking_mode: Literal["provider_default", "enabled", "disabled"]
    include_schema_in_prompt: bool
    max_output_tokens_per_segment: int
    request_timeout_seconds: float
    request_attempts: int
    last_tested_at: datetime | None
    last_test_status: Literal["passed", "failed"] | None
    last_test_message: str | None
    created_at: datetime
    updated_at: datetime


class _EnterpriseLLMProviderInputBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,119}$")
    base_url: str = Field(min_length=10, max_length=2048)
    model: str = Field(min_length=1, max_length=500)
    response_format_mode: Literal["json_schema", "json_object", "prompt_only"] = "prompt_only"
    thinking_mode: Literal["provider_default", "enabled", "disabled"] = "disabled"
    include_schema_in_prompt: bool = True
    max_output_tokens_per_segment: int = Field(default=16_384, ge=256, le=131_072)
    request_timeout_seconds: float = Field(default=120, ge=1, le=600)
    request_attempts: int = Field(default=2, ge=1, le=8)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("base_url must be a credential-free HTTPS API root")
        return value.rstrip("/")


class EnterpriseLLMProviderCreate(_EnterpriseLLMProviderInputBase):
    api_key: str = Field(min_length=8, max_length=8192, repr=False)


class EnterpriseLLMProviderUpdate(_EnterpriseLLMProviderInputBase):
    expected_version: int = Field(ge=1)
    api_key: str | None = Field(default=None, min_length=8, max_length=8192, repr=False)
    active: bool


class EnterpriseLLMProviderPrimaryUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    email: str
    display_name: str
    role: UserRole
    active: bool
    token_version: int
    last_login_at: datetime | None
    oidc_issuer: str | None
    created_at: datetime
    updated_at: datetime


class EnterpriseUserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    role: UserRole = UserRole.VIEWER
    initial_password: str | None = Field(default=None, min_length=12, max_length=200)
    oidc_issuer: str | None = Field(default=None, min_length=8, max_length=500)
    oidc_subject: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return _validate_human_display_name(value)

    @model_validator(mode="after")
    def validate_identity_shape(self) -> EnterpriseUserCreate:
        if bool(self.oidc_issuer) != bool(self.oidc_subject):
            raise ValueError("oidc_issuer and oidc_subject must be supplied together")
        if self.initial_password is not None and self.oidc_issuer is not None:
            raise ValueError("initial_password and OIDC identity are mutually exclusive")
        return self


class EnterpriseUserRoleUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_token_version: int = Field(ge=1)
    role: UserRole
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseUserStatusUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_token_version: int = Field(ge=1)
    active: bool
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseDatasetRead(BaseModel):
    id: str
    dataset_key: str
    display_name: str
    active: bool
    version: int
    required_scopes: list[str]
    license_id: str
    license_policy_version: str
    permitted_channels: list[Literal["web", "mcp"]]
    license_current: bool
    attribution: str


class EnterpriseDatasetStatusUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    active: bool
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseSessionRead(BaseModel):
    id: str
    user_id: str
    user_display_name: str
    user_email: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    revoked_by_user_id: str | None
    revoke_reason: str | None
    current: bool


class EnterpriseSessionRevoke(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseApiKeyRead(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: list[str]
    active: bool
    status: Literal["active", "expired", "revoked", "disabled"]
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    commercial_client_id: str | None
    commercial_client_name: str | None
    created_at: datetime
    updated_at: datetime


class EnterpriseApiKeyCatalogRead(BaseModel):
    items: list[EnterpriseApiKeyRead]
    required_scope: str
    allowed_scopes: list[str]
    min_ttl_hours: int
    max_ttl_days: int


def _managed_api_key_scopes(values: list[str]) -> list[str]:
    normalized = sorted({value.strip() for value in values if value.strip()})
    unknown = sorted(set(normalized) - set(MANAGED_API_KEY_SCOPES))
    if unknown:
        raise ValueError(f"Unmanaged API key scopes: {', '.join(unknown)}")
    if "mcp:connect" not in normalized:
        raise ValueError("Managed API keys must include mcp:connect")
    if len(normalized) < 2:
        raise ValueError("Managed API keys must include at least one data-access scope")
    return normalized


class EnterpriseApiKeyCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(min_length=2, max_length=len(MANAGED_API_KEY_SCOPES))
    expires_at: datetime
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        return _managed_api_key_scopes(value)


class EnterpriseApiKeyRotate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    expires_at: datetime
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseApiKeyRevoke(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    reason: str = Field(min_length=3, max_length=500)


class EnterpriseApiKeySecretRead(EnterpriseApiKeyRead):
    secret: str


class UserGroupCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=500)


class UserGroupUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=500)
    active: bool
    reason: str = Field(min_length=3, max_length=500)


class UserGroupMembershipUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    user_ids: list[str] = Field(default_factory=list, max_length=500)
    reason: str = Field(min_length=3, max_length=500)


class UserGroupRead(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str
    active: bool
    version: int
    member_ids: list[str]
    member_count: int
    created_at: datetime
    updated_at: datetime


class EnterpriseAuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    actor_type: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    request_id: str
    details: dict[str, Any]
    occurred_at: datetime


class EnterpriseAuditPageRead(BaseModel):
    items: list[EnterpriseAuditEventRead]
    next_cursor: str | None
