from __future__ import annotations

import asyncio
import json
import tomllib
from datetime import timedelta
from importlib.metadata import metadata
from pathlib import Path

from fastapi.testclient import TestClient
from mcp.shared.memory import create_connected_server_and_client_session

from pharma_intel import __version__
from pharma_intel.api import app
from pharma_intel.mcp_server import mcp
from pharma_intel.product import PRODUCT_NAME, PROJECT_URL


def test_product_metadata_and_both_interfaces_expose_x_pharma() -> None:
    assert metadata("x-pharma")["Name"] == "X-Pharma"
    assert PROJECT_URL == "https://github.com/Victor-Xu-1/X-Pharma"
    assert metadata("x-pharma")["License-Expression"] == "Apache-2.0"
    assert metadata("x-pharma")["Version"] == __version__
    assert app.openapi()["info"]["title"] == PRODUCT_NAME == "X-Pharma"
    assert app.openapi()["info"]["version"] == __version__
    assert mcp.name == PRODUCT_NAME


def test_rebranding_preserves_liveness_and_protected_api_boundary() -> None:
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/api/v1/enterprise/users").status_code == 401


def test_first_party_versions_match_the_authoritative_product_manifest() -> None:
    root = Path(__file__).parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    web = json.loads((root / "apps/web/package.json").read_text())
    contract = json.loads((root / "docs/openapi.json").read_text())
    assert project["version"] == __version__ == "0.1.0"
    assert web["version"] == contract["info"]["version"] == __version__


def test_liveness_exposes_product_identity_without_changing_readiness_or_authorization() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")
        assert response.json() == {"status": "ok", "product": PRODUCT_NAME, "version": __version__}
        assert client.get("/api/v1/enterprise/users").status_code == 401


def test_real_mcp_initialization_reports_product_version_not_sdk_version() -> None:
    async def initialize() -> None:
        async with create_connected_server_and_client_session(mcp, read_timeout_seconds=timedelta(seconds=5)) as client:
            result = await client.initialize()
            assert result.serverInfo.name == PRODUCT_NAME
            assert result.serverInfo.version == __version__
            assert result.protocolVersion == "2025-11-25"

    asyncio.run(initialize())
