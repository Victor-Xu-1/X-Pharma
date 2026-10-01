from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.ingest.replay import replayable_source_version_stages
from pharma_intel.models import SourceAsset, SourceAssetState, SourceVersion
from pharma_intel.schemas import SourceAssetDetailRead, SourceAssetPageRead, SourceAssetRead, SourceVersionRead

router = APIRouter()


@router.get("/api/v1/admin/source-assets", response_model=SourceAssetPageRead, tags=["data-factory"])
def list_source_assets(
    principal: PrincipalDep,
    session: SessionDep,
    data_source_id: str | None = None,
    state_filter: Annotated[SourceAssetState | None, Query(alias="state")] = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> SourceAssetPageRead:
    principal.require("ingestion:read")
    filters = [SourceAsset.tenant_id == principal.tenant_id]
    if data_source_id:
        filters.append(SourceAsset.data_source_id == data_source_id)
    if state_filter is not None:
        filters.append(SourceAsset.state == state_filter)
    total = int(session.scalar(select(func.count()).select_from(SourceAsset).where(*filters)) or 0)
    statement = select(SourceAsset).where(*filters)
    assets = session.scalars(
        statement.order_by(SourceAsset.last_seen_at.desc(), SourceAsset.id).offset(offset).limit(limit)
    )
    return SourceAssetPageRead(
        items=[SourceAssetRead.model_validate(asset) for asset in assets],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/api/v1/admin/source-assets/{asset_id}",
    response_model=SourceAssetDetailRead,
    tags=["data-factory"],
)
def get_source_asset_detail(
    asset_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> SourceAssetDetailRead:
    principal.require("ingestion:read")
    asset = session.scalar(
        select(SourceAsset).where(
            SourceAsset.id == asset_id,
            SourceAsset.tenant_id == principal.tenant_id,
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Source asset not found")
    versions = list(
        session.scalars(
            select(SourceVersion)
            .where(
                SourceVersion.source_asset_id == asset.id,
                SourceVersion.tenant_id == principal.tenant_id,
            )
            .order_by(SourceVersion.version_number.desc())
        )
    )
    settings = runtime.get_settings()
    return SourceAssetDetailRead(
        **SourceAssetRead.model_validate(asset).model_dump(),
        versions=[
            SourceVersionRead(
                **SourceVersionRead.model_validate(version).model_dump(exclude={"replayable_stages"}),
                replayable_stages=replayable_source_version_stages(
                    version,
                    ai_governance_enabled=settings.ai_governance_enabled,
                ),
            )
            for version in versions
        ],
    )
