"""Local brand icons for browser defaults and optional developer documentation."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.responses import FileResponse, HTMLResponse

BRAND_ICON_NAME = re.compile(r"X-Pharma-favicon-[A-Za-z0-9_-]{8,}\.ico")


def install_web_branding(application: FastAPI, web_root: Path, *, docs_enabled: bool) -> None:
    @application.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
    def favicon() -> FileResponse:
        assets = web_root / "assets"
        if web_root.is_symlink() or assets.is_symlink():
            raise HTTPException(status_code=404, detail="Brand icon unavailable; build the web workspace")
        icons = [
            candidate
            for candidate in assets.glob("X-Pharma-favicon-*.ico")
            if BRAND_ICON_NAME.fullmatch(candidate.name) and not candidate.is_symlink() and candidate.is_file()
        ]
        if len(icons) != 1:
            raise HTTPException(status_code=404, detail="Brand icon unavailable; build the web workspace")
        return FileResponse(icons[0], media_type="image/x-icon", headers={"Cache-Control": "no-cache, must-revalidate"})

    if not docs_enabled:
        return
    if application.openapi_url is None:
        raise ValueError("Interactive API documentation requires a configured OpenAPI URL")
    openapi_url = application.openapi_url

    @application.get("/docs", include_in_schema=False)
    def swagger(request: Request) -> HTMLResponse:
        prefix = quote(request.scope.get("root_path", "").rstrip("/"), safe="/")
        return get_swagger_ui_html(
            openapi_url=f"{prefix}{openapi_url}",
            title=f"{application.title} - API",
            swagger_favicon_url=f"{prefix}/favicon.ico",
            oauth2_redirect_url=f"{prefix}/docs/oauth2-redirect",
            init_oauth=application.swagger_ui_init_oauth,
            swagger_ui_parameters=application.swagger_ui_parameters,
        )

    @application.get("/docs/oauth2-redirect", include_in_schema=False)
    def oauth_redirect() -> HTMLResponse:
        return get_swagger_ui_oauth2_redirect_html()

    @application.get("/redoc", include_in_schema=False)
    def redoc(request: Request) -> HTMLResponse:
        prefix = quote(request.scope.get("root_path", "").rstrip("/"), safe="/")
        return get_redoc_html(
            openapi_url=f"{prefix}{openapi_url}",
            title=f"{application.title} - API",
            redoc_favicon_url=f"{prefix}/favicon.ico",
        )
