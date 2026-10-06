from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_intel.config import get_settings
from pharma_intel.models import DevelopmentPhase, DevelopmentProgram, Entity, EntityType, Tenant


def test_explicit_stage_migration_preserves_old_records_and_refuses_stage_loss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = f"sqlite:///{tmp_path / 'explicit-stage.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "d32a6c1f9e74")
    engine = create_engine(url)
    try:
        with Session(engine, expire_on_commit=False) as session:
            tenant = Tenant(slug="phase-migration", name="Phase migration")
            session.add(tenant)
            session.flush()
            drug = Entity(
                tenant_id=tenant.id,
                entity_type=EntityType.DRUG,
                name="Migration drug",
                normalized_name="migration drug",
            )
            session.add(drug)
            session.flush()
            old = DevelopmentProgram(tenant_id=tenant.id, drug_entity_id=drug.id, phase=DevelopmentPhase.APPROVED)
            session.add(old)
            session.commit()
            old_id, tenant_id, drug_id = old.id, tenant.id, drug.id
        command.upgrade(config, "head")
        with Session(engine, expire_on_commit=False) as session:
            preserved = session.get(DevelopmentProgram, old_id)
            assert preserved is not None and preserved.phase == DevelopmentPhase.APPROVED
            early = DevelopmentProgram(
                tenant_id=tenant_id,
                drug_entity_id=drug_id,
                phase=DevelopmentPhase.EARLY_PHASE_1,
                global_phase="early_phase_1",
                china_phase="unknown",
            )
            session.add(early)
            session.commit()
            early_id = early.id
        with pytest.raises(RuntimeError, match="preservation plan"):
            command.downgrade(config, "d32a6c1f9e74")
        with Session(engine) as session:
            assert session.get(DevelopmentProgram, old_id) is not None
            preserved_early = session.get(DevelopmentProgram, early_id)
            assert preserved_early is not None and preserved_early.phase == DevelopmentPhase.EARLY_PHASE_1
            assert preserved_early.global_phase == "early_phase_1" and preserved_early.china_phase == "unknown"
    finally:
        engine.dispose()
        get_settings.cache_clear()
