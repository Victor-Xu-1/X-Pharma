from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

import pharma_intel.object_store as object_store_module
from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.ingest.commands.versions import replay_source_version as command_replay_source_version
from pharma_intel.models import SourceVersion
from pharma_intel.schemas import SourceVersionPreviewRead, SourceVersionReplayAcceptedRead, SourceVersionReplayRequest

router = APIRouter()


@router.get(
    "/api/v1/admin/source-versions/{version_id}/preview",
    response_model=SourceVersionPreviewRead,
    tags=["data-factory"],
)
def get_source_version_preview(
    version_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    max_chars: int = Query(default=20_000, ge=100, le=100_000),
) -> SourceVersionPreviewRead:
    principal.require("ingestion:read")
    version = session.scalar(
        select(SourceVersion).where(
            SourceVersion.id == version_id,
            SourceVersion.tenant_id == principal.tenant_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Source version not found")
    if version.error_code == "malware_detected":
        raise HTTPException(status_code=409, detail="Quarantined malware content cannot be previewed")
    if not version.extracted_text_object_uri or not version.extracted_text_sha256:
        raise HTTPException(status_code=409, detail="Parsed text is not available for this source version")
    try:
        payload = object_store_module.build_object_store(runtime.get_settings()).read_bytes(
            version.extracted_text_object_uri,
            max_bytes=8_000_000,
        )
        text_content = payload.decode("utf-8")
    except (object_store_module.ObjectStoreError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Parsed text preview is unavailable or exceeds the safe limit",
        ) from exc
    preview = text_content[:max_chars]
    return SourceVersionPreviewRead(
        source_version_id=version.id,
        text=preview,
        truncated=len(text_content) > len(preview),
        returned_chars=len(preview),
        extracted_text_sha256=version.extracted_text_sha256,
    )


@router.post(
    "/api/v1/admin/source-versions/{version_id}/replay",
    response_model=SourceVersionReplayAcceptedRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["data-factory"],
)
async def replay_source_version(
    version_id: str,
    payload: SourceVersionReplayRequest,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> SourceVersionReplayAcceptedRead:
    return await command_replay_source_version(
        version_id, payload, request.state.request_id, principal, session, settings=runtime.get_settings()
    )
