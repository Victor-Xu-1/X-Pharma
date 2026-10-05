"""Registry labels are associations, not approved indications or legal identities."""

TRIAL_LABEL_PREDICATES = frozenset({"trial_studies_condition", "trial_lead_sponsor", "trial_collaborator"})
TRIAL_ENTITY_LINK_PREDICATES = frozenset({"trial_links_entity", *TRIAL_LABEL_PREDICATES})
