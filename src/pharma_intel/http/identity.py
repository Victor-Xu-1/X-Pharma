from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status

from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.identity import EntityIdentityService, IdentityError, resolution_case_view, supported_namespaces
from pharma_intel.models import EntityType, ResolutionStatus, ReviewStatus
from pharma_intel.schemas import (
    EntityOntologyMappingCreate,
    EntityResolutionCaseRead,
    EntityResolutionDecisionRequest,
    EntityResolutionImpactRead,
    OntologyTermRead,
    OntologyTermUpsert,
)

router = APIRouter()


@router.get("/api/v1/governance/identity/namespaces", tags=["governance"])
def list_identifier_namespaces(principal: PrincipalDep) -> list[dict[str, Any]]:
    principal.require("governance:read")
    return supported_namespaces()


@router.get(
    "/api/v1/governance/ontology/terms",
    response_model=list[OntologyTermRead],
    tags=["governance"],
)
def list_ontology_terms(
    principal: PrincipalDep,
    session: SessionDep,
    ontology_name: str | None = Query(default=None, max_length=100),
    entity_type: EntityType | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[OntologyTermRead]:
    principal.require("governance:read")
    terms = EntityIdentityService(session, principal.tenant_id).list_ontology_terms(
        ontology_name=ontology_name,
        entity_type=entity_type,
        limit=limit,
    )
    return [OntologyTermRead.model_validate(item) for item in terms]


@router.post(
    "/api/v1/governance/ontology/terms",
    response_model=OntologyTermRead,
    status_code=status.HTTP_201_CREATED,
    tags=["governance"],
)
def register_ontology_term(
    payload: OntologyTermUpsert,
    principal: PrincipalDep,
    session: SessionDep,
) -> OntologyTermRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    try:
        term = EntityIdentityService(session, principal.tenant_id).register_ontology_term(payload.model_dump())
    except IdentityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return OntologyTermRead.model_validate(term)


@router.post(
    "/api/v1/governance/entities/{entity_id}/ontology-mappings",
    status_code=status.HTTP_201_CREATED,
    tags=["governance"],
)
def create_entity_ontology_mapping(
    entity_id: str,
    payload: EntityOntologyMappingCreate,
    principal: PrincipalDep,
    session: SessionDep,
) -> dict[str, Any]:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    try:
        mapping = EntityIdentityService(session, principal.tenant_id).map_ontology_term(
            entity_id=entity_id,
            ontology_term_id=payload.ontology_term_id,
            mapping_type=payload.mapping_type,
            confidence=payload.confidence,
            source_document_id=payload.source_document_id,
            evidence=payload.evidence,
            review_status=ReviewStatus.VERIFIED,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IdentityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": mapping.id,
        "entity_id": mapping.entity_id,
        "ontology_term_id": mapping.ontology_term_id,
        "mapping_type": mapping.mapping_type,
        "confidence": mapping.confidence,
        "review_status": mapping.review_status,
    }


@router.get(
    "/api/v1/governance/entity-resolution-cases",
    response_model=list[EntityResolutionCaseRead],
    tags=["governance"],
)
def list_entity_resolution_cases(
    principal: PrincipalDep,
    session: SessionDep,
    case_status: Annotated[ResolutionStatus, Query(alias="status")] = ResolutionStatus.PENDING,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[EntityResolutionCaseRead]:
    principal.require("governance:read")
    cases = EntityIdentityService(session, principal.tenant_id).list_cases(status=case_status, limit=limit)
    return [EntityResolutionCaseRead.model_validate(resolution_case_view(session, item)) for item in cases]


@router.get(
    "/api/v1/governance/entity-resolution-cases/{case_id}/impact",
    response_model=EntityResolutionImpactRead,
    tags=["governance"],
)
def get_entity_resolution_case_impact(
    case_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> EntityResolutionImpactRead:
    principal.require("governance:read")
    try:
        impact = EntityIdentityService(session, principal.tenant_id).resolution_impact(case_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IdentityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return EntityResolutionImpactRead.model_validate(impact)


@router.post(
    "/api/v1/governance/entity-resolution-cases/{case_id}/decision",
    response_model=EntityResolutionCaseRead,
    tags=["governance"],
)
def decide_entity_resolution_case(
    case_id: str,
    payload: EntityResolutionDecisionRequest,
    principal: PrincipalDep,
    session: SessionDep,
) -> EntityResolutionCaseRead:
    principal.require("governance:review")
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="A human reviewer account is required")
    try:
        item = EntityIdentityService(session, principal.tenant_id).decide(
            case_id,
            action=payload.action,
            expected_status=payload.expected_status,
            canonical_entity_id=payload.canonical_entity_id,
            user_id=principal.user_id,
            notes=payload.notes,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IdentityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return EntityResolutionCaseRead.model_validate(resolution_case_view(session, item))
