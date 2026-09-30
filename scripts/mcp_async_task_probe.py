from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import re
import secrets
import subprocess
import tempfile
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from pharma_intel.commercial.admin import CommercialAdminService, ProvisionClientCommand
from pharma_intel.commercial.exports import build_export_service, default_export_field_policy
from pharma_intel.commercial.plans import RateCardDefinition
from pharma_intel.config import Settings, get_settings
from pharma_intel.db import set_tenant_context
from pharma_intel.models import (
    ApiKey,
    DataExportJob,
    Entity,
    EntityType,
    Tenant,
    UsageReservation,
    UsageReservationState,
    UsageSettlement,
)
from pharma_intel.security import issue_api_key

try:
    from scripts.mcp_anti_extraction_probe import (
        MCP_PROTOCOL_BASELINE,
        ProbeRejected,
        _available_port,
        _call_tool,
        _create_database,
        _drop_database,
        _exception_tree_matches,
        _local_database_credentials,
        _migrate_database,
        _runtime_url,
        _service_environment,
        _start_service,
        _stop_process,
        _wait_for_api,
        _wait_for_mcp,
    )
except ModuleNotFoundError as exc:
    if exc.name != "scripts":
        raise
    from mcp_anti_extraction_probe import (  # type: ignore[no-redef,import-not-found]
        MCP_PROTOCOL_BASELINE,
        ProbeRejected,
        _available_port,
        _call_tool,
        _create_database,
        _drop_database,
        _exception_tree_matches,
        _local_database_credentials,
        _migrate_database,
        _runtime_url,
        _service_environment,
        _start_service,
        _stop_process,
        _wait_for_api,
        _wait_for_mcp,
    )

REPORT_SCHEMA = "pharma.mcp-async-task-interoperability.v1"
DATABASE_NAME = re.compile(r"^pharma_mcp_async_task_[0-9a-f]{12}$")
OUTPUT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
EXPORT_FIELDS = ("id", "entity_type", "name")

ToolCall = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class Fixture:
    tenant_id: str
    inspector_token: str
    sdk_token: str


@dataclass(frozen=True)
class ClientAdapter:
    name: str
    version: str
    call: ToolCall


def _seed_fixture(database_url: URL) -> Fixture:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine, expire_on_commit=False) as session:
            tenant = Tenant(slug="mcp-async-task-acceptance", name="MCP Async Task Acceptance")
            session.add(tenant)
            session.flush()
            set_tenant_context(session, tenant.id)

            credentials: dict[str, tuple[ApiKey, str]] = {}
            for client_name in ("inspector", "python-sdk"):
                token, token_hash = issue_api_key()
                api_key = ApiKey(
                    tenant_id=tenant.id,
                    name=f"mcp-async-task-{client_name}",
                    prefix=token[:12],
                    secret_hash=token_hash,
                    scopes=["mcp:connect", "data:export"],
                )
                session.add(api_key)
                session.flush()
                credentials[client_name] = (api_key, token)
            session.commit()

            admin = CommercialAdminService(session, tenant, actor_id="isolated-mcp-async-task")
            card = admin.publish_rate_card(
                RateCardDefinition.model_validate(
                    {
                        "rate_card_key": "mcp-async-task-plan",
                        "revision": 1,
                        "currency": "CNY",
                        "effective_from": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
                        "items": [
                            {
                                "billing_class": "export.data",
                                "entitlement_key": "data.export",
                                "base_units": "2",
                                "per_result_units": "0.02",
                                "per_kib_units": "0.001",
                                "per_compute_unit": "0",
                                "max_result_rows": 5000,
                            }
                        ],
                    }
                )
            )
            for client_name, (api_key, _) in credentials.items():
                subscription_key = f"mcp-async-task-{client_name}-subscription"
                admin.provision_client(
                    ProvisionClientCommand(
                        client_key=f"mcp-async-task-{client_name}",
                        oauth_client_id=api_key.id,
                        display_name=f"MCP Async Task {client_name}",
                        actor_type="api_key",
                        subject_id=api_key.id,
                        account_key="mcp-async-task-account",
                        account_name="MCP Async Task Account",
                        subscription_key=subscription_key,
                        rate_card_key=card.rate_card_key,
                        rate_card_revision=card.revision,
                        created_by="isolated-mcp-async-task",
                        export_field_policy=default_export_field_policy(
                            policy_version="mcp-async-task-fields-v1",
                            attribution="Isolated interoperability fixture",
                        ),
                    )
                )
                admin.grant_credit(
                    subscription_key,
                    Decimal("100"),
                    external_reference=f"isolated-{client_name}-credit",
                    reason="isolated MCP async task interoperability",
                )

            for index in range(1, 3):
                session.add(
                    Entity(
                        tenant_id=tenant.id,
                        entity_type=EntityType.TARGET,
                        name=f"MCP async task target {index}",
                        normalized_name=f"mcp async task target {index}",
                        description="Isolated MCP asynchronous export fixture",
                    )
                )
            session.commit()
            return Fixture(
                tenant_id=tenant.id,
                inspector_token=credentials["inspector"][1],
                sdk_token=credentials["python-sdk"][1],
            )
    finally:
        engine.dispose()


def _safe_inspector_error(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, list) and content and isinstance(content[0], dict):
        return " ".join(str(content[0].get("text", "tool error")).split())[:500]
    return "tool error"


def _structured_inspector(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("isError") is True:
        raise ProbeRejected(f"MCP Inspector rejected the request: {_safe_inspector_error(payload)}")
    structured = payload.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    content = payload.get("content")
    if not isinstance(content, list) or not content or not isinstance(content[0], dict):
        raise RuntimeError("MCP Inspector returned no structured content")
    text = content[0].get("text")
    if not isinstance(text, str):
        raise RuntimeError("MCP Inspector text content is missing")
    decoded = json.loads(text)
    if not isinstance(decoded, dict):
        raise RuntimeError("MCP Inspector returned a non-object tool result")
    return decoded


def _run_inspector_tool(
    node: Path,
    cli: Path,
    url: str,
    token: str,
    tool: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    command = [
        str(node),
        str(cli),
        "--cli",
        url,
        "--transport",
        "http",
        "--method",
        "tools/call",
        "--tool-name",
        tool,
    ]
    if arguments:
        command.append("--tool-arg")
        command.extend(f"{key}={json.dumps(value, separators=(',', ':'))}" for key, value in arguments.items())
    command.extend(["--header", f"Authorization: Bearer {token}"])
    environment = os.environ.copy()
    environment["PATH"] = f"{node.parent}{os.pathsep}{environment.get('PATH', '')}"
    completed = subprocess.run(  # noqa: S603 - executable paths and argv are validated by the caller.
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=cli.parent,
        env=environment,
    )
    if completed.returncode:
        detail = f"{completed.stdout}\n{completed.stderr}".replace(token, "[REDACTED]")
        raise RuntimeError(f"MCP Inspector export call failed: {' '.join(detail.split())[:1000]}")
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("MCP Inspector returned a non-object response")
    return _structured_inspector(payload)


def _execute_export(runtime_url: URL, tenant_id: str, job_id: str, work: Path) -> dict[str, str]:
    settings = Settings(
        app_env="development",
        database_url=runtime_url.render_as_string(hide_password=False),
        object_store_root=work / "object-store",
        markdown_export_root=work / "markdown-wiki",
    )
    engine = create_engine(runtime_url, pool_pre_ping=True)
    try:
        with Session(engine, expire_on_commit=False) as session:
            set_tenant_context(session, tenant_id)
            job = build_export_service(session, settings).execute(tenant_id, job_id)
            if not job.reservation_id or job.state != "completed":
                raise RuntimeError("Asynchronous export execution did not reach completed with a reservation")
            settlement = session.scalar(
                select(UsageSettlement).where(
                    UsageSettlement.tenant_id == tenant_id,
                    UsageSettlement.reservation_id == job.reservation_id,
                )
            )
            if settlement is None:
                raise RuntimeError("Asynchronous export execution omitted its durable settlement")
            return {"state": job.state, "settlement_id": settlement.id}
    finally:
        engine.dispose()


def _tamper_cursor(cursor: str) -> str:
    if not cursor:
        raise RuntimeError("Asynchronous export first page omitted its cursor")
    replacement = "A" if cursor[-1] != "A" else "B"
    return f"{cursor[:-1]}{replacement}"


async def _expect_rejected(call: ToolCall, tool: str, arguments: dict[str, Any]) -> None:
    try:
        await call(tool, arguments)
    except BaseException as exc:
        if not _exception_tree_matches(exc, (ProbeRejected,)):
            raise
        details = " ".join(_exception_messages(exc)).casefold()
        if "cursor" not in details:
            raise RuntimeError("Asynchronous export rejection did not identify its cursor boundary") from exc
        return
    raise RuntimeError("Asynchronous export accepted a tampered result cursor")


def _exception_messages(error: BaseException) -> list[str]:
    if isinstance(error, BaseExceptionGroup):
        return [message for child in error.exceptions for message in _exception_messages(child)]
    return [str(error)]


def _manifest_digest(manifest: object, client_name: str) -> str:
    if not isinstance(manifest, dict) or manifest.get("schema") != "pharma.data-export-envelope.v1":
        raise RuntimeError(f"{client_name} export page omitted its signed manifest envelope")
    payload = manifest.get("payload")
    if (
        not isinstance(payload, dict)
        or payload.get("dataset") != "entities"
        or payload.get("record_count") != 2
        or payload.get("authority") != "PostgreSQL tenant authority store"
    ):
        raise RuntimeError(f"{client_name} export manifest is not bound to the isolated authority dataset")
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def _exercise_client(
    adapter: ClientAdapter,
    runtime_url: URL,
    tenant_id: str,
    work: Path,
) -> dict[str, Any]:
    cancellation = await adapter.call(
        "create_data_export",
        {
            "dataset": "entities",
            "export_format": "jsonl",
            "filters": {"entity_type": "TARGET"},
            "fields": list(EXPORT_FIELDS),
            "max_records": 1001,
            "idempotency_key": f"async-cancel-{uuid.uuid4().hex}",
            "max_billable_units": "100",
        },
    )
    cancellation_id = cancellation.get("id")
    if (
        not isinstance(cancellation_id, str)
        or cancellation.get("state") != "pending_approval"
        or cancellation.get("approval_required") is not True
    ):
        raise RuntimeError(f"{adapter.name} did not create an approval-gated asynchronous task")
    pending_status = await adapter.call("get_data_export", {"job_id": cancellation_id})
    if pending_status.get("state") != "pending_approval":
        raise RuntimeError(f"{adapter.name} did not read the pending asynchronous task state")
    cancelled = await adapter.call("cancel_data_export", {"job_id": cancellation_id})
    if cancelled.get("state") != "cancelled":
        raise RuntimeError(f"{adapter.name} did not cancel the approval-gated asynchronous task")
    cancelled_status = await adapter.call("get_data_export", {"job_id": cancellation_id})
    if cancelled_status.get("state") != "cancelled":
        raise RuntimeError(f"{adapter.name} did not observe the terminal cancelled task state")

    created = await adapter.call(
        "create_data_export",
        {
            "dataset": "entities",
            "export_format": "jsonl",
            "filters": {"entity_type": "TARGET"},
            "fields": list(EXPORT_FIELDS),
            "max_records": 2,
            "idempotency_key": f"async-complete-{uuid.uuid4().hex}",
            "max_billable_units": "100",
        },
    )
    job_id = created.get("id")
    if not isinstance(job_id, str) or created.get("state") != "queued":
        raise RuntimeError(f"{adapter.name} did not queue a bounded asynchronous export")
    execution = await asyncio.to_thread(_execute_export, runtime_url, tenant_id, job_id, work)
    completed = await adapter.call("get_data_export", {"job_id": job_id})
    if (
        execution.get("state") != "completed"
        or completed.get("state") != "completed"
        or completed.get("record_count") != 2
        or not completed.get("artifact_sha256")
        or not completed.get("manifest_signature")
    ):
        raise RuntimeError(f"{adapter.name} completed export omitted signed artifact metadata")

    first_page = await adapter.call("read_data_export", {"job_id": job_id, "limit": 1})
    first_items = first_page.get("items")
    first_cursor = first_page.get("next_cursor")
    if (
        not isinstance(first_items, list)
        or len(first_items) != 1
        or not isinstance(first_items[0], dict)
        or not isinstance(first_cursor, str)
        or not first_cursor
    ):
        raise RuntimeError(f"{adapter.name} first asynchronous export page was invalid")
    await _expect_rejected(
        adapter.call,
        "read_data_export",
        {"job_id": job_id, "limit": 1, "cursor": _tamper_cursor(first_cursor)},
    )
    second_page = await adapter.call(
        "read_data_export",
        {"job_id": job_id, "limit": 1, "cursor": first_cursor},
    )
    second_items = second_page.get("items")
    if (
        not isinstance(second_items, list)
        or len(second_items) != 1
        or not isinstance(second_items[0], dict)
        or second_page.get("next_cursor") is not None
    ):
        raise RuntimeError(f"{adapter.name} did not recover with the second export page")
    raw_entity_ids = [first_items[0].get("id"), second_items[0].get("id")]
    entity_ids = [value for value in raw_entity_ids if isinstance(value, str) and value]
    if len(entity_ids) != 2 or len(set(entity_ids)) != 2:
        raise RuntimeError(f"{adapter.name} export pagination omitted unique authority identifiers")
    manifest_sha256 = _manifest_digest(first_page.get("manifest"), adapter.name)
    if _manifest_digest(second_page.get("manifest"), adapter.name) != manifest_sha256:
        raise RuntimeError(f"{adapter.name} export manifest changed between result pages")
    return {
        "client": adapter.name,
        "client_version": adapter.version,
        "tasks_created": 2,
        "completed_tasks": 1,
        "cancelled_tasks": 1,
        "result_pages": 2,
        "unique_records": 2,
        "entity_ids_sha256": hashlib.sha256("\n".join(sorted(entity_ids)).encode()).hexdigest(),
        "manifest_sha256": manifest_sha256,
        "tampered_cursor_rejected": True,
        "recovered_after_error": True,
        "settlement_created": bool(execution.get("settlement_id")),
        "credentials_recorded": False,
        "status": "passed",
    }


def _verify_database(runtime_url: URL, tenant_id: str) -> dict[str, int | bool]:
    engine = create_engine(runtime_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            set_tenant_context(session, tenant_id)
            states = Counter(session.scalars(select(DataExportJob.state)).all())
            settlements = int(
                session.scalar(select(func.count(UsageSettlement.id)).where(UsageSettlement.tenant_id == tenant_id))
                or 0
            )
            active_reservations = int(
                session.scalar(
                    select(func.count(UsageReservation.id)).where(
                        UsageReservation.tenant_id == tenant_id,
                        UsageReservation.state == UsageReservationState.RESERVED,
                    )
                )
                or 0
            )
            signed_completed = int(
                session.scalar(
                    select(func.count(DataExportJob.id)).where(
                        DataExportJob.tenant_id == tenant_id,
                        DataExportJob.state == "completed",
                        DataExportJob.manifest_signature.is_not(None),
                        DataExportJob.artifact_sha256.is_not(None),
                    )
                )
                or 0
            )
    finally:
        engine.dispose()
    if states != Counter({"cancelled": 2, "completed": 2}):
        raise RuntimeError(f"Asynchronous task fixture produced unexpected states: {dict(states)}")
    if settlements != 2 or signed_completed != 2 or active_reservations != 0:
        raise RuntimeError("Asynchronous task accounting or signed artifact invariants failed")
    return {
        "tasks": sum(states.values()),
        "completed_tasks": states["completed"],
        "cancelled_tasks": states["cancelled"],
        "settlements": settlements,
        "signed_completed_tasks": signed_completed,
        "active_reservations_after": active_reservations,
    }


async def _exercise(
    node: Path,
    cli: Path,
    inspector_version: str,
    mcp_url: str,
    runtime_url: URL,
    fixture: Fixture,
    work: Path,
) -> tuple[list[dict[str, Any]], dict[str, int | bool]]:
    async def inspector_call(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(
            _run_inspector_tool,
            node,
            cli,
            mcp_url,
            fixture.inspector_token,
            tool,
            arguments,
        )

    async def sdk_call(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await _call_tool(mcp_url, fixture.sdk_token, tool, arguments)

    clients = [
        ClientAdapter("MCP Inspector", inspector_version, inspector_call),
        ClientAdapter("Python MCP SDK", importlib.metadata.version("mcp"), sdk_call),
    ]
    results = [await _exercise_client(adapter, runtime_url, fixture.tenant_id, work) for adapter in clients]
    digests = {str(result["entity_ids_sha256"]) for result in results}
    if len(digests) != 1:
        raise RuntimeError("Independent MCP clients exported different authority record sets")
    return results, _verify_database(runtime_url, fixture.tenant_id)


def _atomic_write(path: Path, document: dict[str, Any]) -> None:
    if not OUTPUT_NAME.fullmatch(path.name):
        raise ValueError("Invalid MCP async task evidence filename")
    parent = path.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    resolved = parent / path.name
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    temporary = parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, resolved, follow_symlinks=False)
        except FileExistsError as exc:
            raise FileExistsError(f"Refusing to overwrite MCP async task evidence: {resolved}") from exc
        directory_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def execute(node: Path, cli: Path, inspector_version: str, output: Path) -> dict[str, Any]:
    if get_settings().app_env.casefold() == "production":
        raise RuntimeError("The isolated MCP async task probe cannot run with APP_ENV=production")
    if not node.is_file() or not os.access(node, os.X_OK):
        raise RuntimeError("The configured Node.js executable is unavailable")
    if not cli.is_file():
        raise RuntimeError("The pinned MCP Inspector CLI is unavailable")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", inspector_version):
        raise RuntimeError("The MCP Inspector version is invalid")

    credentials = _local_database_credentials()
    database_name = f"pharma_mcp_async_task_{secrets.token_hex(6)}"
    database_dropped = False
    api_stopped = False
    mcp_stopped = False
    api_process: subprocess.Popen[bytes] | None = None
    mcp_process: subprocess.Popen[bytes] | None = None
    client_results: list[dict[str, Any]] | None = None
    database_result: dict[str, int | bool] | None = None
    secret_values: list[str] = []

    with tempfile.TemporaryDirectory(prefix="pharma-mcp-async-task-") as temporary:
        work = Path(temporary)
        admin_target = _create_database(
            credentials.admin_url,
            database_name,
            database_name_pattern=DATABASE_NAME,
        )
        try:
            _migrate_database(admin_target, credentials.runtime_password, work)
            fixture = _seed_fixture(admin_target)
            secret_values.extend((fixture.inspector_token, fixture.sdk_token))
            runtime_url = _runtime_url(admin_target, credentials)
            gateway_port = _available_port()
            environment = _service_environment(runtime_url, gateway_port, gateway_port, work)
            api_process = _start_service("pharma-gateway", environment, work / "gateway.log")
            mcp_process = api_process
            api_url = f"http://127.0.0.1:{gateway_port}"
            _wait_for_api(api_url, api_process)
            mcp_url = f"http://127.0.0.1:{gateway_port}/mcp"
            _wait_for_mcp(mcp_url, fixture.inspector_token, mcp_process)
            client_results, database_result = asyncio.run(
                _exercise(node, cli, inspector_version, mcp_url, runtime_url, fixture, work)
            )
        finally:
            mcp_stopped = _stop_process(mcp_process)
            api_stopped = _stop_process(api_process)
            _drop_database(
                credentials.admin_url,
                database_name,
                database_name_pattern=DATABASE_NAME,
            )
            database_dropped = True

    if client_results is None or database_result is None:
        raise RuntimeError("MCP async task probe did not produce a result")
    cleanup = {
        "api_stopped": api_stopped,
        "mcp_stopped": mcp_stopped,
        "database_dropped": database_dropped,
        "temporary_object_store_destroyed": True,
    }
    report = {
        "schema": REPORT_SCHEMA,
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "environment": "local-wsl-isolated-postgresql-object-store",
        "production_claim": False,
        "controlled_fixture": True,
        "credentials_recorded": False,
        "protocol_version": MCP_PROTOCOL_BASELINE,
        "client_count": 2,
        "clients": client_results,
        "same_authority_record_set": True,
        "database": database_result,
        "assertions": {
            "two_independent_clients": True,
            "approval_gated_task_created": True,
            "task_status_read": True,
            "task_cancellation": True,
            "bounded_export_completed": True,
            "signed_manifest_verified": True,
            "result_pagination": True,
            "tampered_cursor_rejected": True,
            "error_recovery": True,
            "one_settlement_per_completed_export": True,
            "zero_active_reservations": True,
            "isolated_runtime_destroyed": True,
        },
        "cleanup": cleanup,
    }
    serialized = json.dumps(report, sort_keys=True)
    if any(secret in serialized for secret in secret_values):
        raise RuntimeError("MCP async task evidence contains a generated credential")
    if not all(cleanup.values()):
        raise RuntimeError("MCP async task cleanup did not complete")
    _atomic_write(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify governed asynchronous data tasks through MCP Inspector and the Python MCP SDK"
    )
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--inspector-cli", type=Path, required=True)
    parser.add_argument("--inspector-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = execute(args.node.resolve(), args.inspector_cli.resolve(), args.inspector_version, args.output)
    print(
        "MCP_ASYNC_TASK_INTEROPERABILITY "
        f"status={report['status']} clients={report['client_count']} "
        f"settlements={report['database']['settlements']} "
        "database_dropped=true credentials_recorded=false production_claim=false"
    )
    print(f"mcp_async_task_report={args.output.resolve()}")


if __name__ == "__main__":
    main()
