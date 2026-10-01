from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from pharma_intel.db import get_session_factory, set_tenant_context
from pharma_intel.models import (
    AgentClient,
    ApiKey,
    BillingAccount,
    BillingAccountStatus,
    Entity,
    Tenant,
    User,
)
from pharma_intel.runtime_hygiene import _SYNTHETIC_TENANT_SLUG, _TEST_CREDENTIAL_NAME

CONFIRMATION = "CLEAN_SYNTHETIC_RUNTIME_DATA"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def cleanup_runtime_hygiene(
    session_factory: Callable[[], Session],
    *,
    backup_sha256: str,
) -> dict[str, Any]:
    if SHA256_PATTERN.fullmatch(backup_sha256) is None:
        raise ValueError("A lowercase SHA-256 for the verified pre-cleanup backup is required")
    with session_factory() as session:
        tenants = list(session.scalars(select(Tenant).order_by(Tenant.id)))
        default_tenant = session.scalar(select(Tenant).where(Tenant.slug == "default"))
        if default_tenant is None:
            raise RuntimeError("Default tenant is required for runtime hygiene cleanup")
        set_tenant_context(session, default_tenant.id)
        fixture_entity_ids = list(
            session.scalars(
                select(Entity.id).where(
                    Entity.tenant_id == default_tenant.id,
                    Entity.attributes["acceptance_fixture"].as_boolean().is_(True),
                )
            )
        )
        temporary_user_ids = list(
            session.scalars(
                select(User.id).where(
                    User.home_tenant_id == default_tenant.id,
                    User.normalized_email.like("e2e-%@example.test"),
                )
            )
        )
    if fixture_entity_ids or temporary_user_ids:
        raise RuntimeError(
            "Shared-tenant browser fixtures require the privileged recovery command: "
            "scripts/run-browser-acceptance.sh --recover-interrupted-run"
        )
    synthetic = [
        tenant
        for tenant in tenants
        if _SYNTHETIC_TENANT_SLUG.fullmatch(tenant.slug.casefold()) or tenant.name.casefold().endswith(" test")
    ]
    deleted_by_table: dict[str, int] = {}
    for tenant in synthetic:
        with session_factory() as session:
            set_tenant_context(session, tenant.id)
            api_keys = session.execute(
                update(ApiKey).where(ApiKey.tenant_id == tenant.id, ApiKey.active.is_(True)).values(active=False)
            )
            clients = session.execute(
                update(AgentClient)
                .where(AgentClient.tenant_id == tenant.id, AgentClient.active.is_(True))
                .values(active=False)
            )
            billing = session.execute(
                update(BillingAccount)
                .where(
                    BillingAccount.tenant_id == tenant.id,
                    BillingAccount.status == BillingAccountStatus.ACTIVE,
                )
                .values(status=BillingAccountStatus.SUSPENDED)
            )
            if api_keys.rowcount:
                deleted_by_table["api_keys_deactivated"] = (
                    deleted_by_table.get("api_keys_deactivated", 0) + api_keys.rowcount
                )
            if clients.rowcount:
                deleted_by_table["agent_clients_deactivated"] = (
                    deleted_by_table.get("agent_clients_deactivated", 0) + clients.rowcount
                )
            if billing.rowcount:
                deleted_by_table["billing_accounts_suspended"] = (
                    deleted_by_table.get("billing_accounts_suspended", 0) + billing.rowcount
                )
            session.commit()
        with session_factory() as session:
            result = session.execute(update(Tenant).where(Tenant.id == tenant.id).values(active=False))
            if result.rowcount != 1:
                raise RuntimeError("Synthetic tenant disappeared during quarantine")
            session.commit()
            deleted_by_table["tenants_quarantined"] = deleted_by_table.get("tenants_quarantined", 0) + 1

    with session_factory() as session:
        set_tenant_context(session, default_tenant.id)
        test_api_key_ids = [
            item.id
            for item in session.scalars(
                select(ApiKey).where(ApiKey.tenant_id == default_tenant.id, ApiKey.active.is_(True))
            )
            if _TEST_CREDENTIAL_NAME.search(item.name)
        ]
        if test_api_key_ids:
            result = session.execute(
                update(ApiKey)
                .where(ApiKey.tenant_id == default_tenant.id, ApiKey.id.in_(test_api_key_ids))
                .values(active=False)
            )
            deleted_by_table["api_keys_deactivated"] = result.rowcount

        test_client_ids = [
            item.id
            for item in session.scalars(
                select(AgentClient).where(AgentClient.tenant_id == default_tenant.id, AgentClient.active.is_(True))
            )
            if _TEST_CREDENTIAL_NAME.search(item.client_key) or _TEST_CREDENTIAL_NAME.search(item.display_name)
        ]
        if test_client_ids:
            result = session.execute(
                update(AgentClient)
                .where(AgentClient.tenant_id == default_tenant.id, AgentClient.id.in_(test_client_ids))
                .values(active=False)
            )
            deleted_by_table["agent_clients_deactivated"] = result.rowcount

        test_billing_ids = [
            item.id
            for item in session.scalars(
                select(BillingAccount).where(
                    BillingAccount.tenant_id == default_tenant.id,
                    BillingAccount.status == BillingAccountStatus.ACTIVE,
                )
            )
            if _TEST_CREDENTIAL_NAME.search(item.account_key) or _TEST_CREDENTIAL_NAME.search(item.display_name)
        ]
        if test_billing_ids:
            result = session.execute(
                update(BillingAccount)
                .where(BillingAccount.tenant_id == default_tenant.id, BillingAccount.id.in_(test_billing_ids))
                .values(status=BillingAccountStatus.SUSPENDED)
            )
            deleted_by_table["billing_accounts_suspended"] = result.rowcount
        session.commit()

    return {
        "schema": "pharma.runtime-cleanup.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "backup_sha256": backup_sha256,
        "synthetic_tenant_ids_quarantined": sorted(tenant.id for tenant in synthetic),
        "fixture_entity_ids": sorted(fixture_entity_ids),
        "temporary_user_ids": sorted(temporary_user_ids),
        "test_api_key_ids": sorted(test_api_key_ids),
        "test_agent_client_ids": sorted(test_client_ids),
        "test_billing_account_ids": sorted(test_billing_ids),
        "affected_rows": dict(sorted(deleted_by_table.items())),
    }


def run() -> None:
    parser = argparse.ArgumentParser(
        description="Quarantine explicitly identified synthetic runtime state; shared browser fixtures require recovery"
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--backup-sha256", default="")
    args = parser.parse_args()
    if not args.apply or args.confirmation != CONFIRMATION:
        parser.error(f"cleanup requires --apply --confirmation {CONFIRMATION}")
    report = cleanup_runtime_hygiene(get_session_factory(), backup_sha256=args.backup_sha256)
    payload = json.dumps(report, sort_keys=True, separators=(",", ":"))
    print(payload)
    print(hashlib.sha256(payload.encode()).hexdigest())
