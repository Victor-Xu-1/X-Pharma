from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.config import Settings
from pharma_intel.ingest.cli import collect_ingestion_readiness, inspect_source
from pharma_intel.ingest.connectors import FolderSourceConnector, SourceConnectorRegistry
from pharma_intel.ingest.readiness import SourceReadinessService
from pharma_intel.ingest.source_roots import SourceRootPolicyError, validate_folder_source_root
from pharma_intel.licensing import EvidenceLicensePolicy, internal_evidence_license_policy
from pharma_intel.models import DataSource, DataSourceType, Tenant, TenantDataset


def _source(tenant_id: str, root: Path) -> DataSource:
    return DataSource(
        tenant_id=tenant_id,
        name="Licensed literature",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Research Operations",
        data_classification="confidential",
        authorization_scopes=["contract:literature-2026"],
        authorization_valid_from=datetime.now(UTC) - timedelta(seconds=1),
        dataset_key="literature",
        include_globs=["*", "**/*"],
        exclude_globs=[],
        stable_seconds=0,
        max_file_bytes=1_073_741_824,
        expected_freshness_seconds=3600,
    )


def test_source_root_policy_rejects_unlisted_and_symlink_escape(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    nested = allowed / "team"
    outside = tmp_path / "outside"
    nested.mkdir(parents=True)
    outside.mkdir()

    assert validate_folder_source_root(nested, [allowed], require_existing=True) == nested.resolve()
    with pytest.raises(SourceRootPolicyError, match="outside"):
        validate_folder_source_root(outside, [allowed], require_existing=True)
    with pytest.raises(SourceRootPolicyError, match="No folder"):
        validate_folder_source_root(nested, [], require_existing=True)

    escape = allowed / "escape"
    escape.symlink_to(outside, target_is_directory=True)
    with pytest.raises(SourceRootPolicyError, match="outside"):
        validate_folder_source_root(escape, [allowed], require_existing=True)


def test_folder_connector_has_stable_inventory_cursor_and_snapshot_handle(
    tmp_path: Path,
    tenant: Tenant,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    document = root / "evidence.md"
    document.write_text("EGFR evidence", encoding="utf-8")
    source = _source(tenant.id, root)
    settings = Settings(source_roots_config=str(tmp_path))
    connector = FolderSourceConnector(settings)

    first = connector.discover(source)
    second = connector.discover(source)

    assert connector.capabilities.incremental is True
    assert connector.capabilities.replayable is True
    assert first.cursor == second.cursor
    assert first.cursor["object_count"] == 1
    assert first.objects[0].source_uri == str(document.resolve())
    with connector.materialize(first.objects[0]) as materialized:
        materialized_path = materialized
        assert materialized != document
        assert materialized.read_text(encoding="utf-8") == "EGFR evidence"
    assert not materialized_path.exists()
    assert SourceConnectorRegistry(settings).get(DataSourceType.FOLDER).capabilities.connector_id == "folder-v1"


def test_connector_inspection_reports_safe_authoritative_inventory(tmp_path: Path, tenant: Tenant) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "evidence.md").write_text("EGFR evidence", encoding="utf-8")
    source = _source(tenant.id, root)

    result = inspect_source(source, Settings(source_roots_config=str(tmp_path)))

    assert result == {
        "schema_version": 1,
        "source_id": source.id,
        "source_type": "folder",
        "connector_id": "folder-v1",
        "authoritative_inventory": True,
        "discovered": 1,
        "stable": 1,
        "oversized": 0,
        "excluded": 0,
        "error_count": 0,
        "configuration_error_count": 0,
    }


def test_ingestion_readiness_distinguishes_an_empty_ready_platform_from_ingestion_evidence(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    settings = Settings(
        source_roots_config=str(tmp_path),
        temporal_enabled=True,
        temporal_worker_enabled=True,
        temporal_scheduler_enabled=True,
        malware_scan_enabled=True,
        parser_backend="service",
    )

    report = collect_ingestion_readiness(settings, factory)

    assert report["status"] == "ready_for_source_registration"
    assert report["production_claim"] is False
    assert report["real_source_automatic_ingestion_verified"] is False
    assert report["inventory"] == {
        "active_tenant_count": 1,
        "registered_source_count": 0,
        "configuration_ready_source_count": 0,
        "blocked_source_count": 0,
    }
    connectors = report["connectors"]
    assert isinstance(connectors, list)
    assert {item["connector_id"] for item in connectors} == {
        "clinicaltrials-gov-v2",
        "chembl-rest-v1",
        "folder-v1",
        "http-manifest-v1",
        "pubmed-eutilities-v1",
        "s3-snapshot-v1",
        "sftp-snapshot-v1",
        "smb-snapshot-v1",
    }


def test_ingestion_readiness_fails_closed_and_redacts_registered_source_identity(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "licensed-secret-source"
    root.mkdir()
    source = _source(tenant.id, root)
    source.name = "Confidential supplier name"
    session.add(source)
    session.commit()
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    settings = Settings(
        source_roots_config=str(tmp_path),
        temporal_enabled=True,
        temporal_worker_enabled=True,
        temporal_scheduler_enabled=True,
        malware_scan_enabled=True,
        parser_backend="service",
    )

    report = collect_ingestion_readiness(settings, factory)

    assert report["status"] == "blocked"
    assert report["inventory"]["blocked_source_count"] == 1
    serialized = str(report)
    assert source.id not in serialized
    assert source.name not in serialized
    assert str(root) not in serialized
    source_report = report["sources"][0]
    assert source_report["source_ref"] != source.id
    assert {check["code"] for check in source_report["checks"] if check["status"] == "fail"} == {"dataset"}


def test_folder_connector_rejects_source_mutation_after_discovery(tmp_path: Path, tenant: Tenant) -> None:
    root = tmp_path / "source"
    root.mkdir()
    document = root / "evidence.md"
    document.write_text("initial evidence", encoding="utf-8")
    source = _source(tenant.id, root)
    connector = FolderSourceConnector(Settings(source_roots_config=str(tmp_path)))
    discovered = connector.discover(source).objects[0]

    document.write_text("changed evidence with a different size", encoding="utf-8")

    with pytest.raises(ValueError, match="changed after discovery"):
        with connector.materialize(discovered):
            pytest.fail("Mutated source must not be materialized")


def test_readiness_binds_owner_authorization_dataset_license_and_freshness(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    dataset = TenantDataset(
        tenant_id=tenant.id,
        dataset_key="literature",
        display_name="Literature",
        license_policy=internal_evidence_license_policy(source="test"),
    )
    source = _source(tenant.id, root)
    now = datetime.now(UTC)
    source.last_success_at = now - timedelta(hours=2)
    source.connector_cursor = {"schema_version": "1.0", "inventory_sha256": "0" * 64}
    source.last_cursor_at = now - timedelta(hours=2)
    session.add_all([dataset, source])
    session.commit()

    result = SourceReadinessService(
        session,
        Settings(source_roots_config=str(tmp_path)),
        tenant.id,
    ).evaluate(source, now=now)

    assert result.configuration_ready is True
    assert result.operational_status == "stale"
    assert result.delivery_channels == ["web", "mcp"]
    assert result.cursor_present is True
    assert any(check.code == "freshness" and check.status == "warn" for check in result.checks)


def test_readiness_fails_closed_for_unowned_source_and_invalid_license(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    dataset = TenantDataset(
        tenant_id=tenant.id,
        dataset_key="literature",
        display_name="Literature",
        license_policy={"untrusted": True},
    )
    source = _source(tenant.id, root)
    source.owner = "migration-unassigned"
    source.authorization_scopes = []
    session.add_all([dataset, source])
    session.commit()

    result = SourceReadinessService(
        session,
        Settings(source_roots_config=str(tmp_path)),
        tenant.id,
    ).evaluate(source)

    assert result.configuration_ready is False
    assert result.operational_status == "blocked"
    assert {check.code for check in result.checks if check.status == "fail"} == {
        "authorization_scopes",
        "license_policy",
        "owner",
    }


def test_readiness_preserves_valid_single_channel_license_as_policy_limited(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    policy = EvidenceLicensePolicy(
        license_id="web-only-license",
        policy_version="2026-01",
        permitted_channels=["web"],
        allowed_fields=["content", "source_version_id"],
        attribution="Licensed for internal Web use",
    )
    session.add(
        TenantDataset(
            tenant_id=tenant.id,
            dataset_key="literature",
            display_name="Literature",
            license_policy=policy.document(),
        )
    )
    source = _source(tenant.id, root)
    session.add(source)
    session.commit()

    result = SourceReadinessService(
        session,
        Settings(source_roots_config=str(tmp_path)),
        tenant.id,
    ).evaluate(source)

    assert result.configuration_ready is True
    assert result.delivery_channels == ["web"]
    assert any(check.code == "delivery_channels" and check.status == "warn" for check in result.checks)


@pytest.mark.parametrize(
    ("valid_from_offset", "valid_until_offset", "expected_code"),
    [
        (timedelta(days=1), timedelta(days=31), "authorization_not_yet_valid"),
        (timedelta(days=-31), timedelta(seconds=-1), "authorization_expired"),
    ],
)
def test_readiness_fails_closed_outside_source_authorization_window(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    valid_from_offset: timedelta,
    valid_until_offset: timedelta,
    expected_code: str,
) -> None:
    root = tmp_path / expected_code
    root.mkdir()
    now = datetime.now(UTC)
    source = _source(tenant.id, root)
    source.authorization_valid_from = now + valid_from_offset
    source.authorization_valid_until = now + valid_until_offset
    session.add_all(
        [
            source,
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key="literature",
                display_name="Literature",
                license_policy=internal_evidence_license_policy(source="test"),
            ),
        ]
    )
    session.commit()

    result = SourceReadinessService(
        session,
        Settings(source_roots_config=str(tmp_path)),
        tenant.id,
    ).evaluate(source, now=now)

    assert result.configuration_ready is False
    assert result.operational_status == "blocked"
    assert any(check.code == expected_code and check.status == "fail" for check in result.checks)


def test_readiness_warns_before_source_authorization_expires(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "expiring"
    root.mkdir()
    now = datetime.now(UTC)
    source = _source(tenant.id, root)
    source.authorization_valid_from = now - timedelta(days=1)
    source.authorization_valid_until = now + timedelta(days=30)
    session.add_all(
        [
            source,
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key="literature",
                display_name="Literature",
                license_policy=internal_evidence_license_policy(source="test"),
            ),
        ]
    )
    session.commit()

    result = SourceReadinessService(
        session,
        Settings(source_roots_config=str(tmp_path)),
        tenant.id,
    ).evaluate(source, now=now)

    assert result.configuration_ready is True
    assert any(check.code == "authorization_expiring" and check.status == "warn" for check in result.checks)
