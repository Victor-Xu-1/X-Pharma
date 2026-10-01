from __future__ import annotations

from fastapi import APIRouter

import pharma_intel.object_store as object_store_module
from pharma_intel.db import get_session_factory
from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep
from pharma_intel.schemas import SearchProjectionStatusRead
from pharma_intel.search.client import get_opensearch_gateway
from pharma_intel.search.projector import SearchProjectionConsumer

router = APIRouter()


@router.get(
    "/api/v1/admin/search/status",
    response_model=SearchProjectionStatusRead,
    tags=["data-factory"],
)
def search_projection_status(principal: PrincipalDep) -> SearchProjectionStatusRead:
    principal.require("ingestion:read")
    settings = runtime.get_settings()
    gateway = get_opensearch_gateway()
    status_snapshot = gateway.status()
    consumer = SearchProjectionConsumer(
        get_session_factory(),
        gateway,
        object_store_module.build_object_store(settings),
        settings,
    )
    return SearchProjectionStatusRead(
        available=status_snapshot.available,
        version=status_snapshot.version,
        cluster_name=status_snapshot.cluster_name,
        cluster_status=status_snapshot.cluster_status,
        aliases=status_snapshot.aliases,
        deliveries=consumer.delivery_counts(),
        error=status_snapshot.error,
    )
