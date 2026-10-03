from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import select

from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.ingest.commands.quarantine import (
    decide_source_version_quarantine_case as command_decide_source_version_quarantine_case,
)
from pharma_intel.models import (
    QuarantineStatus,
    SourceAsset,
    SourceVersion,
    SourceVersionQuarantineDecision,
)
from pharma_intel.schemas import (
    SourceVersionQuarantineCaseRead,
    SourceVersionQuarantineDecisionAcceptedRead,
    SourceVersionQuarantineDecisionRead,
    SourceVersionQuarantineDecisionRequest,
)

router = APIRouter()


def _quarantine_case_read(
    version: SourceVersion,
    asset: SourceAsset,
    decisions: list[SourceVersionQuarantineDecision],
) -> SourceVersionQuarantineCaseRead:
    malware = version.metadata_json.get("malware_scan")
    threat_name = malware.get("threat_name") if isinstance(malware, dict) else None
    return SourceVersionQuarantineCaseRead(
        source_version_id=version.id,
        source_asset_id=asset.id,
        file_name=asset.file_name,
        logical_path=asset.logical_path,
        quarantine_status=version.quarantine_status,
        quarantine_version=version.quarantine_version,
        threat_name=str(threat_name)[:240] if threat_name else None,
        error_code=version.error_code,
        error_message=version.error_message,
        updated_at=version.quarantine_updated_at or version.malware_scanned_at or version.discovered_at,
        decisions=[SourceVersionQuarantineDecisionRead.model_validate(item) for item in decisions],
    )


@router.get(
    "/api/v1/admin/quarantine-cases",
    response_model=list[SourceVersionQuarantineCaseRead],
    tags=["data-factory"],
)
def list_source_version_quarantine_cases(
    principal: PrincipalDep,
    session: SessionDep,
    status_filter: Annotated[QuarantineStatus | None, Query(alias="status")] = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SourceVersionQuarantineCaseRead]:
    principal.require("ingestion:read")
    filters = [
        SourceVersion.tenant_id == principal.tenant_id,
        SourceVersion.quarantine_status != QuarantineStatus.NOT_APPLICABLE,
    ]
    if status_filter is not None:
        filters.append(SourceVersion.quarantine_status == status_filter)
    rows = list(
        session.execute(
            select(SourceVersion, SourceAsset)
            .join(SourceAsset, SourceAsset.id == SourceVersion.source_asset_id)
            .where(*filters)
            .order_by(SourceVersion.quarantine_updated_at.desc(), SourceVersion.id)
            .limit(limit)
        )
    )
    # Queue reads stay bounded; immutable history is loaded only from the case detail endpoint.
    return [_quarantine_case_read(version, asset, []) for version, asset in rows]


@router.get(
    "/api/v1/admin/quarantine-cases/{version_id}",
    response_model=SourceVersionQuarantineCaseRead,
    tags=["data-factory"],
)
def get_source_version_quarantine_case(
    version_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> SourceVersionQuarantineCaseRead:
    principal.require("ingestion:read")
    row = session.execute(
        select(SourceVersion, SourceAsset)
        .join(SourceAsset, SourceAsset.id == SourceVersion.source_asset_id)
        .where(
            SourceVersion.id == version_id,
            SourceVersion.tenant_id == principal.tenant_id,
            SourceVersion.quarantine_status != QuarantineStatus.NOT_APPLICABLE,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Quarantine case not found")
    version, asset = row
    decisions = list(
        session.scalars(
            select(SourceVersionQuarantineDecision)
            .where(
                SourceVersionQuarantineDecision.tenant_id == principal.tenant_id,
                SourceVersionQuarantineDecision.source_version_id == version.id,
            )
            .order_by(SourceVersionQuarantineDecision.resulting_version)
        )
    )
    return _quarantine_case_read(version, asset, decisions)


@router.post(
    "/api/v1/admin/quarantine-cases/{version_id}/decisions",
    response_model=SourceVersionQuarantineDecisionAcceptedRead,
    tags=["data-factory"],
)
async def decide_source_version_quarantine_case(
    version_id: str,
    payload: SourceVersionQuarantineDecisionRequest,
    request: Request,
    response: Response,
    principal: PrincipalDep,
    session: SessionDep,
) -> SourceVersionQuarantineDecisionAcceptedRead:
    response.status_code = status.HTTP_202_ACCEPTED if payload.action == "rescan" else status.HTTP_200_OK
    return await command_decide_source_version_quarantine_case(
        version_id, payload, request.state.request_id, principal, session, settings=runtime.get_settings()
    )
