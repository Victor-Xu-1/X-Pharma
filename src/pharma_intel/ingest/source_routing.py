from __future__ import annotations

from typing import Any

from pharma_intel.ingest.chembl import ChemblRoutingRule
from pharma_intel.ingest.clinicaltrials import ClinicalTrialsGovRoutingRule
from pharma_intel.ingest.pubmed import PubMedRoutingRule
from pharma_intel.models import DataSourceType


def canonical_routing_rules(source_type: DataSourceType, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if source_type == DataSourceType.CLINICALTRIALS_GOV:
        return [ClinicalTrialsGovRoutingRule.model_validate(rule).document() for rule in rules]
    if source_type == DataSourceType.CHEMBL:
        return [ChemblRoutingRule.model_validate(rule).document() for rule in rules]
    if source_type == DataSourceType.PUBMED:
        return [PubMedRoutingRule.model_validate(rule).model_dump(mode="json") for rule in rules]
    return rules


def routing_scope_identity(source_type: DataSourceType, rules: list[dict[str, Any]]) -> object:
    canonical = canonical_routing_rules(source_type, rules)
    if len(canonical) != 1:
        return canonical
    keys = {
        DataSourceType.CLINICALTRIALS_GOV: ("query_term", "start_date"),
        DataSourceType.PUBMED: ("query_term", "include_abstract"),
        DataSourceType.CHEMBL: ("target_chembl_id",),
    }.get(source_type)
    if keys is None:
        return canonical
    return {key: canonical[0].get(key) for key in keys}
