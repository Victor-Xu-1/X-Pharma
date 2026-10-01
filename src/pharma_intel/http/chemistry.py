from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from pharma_intel.chemistry import ChemistrySearchResult, ChemistryService
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _assert_public_entity_ids_visible, _intelligence_service
from pharma_intel.schemas import (
    ChemistrySearchHitRead,
    ChemistrySearchRead,
    ChemistrySearchRequest,
    CompoundStructureRead,
)

router = APIRouter()


def _chemistry_arguments(payload: ChemistrySearchRequest) -> dict[str, object]:
    arguments: dict[str, object] = {
        "mode": payload.mode,
        "query": payload.query,
        "limit": payload.limit,
    }
    if payload.mode == "similarity":
        arguments["threshold"] = payload.threshold
    return arguments


def _execute_chemistry_search(
    session: Session,
    tenant_id: str,
    payload: ChemistrySearchRequest,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> ChemistrySearchRead:
    service = ChemistryService(session, tenant_id)
    resolved_limit = limit or payload.limit
    result: ChemistrySearchResult
    if payload.mode == "exact":
        result = service.exact(payload.query, resolved_limit, offset)
    elif payload.mode == "substructure":
        result = service.substructure(payload.query, resolved_limit, offset)
    else:
        result = service.similarity(payload.query, payload.threshold, resolved_limit, offset)
    return ChemistrySearchRead(
        mode=result.mode,
        normalized_query=result.normalized_query,
        items=[ChemistrySearchHitRead.model_validate(item) for item in result.hits],
        count=len(result.hits),
        as_of=result.as_of,
        standardization_version=result.standardization_version,
        fingerprint_version=result.fingerprint_version,
        similarity_threshold=result.similarity_threshold,
    )


@router.get("/api/v1/structures", response_model=list[CompoundStructureRead], tags=["structures"])
def search_structures(
    principal: PrincipalDep,
    session: SessionDep,
    entity_id: str | None = None,
    inchi_key: str | None = Query(default=None, max_length=27),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[CompoundStructureRead]:
    principal.require("structures:read")
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    return _intelligence_service(session, principal).structures(entity_id, inchi_key, limit)


@router.post(
    "/api/v1/chemistry/search",
    response_model=ChemistrySearchRead,
    tags=["structures"],
)
def search_chemistry(
    payload: ChemistrySearchRequest,
    principal: PrincipalDep,
    session: SessionDep,
) -> ChemistrySearchRead:
    principal.require("structures:read")
    return _execute_chemistry_search(session, principal.tenant_id, payload)
