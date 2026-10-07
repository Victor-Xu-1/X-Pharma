"""Bounded source-reported names, without inference across related entities."""

from __future__ import annotations

from typing import Any

from pharma_intel.identity import normalize_name
from pharma_intel.ingest.connectors import ConnectorTransportError

MAX_ALIASES = 200
TARGET_NAME_TYPES = frozenset({"GENE_SYMBOL", "GENE_SYMBOL_OTHER", "UNIPROT"})


def provider_names(records: Any, *, fields: tuple[str, ...], canonical_name: str, target: bool = False) -> list[str]:
    if records is None:
        return []
    if not isinstance(records, list) or len(records) > 2000:
        raise ConnectorTransportError("ChEMBL synonym collection is invalid or exceeds its bounded limit")
    names: dict[str, str] = {}
    canonical = normalize_name(canonical_name)
    for record in records:
        if not isinstance(record, dict):
            raise ConnectorTransportError("ChEMBL synonym record must be an object")
        if target and record.get("syn_type") not in TARGET_NAME_TYPES:
            continue
        for field in fields:
            value = record.get(field)
            if value is None:
                continue
            if not isinstance(value, str) or len(value) > 500:
                raise ConnectorTransportError("ChEMBL synonym must be text of at most 500 characters")
            value = value.strip()
            normalized = normalize_name(value)
            if normalized and normalized != canonical:
                names.setdefault(normalized, value)
            if len(names) > MAX_ALIASES:
                raise ConnectorTransportError("ChEMBL synonym collection exceeds the supported name limit")
    return list(names.values())
