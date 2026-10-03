from __future__ import annotations

from fastapi import APIRouter, Query, Request, status
from sqlalchemy.orm import Session

import pharma_intel.object_store as object_store_module
from pharma_intel.governance.lifecycle import DataLifecycleService, SourceAssetImpact
from pharma_intel.http import runtime
from pharma_intel.http.commercial_exports import _export_read
from pharma_intel.http.commercial_policy import _require_human_commercial
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.schemas import (
    DataExportRead,
    DataLifecycleEventRead,
    DataLifecyclePurgeRead,
    DataLifecyclePurgeRequest,
    DataRetentionPolicyRead,
    DataRetentionPolicyUpdate,
    DeletedSourceAssetRead,
    LegalHoldCreate,
    LegalHoldRead,
    LegalHoldRelease,
    SourceAssetImpactRead,
)
from pharma_intel.security import Principal

router = APIRouter()


def _data_lifecycle_service(session: Session, principal: Principal, scope: str) -> DataLifecycleService:
    _require_human_commercial(principal, scope)
    return DataLifecycleService(session, object_store_module.build_object_store(runtime.get_settings()))


@router.get(
    "/api/v1/commercial/data-lifecycle/retention-policies",
    response_model=list[DataRetentionPolicyRead],
    tags=["commercial"],
)
def list_data_retention_policies(
    principal: PrincipalDep,
    session: SessionDep,
) -> list[DataRetentionPolicyRead]:
    policies = _data_lifecycle_service(session, principal, "commercial:read").list_policies(principal)
    return [DataRetentionPolicyRead.model_validate(policy) for policy in policies]


@router.put(
    "/api/v1/commercial/data-lifecycle/retention-policies/export-artifacts",
    response_model=DataRetentionPolicyRead,
    tags=["commercial"],
)
def upsert_export_retention_policy(
    payload: DataRetentionPolicyUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataRetentionPolicyRead:
    policy = _data_lifecycle_service(session, principal, "commercial:write").upsert_export_policy(
        principal,
        retention_seconds=payload.retention_seconds,
        legal_basis=payload.legal_basis,
        geographic_scope=payload.geographic_scope,
        active=payload.active,
        request_id=request.state.request_id,
    )
    return DataRetentionPolicyRead.model_validate(policy)


@router.put(
    "/api/v1/commercial/data-lifecycle/retention-policies/source-assets",
    response_model=DataRetentionPolicyRead,
    tags=["commercial"],
)
def upsert_source_retention_policy(
    payload: DataRetentionPolicyUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataRetentionPolicyRead:
    policy = _data_lifecycle_service(session, principal, "commercial:write").upsert_source_policy(
        principal,
        retention_seconds=payload.retention_seconds,
        legal_basis=payload.legal_basis,
        geographic_scope=payload.geographic_scope,
        active=payload.active,
        request_id=request.state.request_id,
    )
    return DataRetentionPolicyRead.model_validate(policy)


@router.get(
    "/api/v1/commercial/data-lifecycle/legal-holds",
    response_model=list[LegalHoldRead],
    tags=["commercial"],
)
def list_legal_holds(
    principal: PrincipalDep,
    session: SessionDep,
    active_only: bool = Query(default=False),
) -> list[LegalHoldRead]:
    holds = _data_lifecycle_service(session, principal, "commercial:read").list_holds(
        principal,
        active_only=active_only,
    )
    return [LegalHoldRead.model_validate(hold) for hold in holds]


@router.post(
    "/api/v1/commercial/data-lifecycle/legal-holds",
    response_model=LegalHoldRead,
    status_code=status.HTTP_201_CREATED,
    tags=["commercial"],
)
def place_legal_hold(
    payload: LegalHoldCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> LegalHoldRead:
    hold = _data_lifecycle_service(session, principal, "commercial:write").place_hold(
        principal,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        matter_reference=payload.matter_reference,
        reason=payload.reason,
        request_id=request.state.request_id,
    )
    return LegalHoldRead.model_validate(hold)


@router.post(
    "/api/v1/commercial/data-lifecycle/legal-holds/{hold_id}/release",
    response_model=LegalHoldRead,
    tags=["commercial"],
)
def release_legal_hold(
    hold_id: str,
    payload: LegalHoldRelease,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> LegalHoldRead:
    hold = _data_lifecycle_service(session, principal, "commercial:write").release_hold(
        principal,
        hold_id,
        reason=payload.reason,
        request_id=request.state.request_id,
    )
    return LegalHoldRead.model_validate(hold)


@router.get(
    "/api/v1/commercial/data-lifecycle/export-candidates",
    response_model=list[DataExportRead],
    tags=["commercial"],
)
def list_export_purge_candidates(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DataExportRead]:
    jobs = _data_lifecycle_service(session, principal, "commercial:read").export_candidates(
        principal,
        limit=limit,
    )
    return [_export_read(job) for job in jobs]


def _source_asset_impact_read(impact: SourceAssetImpact) -> SourceAssetImpactRead:
    return SourceAssetImpactRead(
        id=impact.asset.id,
        data_source_id=impact.asset.data_source_id,
        logical_path=impact.asset.logical_path,
        file_name=impact.asset.file_name,
        state=impact.asset.state.value,
        missing_since=impact.asset.missing_since,
        retention_eligible=impact.retention_eligible,
        version_count=impact.version_count,
        raw_object_count=impact.raw_object_count,
        extracted_object_count=impact.extracted_object_count,
        extraction_run_count=impact.extraction_run_count,
        staged_fact_count=impact.staged_fact_count,
        published_fact_count=impact.published_fact_count,
        evidence_claim_count=impact.evidence_claim_count,
        knowledge_citation_count=impact.knowledge_citation_count,
        retrieval_projection_count=impact.retrieval_projection_count,
        shared_document_count=impact.shared_document_count,
        other_document_reference_count=impact.other_document_reference_count,
        blockers=impact.blockers,
    )


@router.get(
    "/api/v1/commercial/data-lifecycle/source-candidates",
    response_model=list[SourceAssetImpactRead],
    tags=["commercial"],
)
def list_source_purge_candidates(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SourceAssetImpactRead]:
    impacts = _data_lifecycle_service(session, principal, "commercial:read").source_candidates(
        principal,
        limit=limit,
    )
    return [_source_asset_impact_read(impact) for impact in impacts]


@router.get(
    "/api/v1/commercial/data-lifecycle/source-assets/deleted",
    response_model=list[DeletedSourceAssetRead],
    tags=["commercial"],
)
def list_deleted_source_assets(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DeletedSourceAssetRead]:
    assets = _data_lifecycle_service(session, principal, "commercial:read").deleted_source_assets(
        principal,
        limit=limit,
    )
    return [DeletedSourceAssetRead.model_validate(asset) for asset in assets]


@router.get(
    "/api/v1/commercial/data-lifecycle/source-assets/{asset_id}/impact",
    response_model=SourceAssetImpactRead,
    tags=["commercial"],
)
def get_source_asset_purge_impact(
    asset_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> SourceAssetImpactRead:
    impact = _data_lifecycle_service(session, principal, "commercial:read").source_asset_impact(
        principal,
        asset_id,
    )
    return _source_asset_impact_read(impact)


@router.post(
    "/api/v1/commercial/data-lifecycle/source-assets/{asset_id}/purge",
    response_model=DataLifecyclePurgeRead,
    tags=["commercial"],
)
def purge_source_asset(
    asset_id: str,
    payload: DataLifecyclePurgeRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataLifecyclePurgeRead:
    outcome = _data_lifecycle_service(session, principal, "commercial:write").purge_source_asset(
        principal,
        asset_id,
        idempotency_key=payload.idempotency_key,
        reason=payload.reason,
        request_id=request.state.request_id,
    )
    return DataLifecyclePurgeRead(
        event=DataLifecycleEventRead.model_validate(outcome.event),
        replayed=outcome.replayed,
    )


@router.post(
    "/api/v1/commercial/data-lifecycle/source-assets/{asset_id}/reauthorize",
    response_model=DataLifecyclePurgeRead,
    tags=["commercial"],
)
def reauthorize_source_asset(
    asset_id: str,
    payload: DataLifecyclePurgeRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataLifecyclePurgeRead:
    outcome = _data_lifecycle_service(session, principal, "commercial:write").reauthorize_source_asset(
        principal,
        asset_id,
        idempotency_key=payload.idempotency_key,
        reason=payload.reason,
        request_id=request.state.request_id,
    )
    return DataLifecyclePurgeRead(
        event=DataLifecycleEventRead.model_validate(outcome.event),
        replayed=outcome.replayed,
    )


@router.post(
    "/api/v1/commercial/data-lifecycle/exports/{job_id}/purge",
    response_model=DataLifecyclePurgeRead,
    tags=["commercial"],
)
def purge_export_artifacts(
    job_id: str,
    payload: DataLifecyclePurgeRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataLifecyclePurgeRead:
    outcome = _data_lifecycle_service(session, principal, "commercial:write").purge_export(
        principal,
        job_id,
        idempotency_key=payload.idempotency_key,
        reason=payload.reason,
        request_id=request.state.request_id,
    )
    return DataLifecyclePurgeRead(
        event=DataLifecycleEventRead.model_validate(outcome.event),
        replayed=outcome.replayed,
    )


@router.get(
    "/api/v1/commercial/data-lifecycle/events",
    response_model=list[DataLifecycleEventRead],
    tags=["commercial"],
)
def list_data_lifecycle_events(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DataLifecycleEventRead]:
    events = _data_lifecycle_service(session, principal, "commercial:read").list_events(
        principal,
        limit=limit,
    )
    return [DataLifecycleEventRead.model_validate(event) for event in events]
