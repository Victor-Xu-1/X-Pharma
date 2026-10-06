from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

import pharma_intel.object_store as object_store_module
from pharma_intel.governance.review_comparison import read_fact_comparison
from pharma_intel.governance.service import GovernanceError, GovernanceService, governance_policy_sha256
from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.knowledge.compiler import KnowledgeCompiler
from pharma_intel.models import (
    EvidenceClaim,
    ExtractionRun,
    GovernanceStatus,
    ReviewTask,
    RunState,
    SourceAsset,
    SourceVersion,
    StagedFact,
)
from pharma_intel.schemas import GovernanceRunPageRead, GovernanceRunRead, ReviewDecision, StagedFactRead
from pharma_intel.schemas.governance import GovernanceFactComparisonRead

request_logger = structlog.get_logger("pharma_intel.request")

router = APIRouter()


@router.get(
    "/api/v1/governance/runs",
    response_model=GovernanceRunPageRead,
    tags=["governance"],
)
def list_governance_runs(
    principal: PrincipalDep,
    session: SessionDep,
    run_status: Annotated[RunState | None, Query(alias="status")] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> GovernanceRunPageRead:
    principal.require("governance:read")
    filters = [ExtractionRun.tenant_id == principal.tenant_id]
    if run_status is not None:
        filters.append(ExtractionRun.status == run_status)
    total = int(session.scalar(select(func.count()).select_from(ExtractionRun).where(*filters)) or 0)
    rows = session.execute(
        select(ExtractionRun, SourceVersion, SourceAsset)
        .join(
            SourceVersion,
            (SourceVersion.id == ExtractionRun.source_version_id)
            & (SourceVersion.tenant_id == ExtractionRun.tenant_id),
        )
        .join(
            SourceAsset,
            (SourceAsset.id == SourceVersion.source_asset_id) & (SourceAsset.tenant_id == ExtractionRun.tenant_id),
        )
        .where(*filters)
        .order_by(ExtractionRun.created_at.desc(), ExtractionRun.id.desc())
        .limit(limit)
        .offset(offset)
    )
    current_policy = governance_policy_sha256(runtime.get_settings())
    items = [
        GovernanceRunRead(
            id=run.id,
            source_version_id=version.id,
            source_asset_id=asset.id,
            source_logical_path=asset.logical_path,
            source_file_name=asset.file_name,
            source_content_sha256=version.content_sha256,
            schema_name=run.schema_name,
            schema_version=run.schema_version,
            model_provider=run.model_provider,
            model_name=run.model_name,
            prompt_sha256=run.prompt_sha256,
            policy_sha256=run.policy_sha256,
            input_sha256=run.input_sha256,
            policy_current=run.policy_sha256 == current_policy,
            status=run.status,
            validation_errors=run.validation_errors[:20],
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            estimated_cost=run.estimated_cost,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
        )
        for run, version, asset in rows
    ]
    return GovernanceRunPageRead(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        current_policy_sha256=current_policy,
    )


@router.get("/api/v1/governance/review-queue", response_model=list[StagedFactRead], tags=["governance"])
def list_review_queue(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[StagedFactRead]:
    principal.require("governance:read")
    facts = session.scalars(
        select(StagedFact)
        .join(ReviewTask, ReviewTask.staged_fact_id == StagedFact.id)
        .where(
            StagedFact.tenant_id == principal.tenant_id,
            ReviewTask.tenant_id == principal.tenant_id,
            ReviewTask.status == GovernanceStatus.REVIEW_PENDING,
        )
        .order_by(ReviewTask.priority.desc(), ReviewTask.created_at)
        .limit(limit)
    )
    return [StagedFactRead.model_validate(fact) for fact in facts]


def _export_published_knowledge_page(compiler: KnowledgeCompiler, page_id: str) -> None:
    try:
        compiler.export_page(page_id, runtime.get_settings().markdown_export_root)
    except (OSError, ValueError) as exc:
        request_logger.error(
            "knowledge_markdown_export_failed_after_publish",
            page_id=page_id,
            error_type=type(exc).__name__,
        )


@router.get(
    "/api/v1/governance/staged-facts/{staged_fact_id}/comparison",
    response_model=GovernanceFactComparisonRead,
    tags=["governance"],
)
def get_staged_fact_comparison(
    staged_fact_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> GovernanceFactComparisonRead:
    principal.require("governance:read")
    try:
        return read_fact_comparison(session, principal.tenant_id, staged_fact_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Staged fact not found") from exc


@router.post(
    "/api/v1/governance/staged-facts/{staged_fact_id}/decision",
    response_model=StagedFactRead,
    tags=["governance"],
)
def decide_staged_fact(
    staged_fact_id: str,
    payload: ReviewDecision,
    principal: PrincipalDep,
    session: SessionDep,
) -> StagedFactRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    if payload.decision == "reject" and not payload.notes:
        raise HTTPException(status_code=422, detail="A rejection reason is required")
    service = GovernanceService(
        session,
        runtime.get_settings(),
        object_store_module.build_object_store(runtime.get_settings()),
        principal.tenant_id,
    )
    try:
        if payload.decision == "approve":
            staged = service.approve_fact(staged_fact_id, principal.user_id, payload.notes)
            if staged.published_resource_type == "evidence_claim" and staged.published_resource_id:
                claim = session.get(EvidenceClaim, staged.published_resource_id)
                if claim is not None:
                    compiler = KnowledgeCompiler(session, principal.tenant_id)
                    result = compiler.compile_entity(claim.subject_id, run_id=f"review:{staged.id}")
                    _export_published_knowledge_page(compiler, result.page_id)
        else:
            staged = service.reject_fact(staged_fact_id, principal.user_id, payload.notes or "")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return StagedFactRead.model_validate(staged)
