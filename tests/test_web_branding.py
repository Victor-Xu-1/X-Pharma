from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pharma_intel.web_branding import install_web_branding

ROOT = Path(__file__).parents[1]
ICON = ROOT / "apps" / "web" / "src" / "assets" / "brand" / "X-Pharma-favicon.ico"


def _application(root: Path, *, docs_enabled: bool = True, root_path: str = "") -> FastAPI:
    application = FastAPI(
        title="X-Pharma",
        docs_url=None,
        redoc_url=None,
        root_path=root_path,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    install_web_branding(application, root, docs_enabled=docs_enabled)
    return application


def _install_icon(root: Path) -> Path:
    assets = root / "assets"
    assets.mkdir()
    destination = assets / "X-Pharma-favicon-Abcd0123.ico"
    destination.write_bytes(ICON.read_bytes())
    return destination


def test_real_browser_default_favicon_uses_the_supplied_icon_and_revalidates(tmp_path: Path) -> None:
    _install_icon(tmp_path)
    with TestClient(_application(tmp_path)) as client:
        response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.content == ICON.read_bytes()
    assert response.headers["content-type"] == "image/x-icon"
    assert response.headers["cache-control"] == "no-cache, must-revalidate"


def test_favicon_head_has_the_same_metadata_without_a_body(tmp_path: Path) -> None:
    _install_icon(tmp_path)
    with TestClient(_application(tmp_path)) as client:
        response = client.head("/favicon.ico")
    assert response.status_code == 200
    assert response.content == b""
    assert int(response.headers["content-length"]) == ICON.stat().st_size
    assert response.headers["cache-control"] == "no-cache, must-revalidate"


@pytest.mark.parametrize("entry", ["/docs", "/redoc"])
def test_optional_documentation_uses_local_branded_icons(tmp_path: Path, entry: str) -> None:
    with TestClient(_application(tmp_path, root_path="/platform")) as client:
        response = client.get(entry)
    assert response.status_code == 200
    assert 'href="/platform/favicon.ico"' in response.text
    assert "favicon.png" not in response.text
    assert "X-Pharma - API" in response.text
    assert "/platform/openapi.json" in response.text


def test_branding_does_not_reenable_disabled_api_documentation(tmp_path: Path) -> None:
    _install_icon(tmp_path)
    with TestClient(_application(tmp_path, docs_enabled=False)) as client:
        for path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
            assert client.get(path).status_code == 404
        assert client.get("/favicon.ico").status_code == 200


def test_missing_or_ambiguous_icons_fail_without_serving_an_arbitrary_file(tmp_path: Path) -> None:
    with TestClient(_application(tmp_path)) as client:
        assert client.get("/favicon.ico").status_code == 404
        _install_icon(tmp_path)
        (tmp_path / "assets" / "X-Pharma-favicon-Efgh4567.ico").write_bytes(b"other icon")
        assert client.get("/favicon.ico").status_code == 404


def test_icon_symlinks_cannot_expose_a_file_outside_the_build(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    outside = tmp_path / "private-file"
    outside.write_bytes(b"not a public brand icon")
    (assets / "X-Pharma-favicon-Abcd0123.ico").symlink_to(outside)
    with TestClient(_application(tmp_path)) as client:
        assert client.get("/favicon.ico").status_code == 404


def test_symlinked_asset_directory_is_not_a_brand_source(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    _install_icon(outside)
    build = tmp_path / "build"
    build.mkdir()
    (build / "assets").symlink_to(outside / "assets", target_is_directory=True)
    with TestClient(_application(build)) as client:
        assert client.get("/favicon.ico").status_code == 404
