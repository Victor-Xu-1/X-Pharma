from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.orm import Session

from pharma_intel.governance.normalization import FactNormalizer
from pharma_intel.models import DataSourceType, Entity, StagedFact


class MaterializationContext(Protocol):
    session: Session
    tenant_id: str
    normalizer: FactNormalizer

    def _entity(self, reference: dict[str, Any], source_document_id: str | None) -> Entity: ...
    def _optional_entity(self, value: Any, source_document_id: str | None) -> Entity | None: ...
    def _relationship(self, subject: Entity, predicate: str, object_entity: Entity, staged: StagedFact) -> None: ...
    def _defer_projection(self, staged: StagedFact, code: str, message: str) -> None: ...
    def _source_type_for_document(self, source_document_id: str | None) -> DataSourceType | None: ...
