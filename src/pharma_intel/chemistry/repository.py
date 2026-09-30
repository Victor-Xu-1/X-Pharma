from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from pharma_intel.chemistry.types import ChemistryBackendUnavailable, ChemistrySearchHit

FINGERPRINT_VERSION = "morganbv-radius2-2048/rdkit-2026.03.3"

_EXACT_SQL = """
WITH query AS (
    SELECT mol_from_smiles(CAST(:canonical_smiles AS text)) AS mol
)
SELECT cs.id, cs.entity_id, entity.name AS entity_name, cs.canonical_smiles,
       cs.isomeric_smiles, cs.standard_inchi, cs.standard_inchi_key,
       cs.molecular_formula, cs.molecular_weight, cs.exact_mass,
       cs.structure_version, cs.standardization_version, cs.fingerprint_version,
       cs.updated_at, NULL::double precision AS similarity
FROM compound_structures AS cs
JOIN entities AS entity ON entity.id = cs.entity_id AND entity.tenant_id = cs.tenant_id
CROSS JOIN query
WHERE cs.tenant_id = :tenant_id AND cs.rdkit_mol = query.mol
ORDER BY cs.id
LIMIT :limit
OFFSET :offset
"""

_SUBSTRUCTURE_SQL = """
WITH query AS (
    SELECT qmol_from_smarts(CAST(:smarts AS cstring)) AS mol
)
SELECT cs.id, cs.entity_id, entity.name AS entity_name, cs.canonical_smiles,
       cs.isomeric_smiles, cs.standard_inchi, cs.standard_inchi_key,
       cs.molecular_formula, cs.molecular_weight, cs.exact_mass,
       cs.structure_version, cs.standardization_version, cs.fingerprint_version,
       cs.updated_at, NULL::double precision AS similarity
FROM compound_structures AS cs
JOIN entities AS entity ON entity.id = cs.entity_id AND entity.tenant_id = cs.tenant_id
CROSS JOIN query
WHERE cs.tenant_id = :tenant_id AND cs.rdkit_mol @> query.mol
ORDER BY cs.standard_inchi_key, cs.id
LIMIT :limit
OFFSET :offset
"""

_SIMILARITY_SQL = """
WITH query AS (
    SELECT morganbv_fp(mol_from_smiles(CAST(:canonical_smiles AS text)), 2) AS fp
)
SELECT cs.id, cs.entity_id, entity.name AS entity_name, cs.canonical_smiles,
       cs.isomeric_smiles, cs.standard_inchi, cs.standard_inchi_key,
       cs.molecular_formula, cs.molecular_weight, cs.exact_mass,
       cs.structure_version, cs.standardization_version, cs.fingerprint_version,
       cs.updated_at, tanimoto_sml(cs.morgan_bfp, query.fp) AS similarity
FROM compound_structures AS cs
JOIN entities AS entity ON entity.id = cs.entity_id AND entity.tenant_id = cs.tenant_id
CROSS JOIN query
WHERE cs.tenant_id = :tenant_id AND cs.morgan_bfp % query.fp
ORDER BY cs.morgan_bfp <%> query.fp, cs.id
LIMIT :limit
OFFSET :offset
"""


class ChemistryRepository:
    def __init__(self, session: Session, tenant_id: str) -> None:
        bind = session.get_bind()
        if bind.dialect.name != "postgresql":
            raise ChemistryBackendUnavailable("Chemical structure search requires PostgreSQL with the RDKit cartridge")
        self.session = session
        self.tenant_id = tenant_id

    def exact(self, canonical_smiles: str, limit: int, offset: int = 0) -> tuple[ChemistrySearchHit, ...]:
        statement = text(_EXACT_SQL)
        rows = self.session.execute(
            statement,
            {
                "canonical_smiles": canonical_smiles,
                "tenant_id": self.tenant_id,
                "limit": limit,
                "offset": offset,
            },
        ).mappings()
        return tuple(self._to_hit(row) for row in rows)

    def substructure(self, normalized_smarts: str, limit: int, offset: int = 0) -> tuple[ChemistrySearchHit, ...]:
        statement = text(_SUBSTRUCTURE_SQL)
        rows = self.session.execute(
            statement,
            {"smarts": normalized_smarts, "tenant_id": self.tenant_id, "limit": limit, "offset": offset},
        ).mappings()
        return tuple(self._to_hit(row) for row in rows)

    def similarity(
        self,
        canonical_smiles: str,
        threshold: float,
        limit: int,
        offset: int = 0,
    ) -> tuple[ChemistrySearchHit, ...]:
        self.session.execute(
            text("SELECT set_config('rdkit.tanimoto_threshold', :threshold, true)"),
            {"threshold": format(threshold, ".8f")},
        )
        statement = text(_SIMILARITY_SQL)
        rows = self.session.execute(
            statement,
            {
                "canonical_smiles": canonical_smiles,
                "tenant_id": self.tenant_id,
                "limit": limit,
                "offset": offset,
            },
        ).mappings()
        return tuple(self._to_hit(row) for row in rows)

    @staticmethod
    def _to_hit(row: RowMapping) -> ChemistrySearchHit:
        similarity = row["similarity"]
        updated_at = row["updated_at"]
        if not isinstance(updated_at, datetime):
            raise ChemistryBackendUnavailable("Chemical structure result has an invalid update timestamp")
        return ChemistrySearchHit(
            id=str(row["id"]),
            entity_id=str(row["entity_id"]),
            entity_name=str(row["entity_name"]),
            canonical_smiles=str(row["canonical_smiles"]),
            isomeric_smiles=str(row["isomeric_smiles"]) if row["isomeric_smiles"] is not None else None,
            standard_inchi=str(row["standard_inchi"]) if row["standard_inchi"] is not None else None,
            standard_inchi_key=str(row["standard_inchi_key"]),
            molecular_formula=str(row["molecular_formula"]) if row["molecular_formula"] is not None else None,
            molecular_weight=float(row["molecular_weight"]) if row["molecular_weight"] is not None else None,
            exact_mass=float(row["exact_mass"]) if row["exact_mass"] is not None else None,
            structure_version=str(row["structure_version"]),
            standardization_version=str(row["standardization_version"]),
            fingerprint_version=str(row["fingerprint_version"]),
            updated_at=updated_at,
            similarity=float(similarity) if similarity is not None else None,
        )
