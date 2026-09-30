from __future__ import annotations

from importlib.metadata import metadata

from fastapi.testclient import TestClient

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
