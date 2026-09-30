from __future__ import annotations

from collections.abc import Sequence

MECHANISM_ACTION_TYPES = frozenset(
    {
        "ACTIVATOR",
        "AGONIST",
        "ANTAGONIST",
        "BINDING AGENT",
        "BLOCKER",
        "CROSS LINKING AGENT",
        "INHIBITOR",
        "INVERSE AGONIST",
        "MODULATOR",
        "NEGATIVE ALLOSTERIC MODULATOR",
        "PARTIAL AGONIST",
        "POSITIVE ALLOSTERIC MODULATOR",
        "VACCINE ANTIGEN",
    }
)

MISSING_PROGRAM_VALUES = frozenset({"", "n/a", "na", "none", "not available", "null", "unknown"})

PROGRAM_DRUG_CATEGORY_BY_MODALITY = {
    "antibody": "biologic",
    "antibody drug conjugate": "biologic",
    "small molecule": "chemical_drug",
}

_TECHNICAL_PROGRAM_TAGS = frozenset({"chembl"})
_TECHNICAL_PROGRAM_TAG_PREFIXES = ("maximum clinical phase",)


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return None if cleaned.casefold() in MISSING_PROGRAM_VALUES else cleaned


def _action_type_key(value: str | None) -> str:
    return " ".join((value or "").strip().upper().replace("_", " ").replace("-", " ").split())


def is_mechanism_action_type(value: str | None) -> bool:
    return _action_type_key(value) in MECHANISM_ACTION_TYPES


def public_program_modality(modality: str | None, drug_category: str | None) -> str | None:
    """Project historical action-type misuse back to the source molecule type."""

    return _clean_value(drug_category) if is_mechanism_action_type(modality) else _clean_value(modality)


def public_program_drug_category(modality: str | None, drug_category: str | None) -> str | None:
    cleaned = _clean_value(drug_category)
    if cleaned is None:
        return None
    if is_mechanism_action_type(modality):
        return PROGRAM_DRUG_CATEGORY_BY_MODALITY.get(cleaned.casefold())
    return cleaned


def public_program_tags(values: Sequence[str] | None) -> list[str]:
    """Return business tags while retaining raw source metadata in storage."""

    visible: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        normalized = " ".join(value.split())
        key = normalized.casefold()
        if (
            not normalized
            or key in _TECHNICAL_PROGRAM_TAGS
            or any(key.startswith(prefix) for prefix in _TECHNICAL_PROGRAM_TAG_PREFIXES)
            or key in seen
        ):
            continue
        visible.append(normalized)
        seen.add(key)
    return visible
