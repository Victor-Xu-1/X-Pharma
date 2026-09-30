from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import InstrumentedAttribute

from pharma_intel.models import (
    AuditEvent,
    Base,
    DataExportJob,
    DataLifecycleEvent,
    DataRetentionPolicy,
    DataSource,
    DataSourceState,
    EvidenceClaim,
    ExtractionRun,
    GovernanceStatus,
    KnowledgeCitation,
    LegalHold,
    OutboxEvent,
    RetrievalProjection,
    ReviewTask,
    SourceAsset,
    SourceAssetState,
    SourceDocument,
    SourceVersion,
    StagedFact,
    StageStatus,
    Tenant,
)
from pharma_intel.object_store import ObjectStore
from pharma_intel.security import Principal

EXPORT_DATA_CLASS = "commercial_export_artifact"
SOURCE_DATA_CLASS = "source_asset_snapshot"


class LifecycleError(ValueError):
    pass


class LifecycleConflict(LifecycleError):
    pass


@dataclass(frozen=True)
class LifecycleOutcome:
    event: DataLifecycleEvent
    replayed: bool


@dataclass(frozen=True)
class SourceAssetImpact:
    asset: SourceAsset
    retention_eligible: bool
    version_count: int
    raw_object_count: int
    extracted_object_count: int
    extraction_run_count: int
    staged_fact_count: int
    published_fact_count: int
    evidence_claim_count: int
    knowledge_citation_count: int
    retrieval_projection_count: int
    shared_document_count: int
    other_document_reference_count: int
    blockers: list[str]

    def details(self) -> dict[str, object]:
        return {
            "retention_eligible": self.retention_eligible,
            "version_count": self.version_count,
            "raw_object_count": self.raw_object_count,
            "extracted_object_count": self.extracted_object_count,
            "extraction_run_count": self.extraction_run_count,
            "staged_fact_count": self.staged_fact_count,
            "published_fact_count": self.published_fact_count,
            "evidence_claim_count": self.evidence_claim_count,
            "knowledge_citation_count": self.knowledge_citation_count,
            "retrieval_projection_count": self.retrieval_projection_count,
            "shared_document_count": self.shared_document_count,
            "other_document_reference_count": self.other_document_reference_count,
            "blockers": self.blockers,
        }


class DataLifecycleService:
    def __init__(self, session: Session, object_store: ObjectStore) -> None:
        self.session = session
        self.object_store = object_store

    def list_policies(self, principal: Principal) -> list[DataRetentionPolicy]:
        principal.require("commercial:read")
        return list(
            self.session.scalars(
                select(DataRetentionPolicy)
                .where(DataRetentionPolicy.tenant_id == principal.tenant_id)
                .order_by(DataRetentionPolicy.data_class)
            )
        )

    def upsert_export_policy(
        self,
        principal: Principal,
        *,
        retention_seconds: int,
        legal_basis: str,
        geographic_scope: list[str],
        active: bool,
        request_id: str,
    ) -> DataRetentionPolicy:
        return self._upsert_policy(
            principal,
            data_class=EXPORT_DATA_CLASS,
            retention_seconds=retention_seconds,
            legal_basis=legal_basis,
            geographic_scope=geographic_scope,
            active=active,
            request_id=request_id,
        )

    def upsert_source_policy(
        self,
        principal: Principal,
        *,
        retention_seconds: int,
        legal_basis: str,
        geographic_scope: list[str],
        active: bool,
        request_id: str,
    ) -> DataRetentionPolicy:
        return self._upsert_policy(
            principal,
            data_class=SOURCE_DATA_CLASS,
            retention_seconds=retention_seconds,
            legal_basis=legal_basis,
            geographic_scope=geographic_scope,
            active=active,
            request_id=request_id,
        )

    def _upsert_policy(
        self,
        principal: Principal,
        *,
        data_class: str,
        retention_seconds: int,
        legal_basis: str,
        geographic_scope: list[str],
        active: bool,
        request_id: str,
    ) -> DataRetentionPolicy:
        principal.require("commercial:write")
        if retention_seconds < 300:
            raise LifecycleError("Retention must be at least 300 seconds")
        self._lock_tenant(principal.tenant_id)
        timestamp = datetime.now(UTC)
        policy = self.session.scalar(
            select(DataRetentionPolicy)
            .where(
                DataRetentionPolicy.tenant_id == principal.tenant_id,
                DataRetentionPolicy.data_class == data_class,
            )
            .with_for_update()
        )
        if policy is None:
            policy = DataRetentionPolicy(
                tenant_id=principal.tenant_id,
                data_class=data_class,
                policy_version=1,
                retention_seconds=retention_seconds,
                legal_basis=legal_basis,
                geographic_scope=geographic_scope,
                active=active,
                configured_by_user_id=principal.actor_id,
                created_at=timestamp,
                updated_at=timestamp,
            )
            self.session.add(policy)
        else:
            policy.policy_version += 1
            policy.retention_seconds = retention_seconds
            policy.legal_basis = legal_basis
            policy.geographic_scope = geographic_scope
            policy.active = active
            policy.configured_by_user_id = principal.actor_id
            policy.updated_at = timestamp
        self._audit(principal, "data.retention_policy.upsert", policy.id, "success", request_id)
        self.session.commit()
        return policy

    def list_holds(self, principal: Principal, *, active_only: bool = False) -> list[LegalHold]:
        principal.require("commercial:read")
        statement = select(LegalHold).where(LegalHold.tenant_id == principal.tenant_id)
        if active_only:
            statement = statement.where(LegalHold.status == "active")
        return list(self.session.scalars(statement.order_by(LegalHold.placed_at.desc())))

    def list_events(self, principal: Principal, *, limit: int = 100) -> list[DataLifecycleEvent]:
        principal.require("commercial:read")
        return list(
            self.session.scalars(
                select(DataLifecycleEvent)
                .where(DataLifecycleEvent.tenant_id == principal.tenant_id)
                .order_by(DataLifecycleEvent.created_at.desc())
                .limit(limit)
            )
        )

    def place_hold(
        self,
        principal: Principal,
        *,
        scope_type: str,
        scope_id: str | None,
        matter_reference: str,
        reason: str,
        request_id: str,
    ) -> LegalHold:
        principal.require("commercial:write")
        self._lock_tenant(principal.tenant_id)
        self._validate_scope(principal.tenant_id, scope_type, scope_id)
        duplicate = self.session.scalar(
            select(LegalHold).where(
                LegalHold.tenant_id == principal.tenant_id,
                LegalHold.status == "active",
                LegalHold.scope_type == scope_type,
                LegalHold.scope_id.is_(None) if scope_id is None else LegalHold.scope_id == scope_id,
                LegalHold.matter_reference == matter_reference,
            )
        )
        if duplicate is not None:
            raise LifecycleConflict("An active legal hold already exists for this matter and scope")
        hold = LegalHold(
            tenant_id=principal.tenant_id,
            scope_type=scope_type,
            scope_id=scope_id,
            matter_reference=matter_reference,
            reason=reason,
            placed_by_user_id=principal.actor_id,
        )
        self.session.add(hold)
        self._audit(principal, "data.legal_hold.place", hold.id, "success", request_id)
        self.session.commit()
        return hold

    def release_hold(
        self,
        principal: Principal,
        hold_id: str,
        *,
        reason: str,
        request_id: str,
    ) -> LegalHold:
        principal.require("commercial:write")
        self._lock_tenant(principal.tenant_id)
        hold = self.session.scalar(
            select(LegalHold)
            .where(LegalHold.tenant_id == principal.tenant_id, LegalHold.id == hold_id)
            .with_for_update()
        )
        if hold is None:
            raise LifecycleError("Legal hold not found")
        if hold.status == "released":
            return hold
        hold.status = "released"
        hold.released_by_user_id = principal.actor_id
        hold.released_at = datetime.now(UTC)
        hold.release_reason = reason
        self._audit(principal, "data.legal_hold.release", hold.id, "success", request_id)
        self.session.commit()
        return hold

    def export_candidates(self, principal: Principal, *, limit: int = 100) -> list[DataExportJob]:
        principal.require("commercial:read")
        policy = self._active_export_policy(principal.tenant_id)
        cutoff = datetime.now(UTC) - timedelta(seconds=policy.retention_seconds)
        return list(
            self.session.scalars(
                select(DataExportJob)
                .where(
                    DataExportJob.tenant_id == principal.tenant_id,
                    DataExportJob.state.in_(("completed", "expired")),
                    DataExportJob.expires_at.is_not(None),
                    DataExportJob.expires_at <= datetime.now(UTC),
                    DataExportJob.completed_at.is_not(None),
                    DataExportJob.completed_at <= cutoff,
                    or_(DataExportJob.artifact_uri.is_not(None), DataExportJob.manifest_uri.is_not(None)),
                )
                .order_by(DataExportJob.expires_at)
                .limit(limit)
            )
        )

    def source_candidates(self, principal: Principal, *, limit: int = 100) -> list[SourceAssetImpact]:
        principal.require("commercial:read")
        policy = self._active_policy(principal.tenant_id, SOURCE_DATA_CLASS)
        cutoff = datetime.now(UTC) - timedelta(seconds=policy.retention_seconds)
        assets = self.session.scalars(
            select(SourceAsset)
            .where(
                SourceAsset.tenant_id == principal.tenant_id,
                SourceAsset.state == SourceAssetState.MISSING,
                SourceAsset.missing_since.is_not(None),
                SourceAsset.missing_since <= cutoff,
            )
            .order_by(SourceAsset.missing_since, SourceAsset.id)
            .limit(limit)
        )
        return [self._source_asset_impact(asset, policy) for asset in assets]

    def deleted_source_assets(self, principal: Principal, *, limit: int = 100) -> list[SourceAsset]:
        principal.require("commercial:read")
        return list(
            self.session.scalars(
                select(SourceAsset)
                .where(
                    SourceAsset.tenant_id == principal.tenant_id,
                    SourceAsset.state == SourceAssetState.DELETED,
                )
                .order_by(SourceAsset.updated_at.desc(), SourceAsset.id)
                .limit(limit)
            )
        )

    def source_asset_impact(self, principal: Principal, asset_id: str) -> SourceAssetImpact:
        principal.require("commercial:read")
        asset = self.session.scalar(
            select(SourceAsset).where(
                SourceAsset.tenant_id == principal.tenant_id,
                SourceAsset.id == asset_id,
            )
        )
        if asset is None:
            raise LifecycleError("Source asset not found")
        return self._source_asset_impact(asset, self._active_policy(principal.tenant_id, SOURCE_DATA_CLASS))

    def purge_source_asset(
        self,
        principal: Principal,
        asset_id: str,
        *,
        idempotency_key: str,
        reason: str,
        request_id: str,
    ) -> LifecycleOutcome:
        principal.require("commercial:write")
        self._lock_tenant(principal.tenant_id)
        existing = self._idempotent_event(principal.tenant_id, idempotency_key, "source_asset", asset_id)
        if existing is not None:
            return LifecycleOutcome(existing, True)
        asset = self.session.scalar(
            select(SourceAsset)
            .where(SourceAsset.tenant_id == principal.tenant_id, SourceAsset.id == asset_id)
            .with_for_update()
        )
        if asset is None:
            raise LifecycleError("Source asset not found")
        if asset.state == SourceAssetState.DELETED:
            raise LifecycleConflict("Source asset has already been deleted")
        policy = self._active_policy(principal.tenant_id, SOURCE_DATA_CLASS)
        impact = self._source_asset_impact(asset, policy)
        if not impact.retention_eligible:
            raise LifecycleConflict("Source asset is not eligible for retention purge")

        holds = self._applicable_source_holds(asset)
        blockers = list(impact.blockers)
        if holds:
            blockers.append("legal_hold_active")
        if blockers:
            event = self._event(
                principal,
                data_class=SOURCE_DATA_CLASS,
                target_type="source_asset",
                target_id=asset.id,
                policy=policy,
                idempotency_key=idempotency_key,
                reason=reason,
                outcome="blocked",
                legal_hold_ids=[hold.id for hold in holds],
                details={**impact.details(), "blockers": list(dict.fromkeys(blockers))},
            )
            self._audit(principal, "data.source_asset.purge", asset.id, "blocked", request_id)
            self.session.commit()
            return LifecycleOutcome(event, False)

        versions = list(
            self.session.scalars(
                select(SourceVersion)
                .where(
                    SourceVersion.tenant_id == principal.tenant_id,
                    SourceVersion.source_asset_id == asset.id,
                )
                .with_for_update()
            )
        )
        version_ids = [version.id for version in versions]
        document_ids = {version.source_document_id for version in versions if version.source_document_id}
        deleted_objects: dict[str, str] = {}
        for version in versions:
            if version.raw_object_uri:
                deleted_objects[f"raw:{version.id}"] = self._delete_version_object_if_unreferenced(
                    version, version.raw_object_uri, version.content_sha256, SourceVersion.raw_object_uri
                )
            if version.extracted_text_object_uri and version.extracted_text_sha256:
                deleted_objects[f"text:{version.id}"] = self._delete_version_object_if_unreferenced(
                    version,
                    version.extracted_text_object_uri,
                    version.extracted_text_sha256,
                    SourceVersion.extracted_text_object_uri,
                )

        run_ids = (
            list(
                self.session.scalars(
                    select(ExtractionRun.id).where(
                        ExtractionRun.tenant_id == principal.tenant_id,
                        ExtractionRun.source_version_id.in_(version_ids),
                    )
                )
            )
            if version_ids
            else []
        )
        fact_ids = (
            list(
                self.session.scalars(
                    select(StagedFact.id).where(
                        StagedFact.tenant_id == principal.tenant_id,
                        StagedFact.extraction_run_id.in_(run_ids),
                    )
                )
            )
            if run_ids
            else []
        )
        if fact_ids:
            self.session.execute(delete(ReviewTask).where(ReviewTask.staged_fact_id.in_(fact_ids)))
            self.session.execute(delete(StagedFact).where(StagedFact.id.in_(fact_ids)))
        if run_ids:
            self.session.execute(delete(ExtractionRun).where(ExtractionRun.id.in_(run_ids)))

        withdrawn_at = datetime.now(UTC)
        for version in versions:
            version.raw_object_uri = None
            version.extracted_text_object_uri = None
            version.source_document_id = None
            version.retrieval_projection_id = None
            version.retrieval_status = StageStatus.SKIPPED
            metadata = dict(version.metadata_json)
            metadata["lifecycle"] = {"state": "withdrawn", "withdrawn_at": withdrawn_at.isoformat()}
            version.metadata_json = metadata
        self.session.flush()

        removable_documents = self._unshared_document_ids(principal.tenant_id, document_ids)
        if removable_documents:
            self.session.execute(
                delete(RetrievalProjection).where(
                    RetrievalProjection.tenant_id == principal.tenant_id,
                    RetrievalProjection.source_document_id.in_(removable_documents),
                )
            )
            self.session.execute(
                delete(SourceDocument).where(
                    SourceDocument.tenant_id == principal.tenant_id,
                    SourceDocument.id.in_(removable_documents),
                )
            )

        asset.state = SourceAssetState.DELETED
        asset.current_version_id = None
        asset.updated_at = withdrawn_at
        self.session.add(
            OutboxEvent(
                tenant_id=principal.tenant_id,
                aggregate_type="source_asset",
                aggregate_id=asset.id,
                event_type="source.asset.deleted",
                payload={"source_asset_id": asset.id, "data_source_id": asset.data_source_id},
            )
        )
        event = self._event(
            principal,
            data_class=SOURCE_DATA_CLASS,
            target_type="source_asset",
            target_id=asset.id,
            policy=policy,
            idempotency_key=idempotency_key,
            reason=reason,
            outcome="succeeded",
            legal_hold_ids=[],
            details={
                **impact.details(),
                "deleted_objects": deleted_objects,
                "deleted_source_documents": len(removable_documents),
            },
        )
        self._audit(principal, "data.source_asset.purge", asset.id, "success", request_id)
        self.session.commit()
        return LifecycleOutcome(event, False)

    def reauthorize_source_asset(
        self,
        principal: Principal,
        asset_id: str,
        *,
        idempotency_key: str,
        reason: str,
        request_id: str,
    ) -> LifecycleOutcome:
        principal.require("commercial:write")
        self._lock_tenant(principal.tenant_id)
        existing = self._idempotent_event(principal.tenant_id, idempotency_key, "source_asset", asset_id)
        if existing is not None:
            if existing.action != "reauthorize":
                raise LifecycleConflict("Idempotency key was used for another lifecycle action")
            return LifecycleOutcome(existing, True)
        asset = self.session.scalar(
            select(SourceAsset)
            .where(SourceAsset.tenant_id == principal.tenant_id, SourceAsset.id == asset_id)
            .with_for_update()
        )
        if asset is None:
            raise LifecycleError("Source asset not found")
        if asset.state != SourceAssetState.DELETED:
            raise LifecycleConflict("Only a deleted source asset can be reauthorized")
        source = self.session.scalar(
            select(DataSource)
            .where(
                DataSource.tenant_id == principal.tenant_id,
                DataSource.id == asset.data_source_id,
            )
            .with_for_update()
        )
        if source is None or source.state != DataSourceState.ACTIVE:
            raise LifecycleConflict("Source asset requires an active data source before reauthorization")
        policy = self._active_policy(principal.tenant_id, SOURCE_DATA_CLASS)
        holds = self._applicable_source_holds(asset)
        if holds:
            event = self._event(
                principal,
                data_class=SOURCE_DATA_CLASS,
                target_type="source_asset",
                target_id=asset.id,
                policy=policy,
                idempotency_key=idempotency_key,
                reason=reason,
                action="reauthorize",
                outcome="blocked",
                legal_hold_ids=[hold.id for hold in holds],
                details={"blockers": ["legal_hold_active"]},
            )
            self._audit(principal, "data.source_asset.reauthorize", asset.id, "blocked", request_id)
            self.session.commit()
            return LifecycleOutcome(event, False)

        reauthorized_at = datetime.now(UTC)
        asset.state = SourceAssetState.MISSING
        asset.current_version_id = None
        asset.source_fingerprint = None
        asset.missing_since = reauthorized_at
        asset.updated_at = reauthorized_at
        self.session.add(
            OutboxEvent(
                tenant_id=principal.tenant_id,
                aggregate_type="source_asset",
                aggregate_id=asset.id,
                event_type="source.asset.reauthorized",
                payload={"source_asset_id": asset.id, "data_source_id": asset.data_source_id},
            )
        )
        event = self._event(
            principal,
            data_class=SOURCE_DATA_CLASS,
            target_type="source_asset",
            target_id=asset.id,
            policy=policy,
            idempotency_key=idempotency_key,
            reason=reason,
            action="reauthorize",
            outcome="succeeded",
            legal_hold_ids=[],
            details={"next_state": SourceAssetState.MISSING.value, "requires_rescan": True},
        )
        self._audit(principal, "data.source_asset.reauthorize", asset.id, "success", request_id)
        self.session.commit()
        return LifecycleOutcome(event, False)

    def purge_export(
        self,
        principal: Principal,
        job_id: str,
        *,
        idempotency_key: str,
        reason: str,
        request_id: str,
    ) -> LifecycleOutcome:
        principal.require("commercial:write")
        self._lock_tenant(principal.tenant_id)
        existing = self.session.scalar(
            select(DataLifecycleEvent).where(
                DataLifecycleEvent.tenant_id == principal.tenant_id,
                DataLifecycleEvent.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.target_type != "data_export_job" or existing.target_id != job_id:
                raise LifecycleConflict("Idempotency key was used for another lifecycle target")
            return LifecycleOutcome(existing, True)

        job = self.session.scalar(
            select(DataExportJob)
            .where(DataExportJob.tenant_id == principal.tenant_id, DataExportJob.id == job_id)
            .with_for_update()
        )
        if job is None:
            raise LifecycleError("Export job not found")
        policy = self._active_export_policy(principal.tenant_id)
        now = datetime.now(UTC)
        retention_deadline = (
            _as_utc(job.completed_at) + timedelta(seconds=policy.retention_seconds) if job.completed_at else None
        )
        if (
            job.state not in {"completed", "expired"}
            or job.expires_at is None
            or _as_utc(job.expires_at) > now
            or retention_deadline is None
            or retention_deadline > now
        ):
            raise LifecycleConflict("Export artifact is not eligible for retention purge")
        holds = self._applicable_holds(job)
        if holds:
            event = self._event(
                principal,
                data_class=EXPORT_DATA_CLASS,
                target_type="data_export_job",
                target_id=job.id,
                policy=policy,
                idempotency_key=idempotency_key,
                reason=reason,
                outcome="blocked",
                legal_hold_ids=[hold.id for hold in holds],
                details={"reason": "legal_hold_active"},
            )
            self._audit(principal, "data.export_artifact.purge", job.id, "blocked", request_id)
            self.session.commit()
            return LifecycleOutcome(event, False)

        snapshot = {
            "artifact_sha256": job.artifact_sha256,
            "artifact_bytes": job.artifact_bytes,
            "manifest_sha256": job.manifest_sha256,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "expires_at": job.expires_at.isoformat(),
        }
        deleted = {"artifact": "absent", "manifest": "absent"}
        if job.artifact_uri and job.artifact_sha256:
            deleted["artifact"] = self._delete_if_unreferenced(
                job,
                job.artifact_uri,
                job.artifact_sha256,
                DataExportJob.artifact_uri,
            )
        if job.manifest_uri and job.manifest_sha256:
            deleted["manifest"] = self._delete_if_unreferenced(
                job,
                job.manifest_uri,
                job.manifest_sha256,
                DataExportJob.manifest_uri,
            )
        job.state = "expired"
        job.artifact_uri = None
        job.manifest_uri = None
        job.manifest_signature = None
        job.manifest_key_id = None
        job.updated_at = now
        event = self._event(
            principal,
            data_class=EXPORT_DATA_CLASS,
            target_type="data_export_job",
            target_id=job.id,
            policy=policy,
            idempotency_key=idempotency_key,
            reason=reason,
            outcome="succeeded",
            legal_hold_ids=[],
            details={"object_existed": deleted, "deleted_object_snapshot": snapshot},
        )
        self._audit(principal, "data.export_artifact.purge", job.id, "success", request_id)
        self.session.commit()
        return LifecycleOutcome(event, False)

    def _lock_tenant(self, tenant_id: str) -> None:
        tenant = self.session.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
        if tenant is None or not tenant.active:
            raise LifecycleError("Active tenant not found")

    def _delete_if_unreferenced(
        self,
        job: DataExportJob,
        uri: str,
        digest: str,
        uri_column: InstrumentedAttribute[str | None],
    ) -> str:
        shared_reference = self.session.scalar(
            select(DataExportJob.id)
            .where(
                DataExportJob.tenant_id == job.tenant_id,
                DataExportJob.id != job.id,
                uri_column == uri,
            )
            .with_for_update()
            .limit(1)
        )
        if shared_reference is not None:
            return "retained_shared_reference"
        return "deleted" if self.object_store.delete(uri, digest) else "already_absent"

    def _delete_version_object_if_unreferenced(
        self,
        version: SourceVersion,
        uri: str,
        digest: str,
        uri_column: InstrumentedAttribute[str | None],
    ) -> str:
        shared_reference = self.session.scalar(
            select(SourceVersion.id)
            .where(
                SourceVersion.tenant_id == version.tenant_id,
                SourceVersion.source_asset_id != version.source_asset_id,
                uri_column == uri,
            )
            .with_for_update()
            .limit(1)
        )
        if shared_reference is not None:
            return "retained_shared_reference"
        return "deleted" if self.object_store.delete(uri, digest) else "already_absent"

    def _source_asset_impact(
        self,
        asset: SourceAsset,
        policy: DataRetentionPolicy,
    ) -> SourceAssetImpact:
        versions = list(
            self.session.scalars(
                select(SourceVersion).where(
                    SourceVersion.tenant_id == asset.tenant_id,
                    SourceVersion.source_asset_id == asset.id,
                )
            )
        )
        version_ids = [version.id for version in versions]
        document_ids = {version.source_document_id for version in versions if version.source_document_id}
        run_ids = (
            list(
                self.session.scalars(
                    select(ExtractionRun.id).where(
                        ExtractionRun.tenant_id == asset.tenant_id,
                        ExtractionRun.source_version_id.in_(version_ids),
                    )
                )
            )
            if version_ids
            else []
        )
        staged_fact_count = published_fact_count = 0
        if run_ids:
            staged_fact_count = int(
                self.session.scalar(
                    select(func.count(StagedFact.id)).where(
                        StagedFact.tenant_id == asset.tenant_id,
                        StagedFact.extraction_run_id.in_(run_ids),
                    )
                )
                or 0
            )
            published_fact_count = int(
                self.session.scalar(
                    select(func.count(StagedFact.id)).where(
                        StagedFact.tenant_id == asset.tenant_id,
                        StagedFact.extraction_run_id.in_(run_ids),
                        or_(
                            StagedFact.status == GovernanceStatus.PUBLISHED,
                            StagedFact.published_resource_id.is_not(None),
                        ),
                    )
                )
                or 0
            )
        evidence_claim_count = self._document_count(EvidenceClaim, asset.tenant_id, document_ids)
        knowledge_citation_count = self._document_count(KnowledgeCitation, asset.tenant_id, document_ids)
        retrieval_projection_count = self._document_count(RetrievalProjection, asset.tenant_id, document_ids)
        shared_document_count = 0
        if document_ids:
            shared_document_count = int(
                self.session.scalar(
                    select(func.count(func.distinct(SourceVersion.source_document_id))).where(
                        SourceVersion.tenant_id == asset.tenant_id,
                        SourceVersion.source_asset_id != asset.id,
                        SourceVersion.source_document_id.in_(document_ids),
                    )
                )
                or 0
            )
        other_reference_count = self._other_document_reference_count(asset.tenant_id, document_ids, run_ids)
        eligible = bool(
            asset.state == SourceAssetState.MISSING
            and asset.missing_since is not None
            and _as_utc(asset.missing_since) + timedelta(seconds=policy.retention_seconds) <= datetime.now(UTC)
        )
        blockers: list[str] = []
        if published_fact_count:
            blockers.append("published_facts")
        if evidence_claim_count:
            blockers.append("evidence_claims")
        if knowledge_citation_count:
            blockers.append("knowledge_citations")
        if other_reference_count:
            blockers.append("other_source_document_references")
        return SourceAssetImpact(
            asset=asset,
            retention_eligible=eligible,
            version_count=len(versions),
            raw_object_count=sum(version.raw_object_uri is not None for version in versions),
            extracted_object_count=sum(version.extracted_text_object_uri is not None for version in versions),
            extraction_run_count=len(run_ids),
            staged_fact_count=staged_fact_count,
            published_fact_count=published_fact_count,
            evidence_claim_count=evidence_claim_count,
            knowledge_citation_count=knowledge_citation_count,
            retrieval_projection_count=retrieval_projection_count,
            shared_document_count=shared_document_count,
            other_document_reference_count=other_reference_count,
            blockers=blockers,
        )

    def _document_count(
        self,
        model: type[EvidenceClaim] | type[KnowledgeCitation] | type[RetrievalProjection],
        tenant_id: str,
        document_ids: set[str],
    ) -> int:
        if not document_ids:
            return 0
        return int(
            self.session.scalar(
                select(func.count(model.id)).where(
                    model.tenant_id == tenant_id,
                    model.source_document_id.in_(document_ids),
                )
            )
            or 0
        )

    def _other_document_reference_count(
        self,
        tenant_id: str,
        document_ids: set[str],
        owned_extraction_run_ids: list[str],
    ) -> int:
        if not document_ids:
            return 0
        excluded_tables = {
            "source_versions",
            "retrieval_projections",
            "staged_facts",
            "evidence_claims",
            "knowledge_citations",
        }
        staged_fact_filters = [
            StagedFact.tenant_id == tenant_id,
            StagedFact.source_document_id.in_(document_ids),
        ]
        if owned_extraction_run_ids:
            staged_fact_filters.append(StagedFact.extraction_run_id.not_in(owned_extraction_run_ids))
        total = int(self.session.scalar(select(func.count(StagedFact.id)).where(*staged_fact_filters)) or 0)
        for table in Base.metadata.sorted_tables:
            if table.name in excluded_tables or "tenant_id" not in table.c:
                continue
            for column in table.c:
                if any(foreign_key.target_fullname == "source_documents.id" for foreign_key in column.foreign_keys):
                    total += int(
                        self.session.scalar(
                            select(func.count())
                            .select_from(table)
                            .where(
                                table.c.tenant_id == tenant_id,
                                column.in_(document_ids),
                            )
                        )
                        or 0
                    )
        return total

    def _unshared_document_ids(self, tenant_id: str, document_ids: set[str]) -> set[str]:
        if not document_ids:
            return set()
        shared_ids = set(
            self.session.scalars(
                select(SourceVersion.source_document_id).where(
                    SourceVersion.tenant_id == tenant_id,
                    SourceVersion.source_document_id.in_(document_ids),
                )
            )
        )
        return document_ids - shared_ids

    def _active_export_policy(self, tenant_id: str) -> DataRetentionPolicy:
        return self._active_policy(tenant_id, EXPORT_DATA_CLASS)

    def _active_policy(self, tenant_id: str, data_class: str) -> DataRetentionPolicy:
        policy = self.session.scalar(
            select(DataRetentionPolicy).where(
                DataRetentionPolicy.tenant_id == tenant_id,
                DataRetentionPolicy.data_class == data_class,
                DataRetentionPolicy.active.is_(True),
            )
        )
        if policy is None:
            label = "export" if data_class == EXPORT_DATA_CLASS else "source asset"
            raise LifecycleConflict(f"No active {label} retention policy is configured")
        return policy

    def _applicable_holds(self, job: DataExportJob) -> list[LegalHold]:
        return list(
            self.session.scalars(
                select(LegalHold).where(
                    LegalHold.tenant_id == job.tenant_id,
                    LegalHold.status == "active",
                    or_(
                        LegalHold.scope_type == "tenant",
                        (LegalHold.scope_type == "billing_account") & (LegalHold.scope_id == job.billing_account_id),
                        (LegalHold.scope_type == "data_export_job") & (LegalHold.scope_id == job.id),
                    ),
                )
            )
        )

    def _applicable_source_holds(self, asset: SourceAsset) -> list[LegalHold]:
        return list(
            self.session.scalars(
                select(LegalHold).where(
                    LegalHold.tenant_id == asset.tenant_id,
                    LegalHold.status == "active",
                    or_(
                        LegalHold.scope_type == "tenant",
                        (LegalHold.scope_type == "data_source") & (LegalHold.scope_id == asset.data_source_id),
                        (LegalHold.scope_type == "source_asset") & (LegalHold.scope_id == asset.id),
                    ),
                )
            )
        )

    def _validate_scope(self, tenant_id: str, scope_type: str, scope_id: str | None) -> None:
        if scope_type == "tenant":
            if scope_id is not None:
                raise LifecycleError("Tenant legal hold must not have a scope ID")
            return
        if scope_type not in {"billing_account", "data_export_job", "data_source", "source_asset"} or scope_id is None:
            raise LifecycleError("Legal hold scope is invalid")
        if scope_type == "data_export_job":
            target = self.session.scalar(
                select(DataExportJob.id).where(DataExportJob.tenant_id == tenant_id, DataExportJob.id == scope_id)
            )
        elif scope_type == "billing_account":
            from pharma_intel.models import BillingAccount

            target = self.session.scalar(
                select(BillingAccount.id).where(BillingAccount.tenant_id == tenant_id, BillingAccount.id == scope_id)
            )
        elif scope_type == "data_source":
            target = self.session.scalar(
                select(DataSource.id).where(DataSource.tenant_id == tenant_id, DataSource.id == scope_id)
            )
        else:
            target = self.session.scalar(
                select(SourceAsset.id).where(SourceAsset.tenant_id == tenant_id, SourceAsset.id == scope_id)
            )
        if target is None:
            raise LifecycleError("Legal hold scope target not found")

    def _idempotent_event(
        self,
        tenant_id: str,
        idempotency_key: str,
        target_type: str,
        target_id: str,
    ) -> DataLifecycleEvent | None:
        existing = self.session.scalar(
            select(DataLifecycleEvent).where(
                DataLifecycleEvent.tenant_id == tenant_id,
                DataLifecycleEvent.idempotency_key == idempotency_key,
            )
        )
        if existing is not None and (existing.target_type != target_type or existing.target_id != target_id):
            raise LifecycleConflict("Idempotency key was used for another lifecycle target")
        return existing

    def _event(
        self,
        principal: Principal,
        *,
        data_class: str,
        target_type: str,
        target_id: str,
        policy: DataRetentionPolicy,
        idempotency_key: str,
        reason: str,
        outcome: str,
        legal_hold_ids: list[str],
        details: dict[str, object],
        action: str | None = None,
    ) -> DataLifecycleEvent:
        event = DataLifecycleEvent(
            tenant_id=principal.tenant_id,
            data_class=data_class,
            target_type=target_type,
            target_id=target_id,
            action=action or ("blocked" if outcome == "blocked" else "purge"),
            outcome=outcome,
            idempotency_key=idempotency_key,
            policy_id=policy.id,
            policy_version=policy.policy_version,
            legal_hold_ids=legal_hold_ids,
            actor_user_id=principal.actor_id,
            reason=reason,
            details=details,
        )
        self.session.add(event)
        return event

    def _audit(
        self,
        principal: Principal,
        action: str,
        resource_id: str | None,
        outcome: str,
        request_id: str,
    ) -> None:
        self.session.add(
            AuditEvent(
                tenant_id=principal.tenant_id,
                actor_type="user",
                actor_id=principal.actor_id,
                action=action,
                resource_type="data_lifecycle",
                resource_id=resource_id,
                outcome=outcome,
                request_id=request_id,
                details={},
            )
        )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
