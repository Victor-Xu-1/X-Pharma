from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, status

from pharma_intel.enterprise.admin import (
    CreateGroupCommand,
    CreateUserCommand,
    GroupView,
    UpdateDatasetStatusCommand,
    UpdateGroupCommand,
    UpdateGroupMembersCommand,
    UpdateUserRoleCommand,
    UpdateUserStatusCommand,
)
from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.enterprise_access import _enterprise_service
from pharma_intel.licensing import DeliveryChannel, EvidenceLicensePolicy
from pharma_intel.models import (
    TenantDataset,
)
from pharma_intel.platform.operations import PlatformOperationsError, PlatformOperationsService
from pharma_intel.schemas import (
    EnterpriseAuditEventRead,
    EnterpriseAuditPageRead,
    EnterpriseDatasetRead,
    EnterpriseDatasetStatusUpdate,
    EnterpriseOverviewRead,
    EnterpriseSessionRead,
    EnterpriseSessionRevoke,
    EnterpriseUserCreate,
    EnterpriseUserRead,
    EnterpriseUserRoleUpdate,
    EnterpriseUserStatusUpdate,
    PlatformOperationsRead,
    UserGroupCreate,
    UserGroupMembershipUpdate,
    UserGroupRead,
    UserGroupUpdate,
)

router = APIRouter()


def _group_read(view: GroupView) -> UserGroupRead:
    group = view.group
    return UserGroupRead(
        id=group.id,
        tenant_id=group.tenant_id,
        name=group.name,
        description=group.description,
        active=group.active,
        version=group.version,
        member_ids=list(view.member_ids),
        member_count=len(view.member_ids),
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


@router.get("/api/v1/enterprise/overview", response_model=EnterpriseOverviewRead, tags=["enterprise"])
def enterprise_overview(request: Request, principal: PrincipalDep, session: SessionDep) -> EnterpriseOverviewRead:
    service = _enterprise_service(request, session, principal)
    return EnterpriseOverviewRead.model_validate(service.overview())


@router.get("/api/v1/enterprise/platform", response_model=PlatformOperationsRead, tags=["enterprise"])
def enterprise_platform_operations(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> PlatformOperationsRead:
    _enterprise_service(request, session, principal)
    try:
        snapshot = PlatformOperationsService(
            session,
            tenant_id=principal.tenant_id,
            settings=runtime.get_settings(),
        ).snapshot()
    except PlatformOperationsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return PlatformOperationsRead.model_validate(snapshot)


@router.get("/api/v1/enterprise/users", response_model=list[EnterpriseUserRead], tags=["enterprise"])
def list_enterprise_users(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[EnterpriseUserRead]:
    service = _enterprise_service(request, session, principal)
    return [EnterpriseUserRead.model_validate(user) for user in service.list_users()]


@router.post(
    "/api/v1/enterprise/users",
    response_model=EnterpriseUserRead,
    status_code=status.HTTP_201_CREATED,
    tags=["enterprise"],
)
def create_enterprise_user(
    payload: EnterpriseUserCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseUserRead:
    service = _enterprise_service(request, session, principal)
    user = service.create_user(
        CreateUserCommand(
            email=payload.email,
            display_name=payload.display_name,
            role=payload.role,
            auth_mode=runtime.get_settings().human_auth_mode,
            initial_password=payload.initial_password,
            oidc_issuer=payload.oidc_issuer,
            oidc_subject=payload.oidc_subject,
        )
    )
    return EnterpriseUserRead.model_validate(user)


@router.post(
    "/api/v1/enterprise/users/{user_id}/role",
    response_model=EnterpriseUserRead,
    tags=["enterprise"],
)
def update_enterprise_user_role(
    user_id: str,
    payload: EnterpriseUserRoleUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseUserRead:
    service = _enterprise_service(request, session, principal)
    user = service.update_user_role(
        user_id,
        UpdateUserRoleCommand(
            expected_token_version=payload.expected_token_version,
            role=payload.role,
            reason=payload.reason,
        ),
    )
    return EnterpriseUserRead.model_validate(user)


@router.post(
    "/api/v1/enterprise/users/{user_id}/status",
    response_model=EnterpriseUserRead,
    tags=["enterprise"],
)
def update_enterprise_user_status(
    user_id: str,
    payload: EnterpriseUserStatusUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseUserRead:
    service = _enterprise_service(request, session, principal)
    user = service.update_user_status(
        user_id,
        UpdateUserStatusCommand(
            expected_token_version=payload.expected_token_version,
            active=payload.active,
            reason=payload.reason,
        ),
    )
    return EnterpriseUserRead.model_validate(user)


@router.get("/api/v1/enterprise/groups", response_model=list[UserGroupRead], tags=["enterprise"])
def list_enterprise_groups(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[UserGroupRead]:
    service = _enterprise_service(request, session, principal)
    return [_group_read(view) for view in service.list_groups()]


def _enterprise_dataset_read(dataset: TenantDataset) -> EnterpriseDatasetRead:
    try:
        policy = EvidenceLicensePolicy.model_validate(dataset.license_policy)
        now = datetime.now(UTC)
        available_channels: tuple[DeliveryChannel, ...] = ("web", "mcp")
        channels = [channel for channel in available_channels if policy.permits(channel, now)]
        return EnterpriseDatasetRead(
            id=dataset.id,
            dataset_key=dataset.dataset_key,
            display_name=dataset.display_name,
            active=dataset.active,
            version=dataset.version,
            required_scopes=dataset.required_scopes,
            license_id=policy.license_id,
            license_policy_version=policy.policy_version,
            permitted_channels=channels,
            license_current=bool(channels),
            attribution=policy.attribution,
        )
    except ValueError:
        return EnterpriseDatasetRead(
            id=dataset.id,
            dataset_key=dataset.dataset_key,
            display_name=dataset.display_name,
            active=dataset.active,
            version=dataset.version,
            required_scopes=dataset.required_scopes,
            license_id="invalid",
            license_policy_version="invalid",
            permitted_channels=[],
            license_current=False,
            attribution="Invalid license policy",
        )


@router.get("/api/v1/enterprise/datasets", response_model=list[EnterpriseDatasetRead], tags=["enterprise"])
def list_enterprise_datasets(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> list[EnterpriseDatasetRead]:
    return [_enterprise_dataset_read(item) for item in _enterprise_service(request, session, principal).list_datasets()]


@router.post(
    "/api/v1/enterprise/datasets/{dataset_id}/status",
    response_model=EnterpriseDatasetRead,
    tags=["enterprise"],
)
def update_enterprise_dataset_status(
    dataset_id: str,
    payload: EnterpriseDatasetStatusUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseDatasetRead:
    dataset = _enterprise_service(request, session, principal).update_dataset_status(
        dataset_id,
        UpdateDatasetStatusCommand(payload.expected_version, payload.active, payload.reason),
    )
    return _enterprise_dataset_read(dataset)


@router.get("/api/v1/enterprise/sessions", response_model=list[EnterpriseSessionRead], tags=["enterprise"])
def list_enterprise_sessions(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[EnterpriseSessionRead]:
    return [
        EnterpriseSessionRead(
            id=item.session.id,
            user_id=item.user.id,
            user_display_name=item.user.display_name,
            user_email=item.user.email,
            issued_at=item.session.issued_at,
            expires_at=item.session.expires_at,
            revoked_at=item.session.revoked_at,
            revoked_by_user_id=item.session.revoked_by_user_id,
            revoke_reason=item.session.revoke_reason,
            current=item.session.id == principal.session_id,
        )
        for item in _enterprise_service(request, session, principal).list_sessions(limit=limit)
    ]


@router.post(
    "/api/v1/enterprise/sessions/{session_id}/revoke",
    response_model=EnterpriseSessionRead,
    tags=["enterprise"],
)
def revoke_enterprise_session(
    session_id: str,
    payload: EnterpriseSessionRevoke,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> EnterpriseSessionRead:
    item = _enterprise_service(request, session, principal).revoke_session(session_id, reason=payload.reason)
    return EnterpriseSessionRead(
        id=item.session.id,
        user_id=item.user.id,
        user_display_name=item.user.display_name,
        user_email=item.user.email,
        issued_at=item.session.issued_at,
        expires_at=item.session.expires_at,
        revoked_at=item.session.revoked_at,
        revoked_by_user_id=item.session.revoked_by_user_id,
        revoke_reason=item.session.revoke_reason,
        current=item.session.id == principal.session_id,
    )


@router.post(
    "/api/v1/enterprise/groups",
    response_model=UserGroupRead,
    status_code=status.HTTP_201_CREATED,
    tags=["enterprise"],
)
def create_enterprise_group(
    payload: UserGroupCreate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> UserGroupRead:
    service = _enterprise_service(request, session, principal)
    return _group_read(service.create_group(CreateGroupCommand(payload.name, payload.description)))


@router.put("/api/v1/enterprise/groups/{group_id}", response_model=UserGroupRead, tags=["enterprise"])
def update_enterprise_group(
    group_id: str,
    payload: UserGroupUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> UserGroupRead:
    service = _enterprise_service(request, session, principal)
    return _group_read(
        service.update_group(
            group_id,
            UpdateGroupCommand(
                expected_version=payload.expected_version,
                name=payload.name,
                description=payload.description,
                active=payload.active,
                reason=payload.reason,
            ),
        )
    )


@router.put(
    "/api/v1/enterprise/groups/{group_id}/members",
    response_model=UserGroupRead,
    tags=["enterprise"],
)
def update_enterprise_group_members(
    group_id: str,
    payload: UserGroupMembershipUpdate,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
) -> UserGroupRead:
    service = _enterprise_service(request, session, principal)
    return _group_read(
        service.update_group_members(
            group_id,
            UpdateGroupMembersCommand(
                expected_version=payload.expected_version,
                user_ids=tuple(payload.user_ids),
                reason=payload.reason,
            ),
        )
    )


@router.get("/api/v1/enterprise/audit-events", response_model=EnterpriseAuditPageRead, tags=["enterprise"])
def list_enterprise_audit_events(
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=200),
    cursor: str | None = Query(default=None, min_length=20, max_length=4096),
    action: str | None = Query(default=None, min_length=1, max_length=160),
    outcome: str | None = Query(default=None, min_length=1, max_length=40),
    actor_type: Literal["agent", "api_key", "user"] | None = Query(default=None),
) -> EnterpriseAuditPageRead:
    service = _enterprise_service(request, session, principal)
    page = service.list_audit_events(
        limit=limit,
        cursor=cursor,
        action=action,
        outcome=outcome,
        actor_type=actor_type,
    )
    return EnterpriseAuditPageRead(
        items=[EnterpriseAuditEventRead.model_validate(item) for item in page.items],
        next_cursor=page.next_cursor,
    )
