from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from mcp.server.auth.provider import AccessToken, TokenVerifier
from starlette.requests import Request

from pharma_intel import mcp_server
from pharma_intel.mcp_dpop import DpopSenderConstraintMiddleware
from pharma_intel.mcp_server import McpContext, mcp

DATA_TOOLS = {
    "compare_target_sar",
    "get_bioactivity_landscape",
    "get_clinical_trial",
    "get_clinical_trials",
    "get_company_timeline",
    "get_competitive_pipeline",
    "get_deals",
    "get_entity",
    "get_entity_dossier",
    "get_epidemiology_observations",
    "get_knowledge_page",
    "get_news_events",
    "get_patent_landscape",
    "get_record_provenance",
    "get_regulatory_events",
    "get_target_profile",
    "get_target_evidence",
    "resolve_entity",
    "search_entities",
    "search_evidence",
    "search_knowledge_pages",
    "search_chemical_structures",
    "search_structures",
}
EXPORT_TOOLS = {"create_data_export", "get_data_export", "cancel_data_export", "read_data_export"}
CONTROL_TOOLS = {"get_commercial_access", "estimate_usage", "get_usage_summary"}


class AcceptingVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        return AccessToken(token=token, client_id="test", scopes=["mcp:connect"])


class RefreshingVerifier(TokenVerifier):
    def __init__(self, client_id: str = "test") -> None:
        self.client_id = client_id
        self.tokens: list[str] = []

    async def verify_token(self, token: str) -> AccessToken | None:
        self.tokens.append(token)
        return AccessToken(
            token="fresh-internal-token",  # noqa: S106 - test-only token value
            client_id=self.client_id,
            scopes=["mcp:connect"],
        )


@pytest.fixture(autouse=True)
def authenticated_commercial_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mcp_server,
        "get_access_token",
        lambda: AccessToken(token="test-token", client_id="test", scopes=["mcp:connect"]),  # noqa: S106
    )
    monkeypatch.setattr(mcp_server, "_correlation_headers", lambda _ctx: {})


async def _wait_for_cancelled_operations() -> None:
    for _ in range(100):
        if not mcp_server._cancelled_commercial_operations:  # noqa: SLF001
            return
        await asyncio.sleep(0.01)
    raise AssertionError("cancelled commercial operation was retained after cleanup")


def test_internal_api_client_never_uses_ambient_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class CapturingClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", CapturingClient)

    client = mcp_server._internal_api_client()  # noqa: SLF001

    assert isinstance(client, CapturingClient)
    assert captured["base_url"] == mcp_server.settings.agent_api_base_url
    assert captured["follow_redirects"] is False
    assert captured["trust_env"] is False


def test_commercial_datetime_arguments_share_the_domain_api_utc_identity() -> None:
    source = {
        "published_from": "2026-07-26T08:30:00+08:00",
        "published_to": "2026-07-26T01:30:00Z",
        "decision_from": "invalid",
        "decision_to": "2026-07-26T01:30:00",
        "q": "2026-07-26T01:30:00Z",
    }

    normalized = mcp_server._canonical_commercial_datetime_arguments(source)  # noqa: SLF001

    assert normalized == {
        "published_from": "2026-07-26T00:30:00+00:00",
        "published_to": "2026-07-26T01:30:00+00:00",
        "decision_from": "invalid",
        "decision_to": "2026-07-26T01:30:00",
        "q": "2026-07-26T01:30:00Z",
    }
    assert source["published_from"] == "2026-07-26T08:30:00+08:00"


@pytest.mark.parametrize(
    "path",
    [
        "https://attacker.example/collect",
        "/internal/v1/domain/../commercial/access",
        "/internal/v1/domain/%2e%2e/commercial/access",
        "/internal/v1/domain/%252e%252e/commercial/access",
        "/internal/v1/domain/%5c..%5ccommercial/access",
        "/internal/v1/domain/%00",
        "/internal/v1/domain/%2f%2fattacker.example",
        "/health/ready",
    ],
)
@pytest.mark.anyio
async def test_api_request_rejects_paths_outside_the_internal_application_boundary(path: str) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("MCP must reject the path before opening an HTTP request")

    async with httpx.AsyncClient(
        base_url="http://api.internal",
        transport=httpx.MockTransport(handler),
    ) as client:
        token = mcp_server._api_request_override.set(  # noqa: SLF001
            mcp_server.ApiRequestOverride(client, "internal-token", {})  # noqa: S106
        )
        try:
            with pytest.raises(RuntimeError, match="MCP internal API path"):
                await mcp_server.api_request(cast(McpContext, object()), "GET", path)
        finally:
            mcp_server._api_request_override.reset(token)  # noqa: SLF001


@pytest.mark.anyio
async def test_tool_call_revalidates_source_credential_before_internal_api_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = RefreshingVerifier()
    monkeypatch.setattr(mcp_server, "token_verifier", verifier)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/mcp",
            "headers": [(b"authorization", b"Bearer source-api-key")],
        }
    )
    ctx = cast(McpContext, SimpleNamespace(request_context=SimpleNamespace(request=request)))

    refreshed = await mcp_server._revalidate_access_token(ctx)  # noqa: SLF001

    assert refreshed.token == "fresh-internal-token"  # noqa: S105
    assert verifier.tokens == ["source-api-key"]


@pytest.mark.anyio
async def test_tool_call_rejects_source_credential_identity_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_server, "token_verifier", RefreshingVerifier(client_id="another-client"))
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/mcp",
            "headers": [(b"authorization", b"DPoP source-oidc-token")],
        }
    )
    ctx = cast(McpContext, SimpleNamespace(request_context=SimpleNamespace(request=request)))

    with pytest.raises(RuntimeError, match="identity changed"):
        await mcp_server._revalidate_access_token(ctx)  # noqa: SLF001


@pytest.mark.anyio
async def test_api_request_reports_bounded_validation_errors_without_echoing_input() -> None:
    sensitive_input = "must-not-be-returned"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            request=request,
            json={
                "detail": [
                    {
                        "loc": ["body", "dataset"],
                        "msg": "Input should be a supported dataset",
                        "type": "literal_error",
                        "input": sensitive_input,
                    }
                ]
            },
        )

    async with httpx.AsyncClient(
        base_url="http://api.internal",
        transport=httpx.MockTransport(handler),
    ) as client:
        token = mcp_server._api_request_override.set(  # noqa: SLF001
            mcp_server.ApiRequestOverride(client, "internal-token", {})  # noqa: S106
        )
        try:
            with pytest.raises(ValueError) as error:
                await mcp_server.api_request(cast(McpContext, object()), "POST", "/internal/v1/exports", json={})
        finally:
            mcp_server._api_request_override.reset(token)  # noqa: SLF001

    assert "body.dataset [literal_error]" in str(error.value)
    assert sensitive_input not in str(error.value)


@pytest.mark.anyio
async def test_api_request_reports_sanitized_domain_validation_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            request=request,
            json={"detail": "Unsupported export field\nBearer secret-value"},
        )

    async with httpx.AsyncClient(
        base_url="http://api.internal",
        transport=httpx.MockTransport(handler),
    ) as client:
        token = mcp_server._api_request_override.set(  # noqa: SLF001
            mcp_server.ApiRequestOverride(client, "internal-token", {})  # noqa: S106
        )
        try:
            with pytest.raises(ValueError) as error:
                await mcp_server.api_request(cast(McpContext, object()), "POST", "/internal/v1/exports", json={})
        finally:
            mcp_server._api_request_override.reset(token)  # noqa: SLF001

    assert "Unsupported export field Bearer [redacted]" in str(error.value)
    assert "secret-value" not in str(error.value)


def test_mcp_server_registers_only_core_domain_and_commercial_control_tools() -> None:
    tool_names = set(mcp._tool_manager._tools)  # noqa: SLF001

    assert tool_names == DATA_TOOLS | EXPORT_TOOLS | CONTROL_TOOLS
    assert "build_research_bundle" not in tool_names
    for name in DATA_TOOLS:
        parameters = mcp._tool_manager._tools[name].parameters  # noqa: SLF001
        assert "idempotency_key" in parameters["required"]
        assert "max_billable_units" in parameters["required"]
    create_parameters = mcp._tool_manager._tools["create_data_export"].parameters  # noqa: SLF001
    assert {"dataset", "idempotency_key", "max_billable_units"}.issubset(create_parameters["required"])


def test_mcp_http_app_wraps_sdk_authentication_with_dpop_when_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mcp_server.settings, "mcp_dpop_required", True)
    monkeypatch.setattr(mcp_server, "token_verifier", AcceptingVerifier())

    app = mcp_server.build_http_app()

    assert isinstance(app, DpopSenderConstraintMiddleware)


@pytest.mark.anyio
async def test_export_tools_use_dedicated_async_api_without_per_page_rebilling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def fake_request(_ctx: McpContext, method: str, path: str, **kwargs: Any) -> Any:
        calls.append((method, path, kwargs))
        if path.endswith("/chunks"):
            return {"items": [{"id": "entity-1"}], "count": 1, "next_cursor": None, "manifest": {}}
        return {"id": "job-1", "state": "queued"}

    monkeypatch.setattr(mcp_server, "api_request", fake_request)
    ctx = cast(McpContext, object())
    created = await mcp_server.create_data_export(
        ctx,
        "entities",
        "export-tool-0001",
        "100",
        filters={"entity_type": "target"},
        fields=["id", "name"],
        max_records=100,
    )
    status_result = await mcp_server.get_data_export(ctx, "job-1")
    chunk = await mcp_server.read_data_export(ctx, "job-1", 25)
    cancelled = await mcp_server.cancel_data_export(ctx, "job-1")

    assert created["state"] == status_result["state"] == cancelled["state"] == "queued"
    assert chunk["count"] == 1
    assert [path for _, path, _ in calls] == [
        "/internal/v1/exports",
        "/internal/v1/exports/job-1",
        "/internal/v1/exports/job-1/chunks",
        "/internal/v1/exports/job-1/cancel",
    ]
    assert not any("commercial/reservations" in path for _, path, _ in calls)


@pytest.mark.anyio
async def test_structured_domain_tools_preserve_ordered_multi_sort_for_billing_and_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_commercial_request(_ctx: McpContext, **kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"data": {"items": []}, "usage": {"settlement_id": "settlement-1"}}

    monkeypatch.setattr(mcp_server, "commercial_api_request", fake_commercial_request)
    ctx = cast(McpContext, object())
    expected = {
        "entity.search": ["entity_type:asc", "name:desc"],
        "pipeline.search": ["global_phase:desc", "drug_name:asc"],
        "trial.search": ["overall_status:asc", "registry_id:desc"],
        "patent.search": ["legal_status:asc", "family_identifier:desc"],
        "deal.search": ["status:asc", "name:desc"],
        "regulatory.search": ["agency:asc", "subject:desc"],
        "epidemiology.search": ["measure:asc", "value:desc"],
        "news.search": ["event_type:asc", "title:desc"],
    }

    await mcp_server.search_entities(
        ctx,
        "EGFR",
        "multi-sort-entity",
        "100",
        sort=expected["entity.search"],
    )
    await mcp_server.get_competitive_pipeline(
        ctx,
        "target-1",
        "multi-sort-pipeline",
        "100",
        sort=expected["pipeline.search"],
    )
    await mcp_server.get_clinical_trials(
        ctx,
        "multi-sort-trial",
        "100",
        sort=expected["trial.search"],
    )
    await mcp_server.get_patent_landscape(
        ctx,
        "multi-sort-patent",
        "100",
        sort=expected["patent.search"],
    )
    await mcp_server.get_deals(
        ctx,
        "multi-sort-deal",
        "100",
        sort=expected["deal.search"],
    )
    await mcp_server.get_regulatory_events(
        ctx,
        "multi-sort-regulatory",
        "100",
        sort=expected["regulatory.search"],
    )
    await mcp_server.get_epidemiology_observations(
        ctx,
        "multi-sort-epidemiology",
        "100",
        sort=expected["epidemiology.search"],
    )
    await mcp_server.get_news_events(
        ctx,
        "multi-sort-news",
        "100",
        sort=expected["news.search"],
    )

    assert len(calls) == len(expected)
    for call in calls:
        billing_class = call["billing_class"]
        assert call["request_arguments"]["sort"] == expected[billing_class]
        assert call["params"]["sort"] == expected[billing_class]
    entity_call = next(call for call in calls if call["billing_class"] == "entity.search")
    assert entity_call["request_arguments"]["review_status"] == "verified"
    assert entity_call["params"]["review_status"] == "verified"

    with pytest.raises(ValueError, match="unique"):
        await mcp_server.search_entities(
            ctx,
            "EGFR",
            "duplicate-sort-entity",
            "100",
            sort=["name:asc", "name:desc"],
        )
    assert len(calls) == len(expected)

    with pytest.raises(ValueError, match="verified records"):
        await mcp_server.search_entities(
            ctx,
            "EGFR",
            "draft-entity-query",
            "100",
            review_status="draft",
        )
    assert len(calls) == len(expected)


@pytest.mark.anyio
async def test_all_domain_tools_reserve_execute_and_settle_bounded_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, dict[str, Any]]] = []
    reservations = 0

    async def fake_request(_ctx: McpContext, method: str, path: str, **kwargs: Any) -> Any:
        nonlocal reservations
        calls.append((method, path, kwargs))
        if path == "/internal/v1/commercial/access":
            return {"status": "active"}
        if path == "/internal/v1/commercial/estimate":
            return {"estimated_units_before_response_bytes": "1.10000000"}
        if path == "/internal/v1/commercial/usage-summary":
            return {"settlement_count": 1}
        if path == "/internal/v1/commercial/reservations":
            reservations += 1
            return {
                "reservation_id": f"reservation-{reservations}",
                "state": "reserved",
                "billing_class": kwargs["json"]["billing_class"],
                "estimated_units": "1.00000000",
                "reserved_units": kwargs["json"]["max_billable_units"],
                "lease_expires_at": "2026-07-16T01:00:00Z",
                "page_depth": 1,
                "replayed": False,
                "settlement": None,
            }
        if path.endswith("/settle"):
            number = path.split("/")[-2].split("-")[-1]
            return {
                "reservation_id": f"reservation-{number}",
                "state": "settled",
                "billing_class": kwargs["json"]["metrics"]["tool"],
                "estimated_units": "1.00000000",
                "reserved_units": "100.00000000",
                "lease_expires_at": "2026-07-16T01:00:00Z",
                "page_depth": 1,
                "replayed": False,
                "settlement": {
                    "settlement_id": f"settlement-{number}",
                    "usage_event_id": f"usage-{number}",
                    "charged_units": "1.00000000",
                    "result_count": kwargs["json"]["result_count"],
                    "unique_record_count": kwargs["json"]["result_count"],
                    "new_unique_record_count": kwargs["json"]["result_count"],
                    "response_bytes": 100,
                    "price_breakdown": {},
                    "result": kwargs["json"]["result"],
                    "created_at": "2026-07-16T00:00:00Z",
                },
            }
        if path == "/internal/v1/domain/entities":
            return {"items": [{"id": "entity-1"}], "limit": 1, "page_depth": 1, "next_cursor": None}
        if path == "/internal/v1/domain/chemistry/search":
            return {"items": [{"id": "structure-1", "standard_inchi_key": "one"}], "mode": "similarity"}
        if path == "/internal/v1/domain/evidence/search":
            return {
                "query": "EGFR",
                "chunks": [{"id": "chunk-1", "dataset_id": "literature"}],
                "engine": "opensearch",
                "license_scopes": [
                    {
                        "dataset_key": "literature",
                        "license_id": "licensed-source-1",
                        "policy_version": "contract-v1",
                        "attribution": "Licensed source",
                        "delivery_channel": "mcp",
                        "allowed_fields": ["content"],
                        "max_content_chars": 1000,
                    }
                ],
                "warnings": ["Dataset literature content was truncated by license policy"],
                "limit": 50,
                "page_depth": 1,
                "next_cursor": None,
            }
        if path.endswith("/dossier"):
            return {
                "entity": {"id": "entity-1"},
                "relationships": [],
                "activities": [],
                "programs": [],
                "clinical_trials": [{"id": "trial-1"}],
                "patents": [],
                "deals": [],
                "regulatory_events": [],
                "news_events": [],
                "structures": [],
                "target_evidence": [],
                "coverage": [],
                "warnings": [],
            }
        if path.startswith("/api/v1/trials/"):
            return {"id": "trial-1", "registry_id": "NCT00000001", "has_results": True}
        if path.endswith("/profile") or "/entities/" in path or "/knowledge/pages/" in path:
            return {"id": "one"}
        return {"items": [{"id": "row-1"}], "limit": 100, "page_depth": 1, "next_cursor": None}

    monkeypatch.setattr(mcp_server, "api_request", fake_request)
    ctx = cast(McpContext, object())

    assert await mcp_server.get_commercial_access(ctx) == {"status": "active"}
    assert (await mcp_server.estimate_usage(ctx, "entity.search", 10))["estimated_units_before_response_bytes"] == (
        "1.10000000"
    )
    assert (await mcp_server.get_usage_summary(ctx))["settlement_count"] == 1
    opaque_cursor = "signed-opaque-cursor"
    results = [
        await mcp_server.search_entities(
            ctx,
            "EGFR",
            "search-entity-001",
            "100",
            "target",
            500,
            review_status="verified",
            sort_by="updated_at",
            sort_direction="asc",
            entity_types=["drug", "target", "drug"],
        ),
        await mcp_server.resolve_entity(ctx, "P00533", "resolve-entity-01", "100", "target", 0),
        await mcp_server.get_entity(ctx, "entity-1", "get-entity-00001", "100"),
        await mcp_server.get_entity_dossier(ctx, "entity-1", "get-dossier-0001", "100", 250),
        await mcp_server.search_evidence(
            ctx, "EGFR inhibitor", "search-evidence-1", "100", ["literature"], 100, opaque_cursor
        ),
        await mcp_server.get_record_provenance(
            ctx,
            "activity_measurement",
            "11111111-1111-4111-8111-111111111111",
            "record-provenance-1",
            "100",
            500,
        ),
        await mcp_server.get_target_profile(ctx, "target-1", "target-profile-01", "100"),
        await mcp_server.get_target_evidence(
            ctx,
            "target-1",
            "target-evidence-01",
            "100",
            "genetic_association",
            "supports",
            "disease-1",
            10_000,
            opaque_cursor,
        ),
        await mcp_server.get_bioactivity_landscape(
            ctx, "target-1", "bioactivity-0001", "100", "IC50", 10_000, opaque_cursor
        ),
        await mcp_server.compare_target_sar(
            ctx,
            "target-1",
            "sar-compare-0001",
            "100",
            "IC50",
            "binding",
            "biochemical",
            "Homo sapiens",
            "A549",
            10_000,
            opaque_cursor,
        ),
        await mcp_server.get_competitive_pipeline(
            ctx,
            "target-1",
            "pipeline-search-1",
            "100",
            limit=10_000,
            cursor=opaque_cursor,
            drug_entity_id="drug-1",
            disease_entity_id="disease-1",
            organization_entity_id="organization-1",
            program_status="active",
            organization_role="collaborator",
            organization_type="biotech",
            organization_country_region="US",
            modality="small molecule",
            global_phase="phase_2",
            china_phase="phase_1",
            development_rights_region="Global",
            commercialization_rights_region="Greater China",
            program_tag="first_in_class",
            milestone_type="first_patient_in",
            milestone_from="2026-06-01T00:00:00Z",
            milestone_to="2026-06-30T23:59:59Z",
            sort_by="drug_name",
            sort_direction="asc",
            has_clinical_results=True,
            clinical_result_evaluation="positive",
            has_deal=False,
        ),
        await mcp_server.search_structures(
            ctx,
            "structure-search1",
            "100",
            "drug-1",
            "ABCDEFGHIJKLMN-ABCDEFGHIJ-A",
            1_000,
            opaque_cursor,
        ),
        await mcp_server.search_chemical_structures(
            ctx,
            "similarity",
            "CC(=O)OC1=CC=CC=C1C(=O)O",
            "chemical-search-01",
            "100",
            0.7,
            500,
            opaque_cursor,
        ),
        await mcp_server.get_clinical_trials(
            ctx,
            "trial-search-001",
            "100",
            "target-1",
            "lung cancer",
            2_000,
            opaque_cursor,
            "ClinicalTrials.gov",
            "RECRUITING",
            "PHASE2",
            "INTERVENTIONAL",
            True,
            "2026-01-01T00:00:00Z",
            "2026-12-31T23:59:59.999Z",
            "positive",
            "VX-101",
            "Pembrolizumab",
            "EGFR",
            "PD-1",
            "",
            "investigational_drug",
            True,
            "PMID:12345678",
            "ASCO 2026",
            "2026-06-01T00:00:00Z",
            "2026-12-31T23:59:59.999Z",
            "registry_id",
            "asc",
            "KEYNOTE",
            "ist",
            "first_line",
            [
                "550e8400-e29b-41d4-a716-446655440003",
                "550e8400-e29b-41d4-a716-446655440004",
            ],
            ["550e8400-e29b-41d4-a716-446655440010"],
            ["550e8400-e29b-41d4-a716-446655440011"],
            ["550e8400-e29b-41d4-a716-446655440012"],
            ["550e8400-e29b-41d4-a716-446655440013"],
            ["antibody"],
            ["innovative"],
            ["biologic"],
            ["first_in_class"],
            "phase_3",
            "CN",
        ),
        await mcp_server.get_clinical_trial(ctx, "trial-1", "trial-read-0001", "100"),
        await mcp_server.get_patent_landscape(
            ctx,
            "patent-search-01",
            "100",
            "target-1",
            "WO2026",
            2_000,
            opaque_cursor,
            "Victor Therapeutics",
            "ACTIVE",
            "family_identifier",
            "asc",
        ),
        await mcp_server.get_deals(
            ctx,
            "deal-search-0001",
            "100",
            entity_id="drug-1",
            limit=2_000,
            cursor=opaque_cursor,
            query="license",
            deal_type="license",
            status="active",
            direction="outbound",
            direction_reference_jurisdiction="US",
            territory="global",
            asset_entity_id="drug-1",
            target_entity_id="target-1",
            disease_entity_id="disease-1",
            asset_modality="antibody",
            asset_program_tag="first_in_class",
            asset_modalities=["antibody", "small molecule"],
            asset_program_tags=["first_in_class", "best_in_class"],
            party="Victor Therapeutics",
            party_entity_id="company-1",
            party_role="licensor",
            party_country_region="US",
            party_organization_type="biopharma",
            development_phase_at_transaction="phase_2",
            current_development_phase="phase_3",
            right_type="commercialization",
            rights_territory="Greater China",
            currency="USD",
            announced_from="2026-01-01T00:00:00Z",
            announced_to="2026-12-31T23:59:59.999Z",
            terminated_from="2026-02-01T00:00:00Z",
            terminated_to="2026-12-31T23:59:59.999Z",
            source_updated_from="2026-03-01T00:00:00Z",
            source_updated_to="2026-12-31T23:59:59.999Z",
            upfront_amount_min=10_000_000,
            upfront_amount_max=30_000_000,
            total_potential_amount_min=100_000_000,
            total_potential_amount_max=500_000_000,
            sort_by="name",
            sort_direction="asc",
        ),
        await mcp_server.get_company_timeline(
            ctx,
            "company-1",
            "company-timeline-1",
            "100",
            2_000,
            opaque_cursor,
        ),
        await mcp_server.get_regulatory_events(
            ctx,
            "regulatory-search1",
            "100",
            "drug-1",
            "NDA 219999",
            "FDA",
            2_000,
            opaque_cursor,
            "US",
            "approval",
            "approved",
            "breakthrough_therapy",
            "initial_label",
            True,
            "adverse_event",
            "serious",
            "confirmed",
            "2026-01-01T00:00:00Z",
            "2026-12-31T23:59:59.999Z",
            "2026-02-01T00:00:00Z",
            "2026-12-31T23:59:59.999Z",
            "subject",
            "asc",
        ),
        await mcp_server.get_epidemiology_observations(
            ctx,
            "epidemiology-001",
            "100",
            "disease-1",
            "NSCLC burden",
            "prevalence",
            "China",
            "patients",
            "adults",
            "18+",
            "all",
            "2025-01-01T00:00:00Z",
            "2025-12-31T00:00:00Z",
            2_000,
            opaque_cursor,
            "population-1",
            "value",
            "asc",
        ),
        await mcp_server.get_news_events(
            ctx,
            "news-search-0001",
            "100",
            "target-1",
            "Phase 2 update",
            "press_release",
            "Victor Therapeutics",
            "en",
            "ASCO 2026",
            "2026-01-01T00:00:00Z",
            "2026-12-31T00:00:00Z",
            2_000,
            opaque_cursor,
            "title",
            "asc",
        ),
        await mcp_server.search_knowledge_pages(ctx, "knowledge-search", "100", "EGFR", "target", 2_000, opaque_cursor),
        await mcp_server.get_knowledge_page(ctx, "page-1", "knowledge-read-01", "100"),
    ]

    assert all(result["usage"]["settlement_id"].startswith("settlement-") for result in results)
    assert results[4]["data"]["license_scopes"][0]["delivery_channel"] == "mcp"
    assert results[4]["data"]["warnings"]
    reserve_calls = [call for call in calls if call[1] == "/internal/v1/commercial/reservations"]
    settle_calls = [call for call in calls if call[1].endswith("/settle")]
    assert len(reserve_calls) == len(DATA_TOOLS) == len(settle_calls)
    limits = {call[2]["json"]["billing_class"]: call[2]["json"]["requested_result_limit"] for call in reserve_calls}
    assert limits == {
        "entity.search": 100,
        "entity.resolve": 1,
        "entity.read": 1,
        "entity.dossier": 1001,
        "evidence.search": 50,
        "provenance.read": 100,
        "target.profile": 1,
        "target.evidence.search": 500,
        "bioactivity.search": 500,
        "sar.compare": 500,
        "pipeline.search": 500,
        "structure.search": 100,
        "structure.similarity": 50,
        "trial.search": 500,
        "trial.read": 1,
        "patent.search": 500,
        "deal.search": 500,
        "company.timeline": 500,
        "regulatory.search": 500,
        "epidemiology.search": 500,
        "news.search": 500,
        "knowledge.search": 100,
        "knowledge.read": 1,
    }
    dossier_settlement = next(call for call in settle_calls if call[2]["json"]["metrics"]["tool"] == "entity.dossier")
    assert dossier_settlement[2]["json"]["result_count"] == 2
    entity_reservation = next(call for call in reserve_calls if call[2]["json"]["billing_class"] == "entity.search")
    assert entity_reservation[2]["json"]["request_arguments"]["review_status"] == "verified"
    assert entity_reservation[2]["json"]["request_arguments"]["entity_types"] == ["drug", "target"]
    assert "entity_type" not in entity_reservation[2]["json"]["request_arguments"]
    pipeline_reservation = next(call for call in reserve_calls if call[2]["json"]["billing_class"] == "pipeline.search")
    assert pipeline_reservation[2]["json"]["request_arguments"] == {
        "target_entity_id": "target-1",
        "limit": 500,
        "cursor": opaque_cursor,
        "drug_entity_id": "drug-1",
        "disease_entity_id": "disease-1",
        "organization_entity_id": "organization-1",
        "program_status": "active",
        "organization_role": "collaborator",
        "organization_type": "biotech",
        "organization_country_region": "US",
        "modality": ["small molecule"],
        "global_phase": "phase_2",
        "china_phase": "phase_1",
        "development_rights_region": "Global",
        "commercialization_rights_region": "Greater China",
        "program_tag": ["first_in_class"],
        "milestone_type": "first_patient_in",
        "milestone_from": "2026-06-01T00:00:00+00:00",
        "milestone_to": "2026-06-30T23:59:59+00:00",
        "sort": ["drug_name:asc"],
        "has_clinical_results": True,
        "clinical_result_evaluation": "positive",
        "has_deal": False,
    }
    pipeline_domain = next(
        call for call in calls if call[1] == "/internal/v1/domain/targets/target-1/competitive-programs"
    )
    assert pipeline_domain[2]["params"] == {
        key: value
        for key, value in pipeline_reservation[2]["json"]["request_arguments"].items()
        if key != "target_entity_id"
    }
    entity_domain = next(call for call in calls if call[1] == "/internal/v1/domain/entities")
    assert entity_domain[2]["params"]["review_status"] == "verified"
    assert entity_domain[2]["params"]["sort"] == ["updated_at:asc"]
    assert entity_domain[2]["params"]["entity_types"] == ["drug", "target"]
    assert "entity_type" not in entity_domain[2]["params"]
    target_evidence_domain = next(call for call in calls if call[1] == "/internal/v1/domain/targets/target-1/evidence")
    assert target_evidence_domain[2]["params"] == {
        "evidence_type": "genetic_association",
        "direction": "supports",
        "disease_entity_id": "disease-1",
        "limit": 500,
        "cursor": opaque_cursor,
    }
    sar_domain = next(call for call in calls if call[1] == "/internal/v1/domain/targets/target-1/sar-comparison")
    assert sar_domain[2]["params"] == {
        "standard_type": "IC50",
        "assay_type": "binding",
        "assay_format": "biochemical",
        "organism": "Homo sapiens",
        "cell_line": "A549",
        "limit": 500,
        "cursor": opaque_cursor,
    }
    trial_domain = next(call for call in calls if call[1] == "/internal/v1/domain/clinical-trials")
    assert trial_domain[2]["params"] == {
        "entity_id": "target-1",
        "q": "lung cancer",
        "registry": "ClinicalTrials.gov",
        "status": "RECRUITING",
        "phase": "PHASE2",
        "study_type": "INTERVENTIONAL",
        "acronym": "KEYNOTE",
        "initiation_type": "ist",
        "therapy_line": "first_line",
        "has_results": True,
        "results_posted_from": "2026-01-01T00:00:00+00:00",
        "results_posted_to": "2026-12-31T23:59:59.999000+00:00",
        "result_evaluation": "positive",
        "investigational_drug": "VX-101",
        "combination_drug": "Pembrolizumab",
        "investigational_target": "EGFR",
        "combination_target": "PD-1",
        "role_entity_ids": [
            "550e8400-e29b-41d4-a716-446655440003",
            "550e8400-e29b-41d4-a716-446655440004",
        ],
        "investigational_drug_entity_ids": ["550e8400-e29b-41d4-a716-446655440010"],
        "combination_drug_entity_ids": ["550e8400-e29b-41d4-a716-446655440011"],
        "investigational_target_entity_ids": ["550e8400-e29b-41d4-a716-446655440012"],
        "combination_target_entity_ids": ["550e8400-e29b-41d4-a716-446655440013"],
        "linked_drug_modality": ["antibody"],
        "linked_drug_innovation_type": ["innovative"],
        "linked_drug_category": ["biologic"],
        "linked_drug_program_tag": ["first_in_class"],
        "linked_drug_global_phase": "phase_3",
        "linked_drug_organization_country_region": "CN",
        "role_entity_role": "investigational_drug",
        "has_key_result": True,
        "publication_id": "PMID:12345678",
        "conference": "ASCO 2026",
        "disclosed_from": "2026-06-01T00:00:00+00:00",
        "disclosed_to": "2026-12-31T23:59:59.999000+00:00",
        "limit": 500,
        "cursor": opaque_cursor,
        "sort": ["registry_id:asc"],
    }
    patent_domain = next(call for call in calls if call[1] == "/internal/v1/domain/patents")
    assert patent_domain[2]["params"] == {
        "entity_id": "target-1",
        "q": "WO2026",
        "applicant": "Victor Therapeutics",
        "legal_status": "ACTIVE",
        "limit": 500,
        "cursor": opaque_cursor,
        "sort": ["family_identifier:asc"],
    }
    deal_domain = next(call for call in calls if call[1] == "/internal/v1/domain/deals")
    assert deal_domain[2]["params"] == {
        "entity_id": "drug-1",
        "q": "license",
        "deal_type": "license",
        "status": "active",
        "direction": "outbound",
        "direction_reference_jurisdiction": "US",
        "territory": "global",
        "asset_entity_id": "drug-1",
        "target_entity_id": "target-1",
        "disease_entity_id": "disease-1",
        "asset_modality": ["antibody", "small molecule"],
        "asset_program_tag": ["first_in_class", "best_in_class"],
        "party": "Victor Therapeutics",
        "party_entity_id": "company-1",
        "party_role": "licensor",
        "party_country_region": "US",
        "party_organization_type": "biopharma",
        "development_phase_at_transaction": "phase_2",
        "current_development_phase": "phase_3",
        "right_type": "commercialization",
        "rights_territory": "Greater China",
        "currency": "USD",
        "announced_from": "2026-01-01T00:00:00+00:00",
        "announced_to": "2026-12-31T23:59:59.999000+00:00",
        "terminated_from": "2026-02-01T00:00:00+00:00",
        "terminated_to": "2026-12-31T23:59:59.999000+00:00",
        "source_updated_from": "2026-03-01T00:00:00+00:00",
        "source_updated_to": "2026-12-31T23:59:59.999000+00:00",
        "upfront_amount_min": 10_000_000,
        "upfront_amount_max": 30_000_000,
        "total_potential_amount_min": 100_000_000,
        "total_potential_amount_max": 500_000_000,
        "limit": 500,
        "cursor": opaque_cursor,
        "sort": ["name:asc"],
    }
    company_domain = next(call for call in calls if call[1] == "/internal/v1/domain/companies/company-1/timeline")
    assert company_domain[2]["params"] == {"limit": 500, "cursor": opaque_cursor}
    regulatory_domain = next(call for call in calls if call[1] == "/internal/v1/domain/regulatory-events")
    assert regulatory_domain[2]["params"] == {
        "entity_id": "drug-1",
        "q": "NDA 219999",
        "agency": "FDA",
        "jurisdiction": "US",
        "event_type": "approval",
        "status": "approved",
        "designation_type": "breakthrough_therapy",
        "label_change_type": "initial_label",
        "has_boxed_warning": True,
        "safety_signal_type": "adverse_event",
        "safety_severity": "serious",
        "safety_status": "confirmed",
        "decision_from": "2026-01-01T00:00:00+00:00",
        "decision_to": "2026-12-31T23:59:59.999000+00:00",
        "source_updated_from": "2026-02-01T00:00:00+00:00",
        "source_updated_to": "2026-12-31T23:59:59.999000+00:00",
        "limit": 500,
        "cursor": opaque_cursor,
        "sort": ["subject:asc"],
    }
    epidemiology_domain = next(call for call in calls if call[1] == "/internal/v1/domain/epidemiology-observations")
    assert epidemiology_domain[2]["params"] == {
        "disease_entity_id": "disease-1",
        "q": "NSCLC burden",
        "measure": "prevalence",
        "geography": "China",
        "unit": "patients",
        "population_scope": "adults",
        "age_group": "18+",
        "sex": "all",
        "period_start_from": "2025-01-01T00:00:00+00:00",
        "period_end_to": "2025-12-31T00:00:00+00:00",
        "patient_population_id": "population-1",
        "limit": 500,
        "cursor": opaque_cursor,
        "sort": ["value:asc"],
    }
    news_domain = next(call for call in calls if call[1] == "/internal/v1/domain/news-events")
    assert news_domain[2]["params"] == {
        "entity_id": "target-1",
        "q": "Phase 2 update",
        "event_type": "press_release",
        "publisher": "Victor Therapeutics",
        "language": "en",
        "venue": "ASCO 2026",
        "published_from": "2026-01-01T00:00:00+00:00",
        "published_to": "2026-12-31T00:00:00+00:00",
        "limit": 500,
        "cursor": opaque_cursor,
        "sort": ["title:asc"],
    }
    pageable_classes = {
        "evidence.search",
        "target.evidence.search",
        "bioactivity.search",
        "sar.compare",
        "pipeline.search",
        "structure.search",
        "structure.similarity",
        "trial.search",
        "patent.search",
        "deal.search",
        "company.timeline",
        "regulatory.search",
        "epidemiology.search",
        "news.search",
        "knowledge.search",
    }
    pageable_reservations = [call for call in reserve_calls if call[2]["json"]["billing_class"] in pageable_classes]
    assert len(pageable_reservations) == 15
    assert all(call[2]["json"]["request_arguments"]["cursor"] == opaque_cursor for call in pageable_reservations)
    pageable_domain_calls = [call for call in calls if call[2].get("params", {}).get("cursor") == opaque_cursor]
    assert len(pageable_domain_calls) == 15
    evidence_reservation = next(call for call in reserve_calls if call[2]["json"]["billing_class"] == "evidence.search")
    assert evidence_reservation[2]["json"]["request_arguments"]["entity_types"] == []
    evidence_domain = next(call for call in calls if call[1] == "/internal/v1/domain/evidence/search")
    assert evidence_domain[2]["json"]["entity_types"] == []

    chemistry_reservation = next(
        call for call in reserve_calls if call[2]["json"]["billing_class"] == "structure.similarity"
    )
    assert chemistry_reservation[2]["json"]["requested_compute_units"] == "1"
    chemistry_settlement = next(
        call for call in settle_calls if call[2]["json"]["metrics"]["tool"] == "structure.similarity"
    )
    assert chemistry_settlement[2]["json"]["metrics"]["compute_units"] == "1"


@pytest.mark.anyio
async def test_settled_idempotent_replay_returns_durable_result_without_domain_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_request(_ctx: McpContext, _method: str, path: str, **_kwargs: Any) -> Any:
        calls.append(path)
        return {
            "reservation_id": "reservation-1",
            "state": "settled",
            "billing_class": "entity.search",
            "estimated_units": "1.00000000",
            "reserved_units": "10.00000000",
            "lease_expires_at": "2026-07-16T01:00:00Z",
            "page_depth": 1,
            "replayed": True,
            "settlement": {
                "settlement_id": "settlement-1",
                "usage_event_id": "usage-1",
                "charged_units": "1.11000000",
                "result_count": 1,
                "unique_record_count": 1,
                "new_unique_record_count": 1,
                "response_bytes": 100,
                "price_breakdown": {},
                "result": {"items": [{"id": "egfr"}]},
                "created_at": "2026-07-16T00:00:00Z",
            },
        }

    monkeypatch.setattr(mcp_server, "api_request", fake_request)
    result = await mcp_server.search_entities(cast(McpContext, object()), "EGFR", "replay-key-00001", "10")

    assert result["data"] == {"items": [{"id": "egfr"}]}
    assert result["usage"]["replayed"] is True
    assert calls == ["/internal/v1/commercial/reservations"]


@pytest.mark.anyio
async def test_domain_failure_releases_reservation_without_settlement(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_request(_ctx: McpContext, _method: str, path: str, **kwargs: Any) -> Any:
        calls.append(path)
        if path == "/internal/v1/commercial/reservations":
            return {
                "reservation_id": "reservation-1",
                "state": "reserved",
                "billing_class": kwargs["json"]["billing_class"],
                "replayed": False,
            }
        if path.endswith("/release"):
            return {"state": "released"}
        raise RuntimeError("domain unavailable")

    monkeypatch.setattr(mcp_server, "api_request", fake_request)
    with pytest.raises(RuntimeError, match="domain unavailable"):
        await mcp_server.search_entities(cast(McpContext, object()), "EGFR", "failure-key-0001", "10")

    assert calls == [
        "/internal/v1/commercial/reservations",
        "/internal/v1/domain/entities",
        "/internal/v1/commercial/reservations/reservation-1/release",
    ]
    assert not any(path.endswith("/settle") for path in calls)


@pytest.mark.anyio
async def test_commercial_http_forbidden_becomes_safe_entitlement_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("POST", "http://api.internal/internal/v1/commercial/reservations")
    response = httpx.Response(403, request=request, json={"detail": "Insufficient scope"})
    upstream_error = httpx.HTTPStatusError("internal URL must not escape", request=request, response=response)

    async def denied_request(_ctx: McpContext, **_kwargs: Any) -> dict[str, Any]:
        raise upstream_error

    monkeypatch.setattr(mcp_server, "_commercial_api_request", denied_request)

    with pytest.raises(mcp_server.McpCommercialError) as error:
        await mcp_server.commercial_api_request(
            cast(McpContext, object()),
            billing_class="entity.dossier",
            idempotency_key="entitlement-error-0001",
            max_billable_units="10",
            requested_result_limit=1,
            request_arguments={"entity_id": "entity-1"},
            method="GET",
            path="/internal/v1/domain/entities/entity-1/dossier",
        )

    assert error.value.code == "ENTITLEMENT_REQUIRED"
    assert str(error.value) == (
        "ENTITLEMENT_REQUIRED: The requested data access is not included in the active Agent subscription"
    )
    assert "api.internal" not in str(error.value)
    assert "Insufficient scope" not in str(error.value)


@pytest.mark.anyio
async def test_cancellation_during_reservation_creation_waits_for_and_releases_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    reservation_started = asyncio.Event()
    allow_reservation = asyncio.Event()
    reservation_released = asyncio.Event()

    async def fake_request(_ctx: McpContext, _method: str, path: str, **kwargs: Any) -> Any:
        calls.append(path)
        if path == "/internal/v1/commercial/reservations":
            reservation_started.set()
            await allow_reservation.wait()
            return {
                "reservation_id": "reservation-cancelled",
                "state": "reserved",
                "billing_class": kwargs["json"]["billing_class"],
                "replayed": False,
            }
        if path.endswith("/release"):
            assert kwargs["json"]["reason"] == "caller cancelled before domain execution"
            reservation_released.set()
            return {"state": "released"}
        raise AssertionError("domain execution must not start after cancellation")

    monkeypatch.setattr(mcp_server, "api_request", fake_request)
    task = asyncio.create_task(
        mcp_server.search_entities(cast(McpContext, object()), "EGFR", "cancel-reserve-key-1", "10")
    )
    await reservation_started.wait()
    task.cancel()
    allow_reservation.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(reservation_released.wait(), timeout=1)
    await _wait_for_cancelled_operations()

    assert calls == [
        "/internal/v1/commercial/reservations",
        "/internal/v1/commercial/reservations/reservation-cancelled/release",
    ]
    assert not mcp_server._cancelled_commercial_operations  # noqa: SLF001


@pytest.mark.anyio
async def test_cancellation_during_domain_read_finishes_cleanup_without_settlement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    domain_started = asyncio.Event()
    allow_domain = asyncio.Event()
    reservation_released = asyncio.Event()

    async def fake_request(_ctx: McpContext, _method: str, path: str, **kwargs: Any) -> Any:
        calls.append(path)
        if path == "/internal/v1/commercial/reservations":
            return {
                "reservation_id": "reservation-domain-cancelled",
                "state": "reserved",
                "billing_class": kwargs["json"]["billing_class"],
                "replayed": False,
            }
        if path == "/internal/v1/domain/entities":
            domain_started.set()
            await allow_domain.wait()
            return {"items": []}
        if path.endswith("/release"):
            reservation_released.set()
            return {"state": "released"}
        raise AssertionError("cancellation must not settle usage")

    monkeypatch.setattr(mcp_server, "api_request", fake_request)
    task = asyncio.create_task(
        mcp_server.search_entities(cast(McpContext, object()), "EGFR", "cancel-domain-key-1", "10")
    )
    await domain_started.wait()
    task.cancel()
    allow_domain.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(reservation_released.wait(), timeout=1)
    await _wait_for_cancelled_operations()

    assert calls == [
        "/internal/v1/commercial/reservations",
        "/internal/v1/domain/entities",
        "/internal/v1/commercial/reservations/reservation-domain-cancelled/release",
    ]
    assert not mcp_server._cancelled_commercial_operations  # noqa: SLF001
