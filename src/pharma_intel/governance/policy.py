from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

from pharma_intel.chemistry.standardization import STANDARDIZATION_VERSION
from pharma_intel.config import Settings
from pharma_intel.governance.contracts import HIGH_RISK_FACT_KINDS, POLICY_SCHEMA, SCHEMA_NAME, SCHEMA_VERSION
from pharma_intel.governance.fact_identity import _hash_json
from pharma_intel.governance.model_gateway import extraction_schema, extraction_system_prompt


def governance_policy_manifest(settings: Settings) -> dict[str, Any]:
    prompt = extraction_system_prompt(
        settings.ai_max_facts_per_segment,
        settings.ai_max_model_string_chars,
    )
    schema_parameters = (
        settings.ai_max_facts_per_segment,
        settings.ai_max_model_string_chars,
        settings.ai_max_model_collection_items,
    )
    schemas = {
        "default_sha256": _hash_json(extraction_schema(*schema_parameters, allow_structure=False)),
        "structure_sha256": _hash_json(extraction_schema(*schema_parameters, allow_structure=True)),
    }
    clinicaltrials_fact_kinds = frozenset({"trial"})
    clinicaltrials_prompt = extraction_system_prompt(
        1,
        settings.ai_max_model_string_chars,
        fact_kind_allowlist=clinicaltrials_fact_kinds,
        source_profile="clinicaltrials_gov",
    )
    clinicaltrials_schema = extraction_schema(
        1,
        settings.ai_max_model_string_chars,
        settings.ai_max_model_collection_items,
        fact_kind_allowlist=clinicaltrials_fact_kinds,
    )
    pubmed_fact_kinds = frozenset({"claim"})
    pubmed_max_facts = min(5, settings.ai_max_facts_per_segment)
    pubmed_prompt = extraction_system_prompt(
        pubmed_max_facts,
        settings.ai_max_model_string_chars,
        fact_kind_allowlist=pubmed_fact_kinds,
        source_profile="pubmed",
    )
    pubmed_schema = extraction_schema(
        pubmed_max_facts,
        settings.ai_max_model_string_chars,
        settings.ai_max_model_collection_items,
        fact_kind_allowlist=pubmed_fact_kinds,
    )
    return {
        "schema": POLICY_SCHEMA,
        "governance_schema_name": SCHEMA_NAME,
        "governance_schema_version": SCHEMA_VERSION,
        "normalization_policy": STANDARDIZATION_VERSION,
        "model_provider": "openai-compatible",
        "model_name": settings.ai_model,
        "model_endpoint_sha256": hashlib.sha256(settings.ai_base_url.strip().rstrip("/").encode("utf-8")).hexdigest(),
        "allowed_response_models": sorted(settings.ai_allowed_response_models),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "response_schemas": schemas,
        "source_profiles": {
            "clinicaltrials_gov": {
                "prompt_sha256": hashlib.sha256(clinicaltrials_prompt.encode("utf-8")).hexdigest(),
                "response_schema_sha256": _hash_json(clinicaltrials_schema),
                "max_facts": 1,
            },
            "pubmed": {
                "prompt_sha256": hashlib.sha256(pubmed_prompt.encode("utf-8")).hexdigest(),
                "response_schema_sha256": _hash_json(pubmed_schema),
                "max_facts": pubmed_max_facts,
            },
        },
        "limits": {
            "max_input_chars": settings.ai_max_input_chars,
            "max_document_chars": settings.ai_max_document_chars,
            "max_segments_per_document": settings.ai_max_segments_per_document,
            "max_facts_per_segment": settings.ai_max_facts_per_segment,
            "max_model_string_chars": settings.ai_max_model_string_chars,
            "max_model_collection_items": settings.ai_max_model_collection_items,
            "max_output_tokens_per_segment": settings.ai_max_output_tokens_per_segment,
            "max_document_input_tokens": settings.ai_max_document_input_tokens,
            "max_document_output_tokens": settings.ai_max_document_output_tokens,
            "max_response_bytes": settings.ai_max_response_bytes,
        },
        "accounting": {
            "require_usage_metadata": settings.ai_require_usage_metadata,
            "require_provider_request_id": settings.ai_require_provider_request_id,
            "input_cost_per_million_tokens": format(settings.ai_input_cost_per_million_tokens, "f"),
            "output_cost_per_million_tokens": format(settings.ai_output_cost_per_million_tokens, "f"),
            "max_document_cost": format(settings.ai_max_document_cost, "f"),
        },
        "publication": {
            "auto_publish_threshold": format(Decimal(str(settings.ai_auto_publish_threshold)), "f"),
            "auto_publish_fact_kinds": sorted(settings.ai_auto_publish_fact_kinds),
            "high_risk_fact_kinds": sorted(HIGH_RISK_FACT_KINDS),
        },
    }


def governance_policy_sha256(settings: Settings) -> str:
    return _hash_json(governance_policy_manifest(settings))
