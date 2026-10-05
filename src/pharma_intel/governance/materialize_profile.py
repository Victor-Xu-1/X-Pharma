from __future__ import annotations

import re
from typing import Any, cast

from sqlalchemy import select

from pharma_intel.governance.fact_identity import _projection
from pharma_intel.governance.materialization_context import MaterializationContext
from pharma_intel.identity import normalize_name
from pharma_intel.models import EntityAlias, OutboxEvent, StagedFact, TargetProfile


def materialize_target_profile(
    context: MaterializationContext, staged: StagedFact, payload: dict[str, Any]
) -> list[dict[str, str]]:
    subject = context._entity(cast(dict[str, Any], payload["subject"]), staged.source_document_id)
    profile = context.session.scalar(
        select(TargetProfile).where(TargetProfile.tenant_id == context.tenant_id, TargetProfile.entity_id == subject.id)
    )
    if profile is None:
        profile = TargetProfile(
            tenant_id=context.tenant_id, entity_id=subject.id, organism=str(payload.get("organism") or "Homo sapiens")
        )
        context.session.add(profile)
    for field in ("gene_symbol", "uniprot_accession", "target_class", "function_summary"):
        if payload.get(field) is not None:
            setattr(profile, field, payload[field])
    if payload.get("sequence") is not None:
        profile.sequence = re.sub(r"\s+", "", str(payload["sequence"])).upper()
    if payload.get("organism") is not None:
        profile.organism = str(payload["organism"])
    profile.source_document_id = staged.source_document_id
    # The accepted source's gene symbol is a name of this target, not a name of
    # its drugs. It must be projected through the existing alias authority.
    gene = str(payload.get("gene_symbol") or "").strip()
    if gene and normalize_name(gene) != subject.normalized_name:
        existing = context.session.scalar(
            select(EntityAlias.id).where(
                EntityAlias.tenant_id == context.tenant_id,
                EntityAlias.entity_id == subject.id,
                EntityAlias.normalized_alias == normalize_name(gene),
            )
        )
        if existing is None:
            context.session.add(
                EntityAlias(
                    tenant_id=context.tenant_id, entity_id=subject.id, alias=gene, normalized_alias=normalize_name(gene)
                )
            )
            context.session.add(
                OutboxEvent(
                    tenant_id=context.tenant_id,
                    aggregate_type="entity",
                    aggregate_id=subject.id,
                    event_type="canonical.entity.upserted",
                    payload={"entity_id": subject.id, "schema_version": 1},
                )
            )
    context.session.flush()
    return [_projection("target_profile", profile.id)]
