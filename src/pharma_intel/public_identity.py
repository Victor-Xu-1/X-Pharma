"""Shared display policy for canonical identifiers and search explanations."""

from __future__ import annotations

_HIDDEN_IDENTIFIER_PREFIXES = ("pharmcube", "internal", "source", "ingestion")


def is_public_entity_identifier_namespace(namespace: str) -> bool:
    normalized = namespace.strip().casefold().replace("-", "_")
    return bool(normalized) and not any(
        normalized == prefix or normalized.startswith(f"{prefix}_") for prefix in _HIDDEN_IDENTIFIER_PREFIXES
    )
