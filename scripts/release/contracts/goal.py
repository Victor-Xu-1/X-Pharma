from __future__ import annotations

import re

GOAL_COMPLETION_MATRIX_SCHEMA = "pharma.goal-completion-matrix.v1"


GOAL_COMPLETION_AUDIT_SCHEMA = "pharma.goal-completion-audit.v1"


GOAL_DOCUMENT_VERSION = "1.9.9"


GOAL_REQUIREMENT_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]+\.[a-z][a-z0-9_]+")


GOAL_MATRIX_FIELDS = frozenset(
    {"schema", "schema_version", "goal_document_id", "goal_version", "section", "requirements"}
)


GOAL_REQUIREMENT_FIELDS = frozenset(
    {
        "id",
        "ordinal",
        "group",
        "title",
        "baseline_categories",
        "production_categories",
        "requires_release_security",
        "requires_signed_git_tag",
        "requires_bundle_signature",
    }
)


GOAL_SECTION_19_REQUIREMENTS = (
    ("product_data.capability_uat", "product_data"),
    ("product_data.internal_operations", "product_data"),
    ("product_data.licensed_coverage", "product_data"),
    ("product_data.automatic_source_lifecycle", "product_data"),
    ("product_data.cross_entry_traceability", "product_data"),
    ("human_agent.browser_workflows", "human_agent"),
    ("human_agent.workbench_isolation", "human_agent"),
    ("human_agent.remote_mcp_gateway", "human_agent"),
    ("human_agent.mcp_interoperability", "human_agent"),
    ("human_agent.financial_traceability", "human_agent"),
    ("human_agent.anti_extraction", "human_agent"),
    ("human_agent.real_target_cross_domain", "human_agent"),
    ("human_agent.web_mcp_consistency", "human_agent"),
    ("security.external_services", "security_reliability_operations"),
    ("security.approved_capacity", "security_reliability_operations"),
    ("security.penetration_supply_chain", "security_reliability_operations"),
    ("security.risk_billing_drills", "security_reliability_operations"),
    ("security.recovery_rpo_rto", "security_reliability_operations"),
    ("security.operating_model", "security_reliability_operations"),
    ("engineering.production_topology", "engineering_delivery"),
    ("engineering.clean_clone_lifecycle", "engineering_delivery"),
    ("engineering.contract_consistency", "engineering_delivery"),
    ("engineering.release_evidence_bundle", "engineering_delivery"),
    ("engineering.repository_hygiene", "engineering_delivery"),
)
