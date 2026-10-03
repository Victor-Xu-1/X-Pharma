from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import Response
from opentelemetry import trace
from sqlalchemy.orm import Session

from pharma_intel.db import get_session_factory, set_tenant_context
from pharma_intel.models import AuditEvent
from pharma_intel.research_activity import RequestAuditResource
from pharma_intel.security import Principal
from pharma_intel.web_assets import workspace_cache_headers_for_path

request_logger = structlog.get_logger("pharma_intel.request")


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


REQUEST_AUDIT_EXEMPT_PATHS = frozenset({"/api/v1/workspace/web-vitals"})


RDKIT_WORKER_ASSET_PATTERN = re.compile(r"^/assets/rdkit\.worker-[A-Za-z0-9_-]+\.js$")


INDIGO_WORKER_ASSET_PATTERN = re.compile(r"^/assets/indigoWorker-[A-Za-z0-9_-]+\.js$")


BROWSER_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "worker-src 'self'; "
        "manifest-src 'self'"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


RDKIT_WORKER_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self' 'unsafe-eval'; connect-src 'self'; object-src 'none'"
)


INDIGO_WORKER_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; connect-src 'self'; object-src 'none'"
)


def browser_security_headers_for_path(path: str) -> dict[str, str]:
    headers = dict(BROWSER_SECURITY_HEADERS)
    if RDKIT_WORKER_ASSET_PATTERN.fullmatch(path):
        headers["Content-Security-Policy"] = RDKIT_WORKER_CONTENT_SECURITY_POLICY
    elif INDIGO_WORKER_ASSET_PATTERN.fullmatch(path):
        headers["Content-Security-Policy"] = INDIGO_WORKER_CONTENT_SECURITY_POLICY
    return headers


async def request_audit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    incoming = request.headers.get("X-Request-ID", "")
    request_id = incoming if REQUEST_ID_PATTERN.fullmatch(incoming) else str(uuid.uuid4())
    request.state.request_id = request_id
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute("pharma.request_id", request_id)
    response_status = 500
    try:
        response = await call_next(request)
        response_status = response.status_code
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith(("/api/", "/internal/")):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        for header, value in browser_security_headers_for_path(request.url.path).items():
            response.headers.setdefault(header, value)
        if 200 <= response_status < 400:
            for header, value in workspace_cache_headers_for_path(request.url.path).items():
                response.headers.setdefault(header, value)
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        return response
    finally:
        principal = getattr(request.state, "principal", None)
        if (
            isinstance(principal, Principal)
            and request.url.path.startswith(("/api/", "/internal/"))
            and request.url.path not in REQUEST_AUDIT_EXEMPT_PATHS
        ):
            audit_session: Session | None = None
            owns_audit_session = False
            try:
                audit_session = getattr(request.state, "db_session", None)
                if not isinstance(audit_session, Session):
                    # Dependency-owned request sessions are closed before middleware unwinds. Keep
                    # audit persistence independent so read-only routes are audited as reliably as writes.
                    audit_session = get_session_factory()()
                    owns_audit_session = True
                if audit_session.in_transaction():
                    audit_session.rollback()
                set_tenant_context(audit_session, principal.tenant_id)
                resource = getattr(request.state, "audit_resource", None)
                audit_session.add(
                    AuditEvent(
                        tenant_id=principal.tenant_id,
                        actor_type=principal.actor_type,
                        actor_id=principal.actor_id,
                        action=f"{request.method} {request.url.path}",
                        resource_type=resource.resource_type
                        if isinstance(resource, RequestAuditResource)
                        else "http_request",
                        resource_id=resource.resource_id if isinstance(resource, RequestAuditResource) else None,
                        outcome="success" if response_status < 400 else "failure",
                        request_id=request_id,
                        details={
                            "status_code": response_status,
                            **(resource.details if isinstance(resource, RequestAuditResource) else {}),
                        },
                    )
                )
                audit_session.commit()
            except Exception as exc:
                if isinstance(audit_session, Session):
                    audit_session.rollback()
                request_logger.error("audit_write_failed", request_id=request_id, error_type=type(exc).__name__)
            finally:
                if owns_audit_session and isinstance(audit_session, Session):
                    audit_session.close()


def install_request_boundary(app: FastAPI) -> None:
    app.middleware("http")(request_audit_middleware)
