from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from pharma_intel.chemistry.repository import FINGERPRINT_VERSION, ChemistryRepository
from pharma_intel.chemistry.standardization import ChemistryStandardizer
from pharma_intel.chemistry.types import ChemistrySearchResult, ChemistryValidationError, StandardizedStructure
from pharma_intel.db import set_tenant_context

MAX_INTERACTIVE_CHEMISTRY_RESULTS = 100


class ChemistryService:
    def __init__(
        self,
        session: Session,
        tenant_id: str,
        standardizer: ChemistryStandardizer | None = None,
        repository: ChemistryRepository | None = None,
    ) -> None:
        set_tenant_context(session, tenant_id)
        self.standardizer = standardizer or ChemistryStandardizer()
        self.repository = repository or ChemistryRepository(session, tenant_id)

    def standardize_for_storage(self, smiles: str) -> StandardizedStructure:
        return self.standardizer.standardize_smiles(smiles)

    def exact(self, smiles: str, limit: int = 20, offset: int = 0) -> ChemistrySearchResult:
        validated_limit = self._validate_limit(limit)
        query = self.standardizer.standardize_smiles(smiles)
        return ChemistrySearchResult(
            mode="exact",
            normalized_query=query.canonical_smiles,
            hits=self.repository.exact(query.canonical_smiles, validated_limit, offset),
            as_of=datetime.now(UTC),
            standardization_version=query.standardization_version,
        )

    def substructure(self, smarts: str, limit: int = 50, offset: int = 0) -> ChemistrySearchResult:
        validated_limit = self._validate_limit(limit)
        normalized_smarts = self.standardizer.normalize_smarts(smarts)
        return ChemistrySearchResult(
            mode="substructure",
            normalized_query=normalized_smarts,
            hits=self.repository.substructure(normalized_smarts, validated_limit, offset),
            as_of=datetime.now(UTC),
        )

    def similarity(
        self, smiles: str, threshold: float = 0.5, limit: int = 50, offset: int = 0
    ) -> ChemistrySearchResult:
        validated_limit = self._validate_limit(limit)
        if not 0.0 <= threshold <= 1.0:
            raise ChemistryValidationError(
                "invalid_similarity_threshold",
                "Similarity threshold must be between 0 and 1",
            )
        query = self.standardizer.standardize_smiles(smiles)
        return ChemistrySearchResult(
            mode="similarity",
            normalized_query=query.canonical_smiles,
            hits=self.repository.similarity(query.canonical_smiles, threshold, validated_limit, offset),
            as_of=datetime.now(UTC),
            standardization_version=query.standardization_version,
            fingerprint_version=FINGERPRINT_VERSION,
            similarity_threshold=threshold,
        )

    @staticmethod
    def _validate_limit(limit: int) -> int:
        if not 1 <= limit <= MAX_INTERACTIVE_CHEMISTRY_RESULTS:
            raise ChemistryValidationError(
                "invalid_result_limit",
                f"Interactive chemistry result limits must be between 1 and {MAX_INTERACTIVE_CHEMISTRY_RESULTS}",
            )
        return limit
