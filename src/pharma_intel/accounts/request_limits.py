from __future__ import annotations

from fastapi import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

ACCOUNT_BODY_LIMIT = 16 * 1024
BOUNDED_ACCOUNT_REQUESTS = {
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/login"),
    ("PATCH", "/api/v1/auth/me"),
    ("POST", "/api/v1/auth/me/password"),
    ("POST", "/api/v1/auth/invitations/accept"),
    ("POST", "/api/v1/auth/organizations/join"),
    ("POST", "/api/v1/auth/oidc/invitation"),
}


class AccountRequestLimits:
    """Bound credential and identity requests before parsing, including chunked bodies."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or (scope.get("method"), scope.get("path")) not in BOUNDED_ACCOUNT_REQUESTS:
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        declared = headers.get(b"content-length")
        if declared is not None:
            if not declared.isdigit():
                await JSONResponse({"detail": "账号请求长度无效"}, status_code=400)(scope, receive, send)
                return
            significant = declared.lstrip(b"0") or b"0"
            if len(significant) > 6 or int(significant) > ACCOUNT_BODY_LIMIT:
                await JSONResponse({"detail": "账号请求过大"}, status_code=413)(scope, receive, send)
                return
        consumed = 0

        async def bounded_receive() -> Message:
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > ACCOUNT_BODY_LIMIT:
                    raise HTTPException(status_code=413, detail="账号请求过大")
            return message

        await self.app(scope, bounded_receive, send)
