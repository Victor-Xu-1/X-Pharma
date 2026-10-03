from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import httpx2
import psycopg
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent
from psycopg import sql
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from pharma_intel.commercial.admin import CommercialAdminService, ProvisionClientCommand
from pharma_intel.commercial.exports import default_export_field_policy
from pharma_intel.commercial.plans import RateCardDefinition
from pharma_intel.config import get_settings
from pharma_intel.db import set_tenant_context
from pharma_intel.models import (
    AgentClient,
    ApiKey,
    AuditEvent,
    BillingAccount,
    CommercialPolicyEvent,
    CommercialRiskPolicy,
    DataExportJob,
    Entity,
    EntityType,
    ReviewStatus,
    Tenant,
    UsageReservation,
    UsageReservationState,
    UsageSettlement,
    User,
    UserRole,
)
from pharma_intel.security import hash_password, issue_api_key, normalize_email

MCP_PROTOCOL_BASELINE = "2025-11-25"
REPORT_SCHEMA = "pharma.mcp-anti-extraction-acceptance.v1"
OUTPUT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DATABASE_NAME = re.compile(r"^pharma_anti_extract_[0-9a-f]{12}$")
MAX_PROCESS_LOG_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class DatabaseCredentials:
    admin_url: URL
    runtime_user: str
    runtime_password: str


@dataclass(frozen=True)
class Fixture:
    tenant_id: str
    primary_token: str
    related_token: str
    numeric_token: str
    numeric_related_token: str
    numeric_rotated_token: str
    related_client_id: str
    admin_email: str
    admin_password: str


class ProbeRejected(RuntimeError):
    pass


def _executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"Required executable is unavailable: {name}")
    return path


def _compose(*arguments: str, timeout: float = 30) -> str:
    completed = subprocess.run(  # noqa: S603 - executable is resolved and argv is not passed through a shell.
        [_executable("docker"), "compose", "-f", "compose.yaml", "-f", "compose.dev.yaml", *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Docker Compose command failed: {' '.join(arguments[:3])}")
    return completed.stdout.strip()


def _compose_environment(service: str, name: str) -> str:
    value = _compose("exec", "-T", service, "printenv", name)
    if not value:
        raise RuntimeError(f"{service} does not expose required runtime configuration: {name}")
    return value


def _local_database_credentials() -> DatabaseCredentials:
    if get_settings().app_env.casefold() == "production":
        raise RuntimeError("The isolated anti-extraction probe cannot run with APP_ENV=production")
    for service in ("postgres", "api"):
        container = _compose("ps", "-q", service)
        if not container:
            raise RuntimeError(f"Required Compose service is not running: {service}")
        if _compose("exec", "-T", service, "true"):
            raise RuntimeError(f"Unexpected output while checking Compose service: {service}")

    endpoint = _compose("port", "postgres", "5432")
    host, separator, port_text = endpoint.rpartition(":")
    if not separator or host not in {"127.0.0.1", "localhost", "[::1]"} or not port_text.isdigit():
        raise RuntimeError("PostgreSQL must be published on a loopback interface for this probe")
    admin_user = _compose_environment("postgres", "POSTGRES_USER")
    admin_password = _compose_environment("postgres", "POSTGRES_PASSWORD")
    admin_database = _compose_environment("postgres", "POSTGRES_DB")
    runtime = make_url(_compose_environment("api", "DATABASE_URL"))
    if runtime.get_backend_name() != "postgresql" or not runtime.username or runtime.password is None:
        raise RuntimeError("The API runtime PostgreSQL identity is incomplete")
    admin_url = URL.create(
        "postgresql+psycopg",
        username=admin_user,
        password=admin_password,
        host="127.0.0.1",
        port=int(port_text),
        database=admin_database,
    )
    _require_local_postgres(admin_url)
    return DatabaseCredentials(admin_url, runtime.username, runtime.password)


def _require_local_postgres(url: URL) -> None:
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("The anti-extraction probe requires PostgreSQL")
    if url.host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("The anti-extraction probe refuses non-loopback databases")
    if not url.database or not url.username or url.password is None:
        raise RuntimeError("The local PostgreSQL URL is incomplete")


def _psycopg_dsn(url: URL) -> str:
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _create_database(
    admin_url: URL,
    database_name: str,
    *,
    database_name_pattern: re.Pattern[str] = DATABASE_NAME,
) -> URL:
    if not database_name_pattern.fullmatch(database_name):
        raise RuntimeError("Refusing unsafe acceptance database name")
    with psycopg.connect(_psycopg_dsn(admin_url), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    return admin_url.set(database=database_name)


def _drop_database(
    admin_url: URL,
    database_name: str,
    *,
    database_name_pattern: re.Pattern[str] = DATABASE_NAME,
) -> None:
    if not database_name_pattern.fullmatch(database_name):
        raise RuntimeError("Refusing unsafe acceptance database cleanup")
    with psycopg.connect(_psycopg_dsn(admin_url), autocommit=True) as connection:
        connection.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name)))


def _runtime_url(admin_target: URL, credentials: DatabaseCredentials) -> URL:
    return admin_target.set(username=credentials.runtime_user, password=credentials.runtime_password)


def _run_checked(command: list[str], environment: dict[str, str], log_path: Path, timeout: float) -> None:
    with log_path.open("ab") as output:
        completed = subprocess.run(  # noqa: S603 - callers supply fixed acceptance commands without a shell.
            command,
            check=False,
            cwd=Path.cwd(),
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    if log_path.stat().st_size > MAX_PROCESS_LOG_BYTES:
        raise RuntimeError("Acceptance setup log exceeded its safety limit")
    if completed.returncode != 0:
        raise RuntimeError(f"Acceptance setup command failed: {command[-2:]}")


def _migrate_database(admin_target: URL, runtime_password: str, work: Path) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "development",
            "DATABASE_URL": admin_target.render_as_string(hide_password=False),
            "DATABASE_CREDENTIALS_MODE": "static",
            "POSTGRES_RUNTIME_PASSWORD": runtime_password,
        }
    )
    log_path = work / "database-setup.log"
    uv = _executable("uv")
    _run_checked([uv, "run", "--no-sync", "alembic", "upgrade", "head"], environment, log_path, 180)
    _run_checked([uv, "run", "--no-sync", "pharma-db-provision"], environment, log_path, 60)


def _seed_fixture(admin_target: URL) -> Fixture:
    engine = create_engine(admin_target, pool_pre_ping=True)
    try:
        with Session(engine, expire_on_commit=False) as session:
            tenant = Tenant(slug="anti-extraction-acceptance", name="Anti-Extraction Acceptance")
            session.add(tenant)
            session.flush()
            set_tenant_context(session, tenant.id)

            admin_email = "anti-extraction-admin@example.invalid"
            admin_password = secrets.token_urlsafe(32)
            session.add(
                User(
                    tenant_id=tenant.id,
                    email=admin_email,
                    normalized_email=normalize_email(admin_email),
                    display_name="Acceptance Security Operator",
                    password_hash=hash_password(admin_password),
                    role=UserRole.ADMIN,
                )
            )
            keys: dict[str, tuple[ApiKey, str]] = {}
            for key_name in ("primary", "related", "numeric", "numeric-related", "numeric-rotated"):
                token, token_hash = issue_api_key()
                key = ApiKey(
                    tenant_id=tenant.id,
                    name=f"anti-extraction-{key_name}",
                    prefix=token[:12],
                    secret_hash=token_hash,
                    scopes=["mcp:connect", "entities:read"],
                )
                session.add(key)
                session.flush()
                keys[key_name] = (key, token)
            session.commit()

            admin = CommercialAdminService(session, tenant, actor_id="isolated-acceptance")
            card = admin.publish_rate_card(
                RateCardDefinition.model_validate(
                    {
                        "rate_card_key": "anti-extraction-plan",
                        "revision": 1,
                        "currency": "CNY",
                        "effective_from": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
                        "items": [
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
                                "billing_class": "export.data",
                                "entitlement_key": "data.export",
                                "base_units": "10",
                                "per_result_units": "0.05",
                                "per_kib_units": "0.01",
                                "per_compute_unit": "0",
                                "max_result_rows": 5000,
                            },
                        ],
                    }
                )
            )
            clients: dict[str, AgentClient] = {}
            client_accounts = (
                ("primary", "alpha-account"),
                ("related", "alpha-account"),
                ("numeric", "numeric-account"),
                ("numeric-related", "numeric-account"),
                ("numeric-rotated", "numeric-account"),
            )
            for key_name, account_key in client_accounts:
                key = keys[key_name][0]
                subscription_key = f"anti-extraction-{key_name}-subscription"
                subscription = admin.provision_client(
                    ProvisionClientCommand(
                        client_key=f"anti-extraction-{key_name}",
                        oauth_client_id=key.id,
                        display_name=f"Anti-Extraction {key_name.title()}",
                        actor_type="api_key",
                        subject_id=key.id,
                        account_key=account_key,
                        account_name=account_key.replace("-", " ").title(),
                        subscription_key=subscription_key,
                        rate_card_key=card.rate_card_key,
                        rate_card_revision=card.revision,
                        created_by="isolated-acceptance",
                        export_field_policy=default_export_field_policy(policy_version=f"{account_key}-v1"),
                        max_page_depth=2,
                        daily_unique_record_limit=1000,
                        max_response_bytes=1_000_000,
                    )
                )
                admin.grant_credit(
                    subscription_key,
                    Decimal("1000"),
                    external_reference=f"isolated-{key_name}-credit",
                    reason="isolated anti-extraction acceptance",
                )
                client = session.get(AgentClient, subscription.agent_client_id)
                if client is None:
                    raise RuntimeError("Provisioned acceptance client is unavailable")
                clients[key_name] = client

            accounts = {
                account.account_key: account
                for account in session.scalars(select(BillingAccount).where(BillingAccount.tenant_id == tenant.id))
            }
            alpha_policy = session.scalar(
                select(CommercialRiskPolicy).where(
                    CommercialRiskPolicy.billing_account_id == accounts["alpha-account"].id
                )
            )
            numeric_policy = session.scalar(
                select(CommercialRiskPolicy).where(
                    CommercialRiskPolicy.billing_account_id == accounts["numeric-account"].id
                )
            )
            if alpha_policy is None or numeric_policy is None:
                raise RuntimeError("Acceptance risk policies were not provisioned")
            alpha_policy.partition_window_seconds = 300
            alpha_policy.max_partition_queries_per_window = 10
            alpha_policy.max_cross_client_partition_queries_per_window = 2
            alpha_policy.max_distinct_networks_per_window = 3
            numeric_policy.partition_window_seconds = 300
            numeric_policy.max_partition_queries_per_window = 2
            numeric_policy.max_cross_client_partition_queries_per_window = 2
            numeric_policy.max_distinct_credentials_per_window = 2
            for index in range(1, 7):
                session.add(
                    Entity(
                        tenant_id=tenant.id,
                        entity_type=EntityType.TARGET,
                        name=f"Acceptance probe record {index:03d}",
                        normalized_name=f"acceptance probe record {index:03d}",
                        description="Isolated security acceptance record",
                        review_status=ReviewStatus.VERIFIED,
                    )
                )
            session.commit()
            return Fixture(
                tenant_id=tenant.id,
                primary_token=keys["primary"][1],
                related_token=keys["related"][1],
                numeric_token=keys["numeric"][1],
                numeric_related_token=keys["numeric-related"][1],
                numeric_rotated_token=keys["numeric-rotated"][1],
                related_client_id=clients["related"].id,
                admin_email=admin_email,
                admin_password=admin_password,
            )
    finally:
        engine.dispose()


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


def _service_environment(runtime_url: URL, api_port: int, mcp_port: int, work: Path) -> dict[str, str]:
    environment = os.environ.copy()
    api_url = f"http://127.0.0.1:{api_port}"
    mcp_url = f"http://127.0.0.1:{mcp_port}/mcp"
    environment.update(
        {
            "APP_ENV": "development",
            "APP_HOST": "127.0.0.1",
            "APP_PORT": str(api_port),
            "PUBLIC_BASE_URL": api_url,
            "DATABASE_URL": runtime_url.render_as_string(hide_password=False),
            "SEARCH_BACKEND": "database",
            "EVIDENCE_SEARCH_BACKEND": "ragflow",
            "TEMPORAL_ENABLED": "false",
            "OTEL_ENABLED": "false",
            "HUMAN_AUTH_MODE": "local",
            "AGENT_API_BASE_URL": api_url,
            "MCP_HOST": "127.0.0.1",
            "MCP_PORT": str(mcp_port),
            "MCP_AUTH_ENABLED": "true",
            "MCP_TOKEN_VERIFIER_MODE": "api_key",
            "MCP_AUTH_ISSUER_URL": api_url,
            "MCP_RESOURCE_SERVER_URL": mcp_url,
            "MCP_CORRELATION_HMAC_SECRET": "isolated-correlation-hmac-secret-1234567890",
            "OBJECT_STORE_ROOT": str(work / "object-store"),
            "MARKDOWN_EXPORT_ROOT": str(work / "markdown-wiki"),
            "WEB_ROOT": str(work / "no-web-root"),
        }
    )
    return environment


def _start_service(command: str, environment: dict[str, str], log_path: Path) -> subprocess.Popen[bytes]:
    if command not in {"pharma-api", "pharma-gateway", "pharma-mcp"}:
        raise ValueError("Unsupported isolated service command")
    log_handle = log_path.open("wb")
    try:
        return subprocess.Popen(  # noqa: S603 - executable and service command are allowlisted above.
            [_executable("uv"), "run", "--no-sync", command],
            cwd=Path.cwd(),
            env=environment,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log_handle.close()


def _wait_for_api(api_url: str, process: subprocess.Popen[bytes], timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Isolated API process exited before readiness")
        try:
            response = httpx.get(f"{api_url}/health/ready", timeout=2, trust_env=False)
            if response.status_code == 200 and response.json().get("status") == "ready":
                return
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(0.25)
    raise RuntimeError("Isolated API readiness timed out")


def _stop_process(process: subprocess.Popen[bytes] | None) -> bool:
    if process is None or process.poll() is not None:
        return True
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    return process.poll() is not None


def _structured(result: Any) -> dict[str, Any]:
    if result.is_error:
        messages = [item.text for item in result.content if isinstance(item, TextContent)]
        summary = " ".join(messages)
        summary = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", summary)
        summary = " ".join(summary.split())[:500]
        suffix = f": {summary}" if summary else ""
        raise ProbeRejected(f"MCP tool rejected the request{suffix}")
    payload = result.structured_content
    if payload is None:
        if not result.content or not isinstance(result.content[0], TextContent):
            raise RuntimeError("MCP tool returned no structured content")
        payload = json.loads(result.content[0].text)
    if not isinstance(payload, dict):
        raise RuntimeError("MCP tool returned a non-object payload")
    return payload


async def _call_tool(
    url: str,
    token: str,
    tool: str,
    arguments: dict[str, Any],
    *,
    network_address: str = "198.51.100.10",
) -> dict[str, Any]:
    async with httpx2.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}",
            "X-Forwarded-For": network_address,
        },
        timeout=httpx2.Timeout(20),
        follow_redirects=False,
        trust_env=False,
    ) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialization = await session.initialize()
                if str(initialization.protocol_version) != MCP_PROTOCOL_BASELINE:
                    raise RuntimeError("MCP protocol baseline was not negotiated")
                return _structured(await session.call_tool(tool, arguments))


def _exception_tree_matches(error: BaseException, accepted: tuple[type[BaseException], ...]) -> bool:
    if isinstance(error, accepted):
        return True
    if isinstance(error, BaseExceptionGroup):
        return bool(error.exceptions) and all(_exception_tree_matches(child, accepted) for child in error.exceptions)
    return False


async def _expect_rejected(
    url: str,
    token: str,
    tool: str,
    arguments: dict[str, Any],
    *,
    network_address: str = "198.51.100.10",
) -> None:
    try:
        await _call_tool(url, token, tool, arguments, network_address=network_address)
    except BaseException as exc:
        if _exception_tree_matches(exc, (ProbeRejected, httpx2.HTTPError)):
            return
        raise
    raise RuntimeError(f"MCP anti-extraction scenario was not rejected: {tool}")


def _wait_for_mcp(url: str, token: str, process: subprocess.Popen[bytes], timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Isolated MCP process exited before readiness")
        try:
            asyncio.run(_call_tool(url, token, "get_commercial_access", {}))
            return
        except BaseException as exc:
            if not _exception_tree_matches(exc, (httpx2.HTTPError,)):
                raise
            time.sleep(0.25)
    raise RuntimeError("Isolated MCP readiness timed out")


def _search_arguments(query: str, *, cursor: str = "") -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "query": query,
        "limit": 1,
        "idempotency_key": f"anti-extraction-{secrets.token_hex(12)}",
        "max_billable_units": "100",
    }
    if cursor:
        arguments["cursor"] = cursor
    return arguments


async def _exercise_protocol(api_url: str, mcp_url: str, fixture: Fixture) -> dict[str, bool]:
    first = await _call_tool(mcp_url, fixture.primary_token, "search_entities", _search_arguments("acceptance"))
    first_data = first.get("data")
    first_usage = first.get("usage")
    if not isinstance(first_data, dict) or not isinstance(first_usage, dict):
        raise RuntimeError("Normal MCP search omitted data or usage")
    if len(first_data.get("items", [])) != 1 or not first_usage.get("settlement_id"):
        raise RuntimeError("Normal MCP search was not durably settled")
    first_cursor = first_data.get("next_cursor")
    if not isinstance(first_cursor, str) or not first_cursor:
        raise RuntimeError("Acceptance data did not produce a pagination cursor")
    second = await _call_tool(
        mcp_url,
        fixture.primary_token,
        "search_entities",
        _search_arguments("acceptance", cursor=first_cursor),
    )
    second_data = second.get("data")
    second_cursor = second_data.get("next_cursor") if isinstance(second_data, dict) else None
    if second_cursor is not None:
        raise RuntimeError("Licensed pagination continued beyond the configured boundary")
    await _expect_rejected(
        mcp_url,
        fixture.primary_token,
        "search_entities",
        _search_arguments("acceptance", cursor=f"{first_cursor}x"),
    )

    await _call_tool(mcp_url, fixture.primary_token, "search_entities", _search_arguments("A"))
    await _call_tool(mcp_url, fixture.related_token, "search_entities", _search_arguments("B"))
    await _expect_rejected(mcp_url, fixture.primary_token, "search_entities", _search_arguments("C"))

    await _call_tool(mcp_url, fixture.numeric_token, "search_entities", _search_arguments("0"))
    await _call_tool(mcp_url, fixture.numeric_token, "search_entities", _search_arguments("1"))
    await _expect_rejected(mcp_url, fixture.numeric_token, "search_entities", _search_arguments("2"))

    await _call_tool(
        mcp_url,
        fixture.primary_token,
        "search_entities",
        _search_arguments("network rotation"),
        network_address="198.51.101.10",
    )
    await _call_tool(
        mcp_url,
        fixture.primary_token,
        "search_entities",
        _search_arguments("network rotation"),
        network_address="198.51.102.10",
    )
    await _expect_rejected(
        mcp_url,
        fixture.primary_token,
        "search_entities",
        _search_arguments("network rotation"),
        network_address="198.51.103.10",
    )

    await _call_tool(
        mcp_url,
        fixture.numeric_related_token,
        "search_entities",
        _search_arguments("credential rotation"),
    )
    await _expect_rejected(
        mcp_url,
        fixture.numeric_rotated_token,
        "search_entities",
        _search_arguments("credential rotation"),
    )

    await _expect_rejected(
        mcp_url,
        fixture.primary_token,
        "create_data_export",
        {
            "dataset": "entities",
            "idempotency_key": f"anti-extraction-export-{secrets.token_hex(10)}",
            "max_billable_units": "100",
            "fields": ["id", "name"],
            "max_records": 10,
        },
    )

    async with httpx.AsyncClient(base_url=api_url, timeout=20, follow_redirects=False, trust_env=False) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": fixture.admin_email, "password": fixture.admin_password},
        )
        login.raise_for_status()
        risks = await client.get("/api/v1/commercial/risk-events", params={"case_status": "open"})
        risks.raise_for_status()
        reasons = {item.get("reason_code") for item in risks.json() if isinstance(item, dict)}
        expected_reasons = {
            "cross_client_partition_enumeration_detected",
            "partition_enumeration_detected",
            "network_rotation_limit_exceeded",
            "credential_rotation_limit_exceeded",
        }
        if not expected_reasons.issubset(reasons):
            raise RuntimeError("Human risk console omitted anti-extraction events")
        csrf = client.cookies.get("pharma_csrf")
        if not csrf:
            raise RuntimeError("Human security session omitted CSRF protection")
        revoked = await client.post(
            f"/api/v1/commercial/clients/{fixture.related_client_id}/status",
            headers={"X-CSRF-Token": csrf},
            json={"active": False, "reason": "isolated credential revocation acceptance"},
        )
        revoked.raise_for_status()
        if revoked.json().get("active") is not False:
            raise RuntimeError("Commercial credential revocation did not persist")
    await _expect_rejected(mcp_url, fixture.related_token, "get_commercial_access", {})
    return {
        "normal_mcp_query_settled": True,
        "deep_pagination_continuation_withheld": True,
        "tampered_pagination_cursor_denied": True,
        "alphabet_partition_cross_client_denied": True,
        "numeric_partition_denied": True,
        "network_rotation_denied": True,
        "credential_rotation_denied": True,
        "unauthorized_export_denied": True,
        "risk_events_visible_to_human_operator": True,
        "credential_revocation_enforced": True,
    }


def _verify_database(admin_target: URL, fixture: Fixture) -> dict[str, int | bool]:
    engine = create_engine(admin_target, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            set_tenant_context(session, fixture.tenant_id)
            denial_events = session.scalars(
                select(CommercialPolicyEvent).where(
                    CommercialPolicyEvent.tenant_id == fixture.tenant_id,
                    CommercialPolicyEvent.decision == "deny",
                )
            ).all()
            deny_reasons = {event.reason_code for event in denial_events}
            expected = {
                "cross_client_partition_enumeration_detected",
                "partition_enumeration_detected",
                "network_rotation_limit_exceeded",
                "credential_rotation_limit_exceeded",
            }
            if not expected.issubset(deny_reasons):
                raise RuntimeError("Durable policy-event ledger omitted anti-extraction denials")
            hash_fields = ("query_shape_sha256", "partition_token_sha256", "argument_path_sha256")
            raw_argument_fields = {"q", "query", "prefix", "letter", "range_start", "range_end"}
            for event in denial_events:
                if event.reason_code not in {
                    "cross_client_partition_enumeration_detected",
                    "partition_enumeration_detected",
                }:
                    continue
                if not re.fullmatch(r"[0-9a-f]{64}", event.query_sha256):
                    raise RuntimeError("Commercial denial stored an invalid query digest")
                if raw_argument_fields.intersection(event.details):
                    raise RuntimeError("Commercial denial persisted a raw partition argument")
                if any(
                    not isinstance(event.details.get(field), str)
                    or re.fullmatch(r"[0-9a-f]{64}", event.details[field]) is None
                    for field in hash_fields
                ):
                    raise RuntimeError("Commercial denial did not persist hashed risk signals")
            correlation_events = [
                event
                for event in denial_events
                if event.reason_code in {"network_rotation_limit_exceeded", "credential_rotation_limit_exceeded"}
            ]
            if len(correlation_events) != 2:
                raise RuntimeError("Commercial denial ledger omitted correlation risk events")
            for event in correlation_events:
                fingerprint_key = (
                    "network_fingerprint"
                    if event.reason_code == "network_rotation_limit_exceeded"
                    else "credential_fingerprint"
                )
                if re.fullmatch(r"[0-9a-f]{64}", str(event.details.get(fingerprint_key))) is None:
                    raise RuntimeError("Commercial correlation denial omitted its HMAC fingerprint")
                if any(raw in str(event.details) for raw in ("198.51.101", "198.51.102", "198.51.103")):
                    raise RuntimeError("Commercial correlation denial persisted a raw network address")
            active_reservations = int(
                session.scalar(
                    select(func.count())
                    .select_from(UsageReservation)
                    .where(
                        UsageReservation.tenant_id == fixture.tenant_id,
                        UsageReservation.state == UsageReservationState.RESERVED,
                    )
                )
                or 0
            )
            settlements = int(
                session.scalar(
                    select(func.count())
                    .select_from(UsageSettlement)
                    .where(UsageSettlement.tenant_id == fixture.tenant_id)
                )
                or 0
            )
            export_jobs = int(
                session.scalar(
                    select(func.count()).select_from(DataExportJob).where(DataExportJob.tenant_id == fixture.tenant_id)
                )
                or 0
            )
            revocations = int(
                session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.tenant_id == fixture.tenant_id,
                        AuditEvent.action == "commercial.client.revoke",
                    )
                )
                or 0
            )
            related_active = session.scalar(
                select(AgentClient.active).where(AgentClient.id == fixture.related_client_id)
            )
            if active_reservations != 0 or settlements < 9 or export_jobs != 0 or revocations != 1:
                raise RuntimeError("Anti-extraction database invariants did not hold")
            if related_active is not False:
                raise RuntimeError("Revoked commercial client remained active")
            return {
                "durable_denial_reason_count": len(expected),
                "successful_settlement_count": settlements,
                "active_reservations_after": active_reservations,
                "unauthorized_export_jobs_created": export_jobs,
                "credential_revocation_audit_events": revocations,
                "raw_partition_values_persisted": False,
                "raw_correlation_values_persisted": False,
            }
    finally:
        engine.dispose()


def _atomic_write(path: Path, document: dict[str, Any]) -> None:
    if not OUTPUT_NAME.fullmatch(path.name):
        raise ValueError("Output filename contains unsupported characters")
    path.parent.mkdir(parents=True, exist_ok=True)
    path = path.parent.resolve() / path.name
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"Refusing to overwrite anti-extraction evidence: {path}")
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise FileExistsError(f"Refusing to overwrite anti-extraction evidence: {path}") from exc
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def execute(output: Path) -> dict[str, Any]:
    started = time.monotonic()
    credentials = _local_database_credentials()
    database_name = f"pharma_anti_extract_{secrets.token_hex(6)}"
    work = Path(tempfile.mkdtemp(prefix="pharma-anti-extraction-"))
    admin_target: URL | None = None
    api_process: subprocess.Popen[bytes] | None = None
    mcp_process: subprocess.Popen[bytes] | None = None
    failure: BaseException | None = None
    assertions: dict[str, bool] = {}
    database_result: dict[str, int | bool] = {}
    fixture: Fixture | None = None
    cleanup = {"api_stopped": False, "mcp_stopped": False, "database_dropped": False}
    try:
        admin_target = _create_database(credentials.admin_url, database_name)
        _migrate_database(admin_target, credentials.runtime_password, work)
        fixture = _seed_fixture(admin_target)
        gateway_port = _available_port()
        environment = _service_environment(
            _runtime_url(admin_target, credentials),
            gateway_port,
            gateway_port,
            work,
        )
        api_process = _start_service("pharma-gateway", environment, work / "gateway.log")
        mcp_process = api_process
        api_url = f"http://127.0.0.1:{gateway_port}"
        _wait_for_api(api_url, api_process)
        mcp_url = f"http://127.0.0.1:{gateway_port}/mcp"
        _wait_for_mcp(mcp_url, fixture.primary_token, mcp_process)
        assertions = asyncio.run(_exercise_protocol(api_url, mcp_url, fixture))
        database_result = _verify_database(admin_target, fixture)
    except BaseException as exc:
        failure = exc
    finally:
        cleanup["mcp_stopped"] = _stop_process(mcp_process)
        cleanup["api_stopped"] = _stop_process(api_process)
        try:
            if admin_target is not None:
                _drop_database(credentials.admin_url, database_name)
                cleanup["database_dropped"] = True
        except BaseException as exc:
            failure = failure or exc
        for log_name in ("database-setup.log", "gateway.log"):
            log = work / log_name
            if log.exists() and log.stat().st_size > MAX_PROCESS_LOG_BYTES:
                failure = failure or RuntimeError(f"Acceptance process log exceeded its safety limit: {log_name}")
        expected_parent = Path(tempfile.gettempdir()).resolve()
        if work.parent.resolve() != expected_parent or not work.name.startswith("pharma-anti-extraction-"):
            failure = failure or RuntimeError("Refusing unsafe acceptance workspace cleanup")
        else:
            shutil.rmtree(work)
    if failure is not None:
        raise RuntimeError(f"Isolated MCP anti-extraction acceptance failed: {type(failure).__name__}") from failure
    if not all(cleanup.values()):
        raise RuntimeError("Isolated MCP anti-extraction cleanup was incomplete")
    assertions.update(
        {
            "no_active_reservations_after": database_result["active_reservations_after"] == 0,
            "no_unauthorized_export_created": database_result["unauthorized_export_jobs_created"] == 0,
            "isolated_database_destroyed": cleanup["database_dropped"],
            "credentials_absent_from_report": True,
        }
    )
    report = {
        "schema": REPORT_SCHEMA,
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "environment": "local-wsl-isolated-postgresql",
        "production_claim": False,
        "controlled_fixture": True,
        "credentials_recorded": False,
        "auth_profile": "isolated-database-api-key",
        "production_oidc_covered": False,
        "protocol_version": MCP_PROTOCOL_BASELINE,
        "scenarios": {
            "normal_billed_query": "passed",
            "deep_pagination": "bounded-and-tamper-denied",
            "alphabet_partition_across_clients": "denied",
            "numeric_partition": "denied",
            "network_rotation": "denied",
            "credential_rotation": "denied",
            "unauthorized_export": "denied",
            "credential_after_revocation": "denied",
            "human_risk_console": "passed",
        },
        "database": database_result,
        "cleanup": cleanup,
        "assertions": assertions,
        "duration_seconds": round(time.monotonic() - started, 3),
    }
    if fixture is None:
        raise RuntimeError("Acceptance fixture was unavailable after a successful run")
    serialized_report = json.dumps(report, sort_keys=True)
    secret_values = (
        fixture.primary_token,
        fixture.related_token,
        fixture.numeric_token,
        fixture.numeric_related_token,
        fixture.numeric_rotated_token,
        fixture.admin_password,
    )
    if any(secret in serialized_report for secret in secret_values):
        raise RuntimeError("Acceptance report contains a generated credential")
    _atomic_write(output, report)
    return report


def run() -> None:
    parser = argparse.ArgumentParser(
        description="Run destructive-pattern MCP probes against an isolated, disposable local PostgreSQL database"
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = execute(args.output)
    print(
        "MCP_ANTI_EXTRACTION "
        f"status={report['status']} scenarios={len(report['scenarios'])} "
        f"database_dropped={str(report['cleanup']['database_dropped']).lower()} "
        "credentials_recorded=false production_claim=false"
    )
    print(f"anti_extraction_report={args.output.resolve()}")


if __name__ == "__main__":
    run()
