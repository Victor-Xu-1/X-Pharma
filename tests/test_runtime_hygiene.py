from __future__ import annotations

import hashlib
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.accounts.identity import create_account
from pharma_intel.config import Settings
from pharma_intel.models import (
    AgentClient,
    ApiKey,
    Base,
    BillingAccount,
    DataSource,
    DataSourceType,
    Entity,
    EntityType,
    Tenant,
    UserRole,
)
from pharma_intel.runtime_hygiene import inspect_runtime_hygiene


@pytest.fixture
def hygiene_factory(tmp_path: Path) -> Generator[sessionmaker[Session]]:
    engine = create_engine(f"sqlite:///{tmp_path / 'hygiene.db'}")
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        engine.dispose()


def test_runtime_hygiene_accepts_clean_runtime(
    tmp_path: Path,
    hygiene_factory: sessionmaker[Session],
) -> None:
    factory = hygiene_factory
    object_root = tmp_path / "objects"
    object_root.mkdir()
    credential_hash = hashlib.sha256(b"runtime-hygiene-clean-fixture").hexdigest()
    with factory() as session:
        tenant = Tenant(slug="customer", name="Customer")
        session.add(tenant)
        session.flush()
        (object_root / tenant.id).mkdir()
        session.add(
            create_account(
                tenant_id=tenant.id,
                email="operator@customer.invalid",
                normalized_email="operator@customer.invalid",
                display_name="Operator",
                password_hash=credential_hash,
                role=UserRole.ADMIN,
            )
        )
        session.commit()

    report = inspect_runtime_hygiene(
        factory,
        Settings(object_store_backend="filesystem", object_store_root=object_root),
    )

    assert report.as_dict() == {
        "schema_version": 1,
        "status": "passed",
        "finding_count": 0,
        "findings": [],
    }


def test_runtime_hygiene_reports_synthetic_and_orphaned_state(
    tmp_path: Path,
    hygiene_factory: sessionmaker[Session],
) -> None:
    factory = hygiene_factory
    object_root = tmp_path / "objects"
    object_root.mkdir()
    orphan_id = "10000000-0000-0000-0000-000000000001"
    (object_root / orphan_id).mkdir()
    credential_hash = hashlib.sha256(b"runtime-hygiene-synthetic-fixture").hexdigest()
    temporary_root = "/" + "tmp/pytest-example/source"
    with factory() as session:
        tenant = Tenant(slug="governed-chem-10000000-0000-0000-0000-000000000002", name="Chemistry Test")
        session.add(tenant)
        session.flush()
        session.add_all(
            [
                create_account(
                    tenant_id=tenant.id,
                    email="acceptance@example.test",
                    normalized_email="acceptance@example.test",
                    display_name="Acceptance",
                    password_hash=credential_hash,
                    role=UserRole.ADMIN,
                ),
                DataSource(
                    tenant_id=tenant.id,
                    name="Temporary Source",
                    source_type=DataSourceType.FOLDER,
                    root_uri=temporary_root,
                    dataset_key="projects",
                ),
                Entity(
                    tenant_id=tenant.id,
                    entity_type=EntityType.TARGET,
                    name="Fixture target",
                    normalized_name="fixture target",
                    attributes={"acceptance_fixture": True},
                ),
                ApiKey(
                    tenant_id=tenant.id,
                    name="Search acceptance",
                    prefix="acceptance",
                    secret_hash=hashlib.sha256(b"acceptance-api-key").hexdigest(),
                    scopes=["search:read"],
                ),
                AgentClient(
                    tenant_id=tenant.id,
                    client_key="search-assertion",
                    oauth_client_id="search-assertion",
                    display_name="Search assertion",
                ),
                BillingAccount(
                    tenant_id=tenant.id,
                    account_key="acceptance-account",
                    display_name="Acceptance account",
                    currency="CNY",
                ),
            ]
        )
        session.commit()

    report = inspect_runtime_hygiene(
        factory,
        Settings(object_store_backend="filesystem", object_store_root=object_root),
    )

    findings = {finding.code: finding for finding in report.findings}
    assert report.status == "failed"
    assert set(findings) == {
        "acceptance_fixtures",
        "active_test_agent_clients",
        "active_test_api_keys",
        "active_test_billing_accounts",
        "orphan_object_namespaces",
        "synthetic_tenants",
        "temporary_accounts",
        "temporary_source_roots",
    }
    assert findings["orphan_object_namespaces"].identifiers == [orphan_id]


def test_runtime_hygiene_reports_content_in_an_inactive_synthetic_tenant(
    tmp_path: Path,
    hygiene_factory: sessionmaker[Session],
) -> None:
    factory = hygiene_factory
    object_root = tmp_path / "objects"
    object_root.mkdir()
    with factory() as session:
        tenant = Tenant(slug="acceptance", name="Acceptance Tenant", active=False)
        session.add(tenant)
        session.flush()
        session.add(
            Entity(
                tenant_id=tenant.id,
                entity_type=EntityType.TARGET,
                name="Historical acceptance fixture",
                normalized_name="historical acceptance fixture",
                attributes={"acceptance_fixture": True},
            )
        )
        session.commit()

    report = inspect_runtime_hygiene(
        factory,
        Settings(object_store_backend="filesystem", object_store_root=object_root),
    )

    findings = {finding.code: finding for finding in report.findings}
    assert report.status == "failed"
    assert findings["inactive_synthetic_tenant_content"].identifiers == [tenant.id]
