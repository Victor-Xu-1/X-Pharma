from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from pharma_intel.http import runtime
from pharma_intel.http.dependencies import SessionDep
from pharma_intel.search.client import SearchProjectionError, get_opensearch_gateway

router = APIRouter()


@router.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", tags=["health"])
def ready(session: SessionDep) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    settings = runtime.get_settings()
    if settings.search_backend == "opensearch":
        try:
            get_opensearch_gateway().assert_projection_ready()
        except SearchProjectionError as exc:
            raise HTTPException(status_code=503, detail="Search projection unavailable") from exc
    return {"status": "ready", "search": settings.search_backend}
