from __future__ import annotations

from sqlalchemy import CheckConstraint

from .enums import DevelopmentPhase


def development_phase_check(column: str, name: str) -> CheckConstraint:
    if column not in {"global_phase", "china_phase", "development_phase_at_transaction"}:
        raise ValueError("Unsupported development-phase constraint column")
    values = ",".join(f"'{phase.value}'" for phase in DevelopmentPhase)
    return CheckConstraint(f"{column} IS NULL OR {column} IN ({values})", name=name)
