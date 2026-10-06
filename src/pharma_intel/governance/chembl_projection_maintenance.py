from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from pharma_intel.governance.chembl_projection_proof import prove_legacy_regional_projection
from pharma_intel.governance.projection_repair_models import RegionalRepairPlan, RegionalRepairResult
from pharma_intel.models import (
    AuditEvent,
    DataSource,
    DataSourceType,
    DevelopmentProgram,
    FactProvenanceLink,
    OutboxEvent,
    SourceAsset,
)
from pharma_intel.object_store import ObjectStore

MAX_PROGRAMS = 200
REPAIR_ACTION = "governance.chembl.regional_inference_repaired"


class ChemblProjectionMaintenance:
    def __init__(self, session: Session, object_store: ObjectStore, tenant_id: str, source_id: str) -> None:
        self.session, self.object_store, self.tenant_id, self.source_id = session, object_store, tenant_id, source_id

    def _clean_transaction(self) -> None:
        if self.session.new or self.session.dirty or self.session.deleted:
            raise ValueError("Use a clean maintenance transaction; unrelated writes were preserved")

    def preview(self, *, lock_rows: bool = False) -> RegionalRepairPlan:
        self._clean_transaction()
        statement = select(DataSource).where(DataSource.tenant_id == self.tenant_id, DataSource.id == self.source_id)
        if lock_rows:
            statement = statement.with_for_update()
        source = self.session.scalar(statement.execution_options(populate_existing=True))
        if (
            source is None
            or source.source_type != DataSourceType.CHEMBL
            or "public:chembl" not in source.authorization_scopes
        ):
            raise ValueError("An authorized tenant-scoped ChEMBL source is required")
        identifiers = list(
            self.session.scalars(
                select(FactProvenanceLink.resource_id)
                .join(SourceAsset, SourceAsset.id == FactProvenanceLink.source_asset_id)
                .where(
                    FactProvenanceLink.tenant_id == self.tenant_id,
                    SourceAsset.tenant_id == self.tenant_id,
                    SourceAsset.data_source_id == source.id,
                    FactProvenanceLink.resource_type == "development_program",
                )
                .distinct()
                .limit(MAX_PROGRAMS + 1)
            )
        )
        if len(identifiers) > MAX_PROGRAMS:
            raise ValueError("Source exceeds the bounded maintenance scope; no repair was executed")
        programs = (
            select(DevelopmentProgram)
            .where(
                DevelopmentProgram.tenant_id == self.tenant_id,
                DevelopmentProgram.id.in_(identifiers),
                DevelopmentProgram.global_phase.is_not(None),
            )
            .order_by(DevelopmentProgram.id)
            .execution_options(populate_existing=True)
        )
        if lock_rows:
            programs = programs.with_for_update()
        plan = RegionalRepairPlan(
            tenant_id=self.tenant_id,
            data_source_id=source.id,
            source_scope_digest=source.scope_digest,
            source_config_version=source.config_version,
            changes=[],
            blocked={},
        )
        for program in self.session.scalars(programs):
            change, reason = prove_legacy_regional_projection(
                self.session, self.object_store, self.tenant_id, source, program, lock_facts=lock_rows
            )
            if change is not None:
                plan.changes.append(change)
            else:
                plan.blocked[program.id] = reason or "unproven_projection"
        encoded = json.dumps(
            plan.model_dump(mode="json", exclude={"plan_sha256"}), sort_keys=True, separators=(",", ":")
        )
        return plan.model_copy(update={"plan_sha256": hashlib.sha256(encoded.encode()).hexdigest()})

    def apply(self, expected_sha256: str) -> RegionalRepairResult:
        self._clean_transaction()
        previous = self.session.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.tenant_id == self.tenant_id,
                AuditEvent.action == REPAIR_ACTION,
                AuditEvent.resource_id == self.source_id,
                AuditEvent.details["plan_sha256"].as_string() == expected_sha256,
            )
            .limit(1)
        )
        if previous is not None:
            return RegionalRepairResult.model_validate(previous.details["result"]).model_copy(update={"replayed": True})
        if self.session.get_bind().dialect.name == "postgresql":
            self.session.execute(text("SET LOCAL lock_timeout = '5s'"))
        plan = self.preview(lock_rows=True)
        if expected_sha256 != plan.plan_sha256:
            self.session.rollback()
            raise ValueError("Maintenance evidence or source changed; regenerate the preview")
        request_id = str(uuid.uuid4())
        for change in plan.changes:
            program = self.session.get(DevelopmentProgram, change.program_id)
            if (
                program is None
                or program.tenant_id != self.tenant_id
                or program.global_phase != change.old_global_phase
            ):
                self.session.rollback()
                raise ValueError("Regional projection changed; no partial repair was committed")
            program.global_phase = None
            self.session.add(
                OutboxEvent(
                    tenant_id=self.tenant_id,
                    aggregate_type="entity",
                    aggregate_id=change.drug_entity_id,
                    event_type="canonical.entity.upserted",
                    payload={"entity_id": change.drug_entity_id, "schema_version": 1},
                )
            )
        result = RegionalRepairResult(
            status="applied" if plan.changes else "no_changes",
            data_source_id=self.source_id,
            plan_sha256=plan.plan_sha256,
            changes_applied=len(plan.changes),
            program_ids=[change.program_id for change in plan.changes],
            blocked=plan.blocked,
            request_id=request_id,
        )
        if plan.changes:
            self.session.add(
                AuditEvent(
                    tenant_id=self.tenant_id,
                    actor_type="system",
                    actor_id="governance-maintenance",
                    action=REPAIR_ACTION,
                    resource_type="data_source",
                    resource_id=self.source_id,
                    outcome="success",
                    request_id=request_id,
                    details={
                        "plan_sha256": plan.plan_sha256,
                        "plan": plan.model_dump(mode="json"),
                        "result": result.model_dump(mode="json"),
                    },
                )
            )
            try:
                self.session.commit()
            except SQLAlchemyError:
                self.session.rollback()
                raise
        else:
            self.session.rollback()
        return result
