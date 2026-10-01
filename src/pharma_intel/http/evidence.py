from __future__ import annotations

import hashlib
import uuid
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.dataset_repository import (
    DatasetAccessDenied,
    DatasetRepository,
    DatasetSelectionError,
    ResolvedDataset,
)
from pharma_intel.http import runtime
from pharma_intel.http.commercial_policy import _commercial_service
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _public_dossier_projection
from pharma_intel.licensing import DeliveryChannel, apply_evidence_license
from pharma_intel.models import SourceAsset, SourceAssetState, TenantDataset
from pharma_intel.provenance import ProvenanceRepository
from pharma_intel.schemas import (
    AgentEvidenceSearchResult,
    EvidenceChunk,
    EvidenceDatasetRead,
    EvidenceLicenseScope,
    EvidenceSearchRequest,
    EvidenceSearchResponse,
    ProvenanceResourceType,
    RecordProvenanceRead,
    RecordProvenanceResponse,
)
from pharma_intel.search.client import SearchProjectionError, get_opensearch_gateway
from pharma_intel.security import Principal

router = APIRouter()


def _evidence_delivery_channel(principal: Principal) -> DeliveryChannel:
    return "web" if principal.actor_type == "user" else "mcp"


def _evidence_license_scope(
    dataset: ResolvedDataset,
    channel: DeliveryChannel,
) -> EvidenceLicenseScope:
    policy = dataset.license_policy
    allowed_fields: list[str] = list(policy.allowed_fields)
    return EvidenceLicenseScope(
        dataset_key=dataset.key,
        license_id=policy.license_id,
        policy_version=policy.policy_version,
        attribution=policy.attribution,
        delivery_channel=channel,
        allowed_fields=allowed_fields,
        max_content_chars=policy.max_content_chars,
        valid_from=policy.valid_from,
        expires_at=policy.expires_at,
    )


def _public_evidence_document_id(dataset_key: str, document_id: str) -> str:
    digest = hashlib.sha256(f"{dataset_key}\0{document_id}".encode()).hexdigest()[:24]
    return f"citation-{digest}"


def _public_web_evidence_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    public: dict[str, Any] = {}
    source = metadata.get("source")
    if isinstance(source, str):
        parsed = urlsplit(source)
        if parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.username and not parsed.password:
            public["source"] = source
    license_metadata = metadata.get("license")
    if isinstance(license_metadata, dict):
        attribution = license_metadata.get("attribution")
        if isinstance(attribution, str) and attribution.strip():
            public["license"] = {"attribution": attribution.strip()}
    return public


def _licensed_evidence_chunk(
    dataset: ResolvedDataset,
    chunk: EvidenceChunk,
    channel: DeliveryChannel,
) -> tuple[EvidenceChunk, list[str]]:
    delivery = apply_evidence_license(
        dataset.license_policy,
        dataset_key=dataset.key,
        content=chunk.content,
        document_name=chunk.document_name,
        positions=chunk.positions,
        metadata=chunk.metadata,
    )
    updates: dict[str, Any] = {
        "content": delivery.content,
        "document_name": delivery.document_name,
        "dataset_id": dataset.key,
        "positions": delivery.positions,
        "metadata": delivery.metadata,
    }
    if channel == "web":
        updates.update(
            {
                "document_id": _public_evidence_document_id(dataset.key, chunk.document_id),
                "similarity": None,
                "metadata": _public_web_evidence_metadata(delivery.metadata),
            }
        )
    return chunk.model_copy(update=updates), delivery.warnings


def _search_evidence_response(
    payload: EvidenceSearchRequest,
    principal: Principal,
    session: Session,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> EvidenceSearchResponse:
    principal.require("evidence:read")
    resolved_limit = limit or payload.limit
    settings = runtime.get_settings()
    try:
        datasets = DatasetRepository(session, principal.tenant_id).resolve_for_principal(
            principal,
            payload.dataset_keys,
        )
    except DatasetAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DatasetSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    channel = _evidence_delivery_channel(principal)
    license_scopes = [_evidence_license_scope(dataset, channel) for dataset in datasets]
    warnings: list[str] = []
    try:
        matches = get_opensearch_gateway().search_evidence(
            principal.tenant_id,
            payload.query,
            [dataset.key for dataset in datasets],
            resolved_limit,
            offset,
        )
    except SearchProjectionError as exc:
        raise HTTPException(status_code=503, detail="Evidence search projection unavailable") from exc

    source_asset_ids = {
        str(match.metadata["source_asset_id"]) for match in matches if match.metadata.get("source_asset_id")
    }
    deleted_source_asset_ids = (
        set(
            session.scalars(
                select(SourceAsset.id).where(
                    SourceAsset.tenant_id == principal.tenant_id,
                    SourceAsset.id.in_(source_asset_ids),
                    SourceAsset.state == SourceAssetState.DELETED,
                )
            )
        )
        if source_asset_ids
        else set()
    )
    if deleted_source_asset_ids:
        matches = [
            match
            for match in matches
            if str(match.metadata.get("source_asset_id") or "") not in deleted_source_asset_ids
        ]
        warnings.append("Withdrawn source evidence was removed while the search projection catches up")

    dataset_by_key = {dataset.key: dataset for dataset in datasets}
    chunks: list[EvidenceChunk] = []
    for match in matches:
        dataset = dataset_by_key.get(match.dataset_key)
        if dataset is None:
            raise HTTPException(
                status_code=503,
                detail="Evidence search returned an unauthorized dataset",
            )
        chunk, chunk_warnings = _licensed_evidence_chunk(
            dataset,
            EvidenceChunk(
                content=match.content,
                document_id=match.document_id,
                document_name=match.document_name,
                dataset_id=match.dataset_key,
                similarity=match.score,
                positions=match.positions,
                metadata=match.metadata,
            ),
            channel,
        )
        chunks.append(chunk)
        warnings.extend(chunk_warnings)
    return EvidenceSearchResponse(
        query=payload.query,
        chunks=chunks,
        engine=("opensearch-hybrid" if settings.search_semantic_enabled else "opensearch")
        if channel == "mcp"
        else "evidence",
        license_scopes=license_scopes if channel == "mcp" else [],
        warnings=list(dict.fromkeys(warnings)),
    )


def _record_provenance_response(
    resource_type: ProvenanceResourceType,
    resource_id: str,
    principal: Principal,
    session: Session,
    *,
    limit: int,
) -> RecordProvenanceResponse:
    principal.require("evidence:read")
    repository = ProvenanceRepository(session, principal.tenant_id)
    dataset_keys = repository.dataset_keys_for_record(resource_type, resource_id)
    if not dataset_keys:
        return RecordProvenanceResponse(
            resource_type=resource_type,
            resource_id=resource_id,
            items=[],
            license_scopes=[],
        )
    try:
        datasets = DatasetRepository(session, principal.tenant_id).resolve_for_principal(
            principal,
            dataset_keys,
        )
    except DatasetAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DatasetSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    dataset_by_key = {dataset.key: dataset for dataset in datasets}
    channel = _evidence_delivery_channel(principal)
    warnings: list[str] = []
    withdrawn_count = repository.withdrawn_count(resource_type, resource_id)
    if withdrawn_count:
        warnings.append(f"{withdrawn_count} withdrawn source record(s) were omitted")
    items: list[RecordProvenanceRead] = []
    for record in repository.list_for_record(resource_type, resource_id, limit):
        dataset = dataset_by_key.get(record.link.dataset_key)
        if dataset is None:
            raise HTTPException(status_code=503, detail="Provenance resolved an unauthorized dataset")
        metadata = {
            "source": record.document.source_uri,
            "source_document_id": record.document.id,
            "source_version_id": record.version.id,
            "content_sha256": record.version.content_sha256,
            "evidence_claim_id": record.claim.id,
            "subject_entity_id": record.claim.subject_id,
            "review_status": record.claim.review_status.value,
        }
        delivery = apply_evidence_license(
            dataset.license_policy,
            dataset_key=dataset.key,
            content=record.staged_fact.source_quote,
            document_name=record.document.title,
            positions=[record.link.source_locator] if record.link.source_locator else [],
            metadata=metadata,
        )
        license_metadata = delivery.metadata.get("license")
        if not isinstance(license_metadata, dict):
            raise HTTPException(status_code=500, detail="Evidence license delivery metadata is invalid")
        locator = delivery.positions[0] if delivery.positions and isinstance(delivery.positions[0], str) else None
        items.append(
            RecordProvenanceRead(
                id=record.link.id,
                resource_type=resource_type,
                resource_id=resource_id,
                dataset_key=record.link.dataset_key,
                evidence_claim_id=delivery.metadata.get("evidence_claim_id"),
                source_document_id=delivery.metadata.get("source_document_id"),
                source_version_id=delivery.metadata.get("source_version_id"),
                content_sha256=delivery.metadata.get("content_sha256"),
                document_name=delivery.document_name,
                source_uri=delivery.metadata.get("source"),
                locator=locator,
                quote=delivery.content,
                subject_entity_id=delivery.metadata.get("subject_entity_id"),
                review_status=delivery.metadata.get("review_status"),
                created_at=record.link.created_at,
                license=license_metadata,
                warnings=delivery.warnings,
            )
        )
        warnings.extend(delivery.warnings)
    return RecordProvenanceResponse(
        resource_type=resource_type,
        resource_id=resource_id,
        items=items,
        license_scopes=[_evidence_license_scope(dataset, channel) for dataset in datasets],
        warnings=list(dict.fromkeys(warnings)),
    )


@router.get("/api/v1/evidence/datasets", response_model=list[EvidenceDatasetRead], tags=["evidence"])
def list_evidence_datasets(principal: PrincipalDep, session: SessionDep) -> list[EvidenceDatasetRead]:
    principal.require("evidence:read")
    try:
        resolved = DatasetRepository(session, principal.tenant_id).resolve_for_principal(
            principal,
            [],
            allow_empty=True,
        )
    except DatasetAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DatasetSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    keys = [dataset.key for dataset in resolved]
    names = {
        dataset.dataset_key: dataset.display_name
        for dataset in session.scalars(
            select(TenantDataset).where(
                TenantDataset.tenant_id == principal.tenant_id,
                TenantDataset.dataset_key.in_(keys),
            )
        )
    }
    return [
        EvidenceDatasetRead(
            dataset_key=dataset.key,
            display_name=names.get(dataset.key, dataset.key),
            attribution=dataset.license_policy.attribution,
        )
        for dataset in resolved
    ]


@router.post("/api/v1/evidence/search", response_model=EvidenceSearchResponse, tags=["evidence"])
def search_evidence(
    payload: EvidenceSearchRequest,
    principal: PrincipalDep,
    session: SessionDep,
) -> EvidenceSearchResponse:
    return _search_evidence_response(payload, principal, session)


@router.get(
    "/api/v1/provenance/{resource_type}/{resource_id}",
    response_model=RecordProvenanceResponse,
    response_model_exclude_none=True,
    tags=["evidence"],
)
def get_record_provenance(
    resource_type: ProvenanceResourceType,
    resource_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> RecordProvenanceResponse:
    return _public_dossier_projection(
        _record_provenance_response(resource_type, str(resource_id), principal, session, limit=limit)
    )


@router.post(
    "/internal/v1/domain/evidence/search",
    response_model=AgentEvidenceSearchResult,
    tags=["internal-domain"],
)
def search_evidence_for_agent(
    payload: EvidenceSearchRequest,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentEvidenceSearchResult:
    principal.require("evidence:read")
    arguments: dict[str, object] = payload.model_dump(mode="json")
    if cursor is not None:
        arguments["cursor"] = cursor
    commercial_service = _commercial_service(session, principal)
    reservation = commercial_service.authorize_paginated_query(
        reservation_id,
        billing_class="evidence.search",
        request_arguments=arguments,
        page_size=payload.limit,
    )
    result = _search_evidence_response(
        payload,
        principal,
        session,
        limit=payload.limit + 1,
        offset=reservation.page_offset,
    )
    chunks = result.chunks[: payload.limit]
    next_cursor = commercial_service.issue_next_cursor(
        reservation,
        next_offset=reservation.page_offset + len(chunks),
        has_more=len(result.chunks) > payload.limit,
    )
    return AgentEvidenceSearchResult(
        **result.model_dump(exclude={"chunks"}),
        chunks=chunks,
        limit=payload.limit,
        page_depth=reservation.page_depth,
        next_cursor=next_cursor,
    )


@router.get(
    "/internal/v1/domain/provenance/{resource_type}/{resource_id}",
    response_model=RecordProvenanceResponse,
    tags=["internal-domain"],
)
def get_record_provenance_for_agent(
    resource_type: ProvenanceResourceType,
    resource_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    limit: int = Query(default=20, ge=1, le=100),
) -> RecordProvenanceResponse:
    resource_id_string = str(resource_id)
    _commercial_service(session, principal).authorize_paginated_query(
        reservation_id,
        billing_class="provenance.read",
        request_arguments={
            "resource_type": resource_type,
            "resource_id": resource_id_string,
            "limit": limit,
        },
        page_size=limit,
    )
    return _record_provenance_response(
        resource_type,
        resource_id_string,
        principal,
        session,
        limit=limit,
    )
