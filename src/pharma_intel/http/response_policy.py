from __future__ import annotations

from fastapi.responses import Response


def _prevent_secret_caching(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
