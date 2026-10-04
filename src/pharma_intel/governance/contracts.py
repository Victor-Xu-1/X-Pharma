from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pharma_intel.governance.normalization import PreparedFact

SCHEMA_NAME = "pharma_document_facts"
SCHEMA_VERSION = "2.13.0"
POLICY_SCHEMA = "pharma.governance-policy.v1"
OFFICIAL_SOURCE_UPDATE_POLICY = "same-asset-monotonic-v1"
HIGH_RISK_FACT_KINDS = frozenset(
    {
        "activity",
        "deal",
        "epidemiology",
        "news",
        "patent",
        "program",
        "regulatory",
        "structure",
        "target_evidence",
        "trial",
    }
)
MILLION_TOKENS = Decimal("1000000")
CLINICALTRIALS_PROFILE_INPUT_STRING_CHARS = 1200


class GovernanceError(RuntimeError):
    pass


class GovernanceBudgetError(GovernanceError):
    pass


@dataclass(frozen=True)
class DocumentSegment:
    text: str
    start_char: int
    end_char: int


@dataclass(frozen=True)
class SourceQuoteMatch:
    locator: str
    quote: str


@dataclass(frozen=True)
class PreparedSegmentFact:
    prepared: PreparedFact
    segment_index: int
    segment_sha256: str
    quote_verified: bool
    source_locator: str | None
    source_quote: str | None
