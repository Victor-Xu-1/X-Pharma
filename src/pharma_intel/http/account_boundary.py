from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from pharma_intel.accounts.service import AccountAccessDenied, AccountConflict, AccountNotFound
from pharma_intel.http import runtime


def _account_error(error: AccountAccessDenied | AccountConflict | AccountNotFound) -> HTTPException:
    status = 403 if isinstance(error, AccountAccessDenied) else 409 if isinstance(error, AccountConflict) else 404
    return HTTPException(status_code=status, detail=str(error))


def require_account_origin(request: Request) -> None:
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        raise HTTPException(status_code=403, detail="请从本工作台提交账号操作")
    origin = request.headers.get("origin")
    if origin:
        configured = urlsplit(runtime.get_settings().public_base_url)
        if origin != f"{configured.scheme}://{configured.netloc}":
            raise HTTPException(status_code=403, detail="请从本工作台提交账号操作")
