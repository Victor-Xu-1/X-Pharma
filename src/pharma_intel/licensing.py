from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DeliveryChannel = Literal["web", "mcp"]
EvidenceDeliveryField = Literal[
    "content",
    "document_name",
    "source_uri",
    "locator",
    "source_document_id",
    "source_version_id",
    "content_sha256",
    "evidence_claim_id",
    "subject_entity_id",
    "review_status",
]


class EvidenceLicensePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    license_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,119}$")
    policy_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")
    permitted_channels: list[DeliveryChannel] = Field(min_length=1)
    allowed_fields: list[EvidenceDeliveryField] = Field(min_length=1)
    max_content_chars: int = Field(default=2000, ge=1, le=20_000)
    attribution: str = Field(min_length=1, max_length=500)
    valid_from: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("permitted_channels", "allowed_fields")
    @classmethod
    def unique_sorted_values(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("License policy lists must not contain duplicates")
        return sorted(value)

    @model_validator(mode="after")
    def validate_window(self) -> EvidenceLicensePolicy:
        if self.valid_from and self.expires_at and _as_utc(self.expires_at) <= _as_utc(self.valid_from):
            raise ValueError("License expiration must be after its validity start")
        return self

    def permits(self, channel: DeliveryChannel, at: datetime) -> bool:
        timestamp = _as_utc(at)
        return (
            channel in self.permitted_channels
            and (self.valid_from is None or _as_utc(self.valid_from) <= timestamp)
            and (self.expires_at is None or _as_utc(self.expires_at) > timestamp)
        )

    def document(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


def internal_evidence_license_policy(*, source: str) -> dict[str, Any]:
    return EvidenceLicensePolicy(
        license_id="tenant-owned-internal",
        policy_version="tenant-owned-v1",
        permitted_channels=["web", "mcp"],
        allowed_fields=[
            "content",
            "content_sha256",
            "document_name",
            "evidence_claim_id",
            "locator",
            "review_status",
            "source_document_id",
            "source_uri",
            "source_version_id",
            "subject_entity_id",
        ],
        max_content_chars=5000,
        attribution="Tenant-provided source material",
        metadata={"source": source},
    ).document()


@dataclass(frozen=True)
class LicensedEvidenceDelivery:
    content: str
    document_name: str
    positions: list[Any]
    metadata: dict[str, Any]
    warnings: list[str]


def apply_evidence_license(
    policy: EvidenceLicensePolicy,
    *,
    dataset_key: str,
    content: str,
    document_name: str,
    positions: list[Any],
    metadata: dict[str, Any],
) -> LicensedEvidenceDelivery:
    allowed = set(policy.allowed_fields)
    omitted: list[str] = []
    warnings: list[str] = []

    delivered_content = ""
    if "content" in allowed:
        delivered_content = content[: policy.max_content_chars]
        if len(content) > policy.max_content_chars:
            warnings.append(
                f"Dataset {dataset_key} content was truncated to "
                f"{policy.max_content_chars} characters by license policy"
            )
    elif content:
        omitted.append("content")

    delivered_name = document_name if "document_name" in allowed else ""
    if document_name and "document_name" not in allowed:
        omitted.append("document_name")

    delivered_positions = positions if "locator" in allowed else []
    if positions and "locator" not in allowed:
        omitted.append("locator")

    metadata_fields = {
        "source_uri": "source",
        "source_document_id": "source_document_id",
        "source_version_id": "source_version_id",
        "content_sha256": "content_sha256",
        "evidence_claim_id": "evidence_claim_id",
        "subject_entity_id": "subject_entity_id",
        "review_status": "review_status",
    }
    delivered_metadata: dict[str, Any] = {}
    for license_field, source_field in metadata_fields.items():
        value = metadata.get(source_field)
        if license_field in allowed:
            delivered_metadata[source_field] = value
        elif value is not None:
            omitted.append(license_field)
    delivered_metadata["license"] = {
        "schema_version": policy.schema_version,
        "license_id": policy.license_id,
        "policy_version": policy.policy_version,
        "attribution": policy.attribution,
    }
    if omitted:
        warnings.append(f"Dataset {dataset_key} license policy omitted fields: {', '.join(sorted(omitted))}")
    return LicensedEvidenceDelivery(
        content=delivered_content,
        document_name=delivered_name,
        positions=delivered_positions,
        metadata=delivered_metadata,
        warnings=warnings,
    )


class ExportDatasetFieldPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fields: list[str] = Field(min_length=1, max_length=100)
    filter_fields: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("fields", "filter_fields")
    @classmethod
    def validate_field_names(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Export policy fields must not contain duplicates")
        if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", item) for item in value):
            raise ValueError("Export policy field names are invalid")
        return sorted(value)

    @model_validator(mode="after")
    def require_id(self) -> ExportDatasetFieldPolicy:
        if "id" not in self.fields:
            raise ValueError("Every export dataset policy must include id")
        return self


class ExportFieldPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    policy_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")
    attribution: str = Field(min_length=1, max_length=500)
    datasets: dict[str, ExportDatasetFieldPolicy] = Field(min_length=1, max_length=50)

    @field_validator("datasets")
    @classmethod
    def validate_dataset_keys(cls, value: dict[str, ExportDatasetFieldPolicy]) -> dict[str, ExportDatasetFieldPolicy]:
        if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", key) for key in value):
            raise ValueError("Export policy dataset keys are invalid")
        return dict(sorted(value.items()))

    def document(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def full_export_field_policy(
    catalog: Mapping[str, tuple[Sequence[str], Sequence[str]]],
    *,
    policy_version: str,
    attribution: str,
) -> dict[str, Any]:
    return ExportFieldPolicy(
        policy_version=policy_version,
        attribution=attribution,
        datasets={
            key: ExportDatasetFieldPolicy(fields=list(fields), filter_fields=list(filter_fields))
            for key, (fields, filter_fields) in catalog.items()
        },
    ).document()


def canonical_policy_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
