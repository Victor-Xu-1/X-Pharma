from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import select

from pharma_intel.governance.fact_identity import _projection
from pharma_intel.governance.materialization_context import MaterializationContext
from pharma_intel.governance.temporal_merge import (
    _as_utc,
    _merge_program_milestones,
    _merge_program_status_history,
    _normalize_phase,
    _should_update_temporal_state,
    _validated_datetime,
)
from pharma_intel.models import (
    DevelopmentPhase,
    DevelopmentProgram,
    DevelopmentProgramOrganization,
    DevelopmentProgramTarget,
    Entity,
    ProgramTargetRole,
    StagedFact,
)


def materialize_program(
    context: MaterializationContext, staged: StagedFact, payload: dict[str, Any]
) -> list[dict[str, str]]:
    drug = context._entity(cast(dict[str, Any], payload["drug"]), staged.source_document_id)
    target_facts = list(payload.get("targets") or [])
    if payload.get("target") is not None:
        target_facts = [{"role": ProgramTargetRole.PRIMARY.value, "entity": payload["target"]}]
    targets = [
        (
            ProgramTargetRole(str(item["role"])),
            context._entity(cast(dict[str, Any], item["entity"]), staged.source_document_id),
        )
        for item in target_facts
    ]
    targets.sort(key=lambda item: (item[0] != ProgramTargetRole.PRIMARY, item[1].id))
    disease = context._optional_entity(payload.get("indication"), staged.source_document_id)
    organization = context._optional_entity(payload.get("organization"), staged.source_document_id)
    organization_facts = list(payload.get("organizations") or [])
    if organization is not None and not any(item.get("role") == "originator" for item in organization_facts):
        # A legacy organization is authoritative for the originator identity. Keep it
        # when newer payloads also carry collaborators instead of silently dropping it.
        organization_facts.append({"role": "originator", "entity": payload["organization"]})
    organizations = [
        (
            str(item["role"]),
            context._entity(cast(dict[str, Any], item["entity"]), staged.source_document_id),
            cast(str | None, item.get("country_region")),
            cast(str | None, item.get("organization_type")),
        )
        for item in organization_facts
    ]
    organizations.sort(key=lambda item: (item[0] != "originator", item[1].id))
    if organization is None:
        organization = next((entity for role, entity, _, _ in organizations if role == "originator"), None)
    phase = _normalize_phase(str(payload["phase"]))
    if phase is None:
        context._defer_projection(
            staged,
            "unsupported_development_phase",
            f"Program phase {payload['phase']!r} is not in the controlled phase vocabulary.",
        )
        return []
    regional_phases: dict[str, DevelopmentPhase | None] = {}
    for field_name in ("global_phase", "china_phase"):
        raw_phase = payload.get(field_name)
        normalized = _normalize_phase(str(raw_phase)) if raw_phase is not None else None
        if raw_phase is not None and normalized is None:
            context._defer_projection(
                staged,
                f"unsupported_{field_name}",
                f"Program {field_name} {raw_phase!r} is not in the controlled phase vocabulary.",
            )
            return []
        regional_phases[field_name] = normalized
    program = context.session.scalar(
        select(DevelopmentProgram).where(
            DevelopmentProgram.tenant_id == context.tenant_id,
            DevelopmentProgram.drug_entity_id == drug.id,
            DevelopmentProgram.disease_entity_id == (disease.id if disease else None),
            DevelopmentProgram.organization_entity_id == (organization.id if organization else None),
        )
    )
    if program is None:
        program = DevelopmentProgram(
            tenant_id=context.tenant_id,
            drug_entity_id=drug.id,
            disease_entity_id=disease.id if disease else None,
            organization_entity_id=organization.id if organization else None,
            phase=phase,
        )
        context.session.add(program)
    incoming_status_date = _validated_datetime(payload.get("status_date"))
    should_update_current = program.status_date is None or (
        incoming_status_date is not None and _as_utc(incoming_status_date) >= _as_utc(program.status_date)
    )
    if should_update_current:
        program.phase = phase
        raw_status = cast(str | None, payload.get("status"))
        program.status_detail = raw_status
        # The model may emit the governed state directly; otherwise only an exact
        # controlled token in the free-text detail is promoted. Anything else stays
        # NULL rather than being bucketed by guesswork.
        governed_status = cast(str | None, payload.get("program_status"))
        fallback = raw_status.strip().lower() if raw_status else None
        program.program_status = governed_status or (
            fallback if fallback in {"active", "inactive", "unknown"} else None
        )
        program.modality = cast(str | None, payload.get("modality"))
        program.innovation_type = cast(str | None, payload.get("innovation_type"))
        program.therapeutic_area = cast(str | None, payload.get("therapeutic_area"))
        program.drug_category = cast(str | None, payload.get("drug_category"))
        program.mechanism_of_action = cast(str | None, payload.get("mechanism_of_action"))
        program.geography = cast(str | None, payload.get("geography"))
        program.status_date = incoming_status_date
        if payload.get("development_rights_regions"):
            program.development_rights_regions = list(payload["development_rights_regions"])
        if payload.get("commercialization_rights_regions"):
            program.commercialization_rights_regions = list(payload["commercialization_rights_regions"])
        if payload.get("program_tags"):
            program.program_tags = list(payload["program_tags"])
        _sync_program_targets(context, program, targets, staged.source_document_id)
        _sync_program_organizations(context, program, organizations, staged.source_document_id)
    for field_name, date_field in (
        ("global_phase", "global_phase_started_at"),
        ("china_phase", "china_phase_started_at"),
    ):
        regional_phase = regional_phases[field_name]
        incoming_phase_at = _validated_datetime(payload.get(date_field))
        current_phase_at = cast(datetime | None, getattr(program, date_field))
        if regional_phase is not None and _should_update_temporal_state(current_phase_at, incoming_phase_at):
            setattr(program, field_name, regional_phase.value)
            setattr(program, date_field, incoming_phase_at)
    program.status_history = _merge_program_status_history(
        program.status_history or [],
        cast(list[dict[str, Any]], payload.get("status_history") or []),
        current_phase=phase.value,
        current_status=cast(str | None, payload.get("status")),
        current_status_at=incoming_status_date,
        current_geography=cast(str | None, payload.get("geography")),
        source_document_id=staged.source_document_id,
    )
    program.milestones = _merge_program_milestones(
        program.milestones or [],
        cast(list[dict[str, Any]], payload.get("milestones") or []),
        source_document_id=staged.source_document_id,
    )
    program.source_document_id = staged.source_document_id
    for _, target in targets:
        context._relationship(drug, "has_target", target, staged)
    if disease:
        context._relationship(drug, "developed_for", disease, staged)
    for role, linked_organization, _, _ in organizations:
        predicate = "develops" if role == "originator" else f"program_{role}"
        context._relationship(linked_organization, predicate, drug, staged)
    context.session.flush()
    return [_projection("development_program", program.id)]


def _sync_program_organizations(
    context: MaterializationContext,
    program: DevelopmentProgram,
    organizations: list[tuple[str, Entity, str | None, str | None]],
    source_document_id: str | None,
) -> None:
    """Append-only versioned organization set, mirroring the target set semantics."""
    context.session.flush()
    current_version = int(program.organization_set_version or 1)
    current = list(
        context.session.scalars(
            select(DevelopmentProgramOrganization)
            .where(
                DevelopmentProgramOrganization.tenant_id == context.tenant_id,
                DevelopmentProgramOrganization.program_id == program.id,
                DevelopmentProgramOrganization.organization_set_version == current_version,
            )
            .order_by(DevelopmentProgramOrganization.position, DevelopmentProgramOrganization.id)
        )
    )
    desired = [
        (entity.id, role, country, org_type, position)
        for position, (role, entity, country, org_type) in enumerate(organizations)
    ]
    existing = [
        (item.organization_entity_id, item.role, item.country_region, item.organization_type, item.position)
        for item in current
    ]
    if existing == desired:
        if not current and organizations:
            _append_program_organizations(context, program, current_version, organizations, source_document_id)
        return
    next_version = current_version + 1 if existing else current_version
    program.organization_set_version = next_version
    program.organization_entity_id = next(
        (entity.id for role, entity, _, _ in organizations if role == "originator"),
        None,
    )
    _append_program_organizations(context, program, next_version, organizations, source_document_id)


def _append_program_organizations(
    context: MaterializationContext,
    program: DevelopmentProgram,
    version: int,
    organizations: list[tuple[str, Entity, str | None, str | None]],
    source_document_id: str | None,
) -> None:
    for position, (role, entity, country, org_type) in enumerate(organizations):
        context.session.add(
            DevelopmentProgramOrganization(
                tenant_id=context.tenant_id,
                program_id=program.id,
                organization_set_version=version,
                organization_entity_id=entity.id,
                role=role,
                country_region=country,
                organization_type=org_type,
                position=position,
                source_document_id=source_document_id,
            )
        )


def _sync_program_targets(
    context: MaterializationContext,
    program: DevelopmentProgram,
    targets: list[tuple[ProgramTargetRole, Entity]],
    source_document_id: str | None,
) -> None:
    context.session.flush()
    current_version = int(program.target_set_version or 1)
    current = list(
        context.session.scalars(
            select(DevelopmentProgramTarget)
            .where(
                DevelopmentProgramTarget.tenant_id == context.tenant_id,
                DevelopmentProgramTarget.program_id == program.id,
                DevelopmentProgramTarget.target_set_version == current_version,
            )
            .order_by(DevelopmentProgramTarget.position, DevelopmentProgramTarget.id)
        )
    )
    desired_signature = [(entity.id, role.value, position) for position, (role, entity) in enumerate(targets)]
    current_signature = [(item.target_entity_id, item.role.value, item.position) for item in current]
    if not current and program.target_entity_id:
        current_signature = [(program.target_entity_id, ProgramTargetRole.PRIMARY.value, 0)]
        if current_signature != desired_signature:
            context.session.add(
                DevelopmentProgramTarget(
                    tenant_id=context.tenant_id,
                    program_id=program.id,
                    target_set_version=current_version,
                    target_entity_id=program.target_entity_id,
                    role=ProgramTargetRole.PRIMARY,
                    position=0,
                    source_document_id=program.source_document_id,
                )
            )
    if current_signature == desired_signature:
        if not current and targets:
            _append_program_targets(context, program, current_version, targets, source_document_id)
        program.target_combination_key = _target_combination_key(targets)
        program.target_entity_id = next(
            (entity.id for role, entity in targets if role == ProgramTargetRole.PRIMARY),
            None,
        )
        return
    next_version = current_version + 1 if current_signature else current_version
    program.target_set_version = next_version
    program.target_combination_key = _target_combination_key(targets)
    program.target_entity_id = next(
        (entity.id for role, entity in targets if role == ProgramTargetRole.PRIMARY),
        None,
    )
    _append_program_targets(context, program, next_version, targets, source_document_id)


def _append_program_targets(
    context: MaterializationContext,
    program: DevelopmentProgram,
    version: int,
    targets: list[tuple[ProgramTargetRole, Entity]],
    source_document_id: str | None,
) -> None:
    for position, (role, target) in enumerate(targets):
        context.session.add(
            DevelopmentProgramTarget(
                tenant_id=context.tenant_id,
                program_id=program.id,
                target_set_version=version,
                target_entity_id=target.id,
                role=role,
                position=position,
                source_document_id=source_document_id,
            )
        )


def _target_combination_key(targets: list[tuple[ProgramTargetRole, Entity]]) -> str | None:
    target_ids = sorted(entity.id for _, entity in targets)
    return "|".join(target_ids) if target_ids else None
