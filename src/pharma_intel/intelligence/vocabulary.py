from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import and_, case, func
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.models import ActivityMeasurement, Assay, MeasurementRelation, TrialResultEvaluation
from pharma_intel.program_semantics import (
    MECHANISM_ACTION_TYPES,
    MISSING_PROGRAM_VALUES,
    PROGRAM_DRUG_CATEGORY_BY_MODALITY,
)
from pharma_intel.schemas import SortCriterionRead
from pharma_intel.sorting import SortClause

_DEVELOPMENT_PHASE_RANK = {
    "discontinued": -1,
    "discovery": 0,
    "preclinical": 1,
    "ind": 2,
    "early_phase_1": 3,
    "phase_1": 4,
    "phase_1_2": 5,
    "phase_2": 6,
    "phase_2_3": 7,
    "phase_3": 8,
    "filed": 9,
    "approved": 10,
}


_MISSING_ENTITY_LABELS = frozenset(
    {"-", "--", "n/a", "na", "none", "null", "not available", "unknown", "未披露", "暂无"}
)


def _is_meaningful_entity_label(value: str | None) -> bool:
    return value is not None and " ".join(value.casefold().split()) not in _MISSING_ENTITY_LABELS


def _meaningful_entity_name_sql(column: Any) -> ColumnElement[bool]:
    return and_(
        column.is_not(None),
        func.lower(func.trim(column)).not_in(tuple(sorted(_MISSING_ENTITY_LABELS))),
    )


def _program_action_type_sql(modality: Any) -> ColumnElement[bool]:
    normalized = func.upper(func.trim(func.replace(func.replace(modality, "_", " "), "-", " ")))
    return normalized.in_(tuple(sorted(MECHANISM_ACTION_TYPES)))


def _public_program_modality_sql(modality: Any, drug_category: Any) -> Any:
    cleaned_modality = func.nullif(func.trim(modality), "")
    cleaned_category = func.nullif(func.trim(drug_category), "")
    category_key = func.lower(cleaned_category)
    return case(
        (
            _program_action_type_sql(modality),
            case(
                (category_key.in_(tuple(sorted(MISSING_PROGRAM_VALUES))), None),
                else_=cleaned_category,
            ),
        ),
        else_=cleaned_modality,
    )


def _public_program_drug_category_sql(modality: Any, drug_category: Any) -> Any:
    cleaned_category = func.nullif(func.trim(drug_category), "")
    category_key = func.lower(cleaned_category)
    mapped_category = case(
        *((category_key == key, value) for key, value in sorted(PROGRAM_DRUG_CATEGORY_BY_MODALITY.items())),
        else_=None,
    )
    return case(
        (_program_action_type_sql(modality), mapped_category),
        (category_key.in_(tuple(sorted(MISSING_PROGRAM_VALUES))), None),
        else_=cleaned_category,
    )


def _ordered_sort_expressions[SortField: str](
    clauses: Sequence[SortClause[SortField]],
    expressions: Mapping[SortField, Any],
) -> list[Any]:
    return [
        expressions[clause.field].asc().nullslast()
        if clause.direction == "asc"
        else expressions[clause.field].desc().nullslast()
        for clause in clauses
    ]


def _sort_criteria_read[SortField: str](
    clauses: Sequence[SortClause[SortField]],
) -> list[SortCriterionRead]:
    return [SortCriterionRead(field=clause.field, direction=clause.direction) for clause in clauses]


TARGET_STATUS_VOCABULARY_VERSION = "target-dossier-status@1"


_RECRUITING_TRIAL_STATUSES = frozenset(
    {
        "recruiting",
        "enrolling by invitation",
        "active recruiting",
    }
)


_NON_RECRUITING_TRIAL_STATUSES = frozenset(
    {
        "not yet recruiting",
        "active not recruiting",
        "completed",
        "terminated",
        "withdrawn",
        "suspended",
        "no longer available",
        "temporarily not available",
        "approved for marketing",
        "unknown status",
        "unknown",
    }
)


_ACTIVE_PATENT_STATUSES = frozenset(
    {
        "active",
        "granted",
        "in force",
        "issued",
    }
)


_INACTIVE_PATENT_STATUSES = frozenset(
    {
        "inactive",
        "expired",
        "lapsed",
        "abandoned",
        "revoked",
        "rejected",
        "withdrawn",
        "pending",
        "not in force",
    }
)


_APPROVAL_REGULATORY_EVENT_TYPES = frozenset({"approval", "conditional_approval"})


def _saved_date_start(value: Any) -> datetime | None:
    """Convert a saved-contract date to the inclusive UTC start of that day."""
    return datetime.combine(value, time.min, tzinfo=UTC) if value else None


def _saved_date_end(value: Any) -> datetime | None:
    """Convert a saved-contract date to the inclusive UTC end of that day."""
    return datetime.combine(value, time.max, tzinfo=UTC) if value else None


def normalize_status_token(value: str | None) -> str:
    """Fold an ungoverned source status into a comparable token.

    Lowercases, replaces separator punctuation with spaces and collapses whitespace so
    that "Active, not recruiting", "ACTIVE_NOT_RECRUITING" and "active not recruiting"
    all resolve to the same token.
    """

    if value is None:
        return ""
    folded = value.strip().lower()
    for separator in ("_", "-", ",", "/", ";"):
        folded = folded.replace(separator, " ")
    return " ".join(folded.split())


RESEARCH_PUBLICATION_EVENT_TYPES = ("publication", "conference_abstract", "poster", "presentation")


_TRIAL_DRUG_ROLES = ("investigational_drug", "combination_drug")


_TRIAL_RESULT_EVALUATION_ORDER = (
    TrialResultEvaluation.SUPERIOR,
    TrialResultEvaluation.POSITIVE,
    TrialResultEvaluation.NON_INFERIOR,
    TrialResultEvaluation.SIMILAR,
    TrialResultEvaluation.NOT_SUPERIOR,
    TrialResultEvaluation.UNFAVORABLE,
    TrialResultEvaluation.TERMINATED,
)


def _sar_comparability_reasons(activity: ActivityMeasurement, assay: Assay) -> list[str]:
    reasons: list[str] = []
    if activity.standard_type is None:
        reasons.append("standard_type_missing")
    if activity.pchembl_value is None:
        reasons.append("pchembl_missing")
    if activity.standard_relation != MeasurementRelation.EQUAL:
        reasons.append("censored_or_approximate_relation")
    if assay.assay_type is None:
        reasons.append("assay_type_missing")
    if assay.assay_format is None:
        reasons.append("assay_format_missing")
    return reasons
