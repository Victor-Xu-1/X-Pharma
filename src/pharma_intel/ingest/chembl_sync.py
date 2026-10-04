from __future__ import annotations

from datetime import datetime
from typing import Any

from pharma_intel.ingest.connectors import ConnectorTransportError
from pharma_intel.ingest.public_sync import ContinuousSyncRule, PublicSyncState, sync_configuration_sha256


def prepare_mechanism_cycle(
    rule: ContinuousSyncRule, previous: PublicSyncState | None, now: datetime
) -> PublicSyncState:
    if previous is not None and previous.pending:
        return previous.model_copy()
    return PublicSyncState(
        configuration_sha256=sync_configuration_sha256(rule),
        source_kind="chembl_mechanism",
        phase="full_scan",
        pending=True,
        cycle_started_at=now,
        last_completed_at=previous.last_completed_at if previous else None,
        last_reconciled_at=previous.last_reconciled_at if previous else None,
    )


def normalize_mechanism(record: object, target_id: str) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ConnectorTransportError("ChEMBL mechanism record is not an object")
    mechanism_id = record.get("mec_id")
    molecule_id = str(record.get("molecule_chembl_id") or "").upper()
    actual_target = str(record.get("target_chembl_id") or "").upper()
    if not isinstance(mechanism_id, int) or isinstance(mechanism_id, bool) or mechanism_id <= 0:
        raise ConnectorTransportError("ChEMBL mechanism record has an invalid mec_id")
    if actual_target != target_id or not molecule_id.startswith("CHEMBL") or not molecule_id[6:].isdigit():
        raise ConnectorTransportError("ChEMBL mechanism record has an invalid target or molecule ID")
    if not str(record.get("mechanism_of_action") or "").strip():
        raise ConnectorTransportError("ChEMBL mechanism record is missing mechanism_of_action")
    if record.get("max_phase") is None:
        raise ConnectorTransportError("ChEMBL mechanism record is missing max_phase")
    normalized = dict(record)
    normalized["molecule_chembl_id"] = molecule_id
    normalized["target_chembl_id"] = actual_target
    return normalized
