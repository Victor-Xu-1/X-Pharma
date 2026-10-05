from __future__ import annotations

from sqlalchemy import select, true, union
from sqlalchemy.sql.selectable import Subquery

from pharma_intel.intelligence.clinical_role_policy import asserted_trial_role
from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.scope import _published_entity_exists
from pharma_intel.models import (
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    Entity,
    EntityType,
    Relationship,
    ReviewStatus,
)


def trial_drug_bindings(context: QueryContext) -> Subquery:
    """Registered drug associations and asserted roles share one read authority.

    Generic links do not acquire a main/combination role. Distinct union keeps
    trial counts consistent when the same association also has a curated role.
    """
    roles = (
        select(
            ClinicalTrialEntityRole.trial_id.label("trial_id"),
            ClinicalTrialEntityRole.entity_id.label("drug_entity_id"),
        )
        .join(ClinicalTrialProfile, ClinicalTrialProfile.id == ClinicalTrialEntityRole.trial_id)
        .join(
            Entity,
            Entity.id == ClinicalTrialEntityRole.entity_id,
        )
        .where(
            ClinicalTrialEntityRole.tenant_id == context.tenant_id,
            ClinicalTrialProfile.tenant_id == context.tenant_id,
            Entity.tenant_id == context.tenant_id,
            Entity.entity_type == EntityType.DRUG,
            ClinicalTrialEntityRole.role.in_(("investigational_drug", "combination_drug")),
            asserted_trial_role(context),
            _published_entity_exists(context, Entity.id),
            _published_entity_exists(context, ClinicalTrialProfile.entity_id),
        )
    )
    registered = (
        select(
            ClinicalTrialProfile.id.label("trial_id"),
            Relationship.object_id.label("drug_entity_id"),
        )
        .join(Relationship, Relationship.subject_id == ClinicalTrialProfile.entity_id)
        .join(
            Entity,
            Entity.id == Relationship.object_id,
        )
        .where(
            ClinicalTrialProfile.tenant_id == context.tenant_id,
            Relationship.tenant_id == context.tenant_id,
            Entity.tenant_id == context.tenant_id,
            Entity.entity_type == EntityType.DRUG,
            Relationship.predicate == "trial_links_entity",
            Relationship.valid_to.is_(None),
            Relationship.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
            _published_entity_exists(context, Entity.id),
            _published_entity_exists(context, ClinicalTrialProfile.entity_id),
        )
    )
    return union(roles, registered).subquery("clinical_trial_drug_bindings")
