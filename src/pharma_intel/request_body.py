from __future__ import annotations

from collections.abc import Mapping

from fastapi import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BoundedRequestBodies:
    """One declared/streamed byte boundary, before FastAPI JSON allocation."""

    def __init__(self, app: ASGIApp, limits: Mapping[tuple[str, str], tuple[int, str]]) -> None:
        self.app = app
        self.limits = limits

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        policy = self.limits.get((scope.get("method", ""), scope.get("path", "")))
        if scope["type"] != "http" or policy is None:
            await self.app(scope, receive, send)
            return
        maximum, label = policy
        declared = dict(scope.get("headers", [])).get(b"content-length")
        if declared is not None:
            if not declared.isdigit():
                await JSONResponse({"detail": f"{label}请求长度无效"}, status_code=400)(scope, receive, send)
                return
            significant = declared.lstrip(b"0") or b"0"
            if len(significant) > 6 or int(significant) > maximum:
                await JSONResponse({"detail": f"{label}请求过大"}, status_code=413)(scope, receive, send)
                return
        consumed = 0

        async def bounded_receive() -> Message:
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > maximum:
                    raise HTTPException(status_code=413, detail=f"{label}请求过大")
            return message

        await self.app(scope, bounded_receive, send)
