from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from pharma_intel.api import app
from pharma_intel.web_assets import workspace_cache_headers_for_path


def test_workspace_html_entries_revalidate_after_deployment() -> None:
    expected = {"Cache-Control": "no-cache, must-revalidate"}

    assert workspace_cache_headers_for_path("/workspace/research") == expected
    assert workspace_cache_headers_for_path("/workspace/internal") == expected
    assert workspace_cache_headers_for_path("/research.html") == expected
    assert workspace_cache_headers_for_path("/") == expected


def test_hashed_workspace_assets_are_immutable() -> None:
    assert workspace_cache_headers_for_path("/assets/preload-helper-Dzq0COLC.css") == {
        "Cache-Control": "public, max-age=31536000, immutable"
    }


def test_hashed_browser_icons_revalidate_by_content_identity() -> None:
    for path in ("/assets/X-Pharma-favicon-Abcd0123.ico", "/assets/X-Pharma-favicon-32-Abcd0123.png"):
        assert workspace_cache_headers_for_path(path) == {"Cache-Control": "public, max-age=31536000, immutable"}
    assert workspace_cache_headers_for_path("/favicon.ico") == {}


def test_non_workspace_api_paths_keep_existing_cache_policy() -> None:
    assert workspace_cache_headers_for_path("/api/v1/entities") == {}


def test_unversioned_or_invalid_asset_paths_are_not_permanently_cached() -> None:
    for path in ("/assets/main.js", "/assets/main-abc.js", "/assets/../main-Abcd0123.js"):
        assert workspace_cache_headers_for_path(path) == {}


def test_real_static_response_receives_policy_but_missing_asset_does_not(tmp_path: Path) -> None:
    (tmp_path / "main-Abcd0123.js").write_text("export const name = 'X-Pharma';\n")
    route = Mount("/assets", app=StaticFiles(directory=tmp_path))
    app.router.routes.insert(0, route)
    try:
        with TestClient(app) as client:
            response = client.get("/assets/main-Abcd0123.js")
            assert response.status_code == 200
            assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
            missing = client.get("/assets/missing-Abcd0123.js")
            assert missing.status_code == 404
            assert "immutable" not in missing.headers.get("cache-control", "")
    finally:
        app.router.routes.remove(route)
