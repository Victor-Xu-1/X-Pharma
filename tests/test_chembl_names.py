from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.chembl import parse_chembl_snapshot
from pharma_intel.governance.service import GovernanceService
from pharma_intel.http.entities import _entity_search_items
from pharma_intel.http.public_read_policy import _public_entity_read
from pharma_intel.ingest.chembl import _molecule_summary, _target_summary
from pharma_intel.ingest.connectors import ConnectorTransportError
from pharma_intel.models import Entity, EntityAlias, EntityType, GovernanceStatus, ReviewStatus, StagedFact, Tenant
from pharma_intel.search.service import EntitySearchService
from tests.test_chembl_connector import _molecules, _target
from tests.test_chembl_governance import _snapshot, _version


def test_target_names_preserve_official_alternative_symbols_but_not_enzyme_classes() -> None:
    target = _target()
    target["target_components"][0]["target_component_synonyms"].extend(  # type: ignore[index]
        [
            {"component_synonym": "ERBB1", "syn_type": "GENE_SYMBOL_OTHER"},
            {"component_synonym": " erbB1 ", "syn_type": "UNIPROT"},
            {"component_synonym": "2.7.10.1", "syn_type": "EC_NUMBER"},
        ]
    )
    result = _target_summary(target, "CHEMBL203")
    assert result["aliases"] == ["EGFR", "ERBB1"]


def test_component_names_never_become_names_of_a_protein_complex() -> None:
    target = _target()
    target["target_type"] = "PROTEIN COMPLEX"
    result = _target_summary(target, "CHEMBL203")
    assert result["aliases"] == []
    assert result["gene_symbol"] is None
    assert result["uniprot_accession"] is None


def test_molecule_names_preserve_research_codes_trade_names_and_deduplicate() -> None:
    molecule = _molecules()[0]
    molecule["molecule_synonyms"] = [
        {"molecule_synonym": " ABX-EGF ", "synonyms": "ABX-EGF", "syn_type": "RESEARCH_CODE"},
        {"molecule_synonym": "Vectibix", "synonyms": "VECTIBIX", "syn_type": "TRADE_NAME"},
        {"molecule_synonym": "Panitumumab", "syn_type": "INN"},
    ]
    assert _molecule_summary(molecule, "CHEMBL1201827")["aliases"] == ["ABX-EGF", "Vectibix"]


@pytest.mark.parametrize("names", [[{"molecule_synonym": "x" * 501}], ["not an object"], "not a list"])
def test_malformed_provider_names_fail_closed_without_truncating_identity(names: object) -> None:
    molecule = _molecules()[0]
    molecule["molecule_synonyms"] = names
    with pytest.raises(ConnectorTransportError, match="synonym"):
        _molecule_summary(molecule, "CHEMBL1201827")


def _named_snapshot() -> bytes:
    payload = json.loads(_snapshot())
    payload["schema_version"] = "pharma.chembl.mechanism.v3"
    payload["target"]["aliases"] = ["EGFR", "ERBB1"]
    payload["molecule"]["aliases"] = ["ABX-EGF", "Vectibix"]
    return json.dumps(payload, sort_keys=True).encode()


def test_v3_names_have_individual_evidence_and_legacy_snapshots_stay_compatible() -> None:
    record = parse_chembl_snapshot(_named_snapshot())
    assert [fact.alias for fact in record.names] == ["EGFR", "ERBB1", "ABX-EGF", "Vectibix"]
    assert all(fact.alias in fact.citation.quote for fact in record.names)
    assert len({fact.citation.locator for fact in record.names}) == 4
    assert parse_chembl_snapshot(_snapshot()).names == ()
    legacy = json.loads(_named_snapshot())
    legacy["schema_version"] = "pharma.chembl.mechanism.v2"
    with pytest.raises(ValueError, match="governed schema"):
        parse_chembl_snapshot(json.dumps(legacy).encode())


def test_official_names_publish_through_governance_idempotently(
    session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    store, version = _version(session, tenant, tmp_path, _named_snapshot())
    service = GovernanceService(session, Settings(object_store_root=tmp_path / "objects"), store, tenant.id)
    first = service.govern_version(version.id)
    second = service.govern_version(version.id)
    assert first["run_id"] == second["run_id"]
    assert first["published"] == first["fact_count"] == 6
    aliases = list(session.scalars(select(EntityAlias)))
    assert {alias.normalized_alias for alias in aliases} >= {"egfr", "erbb1", "abx-egf", "vectibix"}
    assert sum(alias.normalized_alias == "egfr" for alias in aliases) == 1
    drug = session.scalar(select(Entity).where(Entity.entity_type == EntityType.DRUG))
    assert drug is not None
    assert not any(alias.entity_id == drug.id and alias.normalized_alias == "egfr" for alias in aliases)
    assert session.scalar(select(func.count()).select_from(Entity)) == 2
    name_facts = list(session.scalars(select(StagedFact).where(StagedFact.fact_kind == "entity_alias")))
    assert len(name_facts) == 4
    assert all(fact.status == GovernanceStatus.PUBLISHED and fact.published_resource_id for fact in name_facts)
    session.expire_all()
    search = EntitySearchService(session, tenant.id, Settings(search_backend="database"))
    result = search.search("ABX-EGF", EntityType.DRUG, 10, 0, ReviewStatus.VERIFIED)
    assert result.total == 1 and result.items[0].id == drug.id
    assert result.matches[drug.id].match_type == "alias"
    assert result.matches[drug.id].match_relation == "exact"
    assert "ABX-EGF" in _entity_search_items(result)[0].aliases
    assert "ABX-EGF" in _public_entity_read(result.items[0]).aliases
    related = search.search("ERBB1", EntityType.DRUG, 10, 0, ReviewStatus.VERIFIED, include_related=True)
    assert related.total == 1 and related.items[0].id == drug.id
    other = Tenant(slug="isolated-names", name="Isolated names")
    session.add(other)
    session.commit()
    isolated = EntitySearchService(session, other.id, Settings(search_backend="database"))
    assert isolated.search("ABX-EGF", None, 10, 0, ReviewStatus.VERIFIED).total == 0
