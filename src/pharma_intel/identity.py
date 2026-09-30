from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case as sql_case
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from pharma_intel.models import (
    Base,
    Entity,
    EntityAlias,
    EntityCanonicalLink,
    EntityIdentifier,
    EntityOntologyMapping,
    EntityResolutionCase,
    EntityResolutionDecision,
    EntityType,
    OntologyTerm,
    OutboxEvent,
    ResolutionStatus,
    ReviewStatus,
)

_SPACES = re.compile(r"\s+")
_ENTITY_REFERENCE_DOMAINS = {
    "activity_measurements": "chemistry",
    "assays": "chemistry",
    "clinical_trial_entity_roles": "clinical_trials",
    "clinical_trial_profiles": "clinical_trials",
    "comparison_set_members": "workspace",
    "compound_structures": "chemistry",
    "deal_asset_associations": "deals",
    "deal_party_associations": "deals",
    "deal_profiles": "deals",
    "deal_rights": "deals",
    "development_programs": "pipeline",
    "development_program_targets": "pipeline",
    "entity_aliases": "master_data",
    "entity_identifiers": "master_data",
    "entity_ontology_mappings": "master_data",
    "epidemiology_observations": "epidemiology",
    "evidence_claims": "evidence",
    "knowledge_links": "knowledge",
    "knowledge_pages": "knowledge",
    "monitoring_alerts": "monitoring",
    "news_events": "news",
    "patent_families": "patents",
    "patient_population_entity_links": "clinical_trials",
    "regulatory_events": "regulatory",
    "relationships": "relationships",
    "target_evidence_observations": "target_intelligence",
    "target_profiles": "target_intelligence",
}
_ENTITY_REFERENCE_CONTROL_TABLES = {"entity_canonical_links", "entity_resolution_cases"}


def normalize_name(value: str) -> str:
    return _SPACES.sub(" ", value.strip()).casefold()


class IdentityError(RuntimeError):
    pass


@dataclass(frozen=True)
class IdentifierNamespace:
    key: str
    aliases: tuple[str, ...]
    trusted: bool
    case: str = "upper"
    pattern: str | None = None


NAMESPACES = (
    IdentifierNamespace("hgnc", ("hgnc_id",), True, pattern=r"(?:HGNC:)?[0-9]+"),
    IdentifierNamespace("uniprot", ("uniprotkb", "uniprot_id"), True, pattern=r"[A-Z0-9]{6,10}"),
    IdentifierNamespace("ensembl", ("ensembl_id",), True, pattern=r"ENS[A-Z]*[GTP][0-9]+(?:\.[0-9]+)?"),
    IdentifierNamespace("chembl", ("chembl_id",), True, pattern=r"CHEMBL[0-9]+"),
    IdentifierNamespace("drugbank", ("drugbank_id",), True, pattern=r"DB[0-9]{5}"),
    IdentifierNamespace("pubchem_cid", ("pubchem", "cid"), True, pattern=r"[0-9]+"),
    IdentifierNamespace("clinicaltrials", ("nct", "nct_id"), True, pattern=r"NCT[0-9]{8}"),
    IdentifierNamespace("doi", (), True, case="lower", pattern=r"10\.[0-9]{4,9}/\S+"),
    IdentifierNamespace("efo", ("efo_id",), True, pattern=r"EFO[:_][0-9]+"),
    IdentifierNamespace("mesh", ("mesh_id",), True, pattern=r"[A-Z][0-9]{6,9}"),
    IdentifierNamespace("patent", ("publication_number",), True, pattern=r"[A-Z]{2}[A-Z0-9]+"),
    IdentifierNamespace("pharmcube_npuid", (), True, pattern=r"DR[0-9]{6}"),
    IdentifierNamespace("pharmcube_drug", (), True, case="lower", pattern=r"[a-f0-9]{64}"),
    IdentifierNamespace("pharmcube_target", (), True, case="lower", pattern=r"[a-f0-9]{64}"),
    IdentifierNamespace("pharmcube_indication", (), True, case="lower", pattern=r"[a-f0-9]{64}"),
    IdentifierNamespace("pharmcube_organization", (), True, case="lower", pattern=r"[a-f0-9]{64}"),
)
_NAMESPACE_BY_ALIAS = {
    alias.casefold(): namespace for namespace in NAMESPACES for alias in (namespace.key, *namespace.aliases)
}
_SEPARATORS = re.compile(r"[\s-]+")


@dataclass(frozen=True)
class NormalizedIdentifier:
    namespace: str
    value: str
    normalized_value: str
    trusted: bool


def supported_namespaces() -> list[dict[str, Any]]:
    return [
        {
            "namespace": item.key,
            "aliases": list(item.aliases),
            "trusted": item.trusted,
            "pattern": item.pattern,
        }
        for item in NAMESPACES
    ]


def normalize_identifier(namespace: str, value: str) -> NormalizedIdentifier:
    raw_namespace = namespace.strip().casefold().replace("-", "_")
    raw_value = value.strip()
    if not raw_namespace or not raw_value or len(raw_namespace) > 80 or len(raw_value) > 500:
        raise IdentityError("Identifier namespace and value must be non-empty and bounded")
    spec = _NAMESPACE_BY_ALIAS.get(raw_namespace)
    if spec is None:
        return NormalizedIdentifier(raw_namespace, raw_value, raw_value.casefold(), False)
    normalized = raw_value
    if spec.key == "doi":
        normalized = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", normalized, flags=re.I)
    elif spec.key == "hgnc":
        normalized = re.sub(r"^HGNC:", "", normalized, flags=re.I)
    elif spec.key == "patent":
        normalized = _SEPARATORS.sub("", normalized)
    normalized = normalized.lower() if spec.case == "lower" else normalized.upper()
    if spec.pattern and re.fullmatch(spec.pattern, normalized) is None:
        raise IdentityError(f"Invalid {spec.key} identifier")
    return NormalizedIdentifier(spec.key, raw_value, normalized, spec.trusted)


class EntityIdentityService:
    def __init__(self, session: Session, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def sync_identifiers(
        self,
        entity: Entity,
        external_ids: dict[str, str],
        *,
        review_status: ReviewStatus,
        provenance: dict[str, Any] | None = None,
        source_document_id: str | None = None,
    ) -> list[EntityIdentifier]:
        records: list[EntityIdentifier] = []
        canonical_external_ids = dict(entity.external_ids)
        for namespace, value in external_ids.items():
            identifier = normalize_identifier(namespace, str(value))
            existing = self.session.scalar(
                select(EntityIdentifier).where(
                    EntityIdentifier.tenant_id == self.tenant_id,
                    EntityIdentifier.entity_id == entity.id,
                    EntityIdentifier.namespace == identifier.namespace,
                    EntityIdentifier.normalized_value == identifier.normalized_value,
                )
            )
            if existing is None:
                existing = EntityIdentifier(
                    tenant_id=self.tenant_id,
                    entity_id=entity.id,
                    entity_type=entity.entity_type,
                    namespace=identifier.namespace,
                    value=identifier.value,
                    normalized_value=identifier.normalized_value,
                    trusted_namespace=identifier.trusted,
                    source_document_id=source_document_id,
                    provenance=provenance or {},
                    review_status=review_status,
                )
                self.session.add(existing)
            elif review_status == ReviewStatus.VERIFIED:
                existing.review_status = ReviewStatus.VERIFIED
            canonical_external_ids[identifier.namespace] = identifier.normalized_value
            records.append(existing)
        entity.external_ids = canonical_external_ids
        self.session.flush()
        return records

    def resolve_or_create(
        self,
        reference: dict[str, Any],
        *,
        source_document_id: str | None = None,
        allow_unverified_trusted_identifiers: bool = False,
    ) -> Entity:
        entity_type = EntityType(str(reference["entity_type"]))
        name = str(reference["name"]).strip()
        if not name or len(name) > 500:
            raise IdentityError("Entity name must be non-empty and at most 500 characters")
        external_ids = {str(key): str(value) for key, value in (reference.get("external_ids") or {}).items()}
        normalized_ids = [normalize_identifier(key, value) for key, value in external_ids.items()]
        normalized_name = normalize_name(name)
        self._lock_resolution(entity_type, normalized_name, normalized_ids)
        identifier_review_statuses = (
            [ReviewStatus.VERIFIED, ReviewStatus.DRAFT]
            if allow_unverified_trusted_identifiers
            else [ReviewStatus.VERIFIED]
        )
        candidate_ids = {
            item.entity_id
            for identifier in normalized_ids
            if identifier.trusted
            for item in self.session.scalars(
                select(EntityIdentifier).where(
                    EntityIdentifier.tenant_id == self.tenant_id,
                    EntityIdentifier.entity_type == entity_type,
                    EntityIdentifier.namespace == identifier.namespace,
                    EntityIdentifier.normalized_value == identifier.normalized_value,
                    EntityIdentifier.review_status.in_(identifier_review_statuses),
                )
            )
        }
        name_match_ids = set(
            self.session.scalars(
                select(Entity.id).where(
                    Entity.tenant_id == self.tenant_id,
                    Entity.entity_type == entity_type,
                    Entity.normalized_name == normalized_name,
                )
            )
        )
        if len(candidate_ids) == 1:
            candidate_id = next(iter(candidate_ids))
            candidate = self.session.scalar(
                select(Entity).where(
                    Entity.id == candidate_id,
                    Entity.tenant_id == self.tenant_id,
                )
            )
            if candidate is not None and not self._trusted_conflicts(candidate, normalized_ids):
                existing_external_ids = dict(candidate.external_ids)
                self.sync_identifiers(
                    candidate,
                    external_ids,
                    review_status=ReviewStatus.VERIFIED,
                    provenance={"origin": "governed_ai_extraction"},
                    source_document_id=source_document_id,
                )
                if allow_unverified_trusted_identifiers:
                    candidate.review_status = ReviewStatus.VERIFIED
                if candidate.external_ids != existing_external_ids:
                    self._enqueue_entity_projection(candidate)
                return candidate
        if source_document_id and name_match_ids:
            same_source_matches = [
                candidate
                for candidate in self.session.scalars(
                    select(Entity).where(
                        Entity.tenant_id == self.tenant_id,
                        Entity.id.in_(name_match_ids),
                    )
                )
                if candidate.attributes.get("origin") == "governed_ai_extraction"
                and source_document_id in candidate.attributes.get("source_document_ids", [])
            ]
            if len(same_source_matches) == 1 and not self._trusted_conflicts(same_source_matches[0], normalized_ids):
                candidate = same_source_matches[0]
                existing_external_ids = dict(candidate.external_ids)
                self.sync_identifiers(
                    candidate,
                    external_ids,
                    review_status=candidate.review_status,
                    provenance={"origin": "governed_ai_extraction", "same_source_reference": True},
                    source_document_id=source_document_id,
                )
                if candidate.external_ids != existing_external_ids:
                    self._enqueue_entity_projection(candidate)
                return candidate
        needs_review = bool(candidate_ids or name_match_ids)
        entity = Entity(
            tenant_id=self.tenant_id,
            entity_type=entity_type,
            name=name,
            normalized_name=normalized_name,
            external_ids={},
            attributes={
                "origin": "governed_ai_extraction",
                "source_document_ids": [source_document_id] if source_document_id else [],
            },
            review_status=ReviewStatus.DRAFT if needs_review else ReviewStatus.VERIFIED,
        )
        self.session.add(entity)
        self.session.flush()
        self.session.add(
            EntityAlias(
                tenant_id=self.tenant_id,
                entity_id=entity.id,
                alias=name,
                normalized_alias=normalized_name,
            )
        )
        self.sync_identifiers(
            entity,
            external_ids,
            review_status=ReviewStatus.DRAFT if needs_review else ReviewStatus.VERIFIED,
            provenance={"origin": "governed_ai_extraction"},
            source_document_id=source_document_id,
        )
        self._enqueue_entity_projection(entity)
        cases = self.propose_candidates(entity, proposed_by="governed_ai_extraction")
        if len(candidate_ids) > 1:
            for case in cases:
                case.risk_tier = "high"
                case.reasons = [
                    *case.reasons,
                    {"code": "trusted_identifiers_resolve_multiple_entities", "weight": 0.0},
                ]
            self.session.flush()
        return entity

    def _enqueue_entity_projection(self, entity: Entity) -> None:
        self.session.add(
            OutboxEvent(
                tenant_id=self.tenant_id,
                aggregate_type="entity",
                aggregate_id=entity.id,
                event_type="canonical.entity.upserted",
                payload={"entity_id": entity.id, "schema_version": 1},
            )
        )

    def _lock_resolution(
        self,
        entity_type: EntityType,
        normalized_name: str,
        identifiers: list[NormalizedIdentifier],
    ) -> None:
        if self.session.bind is None or self.session.bind.dialect.name != "postgresql":
            return
        keys = {f"identity:{self.tenant_id}:{entity_type.value}:name:{normalized_name}"}
        keys.update(
            f"identity:{self.tenant_id}:{entity_type.value}:{item.namespace}:{item.normalized_value}"
            for item in identifiers
            if item.trusted
        )
        for key in sorted(keys):
            self.session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": key},
            )

    def propose_candidates(self, source: Entity, *, proposed_by: str) -> list[EntityResolutionCase]:
        identifiers = list(
            self.session.scalars(
                select(EntityIdentifier).where(
                    EntityIdentifier.tenant_id == self.tenant_id,
                    EntityIdentifier.entity_id == source.id,
                )
            )
        )
        candidate_ids: set[str] = set()
        if identifiers:
            candidate_ids.update(
                self.session.scalars(
                    select(EntityIdentifier.entity_id).where(
                        EntityIdentifier.tenant_id == self.tenant_id,
                        EntityIdentifier.entity_type == source.entity_type,
                        EntityIdentifier.entity_id != source.id,
                        or_(
                            *[
                                (
                                    (EntityIdentifier.namespace == item.namespace)
                                    & (EntityIdentifier.normalized_value == item.normalized_value)
                                )
                                for item in identifiers
                            ]
                        ),
                    )
                )
            )
        candidate_ids.update(
            self.session.scalars(
                select(Entity.id).where(
                    Entity.tenant_id == self.tenant_id,
                    Entity.entity_type == source.entity_type,
                    Entity.id != source.id,
                    Entity.normalized_name == source.normalized_name,
                )
            )
        )
        cases: list[EntityResolutionCase] = []
        for candidate_id in sorted(candidate_ids):
            candidate = self.session.get(Entity, candidate_id)
            if candidate is None:
                continue
            score, risk_tier, reasons = self._score(source, candidate, identifiers)
            if score < 0.45:
                continue
            case = self.session.scalar(
                select(EntityResolutionCase).where(
                    EntityResolutionCase.tenant_id == self.tenant_id,
                    EntityResolutionCase.source_entity_id == source.id,
                    EntityResolutionCase.candidate_entity_id == candidate.id,
                )
            )
            if case is None:
                case = EntityResolutionCase(
                    tenant_id=self.tenant_id,
                    source_entity_id=source.id,
                    candidate_entity_id=candidate.id,
                    score=score,
                    risk_tier=risk_tier,
                    reasons=reasons,
                    proposed_by=proposed_by,
                )
                self.session.add(case)
            cases.append(case)
        self.session.flush()
        return cases

    def list_cases(self, *, status: ResolutionStatus, limit: int) -> list[EntityResolutionCase]:
        return list(
            self.session.scalars(
                select(EntityResolutionCase)
                .where(
                    EntityResolutionCase.tenant_id == self.tenant_id,
                    EntityResolutionCase.status == status,
                )
                .order_by(
                    sql_case(
                        (EntityResolutionCase.risk_tier == "high", 3),
                        (EntityResolutionCase.risk_tier == "medium", 2),
                        else_=1,
                    ).desc(),
                    EntityResolutionCase.score.desc(),
                )
                .limit(limit)
            )
        )

    def register_ontology_term(self, payload: dict[str, Any]) -> OntologyTerm:
        identity = {
            "ontology_name": str(payload["ontology_name"]).strip().casefold(),
            "ontology_version": str(payload["ontology_version"]).strip(),
            "term_id": str(payload["term_id"]).strip().upper(),
            "entity_type": EntityType(str(payload["entity_type"])),
            "preferred_label": str(payload["preferred_label"]).strip(),
            "definition": payload.get("definition"),
            "synonyms": sorted({str(item).strip() for item in payload.get("synonyms", []) if str(item).strip()}),
            "parent_term_ids": sorted(
                {str(item).strip().upper() for item in payload.get("parent_term_ids", []) if str(item).strip()}
            ),
            "source_uri": payload.get("source_uri"),
        }
        if not all(identity[key] for key in ("ontology_name", "ontology_version", "term_id", "preferred_label")):
            raise IdentityError("Ontology identity fields must be non-empty")
        content_sha256 = hashlib.sha256(
            json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        existing = self.session.scalar(
            select(OntologyTerm).where(
                OntologyTerm.tenant_id == self.tenant_id,
                OntologyTerm.ontology_name == identity["ontology_name"],
                OntologyTerm.ontology_version == identity["ontology_version"],
                OntologyTerm.term_id == identity["term_id"],
            )
        )
        if existing is not None:
            if existing.content_sha256 != content_sha256:
                raise IdentityError("Ontology term version is immutable; publish a new ontology version")
            return existing
        term = OntologyTerm(tenant_id=self.tenant_id, content_sha256=content_sha256, active=True, **identity)
        self.session.add(term)
        self.session.commit()
        self.session.refresh(term)
        return term

    def list_ontology_terms(
        self, *, ontology_name: str | None, entity_type: EntityType | None, limit: int
    ) -> list[OntologyTerm]:
        filters = [OntologyTerm.tenant_id == self.tenant_id, OntologyTerm.active.is_(True)]
        if ontology_name:
            filters.append(OntologyTerm.ontology_name == ontology_name.strip().casefold())
        if entity_type:
            filters.append(OntologyTerm.entity_type == entity_type)
        return list(
            self.session.scalars(
                select(OntologyTerm)
                .where(*filters)
                .order_by(OntologyTerm.ontology_name, OntologyTerm.term_id)
                .limit(limit)
            )
        )

    def map_ontology_term(
        self,
        *,
        entity_id: str,
        ontology_term_id: str,
        mapping_type: str,
        confidence: float,
        evidence: dict[str, Any],
        source_document_id: str | None,
        review_status: ReviewStatus,
    ) -> EntityOntologyMapping:
        entity = self.session.scalar(select(Entity).where(Entity.id == entity_id, Entity.tenant_id == self.tenant_id))
        term = self.session.scalar(
            select(OntologyTerm).where(
                OntologyTerm.id == ontology_term_id,
                OntologyTerm.tenant_id == self.tenant_id,
                OntologyTerm.active.is_(True),
            )
        )
        if entity is None or term is None:
            raise LookupError("Entity or ontology term not found")
        if entity.entity_type != term.entity_type:
            raise IdentityError("Ontology term entity type does not match entity type")
        if mapping_type not in {"exact", "broad", "narrow", "related"} or not 0 <= confidence <= 1:
            raise IdentityError("Invalid ontology mapping type or confidence")
        existing = self.session.scalar(
            select(EntityOntologyMapping).where(
                EntityOntologyMapping.tenant_id == self.tenant_id,
                EntityOntologyMapping.entity_id == entity.id,
                EntityOntologyMapping.ontology_term_id == term.id,
                EntityOntologyMapping.mapping_type == mapping_type,
            )
        )
        if existing is None:
            existing = EntityOntologyMapping(
                tenant_id=self.tenant_id,
                entity_id=entity.id,
                ontology_term_id=term.id,
                mapping_type=mapping_type,
                confidence=confidence,
                source_document_id=source_document_id,
                evidence=evidence,
                review_status=review_status,
            )
            self.session.add(existing)
        else:
            existing.confidence = confidence
            existing.evidence = evidence
            existing.source_document_id = source_document_id
            existing.review_status = review_status
        self.session.commit()
        self.session.refresh(existing)
        return existing

    def resolution_impact(self, case_id: str) -> dict[str, Any]:
        case = self.session.scalar(
            select(EntityResolutionCase).where(
                EntityResolutionCase.id == case_id,
                EntityResolutionCase.tenant_id == self.tenant_id,
            )
        )
        if case is None:
            raise LookupError("Entity resolution case not found")
        source = self.session.scalar(
            select(Entity).where(Entity.id == case.source_entity_id, Entity.tenant_id == self.tenant_id)
        )
        candidate = self.session.scalar(
            select(Entity).where(Entity.id == case.candidate_entity_id, Entity.tenant_id == self.tenant_id)
        )
        if source is None or candidate is None:
            raise IdentityError("Resolution case references an unavailable entity")

        references: list[dict[str, Any]] = []
        source_reference_count = 0
        candidate_reference_count = 0
        for table in sorted(Base.metadata.tables.values(), key=lambda item: item.name):
            if table.name in _ENTITY_REFERENCE_CONTROL_TABLES or "tenant_id" not in table.c:
                continue
            for column in table.columns:
                references_entity = any(
                    foreign_key.column.table.name == Entity.__tablename__ and foreign_key.column.name == Entity.id.key
                    for foreign_key in column.foreign_keys
                )
                if not references_entity:
                    continue
                source_count, candidate_count = self.session.execute(
                    select(
                        func.sum(sql_case((column == source.id, 1), else_=0)),
                        func.sum(sql_case((column == candidate.id, 1), else_=0)),
                    )
                    .select_from(table)
                    .where(table.c.tenant_id == self.tenant_id)
                ).one()
                source_value = int(source_count or 0)
                candidate_value = int(candidate_count or 0)
                source_reference_count += source_value
                candidate_reference_count += candidate_value
                if source_value or candidate_value:
                    references.append(
                        {
                            "domain": _ENTITY_REFERENCE_DOMAINS.get(table.name, "other"),
                            "table": table.name,
                            "column": column.name,
                            "source_count": source_value,
                            "candidate_count": candidate_value,
                        }
                    )

        trusted_counts = dict(
            self.session.execute(
                select(EntityIdentifier.entity_id, func.count())
                .where(
                    EntityIdentifier.tenant_id == self.tenant_id,
                    EntityIdentifier.entity_id.in_([source.id, candidate.id]),
                    EntityIdentifier.trusted_namespace.is_(True),
                    EntityIdentifier.review_status == ReviewStatus.VERIFIED,
                )
                .group_by(EntityIdentifier.entity_id)
            )
            .tuples()
            .all()
        )
        source_trusted_count = int(trusted_counts.get(source.id, 0))
        candidate_trusted_count = int(trusted_counts.get(candidate.id, 0))
        source_rank = (
            source_trusted_count,
            int(source.review_status == ReviewStatus.VERIFIED),
            source_reference_count,
        )
        candidate_rank = (
            candidate_trusted_count,
            int(candidate.review_status == ReviewStatus.VERIFIED),
            candidate_reference_count,
        )
        recommendation_reasons: list[str] = []
        if source_trusted_count != candidate_trusted_count:
            recommendation_reasons.append("verified_trusted_identifier_count")
        if source.review_status != candidate.review_status:
            recommendation_reasons.append("entity_review_status")
        if source_reference_count != candidate_reference_count:
            recommendation_reasons.append("governed_reference_count")
        if not recommendation_reasons:
            recommendation_reasons.append("candidate_stable_tie_break")
        recommended_canonical_entity_id = source.id if source_rank > candidate_rank else candidate.id

        active_link = self.session.scalar(
            select(EntityCanonicalLink)
            .where(
                EntityCanonicalLink.tenant_id == self.tenant_id,
                EntityCanonicalLink.resolution_case_id == case.id,
                EntityCanonicalLink.active.is_(True),
            )
            .order_by(EntityCanonicalLink.updated_at.desc(), EntityCanonicalLink.id.desc())
            .limit(1)
        )
        decisions = list(
            self.session.scalars(
                select(EntityResolutionDecision)
                .where(
                    EntityResolutionDecision.tenant_id == self.tenant_id,
                    EntityResolutionDecision.resolution_case_id == case.id,
                )
                .order_by(EntityResolutionDecision.created_at, EntityResolutionDecision.id)
            )
        )
        return {
            "case": resolution_case_view(self.session, case),
            "source_reference_count": source_reference_count,
            "candidate_reference_count": candidate_reference_count,
            "source_trusted_identifier_count": source_trusted_count,
            "candidate_trusted_identifier_count": candidate_trusted_count,
            "recommended_canonical_entity_id": recommended_canonical_entity_id,
            "recommendation_reasons": recommendation_reasons,
            "active_alias_entity_id": active_link.alias_entity_id if active_link else None,
            "active_canonical_entity_id": active_link.canonical_entity_id if active_link else None,
            "rollback_available": case.status == ResolutionStatus.APPROVED and active_link is not None,
            "references": references,
            "decisions": decisions,
        }

    def decide(
        self,
        case_id: str,
        *,
        action: str,
        expected_status: ResolutionStatus | str,
        canonical_entity_id: str | None,
        user_id: str,
        notes: str | None,
    ) -> EntityResolutionCase:
        case = self.session.scalar(
            select(EntityResolutionCase)
            .where(
                EntityResolutionCase.id == case_id,
                EntityResolutionCase.tenant_id == self.tenant_id,
            )
            .with_for_update()
        )
        if case is None:
            raise LookupError("Entity resolution case not found")
        if action not in {"approve", "reject", "revert"}:
            raise IdentityError("Unsupported entity resolution action")
        if not notes:
            raise IdentityError("An entity resolution decision reason is required")
        try:
            expected = (
                expected_status if isinstance(expected_status, ResolutionStatus) else ResolutionStatus(expected_status)
            )
        except ValueError as exc:
            raise IdentityError("Unsupported expected entity resolution status") from exc
        if case.status != expected:
            raise IdentityError("Entity resolution case changed; refresh before deciding")
        impact_before = self.resolution_impact(case.id)
        link = self.session.scalar(
            select(EntityCanonicalLink)
            .where(
                EntityCanonicalLink.tenant_id == self.tenant_id,
                EntityCanonicalLink.resolution_case_id == case.id,
            )
            .order_by(EntityCanonicalLink.updated_at.desc(), EntityCanonicalLink.id.desc())
            .limit(1)
        )
        resolved_alias_entity_id: str | None = None
        resolved_canonical_entity_id: str | None = None
        if action == "approve":
            if case.status not in {ResolutionStatus.PENDING, ResolutionStatus.REVERTED}:
                raise IdentityError("Only pending or reverted resolution cases can be approved")
            selected_canonical_id = canonical_entity_id or case.candidate_entity_id
            if selected_canonical_id not in {case.source_entity_id, case.candidate_entity_id}:
                raise IdentityError("Canonical entity must be one of the resolution case entities")
            alias_entity_id = (
                case.candidate_entity_id if selected_canonical_id == case.source_entity_id else case.source_entity_id
            )
            effective_canonical_id = self.canonical_entity_id(selected_canonical_id)
            self._assert_no_cycle(alias_entity_id, effective_canonical_id)
            alias_link = self.session.scalar(
                select(EntityCanonicalLink).where(
                    EntityCanonicalLink.tenant_id == self.tenant_id,
                    EntityCanonicalLink.alias_entity_id == alias_entity_id,
                )
            )
            if alias_link is not None and (link is None or alias_link.id != link.id):
                state = "active" if alias_link.active else "historical"
                raise IdentityError(f"Entity already has an {state} canonical link governed by another case")
            if link is None:
                link = EntityCanonicalLink(
                    tenant_id=self.tenant_id,
                    alias_entity_id=alias_entity_id,
                    canonical_entity_id=effective_canonical_id,
                    resolution_case_id=case.id,
                )
                self.session.add(link)
            else:
                if link.active:
                    raise IdentityError("Resolution case already has an active canonical link")
                link.alias_entity_id = alias_entity_id
                link.canonical_entity_id = effective_canonical_id
                link.active = True
            case.status = ResolutionStatus.APPROVED
            resolved_alias_entity_id = alias_entity_id
            resolved_canonical_entity_id = effective_canonical_id
        elif action == "reject":
            if case.status != ResolutionStatus.PENDING:
                raise IdentityError("Only pending resolution cases can be rejected")
            case.status = ResolutionStatus.REJECTED
        else:
            if case.status != ResolutionStatus.APPROVED or link is None or not link.active:
                raise IdentityError("Resolution case has no active canonical link to revert")
            resolved_alias_entity_id = link.alias_entity_id
            resolved_canonical_entity_id = link.canonical_entity_id
            link.active = False
            case.status = ResolutionStatus.REVERTED
        now = datetime.now(UTC)
        case.reviewed_by_user_id = user_id
        case.reviewed_at = now
        case.review_notes = notes
        self.session.add(
            EntityResolutionDecision(
                tenant_id=self.tenant_id,
                resolution_case_id=case.id,
                action=action,
                decided_by_user_id=user_id,
                notes=notes,
                snapshot={
                    "source_entity_id": case.source_entity_id,
                    "candidate_entity_id": case.candidate_entity_id,
                    "score": case.score,
                    "risk_tier": case.risk_tier,
                    "reasons": case.reasons,
                    "expected_status": expected.value,
                    "alias_entity_id": resolved_alias_entity_id,
                    "canonical_entity_id": resolved_canonical_entity_id,
                    "impact_summary": {
                        "source_reference_count": impact_before["source_reference_count"],
                        "candidate_reference_count": impact_before["candidate_reference_count"],
                        "source_trusted_identifier_count": impact_before["source_trusted_identifier_count"],
                        "candidate_trusted_identifier_count": impact_before["candidate_trusted_identifier_count"],
                        "recommended_canonical_entity_id": impact_before["recommended_canonical_entity_id"],
                    },
                    "decided_at": now.isoformat(),
                },
            )
        )
        self.session.commit()
        self.session.refresh(case)
        return case

    def canonical_entity_id(self, entity_id: str) -> str:
        seen: set[str] = set()
        current = entity_id
        while current not in seen:
            seen.add(current)
            link = self.session.scalar(
                select(EntityCanonicalLink).where(
                    EntityCanonicalLink.tenant_id == self.tenant_id,
                    EntityCanonicalLink.alias_entity_id == current,
                    EntityCanonicalLink.active.is_(True),
                )
            )
            if link is None:
                return current
            current = link.canonical_entity_id
        raise IdentityError("Canonical entity link cycle detected")

    def _assert_no_cycle(self, source_id: str, candidate_id: str) -> None:
        if self.canonical_entity_id(candidate_id) == source_id:
            raise IdentityError("Canonical entity link would create a cycle")

    def _trusted_conflicts(self, candidate: Entity, incoming: list[NormalizedIdentifier]) -> bool:
        existing = list(
            self.session.scalars(
                select(EntityIdentifier).where(
                    EntityIdentifier.tenant_id == self.tenant_id,
                    EntityIdentifier.entity_id == candidate.id,
                    EntityIdentifier.trusted_namespace.is_(True),
                    EntityIdentifier.review_status == ReviewStatus.VERIFIED,
                )
            )
        )
        values = {(item.namespace, item.normalized_value) for item in existing}
        namespaces = {item.namespace for item in existing}
        return any(
            item.trusted and item.namespace in namespaces and (item.namespace, item.normalized_value) not in values
            for item in incoming
        )

    def _score(
        self,
        source: Entity,
        candidate: Entity,
        source_identifiers: list[EntityIdentifier],
    ) -> tuple[float, str, list[dict[str, Any]]]:
        reasons: list[dict[str, Any]] = []
        score = 0.0
        candidate_identifiers = list(
            self.session.scalars(
                select(EntityIdentifier).where(
                    EntityIdentifier.tenant_id == self.tenant_id,
                    EntityIdentifier.entity_id == candidate.id,
                )
            )
        )
        candidate_values = {(item.namespace, item.normalized_value) for item in candidate_identifiers}
        exact = [item for item in source_identifiers if (item.namespace, item.normalized_value) in candidate_values]
        if any(item.trusted_namespace for item in exact):
            score += 0.75
            reasons.append({"code": "trusted_identifier_exact", "weight": 0.75})
        elif exact:
            score += 0.25
            reasons.append({"code": "local_identifier_exact", "weight": 0.25})
        if source.normalized_name == candidate.normalized_name:
            score += 0.55
            reasons.append({"code": "normalized_name_exact", "weight": 0.55})
        conflicts = self._trusted_conflicts(
            candidate,
            [
                NormalizedIdentifier(item.namespace, item.value, item.normalized_value, item.trusted_namespace)
                for item in source_identifiers
            ],
        )
        if conflicts:
            score = min(score, 0.60)
            reasons.append({"code": "trusted_identifier_conflict", "weight": -0.40})
        score = round(min(score, 1.0), 4)
        risk_tier = "high" if conflicts or not any(item.trusted_namespace for item in exact) else "medium"
        return score, risk_tier, reasons


def resolution_case_view(session: Session, case: EntityResolutionCase) -> dict[str, Any]:
    source = session.get(Entity, case.source_entity_id)
    candidate = session.get(Entity, case.candidate_entity_id)
    if source is None or candidate is None:
        raise IdentityError("Resolution case references an unavailable entity")
    return {
        "id": case.id,
        "source_entity_id": source.id,
        "source_entity_name": source.name,
        "candidate_entity_id": candidate.id,
        "candidate_entity_name": candidate.name,
        "entity_type": source.entity_type,
        "score": case.score,
        "risk_tier": case.risk_tier,
        "reasons": case.reasons,
        "status": case.status,
        "proposed_by": case.proposed_by,
        "reviewed_by_user_id": case.reviewed_by_user_id,
        "reviewed_at": case.reviewed_at,
        "review_notes": case.review_notes,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
    }
