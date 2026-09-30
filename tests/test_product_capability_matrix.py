from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

EXPECTED_DOMAINS = {
    "global_search",
    "drug_pipeline",
    "target_translation",
    "chemistry_activity",
    "clinical_trials_results",
    "patent_intelligence",
    "deals_companies",
    "regulatory_safety",
    "epidemiology_landscape",
    "news_conference_events",
    "knowledge_research_content",
    "personal_team_productivity",
}

EXPECTED_INTERNAL_DOMAINS = {
    "sources_and_licensing",
    "automatic_ingestion_orchestration",
    "file_and_parsing_governance",
    "ai_governance",
    "master_data_governance",
    "publishing_and_projections",
    "data_quality_and_monitoring",
    "enterprise_administration",
    "commercial_operations",
    "platform_operations",
}


def test_external_workbench_capability_matrix_is_schema_valid_and_complete() -> None:
    root = Path(__file__).parents[1]
    schema = json.loads(
        (root / "deploy" / "release" / "external-workbench-capability-matrix.schema.json").read_text(encoding="utf-8")
    )
    matrix = json.loads(
        (root / "deploy" / "release" / "external-workbench-capability-matrix.json").read_text(encoding="utf-8")
    )

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(matrix)
    domains = matrix["domains"]
    experience_criteria = matrix["experience_gate"]["criteria"]
    assert {domain["id"] for domain in domains} == EXPECTED_DOMAINS
    assert len(experience_criteria) == 8
    assert len({criterion["id"] for criterion in experience_criteria}) == 8
    assert len({capability["id"] for domain in domains for capability in domain["capabilities"]}) == sum(
        len(domain["capabilities"]) for domain in domains
    )
    for domain in domains:
        assert {capability["priority"] for capability in domain["capabilities"]} <= {"P0", "P1"}
        if domain["status"] == "implemented":
            assert all(capability["status"] == "implemented" for capability in domain["capabilities"])
        else:
            assert domain["remaining_gaps"], domain["id"]
        for capability in domain["capabilities"]:
            if capability["status"] == "implemented":
                assert capability["evidence"], capability["id"]
            for evidence in capability["evidence"]:
                assert (root / evidence).exists(), evidence
    for criterion in experience_criteria:
        if criterion["status"] == "implemented":
            assert criterion["evidence"], criterion["id"]
        else:
            assert criterion["remaining_gaps"], criterion["id"]
        for evidence in criterion["evidence"]:
            assert (root / evidence).exists(), evidence


def test_capability_matrix_does_not_overclaim_commercial_completion() -> None:
    root = Path(__file__).parents[1]
    matrix = json.loads(
        (root / "deploy" / "release" / "external-workbench-capability-matrix.json").read_text(encoding="utf-8")
    )

    assert any(domain["status"] != "implemented" for domain in matrix["domains"])
    assert any(criterion["status"] != "implemented" for criterion in matrix["experience_gate"]["criteria"])
    assert matrix["completion_rule"]["requires_real_data"] is True
    assert matrix["completion_rule"]["requires_business_uat"] is True


def test_internal_workbench_capability_matrix_is_schema_valid_complete_and_honest() -> None:
    root = Path(__file__).parents[1]
    schema = json.loads(
        (root / "deploy" / "release" / "internal-workbench-capability-matrix.schema.json").read_text(encoding="utf-8")
    )
    matrix = json.loads(
        (root / "deploy" / "release" / "internal-workbench-capability-matrix.json").read_text(encoding="utf-8")
    )

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(matrix)
    domains = matrix["domains"]
    assert {domain["id"] for domain in domains} == EXPECTED_INTERNAL_DOMAINS
    capabilities = [capability for domain in domains for capability in domain["capabilities"]]
    assert len({capability["id"] for capability in capabilities}) == len(capabilities)
    assert all(capability["status"] == "implemented" for capability in capabilities)
    assert all(domain["status"] == "partial" for domain in domains)
    assert all(domain["remaining_gaps"] for domain in domains if domain["status"] != "implemented")
    for capability in capabilities:
        if capability["status"] != "not_started":
            assert capability["evidence"], capability["id"]
        for evidence in capability["evidence"]:
            assert (root / evidence).exists(), evidence
    assert matrix["completion_rule"]["requires_real_sources"] is True
    assert matrix["completion_rule"]["requires_operator_uat"] is True
    assert matrix["completion_rule"]["requires_no_cli_standard_operations"] is True
