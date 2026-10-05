from __future__ import annotations

from starlette.types import ASGIApp

from pharma_intel.request_body import BoundedRequestBodies

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


class AccountRequestLimits(BoundedRequestBodies):
    """Bound credential and identity requests before parsing, including chunked bodies."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app, {key: (ACCOUNT_BODY_LIMIT, "账号") for key in BOUNDED_ACCOUNT_REQUESTS})
