from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from pharma_intel.licensing import (
    EvidenceLicensePolicy,
    ExportFieldPolicy,
    apply_evidence_license,
    canonical_policy_sha256,
)


def test_evidence_license_enforces_channel_window_and_schema() -> None:
    now = datetime(2026, 7, 17, tzinfo=UTC)
    policy = EvidenceLicensePolicy(
        license_id="licensed-source-1",
        policy_version="contract-v3",
        permitted_channels=["mcp"],
        allowed_fields=["content", "document_name"],
        max_content_chars=100,
        attribution="Licensed source",
        valid_from=now - timedelta(days=1),
        expires_at=now + timedelta(days=1),
    )

    assert policy.permits("mcp", now) is True
    assert policy.permits("web", now) is False
    assert policy.permits("mcp", now + timedelta(days=2)) is False

    with pytest.raises(ValidationError):
        EvidenceLicensePolicy.model_validate(
            {
                **policy.document(),
                "unexpected": "fail closed",
            }
        )
    with pytest.raises(ValidationError):
        EvidenceLicensePolicy.model_validate(
            {
                **policy.document(),
                "valid_from": now,
                "expires_at": now,
            }
        )


def test_evidence_delivery_truncates_and_omits_fields_explicitly() -> None:
    policy = EvidenceLicensePolicy(
        license_id="abstract-only-1",
        policy_version="contract-v1",
        permitted_channels=["mcp"],
        allowed_fields=["content"],
        max_content_chars=4,
        attribution="Abstract-only license",
    )

    delivery = apply_evidence_license(
        policy,
        dataset_key="licensed-literature",
        content="abcdefgh",
        document_name="private-document.pdf",
        positions=[{"page": 8}],
        metadata={
            "source": "s3://private/source",
            "source_version_id": "source-v1",
            "content_sha256": "a" * 64,
        },
    )

    assert delivery.content == "abcd"
    assert delivery.document_name == ""
    assert delivery.positions == []
    assert delivery.metadata == {
        "license": {
            "schema_version": "1.0",
            "license_id": "abstract-only-1",
            "policy_version": "contract-v1",
            "attribution": "Abstract-only license",
        }
    }
    assert any("truncated" in warning for warning in delivery.warnings)
    assert any("omitted fields" in warning for warning in delivery.warnings)


def test_export_field_policy_requires_identity_and_hashes_canonically() -> None:
    first = ExportFieldPolicy.model_validate(
        {
            "schema_version": "1.0",
            "policy_version": "contract-v1",
            "attribution": "Licensed entity data",
            "datasets": {
                "entities": {
                    "fields": ["name", "id"],
                    "filter_fields": ["name", "id"],
                }
            },
        }
    )
    second = ExportFieldPolicy.model_validate(
        {
            "schema_version": "1.0",
            "policy_version": "contract-v1",
            "attribution": "Licensed entity data",
            "datasets": {
                "entities": {
                    "fields": ["id", "name"],
                    "filter_fields": ["id", "name"],
                }
            },
        }
    )
    assert canonical_policy_sha256(first.document()) == canonical_policy_sha256(second.document())

    with pytest.raises(ValidationError):
        ExportFieldPolicy.model_validate(
            {
                "policy_version": "contract-v1",
                "attribution": "Licensed entity data",
                "datasets": {
                    "entities": {
                        "fields": ["name"],
                        "filter_fields": [],
                    }
                },
            }
        )
