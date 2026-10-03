from __future__ import annotations

BROWSER_ACCEPTANCE_SCHEMA = "pharma.browser-acceptance.v9"


BROWSER_ACCEPTANCE_REPORT = "report.json"


ENTRY_CONSISTENCY_SCHEMA = "pharma.entry-consistency-acceptance.v1"


ENTRY_CONSISTENCY_REPORT = "report.json"


ENTRY_CONSISTENCY_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "generated_at",
        "status",
        "environment",
        "production_claim",
        "credentials_recorded",
        "entity_id",
        "canonical_entity_sha256",
        "fields_compared",
        "web_operations",
        "mcp_tools",
        "mcp_protocol_version",
        "mcp_billed_calls",
        "unique_settlements",
        "same_tenant_fixture",
        "same_filtered_facts",
        "temporary_accounts_after",
        "temporary_entities_after",
    }
)


ENTRY_CONSISTENCY_ENTITY_FIELDS = (
    "id",
    "entity_type",
    "name",
    "description",
    "external_ids",
    "attributes",
    "review_status",
    "canonical_entity_id",
    "identity_identifiers",
    "created_at",
    "updated_at",
)


BROWSER_ACCEPTANCE_SCENARIOS = frozenset(
    {
        "accessibility",
        "authenticated_navigation",
        "billing_dispute",
        "browser_quality",
        "web_vitals_rum",
        "chemistry",
        "chemistry_real_api",
        "comparison_export",
        "data_lifecycle",
        "domain_export",
        "result_pagination",
        "result_to_comparison",
        "cross_page_comparison",
        "deal_entity_query",
        "deal_asset_attribute_query",
        "deal_asset_multiselect_query",
        "deal_full_result_landscape",
        "deal_asset_correctness",
        "patent_result_correctness",
        "enterprise_administration",
        "researcher_review",
        "environment_management",
        "external_login",
        "internal_login",
        "internal_workbench",
        "ingestion_replay",
        "loading_empty_error_recovery",
        "master_data_rollback",
        "monitoring",
        "permission_boundary",
        "real_permission_boundary",
        "real_target_dossier",
        "pipeline_intelligence",
        "pipeline_cross_domain_signals",
        "pipeline_cross_domain_navigation",
        "pipeline_dense_results",
        "pipeline_relationship_correctness",
        "clinical_full_result_landscape",
        "clinical_result_dense_fields",
        "clinical_normalized_drug_or",
        "clinical_role_correctness",
        "clinical_linked_program_correctness",
        "publication_governance",
        "public_login",
        "quality_operations",
        "quarantine_governance",
        "reflow_keyboard",
        "regulatory_intelligence",
        "regulatory_result_correctness",
        "regulatory_subscription",
        "saved_search_maintenance",
        "epidemiology_news_subscription",
        "news_result_correctness",
        "epidemiology_trend_correctness",
        "research_workbench",
        "initial_load_boundary",
        "session_recovery",
        "stable_deep_link",
        "table_preference_server_continuity",
        "query_cancellation",
        "professional_query_state_matrix",
        "professional_error_permission_matrix",
        "explorer_quick_detail_continuity",
        "knowledge_research_continuity",
        "evidence_research_continuity",
        "workspace_isolation",
    }
)
