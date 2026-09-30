from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pharma_intel.chemistry import ChemistryService
from pharma_intel.db import set_tenant_context
from tests.support.postgres_safety import require_disposable_postgres_url, require_same_database


@pytest.mark.integration
def test_rdkit_materialization_indexes_and_signed_tenant_rls() -> None:
    admin_url = os.getenv("TEST_CHEMISTRY_ADMIN_DATABASE_URL")
    runtime_url = os.getenv("TEST_CHEMISTRY_RUNTIME_DATABASE_URL")
    if not admin_url or not runtime_url:
        pytest.skip("TEST_CHEMISTRY_ADMIN_DATABASE_URL and TEST_CHEMISTRY_RUNTIME_DATABASE_URL are required")
    require_disposable_postgres_url(admin_url, "TEST_CHEMISTRY_ADMIN_DATABASE_URL")
    require_disposable_postgres_url(runtime_url, "TEST_CHEMISTRY_RUNTIME_DATABASE_URL")
    require_same_database(
        admin_url,
        runtime_url,
        "TEST_CHEMISTRY_ADMIN_DATABASE_URL",
        "TEST_CHEMISTRY_RUNTIME_DATABASE_URL",
    )

    admin_engine = create_engine(admin_url, pool_pre_ping=True)
    runtime_engine = create_engine(runtime_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    other_tenant_id = str(uuid.uuid4())
    entity_id = str(uuid.uuid4())
    paracetamol_entity_id = str(uuid.uuid4())
    caffeine_entity_id = str(uuid.uuid4())
    other_entity_id = str(uuid.uuid4())
    invalid_entity_id = str(uuid.uuid4())

    with admin_engine.begin() as connection:
        extension = connection.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'rdkit'")).scalar_one()
        assert extension == "4.8.0"
        connection.execute(
            text(
                "INSERT INTO tenants (id, slug, name, active, created_at, updated_at) VALUES "
                "(:id, :slug, 'Chemistry Test', true, now(), now()), "
                "(:other_id, :other_slug, 'Other Chemistry Test', true, now(), now())"
            ),
            {
                "id": tenant_id,
                "slug": f"chem-{tenant_id}",
                "other_id": other_tenant_id,
                "other_slug": f"chem-{other_tenant_id}",
            },
        )
        entity_parameters = [
            {"id": entity_id, "tenant_id": tenant_id, "name": "Aspirin", "normalized": f"aspirin-{entity_id}"},
            {
                "id": paracetamol_entity_id,
                "tenant_id": tenant_id,
                "name": "Paracetamol",
                "normalized": f"paracetamol-{paracetamol_entity_id}",
            },
            {
                "id": caffeine_entity_id,
                "tenant_id": tenant_id,
                "name": "Caffeine",
                "normalized": f"caffeine-{caffeine_entity_id}",
            },
            {
                "id": other_entity_id,
                "tenant_id": other_tenant_id,
                "name": "Ibuprofen Other Tenant",
                "normalized": f"ibuprofen-{other_entity_id}",
            },
            {
                "id": invalid_entity_id,
                "tenant_id": tenant_id,
                "name": "Invalid Molecule",
                "normalized": f"invalid-{invalid_entity_id}",
            },
        ]
        for parameters in entity_parameters:
            connection.execute(
                text(
                    "INSERT INTO entities "
                    "(id, tenant_id, entity_type, name, normalized_name, external_ids, attributes, review_status, "
                    "created_at, updated_at) VALUES "
                    "(:id, :tenant_id, 'DRUG', :name, :normalized, '{}'::json, '{}'::json, 'VERIFIED', now(), now())"
                ),
                parameters,
            )
        structure_parameters = [
            {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "entity_id": entity_id,
                "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                "inchi_key": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
            },
            {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "entity_id": paracetamol_entity_id,
                "smiles": "CC(=O)NC1=CC=C(O)C=C1",
                "inchi_key": "RZVAJINKPMORJF-UHFFFAOYSA-N",
            },
            {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "entity_id": caffeine_entity_id,
                "smiles": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
                "inchi_key": "RYYVLZVUVIJVGH-UHFFFAOYSA-N",
            },
            {
                "id": str(uuid.uuid4()),
                "tenant_id": other_tenant_id,
                "entity_id": other_entity_id,
                "smiles": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
                "inchi_key": "HEFNNWSXXWATRW-UHFFFAOYSA-N",
            },
        ]
        for parameters in structure_parameters:
            connection.execute(
                text(
                    "INSERT INTO compound_structures "
                    "(id, tenant_id, entity_id, canonical_smiles, standard_inchi_key, structure_version, "
                    "created_at, updated_at) VALUES "
                    "(:id, :tenant_id, :entity_id, :smiles, :inchi_key, 'test-source/v1', now(), now())"
                ),
                parameters,
            )

    with admin_engine.connect() as connection:
        materialized = connection.execute(
            text(
                "SELECT mol_to_smiles(rdkit_mol), morgan_bfp IS NOT NULL, fingerprint_version "
                "FROM compound_structures WHERE entity_id = :entity_id"
            ),
            {"entity_id": entity_id},
        ).one()
        assert materialized[0]
        assert materialized[1] is True
        assert materialized[2] == "morganbv-radius2-2048/rdkit-2026.03.3"
        indexes = set(
            connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'compound_structures'"
                )
            ).scalars()
        )
        assert {
            "ix_compound_structures_rdkit_mol_gist",
            "ix_compound_structures_morgan_bfp_gist",
        } <= indexes
        connection.execute(text("SET enable_seqscan = off"))
        substructure_plan = "\n".join(
            connection.execute(
                text(
                    "EXPLAIN (COSTS OFF) SELECT id FROM compound_structures "
                    "WHERE tenant_id = :tenant_id AND rdkit_mol @> qmol_from_smarts('c1ccccc1'::cstring)"
                ),
                {"tenant_id": tenant_id},
            ).scalars()
        )
        assert "ix_compound_structures_rdkit_mol_gist" in substructure_plan
        similarity_plan = "\n".join(
            connection.execute(
                text(
                    "EXPLAIN (COSTS OFF) SELECT id FROM compound_structures "
                    "WHERE tenant_id = :tenant_id "
                    "AND morgan_bfp % morganbv_fp(mol_from_smiles('CC(=O)OC1=CC=CC=C1C(=O)O'), 2)"
                ),
                {"tenant_id": tenant_id},
            ).scalars()
        )
        assert "ix_compound_structures_morgan_bfp_gist" in similarity_plan
        rls = connection.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE oid = 'public.compound_structures'::regclass"
            )
        ).one()
        assert rls == (True, True)

    with pytest.raises(DBAPIError, match="canonical_smiles is not valid SMILES"):
        with admin_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO compound_structures "
                    "(id, tenant_id, entity_id, canonical_smiles, standard_inchi_key, structure_version, "
                    "created_at, updated_at) VALUES "
                    "(:id, :tenant_id, :entity_id, 'not-a-smiles', 'AAAAAAAAAAAAAA-BBBBBBBBBB-C', "
                    "'test-source/v1', now(), now())"
                ),
                {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "entity_id": invalid_entity_id},
            )

    with Session(runtime_engine) as runtime_session:
        assert runtime_session.scalar(text("SELECT count(*) FROM compound_structures")) == 0
        set_tenant_context(runtime_session, tenant_id)
        assert runtime_session.scalar(text("SELECT count(*) FROM compound_structures")) == 3

    with Session(runtime_engine) as chemistry_session:
        chemistry = ChemistryService(chemistry_session, tenant_id)
        exact = chemistry.exact("O=C(O)c1ccccc1OC(C)=O")
        assert [hit.entity_name for hit in exact.hits] == ["Aspirin"]
        substructure = chemistry.substructure("c1ccccc1")
        assert {hit.entity_name for hit in substructure.hits} == {"Aspirin", "Paracetamol"}
        similarity = chemistry.similarity("CC(=O)OC1=CC=CC=C1C(=O)O", threshold=0.1)
        assert similarity.hits[0].entity_name == "Aspirin"
        assert similarity.hits[0].similarity == pytest.approx(1.0)
        assert all(hit.entity_name != "Ibuprofen Other Tenant" for hit in similarity.hits)

    with Session(runtime_engine) as wrong_tenant_session:
        set_tenant_context(wrong_tenant_session, other_tenant_id)
        assert wrong_tenant_session.scalar(text("SELECT count(*) FROM compound_structures")) == 1

    admin_engine.dispose()
    runtime_engine.dispose()
