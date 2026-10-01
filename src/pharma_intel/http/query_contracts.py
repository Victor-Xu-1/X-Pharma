from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import HTTPException
from pydantic import StringConstraints

from pharma_intel.models import (
    EntityType,
    TrialEntityRole,
    TrialResultEvaluation,
)
from pharma_intel.schemas import (
    DealSortField,
    SortCriterionRead,
    SortDirection,
)
from pharma_intel.sorting import SortClause, SortValidationError, resolve_sort_clauses

DealAssetModalityQueryValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


DealAssetProgramTagQueryValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=240),
]


PipelineModalityQueryValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


PipelineProgramTagQueryValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=240),
]


def _validated_utc_datetime_range(
    start: datetime | None,
    end: datetime | None,
    *,
    start_field: str,
    end_field: str,
) -> tuple[datetime | None, datetime | None]:
    for field, value in ((start_field, start), (end_field, end)):
        if value is not None and value.tzinfo is None:
            raise HTTPException(status_code=422, detail=f"{field} must include a timezone offset")
    normalized_start = start.astimezone(UTC) if start else None
    normalized_end = end.astimezone(UTC) if end else None
    if normalized_start and normalized_end and normalized_start > normalized_end:
        raise HTTPException(status_code=422, detail=f"{start_field} must not be after {end_field}")
    return normalized_start, normalized_end


def _validated_trial_role_entity_filter(
    entity_id: str | None,
    entity_ids: list[str] | None,
    role: TrialEntityRole | None,
) -> tuple[str | None, list[str] | None, TrialEntityRole | None]:
    if entity_id is not None and entity_ids:
        raise HTTPException(status_code=422, detail="role_entity_id cannot be combined with role_entity_ids")
    normalized_ids = sorted(set(entity_ids or [])) or None
    if normalized_ids and any(not entity_value or len(entity_value) > 36 for entity_value in normalized_ids):
        raise HTTPException(status_code=422, detail="role_entity_ids contains an invalid entity ID")
    if role is not None and entity_id is None and normalized_ids is None:
        raise HTTPException(
            status_code=422,
            detail="role_entity_role requires role_entity_id or role_entity_ids",
        )
    return entity_id, normalized_ids, role


def _validated_trial_role_entity_ids(field: str, entity_ids: list[str] | None) -> list[str] | None:
    normalized_ids = sorted(set(entity_ids or [])) or None
    if normalized_ids and any(len(entity_id) != 36 for entity_id in normalized_ids):
        raise HTTPException(status_code=422, detail=f"{field} contains an invalid entity ID")
    return normalized_ids


def _validated_number_range(
    minimum: float | None,
    maximum: float | None,
    *,
    minimum_field: str,
    maximum_field: str,
) -> tuple[float | None, float | None]:
    if minimum is not None and maximum is not None and minimum > maximum:
        raise HTTPException(status_code=422, detail=f"{minimum_field} must not exceed {maximum_field}")
    return minimum, maximum


def _normalized_repeated_filter(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    return list(dict.fromkeys(values))


def _validated_sort[SortField: str](
    tokens: list[str] | None,
    allowed_fields: tuple[SortField, ...],
    *,
    default_field: SortField,
    default_direction: SortDirection,
    legacy_field: SortField | None,
    legacy_direction: SortDirection | None,
) -> tuple[SortClause[SortField], ...]:
    try:
        return resolve_sort_clauses(
            tokens,
            allowed_fields,
            default_field=default_field,
            default_direction=default_direction,
            legacy_field=legacy_field,
            legacy_direction=legacy_direction,
        )
    except SortValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _sort_reads[SortField: str](clauses: tuple[SortClause[SortField], ...]) -> list[SortCriterionRead]:
    return [SortCriterionRead(field=clause.field, direction=clause.direction) for clause in clauses]


def _validate_deal_amount_sort(sort: tuple[SortClause[DealSortField], ...], currency: str | None) -> None:
    if any(clause.field in {"upfront_amount", "total_potential_amount"} for clause in sort) and currency is None:
        raise HTTPException(
            status_code=422,
            detail="currency is required when sorting disclosed deal amounts",
        )


def _validated_pipeline_signal_filters(
    has_clinical_results: bool | None,
    clinical_result_evaluation: TrialResultEvaluation | None,
    has_deal: bool | None,
    deal_currency: str | None,
    deal_total_potential_amount_min: float | None,
    deal_total_potential_amount_max: float | None,
) -> tuple[float | None, float | None]:
    if has_clinical_results is False and clinical_result_evaluation is not None:
        raise HTTPException(
            status_code=422,
            detail="clinical_result_evaluation cannot be combined with has_clinical_results=false",
        )
    if has_deal is False and any(
        value is not None for value in (deal_currency, deal_total_potential_amount_min, deal_total_potential_amount_max)
    ):
        raise HTTPException(status_code=422, detail="deal detail filters cannot be combined with has_deal=false")
    if (
        deal_total_potential_amount_min is not None or deal_total_potential_amount_max is not None
    ) and deal_currency is None:
        raise HTTPException(status_code=422, detail="deal_currency is required for disclosed amount filters")
    return _validated_number_range(
        deal_total_potential_amount_min,
        deal_total_potential_amount_max,
        minimum_field="deal_total_potential_amount_min",
        maximum_field="deal_total_potential_amount_max",
    )


def _normalize_entity_types(entity_type: EntityType | None, entity_types: list[EntityType]) -> list[EntityType]:
    selected = set(entity_types)
    if entity_type is not None:
        selected.add(entity_type)
    return sorted(selected, key=lambda item: item.value)
