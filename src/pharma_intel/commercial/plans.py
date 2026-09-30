from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class RateCardItemDefinition(BaseModel):
    billing_class: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    entitlement_key: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    base_units: Decimal = Field(ge=0, max_digits=28, decimal_places=8)
    per_result_units: Decimal = Field(ge=0, max_digits=28, decimal_places=8)
    per_kib_units: Decimal = Field(ge=0, max_digits=28, decimal_places=8)
    per_compute_unit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=28, decimal_places=8)
    max_result_rows: int = Field(gt=0, le=5000)


class RateCardDefinition(BaseModel):
    rate_card_key: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,119}$")
    revision: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    effective_from: datetime
    effective_until: datetime | None = None
    items: list[RateCardItemDefinition] = Field(min_length=1, max_length=200)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.upper()
        if not normalized.isalpha():
            raise ValueError("Currency must be a three-letter ISO-style code")
        return normalized

    @model_validator(mode="after")
    def validate_definition(self) -> RateCardDefinition:
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise ValueError("effective_until must be after effective_from")
        billing_classes = [item.billing_class for item in self.items]
        if len(set(billing_classes)) != len(billing_classes):
            raise ValueError("Rate-card billing classes must be unique")
        return self

    def canonical_json(self) -> str:
        payload = self.model_dump(mode="json")
        return json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
