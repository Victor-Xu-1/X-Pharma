from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_intel.identity import EntityIdentityService
from pharma_intel.models import Base, DataSource, DataSourceType, EntityType, ResolutionStatus, ReviewStatus, Tenant
from pharma_intel.repository import EntityRepository
from pharma_intel.schemas import EntityCreate
from tests.support.postgres_safety import require_disposable_postgres_url


@pytest.mark.integration
def test_entity_search_with_json_columns_on_postgres() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_DATABASE_URL")

    engine = create_engine(database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            tenant = Tenant(slug="postgres-test", name="PostgreSQL Test")
            session.add(tenant)
            session.commit()
            repository = EntityRepository(session, tenant.id)
            created = repository.create(
                EntityCreate(
                    entity_type=EntityType.TARGET,
                    name="Epidermal growth factor receptor",
                    aliases=["EGFR"],
                    external_ids={"uniprot": "P00533"},
                    attributes={"organism": "Homo sapiens"},
                )
            )

            items, total = repository.search("EGFR", EntityType.TARGET, 20, 0)

            assert total == 1
            assert [item.id for item in items] == [created.id]
            repository.create(EntityCreate(entity_type=EntityType.TARGET, name="EGFR Alpha"))
            repository.create(EntityCreate(entity_type=EntityType.TARGET, name="EGFR Beta"))
            sorted_items, sorted_total = repository.search(
                "EGFR",
                EntityType.TARGET,
                1,
                1,
                sort_by="name",
                sort_direction="desc",
            )
            assert sorted_total == 3
            assert [item.name for item in sorted_items] == ["EGFR Beta"]
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.integration
def test_conflicting_trusted_identifiers_are_reviewed_on_postgres() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_DATABASE_URL")

    engine = create_engine(database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            tenant = Tenant(slug="identity-postgres-test", name="Identity PostgreSQL Test")
            session.add(tenant)
            session.commit()
            repository = EntityRepository(session, tenant.id)
            first = repository.create(
                EntityCreate(entity_type=EntityType.TARGET, name="Target A", external_ids={"hgnc": "427"})
            )
            second = repository.create(
                EntityCreate(entity_type=EntityType.TARGET, name="Target B", external_ids={"uniprot": "P00533"})
            )
            identity = EntityIdentityService(session, tenant.id)
            identity.sync_identifiers(first, {"hgnc": "427"}, review_status=ReviewStatus.VERIFIED)
            identity.sync_identifiers(second, {"uniprot": "P00533"}, review_status=ReviewStatus.VERIFIED)

            source = identity.resolve_or_create(
                {
                    "entity_type": "target",
                    "name": "Conflicting bridge",
                    "external_ids": {"hgnc": "427", "uniprot": "P00533"},
                }
            )
            cases = identity.list_cases(status=ResolutionStatus.PENDING, limit=10)

            assert source.review_status == ReviewStatus.DRAFT
            assert {case.candidate_entity_id for case in cases} == {first.id, second.id}
            assert all(case.risk_tier == "high" for case in cases)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.integration
def test_source_authorization_window_constraint_on_postgres() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_DATABASE_URL")

    engine = create_engine(database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            tenant = Tenant(slug="authorization-postgres-test", name="Authorization PostgreSQL Test")
            session.add(tenant)
            session.commit()
            now = datetime.now(UTC)
            session.add(
                DataSource(
                    tenant_id=tenant.id,
                    name="Invalid authorization",
                    source_type=DataSourceType.FOLDER,
                    root_uri="/sources/invalid-authorization",
                    owner="Research Operations",
                    authorization_scopes=["contract:test"],
                    authorization_valid_from=now,
                    authorization_valid_until=now - timedelta(seconds=1),
                    dataset_key="literature",
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
