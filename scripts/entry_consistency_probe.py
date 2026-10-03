from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import Implementation

from pharma_intel.product import PRODUCT_VERSION
from scripts.mcp_sdk_probe import ClientSessionAdapter, McpSession, structured_tool_result
from scripts.mcp_streamable_contract import verify_domain_inventory, verify_positive_settlement

CSRF_COOKIE = "pharma_csrf"
ENTITY_FIELDS = (
    "id",
    "entity_type",
    "name",
    "description",
    "external_ids",
    "attributes",
    "review_status",
    "canonical_entity_id",
    "identity_identifiers",
    "created_at",
    "updated_at",
)


def _object(payload: object, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} returned a non-object payload")
    return payload


def _canonical_entity(payload: object, label: str) -> dict[str, Any]:
    document = _object(payload, label)
    missing = [field for field in ENTITY_FIELDS if field not in document]
    if missing:
        raise RuntimeError(f"{label} omitted canonical fields: {missing}")
    return {field: document[field] for field in ENTITY_FIELDS}


def _assert_same_entity(left: object, right: object, label: str) -> dict[str, Any]:
    canonical_left = _canonical_entity(left, f"{label} left")
    canonical_right = _canonical_entity(right, f"{label} right")
    changed = [field for field in ENTITY_FIELDS if canonical_left[field] != canonical_right[field]]
    if changed:
        raise RuntimeError(f"{label} drifted canonical fields: {changed}")
    return canonical_left


async def _web_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    expected_status: int,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    response = await client.request(method, path, json=json_body, params=params, headers=headers)
    if response.status_code != expected_status:
        raise RuntimeError(f"Web {method} {path} returned HTTP {response.status_code}")
    return _object(response.json(), f"Web {method} {path}")


async def verify_clients(
    web: httpx.AsyncClient,
    mcp_session: McpSession,
    *,
    email: str,
    password: str,
    fixture_marker: str,
    expected_protocol_version: str,
    publish_fixture: Callable[[str], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    await _web_json(
        web,
        "POST",
        "/api/v1/auth/login",
        expected_status=200,
        json_body={"email": email, "password": password},
    )
    csrf_token = web.cookies.get(CSRF_COOKIE)
    if not csrf_token:
        raise RuntimeError("Web login did not issue a CSRF cookie")

    entity_payload = {
        "entity_type": "target",
        "name": f"Entry consistency {fixture_marker}",
        "description": "Isolated Web and MCP consistency fixture",
        "aliases": [f"EC-{fixture_marker}"],
        "external_ids": {"acceptance": fixture_marker},
        "attributes": {
            "acceptance_fixture": True,
            "acceptance_fixture_kind": "entry_consistency",
            "acceptance_fixture_marker": fixture_marker,
        },
    }
    created = await _web_json(
        web,
        "POST",
        "/api/v1/entities",
        expected_status=201,
        json_body=entity_payload,
        headers={"X-CSRF-Token": csrf_token},
    )
    entity_id = created.get("id")
    if not isinstance(entity_id, str) or not entity_id:
        raise RuntimeError("Web entity creation omitted the stable ID")
    web_entity = await _web_json(web, "GET", f"/api/v1/entities/{entity_id}", expected_status=200)
    canonical = _assert_same_entity(created, web_entity, "Web create/read")
    if publish_fixture is not None:
        await publish_fixture(entity_id)
        web_entity = await _web_json(web, "GET", f"/api/v1/entities/{entity_id}", expected_status=200)
        canonical = _canonical_entity(web_entity, "Published Web entity")
    if web_entity.get("review_status") != "verified":
        raise RuntimeError("Entry consistency requires a published fixture, not an unpublished draft")

    web_search_item: dict[str, Any] | None = None
    for _ in range(30):
        search = await _web_json(
            web,
            "GET",
            "/api/v1/entities",
            expected_status=200,
            params={
                "q": fixture_marker,
                "entity_type": "target",
                "review_status": "verified",
                "limit": 10,
                "offset": 0,
            },
        )
        items = search.get("items")
        if not isinstance(items, list):
            raise RuntimeError("Web entity search omitted items")
        candidate = next((item for item in items if isinstance(item, dict) and item.get("id") == entity_id), None)
        if candidate is not None:
            web_search_item = candidate
            break
        await asyncio.sleep(0.5)
    if web_search_item is None:
        raise RuntimeError("Web search projection did not expose the consistency fixture")
    _assert_same_entity(web_entity, web_search_item, "Web read/search")

    initialized = await mcp_session.initialize()
    if initialized.protocolVersion != expected_protocol_version:
        raise RuntimeError(
            f"MCP consistency protocol mismatch: {initialized.protocolVersion} != {expected_protocol_version}"
        )
    settlements: list[str] = []
    listed_tools = await verify_domain_inventory(mcp_session)
    mcp_entity_result = structured_tool_result(
        await mcp_session.call_tool(
            "get_entity",
            {
                "entity_id": entity_id,
                "idempotency_key": f"entry-consistency-{uuid.uuid4().hex}",
                "max_billable_units": "100",
            },
        )
    )
    mcp_entity = mcp_entity_result.get("data")
    mcp_usage = mcp_entity_result.get("usage")
    if not isinstance(mcp_usage, dict) or not isinstance(mcp_usage.get("settlement_id"), str):
        raise RuntimeError("MCP get_entity omitted a settlement")
    verify_positive_settlement(mcp_usage, "entity.read")
    settlements.append(mcp_usage["settlement_id"])
    _assert_same_entity(web_entity, mcp_entity, "Web/MCP entity read")

    mcp_search_result = structured_tool_result(
        await mcp_session.call_tool(
            "search_entities",
            {
                "query": fixture_marker,
                "entity_type": "target",
                "review_status": "verified",
                "limit": 10,
                "idempotency_key": f"entry-consistency-{uuid.uuid4().hex}",
                "max_billable_units": "100",
            },
        )
    )
    mcp_search_data = mcp_search_result.get("data")
    mcp_search_usage = mcp_search_result.get("usage")
    if not isinstance(mcp_search_data, dict) or not isinstance(mcp_search_usage, dict):
        raise RuntimeError("MCP entity search omitted data or usage")
    if not isinstance(mcp_search_usage.get("settlement_id"), str):
        raise RuntimeError("MCP entity search omitted a settlement")
    if mcp_search_data.get("engine") != "opensearch":
        raise RuntimeError("MCP entity search did not use OpenSearch")
    verify_positive_settlement(mcp_search_usage, "entity.search")
    settlements.append(mcp_search_usage["settlement_id"])
    mcp_items = mcp_search_data.get("items")
    if not isinstance(mcp_items, list):
        raise RuntimeError("MCP entity search omitted items")
    mcp_search_item = next(
        (item for item in mcp_items if isinstance(item, dict) and item.get("id") == entity_id),
        None,
    )
    if mcp_search_item is None:
        raise RuntimeError("MCP entity search did not expose the consistency fixture")
    _assert_same_entity(web_search_item, mcp_search_item, "Web/MCP filtered search")
    if len(set(settlements)) != 2:
        raise RuntimeError("MCP consistency calls did not create unique settlements")

    canonical_sha256 = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return {
        "schema": "pharma.entry-consistency-acceptance.v1",
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "environment": "local-wsl-controlled-fixture",
        "production_claim": False,
        "credentials_recorded": False,
        "entity_id": entity_id,
        "canonical_entity_sha256": canonical_sha256,
        "fields_compared": list(ENTITY_FIELDS),
        "web_operations": ["create_entity", "get_entity", "search_entities"],
        "mcp_tools": ["get_entity", "search_entities"],
        "mcp_protocol_version": initialized.protocolVersion,
        "streamable_http_contract_verified": True,
        "listed_mcp_tools": listed_tools,
        "mcp_billed_calls": 2,
        "unique_settlements": 2,
        "same_tenant_fixture": True,
        "same_filtered_facts": True,
    }


async def verify(
    web_url: str,
    mcp_url: str,
    token: str,
    email: str,
    password: str,
    fixture_marker: str,
    expected_protocol_version: str,
    fixture_container: str | None = None,
    fixture_tenant: str | None = None,
) -> dict[str, Any]:
    async def publish_fixture(entity_id: str) -> None:
        if not fixture_container or not fixture_tenant or re.fullmatch(r"[0-9a-f]{64}", fixture_container) is None:
            raise RuntimeError("An explicit owned fixture container and tenant are required")
        uuid.UUID(fixture_tenant)
        uuid.UUID(entity_id)
        docker = shutil.which("docker")
        if docker is None:
            raise RuntimeError("Docker is unavailable for isolated fixture publication")
        process = await asyncio.create_subprocess_exec(
            docker,
            "exec",
            fixture_container,
            "python",
            "-m",
            "pharma_intel.entry_consistency_fixture",
            "--tenant-id",
            fixture_tenant,
            "--entity-id",
            entity_id,
            "--marker",
            fixture_marker,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        if process.returncode != 0:
            raise RuntimeError("The isolated entry fixture could not be published")

    timeout = httpx.Timeout(60, connect=10)
    async with httpx.AsyncClient(base_url=web_url, timeout=timeout, trust_env=False) as web:
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(30, connect=10),
            trust_env=False,
        ) as mcp_http:
            async with streamable_http_client(mcp_url, http_client=mcp_http) as (
                read_stream,
                write_stream,
                _session_id,
            ):
                client_info = Implementation(name="pharma-entry-consistency", version=PRODUCT_VERSION)
                async with ClientSession(read_stream, write_stream, client_info=client_info) as session:
                    return await verify_clients(
                        web,
                        ClientSessionAdapter(session),
                        email=email,
                        password=password,
                        fixture_marker=fixture_marker,
                        expected_protocol_version=expected_protocol_version,
                        publish_fixture=publish_fixture if fixture_container else None,
                    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web-url", required=True)
    parser.add_argument("--mcp-url", required=True)
    parser.add_argument("--fixture-marker", required=True)
    parser.add_argument("--expected-protocol-version", required=True)
    parser.add_argument("--fixture-container")
    parser.add_argument("--fixture-tenant")
    args = parser.parse_args()
    token = os.environ.get("TEST_MCP_ACCESS_TOKEN", "")
    email = os.environ.get("ENTRY_TEST_EMAIL", "")
    password = os.environ.get("ENTRY_TEST_PASSWORD", "")
    if not token or not email or not password:
        raise RuntimeError("TEST_MCP_ACCESS_TOKEN, ENTRY_TEST_EMAIL and ENTRY_TEST_PASSWORD are required")
    result = asyncio.run(
        verify(
            args.web_url,
            args.mcp_url,
            token,
            email,
            password,
            args.fixture_marker,
            args.expected_protocol_version,
            args.fixture_container,
            args.fixture_tenant,
        )
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
