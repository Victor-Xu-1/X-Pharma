from __future__ import annotations

from typing import Any, overload

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import (
    Entity,
    ReviewStatus,
)
from pharma_intel.schemas import (
    CompanyDossierResponse,
    DiseaseDossierResponse,
    DrugComparisonResult,
    DrugDossierResponse,
    DrugProgramSearchResult,
    EntityDossierResponse,
    EntityRead,
    RecordProvenanceResponse,
    TargetDossierResponse,
    TargetProfileResponse,
)
from pharma_intel.security import (
    Principal,
)

_PUBLIC_ENTITY_ATTRIBUTE_KEYS = frozenset(
    {
        "biomarker",
        "cas_number",
        "chemical_name",
        "country",
        "drug_category",
        "development_phase",
        "disease_area",
        "english_name",
        "headquarters",
        "innovation_type",
        "identity_scope",
        "identity_note",
        "label_provider",
        "inchi",
        "inchi_key",
        "mechanism",
        "modality",
        "organism",
        "program_tag",
        "program_tags",
        "region",
        "smiles",
        "status_detail",
        "target_class",
        "therapeutic_area",
    }
)


_PUBLIC_ENTITY_IDENTIFIER_HIDDEN_PREFIXES = (
    "pharmcube",
    "internal",
    "source",
    "ingestion",
)


def _is_public_entity_attribute_value(value: Any) -> bool:
    """Keep arbitrary nested governance payloads outside the human API."""

    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, list):
        return all(item is None or isinstance(item, str | int | float | bool) for item in value)
    return False


def _is_public_entity_identifier_namespace(namespace: str) -> bool:
    normalized = namespace.strip().casefold().replace("-", "_")
    return bool(normalized) and not any(
        normalized == prefix or normalized.startswith(f"{prefix}_")
        for prefix in _PUBLIC_ENTITY_IDENTIFIER_HIDDEN_PREFIXES
    )


def _public_entity_read(entity: Any) -> EntityRead:
    """Build the external entity projection without internal provenance fields."""

    read = EntityRead.model_validate(entity)
    attributes = {
        key: value
        for key, value in read.attributes.items()
        if key in _PUBLIC_ENTITY_ATTRIBUTE_KEYS and _is_public_entity_attribute_value(value)
    }
    external_ids = {
        namespace: value
        for namespace, value in read.external_ids.items()
        if _is_public_entity_identifier_namespace(namespace)
    }
    identifiers = [
        identifier.model_copy(update={"source_document_id": None})
        for identifier in read.identity_identifiers
        if _is_public_entity_identifier_namespace(identifier.namespace)
    ]
    return read.model_copy(
        update={"attributes": attributes, "external_ids": external_ids, "identity_identifiers": identifiers}
    )


_PUBLIC_DOSSIER_HIDDEN_KEYS = frozenset(
    {
        "debug",
        "governance",
        "governed_ai_extraction",
        "ingestion",
        "internal_review_trace",
        "origin",
        "permission",
        "permissions",
        "source_asset_id",
        "source_content_sha256",
        "source_document_id",
        "source_document_ids",
        "source_file_name",
        "source_logical_path",
        "source_version_id",
        "tenant_id",
        "tenant_slug",
    }
)


@overload
def _public_dossier_projection(value: DrugDossierResponse) -> DrugDossierResponse: ...


@overload
def _public_dossier_projection(value: DrugProgramSearchResult) -> DrugProgramSearchResult: ...


@overload
def _public_dossier_projection(value: DrugComparisonResult) -> DrugComparisonResult: ...


@overload
def _public_dossier_projection(value: DiseaseDossierResponse) -> DiseaseDossierResponse: ...


@overload
def _public_dossier_projection(value: CompanyDossierResponse) -> CompanyDossierResponse: ...


@overload
def _public_dossier_projection(value: TargetDossierResponse) -> TargetDossierResponse: ...


@overload
def _public_dossier_projection(value: TargetProfileResponse) -> TargetProfileResponse: ...


@overload
def _public_dossier_projection(value: EntityDossierResponse) -> EntityDossierResponse: ...


@overload
def _public_dossier_projection(value: RecordProvenanceResponse) -> RecordProvenanceResponse: ...


def _public_dossier_projection(value: Any) -> Any:
    """Remove internal provenance from public dossier payloads while keeping evidence text."""

    if isinstance(value, EntityRead):
        return _public_entity_read(value)
    if isinstance(value, BaseModel):
        updates: dict[str, Any] = {}
        for field_name in type(value).model_fields:
            child = getattr(value, field_name)
            if field_name in _PUBLIC_DOSSIER_HIDDEN_KEYS:
                updates[field_name] = [] if isinstance(child, list) else {} if isinstance(child, dict) else None
            else:
                updates[field_name] = _public_dossier_projection(child)
        return value.model_copy(update=updates)
    if isinstance(value, list):
        return [_public_dossier_projection(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _public_dossier_projection(item)
            for key, item in value.items()
            if key not in _PUBLIC_DOSSIER_HIDDEN_KEYS
        }
    return value


def _can_view_unpublished_entities(principal: Principal) -> bool:
    """Allow unpublished records only to explicit governance principals."""

    return "*" in principal.scopes or (principal.actor_type == "user" and "governance:read" in principal.scopes)


def _intelligence_service(session: Session, principal: Principal) -> IntelligenceService:
    return IntelligenceService(
        session,
        principal.tenant_id,
        include_unpublished=_can_view_unpublished_entities(principal),
    )


def _effective_public_review_status(
    principal: Principal,
    requested: ReviewStatus | None,
) -> ReviewStatus | None:
    """Clamp public entity reads to reviewed records for ordinary callers."""

    if _can_view_unpublished_entities(principal):
        return requested
    return ReviewStatus.VERIFIED


def _assert_public_entity_visible(entity: Any, principal: Principal) -> None:
    """Make known IDs obey the same review boundary as public search."""

    if _can_view_unpublished_entities(principal):
        return
    if getattr(entity, "review_status", None) != ReviewStatus.VERIFIED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")


def _assert_public_entity_ids_visible(
    session: Session,
    principal: Principal,
    entity_ids: list[str | None],
    *,
    reject_missing: bool = True,
) -> None:
    """Apply the published-entity boundary to domain filters before reading facts.

    Domain endpoints commonly accept several linked entity IDs. Checking those IDs
    at the API boundary prevents a paid Agent query from using a draft target,
    compound, disease or organization as a side door into domain data. Optional
    multi-value filters can set ``reject_missing=False`` so an unknown filter value
    produces no matching rows instead of turning an otherwise valid search into a
    resource-not-found error; existing unpublished entities are still rejected.
    """

    if _can_view_unpublished_entities(principal):
        return
    requested_ids = {entity_id for entity_id in entity_ids if entity_id}
    if not requested_ids:
        return
    entities = session.scalars(
        select(Entity).where(
            Entity.tenant_id == principal.tenant_id,
            Entity.id.in_(requested_ids),
        )
    ).all()
    if reject_missing and len(entities) != len(requested_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    for entity in entities:
        _assert_public_entity_visible(entity, principal)
