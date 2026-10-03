from __future__ import annotations

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import select

from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.ingest.commands.runs import cancel_ingestion_run as command_cancel_ingestion_run
from pharma_intel.ingest.commands.runs import replay_ingestion_run as command_replay_ingestion_run
from pharma_intel.ingest.run_read_model import IngestionRunReadService
from pharma_intel.models import IngestionFinding, IngestionRun
from pharma_intel.schemas import (
    IngestionFindingRead,
    IngestionRunCancelAcceptedRead,
    IngestionRunCancelRequest,
    IngestionRunRead,
    IngestionRunReplayRequest,
    IngestionScanAcceptedRead,
)

router = APIRouter()


@router.get("/api/v1/admin/ingestion-runs", response_model=list[IngestionRunRead], tags=["data-factory"])
def list_ingestion_runs(
    principal: PrincipalDep,
    session: SessionDep,
    data_source_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[IngestionRunRead]:
    principal.require("ingestion:read")
    statement = select(IngestionRun).where(IngestionRun.tenant_id == principal.tenant_id)
    if data_source_id:
        statement = statement.where(IngestionRun.data_source_id == data_source_id)
    runs = list(session.scalars(statement.order_by(IngestionRun.created_at.desc()).limit(limit)))
    return IngestionRunReadService(session, principal.tenant_id).build_many(runs)


@router.post(
    "/api/v1/admin/ingestion-runs/{run_id}/cancel",
    response_model=IngestionRunCancelAcceptedRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["data-factory"],
)
async def cancel_ingestion_run(
    run_id: str,
    payload: IngestionRunCancelRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> IngestionRunCancelAcceptedRead:
    return await command_cancel_ingestion_run(
        run_id, payload, request.state.request_id, principal, session, settings=runtime.get_settings()
    )


@router.post(
    "/api/v1/admin/ingestion-runs/{run_id}/replay",
    response_model=IngestionScanAcceptedRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["data-factory"],
)
async def replay_ingestion_run(
    run_id: str,
    payload: IngestionRunReplayRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> IngestionScanAcceptedRead:
    return await command_replay_ingestion_run(
        run_id, payload, request.state.request_id, principal, session, settings=runtime.get_settings()
    )


@router.get(
    "/api/v1/admin/ingestion-runs/{run_id}/findings",
    response_model=list[IngestionFindingRead],
    tags=["data-factory"],
)
def list_ingestion_findings(
    run_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[IngestionFindingRead]:
    principal.require("ingestion:read")
    findings = session.scalars(
        select(IngestionFinding)
        .where(
            IngestionFinding.tenant_id == principal.tenant_id,
            IngestionFinding.ingestion_run_id == run_id,
        )
        .order_by(IngestionFinding.occurred_at)
    )
    return [IngestionFindingRead.model_validate(item) for item in findings]
