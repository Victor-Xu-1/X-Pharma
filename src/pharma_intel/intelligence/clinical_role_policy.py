from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.models import ClinicalTrialEntityRole, DataSourceType, SourceDocument


def asserted_trial_role(context: QueryContext) -> ColumnElement[bool]:
    """Registry intervention order never asserts a main/combination role.

    Keep historical rows for audit, but exclude unsupported automatic registry
    annotations from both reads and role-based filters. Explicit, governed role
    annotations from other source documents retain their existing behavior.
    """
    document = aliased(SourceDocument)
    unasserted = (
        select(document.id)
        .where(
            document.tenant_id == context.tenant_id,
            document.id == ClinicalTrialEntityRole.source_document_id,
            document.source_type == DataSourceType.CLINICALTRIALS_GOV.value,
        )
        .correlate_except(document)
        .exists()
    )
    return ~unasserted
