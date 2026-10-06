from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.governance.chembl import ChemblSnapshot
from pharma_intel.governance.chembl_projection_repair import legacy_chembl_regional_history
from pharma_intel.governance.projection_repair_models import RegionalRepairChange, RegionalRepairEvidence
from pharma_intel.models import (
    DataSource,
    DevelopmentProgram,
    GovernanceStatus,
    QuarantineStatus,
    ReviewTask,
    SourceAsset,
)
from pharma_intel.object_store import ObjectStore, ObjectStoreError

MAX_HISTORY = 200
LEGACY_MODELS = frozenset({"chembl_mechanism_json:1.0.0", "chembl_mechanism_json:1.1.0"})


def prove_legacy_regional_projection(
    session: Session,
    object_store: ObjectStore,
    tenant_id: str,
    source: DataSource,
    program: DevelopmentProgram,
    *,
    lock_facts: bool,
) -> tuple[RegionalRepairChange | None, str | None]:
    history = legacy_chembl_regional_history(session, tenant_id, program, limit=MAX_HISTORY + 1, lock_facts=lock_facts)
    if history is None or len(history) > MAX_HISTORY:
        return None, "regional_projection_history_not_proven"
    if not any(fact.payload.get("global_phase") == program.global_phase for fact, _, _ in history):
        return None, "no_recorded_copy_evidence"
    asset_ids = {version.source_asset_id for _, _, version in history}
    assets = list(
        session.scalars(
            select(SourceAsset).where(
                SourceAsset.tenant_id == tenant_id,
                SourceAsset.data_source_id == source.id,
                SourceAsset.id.in_(asset_ids),
            )
        )
    )
    if {asset.id for asset in assets} != asset_ids:
        return None, "mixed_or_missing_source_scope"
    statement = (
        select(ReviewTask)
        .where(ReviewTask.tenant_id == tenant_id, ReviewTask.staged_fact_id.in_([fact.id for fact, _, _ in history]))
        .execution_options(populate_existing=True)
    )
    if lock_facts:
        statement = statement.with_for_update()
    if any(
        review.decided_at is not None
        or review.decided_by_user_id is not None
        or review.status != GovernanceStatus.REVIEW_PENDING
        for review in session.scalars(statement)
    ):
        return None, "human_decision_preserved"
    target_ids = {value for rule in source.routing_rules if isinstance(value := rule.get("target_chembl_id"), str)}
    evidence: list[RegionalRepairEvidence] = []
    for fact, run, version in history:
        if (
            run.model_name not in LEGACY_MODELS
            or fact.status != GovernanceStatus.PUBLISHED
            or fact.published_resource_type != "evidence_claim"
            or fact.published_resource_id is None
            or fact.payload.get("global_phase_started_at") is not None
            or not version.raw_object_uri
            or version.quarantine_status not in {QuarantineStatus.NOT_APPLICABLE, QuarantineStatus.CLEARED}
        ):
            return None, "legacy_adapter_or_regional_evidence_not_proven"
        try:
            raw = object_store.read_bytes(version.raw_object_uri, max_bytes=min(source.max_file_bytes, 8_000_000))
            if hashlib.sha256(raw).hexdigest() != version.content_sha256:
                return None, "source_snapshot_checksum_mismatch"
            snapshot = ChemblSnapshot.model_validate_json(raw)
        except (ObjectStoreError, ValueError):
            return None, "source_snapshot_not_verifiable"
        if (
            snapshot.target.chembl_id not in target_ids
            or fact.source_locator != f"mechanism:{snapshot.mechanism.mec_id}"
        ):
            return None, "snapshot_identity_outside_source_scope"
        evidence.append(
            RegionalRepairEvidence(
                staged_fact_id=fact.id, source_version_id=version.id, source_sha256=version.content_sha256
            )
        )
    if program.global_phase is None:
        return None, "projection_already_corrected"
    return RegionalRepairChange(
        program_id=program.id,
        drug_entity_id=program.drug_entity_id,
        old_global_phase=program.global_phase,
        evidence=evidence,
    ), None
