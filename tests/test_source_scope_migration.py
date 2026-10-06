from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import JSON, Column, MetaData, String, Table, UniqueConstraint, create_engine, select

from pharma_intel.ingest.source_routing import source_scope_digest
from pharma_intel.models import DataSourceType


def test_source_scope_migration_preserves_topics_and_refuses_loss() -> None:
    file = Path(__file__).parents[1] / "migrations/versions/b8f41d6c2e93_scope_public_sources_by_query.py"
    spec = importlib.util.spec_from_file_location("source_scope_migration", file)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    metadata = MetaData()
    sources = Table(
        "data_sources",
        metadata,
        Column("id", String, primary_key=True),
        Column("tenant_id", String),
        Column("root_uri", String),
        Column("source_type", String),
        Column("routing_rules", JSON),
        UniqueConstraint("tenant_id", "root_uri"),
    )
    metadata.create_all(engine)
    rule = {"target_chembl_id": "CHEMBL203", "max_records": 25, "page_size": 25, "sync_mode": "continuous"}
    with engine.begin() as connection:
        connection.execute(
            sources.insert().values(
                id="source-1", tenant_id="tenant", root_uri="same-root", source_type="CHEMBL", routing_rules=[rule]
            )
        )
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        upgraded = Table("data_sources", MetaData(), autoload_with=connection)
        row = connection.execute(select(upgraded)).mappings().one()
        assert row["routing_rules"] == [rule]
        assert row["scope_digest"] == source_scope_digest(DataSourceType.CHEMBL, [rule])
        connection.execute(
            upgraded.insert().values(
                id="source-2",
                tenant_id="tenant",
                root_uri="same-root",
                source_type="CHEMBL",
                routing_rules=[rule],
                scope_digest="other",
            )
        )
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match="preservation plan"):
                migration.downgrade()
        assert len(connection.execute(select(upgraded)).all()) == 2
    engine.dispose()
