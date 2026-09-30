from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI
from starlette.applications import Starlette
from starlette.routing import Router
from starlette.types import ASGIApp, Receive, Scope, Send

from pharma_intel.api import app as api_app
from pharma_intel.config import get_settings
from pharma_intel.mcp_server import build_http_app_components
from pharma_intel.telemetry import instrument_fastapi

MCP_HTTP_PATHS = frozenset({"/mcp", "/.well-known/oauth-protected-resource/mcp"})


class UnifiedGatewayApplication:
    """Route human/API and MCP traffic through one supervised ASGI process."""

    def __init__(self, api: FastAPI, mcp: ASGIApp, mcp_lifespan_app: Starlette) -> None:
        self.api = api
        self.mcp = mcp

        @asynccontextmanager
        async def lifespan(_: Any) -> AsyncIterator[None]:
            async with api.router.lifespan_context(api):
                async with mcp_lifespan_app.router.lifespan_context(mcp_lifespan_app):
                    yield

        self._lifespan_router = Router(lifespan=lifespan)

    @staticmethod
    def is_mcp_path(path: str) -> bool:
        return path in MCP_HTTP_PATHS or path.startswith("/mcp/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._lifespan_router(scope, receive, send)
            return
        target = self.mcp if self.is_mcp_path(str(scope.get("path", ""))) else self.api
        await target(scope, receive, send)


def build_gateway_app() -> UnifiedGatewayApplication:
    mcp_app, mcp_lifespan_app = build_http_app_components()
    return UnifiedGatewayApplication(api_app, mcp_app, mcp_lifespan_app)


app = build_gateway_app()


def run() -> None:
    settings = get_settings()
    instrument_fastapi(api_app, "pharma-gateway")
    uvicorn.run(app, host=settings.app_host, port=settings.app_port, log_level=settings.log_level.lower())
