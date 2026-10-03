from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.contracts import GovernanceError, PreparedSegmentFact
from pharma_intel.governance.model_gateway import ModelGatewayError
from pharma_intel.governance.normalization import FactNormalizer
from pharma_intel.models import ExtractionRun, SourceVersion, StagedFact
from pharma_intel.object_store import ObjectStore


class AdapterContext(Protocol):
    session: Session
    tenant_id: str
    object_store: ObjectStore
    settings: Settings
    normalizer: FactNormalizer

    def _run_summary(self, run: ExtractionRun) -> dict[str, int | str]: ...
    def _apply_successful_version_state(self, version: SourceVersion, counts: Mapping[str, int | str]) -> None: ...
    def _record_failed_run(
        self,
        run: ExtractionRun,
        version: SourceVersion,
        exc: ModelGatewayError | GovernanceError,
        segment_audits: list[dict[str, Any]],
        input_tokens: int,
        output_tokens: int,
        estimated_cost: Decimal,
    ) -> None: ...
    def _stage_fact(
        self,
        run: ExtractionRun,
        version: SourceVersion,
        segment_fact: PreparedSegmentFact,
        *,
        trusted_structured: bool = False,
    ) -> StagedFact: ...
