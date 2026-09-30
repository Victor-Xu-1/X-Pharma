from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings, get_settings
from pharma_intel.db import get_session_factory, set_tenant_context
from pharma_intel.models import (
    AgentClient,
    ApiKey,
    BillingAccount,
    BillingAccountStatus,
    DataSource,
    Entity,
    KnowledgePage,
    SourceDocument,
    Tenant,
    User,
)

_SYNTHETIC_TENANT_SLUG = re.compile(
    r"^(?:acceptance|anti-extraction-acceptance|"
    r"(?:claim|export|commercial|coverage|cross-client-risk|accounting|paid-chem|other-paid-chem|chem|governed-chem)"
    r"-[0-9a-f-]{20,})$"
)
_TEMPORARY_SOURCE_ROOT = re.compile(
    r"^(?:/tmp/(?:pytest-|pharma-)|[A-Za-z]:[\\/]Users[\\/][^\\/]+[\\/]AppData[\\/]Local[\\/]Temp[\\/])",
    re.IGNORECASE,
)
_UUID_DIRECTORY = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_TEST_CREDENTIAL_NAME = re.compile(
    r"(?:^|[-_\s])(?:acceptance|assertion|fixture|test)(?:$|[-_\s])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RuntimeHygieneFinding:
    code: str
    identifiers: list[str]

    @property
    def count(self) -> int:
        return len(self.identifiers)


@dataclass(frozen=True)
class RuntimeHygieneReport:
    status: str
    findings: list[RuntimeHygieneFinding]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "status": self.status,
            "finding_count": sum(finding.count for finding in self.findings),
            "findings": [asdict(finding) | {"count": finding.count} for finding in self.findings],
        }


def inspect_runtime_hygiene(
    session_factory: Callable[[], Session],
    settings: Settings,
) -> RuntimeHygieneReport:
    with session_factory() as session:
        tenants = list(session.scalars(select(Tenant).order_by(Tenant.id)))
    tenant_ids = {tenant.id for tenant in tenants if tenant.active}
    synthetic_tenants = sorted(
        tenant.id
        for tenant in tenants
        if tenant.active
        and (_SYNTHETIC_TENANT_SLUG.fullmatch(tenant.slug.casefold()) or tenant.name.casefold().endswith(" test"))
    )
    inactive_synthetic_tenant_content: list[str] = []

    temporary_accounts: list[str] = []
    temporary_source_roots: list[str] = []
    acceptance_fixtures: list[str] = []
    active_test_api_keys: list[str] = []
    active_test_agent_clients: list[str] = []
    active_test_billing_accounts: list[str] = []
    for tenant_id in sorted(tenant_ids):
        with session_factory() as session:
            set_tenant_context(session, tenant_id)
            temporary_accounts.extend(
                session.scalars(
                    select(User.id).where(
                        User.tenant_id == tenant_id,
                        User.normalized_email.like("%@example.test"),
                    )
                )
            )
            sources = session.scalars(select(DataSource).where(DataSource.tenant_id == tenant_id))
            temporary_source_roots.extend(
                source.id for source in sources if _TEMPORARY_SOURCE_ROOT.match(source.root_uri)
            )
            entities = session.scalars(select(Entity).where(Entity.tenant_id == tenant_id))
            acceptance_fixtures.extend(
                entity.id for entity in entities if entity.attributes.get("acceptance_fixture") is True
            )
            api_keys = session.scalars(select(ApiKey).where(ApiKey.tenant_id == tenant_id, ApiKey.active.is_(True)))
            active_test_api_keys.extend(
                api_key.id for api_key in api_keys if _TEST_CREDENTIAL_NAME.search(api_key.name)
            )
            agent_clients = session.scalars(
                select(AgentClient).where(AgentClient.tenant_id == tenant_id, AgentClient.active.is_(True))
            )
            active_test_agent_clients.extend(
                client.id
                for client in agent_clients
                if _TEST_CREDENTIAL_NAME.search(client.client_key) or _TEST_CREDENTIAL_NAME.search(client.display_name)
            )
            billing_accounts = session.scalars(
                select(BillingAccount).where(
                    BillingAccount.tenant_id == tenant_id,
                    BillingAccount.status == BillingAccountStatus.ACTIVE,
                )
            )
            active_test_billing_accounts.extend(
                account.id
                for account in billing_accounts
                if _TEST_CREDENTIAL_NAME.search(account.account_key)
                or _TEST_CREDENTIAL_NAME.search(account.display_name)
            )

    for tenant in tenants:
        if tenant.active or not (
            _SYNTHETIC_TENANT_SLUG.fullmatch(tenant.slug.casefold()) or tenant.name.casefold().endswith(" test")
        ):
            continue
        with session_factory() as session:
            set_tenant_context(session, tenant.id)
            has_content = any(
                session.scalar(select(model.id).where(model.tenant_id == tenant.id).limit(1)) is not None
                for model in (Entity, DataSource, SourceDocument, KnowledgePage)
            )
            if has_content:
                inactive_synthetic_tenant_content.append(tenant.id)

    orphan_namespaces: list[str] = []
    if settings.object_store_backend == "filesystem" and settings.object_store_root.is_dir():
        orphan_namespaces = sorted(
            child.name
            for child in settings.object_store_root.iterdir()
            if child.is_dir() and _UUID_DIRECTORY.fullmatch(child.name) and child.name not in tenant_ids
        )

    grouped = (
        ("synthetic_tenants", synthetic_tenants),
        ("inactive_synthetic_tenant_content", sorted(inactive_synthetic_tenant_content)),
        ("temporary_accounts", sorted(temporary_accounts)),
        ("temporary_source_roots", sorted(temporary_source_roots)),
        ("acceptance_fixtures", sorted(acceptance_fixtures)),
        ("active_test_api_keys", sorted(active_test_api_keys)),
        ("active_test_agent_clients", sorted(active_test_agent_clients)),
        ("active_test_billing_accounts", sorted(active_test_billing_accounts)),
        ("orphan_object_namespaces", orphan_namespaces),
    )
    findings = [
        RuntimeHygieneFinding(code=code, identifiers=identifiers) for code, identifiers in grouped if identifiers
    ]
    return RuntimeHygieneReport(status="failed" if findings else "passed", findings=findings)


def run() -> None:
    report = inspect_runtime_hygiene(get_session_factory(), get_settings())
    print(json.dumps(report.as_dict(), sort_keys=True))
    if report.status != "passed":
        raise SystemExit(1)
