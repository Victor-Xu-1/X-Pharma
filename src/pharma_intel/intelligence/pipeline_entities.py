from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import and_, select

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.scope import _published_entity_identity_labels
from pharma_intel.intelligence.vocabulary import _is_meaningful_entity_label, _meaningful_entity_name_sql
from pharma_intel.models import (
    DevelopmentProgram,
    DevelopmentProgramOrganization,
    DevelopmentProgramTarget,
    Entity,
    EntityType,
    ProgramTargetRole,
)
from pharma_intel.schemas import ProgramOrganizationRead, ProgramTargetRead


def _program_target_map(
    context: QueryContext,
    programs: list[DevelopmentProgram],
    legacy_targets: dict[str, tuple[str | None, str | None]],
) -> dict[str, list[ProgramTargetRead]]:
    if not programs:
        return {}
    program_ids = [program.id for program in programs]
    rows = context.session.execute(
        select(
            DevelopmentProgramTarget.program_id,
            DevelopmentProgramTarget.target_entity_id,
            Entity.name,
            DevelopmentProgramTarget.role,
            DevelopmentProgramTarget.position,
        )
        .join(
            DevelopmentProgram,
            and_(
                DevelopmentProgram.id == DevelopmentProgramTarget.program_id,
                DevelopmentProgram.tenant_id == DevelopmentProgramTarget.tenant_id,
                DevelopmentProgram.target_set_version == DevelopmentProgramTarget.target_set_version,
            ),
        )
        .join(Entity, Entity.id == DevelopmentProgramTarget.target_entity_id)
        .where(
            DevelopmentProgramTarget.tenant_id == context.tenant_id,
            DevelopmentProgramTarget.program_id.in_(program_ids),
            _meaningful_entity_name_sql(Entity.name),
        )
        .order_by(DevelopmentProgramTarget.program_id, DevelopmentProgramTarget.position)
    ).all()
    result: dict[str, list[ProgramTargetRead]] = {program_id: [] for program_id in program_ids}
    for program_id, target_id, target_name, role, position in rows:
        result[program_id].append(
            ProgramTargetRead(
                entity_id=target_id,
                name=target_name,
                role=role.value if hasattr(role, "value") else str(role),
                position=position,
            )
        )
    for program_id, (target_id, target_name) in legacy_targets.items():
        if not result.get(program_id) and target_id and _is_meaningful_entity_label(target_name):
            result[program_id] = [
                ProgramTargetRead(
                    entity_id=target_id,
                    name=target_name,
                    role=ProgramTargetRole.PRIMARY.value,
                    position=0,
                )
            ]
    for program_id, targets in result.items():
        result[program_id] = [
            target.model_copy(
                update={
                    "role": ProgramTargetRole.PRIMARY.value if index == 0 else ProgramTargetRole.COMBINATION.value,
                    "position": index,
                }
            )
            for index, target in enumerate(targets)
        ]
    return result


def _visible_program_target_map(
    context: QueryContext,
    target_map: Mapping[str, Sequence[ProgramTargetRead]],
) -> dict[str, list[ProgramTargetRead]]:
    if context.include_unpublished:
        return {program_id: list(targets) for program_id, targets in target_map.items()}
    identities = _published_entity_identity_labels(
        context,
        {target.entity_id for targets in target_map.values() for target in targets},
        EntityType.TARGET,
    )
    visible: dict[str, list[ProgramTargetRead]] = {}
    for program_id, targets in target_map.items():
        projected: list[ProgramTargetRead] = []
        seen: set[str] = set()
        for target in targets:
            identity = identities.get(target.entity_id)
            if identity is None or identity[0] in seen:
                continue
            seen.add(identity[0])
            projected.append(
                target.model_copy(
                    update={
                        "entity_id": identity[0],
                        "name": identity[1],
                        "role": (
                            ProgramTargetRole.PRIMARY.value if not projected else ProgramTargetRole.COMBINATION.value
                        ),
                        "position": len(projected),
                    }
                )
            )
        visible[program_id] = projected
    return visible


def _visible_program_organization_map(
    context: QueryContext,
    organization_map: Mapping[str, Sequence[ProgramOrganizationRead]],
) -> dict[str, list[ProgramOrganizationRead]]:
    if context.include_unpublished:
        return {program_id: list(organizations) for program_id, organizations in organization_map.items()}
    identities = _published_entity_identity_labels(
        context,
        {organization.entity_id for organizations in organization_map.values() for organization in organizations},
        EntityType.ORGANIZATION,
    )
    visible: dict[str, list[ProgramOrganizationRead]] = {}
    for program_id, organizations in organization_map.items():
        projected: list[ProgramOrganizationRead] = []
        seen: set[tuple[str, str]] = set()
        for organization in organizations:
            identity = identities.get(organization.entity_id)
            if identity is None:
                continue
            identity_role = (identity[0], organization.role)
            if identity_role in seen:
                continue
            seen.add(identity_role)
            projected.append(
                organization.model_copy(
                    update={
                        "entity_id": identity[0],
                        "name": identity[1],
                        "position": len(projected),
                    }
                )
            )
        visible[program_id] = projected
    return visible


def _program_organization_map(
    context: QueryContext,
    programs: list[DevelopmentProgram],
    legacy_organizations: dict[str, tuple[str | None, str | None]],
) -> dict[str, list[ProgramOrganizationRead]]:
    if not programs:
        return {}
    program_ids = [program.id for program in programs]
    rows = context.session.execute(
        select(
            DevelopmentProgramOrganization.program_id,
            DevelopmentProgramOrganization.organization_entity_id,
            Entity.name,
            DevelopmentProgramOrganization.role,
            DevelopmentProgramOrganization.country_region,
            DevelopmentProgramOrganization.organization_type,
            DevelopmentProgramOrganization.position,
        )
        .join(
            DevelopmentProgram,
            and_(
                DevelopmentProgram.id == DevelopmentProgramOrganization.program_id,
                DevelopmentProgram.tenant_id == DevelopmentProgramOrganization.tenant_id,
                DevelopmentProgram.organization_set_version == DevelopmentProgramOrganization.organization_set_version,
            ),
        )
        .join(Entity, Entity.id == DevelopmentProgramOrganization.organization_entity_id)
        .where(
            DevelopmentProgramOrganization.tenant_id == context.tenant_id,
            DevelopmentProgramOrganization.program_id.in_(program_ids),
        )
        .order_by(
            DevelopmentProgramOrganization.program_id,
            DevelopmentProgramOrganization.position,
        )
    ).all()
    result: dict[str, list[ProgramOrganizationRead]] = {program_id: [] for program_id in program_ids}
    for program_id, organization_id, name, role, country_region, organization_type, position in rows:
        result[program_id].append(
            ProgramOrganizationRead(
                entity_id=organization_id,
                name=name,
                role=role,
                country_region=country_region,
                organization_type=organization_type,
                position=position,
            )
        )
    for program_id, (organization_id, organization_name) in legacy_organizations.items():
        if not result.get(program_id) and organization_id and organization_name:
            result[program_id] = [
                ProgramOrganizationRead(
                    entity_id=organization_id,
                    name=organization_name,
                    role="originator",
                    position=0,
                )
            ]
    return result
