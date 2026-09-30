from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.service import GovernanceError, GovernanceService
from pharma_intel.models import (
    ActivityMeasurement,
    Assay,
    AuditEvent,
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    ClinicalTrialResultDisclosure,
    CompoundStructure,
    DealAssetAssociation,
    DealPartyAssociation,
    DealProfile,
    DealRight,
    DevelopmentProgram,
    EpidemiologyObservation,
    EvidenceClaim,
    FactProvenanceLink,
    FactWithdrawalTombstone,
    GovernancePublicationBatch,
    GovernancePublicationBatchItem,
    GovernanceStatus,
    KnowledgeCitation,
    NewsEvent,
    OutboxEvent,
    PatentFamily,
    PatientPopulation,
    PatientPopulationEntityLink,
    RegulatoryEvent,
    ReviewTask,
    StagedFact,
    TargetEvidenceObservation,
    TargetProfile,
)
from pharma_intel.object_store import ObjectStore

MAX_BATCH_FACTS = 100
RESOURCE_MODELS = {
    "evidence_claim": EvidenceClaim,
    "target_profile": TargetProfile,
    "target_evidence": TargetEvidenceObservation,
    "compound_structure": CompoundStructure,
    "assay": Assay,
    "activity_measurement": ActivityMeasurement,
    "development_program": DevelopmentProgram,
    "clinical_trial": ClinicalTrialProfile,
    "patent_family": PatentFamily,
    "deal": DealProfile,
    "regulatory_event": RegulatoryEvent,
    "epidemiology_observation": EpidemiologyObservation,
    "patient_population": PatientPopulation,
    "news_event": NewsEvent,
}
DELETE_PRIORITY = {
    "activity_measurement": 10,
    "epidemiology_observation": 10,
    "clinical_trial": 20,
    "deal": 20,
    "assay": 30,
    "patient_population": 30,
    "evidence_claim": 100,
}


class PublicationError(RuntimeError):
    pass


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    return value


def _record_snapshot(record: Any, resource_type: str) -> dict[str, Any]:
    state = sa_inspect(record)
    return {
        "resource_type": resource_type,
        "resource_id": record.id,
        "table": state.mapper.local_table.name,
        "record": {
            attribute.key: _json_value(getattr(record, attribute.key)) for attribute in state.mapper.column_attrs
        },
    }


class GovernancePublicationService:
    def __init__(self, session: Session, settings: Settings, object_store: ObjectStore, tenant_id: str):
        self.session = session
        self.settings = settings
        self.object_store = object_store
        self.tenant_id = tenant_id

    def preview(
        self,
        *,
        operation: str,
        staged_fact_ids: list[str],
        idempotency_key: str,
        user_id: str,
        reason: str | None,
    ) -> GovernancePublicationBatch:
        normalized_ids = sorted(set(staged_fact_ids))
        normalized_reason = (reason or "").strip() or None
        if operation not in {"publish", "withdraw"}:
            raise PublicationError("Publication operation must be publish or withdraw")
        if not normalized_ids or len(normalized_ids) > MAX_BATCH_FACTS:
            raise PublicationError(f"A publication batch must contain between 1 and {MAX_BATCH_FACTS} facts")
        if len(normalized_ids) != len(staged_fact_ids):
            raise PublicationError("A publication batch cannot contain duplicate fact IDs")
        if operation == "withdraw" and normalized_reason is None:
            raise PublicationError("Withdrawal preview requires a specific reason")

        existing = self.session.scalar(
            select(GovernancePublicationBatch).where(
                GovernancePublicationBatch.tenant_id == self.tenant_id,
                GovernancePublicationBatch.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            requested = existing.result.get("requested_fact_ids")
            if existing.operation != operation or requested != normalized_ids or existing.reason != normalized_reason:
                raise PublicationError("Idempotency key was already used for a different publication preview")
            return existing

        facts = list(
            self.session.scalars(
                select(StagedFact)
                .where(StagedFact.tenant_id == self.tenant_id, StagedFact.id.in_(normalized_ids))
                .order_by(StagedFact.id)
            )
        )
        if len(facts) != len(normalized_ids):
            raise LookupError("One or more staged facts were not found")

        item_documents: list[dict[str, Any]] = []
        batch_fact_ids = {fact.id for fact in facts}
        batch_resource_keys = {
            (link.resource_type, link.resource_id)
            for link in self.session.scalars(
                select(FactProvenanceLink).where(
                    FactProvenanceLink.tenant_id == self.tenant_id,
                    FactProvenanceLink.staged_fact_id.in_(batch_fact_ids),
                )
            )
        }
        for fact in facts:
            blockers = (
                self._publish_blockers(fact, normalized_reason)
                if operation == "publish"
                else self._withdraw_blockers(fact, batch_fact_ids, batch_resource_keys)
            )
            item_documents.append(
                {
                    "staged_fact_id": fact.id,
                    "fact_kind": fact.fact_kind,
                    "expected_status": fact.status.value,
                    "source_document_id": fact.source_document_id,
                    "published_resource_type": fact.published_resource_type,
                    "published_resource_id": fact.published_resource_id,
                    "blockers": blockers,
                }
            )
        preview_document = {
            "operation": operation,
            "reason": normalized_reason,
            "items": item_documents,
        }
        preview_sha256 = hashlib.sha256(
            json.dumps(preview_document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()
        blocked_count = sum(bool(item["blockers"]) for item in item_documents)
        batch = GovernancePublicationBatch(
            tenant_id=self.tenant_id,
            idempotency_key=idempotency_key,
            operation=operation,
            status="previewed",
            preview_sha256=preview_sha256,
            expected_count=len(facts),
            blocked_count=blocked_count,
            reason=normalized_reason,
            requested_by_user_id=user_id,
            result={"requested_fact_ids": normalized_ids},
        )
        self.session.add(batch)
        self.session.flush()
        for position, item in enumerate(item_documents):
            self.session.add(
                GovernancePublicationBatchItem(
                    tenant_id=self.tenant_id,
                    publication_batch_id=batch.id,
                    staged_fact_id=item["staged_fact_id"],
                    position=position,
                    expected_status=item["expected_status"],
                    outcome="blocked" if item["blockers"] else "ready",
                    blockers=item["blockers"],
                    snapshot=item,
                )
            )
        self.session.add(
            AuditEvent(
                tenant_id=self.tenant_id,
                actor_type="user",
                actor_id=user_id,
                action="governance.publication.previewed",
                resource_type="governance_publication_batch",
                resource_id=batch.id,
                outcome="blocked" if blocked_count else "success",
                request_id=batch.id,
                details={
                    "operation": operation,
                    "expected_count": len(facts),
                    "blocked_count": blocked_count,
                    "preview_sha256": preview_sha256,
                },
            )
        )
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            concurrent = self.session.scalar(
                select(GovernancePublicationBatch).where(
                    GovernancePublicationBatch.tenant_id == self.tenant_id,
                    GovernancePublicationBatch.idempotency_key == idempotency_key,
                )
            )
            if concurrent is not None:
                requested = concurrent.result.get("requested_fact_ids")
                if (
                    concurrent.operation == operation
                    and requested == normalized_ids
                    and concurrent.reason == normalized_reason
                ):
                    return concurrent
                raise PublicationError(
                    "Idempotency key was concurrently used for a different publication preview"
                ) from exc
            raise PublicationError("Publication preview could not be persisted") from exc
        return batch

    def commit(self, batch_id: str, preview_sha256: str, user_id: str) -> GovernancePublicationBatch:
        try:
            batch = self.session.scalar(
                select(GovernancePublicationBatch)
                .where(
                    GovernancePublicationBatch.tenant_id == self.tenant_id,
                    GovernancePublicationBatch.id == batch_id,
                )
                .with_for_update()
            )
            if batch is None:
                raise LookupError("Publication batch not found")
            if batch.status == "committed":
                if batch.preview_sha256 != preview_sha256:
                    raise PublicationError("Committed publication preview hash does not match")
                return batch
            if batch.status != "previewed":
                raise PublicationError("Publication batch is not commit-ready")
            if batch.preview_sha256 != preview_sha256:
                raise PublicationError("Publication preview hash does not match")
            if batch.blocked_count:
                raise PublicationError("Publication batch contains blocking findings")

            items = list(
                self.session.scalars(
                    select(GovernancePublicationBatchItem)
                    .where(
                        GovernancePublicationBatchItem.tenant_id == self.tenant_id,
                        GovernancePublicationBatchItem.publication_batch_id == batch.id,
                    )
                    .order_by(GovernancePublicationBatchItem.position)
                    .with_for_update()
                )
            )
            facts = {
                fact.id: fact
                for fact in self.session.scalars(
                    select(StagedFact)
                    .where(
                        StagedFact.tenant_id == self.tenant_id,
                        StagedFact.id.in_([item.staged_fact_id for item in items]),
                    )
                    .with_for_update()
                )
            }
            if len(items) != batch.expected_count or len(facts) != batch.expected_count:
                raise PublicationError("Publication batch membership changed after preview")
            for item in items:
                fact = facts[item.staged_fact_id]
                if fact.status.value != item.expected_status:
                    raise PublicationError("Publication fact status changed after preview; create a new preview")

            if batch.operation == "publish":
                self._commit_publish(batch, items, facts, user_id)
            else:
                self._commit_withdraw(batch, items, facts, user_id)
            batch.status = "committed"
            batch.committed_by_user_id = user_id
            batch.committed_at = datetime.now(UTC)
            batch.result = {
                **batch.result,
                "committed_count": len(items),
                "committed_at": batch.committed_at.isoformat(),
            }
            self.session.add(
                AuditEvent(
                    tenant_id=self.tenant_id,
                    actor_type="user",
                    actor_id=user_id,
                    action=f"governance.publication.{batch.operation}.committed",
                    resource_type="governance_publication_batch",
                    resource_id=batch.id,
                    outcome="success",
                    request_id=batch.id,
                    details={
                        "operation": batch.operation,
                        "committed_count": len(items),
                        "preview_sha256": batch.preview_sha256,
                    },
                )
            )
            self.session.commit()
            return batch
        except (LookupError, PublicationError):
            self.session.rollback()
            raise
        except Exception as exc:
            self.session.rollback()
            raise PublicationError("Publication batch commit failed atomically") from exc

    def get(self, batch_id: str) -> GovernancePublicationBatch:
        batch = self.session.scalar(
            select(GovernancePublicationBatch).where(
                GovernancePublicationBatch.tenant_id == self.tenant_id,
                GovernancePublicationBatch.id == batch_id,
            )
        )
        if batch is None:
            raise LookupError("Publication batch not found")
        return batch

    def items(self, batch_id: str) -> list[GovernancePublicationBatchItem]:
        self.get(batch_id)
        return list(
            self.session.scalars(
                select(GovernancePublicationBatchItem)
                .where(
                    GovernancePublicationBatchItem.tenant_id == self.tenant_id,
                    GovernancePublicationBatchItem.publication_batch_id == batch_id,
                )
                .order_by(GovernancePublicationBatchItem.position)
            )
        )

    def list_batches(self, limit: int = 100) -> list[GovernancePublicationBatch]:
        return list(
            self.session.scalars(
                select(GovernancePublicationBatch)
                .where(GovernancePublicationBatch.tenant_id == self.tenant_id)
                .order_by(GovernancePublicationBatch.created_at.desc(), GovernancePublicationBatch.id.desc())
                .limit(limit)
            )
        )

    def _publish_blockers(self, fact: StagedFact, reason: str | None) -> list[dict[str, Any]]:
        blockers: list[dict[str, Any]] = []
        if fact.status not in {GovernanceStatus.REVIEW_PENDING, GovernanceStatus.CONFLICT}:
            blockers.append({"code": "fact_not_reviewable", "status": fact.status.value})
        task = self.session.scalar(
            select(ReviewTask).where(
                ReviewTask.tenant_id == self.tenant_id,
                ReviewTask.staged_fact_id == fact.id,
                ReviewTask.status == GovernanceStatus.REVIEW_PENDING,
            )
        )
        if task is None:
            blockers.append({"code": "open_review_task_missing"})
        if fact.source_document_id is None:
            blockers.append({"code": "source_document_missing"})
        if fact.status == GovernanceStatus.CONFLICT and not (reason or "").strip():
            blockers.append({"code": "conflict_decision_reason_required"})
        return blockers

    def _withdraw_blockers(
        self,
        fact: StagedFact,
        withdrawing_fact_ids: set[str] | None = None,
        withdrawing_resource_keys: set[tuple[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        blockers: list[dict[str, Any]] = []
        if fact.status != GovernanceStatus.PUBLISHED:
            return [{"code": "fact_not_published", "status": fact.status.value}]
        links = list(
            self.session.scalars(
                select(FactProvenanceLink).where(
                    FactProvenanceLink.tenant_id == self.tenant_id,
                    FactProvenanceLink.staged_fact_id == fact.id,
                )
            )
        )
        if not links:
            return [{"code": "published_fact_provenance_missing"}]
        excluded_fact_ids = (withdrawing_fact_ids or set()) | {fact.id}
        for link in links:
            if link.resource_type not in RESOURCE_MODELS:
                blockers.append({"code": "unsupported_projection_type", "resource_type": link.resource_type})
                continue
            shared = int(
                self.session.scalar(
                    select(func.count(func.distinct(FactProvenanceLink.staged_fact_id)))
                    .join(StagedFact, StagedFact.id == FactProvenanceLink.staged_fact_id)
                    .where(
                        FactProvenanceLink.tenant_id == self.tenant_id,
                        FactProvenanceLink.resource_type == link.resource_type,
                        FactProvenanceLink.resource_id == link.resource_id,
                        FactProvenanceLink.staged_fact_id.not_in(excluded_fact_ids),
                        StagedFact.status == GovernanceStatus.PUBLISHED,
                    )
                )
                or 0
            )
            if shared:
                blockers.append(
                    {
                        "code": "shared_published_projection",
                        "resource_type": link.resource_type,
                        "resource_id": link.resource_id,
                        "other_published_fact_count": shared,
                    }
                )
            blockers.extend(self._downstream_dependency_blockers(link, withdrawing_resource_keys or set()))
        return blockers

    def _downstream_dependency_blockers(
        self,
        link: FactProvenanceLink,
        withdrawing_resource_keys: set[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        dependencies: list[tuple[Any, Any, str | None]] = []
        if link.resource_type == "evidence_claim":
            dependencies.append((KnowledgeCitation, KnowledgeCitation.evidence_claim_id, None))
        elif link.resource_type == "assay":
            dependencies.append((ActivityMeasurement, ActivityMeasurement.assay_id, "activity_measurement"))
        elif link.resource_type == "patient_population":
            dependencies.append(
                (EpidemiologyObservation, EpidemiologyObservation.patient_population_id, "epidemiology_observation")
            )

        blockers: list[dict[str, Any]] = []
        for model, foreign_key, dependent_resource_type in dependencies:
            rows = list(
                self.session.scalars(
                    select(model).where(
                        model.tenant_id == self.tenant_id,
                        foreign_key == link.resource_id,
                    )
                )
            )
            remaining = [
                row
                for row in rows
                if dependent_resource_type is None or (dependent_resource_type, row.id) not in withdrawing_resource_keys
            ]
            if remaining:
                blockers.append(
                    {
                        "code": "downstream_reference",
                        "resource_type": link.resource_type,
                        "resource_id": link.resource_id,
                        "reference_type": model.__tablename__,
                        "reference_count": len(remaining),
                    }
                )
        return blockers

    def _commit_publish(
        self,
        batch: GovernancePublicationBatch,
        items: list[GovernancePublicationBatchItem],
        facts: dict[str, StagedFact],
        user_id: str,
    ) -> None:
        governance = GovernanceService(self.session, self.settings, self.object_store, self.tenant_id)
        now = datetime.now(UTC)
        for item in items:
            fact = facts[item.staged_fact_id]
            blockers = self._publish_blockers(fact, batch.reason)
            if blockers:
                raise PublicationError("Publication fact is no longer reviewable")
            task = self.session.scalar(
                select(ReviewTask)
                .where(
                    ReviewTask.tenant_id == self.tenant_id,
                    ReviewTask.staged_fact_id == fact.id,
                    ReviewTask.status == GovernanceStatus.REVIEW_PENDING,
                )
                .with_for_update()
            )
            if task is None:
                raise PublicationError("Open review task disappeared after preview")
            try:
                governance._publish(fact)  # noqa: SLF001 - batch transaction reuses the governed publication primitive
            except GovernanceError as exc:
                raise PublicationError(str(exc)) from exc
            task.status = GovernanceStatus.APPROVED
            task.decided_by_user_id = user_id
            task.decision_notes = batch.reason
            task.decided_at = now
            item.outcome = "published"
            item.snapshot = {
                **item.snapshot,
                "published_resource_type": fact.published_resource_type,
                "published_resource_id": fact.published_resource_id,
            }

    def _commit_withdraw(
        self,
        batch: GovernancePublicationBatch,
        items: list[GovernancePublicationBatchItem],
        facts: dict[str, StagedFact],
        user_id: str,
    ) -> None:
        reason = (batch.reason or "").strip()
        if not reason:
            raise PublicationError("Withdrawal reason is required")
        withdrawing_fact_ids = set(facts)
        withdrawing_resource_keys = {
            (link.resource_type, link.resource_id)
            for link in self.session.scalars(
                select(FactProvenanceLink).where(
                    FactProvenanceLink.tenant_id == self.tenant_id,
                    FactProvenanceLink.staged_fact_id.in_(withdrawing_fact_ids),
                )
            )
        }
        for item in items:
            if self._withdraw_blockers(
                facts[item.staged_fact_id],
                withdrawing_fact_ids,
                withdrawing_resource_keys,
            ):
                raise PublicationError("Publication withdrawal dependencies changed after preview")

        snapshots_by_fact: dict[str, list[dict[str, Any]]] = {}
        resources: dict[tuple[str, str], Any] = {}
        for item in items:
            fact = facts[item.staged_fact_id]
            links = list(
                self.session.scalars(
                    select(FactProvenanceLink).where(
                        FactProvenanceLink.tenant_id == self.tenant_id,
                        FactProvenanceLink.staged_fact_id == fact.id,
                    )
                )
            )
            snapshots: list[dict[str, Any]] = []
            for link in links:
                model = RESOURCE_MODELS[link.resource_type]
                record: Any = self.session.get(model, link.resource_id)
                if record is None or record.tenant_id != self.tenant_id:
                    raise PublicationError("Published resource disappeared after preview")
                snapshots.append(_record_snapshot(record, link.resource_type))
                resources[(link.resource_type, link.resource_id)] = record
            snapshots_by_fact[fact.id] = snapshots

        self.session.execute(
            delete(FactProvenanceLink).where(
                FactProvenanceLink.tenant_id == self.tenant_id,
                FactProvenanceLink.staged_fact_id.in_(withdrawing_fact_ids),
            )
        )
        for (resource_type, _resource_id), record in sorted(
            resources.items(),
            key=lambda pair: DELETE_PRIORITY.get(pair[0][0], 50),
        ):
            self._delete_owned_children(resource_type, record.id)
            self.session.delete(record)
        self.session.flush()

        for item in items:
            fact = facts[item.staged_fact_id]
            snapshots = snapshots_by_fact[fact.id]
            self.session.add(
                FactWithdrawalTombstone(
                    tenant_id=self.tenant_id,
                    staged_fact_id=fact.id,
                    publication_batch_id=batch.id,
                    withdrawn_by_user_id=user_id,
                    reason=reason,
                    resource_snapshot=snapshots,
                )
            )
            fact.status = GovernanceStatus.WITHDRAWN
            item.outcome = "withdrawn"
            item.snapshot = {**item.snapshot, "withdrawn_resources": snapshots}
            self.session.add(
                OutboxEvent(
                    tenant_id=self.tenant_id,
                    aggregate_type="staged_fact",
                    aggregate_id=fact.id,
                    event_type="governance.fact.withdrawn",
                    payload={
                        "staged_fact_id": fact.id,
                        "evidence_claim_id": fact.published_resource_id,
                        "resources": [
                            {"resource_type": snapshot["resource_type"], "resource_id": snapshot["resource_id"]}
                            for snapshot in snapshots
                        ],
                    },
                )
            )

    def _delete_owned_children(self, resource_type: str, resource_id: str) -> None:
        if resource_type == "clinical_trial":
            self.session.execute(
                delete(ClinicalTrialResultDisclosure).where(
                    ClinicalTrialResultDisclosure.tenant_id == self.tenant_id,
                    ClinicalTrialResultDisclosure.trial_id == resource_id,
                )
            )
            self.session.execute(
                delete(ClinicalTrialEntityRole).where(
                    ClinicalTrialEntityRole.tenant_id == self.tenant_id,
                    ClinicalTrialEntityRole.trial_id == resource_id,
                )
            )
        elif resource_type == "deal":
            for model in (DealRight, DealAssetAssociation, DealPartyAssociation):
                self.session.execute(
                    delete(model).where(model.tenant_id == self.tenant_id, model.deal_id == resource_id)
                )
        elif resource_type == "patient_population":
            self.session.execute(
                delete(PatientPopulationEntityLink).where(
                    PatientPopulationEntityLink.tenant_id == self.tenant_id,
                    PatientPopulationEntityLink.patient_population_id == resource_id,
                )
            )
