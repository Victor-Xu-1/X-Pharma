"""expand regulatory label designation and safety intelligence

Revision ID: 3b6d9f2a5c87
Revises: 2a5c8e1f4b76
Create Date: 2026-07-24 02:45:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3b6d9f2a5c87"
down_revision: str | Sequence[str] | None = "2a5c8e1f4b76"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DESIGNATION_TYPES = (
    "'breakthrough_therapy','fast_track','priority_review','accelerated_approval','orphan_drug','prime',"
    "'sakigake','conditional_marketing_authorisation','other'"
)
_LABEL_CHANGE_TYPES = (
    "'initial_label','indication_expansion','population_expansion','restriction','dosing_update',"
    "'administration_update','safety_update','boxed_warning','contraindication','other'"
)
_SAFETY_SIGNAL_TYPES = (
    "'adverse_event','boxed_warning','contraindication','risk_management','recall','clinical_hold',"
    "'postmarketing_requirement','other'"
)
_SAFETY_SEVERITIES = "'informational','moderate','serious','severe','life_threatening','fatal','unknown'"
_SAFETY_STATUSES = "'detected','under_evaluation','confirmed','monitoring','resolved','withdrawn','unknown'"
_INDEXED_COLUMNS = (
    "designation_type",
    "label_change_type",
    "label_version",
    "label_effective_at",
    "line_of_therapy",
    "biomarker",
    "route_of_administration",
    "dosage_form",
    "has_boxed_warning",
    "safety_signal_type",
    "safety_term",
    "safety_severity",
    "safety_status",
    "safety_identified_at",
    "safety_confirmed_at",
    "safety_resolved_at",
    "source_updated_at",
)


def upgrade() -> None:
    columns = (
        sa.Column("designation_type", sa.String(length=80), nullable=True),
        sa.Column("label_change_type", sa.String(length=80), nullable=True),
        sa.Column("label_version", sa.String(length=160), nullable=True),
        sa.Column("label_effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_population", sa.Text(), nullable=True),
        sa.Column("line_of_therapy", sa.String(length=240), nullable=True),
        sa.Column("biomarker", sa.String(length=240), nullable=True),
        sa.Column("route_of_administration", sa.String(length=160), nullable=True),
        sa.Column("dosage_form", sa.String(length=160), nullable=True),
        sa.Column("has_boxed_warning", sa.Boolean(), nullable=True),
        sa.Column("safety_signal_type", sa.String(length=80), nullable=True),
        sa.Column("safety_term", sa.String(length=500), nullable=True),
        sa.Column("safety_severity", sa.String(length=40), nullable=True),
        sa.Column("safety_status", sa.String(length=40), nullable=True),
        sa.Column("safety_identified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safety_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safety_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("affected_population", sa.Text(), nullable=True),
        sa.Column("risk_actions", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in columns:
        op.add_column("regulatory_events", column)

    with op.batch_alter_table("regulatory_events") as batch_op:
        batch_op.create_check_constraint(
            "ck_regulatory_designation_type",
            f"designation_type IS NULL OR designation_type IN ({_DESIGNATION_TYPES})",
        )
        batch_op.create_check_constraint(
            "ck_regulatory_label_change_type",
            f"label_change_type IS NULL OR label_change_type IN ({_LABEL_CHANGE_TYPES})",
        )
        batch_op.create_check_constraint(
            "ck_regulatory_safety_signal_type",
            f"safety_signal_type IS NULL OR safety_signal_type IN ({_SAFETY_SIGNAL_TYPES})",
        )
        batch_op.create_check_constraint(
            "ck_regulatory_safety_severity",
            f"safety_severity IS NULL OR safety_severity IN ({_SAFETY_SEVERITIES})",
        )
        batch_op.create_check_constraint(
            "ck_regulatory_safety_status",
            f"safety_status IS NULL OR safety_status IN ({_SAFETY_STATUSES})",
        )
        batch_op.create_check_constraint(
            "ck_regulatory_safety_confirmation_window",
            "safety_confirmed_at IS NULL OR safety_identified_at IS NULL OR "
            "safety_confirmed_at >= safety_identified_at",
        )
        batch_op.create_check_constraint(
            "ck_regulatory_safety_resolution_window",
            "safety_resolved_at IS NULL OR safety_identified_at IS NULL OR safety_resolved_at >= safety_identified_at",
        )
        for column in _INDEXED_COLUMNS:
            batch_op.create_index(op.f(f"ix_regulatory_events_{column}"), [column])
        batch_op.create_index(
            "ix_regulatory_designation_lookup",
            ["tenant_id", "designation_type", "jurisdiction", "subject_entity_id"],
        )
        batch_op.create_index(
            "ix_regulatory_label_lookup",
            ["tenant_id", "label_change_type", "has_boxed_warning", "subject_entity_id"],
        )
        batch_op.create_index(
            "ix_regulatory_safety_lookup",
            ["tenant_id", "safety_status", "safety_severity", "subject_entity_id"],
        )
        batch_op.alter_column("risk_actions", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("regulatory_events") as batch_op:
        batch_op.drop_index("ix_regulatory_safety_lookup")
        batch_op.drop_index("ix_regulatory_label_lookup")
        batch_op.drop_index("ix_regulatory_designation_lookup")
        for column in reversed(_INDEXED_COLUMNS):
            batch_op.drop_index(op.f(f"ix_regulatory_events_{column}"))
        batch_op.drop_constraint("ck_regulatory_safety_resolution_window", type_="check")
        batch_op.drop_constraint("ck_regulatory_safety_confirmation_window", type_="check")
        batch_op.drop_constraint("ck_regulatory_safety_status", type_="check")
        batch_op.drop_constraint("ck_regulatory_safety_severity", type_="check")
        batch_op.drop_constraint("ck_regulatory_safety_signal_type", type_="check")
        batch_op.drop_constraint("ck_regulatory_label_change_type", type_="check")
        batch_op.drop_constraint("ck_regulatory_designation_type", type_="check")
        for column in reversed(
            (
                "designation_type",
                "label_change_type",
                "label_version",
                "label_effective_at",
                "approved_population",
                "line_of_therapy",
                "biomarker",
                "route_of_administration",
                "dosage_form",
                "has_boxed_warning",
                "safety_signal_type",
                "safety_term",
                "safety_severity",
                "safety_status",
                "safety_identified_at",
                "safety_confirmed_at",
                "safety_resolved_at",
                "affected_population",
                "risk_actions",
                "source_updated_at",
            )
        ):
            batch_op.drop_column(column)
