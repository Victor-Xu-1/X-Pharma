from __future__ import annotations

from decimal import Decimal
from typing import Any

from pharma_intel.config import Settings
from pharma_intel.governance.contracts import MILLION_TOKENS, SCHEMA_VERSION
from pharma_intel.governance.policy import governance_policy_sha256


def _model_cost(
    input_tokens: int,
    output_tokens: int,
    input_rate: Decimal,
    output_rate: Decimal,
) -> Decimal:
    return (Decimal(input_tokens) * input_rate + Decimal(output_tokens) * output_rate) / MILLION_TOKENS


def _extraction_audit(
    segment_audits: list[dict[str, Any]],
    settings: Settings,
    estimated_cost: Decimal,
    *,
    policy_sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "governance_schema_version": SCHEMA_VERSION,
        "policy_sha256": policy_sha256 or governance_policy_sha256(settings),
        "segments": segment_audits,
        "budget": {
            "max_document_chars": settings.ai_max_document_chars,
            "max_segments_per_document": settings.ai_max_segments_per_document,
            "max_input_tokens": settings.ai_max_document_input_tokens,
            "max_output_tokens": settings.ai_max_document_output_tokens,
            "max_output_tokens_per_segment": settings.ai_max_output_tokens_per_segment,
            "max_response_bytes": settings.ai_max_response_bytes,
            "input_cost_per_million_tokens": format(settings.ai_input_cost_per_million_tokens, "f"),
            "output_cost_per_million_tokens": format(settings.ai_output_cost_per_million_tokens, "f"),
            "max_document_cost": format(settings.ai_max_document_cost, "f"),
            "estimated_cost": format(estimated_cost, "f"),
        },
    }
