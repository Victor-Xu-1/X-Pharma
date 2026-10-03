"""Provision and remove the commercial contract used by local MCP acceptance.

The interoperability probe must exercise the same paid MCP path as a customer.
This helper uses the production commercial administration service for setup and
performs explicit, scoped teardown for the disposable acceptance contract.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from pharma_intel.commercial.admin import CommercialAdminService, ProvisionClientCommand
from pharma_intel.commercial.exports import default_export_field_policy
from pharma_intel.commercial.plans import RateCardDefinition
from pharma_intel.db import get_session_factory, set_tenant_context
from pharma_intel.models import (
    AgentClient,
    ApiKey,
    Tenant,
)

PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,16}$")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seed",))
    parser.add_argument("--api-key-prefix", required=True)
    return parser.parse_args()


def _suffix(prefix: str) -> str:
    if PREFIX_PATTERN.fullmatch(prefix) is None:
        raise ValueError("api-key prefix is not a safe acceptance identifier")
    normalized = re.sub(r"[^a-z0-9]", "", prefix.casefold())
    if len(normalized) < 8:
        raise ValueError("api-key prefix is too short after normalization")
    return normalized


def _contract_names(prefix: str) -> dict[str, str]:
    suffix = _suffix(prefix)
    base = f"mcp-interoperability-{suffix}"
    return {
        "actor_id": base,
        "client_key": f"{base}-client",
        "account_key": f"{base}-account",
        "subscription_key": f"{base}-subscription",
        "rate_card_key": f"{base}-plan",
        "credit_reference": f"{base}-credit",
    }


def _tenant_and_key(session: Any, prefix: str) -> tuple[Tenant, ApiKey]:
    keys = session.scalars(
        select(ApiKey).where(
            ApiKey.prefix == prefix,
            ApiKey.active.is_(True),
            ApiKey.revoked_at.is_(None),
        )
    ).all()
    if len(keys) != 1:
        raise RuntimeError("acceptance API key prefix did not resolve to exactly one active key")
    key = keys[0]
    tenant = session.get(Tenant, key.tenant_id)
    if tenant is None:
        raise RuntimeError("acceptance API key tenant is unavailable")
    set_tenant_context(session, tenant.id)
    return tenant, key


def _definition(rate_card_key: str) -> RateCardDefinition:
    return RateCardDefinition.model_validate(
        {
            "rate_card_key": rate_card_key,
            "revision": 1,
            "currency": "CNY",
            "effective_from": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "items": [
                {
                    "billing_class": "entity.read",
                    "entitlement_key": "entities.read",
                    "base_units": "1",
                    "per_result_units": "0.01",
                    "per_kib_units": "0.001",
                    "per_compute_unit": "0",
                    "max_result_rows": 1,
                },
                {
                    "billing_class": "entity.search",
                    "entitlement_key": "entities.read",
                    "base_units": "1",
                    "per_result_units": "0.01",
                    "per_kib_units": "0.001",
                    "per_compute_unit": "0",
                    "max_result_rows": 100,
                },
                {
                    "billing_class": "target.profile",
                    "entitlement_key": "targets.read",
                    "base_units": "1",
                    "per_result_units": "0.01",
                    "per_kib_units": "0.001",
                    "per_compute_unit": "0",
                    "max_result_rows": 100,
                },
                {
                    "billing_class": "pipeline.search",
                    "entitlement_key": "pipelines.read",
                    "base_units": "1",
                    "per_result_units": "0.01",
                    "per_kib_units": "0.001",
                    "per_compute_unit": "0",
                    "max_result_rows": 100,
                },
                {
                    "billing_class": "evidence.search",
                    "entitlement_key": "evidence.read",
                    "base_units": "1",
                    "per_result_units": "0.01",
                    "per_kib_units": "0.001",
                    "per_compute_unit": "0",
                    "max_result_rows": 100,
                },
            ],
        }
    )


def seed(prefix: str) -> None:
    names = _contract_names(prefix)
    with get_session_factory()() as session:
        tenant, key = _tenant_and_key(session, prefix)
        existing = session.scalar(
            select(AgentClient).where(
                AgentClient.tenant_id == tenant.id,
                AgentClient.client_key == names["client_key"],
            )
        )
        if existing is not None:
            raise RuntimeError("acceptance commercial client already exists; cleanup the previous run first")
        admin = CommercialAdminService(session, tenant, actor_id=names["actor_id"])
        definition = _definition(names["rate_card_key"])
        card = admin.publish_rate_card(definition)
        subscription = admin.provision_client(
            ProvisionClientCommand(
                client_key=names["client_key"],
                oauth_client_id=key.id,
                display_name="MCP interoperability acceptance client",
                actor_type="api_key",
                subject_id=key.id,
                account_key=names["account_key"],
                account_name="MCP interoperability acceptance account",
                subscription_key=names["subscription_key"],
                rate_card_key=card.rate_card_key,
                rate_card_revision=card.revision,
                created_by=names["actor_id"],
                export_field_policy=default_export_field_policy(
                    policy_version=f"{names['client_key']}-fields-v1",
                    attribution="Isolated MCP interoperability acceptance",
                ),
                max_page_depth=10,
                daily_unique_record_limit=5000,
                max_response_bytes=2_000_000,
            )
        )
        grant = admin.grant_credit(
            names["subscription_key"],
            Decimal("1000"),
            external_reference=names["credit_reference"],
            reason="Isolated MCP interoperability acceptance",
        )
        print(
            json.dumps(
                {
                    "status": "seeded",
                    "tenant_id": tenant.id,
                    "api_key_id": key.id,
                    "agent_client_id": subscription.agent_client_id,
                    "subscription_id": subscription.id,
                    "rate_card_version_id": card.id,
                    "credit_grant_id": grant.id,
                    "client_key": names["client_key"],
                },
                sort_keys=True,
            )
        )


def main() -> None:
    args = _args()
    seed(args.api_key_prefix)


if __name__ == "__main__":
    main()
