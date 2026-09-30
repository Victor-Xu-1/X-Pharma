from __future__ import annotations

from fastapi import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REGISTRATION_BODY_LIMIT = 16 * 1024


class RegistrationRequestLimits:
    """Bound anonymous registration before JSON parsing, including chunked requests."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != "/api/v1/auth/register" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        declared = headers.get(b"content-length")
        if declared is not None:
            if not declared.isdigit():
                await JSONResponse({"detail": "注册请求长度无效"}, status_code=400)(scope, receive, send)
                return
            significant = declared.lstrip(b"0") or b"0"
            if len(significant) > 6 or int(significant) > REGISTRATION_BODY_LIMIT:
                await JSONResponse({"detail": "注册请求过大"}, status_code=413)(scope, receive, send)
                return
        consumed = 0

        async def bounded_receive() -> Message:
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > REGISTRATION_BODY_LIMIT:
                    raise HTTPException(status_code=413, detail="注册请求过大")
            return message

        await self.app(scope, bounded_receive, send)
