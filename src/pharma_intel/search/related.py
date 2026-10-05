from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pharma_intel.clinical_semantics import TRIAL_LABEL_PREDICATES
from pharma_intel.identity import normalize_name
from pharma_intel.models import (
    Entity,
    EntityAlias,
    EntityIdentifier,
    EvidenceClaim,
    GovernanceStatus,
    Relationship,
    ReviewStatus,
    SourceDocument,
    StagedFact,
)
from pharma_intel.search.contracts import EntitySearchMatch

_ANCHOR_LIMIT = 16
_EDGE_LIMIT = 1000
_PREDICATES = frozenset(
    {
        "has_target",
        "developed_for",
        "originates",
        "develops",
        "collaborates_on",
        "trial_links_entity",
        *TRIAL_LABEL_PREDICATES,
        "patent_links_entity",
        "deal_links_entity",
    }
)


@dataclass(frozen=True)
class RelatedEntities:
    matches: dict[str, EntitySearchMatch] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


def related_entities(session: Session, tenant_id: str, query: str) -> RelatedEntities:
    """One evidence-backed hop from exact identities, never inferred identity or an unbounded graph."""
    normalized = normalize_name(query)
    alias = (
        select(EntityAlias.id)
        .where(
            EntityAlias.tenant_id == tenant_id,
            EntityAlias.entity_id == Entity.id,
            EntityAlias.normalized_alias == normalized,
        )
        .exists()
    )
    identifier = (
        select(EntityIdentifier.id)
        .where(
            EntityIdentifier.tenant_id == tenant_id,
            EntityIdentifier.entity_id == Entity.id,
            func.lower(EntityIdentifier.normalized_value) == normalized,
            EntityIdentifier.review_status == ReviewStatus.VERIFIED,
        )
        .exists()
    )
    anchors = list(
        session.scalars(
            select(Entity)
            .where(
                Entity.tenant_id == tenant_id,
                Entity.review_status == ReviewStatus.VERIFIED,
                or_(Entity.normalized_name == normalized, alias, identifier),
            )
            .order_by(Entity.id)
            .limit(_ANCHOR_LIMIT + 1)
        )
    )
    if len(anchors) > _ANCHOR_LIMIT:
        return RelatedEntities(warnings=("同名对象过多，未扩展关联；请使用稳定标识缩小查询。",))
    if not anchors:
        return RelatedEntities()
    by_id = {entity.id: entity for entity in anchors}
    edges = list(
        session.scalars(
            select(Relationship)
            .where(
                Relationship.tenant_id == tenant_id,
                Relationship.review_status == ReviewStatus.VERIFIED,
                Relationship.valid_to.is_(None),
                Relationship.predicate.in_(_PREDICATES),
                or_(Relationship.subject_id.in_(by_id), Relationship.object_id.in_(by_id)),
            )
            .order_by(Relationship.id)
            .limit(_EDGE_LIMIT + 1)
        )
    )
    if len(edges) > _EDGE_LIMIT:
        return RelatedEntities(warnings=("关联超过1000条安全上限，未扩展关联；请进入对象档案按领域筛选。",))
    fact_ids = {
        str(item.get("staged_fact_id"))
        for edge in edges
        for item in edge.attributes.get("evidence", [])
        if isinstance(item, dict) and item.get("staged_fact_id")
    }
    proof: dict[str, str] = (
        {
            fact_id: source_uri
            for fact_id, source_uri in session.execute(
                select(StagedFact.id, SourceDocument.source_uri)
                .join(
                    EvidenceClaim,
                    EvidenceClaim.id == StagedFact.published_resource_id,
                )
                .join(SourceDocument, SourceDocument.id == StagedFact.source_document_id)
                .where(
                    StagedFact.tenant_id == tenant_id,
                    StagedFact.id.in_(fact_ids),
                    StagedFact.status == GovernanceStatus.PUBLISHED,
                    EvidenceClaim.tenant_id == tenant_id,
                    EvidenceClaim.review_status == ReviewStatus.VERIFIED,
                    SourceDocument.tenant_id == tenant_id,
                )
            ).all()
        }
        if fact_ids
        else {}
    )
    peers = {edge.object_id if edge.subject_id in by_id else edge.subject_id for edge in edges} - set(by_id)
    visible_ids = (
        set(
            session.scalars(
                select(Entity.id).where(
                    Entity.tenant_id == tenant_id,
                    Entity.id.in_(peers),
                    Entity.review_status == ReviewStatus.VERIFIED,
                )
            )
        )
        if peers
        else set()
    )
    matches: dict[str, EntitySearchMatch] = {}
    for edge in edges:
        anchor_id = edge.subject_id if edge.subject_id in by_id else edge.object_id
        peer_id = edge.object_id if edge.subject_id in by_id else edge.subject_id
        if peer_id not in visible_ids or peer_id in matches:
            continue
        uri = next(
            (
                proof[str(item["staged_fact_id"])]
                for item in edge.attributes.get("evidence", [])
                if isinstance(item, dict) and str(item.get("staged_fact_id")) in proof
            ),
            None,
        )
        if uri is not None:
            matches[peer_id] = EntitySearchMatch(
                "relationship",
                "related",
                by_id[anchor_id].name,
                via_entity_id=anchor_id,
                predicate=edge.predicate,
                source_uri=_public_uri(uri),
            )
    return RelatedEntities(matches)


def _public_uri(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.hostname
        not in {
            "www.ebi.ac.uk",
            "clinicaltrials.gov",
            "pubmed.ncbi.nlm.nih.gov",
            "europepmc.org",
            "pubchem.ncbi.nlm.nih.gov",
        }
        or parsed.username
        or parsed.password
        or port
        or set(parse_qs(parsed.query)) - {"mec_id"}
    ):
        return None
    return value
