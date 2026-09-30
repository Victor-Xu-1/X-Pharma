from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from pharma_intel.gateway import UnifiedGatewayApplication


def test_unified_gateway_dispatches_api_and_mcp_with_one_lifespan() -> None:
    lifecycle: list[str] = []

    @asynccontextmanager
    async def api_lifespan(_: FastAPI) -> AsyncIterator[None]:
        lifecycle.append("api-start")
        yield
        lifecycle.append("api-stop")

    @asynccontextmanager
    async def mcp_lifespan(_: Starlette) -> AsyncIterator[None]:
        lifecycle.append("mcp-start")
        yield
        lifecycle.append("mcp-stop")

    api = FastAPI(lifespan=api_lifespan)

    @api.get("/health/live")
    def health() -> dict[str, str]:
        return {"surface": "api"}

    async def mcp_endpoint(_request: object) -> JSONResponse:
        return JSONResponse({"surface": "mcp"})

    async def metadata_endpoint(_request: object) -> JSONResponse:
        return JSONResponse({"surface": "metadata"})

    mcp = Starlette(
        routes=[
            Route("/mcp", mcp_endpoint),
            Route("/.well-known/oauth-protected-resource/mcp", metadata_endpoint),
        ],
        lifespan=mcp_lifespan,
    )
    gateway = UnifiedGatewayApplication(api, mcp, mcp)

    with TestClient(gateway) as client:
        assert client.get("/health/live").json() == {"surface": "api"}
        assert client.get("/mcp").json() == {"surface": "mcp"}
        assert client.get("/.well-known/oauth-protected-resource/mcp").json() == {"surface": "metadata"}
        assert lifecycle == ["api-start", "mcp-start"]

    assert lifecycle == ["api-start", "mcp-start", "mcp-stop", "api-stop"]


def test_gateway_only_routes_owned_mcp_paths_to_the_agent_surface() -> None:
    assert UnifiedGatewayApplication.is_mcp_path("/mcp")
    assert UnifiedGatewayApplication.is_mcp_path("/mcp/messages")
    assert UnifiedGatewayApplication.is_mcp_path("/.well-known/oauth-protected-resource/mcp")
    assert not UnifiedGatewayApplication.is_mcp_path("/api/v1/entities")
    assert not UnifiedGatewayApplication.is_mcp_path("/workspace/research")
    assert not UnifiedGatewayApplication.is_mcp_path("/.well-known/openid-configuration")
