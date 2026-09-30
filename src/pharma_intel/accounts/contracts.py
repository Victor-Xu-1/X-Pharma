from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, computed_field, field_validator, model_validator


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workbench: Literal["research", "internal"]
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    password: SecretStr = Field(min_length=12, max_length=256)
    invitation_code: SecretStr | None = Field(default=None, min_length=100, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip()
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) is None:
            raise ValueError("请输入有效的邮箱地址")
        return value

    @field_validator("display_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if not value or not any(character.isalnum() for character in value) or any(ord(c) < 32 for c in value):
            raise ValueError("用户名至少包含一个文字或数字，且不能包含控制字符")
        return value

    @model_validator(mode="after")
    def registration_scope(self) -> RegistrationRequest:
        if self.workbench == "internal" and self.invitation_code is None:
            raise ValueError("内部管理账号必须提供邀请码")
        if self.workbench == "research" and self.invitation_code is not None:
            raise ValueError("内部邀请码只能用于内部管理工作台注册")
        return self


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    valid_hours: int = Field(default=24, ge=1, le=168)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return RegistrationRequest.valid_email(value)


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    email: str
    created_at: datetime
    expires_at: datetime
    claimed_at: datetime | None
    revoked_at: datetime | None

    @field_validator("created_at", "expires_at", "claimed_at", "revoked_at")
    @classmethod
    def utc_dates(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value

    @computed_field  # type: ignore[prop-decorator]  # Pydantic validates the read-only serialized property.
    @property
    def status(self) -> Literal["active", "consumed", "revoked", "expired"]:
        if self.claimed_at is not None:
            return "consumed"
        if self.revoked_at is not None:
            return "revoked"
        return "expired" if self.expires_at <= datetime.now(UTC) else "active"


class InvitationIssued(BaseModel):
    invitation: InvitationRead
    code: str


class RegistrationPolicy(BaseModel):
    research: Literal["independent", "disabled"]
    internal: Literal["invitation", "disabled"]
    password_min_length: int = 12
