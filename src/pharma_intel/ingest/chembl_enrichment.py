from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pharma_intel.ingest.connectors import ConnectorTransportError


def molecule_structure(payload: dict[str, Any]) -> dict[str, Any] | None:
    structure = payload.get("molecule_structures")
    if structure is None:
        return None
    if not isinstance(structure, dict):
        raise ConnectorTransportError("ChEMBL molecule_structures is not an object")
    if not structure.get("canonical_smiles"):
        return None  # Upstream biotherapeutics may have no small-molecule structure.
    properties = payload.get("molecule_properties")
    return {
        "canonical_smiles": structure["canonical_smiles"],
        "standard_inchi": structure.get("standard_inchi"),
        "standard_inchi_key": structure.get("standard_inchi_key"),
        "molecular_formula": properties.get("full_molformula") if isinstance(properties, dict) else None,
    }


def _numeric_report(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, str | int | float) or len(str(value)) > 120:
        return False
    try:
        return Decimal(str(value)).is_finite()
    except InvalidOperation:
        return False


def activity_page(
    payload: dict[str, Any],
    *,
    molecule_id: str,
    target_id: str,
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metadata = payload.get("page_meta")
    total = metadata.get("total_count") if isinstance(metadata, dict) else None
    records = payload.get("activities")
    if not isinstance(total, int) or isinstance(total, bool) or total < 0 or not isinstance(records, list):
        raise ConnectorTransportError("ChEMBL activity response has invalid records or count")
    if len(records) != min(total, limit):
        raise ConnectorTransportError("ChEMBL activity page does not match the bounded requested count")
    result = []
    seen: set[int] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ConnectorTransportError("ChEMBL activity record is not an object")
        identifier = record.get("activity_id")
        if (
            not isinstance(identifier, int)
            or isinstance(identifier, bool)
            or identifier <= 0
            or identifier in seen
            or record.get("molecule_chembl_id") != molecule_id
            or record.get("target_chembl_id") != target_id
        ):
            raise ConnectorTransportError("ChEMBL activity response has an unexpected or duplicate identity")
        seen.add(identifier)
        if (
            record.get("value") is None
            or not _numeric_report(record.get("value"))
            or not record.get("type")
            or record.get("relation") not in {"=", "<", "<=", ">", ">=", "~"}
        ):
            continue  # No reported numeric claim can be made; preserve explicit excluded count.
        result.append(
            {
                "activity_id": identifier,
                "assay_chembl_id": record.get("assay_chembl_id"),
                "molecule_chembl_id": molecule_id,
                "target_chembl_id": target_id,
                "assay_type": record.get("assay_type"),
                "type": record["type"],
                "relation": record["relation"],
                "value": str(record["value"]),
                "units": record.get("units"),
                "standard_type": record.get("standard_type"),
                "standard_relation": record.get("standard_relation"),
                "standard_value": record.get("standard_value"),
                "standard_units": record.get("standard_units"),
                "document_chembl_id": record.get("document_chembl_id"),
            }
        )
    return result, {
        "requested": True,
        "reported_total": total,
        "fetched": len(records),
        "excluded": len(records) - len(result),
        "limit": limit,
    }
