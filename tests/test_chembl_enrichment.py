from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.chembl import parse_chembl_snapshot
from pharma_intel.governance.schemas import ActivityFact, StructureFact
from pharma_intel.governance.service import GovernanceService
from pharma_intel.ingest.chembl import ChemblRoutingRule, _molecule_summary, _snapshot_bytes
from pharma_intel.ingest.chembl_enrichment import activity_page, molecule_structure
from pharma_intel.ingest.connectors import ConnectorTransportError
from pharma_intel.models import ActivityMeasurement, CompoundStructure, Tenant
from tests.test_chembl_governance import _snapshot, _version
from tests.test_official_source_updates import _updated_version


def _enriched_snapshot() -> bytes:
    payload = json.loads(_snapshot())
    payload["schema_version"] = "pharma.chembl.mechanism.v2"
    payload["molecule"]["structure"] = {"canonical_smiles": "CCO"}
    payload["activities"] = [
        {
            "activity_id": 12,
            "assay_chembl_id": "CHEMBL123",
            "molecule_chembl_id": "CHEMBL1201827",
            "target_chembl_id": "CHEMBL203",
            "type": "IC50",
            "relation": "<",
            "value": "10",
            "units": "nM",
            "standard_type": "IC50",
            "standard_relation": "<",
            "standard_value": 10,
            "standard_units": "nM",
        }
    ]
    payload["activity_coverage"] = {"requested": True, "reported_total": 100, "fetched": 1, "excluded": 0, "limit": 1}
    return json.dumps(payload).encode()


def test_v2_retains_reported_structure_and_individual_activity_without_claiming_exhaustive_coverage() -> None:
    record = parse_chembl_snapshot(_enriched_snapshot())
    assert [fact.fact_kind for fact in record.enrichment] == ["structure", "activity"]
    structure, activity = record.enrichment
    assert isinstance(structure, StructureFact) and isinstance(activity, ActivityFact)
    assert structure.canonical_smiles == "CCO"
    assert activity.reported_relation == "<"
    assert activity.citation.locator == "activity:12"
    assert record.activity_coverage is not None and record.activity_coverage.reported_total == 100
    assert parse_chembl_snapshot(_snapshot()).enrichment == ()


@pytest.mark.parametrize("reported_phase", ["4.0", "0.5", "-1"])
def test_connector_snapshot_accepts_exact_official_decimal_phase_text_without_rewriting_source(
    reported_phase: str,
) -> None:
    payload = json.loads(_enriched_snapshot())
    molecule_id = payload["molecule"]["chembl_id"]
    molecule = _molecule_summary(
        {
            "molecule_chembl_id": molecule_id,
            "pref_name": payload["molecule"]["pref_name"],
            "max_phase": reported_phase,
            "molecule_structures": {"canonical_smiles": "CCO"},
        },
        molecule_id,
    )
    content = _snapshot_bytes(
        target_summary=payload["target"],
        molecule=molecule,
        mechanism=payload["mechanism"],
        target_chembl_id=payload["target"]["chembl_id"],
        activity_data=(payload["activities"], payload["activity_coverage"]),
    )
    original = bytes(content)
    record = parse_chembl_snapshot(content)
    assert content == original and json.loads(content)["molecule"]["max_phase"] == reported_phase
    assert [fact.fact_kind for fact in record.enrichment] == ["structure", "activity"]
    assert record.fact.phase == "approved" and record.fact.global_phase is None


@pytest.mark.parametrize("reported_phase", ["0.50000000000000001", "NaN", "Infinity", "4e0", "1.5", "approved", "true"])
def test_decimal_phase_text_must_be_an_exact_known_stage_not_a_rounded_or_invented_number(reported_phase: str) -> None:
    payload = json.loads(_enriched_snapshot())
    payload["molecule"]["max_phase"] = reported_phase
    with pytest.raises(ValueError, match="governed schema"):
        parse_chembl_snapshot(json.dumps(payload).encode())


def test_v2_rejects_cross_target_and_duplicate_activity_identity() -> None:
    payload = json.loads(_enriched_snapshot())
    payload["activities"][0]["target_chembl_id"] = "CHEMBL999"
    with pytest.raises(ValueError, match="scope"):
        parse_chembl_snapshot(json.dumps(payload).encode())
    payload["activities"] *= 2
    with pytest.raises(ValueError, match="governed schema"):
        parse_chembl_snapshot(json.dumps(payload).encode())


def test_activity_discovery_is_bounded_and_missing_reported_values_are_counted_not_invented() -> None:
    record = json.loads(_enriched_snapshot())["activities"][0]
    second = {**record, "activity_id": 13, "value": None}
    observations, coverage = activity_page(
        {"activities": [record, second], "page_meta": {"total_count": 50}},
        molecule_id="CHEMBL1201827",
        target_id="CHEMBL203",
        limit=2,
    )
    assert len(observations) == 1 and coverage["excluded"] == 1 and coverage["reported_total"] == 50
    with pytest.raises(ConnectorTransportError, match="identity"):
        activity_page(
            {"activities": [record], "page_meta": {"total_count": 1}},
            molecule_id="CHEMBL25",
            target_id="CHEMBL203",
            limit=1,
        )
    assert molecule_structure({"molecule_structures": None}) is None
    structure = molecule_structure({"molecule_structures": {"canonical_smiles": "CCO"}})
    assert structure is not None and structure["canonical_smiles"] == "CCO"


@pytest.mark.parametrize("value", [True, "NaN", "Infinity", "inactive"])
def test_non_numeric_activity_is_explicitly_excluded_not_projected_as_a_number(value: object) -> None:
    item = json.loads(_enriched_snapshot())["activities"][0]
    item["value"] = value
    activities, coverage = activity_page(
        {"activities": [item], "page_meta": {"total_count": 1}},
        molecule_id="CHEMBL1201827",
        target_id="CHEMBL203",
        limit=1,
    )
    assert not activities and coverage["excluded"] == 1


def test_legacy_checkpoint_identity_does_not_change_when_activity_enrichment_is_disabled() -> None:
    with pytest.raises(ValueError, match="25 mechanism records"):
        ChemblRoutingRule(target_chembl_id="CHEMBL203", max_records=100, include_activities=True)
    old = {"target_chembl_id": "CHEMBL203", "max_records": 25, "page_size": 25, "sync_mode": "continuous"}
    assert ChemblRoutingRule.model_validate(old).document() == old
    assert (
        ChemblRoutingRule.model_validate({**old, "include_activities": True}).document()["include_activities"] is True
    )


def test_enrichment_uses_the_existing_governance_publication_and_normalization_path(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _enriched_snapshot()
    monkeypatch.setattr("tests.test_chembl_governance._snapshot", lambda: content)
    store, version = _version(session, tenant, tmp_path)
    result = GovernanceService(
        session, Settings(object_store_root=tmp_path / "objects"), store, tenant.id
    ).govern_version(version.id)
    assert result["fact_count"] == 4
    assert result["published"] == 4
    assert session.scalar(select(func.count()).select_from(CompoundStructure)) == 1
    assert session.scalar(select(func.count()).select_from(ActivityMeasurement)) == 1
    activity = session.scalar(select(ActivityMeasurement))
    assert activity is not None and activity.source_system == "chembl"
    assert activity.reported_value == "10" and activity.reported_relation.value == "<"


def test_activity_replay_updates_reported_and_standardized_projection_consistently(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _enriched_snapshot()
    monkeypatch.setattr("tests.test_chembl_governance._snapshot", lambda: content)
    store, older = _version(session, tenant, tmp_path)
    service = GovernanceService(session, Settings(), store, tenant.id)
    service.govern_version(older.id)
    newer = _updated_version(session, store, older)
    payload = json.loads(store.read_bytes(newer.raw_object_uri or "", 1_000_000))
    payload["activities"][0].update(value="20", relation=">=", standard_value=20, standard_relation=">=")
    changed = json.dumps(payload).encode()
    digest = hashlib.sha256(changed).hexdigest()
    newer.raw_object_uri = store.put_bytes(tenant.id, "raw", changed, digest, ".json").uri
    newer.content_sha256 = digest
    newer.size_bytes = len(changed)
    session.commit()
    service.govern_version(newer.id)
    assert session.scalar(select(func.count()).select_from(ActivityMeasurement)) == 1
    activity = session.scalar(select(ActivityMeasurement))
    assert activity is not None and activity.reported_value == "20" and activity.reported_relation.value == ">="
    assert activity.standard_value == 20 and activity.standard_relation is not None
    assert activity.standard_relation.value == ">="
