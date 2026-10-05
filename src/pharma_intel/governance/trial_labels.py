from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text

from pharma_intel.clinical_semantics import TRIAL_LABEL_PREDICATES
from pharma_intel.governance.contracts import GovernanceError
from pharma_intel.governance.fact_identity import _projection
from pharma_intel.governance.materialization_context import MaterializationContext
from pharma_intel.identity import normalize_name
from pharma_intel.models import DataSourceType, Entity, EntityIdentifier, EntityType, Relationship, StagedFact

_PROVIDER = "ClinicalTrials.gov"


def _label(context: MaterializationContext, kind: EntityType, name: str, staged: StagedFact) -> Entity:
    normalized = normalize_name(name)
    namespace = f"source_ctgov_{kind.value}_label"
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    if context.session.bind is not None and context.session.bind.dialect.name == "postgresql":
        context.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"{context.tenant_id}:{namespace}:{digest}"},
        )
    # This is a platform-derived provider label, NOT an externally issued ID.
    # Its namespace is deliberately untrusted by general identity resolution.
    # Only this official adapter may reuse an exact, typed, provider-scoped label.
    candidates = list(
        context.session.scalars(
            select(Entity)
            .join(EntityIdentifier, EntityIdentifier.entity_id == Entity.id)
            .where(
                Entity.tenant_id == context.tenant_id,
                Entity.entity_type == kind,
                EntityIdentifier.tenant_id == context.tenant_id,
                EntityIdentifier.namespace == namespace,
                EntityIdentifier.normalized_value == digest,
            )
            .limit(2)
        )
    )
    if len(candidates) > 1:
        raise GovernanceError("ClinicalTrials.gov label identity is ambiguous")
    if candidates:
        entity = candidates[0]
        if (
            entity.attributes.get("identity_scope") != "provider_label"
            or entity.attributes.get("label_provider") != _PROVIDER
        ):
            raise GovernanceError("ClinicalTrials.gov label identity has incompatible provenance")
        return entity
    entity = context._entity(
        {"entity_type": kind.value, "name": name, "external_ids": {namespace: digest}}, staged.source_document_id
    )
    entity.attributes = {
        **entity.attributes,
        "identity_scope": "provider_label",
        "label_provider": _PROVIDER,
        "identity_note": (
            "ClinicalTrials.gov研究条件名称，不代表获批适应症或本体标准化。"
            if kind == EntityType.DISEASE
            else "ClinicalTrials.gov申办方名称，不代表已核实的法律主体或企业集团归并。"
        ),
    }
    return entity


def materialize_trial_labels(
    context: MaterializationContext, trial: Entity, staged: StagedFact, payload: dict[str, Any]
) -> list[dict[str, str]]:
    if context._source_type_for_document(staged.source_document_id) != DataSourceType.CLINICALTRIALS_GOV:
        return []
    labels: dict[tuple[str, str], Entity] = {}
    for condition in payload.get("conditions") or []:
        name = str(condition).strip()
        if name:
            entity = _label(context, EntityType.DISEASE, name, staged)
            labels[("trial_studies_condition", entity.id)] = entity
    for sponsor in payload.get("sponsors") or []:
        name = str(sponsor.get("name") or "").strip()
        if name:
            entity = _label(context, EntityType.ORGANIZATION, name, staged)
            predicate = "trial_collaborator" if sponsor.get("role") == "collaborator" else "trial_lead_sponsor"
            labels[(predicate, entity.id)] = entity
    for relationship in context.session.scalars(
        select(Relationship).where(
            Relationship.tenant_id == context.tenant_id,
            Relationship.subject_id == trial.id,
            Relationship.predicate.in_(TRIAL_LABEL_PREDICATES),
            Relationship.valid_to.is_(None),
        )
    ):
        if (relationship.predicate, relationship.object_id) not in labels:
            relationship.valid_to = datetime.now(UTC)
    for (predicate, _identifier), entity in labels.items():
        context._relationship(trial, predicate, entity, staged)
    context.session.flush()
    return [_projection("entity", identifier) for identifier in sorted({entity.id for entity in labels.values()})]
