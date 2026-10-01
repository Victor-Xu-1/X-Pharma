from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pharma_intel.models.enums import (
    UserRole,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


def _validate_human_display_name(value: str) -> str:
    if not any(character.isalnum() for character in value):
        raise ValueError("display_name must include at least one letter or number")
    return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    organization_id: str | None = Field(default=None, min_length=36, max_length=36)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    email: str
    display_name: str
    phone: str | None
    avatar_url: str | None
    role: UserRole
    organization_name: str | None = None


class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    avatar_url: str | None = Field(default=None, max_length=2048)

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = urlsplit(value)
            valid = (
                parsed.scheme == "https"
                and parsed.hostname is not None
                and not any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value)
                and parsed.username is None
                and parsed.password is None
                and (parsed.port is None or parsed.port > 0)
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("头像地址必须使用有效且不含凭据的 HTTPS 地址")
        return value

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        return _validate_human_display_name(value) if value is not None else None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> UserProfileUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one profile field must be supplied")
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("display_name cannot be null")
        return self


class UserPasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)
