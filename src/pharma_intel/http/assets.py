from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def install_workspace_assets(app: FastAPI, web_root: Path) -> None:
    if not web_root.is_dir():
        return

    @app.api_route("/workspace/research", methods=["GET", "HEAD"], include_in_schema=False)
    def research_workspace_entry() -> FileResponse:
        return FileResponse(web_root / "research.html")

    @app.api_route("/workspace/internal", methods=["GET", "HEAD"], include_in_schema=False)
    def internal_workspace_entry() -> FileResponse:
        return FileResponse(web_root / "internal.html")

    app.mount("/", StaticFiles(directory=web_root, html=True), name="workspace")
