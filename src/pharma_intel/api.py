from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pharma_intel import __version__
from pharma_intel.accounts.request_limits import AccountRequestLimits
from pharma_intel.http import runtime
from pharma_intel.http.assets import install_workspace_assets
from pharma_intel.http.errors import install_error_handlers
from pharma_intel.http.middleware import install_request_boundary
from pharma_intel.http.routing import install_feature_routes
from pharma_intel.product import PRODUCT_NAME
from pharma_intel.request_body import BoundedRequestBodies
from pharma_intel.telemetry import instrument_fastapi
from pharma_intel.web_branding import install_web_branding


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = runtime.get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    structlog.configure(processors=[structlog.processors.add_log_level, structlog.processors.JSONRenderer()])
    yield


def create_app() -> FastAPI:
    """Compose the single HTTP boundary without owning domain behavior."""
    settings = runtime.get_settings()
    application = FastAPI(
        title=PRODUCT_NAME,
        version=__version__,
        description="Structured pharmaceutical intelligence and evidence retrieval API",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )
    # The machine contract is pinned independently of interactive docs.
    application.openapi_version = "3.1.2"
    install_feature_routes(application)
    application.add_middleware(AccountRequestLimits)
    application.add_middleware(
        BoundedRequestBodies, limits={("POST", "/api/v1/public-research/search"): (4096, "公开检索")}
    )
    install_web_branding(application, settings.web_root, docs_enabled=settings.api_docs_enabled)
    install_error_handlers(application)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.public_base_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Account-ID", "X-Organization-ID"],
    )
    install_request_boundary(application)
    install_workspace_assets(application, settings.web_root)
    return application


app = create_app()


def run() -> None:
    settings = runtime.get_settings()
    instrument_fastapi(app, "pharma-api")
    uvicorn.run("pharma_intel.api:app", host=settings.app_host, port=settings.app_port)
