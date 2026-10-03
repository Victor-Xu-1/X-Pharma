from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import (
    _assert_public_entity_ids_visible,
    _assert_public_entity_visible,
    _intelligence_service,
    _public_dossier_projection,
)
from pharma_intel.research_activity import RESEARCH_ENTITY_RESOURCE_TYPE, RequestAuditResource
from pharma_intel.schemas import (
    BioactivityRead,
    CompanyDossierResponse,
    CompanyTimelineResult,
    DiseaseDossierResponse,
    DrugComparisonResult,
    DrugDossierResponse,
    EntityDossierResponse,
    SarComparisonResult,
    TargetDossierResponse,
    TargetProfileResponse,
)

router = APIRouter()


@router.get(
    "/api/v1/entities/{entity_id}/dossier",
    response_model=EntityDossierResponse,
    response_model_exclude_none=True,
    tags=["entities"],
)
def get_entity_dossier(
    entity_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> EntityDossierResponse:
    principal.require("dossiers:read")
    dossier = _intelligence_service(session, principal).entity_dossier(entity_id, limit)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    _assert_public_entity_visible(dossier.entity, principal)
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=dossier.entity.id,
        details={"entity_type": dossier.entity.entity_type.value},
    )
    return _public_dossier_projection(dossier)


@router.get(
    "/api/v1/drugs/comparison",
    response_model=DrugComparisonResult,
    response_model_exclude_none=True,
    tags=["drugs"],
)
def compare_drugs(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    drug_ids: Annotated[list[str], Query(min_length=2, max_length=4)],
) -> DrugComparisonResult:
    principal.require("dossiers:read")
    if len(set(drug_ids)) != len(drug_ids):
        raise HTTPException(status_code=422, detail="Drug comparison IDs must be unique")
    result = _intelligence_service(session, principal).drug_comparison_profiles(drug_ids)
    if len(result.items) != len(drug_ids):
        raise HTTPException(status_code=404, detail="One or more drugs were not found")
    request.state.audit_resource = RequestAuditResource(
        resource_type="research_drug_comparison",
        resource_id=hashlib.sha256("|".join(drug_ids).encode()).hexdigest(),
        details={"drug_count": len(drug_ids)},
    )
    return _public_dossier_projection(result)


@router.get(
    "/api/v1/drugs/{drug_id}/dossier",
    response_model=DrugDossierResponse,
    response_model_exclude_none=True,
    tags=["drugs"],
)
def get_drug_dossier(
    drug_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=100),
) -> DrugDossierResponse:
    principal.require("dossiers:read")
    dossier = _intelligence_service(session, principal).drug_dossier(drug_id, limit)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Drug not found")
    _assert_public_entity_visible(dossier.entity, principal)
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=dossier.entity.id,
        details={"entity_type": dossier.entity.entity_type.value, "profile": "drug"},
    )
    return _public_dossier_projection(dossier)


@router.get(
    "/api/v1/diseases/{disease_id}/dossier",
    response_model=DiseaseDossierResponse,
    response_model_exclude_none=True,
    tags=["diseases"],
)
def get_disease_dossier(
    disease_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=100),
) -> DiseaseDossierResponse:
    principal.require("dossiers:read")
    principal.require("pipelines:read")
    principal.require("epidemiology:read")
    dossier = _intelligence_service(session, principal).disease_dossier(disease_id, limit)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Disease not found")
    _assert_public_entity_visible(dossier.entity, principal)
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=dossier.entity.id,
        details={"entity_type": dossier.entity.entity_type.value, "profile": "disease"},
    )
    return _public_dossier_projection(dossier)


@router.get(
    "/api/v1/targets/{target_id}/profile",
    response_model=TargetProfileResponse,
    response_model_exclude_none=True,
    tags=["targets"],
)
def get_target_profile(target_id: str, principal: PrincipalDep, session: SessionDep) -> TargetProfileResponse:
    principal.require("targets:read")
    result = _intelligence_service(session, principal).target_profile(target_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Target not found")
    _assert_public_entity_visible(result.entity, principal)
    return _public_dossier_projection(result)


@router.get(
    "/api/v1/targets/{target_id}/dossier",
    response_model=TargetDossierResponse,
    response_model_exclude_none=True,
    tags=["targets"],
)
def get_target_dossier(
    target_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> TargetDossierResponse:
    principal.require("targets:read")
    principal.require("dossiers:read")
    result = _intelligence_service(session, principal).target_dossier(target_id, limit)
    if result is None:
        raise HTTPException(status_code=404, detail="Target not found")
    _assert_public_entity_visible(result.profile.entity, principal)
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=result.profile.entity.id,
        details={"entity_type": result.profile.entity.entity_type.value},
    )
    return _public_dossier_projection(result)


@router.get(
    "/api/v1/targets/{target_id}/bioactivities",
    response_model=list[BioactivityRead],
    tags=["activities"],
)
def get_bioactivities(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    standard_type: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=200, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> list[BioactivityRead]:
    principal.require("activities:read")
    _assert_public_entity_ids_visible(session, principal, [target_id])
    return _intelligence_service(session, principal).bioactivities(target_id, standard_type, limit, offset)


@router.get(
    "/api/v1/targets/{target_id}/sar-comparison",
    response_model=SarComparisonResult,
    tags=["activities"],
)
def compare_target_sar(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    standard_type: str | None = Query(default=None, max_length=120),
    assay_type: str | None = Query(default=None, max_length=120),
    assay_format: str | None = Query(default=None, max_length=160),
    organism: str | None = Query(default=None, max_length=160),
    cell_line: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> SarComparisonResult:
    principal.require("activities:read")
    _assert_public_entity_ids_visible(session, principal, [target_id])
    return _intelligence_service(session, principal).sar_comparison(
        target_id,
        standard_type=standard_type,
        assay_type=assay_type,
        assay_format=assay_format,
        organism=organism,
        cell_line=cell_line,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/api/v1/companies/{company_id}/dossier",
    response_model=CompanyDossierResponse,
    response_model_exclude_none=True,
    tags=["companies"],
)
def get_company_dossier(
    company_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=100),
) -> CompanyDossierResponse:
    principal.require("dossiers:read")
    principal.require("pipelines:read")
    principal.require("deals:read")
    dossier = _intelligence_service(session, principal).company_dossier(company_id, limit)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Company not found")
    _assert_public_entity_visible(dossier.entity, principal)
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=dossier.entity.id,
        details={"entity_type": dossier.entity.entity_type.value, "profile": "company"},
    )
    return _public_dossier_projection(dossier)


@router.get(
    "/api/v1/companies/{company_id}/timeline",
    response_model=CompanyTimelineResult,
    tags=["companies"],
)
def get_company_timeline(
    company_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> CompanyTimelineResult:
    principal.require("pipelines:read")
    principal.require("deals:read")
    _assert_public_entity_ids_visible(session, principal, [company_id])
    result = _intelligence_service(session, principal).company_timeline(company_id, limit, offset)
    if result is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return result
