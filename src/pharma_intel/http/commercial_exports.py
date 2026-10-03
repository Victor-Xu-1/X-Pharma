from __future__ import annotations

from fastapi import APIRouter, Query, status
from sqlalchemy.orm import Session

from pharma_intel.commercial.exports import (
    CommercialExportService,
    CreateExportCommand,
    build_export_service,
    export_job_view,
)
from pharma_intel.commercial.service import CommercialNotConfigured
from pharma_intel.http import runtime
from pharma_intel.http.commercial_policy import _require_human_commercial
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.models import DataExportJob
from pharma_intel.schemas import DataExportChunkRead, DataExportCreate, DataExportRead
from pharma_intel.security import Principal

router = APIRouter()


def _agent_export_service(session: Session, principal: Principal) -> CommercialExportService:
    principal.require(runtime.get_settings().mcp_required_scope)
    if not runtime.get_settings().mcp_commercial_enforcement_enabled:
        raise CommercialNotConfigured("Commercial MCP data access is disabled")
    return build_export_service(session, runtime.get_settings())


def _export_read(job: DataExportJob) -> DataExportRead:
    return DataExportRead.model_validate(export_job_view(job))


@router.post(
    "/internal/v1/exports",
    response_model=DataExportRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["internal-commercial"],
)
def create_data_export(
    payload: DataExportCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataExportRead:
    job = _agent_export_service(session, principal).create(
        principal,
        CreateExportCommand(
            dataset=payload.dataset,
            export_format=payload.export_format,
            filters=payload.filters,
            fields=payload.fields,
            max_records=payload.max_records,
            max_billable_units=payload.max_billable_units,
            idempotency_key=payload.idempotency_key,
        ),
    )
    return _export_read(job)


@router.get(
    "/internal/v1/exports/{job_id}",
    response_model=DataExportRead,
    tags=["internal-commercial"],
)
def read_data_export(
    job_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataExportRead:
    return _export_read(_agent_export_service(session, principal).get(principal, job_id))


@router.post(
    "/internal/v1/exports/{job_id}/cancel",
    response_model=DataExportRead,
    tags=["internal-commercial"],
)
def cancel_data_export(
    job_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataExportRead:
    return _export_read(_agent_export_service(session, principal).cancel(principal, job_id))


@router.get(
    "/internal/v1/exports/{job_id}/chunks",
    response_model=DataExportChunkRead,
    tags=["internal-commercial"],
)
def read_data_export_chunk(
    job_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=1000),
    cursor: str | None = Query(default=None, max_length=4096),
) -> DataExportChunkRead:
    chunk = _agent_export_service(session, principal).read_chunk(
        principal,
        job_id,
        limit=limit,
        cursor=cursor,
    )
    return DataExportChunkRead(
        items=chunk.items,
        count=chunk.count,
        next_cursor=chunk.next_cursor,
        manifest=chunk.manifest,
    )


@router.get(
    "/api/v1/commercial/exports",
    response_model=list[DataExportRead],
    tags=["commercial"],
)
def list_data_exports(
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DataExportRead]:
    _require_human_commercial(principal, "commercial:read")
    jobs = build_export_service(session, runtime.get_settings()).list_for_operator(principal, limit=limit)
    return [_export_read(job) for job in jobs]


@router.post(
    "/api/v1/commercial/exports/{job_id}/approve",
    response_model=DataExportRead,
    tags=["commercial"],
)
def approve_data_export(
    job_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataExportRead:
    _require_human_commercial(principal, "commercial:write")
    return _export_read(build_export_service(session, runtime.get_settings()).approve(principal, job_id))


@router.post(
    "/api/v1/commercial/exports/{job_id}/cancel",
    response_model=DataExportRead,
    tags=["commercial"],
)
def cancel_data_export_as_operator(
    job_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> DataExportRead:
    _require_human_commercial(principal, "commercial:write")
    return _export_read(build_export_service(session, runtime.get_settings()).cancel_as_operator(principal, job_id))
