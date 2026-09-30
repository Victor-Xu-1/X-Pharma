from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel import bootstrap
from pharma_intel.config import get_settings
from pharma_intel.models import ApiKey, DataSource, Tenant, TenantDataset, User, UserRole


class SessionContext:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> Session:
        return self.session

    def __exit__(self, *_args: object) -> None:
        return None


def test_bootstrap_creates_tenant_admin_key_dataset_and_source(
    session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(bootstrap, "get_session_factory", lambda: lambda: SessionContext(session))
    monkeypatch.setenv("SOURCE_ROOTS", str(tmp_path))
    get_settings.cache_clear()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pharma-bootstrap",
            "--tenant-slug",
            "enterprise",
            "--tenant-name",
            "Enterprise Tenant",
            "--admin-email",
            "admin@example.test",
            "--admin-password",
            "strong-bootstrap-password",
            "--dataset",
            "literature",
            "--source",
            f"Literature|{tmp_path}|literature",
            "--source-owner",
            "Research Operations",
            "--source-authorization-scope",
            " contract:test-literature ",
            "--source-authorization-valid-from",
            "2026-01-01T00:00:00+00:00",
            "--source-authorization-valid-until",
            "2027-01-01T00:00:00+00:00",
        ],
    )

    bootstrap.run()

    tenant = session.scalar(select(Tenant).where(Tenant.slug == "enterprise"))
    assert tenant is not None
    user = session.scalar(select(User).where(User.tenant_id == tenant.id))
    assert user is not None and user.role == UserRole.ADMIN
    assert session.scalar(select(ApiKey).where(ApiKey.tenant_id == tenant.id)) is not None
    assert session.scalar(select(TenantDataset).where(TenantDataset.tenant_id == tenant.id)) is not None
    source = session.scalar(select(DataSource).where(DataSource.tenant_id == tenant.id))
    assert source is not None
    assert source.authorization_scopes == ["contract:test-literature"]
    assert source.authorization_valid_from.replace(tzinfo=UTC) == datetime(2026, 1, 1, tzinfo=UTC)
    assert source.authorization_valid_until is not None
    assert source.authorization_valid_until.replace(tzinfo=UTC) == datetime(2027, 1, 1, tzinfo=UTC)
    output = capsys.readouterr().out
    assert "phk_" in output
    assert "Human administrator created" in output
    get_settings.cache_clear()


def test_bootstrap_creates_logical_opensearch_dataset(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bootstrap, "get_session_factory", lambda: lambda: SessionContext(session))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pharma-bootstrap",
            "--tenant-slug",
            "opensearch-only",
            "--tenant-name",
            "OpenSearch Only",
            "--skip-api-key",
            "--dataset",
            "literature",
        ],
    )

    bootstrap.run()

    tenant = session.scalar(select(Tenant).where(Tenant.slug == "opensearch-only"))
    assert tenant is not None
    dataset = session.scalar(select(TenantDataset).where(TenantDataset.tenant_id == tenant.id))
    assert dataset is not None
    assert dataset.dataset_key == "literature"


def test_bootstrap_rejects_source_bound_to_expired_dataset_license(
    session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy_file = tmp_path / "expired-license.json"
    policy_file.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "license_id": "expired-test-license",
                "policy_version": "v1",
                "permitted_channels": ["web", "mcp"],
                "allowed_fields": ["content"],
                "attribution": "Expired test data",
                "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(bootstrap, "get_session_factory", lambda: lambda: SessionContext(session))
    monkeypatch.setenv("SOURCE_ROOTS", str(tmp_path))
    get_settings.cache_clear()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pharma-bootstrap",
            "--tenant-slug",
            "expired-source-license",
            "--tenant-name",
            "Expired Source License",
            "--skip-api-key",
            "--dataset",
            "literature",
            "--dataset-license",
            f"literature={policy_file}",
            "--source",
            f"Literature|{tmp_path}|literature",
            "--source-owner",
            "Research Operations",
            "--source-authorization-scope",
            "contract:test-literature",
        ],
    )

    with pytest.raises(SystemExit):
        bootstrap.run()

    assert session.scalar(select(DataSource)) is None
    session.rollback()
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "arguments",
    [
        ["--admin-password", "password-without-email"],
        ["--admin-email", "admin@example.test"],
        ["--admin-email", "admin@example.test", "--admin-password", "short"],
        ["--admin-oidc-issuer", "https://identity.example.test"],
    ],
)
def test_bootstrap_rejects_incomplete_identity_arguments(
    arguments: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pharma-bootstrap",
            "--tenant-slug",
            "invalid",
            "--tenant-name",
            "Invalid Tenant",
            *arguments,
        ],
    )

    with pytest.raises(SystemExit):
        bootstrap.run()
