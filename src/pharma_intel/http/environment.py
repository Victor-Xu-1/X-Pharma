from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.enterprise_access import _enterprise_service
from pharma_intel.platform.environment import environment_plan, environment_snapshot, record_environment_plan
from pharma_intel.schemas.environment import EnvironmentInstallPlanRead, EnvironmentPlanCreate, EnvironmentRead

router = APIRouter()


@router.get("/api/v1/enterprise/environment", response_model=EnvironmentRead, tags=["environment"])
def read_environment(request: Request, principal: PrincipalDep, session: SessionDep) -> EnvironmentRead:
    _enterprise_service(request, session, principal)
    return environment_snapshot(runtime.get_settings())


@router.post("/api/v1/enterprise/environment/plans", response_model=EnvironmentInstallPlanRead, tags=["environment"])
def prepare_environment_installation(
    payload: EnvironmentPlanCreate, request: Request, principal: PrincipalDep, session: SessionDep
) -> EnvironmentInstallPlanRead:
    _enterprise_service(request, session, principal)
    try:
        plan = environment_plan(runtime.get_settings(), payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_environment_plan(
        session,
        tenant_id=principal.tenant_id,
        actor_id=principal.actor_id,
        request_id=request.state.request_id,
        plan=plan,
    )
    return plan
