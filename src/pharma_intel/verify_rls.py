from __future__ import annotations

import json

from sqlalchemy import func, select, text

from pharma_intel.db import get_engine, get_session_factory, set_tenant_context
from pharma_intel.models import Entity, Tenant


def verify() -> dict[str, object]:
    engine = get_engine()
    with engine.connect() as connection:
        role = connection.execute(
            text("SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
        tenant_id = connection.scalar(select(Tenant.id).limit(1))
        if not tenant_id:
            raise RuntimeError("RLS verification requires at least one tenant")
        no_context_rows = connection.scalar(select(func.count()).select_from(Entity))
        connection.execute(
            text(
                "SELECT set_config('app.tenant_id', :tenant_id, true), "
                "set_config('app.tenant_signature', 'forged', true)"
            ),
            {"tenant_id": tenant_id},
        )
        forged_context_rows = connection.scalar(select(func.count()).select_from(Entity))
        forged_identity = connection.scalar(text("SELECT public.app_current_tenant_id()"))

    with get_session_factory()() as session:
        set_tenant_context(session, tenant_id)
        signed_identity = session.scalar(text("SELECT public.app_current_tenant_id()"))
        signed_context_rows = session.scalar(select(func.count()).select_from(Entity))

    passed = bool(
        role.rolsuper is False
        and role.rolbypassrls is False
        and no_context_rows == 0
        and forged_context_rows == 0
        and forged_identity is None
        and signed_identity == tenant_id
    )
    result: dict[str, object] = {
        "runtime_role": role.rolname,
        "superuser": role.rolsuper,
        "bypass_rls": role.rolbypassrls,
        "no_context_rows": no_context_rows,
        "forged_context_rows": forged_context_rows,
        "signed_context_rows": signed_context_rows,
        "signed_context_valid": signed_identity == tenant_id,
        "passed": passed,
    }
    if not passed:
        raise RuntimeError(f"RLS verification failed: {json.dumps(result, sort_keys=True)}")
    return result


def run() -> None:
    print(json.dumps(verify(), sort_keys=True))


if __name__ == "__main__":
    run()
