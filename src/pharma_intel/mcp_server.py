import asyncio
import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast
from urllib.parse import urlsplit

import anyio
import httpx
import structlog
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import Context, FastMCP
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.types import ASGIApp

from pharma_intel.commercial.cursor import INVALID_CURSOR_CODE
from pharma_intel.config import get_settings
from pharma_intel.dossier import DOSSIER_RECORD_COLLECTIONS, dossier_result_capacity
from pharma_intel.mcp_auth import build_token_verifier
from pharma_intel.mcp_dpop import DpopProofVerifier, DpopSenderConstraintMiddleware, ValkeyDpopReplayStore
from pharma_intel.operational_metrics import McpOutcome, operational_metrics
from pharma_intel.product import PRODUCT_NAME, PRODUCT_VERSION
from pharma_intel.request_correlation import (
    NETWORK_FINGERPRINT_HEADER,
    CorrelationSignalError,
    network_fingerprint,
)
from pharma_intel.schemas import (
    CLINICAL_TRIAL_SORT_FIELDS,
    DEAL_SORT_FIELDS,
    ENTITY_SORT_FIELDS,
    EPIDEMIOLOGY_SORT_FIELDS,
    NEWS_SORT_FIELDS,
    PATENT_SORT_FIELDS,
    PIPELINE_SORT_FIELDS,
    REGULATORY_SORT_FIELDS,
)
from pharma_intel.sorting import SortDirection, resolve_sort_clauses
from pharma_intel.telemetry import initialize_telemetry

settings = get_settings()
logger = structlog.get_logger("pharma_intel.mcp.commercial")

COMMERCIAL_DATETIME_ARGUMENTS = frozenset(
    {
        "announced_from",
        "announced_to",
        "china_phase_started_from",
        "china_phase_started_to",
        "decision_from",
        "decision_to",
        "disclosed_from",
        "disclosed_to",
        "global_phase_started_from",
        "global_phase_started_to",
        "milestone_from",
        "milestone_to",
        "period_end_to",
        "period_start_from",
        "published_from",
        "published_to",
        "results_posted_from",
        "results_posted_to",
        "source_updated_from",
        "source_updated_to",
        "terminated_from",
        "terminated_to",
    }
)


@dataclass
class McpRuntime:
    api_client: httpx.AsyncClient


class McpContext(Context[Any, McpRuntime, Any]):
    """Concrete annotation required by FastMCP 1.x context injection."""


@dataclass(frozen=True)
class ApiRequestOverride:
    client: httpx.AsyncClient
    access_token: str
    correlation_headers: dict[str, str]


_api_request_override: ContextVar[ApiRequestOverride | None] = ContextVar("mcp_api_request_override", default=None)


class McpCommercialError(RuntimeError):
    """Safe, machine-readable failure for a commercial MCP tool call."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _commercial_error_code(response: httpx.Response) -> str | None:
    # Only a bounded, allowlisted machine code crosses the API/MCP boundary.
    # Provider text, URLs and arbitrary nested payloads are never forwarded.
    if len(response.content) > 4096:
        return None
    try:
        payload = response.json()
    except (ValueError, RecursionError):
        return None
    if isinstance(payload, dict) and payload.get("code") == INVALID_CURSOR_CODE:
        return INVALID_CURSOR_CODE
    return None


def _safe_commercial_http_error(error: httpx.HTTPStatusError) -> McpCommercialError:
    status_code = error.response.status_code
    if status_code == 401:
        return McpCommercialError("AUTHENTICATION_REQUIRED", "Agent authentication is required or has expired")
    if status_code == 402:
        return McpCommercialError(
            "INSUFFICIENT_CREDIT",
            "The active Agent subscription does not have enough available credit",
        )
    if status_code == 403:
        if _commercial_error_code(error.response) == INVALID_CURSOR_CODE:
            return McpCommercialError(
                INVALID_CURSOR_CODE, "The pagination cursor is invalid or expired; restart the query"
            )
        return McpCommercialError(
            "ENTITLEMENT_REQUIRED",
            "The requested data access is not included in the active Agent subscription",
        )
    if status_code == 409:
        return McpCommercialError("REQUEST_CONFLICT", "The commercial request conflicts with an existing request state")
    if status_code == 429:
        return McpCommercialError("RATE_LIMITED", "The request rate limit has been reached")
    if status_code >= 500:
        return McpCommercialError("UPSTREAM_UNAVAILABLE", "The commercial data service is temporarily unavailable")
    return McpCommercialError("REQUEST_REJECTED", "The commercial request was rejected by the platform")


def _internal_api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.agent_api_base_url,
        timeout=httpx.Timeout(60, connect=10),
        follow_redirects=False,
        trust_env=False,
    )


def _validate_internal_api_path(path: str) -> None:
    """Keep MCP's privileged internal client on the application API origin."""

    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
        raise RuntimeError("MCP internal API path must be an absolute application-relative path")
    if any(character in path for character in ("\x00", "\r", "\n", "\\")):
        raise RuntimeError("MCP internal API path contains invalid characters")
    try:
        parsed = urlsplit(path)
    except ValueError as exc:
        raise RuntimeError("MCP internal API path is invalid") from exc
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith(("/api/", "/internal/"))
    ):
        raise RuntimeError("MCP internal API path is outside the application boundary")
    if "%" in parsed.path:
        raise RuntimeError("MCP internal API path must not use percent encoding")
    if any(segment in {".", ".."} for segment in parsed.path.split("/")):
        raise RuntimeError("MCP internal API path contains traversal")


@asynccontextmanager
async def lifespan(_: FastMCP[Any]) -> AsyncIterator[McpRuntime]:
    async with _internal_api_client() as client:
        yield McpRuntime(api_client=client)


auth = None
token_verifier = None
if settings.mcp_auth_enabled:
    auth = AuthSettings(
        issuer_url=AnyHttpUrl(settings.mcp_auth_issuer_url),
        resource_server_url=AnyHttpUrl(settings.mcp_resource_server_url),
        required_scopes=[settings.mcp_required_scope],
    )
    token_verifier = build_token_verifier(settings)

mcp = FastMCP(
    PRODUCT_NAME,
    host=settings.mcp_host,
    port=settings.mcp_port,
    stateless_http=True,
    lifespan=lifespan,
    auth=auth,
    token_verifier=token_verifier,
)
# Pinned FastMCP does not forward a product-version constructor argument. Bind
# its existing low-level server once; the real initialize regression protects
# this SDK boundary without replacing handlers or creating another runtime.
mcp._mcp_server.version = PRODUCT_VERSION


async def api_request(ctx: McpContext, method: str, path: str, **kwargs: Any) -> Any:
    supplied_headers = kwargs.pop("headers", {})
    if not isinstance(supplied_headers, dict):
        raise RuntimeError("MCP API request headers must be a mapping")
    _validate_internal_api_path(path)
    if any(str(name).casefold() == NETWORK_FINGERPRINT_HEADER.casefold() for name in supplied_headers):
        raise RuntimeError("MCP API request cannot override the internal network context")

    override = _api_request_override.get()
    if override is None:
        access_token = await _revalidate_access_token(ctx)
        runtime = ctx.request_context.lifespan_context
        client = runtime.api_client
        token = access_token.token
        correlation_headers = _correlation_headers(ctx)
    else:
        client = override.client
        token = override.access_token
        correlation_headers = override.correlation_headers
    response = await client.request(
        method,
        path,
        headers={
            **supplied_headers,
            **correlation_headers,
            "Authorization": f"Bearer {token}",
        },
        **kwargs,
    )
    if response.status_code == 422:
        summary = _validation_error_summary(response)
        if summary:
            raise ValueError(f"Internal API rejected MCP tool arguments: {summary}")
    response.raise_for_status()
    return response.json()


async def _revalidate_access_token(ctx: McpContext) -> AccessToken:
    current = get_access_token()
    if current is None:
        raise RuntimeError("MCP request is missing an authenticated access token")
    request_context = getattr(ctx, "request_context", None)
    request = getattr(request_context, "request", None)
    if not isinstance(request, Request):
        if settings.app_env.lower() == "production":
            raise RuntimeError("MCP request authentication context is unavailable")
        return current
    authorization = request.headers.get("Authorization", "")
    scheme, _, raw_token = authorization.partition(" ")
    if scheme.casefold() not in {"bearer", "dpop"} or not raw_token:
        raise RuntimeError("MCP request is missing its authenticated source credential")
    if token_verifier is None:
        if settings.mcp_auth_enabled:
            raise RuntimeError("MCP token verifier is unavailable")
        return current
    refreshed = await token_verifier.verify_token(raw_token)
    if refreshed is None:
        raise RuntimeError("MCP source credential could not be revalidated")
    if refreshed.client_id != current.client_id:
        raise RuntimeError("MCP source credential identity changed during the request")
    return refreshed


def _validation_error_summary(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    details = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(details, str):
        summary = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", details)
        return " ".join(summary.split())[:500]
    if not isinstance(details, list):
        return ""
    summaries: list[str] = []
    for detail in details[:5]:
        if not isinstance(detail, dict):
            continue
        location = detail.get("loc")
        error_type = detail.get("type")
        message = detail.get("msg")
        if (
            not isinstance(location, list)
            or not all(isinstance(item, str | int) for item in location)
            or not isinstance(error_type, str)
            or not isinstance(message, str)
        ):
            continue
        path = ".".join(str(item) for item in location)
        summaries.append(f"{path} [{error_type}]: {message}")
    return "; ".join(summaries)[:500]


def _correlation_headers(ctx: McpContext) -> dict[str, str]:
    request = ctx.request_context.request
    if not isinstance(request, Request):
        if settings.app_env.lower() == "production":
            raise RuntimeError("MCP request network context is unavailable")
        return {}
    try:
        fingerprint = network_fingerprint(request, settings)
    except CorrelationSignalError as exc:
        raise RuntimeError(str(exc)) from exc
    return {NETWORK_FINGERPRINT_HEADER: fingerprint}


def _result_count(billing_class: str, result: dict[str, Any] | list[Any]) -> int:
    if isinstance(result, list):
        return len(result)
    if billing_class == "entity.dossier":
        count = 1 if isinstance(result.get("entity"), dict) else 0
        for key in DOSSIER_RECORD_COLLECTIONS:
            values = result.get(key)
            if not isinstance(values, list):
                raise RuntimeError(f"Entity dossier field '{key}' must be an array")
            count += len(values)
        return count
    for key in ("items", "chunks"):
        values = result.get(key)
        if isinstance(values, list):
            return len(values)
    return 1


def _canonical_commercial_datetime_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(arguments)
    for key in COMMERCIAL_DATETIME_ARGUMENTS:
        value = normalized.get(key)
        if not isinstance(value, str) or not value:
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is not None:
            normalized[key] = parsed.astimezone(UTC).isoformat()
    return normalized


def _canonical_repeated_filter(
    field: str,
    single_value: str,
    values: list[str] | None,
    *,
    max_length: int,
) -> list[str] | None:
    normalized: list[str] = []
    for raw_value in [single_value, *(values or [])]:
        value = raw_value.strip()
        if not value:
            continue
        if len(value) > max_length:
            raise ValueError(f"{field} values must not exceed {max_length} characters")
        if value not in normalized:
            normalized.append(value)
    if len(normalized) > 20:
        raise ValueError(f"{field} accepts at most 20 values")
    return normalized or None


def _verified_review_status(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized and normalized != "verified":
        raise ValueError("MCP entity tools only expose verified records")
    return "verified"


def _canonical_sort[SortField: str](
    tokens: list[str] | None,
    allowed_fields: tuple[SortField, ...],
    *,
    default_field: SortField,
    default_direction: SortDirection,
    legacy_field: str,
    legacy_direction: str,
) -> list[str]:
    clauses = resolve_sort_clauses(
        tokens,
        allowed_fields,
        default_field=default_field,
        default_direction=default_direction,
        legacy_field=cast(SortField, legacy_field) if legacy_field else None,
        legacy_direction=cast(SortDirection, legacy_direction) if legacy_direction else None,
    )
    return [clause.token for clause in clauses]


async def commercial_api_request(
    ctx: McpContext,
    *,
    billing_class: str,
    idempotency_key: str,
    max_billable_units: str,
    requested_result_limit: int,
    request_arguments: dict[str, Any],
    method: str,
    path: str,
    requested_compute_units: str = "0",
    **kwargs: Any,
) -> dict[str, Any]:
    request_arguments = _canonical_commercial_datetime_arguments(request_arguments)
    request_params = kwargs.get("params")
    if isinstance(request_params, dict):
        kwargs = {**kwargs, "params": _canonical_commercial_datetime_arguments(request_params)}
    started = time.perf_counter()
    cancellation_requested = asyncio.Event()
    access_token = await _revalidate_access_token(ctx)
    correlation_headers = _correlation_headers(ctx)

    async def execute() -> dict[str, Any]:
        with anyio.CancelScope(shield=True):
            async with _internal_api_client() as client:
                override_token = _api_request_override.set(
                    ApiRequestOverride(client, access_token.token, correlation_headers)
                )
                try:
                    return await _commercial_api_request(
                        ctx,
                        billing_class=billing_class,
                        idempotency_key=idempotency_key,
                        max_billable_units=max_billable_units,
                        requested_result_limit=requested_result_limit,
                        request_arguments=request_arguments,
                        method=method,
                        path=path,
                        requested_compute_units=requested_compute_units,
                        cancellation_requested=cancellation_requested,
                        **kwargs,
                    )
                finally:
                    _api_request_override.reset(override_token)
        raise RuntimeError("Shielded commercial operation exited without a terminal result")

    operation = asyncio.create_task(execute())
    try:
        response = await asyncio.shield(operation)
    except asyncio.CancelledError:
        cancellation_requested.set()
        _track_cancelled_commercial_operation(operation, billing_class, started)
        raise
    except httpx.HTTPStatusError as exc:
        operational_metrics().record_mcp_call(billing_class, "failed", time.perf_counter() - started)
        raise _safe_commercial_http_error(exc) from exc
    except BaseException:
        operational_metrics().record_mcp_call(billing_class, "failed", time.perf_counter() - started)
        raise
    usage = response.get("usage")
    outcome: McpOutcome = "replayed" if isinstance(usage, dict) and usage.get("replayed") is True else "settled"
    operational_metrics().record_mcp_call(billing_class, outcome, time.perf_counter() - started)
    return response


_cancelled_commercial_operations: set[asyncio.Task[dict[str, Any]]] = set()


def _track_cancelled_commercial_operation(
    operation: asyncio.Task[dict[str, Any]],
    billing_class: str,
    started: float,
) -> None:
    _cancelled_commercial_operations.add(operation)

    def completed(task: asyncio.Task[dict[str, Any]]) -> None:
        _cancelled_commercial_operations.discard(task)
        try:
            response = task.result()
        except asyncio.CancelledError:
            operational_metrics().record_mcp_call(billing_class, "failed", time.perf_counter() - started)
        except BaseException as exc:
            operational_metrics().record_mcp_call(billing_class, "failed", time.perf_counter() - started)
            logger.error("cancelled_commercial_operation_failed", error=type(exc).__name__)
        else:
            usage = response.get("usage")
            outcome: McpOutcome = "replayed" if isinstance(usage, dict) and usage.get("replayed") is True else "settled"
            operational_metrics().record_mcp_call(billing_class, outcome, time.perf_counter() - started)

    operation.add_done_callback(completed)


async def _commercial_api_request(
    ctx: McpContext,
    *,
    billing_class: str,
    idempotency_key: str,
    max_billable_units: str,
    requested_result_limit: int,
    request_arguments: dict[str, Any],
    method: str,
    path: str,
    requested_compute_units: str = "0",
    cancellation_requested: asyncio.Event | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    reservation = await _create_commercial_reservation(
        ctx,
        billing_class=billing_class,
        idempotency_key=idempotency_key,
        request_arguments=request_arguments,
        requested_result_limit=requested_result_limit,
        max_billable_units=max_billable_units,
        requested_compute_units=requested_compute_units,
    )
    settlement = reservation.get("settlement")
    if reservation.get("state") == "settled" and isinstance(settlement, dict):
        return {"data": settlement["result"], "usage": _usage_metadata(reservation, settlement)}
    if reservation.get("replayed"):
        raise RuntimeError(f"Commercial request is already {reservation.get('state', 'in progress')}")
    if reservation.get("state") != "reserved":
        raise RuntimeError("Commercial usage reservation was not granted")
    if cancellation_requested is not None and cancellation_requested.is_set():
        await api_request(
            ctx,
            "POST",
            f"/internal/v1/commercial/reservations/{reservation['reservation_id']}/release",
            json={"reason": "caller cancelled before domain execution"},
        )
        raise asyncio.CancelledError

    try:
        domain_headers = kwargs.pop("headers", {})
        if not isinstance(domain_headers, dict):
            raise RuntimeError("Commercial domain headers must be a mapping")
        result = await api_request(
            ctx,
            method,
            path,
            headers={**domain_headers, "X-Commercial-Reservation-ID": reservation["reservation_id"]},
            **kwargs,
        )
        if not isinstance(result, dict | list):
            raise RuntimeError("Domain API returned a non-JSON commercial result")
        if cancellation_requested is not None and cancellation_requested.is_set():
            raise asyncio.CancelledError
    except BaseException:
        try:
            await asyncio.shield(
                api_request(
                    ctx,
                    "POST",
                    f"/internal/v1/commercial/reservations/{reservation['reservation_id']}/release",
                    json={"reason": "domain execution did not complete"},
                )
            )
        except BaseException as release_error:
            logger.error(
                "commercial_reservation_release_failed",
                reservation_id=reservation.get("reservation_id"),
                error=type(release_error).__name__,
            )
        raise

    settled = cast(
        dict[str, Any],
        await api_request(
            ctx,
            "POST",
            f"/internal/v1/commercial/reservations/{reservation['reservation_id']}/settle",
            json={
                "result_count": _result_count(billing_class, result),
                "result": result,
                "metrics": {"tool": billing_class, "compute_units": requested_compute_units},
            },
        ),
    )
    settled_record = settled.get("settlement")
    if settled.get("state") != "settled" or not isinstance(settled_record, dict):
        raise RuntimeError("Commercial result did not produce a durable settlement")
    return {"data": settled_record["result"], "usage": _usage_metadata(settled, settled_record)}


async def _create_commercial_reservation(
    ctx: McpContext,
    *,
    billing_class: str,
    idempotency_key: str,
    request_arguments: dict[str, Any],
    requested_result_limit: int,
    max_billable_units: str,
    requested_compute_units: str,
) -> dict[str, Any]:
    task = asyncio.create_task(
        api_request(
            ctx,
            "POST",
            "/internal/v1/commercial/reservations",
            json={
                "billing_class": billing_class,
                "idempotency_key": idempotency_key,
                "request_arguments": request_arguments,
                "requested_result_limit": requested_result_limit,
                "max_billable_units": max_billable_units,
                "requested_compute_units": requested_compute_units,
            },
        )
    )
    try:
        return cast(dict[str, Any], await asyncio.shield(task))
    except asyncio.CancelledError:
        try:
            reservation = await asyncio.shield(task)
            if isinstance(reservation, dict) and reservation.get("state") == "reserved":
                await asyncio.shield(
                    api_request(
                        ctx,
                        "POST",
                        f"/internal/v1/commercial/reservations/{reservation['reservation_id']}/release",
                        json={"reason": "caller cancelled while reservation was being created"},
                    )
                )
        except BaseException as release_error:
            logger.error(
                "commercial_reservation_cancel_cleanup_failed",
                error=type(release_error).__name__,
            )
        raise


def _usage_metadata(reservation: dict[str, Any], settlement: dict[str, Any]) -> dict[str, Any]:
    return {
        "reservation_id": reservation["reservation_id"],
        "settlement_id": settlement["settlement_id"],
        "usage_event_id": settlement["usage_event_id"],
        "billing_class": reservation["billing_class"],
        "charged_units": settlement["charged_units"],
        "result_count": settlement["result_count"],
        "unique_record_count": settlement["unique_record_count"],
        "new_unique_record_count": settlement["new_unique_record_count"],
        "response_bytes": settlement["response_bytes"],
        "compute_units": settlement.get("price_breakdown", {}).get("compute_units", "0.00000000"),
        "page_depth": reservation["page_depth"],
        "replayed": reservation["replayed"],
    }


@mcp.tool()
async def get_commercial_access(ctx: McpContext) -> dict[str, Any]:
    """Read the authenticated Agent client's subscription, balance and enabled data entitlements."""
    return cast(dict[str, Any], await api_request(ctx, "GET", "/internal/v1/commercial/access"))


@mcp.tool()
async def estimate_usage(
    ctx: McpContext,
    billing_class: str,
    requested_result_limit: int,
    requested_compute_units: str = "0",
) -> dict[str, Any]:
    """Quote the active rate card for a bounded call without reading data or reserving credits."""
    return cast(
        dict[str, Any],
        await api_request(
            ctx,
            "POST",
            "/internal/v1/commercial/estimate",
            json={
                "billing_class": billing_class,
                "requested_result_limit": requested_result_limit,
                "requested_compute_units": requested_compute_units,
            },
        ),
    )


@mcp.tool()
async def get_usage_summary(ctx: McpContext) -> dict[str, Any]:
    """Read the authenticated client's current billing-period usage and latest statement reference."""
    return cast(dict[str, Any], await api_request(ctx, "GET", "/internal/v1/commercial/usage-summary"))


@mcp.tool()
async def search_entities(
    ctx: McpContext,
    query: str,
    idempotency_key: str,
    max_billable_units: str,
    entity_type: str = "",
    limit: int = 20,
    cursor: str = "",
    review_status: str = "",
    sort_by: str = "",
    sort_direction: str = "",
    entity_types: list[str] | None = None,
    sort: list[str] | None = None,
) -> dict[str, Any]:
    """Search entities with relevance or stable field ordering and opaque cursor pagination."""
    bounded_limit = min(max(limit, 1), 100)
    params: dict[str, Any] = {"q": query, "limit": bounded_limit}
    selected_types = sorted(set((entity_types or []) + ([entity_type] if entity_type else [])))
    if len(selected_types) == 1:
        params["entity_type"] = selected_types[0]
    elif selected_types:
        params["entity_types"] = selected_types
    params["review_status"] = _verified_review_status(review_status)
    if cursor:
        params["cursor"] = cursor
    params["sort"] = _canonical_sort(
        sort,
        ENTITY_SORT_FIELDS,
        default_field="relevance",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    domain_params = {**params, "billing_class": "entity.search"}
    return await commercial_api_request(
        ctx,
        billing_class="entity.search",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments=params,
        method="GET",
        path="/internal/v1/domain/entities",
        params=domain_params,
    )


@mcp.tool()
async def resolve_entity(
    ctx: McpContext,
    query: str,
    idempotency_key: str,
    max_billable_units: str,
    entity_type: str = "",
    limit: int = 10,
    cursor: str = "",
    review_status: str = "",
    entity_types: list[str] | None = None,
) -> dict[str, Any]:
    """Resolve a term or identifier to normalized entity candidates before domain queries."""
    bounded_limit = min(max(limit, 1), 25)
    params: dict[str, Any] = {"q": query, "limit": bounded_limit}
    selected_types = sorted(set((entity_types or []) + ([entity_type] if entity_type else [])))
    if len(selected_types) == 1:
        params["entity_type"] = selected_types[0]
    elif selected_types:
        params["entity_types"] = selected_types
    params["review_status"] = _verified_review_status(review_status)
    if cursor:
        params["cursor"] = cursor
    domain_params = {**params, "billing_class": "entity.resolve"}
    return await commercial_api_request(
        ctx,
        billing_class="entity.resolve",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments=params,
        method="GET",
        path="/internal/v1/domain/entities",
        params=domain_params,
    )


@mcp.tool()
async def get_entity(
    ctx: McpContext,
    entity_id: str,
    idempotency_key: str,
    max_billable_units: str,
) -> dict[str, Any]:
    """Read one normalized pharmaceutical entity by its stable identifier."""
    return await commercial_api_request(
        ctx,
        billing_class="entity.read",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=1,
        request_arguments={"entity_id": entity_id},
        method="GET",
        path=f"/api/v1/entities/{entity_id}",
    )


@mcp.tool()
async def get_entity_dossier(
    ctx: McpContext,
    entity_id: str,
    idempotency_key: str,
    max_billable_units: str,
    limit: int = 50,
) -> dict[str, Any]:
    """Read a bounded cross-domain dossier with coverage and explicit data gaps for one entity."""
    bounded_limit = min(max(limit, 1), 100)
    result_limit = dossier_result_capacity(bounded_limit)
    arguments = {"entity_id": entity_id, "domain_limit": bounded_limit, "limit": result_limit}
    return await commercial_api_request(
        ctx,
        billing_class="entity.dossier",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=result_limit,
        request_arguments=arguments,
        method="GET",
        path=f"/internal/v1/domain/entities/{entity_id}/dossier",
        params={"limit": bounded_limit},
    )


@mcp.tool()
async def search_evidence(
    ctx: McpContext,
    query: str,
    idempotency_key: str,
    max_billable_units: str,
    dataset_keys: list[str] | None = None,
    limit: int = 10,
    cursor: str = "",
) -> dict[str, Any]:
    """Retrieve source-backed evidence using tenant-authorized logical dataset keys."""
    bounded_limit = min(max(limit, 1), 50)
    payload: dict[str, Any] = {
        "query": query,
        "dataset_keys": dataset_keys or [],
        "entity_types": [],
        "limit": bounded_limit,
    }
    arguments = dict(payload)
    if cursor:
        arguments["cursor"] = cursor
    return await commercial_api_request(
        ctx,
        billing_class="evidence.search",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments=arguments,
        method="POST",
        path="/internal/v1/domain/evidence/search",
        json=payload,
        params={"cursor": cursor} if cursor else {},
    )


@mcp.tool()
async def get_record_provenance(
    ctx: McpContext,
    resource_type: Literal[
        "activity_measurement",
        "assay",
        "clinical_trial",
        "compound_structure",
        "deal",
        "development_program",
        "epidemiology_observation",
        "evidence_claim",
        "patent_family",
        "regulatory_event",
        "target_profile",
    ],
    resource_id: str,
    idempotency_key: str,
    max_billable_units: str,
    limit: int = 20,
) -> dict[str, Any]:
    """Trace one authoritative record to licensed source versions, locations and verified quotations."""
    try:
        normalized_resource_id = str(uuid.UUID(resource_id))
    except ValueError as exc:
        raise ValueError("resource_id must be a UUID") from exc
    bounded_limit = min(max(limit, 1), 100)
    arguments = {
        "resource_type": resource_type,
        "resource_id": normalized_resource_id,
        "limit": bounded_limit,
    }
    return await commercial_api_request(
        ctx,
        billing_class="provenance.read",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments=arguments,
        method="GET",
        path=f"/internal/v1/domain/provenance/{resource_type}/{normalized_resource_id}",
        params={"limit": bounded_limit},
    )


@mcp.tool()
async def get_target_profile(
    ctx: McpContext,
    target_entity_id: str,
    idempotency_key: str,
    max_billable_units: str,
) -> dict[str, Any]:
    """Get normalized target biology, identifiers and current data coverage."""
    return await commercial_api_request(
        ctx,
        billing_class="target.profile",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=1,
        request_arguments={"target_entity_id": target_entity_id},
        method="GET",
        path=f"/api/v1/targets/{target_entity_id}/profile",
    )


@mcp.tool()
async def get_target_evidence(
    ctx: McpContext,
    target_entity_id: str,
    idempotency_key: str,
    max_billable_units: str,
    evidence_type: str = "",
    direction: str = "",
    disease_entity_id: str = "",
    limit: int = 100,
    cursor: str = "",
) -> dict[str, Any]:
    """Get governed genetic, expression, functional, translational, biomarker and safety evidence for a target."""
    bounded_limit = min(max(limit, 1), 500)
    params: dict[str, Any] = {"limit": bounded_limit}
    for name, value in (
        ("evidence_type", evidence_type),
        ("direction", direction),
        ("disease_entity_id", disease_entity_id),
        ("cursor", cursor),
    ):
        if value:
            params[name] = value
    return await commercial_api_request(
        ctx,
        billing_class="target.evidence.search",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments={"target_entity_id": target_entity_id, **params},
        method="GET",
        path=f"/internal/v1/domain/targets/{target_entity_id}/evidence",
        params=params,
    )


@mcp.tool()
async def get_bioactivity_landscape(
    ctx: McpContext,
    target_entity_id: str,
    idempotency_key: str,
    max_billable_units: str,
    standard_type: str = "",
    limit: int = 100,
    cursor: str = "",
) -> dict[str, Any]:
    """Get assay-linked, normalized activity measurements for a target."""
    bounded_limit = min(max(limit, 1), 500)
    params: dict[str, Any] = {"limit": bounded_limit}
    if standard_type:
        params["standard_type"] = standard_type
    if cursor:
        params["cursor"] = cursor
    return await commercial_api_request(
        ctx,
        billing_class="bioactivity.search",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments={"target_entity_id": target_entity_id, **params},
        method="GET",
        path=f"/internal/v1/domain/targets/{target_entity_id}/bioactivities",
        params=params,
    )


@mcp.tool()
async def compare_target_sar(
    ctx: McpContext,
    target_entity_id: str,
    idempotency_key: str,
    max_billable_units: str,
    standard_type: str = "",
    assay_type: str = "",
    assay_format: str = "",
    organism: str = "",
    cell_line: str = "",
    limit: int = 100,
    cursor: str = "",
) -> dict[str, Any]:
    """Compare normalized target potency only within explicitly compatible assay contexts."""
    bounded_limit = min(max(limit, 1), 500)
    params: dict[str, Any] = {"limit": bounded_limit}
    for key, value in (
        ("standard_type", standard_type),
        ("assay_type", assay_type),
        ("assay_format", assay_format),
        ("organism", organism),
        ("cell_line", cell_line),
    ):
        if value:
            params[key] = value
    if cursor:
        params["cursor"] = cursor
    return await commercial_api_request(
        ctx,
        billing_class="sar.compare",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments={"target_entity_id": target_entity_id, **params},
        method="GET",
        path=f"/internal/v1/domain/targets/{target_entity_id}/sar-comparison",
        params=params,
    )


@mcp.tool()
async def get_competitive_pipeline(
    ctx: McpContext,
    target_entity_id: str,
    idempotency_key: str,
    max_billable_units: str,
    limit: int = 100,
    cursor: str = "",
    drug_entity_id: str = "",
    disease_entity_id: str = "",
    organization_entity_id: str = "",
    program_status: Literal["", "active", "inactive", "unknown"] = "",
    organization_role: Literal["", "originator", "collaborator", "licensee", "licensor", "manufacturer", "other"] = "",
    organization_type: str = "",
    organization_country_region: str = "",
    modality: str = "",
    global_phase: str = "",
    china_phase: str = "",
    global_phase_started_from: str = "",
    global_phase_started_to: str = "",
    china_phase_started_from: str = "",
    china_phase_started_to: str = "",
    development_rights_region: str = "",
    commercialization_rights_region: str = "",
    program_tag: str = "",
    milestone_type: str = "",
    milestone_from: str = "",
    milestone_to: str = "",
    sort_by: Literal[
        "",
        "status_date",
        "drug_name",
        "target_name",
        "disease_name",
        "organization_name",
        "modality",
        "mechanism_of_action",
        "phase",
        "status_detail",
        "geography",
        "global_phase",
        "china_phase",
        "global_phase_started_at",
        "china_phase_started_at",
    ] = "",
    sort_direction: Literal["", "asc", "desc"] = "",
    has_clinical_results: bool | None = None,
    clinical_result_evaluation: str = "",
    has_deal: bool | None = None,
    deal_currency: str = "",
    deal_total_potential_amount_min: float | None = None,
    deal_total_potential_amount_max: float | None = None,
    modalities: list[str] | None = None,
    program_tags: list[str] | None = None,
    innovation_types: list[str] | None = None,
    therapeutic_areas: list[str] | None = None,
    drug_categories: list[str] | None = None,
    sort: list[str] | None = None,
) -> dict[str, Any]:
    """Get target programs with development, clinical-result, and transaction signals."""
    bounded_limit = min(max(limit, 1), 500)
    selected_modalities = _canonical_repeated_filter("modalities", modality, modalities, max_length=120)
    selected_program_tags = _canonical_repeated_filter("program_tags", program_tag, program_tags, max_length=240)
    selected_innovation_types = _canonical_repeated_filter("innovation_types", "", innovation_types, max_length=120)
    selected_therapeutic_areas = _canonical_repeated_filter("therapeutic_areas", "", therapeutic_areas, max_length=120)
    selected_drug_categories = _canonical_repeated_filter("drug_categories", "", drug_categories, max_length=120)
    params: dict[str, Any] = {"limit": bounded_limit}
    for name, value in (
        ("cursor", cursor),
        ("drug_entity_id", drug_entity_id),
        ("disease_entity_id", disease_entity_id),
        ("organization_entity_id", organization_entity_id),
        ("program_status", program_status),
        ("organization_role", organization_role),
        ("organization_type", organization_type),
        ("organization_country_region", organization_country_region),
        ("modality", selected_modalities),
        ("innovation_type", selected_innovation_types),
        ("therapeutic_area", selected_therapeutic_areas),
        ("drug_category", selected_drug_categories),
        ("global_phase", global_phase),
        ("china_phase", china_phase),
        ("global_phase_started_from", global_phase_started_from),
        ("global_phase_started_to", global_phase_started_to),
        ("china_phase_started_from", china_phase_started_from),
        ("china_phase_started_to", china_phase_started_to),
        ("development_rights_region", development_rights_region),
        ("commercialization_rights_region", commercialization_rights_region),
        ("program_tag", selected_program_tags),
        ("milestone_type", milestone_type),
        ("milestone_from", milestone_from),
        ("milestone_to", milestone_to),
        ("clinical_result_evaluation", clinical_result_evaluation),
        ("deal_currency", deal_currency),
    ):
        if value:
            params[name] = value
    params["sort"] = _canonical_sort(
        sort,
        PIPELINE_SORT_FIELDS,
        default_field="status_date",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    for typed_name, typed_value in (
        ("has_clinical_results", has_clinical_results),
        ("has_deal", has_deal),
        ("deal_total_potential_amount_min", deal_total_potential_amount_min),
        ("deal_total_potential_amount_max", deal_total_potential_amount_max),
    ):
        if typed_value is not None:
            params[typed_name] = typed_value
    return await commercial_api_request(
        ctx,
        billing_class="pipeline.search",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments={"target_entity_id": target_entity_id, **params},
        method="GET",
        path=f"/internal/v1/domain/targets/{target_entity_id}/competitive-programs",
        params=params,
    )


@mcp.tool()
async def search_structures(
    ctx: McpContext,
    idempotency_key: str,
    max_billable_units: str,
    entity_id: str = "",
    inchi_key: str = "",
    limit: int = 50,
    cursor: str = "",
) -> dict[str, Any]:
    """Read normalized chemical structures by compound entity or exact InChIKey."""
    bounded_limit = min(max(limit, 1), 100)
    params: dict[str, Any] = {"limit": bounded_limit}
    if entity_id:
        params["entity_id"] = entity_id
    if inchi_key:
        params["inchi_key"] = inchi_key
    if cursor:
        params["cursor"] = cursor
    return await commercial_api_request(
        ctx,
        billing_class="structure.search",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments=params,
        method="GET",
        path="/internal/v1/domain/structures",
        params=params,
    )


@mcp.tool()
async def search_chemical_structures(
    ctx: McpContext,
    mode: Literal["exact", "substructure", "similarity"],
    query: str,
    idempotency_key: str,
    max_billable_units: str,
    threshold: float = 0.5,
    limit: int = 20,
    cursor: str = "",
) -> dict[str, Any]:
    """Search tenant chemical structures by exact SMILES, SMARTS substructure, or SMILES similarity."""
    if not query.strip():
        raise ValueError("Chemical structure query is required")
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("Similarity threshold must be between 0 and 1")
    result_cap = 20 if mode == "exact" else 50
    bounded_limit = min(max(limit, 1), result_cap)
    request_arguments: dict[str, Any] = {
        "mode": mode,
        "query": query,
        "limit": bounded_limit,
    }
    if mode == "similarity":
        request_arguments["threshold"] = threshold
    payload = dict(request_arguments)
    if cursor:
        request_arguments["cursor"] = cursor
    return await commercial_api_request(
        ctx,
        billing_class=f"structure.{mode}",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        requested_compute_units="1",
        request_arguments=request_arguments,
        method="POST",
        path="/internal/v1/domain/chemistry/search",
        params={"cursor": cursor} if cursor else {},
        json=payload,
    )


@mcp.tool()
async def get_clinical_trials(
    ctx: McpContext,
    idempotency_key: str,
    max_billable_units: str,
    entity_id: str = "",
    query: str = "",
    limit: int = 100,
    cursor: str = "",
    registry: str = "",
    status: str = "",
    phase: str = "",
    study_type: str = "",
    has_results: bool | None = None,
    results_posted_from: str = "",
    results_posted_to: str = "",
    result_evaluation: str = "",
    investigational_drug: str = "",
    combination_drug: str = "",
    investigational_target: str = "",
    combination_target: str = "",
    role_entity_id: str = "",
    role_entity_role: str = "",
    has_key_result: bool | None = None,
    publication_id: str = "",
    conference: str = "",
    disclosed_from: str = "",
    disclosed_to: str = "",
    sort_by: Literal[
        "",
        "last_update_posted",
        "registry_id",
        "has_results",
        "result_evaluation",
        "overall_status",
        "enrollment",
        "study_type",
        "acronym",
        "initiation_type",
    ] = "",
    sort_direction: Literal["", "asc", "desc"] = "",
    acronym: str = "",
    initiation_type: Literal["iit", "ist", ""] = "",
    therapy_line: Literal[
        "first_line",
        "second_line",
        "third_or_later",
        "prevention",
        "treatment_naive",
        "add_on",
        "adjuvant",
        "neoadjuvant",
        "maintenance",
        "consolidation",
        "induction",
        "conversion",
        "",
    ] = "",
    role_entity_ids: list[str] | None = None,
    investigational_drug_entity_ids: list[str] | None = None,
    combination_drug_entity_ids: list[str] | None = None,
    investigational_target_entity_ids: list[str] | None = None,
    combination_target_entity_ids: list[str] | None = None,
    linked_drug_modalities: list[str] | None = None,
    linked_drug_innovation_types: list[str] | None = None,
    linked_drug_categories: list[str] | None = None,
    linked_drug_program_tags: list[str] | None = None,
    linked_drug_global_phase: str = "",
    linked_drug_organization_country_region: str = "",
    sort: list[str] | None = None,
) -> dict[str, Any]:
    """Read governed trials with role-specific assets/targets and versioned result disclosures."""
    bounded_limit = min(max(limit, 1), 500)
    selected_linked_drug_modalities = _canonical_repeated_filter(
        "linked_drug_modalities", "", linked_drug_modalities, max_length=120
    )
    selected_linked_drug_innovation_types = _canonical_repeated_filter(
        "linked_drug_innovation_types", "", linked_drug_innovation_types, max_length=120
    )
    selected_linked_drug_categories = _canonical_repeated_filter(
        "linked_drug_categories", "", linked_drug_categories, max_length=120
    )
    selected_linked_drug_program_tags = _canonical_repeated_filter(
        "linked_drug_program_tags", "", linked_drug_program_tags, max_length=240
    )
    params: dict[str, Any] = {
        "limit": bounded_limit,
        "sort": _canonical_sort(
            sort,
            CLINICAL_TRIAL_SORT_FIELDS,
            default_field="last_update_posted",
            default_direction="desc",
            legacy_field=sort_by,
            legacy_direction=sort_direction,
        ),
    }
    if entity_id:
        params["entity_id"] = entity_id
    if query:
        params["q"] = query
    if registry:
        params["registry"] = registry
    if status:
        params["status"] = status
    if phase:
        params["phase"] = phase
    if study_type:
        params["study_type"] = study_type
    if has_results is not None:
        params["has_results"] = has_results
    if results_posted_from:
        params["results_posted_from"] = results_posted_from
    if results_posted_to:
        params["results_posted_to"] = results_posted_to
    if result_evaluation:
        params["result_evaluation"] = result_evaluation
    for key, value in {
        "investigational_drug": investigational_drug,
        "combination_drug": combination_drug,
        "investigational_target": investigational_target,
        "combination_target": combination_target,
        "role_entity_id": role_entity_id,
        "role_entity_role": role_entity_role,
        "has_key_result": has_key_result,
        "publication_id": publication_id,
        "conference": conference,
        "disclosed_from": disclosed_from,
        "disclosed_to": disclosed_to,
        "acronym": acronym,
        "initiation_type": initiation_type,
        "therapy_line": therapy_line,
        "role_entity_ids": sorted(set(role_entity_ids or [])) or None,
        "investigational_drug_entity_ids": sorted(set(investigational_drug_entity_ids or [])) or None,
        "combination_drug_entity_ids": sorted(set(combination_drug_entity_ids or [])) or None,
        "investigational_target_entity_ids": sorted(set(investigational_target_entity_ids or [])) or None,
        "combination_target_entity_ids": sorted(set(combination_target_entity_ids or [])) or None,
        "linked_drug_modality": selected_linked_drug_modalities,
        "linked_drug_innovation_type": selected_linked_drug_innovation_types,
        "linked_drug_category": selected_linked_drug_categories,
        "linked_drug_program_tag": selected_linked_drug_program_tags,
        "linked_drug_global_phase": linked_drug_global_phase,
        "linked_drug_organization_country_region": linked_drug_organization_country_region,
    }.items():
        if value is not None and value != "":
            params[key] = value
    if cursor:
        params["cursor"] = cursor
    return await commercial_api_request(
        ctx,
        billing_class="trial.search",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments=params,
        method="GET",
        path="/internal/v1/domain/clinical-trials",
        params=params,
    )


@mcp.tool()
async def get_clinical_trial(
    ctx: McpContext,
    trial_id: str,
    idempotency_key: str,
    max_billable_units: str,
) -> dict[str, Any]:
    """Read one governed trial with design, arms, eligibility, endpoints, results, history and linked entities."""
    return await commercial_api_request(
        ctx,
        billing_class="trial.read",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=1,
        request_arguments={"trial_id": trial_id},
        method="GET",
        path=f"/api/v1/trials/{trial_id}",
    )


@mcp.tool()
async def get_patent_landscape(
    ctx: McpContext,
    idempotency_key: str,
    max_billable_units: str,
    entity_id: str = "",
    query: str = "",
    limit: int = 100,
    cursor: str = "",
    applicant: str = "",
    legal_status: str = "",
    sort_by: Literal["", "priority_date", "family_identifier", "legal_status", "expiration_date"] = "",
    sort_direction: Literal["", "asc", "desc"] = "",
    sort: list[str] | None = None,
) -> dict[str, Any]:
    """Search patent families, priority, publications, legal events, claim summaries and entity links."""
    bounded_limit = min(max(limit, 1), 500)
    params: dict[str, Any] = {
        "limit": bounded_limit,
        "sort": _canonical_sort(
            sort,
            PATENT_SORT_FIELDS,
            default_field="priority_date",
            default_direction="desc",
            legacy_field=sort_by,
            legacy_direction=sort_direction,
        ),
    }
    if entity_id:
        params["entity_id"] = entity_id
    if query:
        params["q"] = query
    if applicant:
        params["applicant"] = applicant
    if legal_status:
        params["legal_status"] = legal_status
    if cursor:
        params["cursor"] = cursor
    return await commercial_api_request(
        ctx,
        billing_class="patent.search",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments=params,
        method="GET",
        path="/internal/v1/domain/patents",
        params=params,
    )


@mcp.tool()
async def get_deals(
    ctx: McpContext,
    idempotency_key: str,
    max_billable_units: str,
    entity_id: str = "",
    limit: int = 100,
    cursor: str = "",
    query: str = "",
    deal_type: str = "",
    status: str = "",
    direction: str = "",
    direction_reference_jurisdiction: str = "",
    territory: str = "",
    asset_entity_id: str = "",
    target_entity_id: str = "",
    disease_entity_id: str = "",
    party: str = "",
    party_entity_id: str = "",
    party_role: str = "",
    party_country_region: str = "",
    party_organization_type: str = "",
    development_phase_at_transaction: str = "",
    current_development_phase: str = "",
    right_type: str = "",
    rights_territory: str = "",
    currency: str = "",
    announced_from: str = "",
    announced_to: str = "",
    terminated_from: str = "",
    terminated_to: str = "",
    source_updated_from: str = "",
    source_updated_to: str = "",
    upfront_amount_min: float | None = None,
    upfront_amount_max: float | None = None,
    total_potential_amount_min: float | None = None,
    total_potential_amount_max: float | None = None,
    sort_by: Literal[
        "",
        "announced_at",
        "name",
        "deal_type",
        "status",
        "direction",
        "territory",
        "upfront_amount",
        "total_potential_amount",
    ] = "",
    sort_direction: Literal["", "asc", "desc"] = "",
    asset_modality: str = "",
    asset_program_tag: str = "",
    asset_modalities: list[str] | None = None,
    asset_program_tags: list[str] | None = None,
    sort: list[str] | None = None,
) -> dict[str, Any]:
    """Search governed deals by asset attributes, parties, direction, stage, rights, time, and amounts."""
    bounded_limit = min(max(limit, 1), 500)
    params: dict[str, Any] = {
        "limit": bounded_limit,
        "sort": _canonical_sort(
            sort,
            DEAL_SORT_FIELDS,
            default_field="announced_at",
            default_direction="desc",
            legacy_field=sort_by,
            legacy_direction=sort_direction,
        ),
    }
    selected_asset_modalities = _canonical_repeated_filter(
        "asset_modalities",
        asset_modality,
        asset_modalities,
        max_length=120,
    )
    selected_asset_program_tags = _canonical_repeated_filter(
        "asset_program_tags",
        asset_program_tag,
        asset_program_tags,
        max_length=240,
    )
    if entity_id:
        params["entity_id"] = entity_id
    if query:
        params["q"] = query
    if deal_type:
        params["deal_type"] = deal_type
    for key, value in {
        "status": status,
        "direction": direction,
        "direction_reference_jurisdiction": direction_reference_jurisdiction,
        "territory": territory,
        "asset_entity_id": asset_entity_id,
        "target_entity_id": target_entity_id,
        "disease_entity_id": disease_entity_id,
        "asset_modality": selected_asset_modalities,
        "asset_program_tag": selected_asset_program_tags,
        "party": party,
        "party_entity_id": party_entity_id,
        "party_role": party_role,
        "party_country_region": party_country_region,
        "party_organization_type": party_organization_type,
        "development_phase_at_transaction": development_phase_at_transaction,
        "current_development_phase": current_development_phase,
        "right_type": right_type,
        "rights_territory": rights_territory,
        "currency": currency,
        "announced_from": announced_from,
        "announced_to": announced_to,
        "terminated_from": terminated_from,
        "terminated_to": terminated_to,
        "source_updated_from": source_updated_from,
        "source_updated_to": source_updated_to,
        "upfront_amount_min": upfront_amount_min,
        "upfront_amount_max": upfront_amount_max,
        "total_potential_amount_min": total_potential_amount_min,
        "total_potential_amount_max": total_potential_amount_max,
    }.items():
        if value != "" and value is not None:
            params[key] = value
    if cursor:
        params["cursor"] = cursor
    return await commercial_api_request(
        ctx,
        billing_class="deal.search",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments=params,
        method="GET",
        path="/internal/v1/domain/deals",
        params=params,
    )


@mcp.tool()
async def get_company_timeline(
    ctx: McpContext,
    company_entity_id: str,
    idempotency_key: str,
    max_billable_units: str,
    limit: int = 100,
    cursor: str = "",
) -> dict[str, Any]:
    """Read one company's dated pipeline status and disclosed transaction events in a unified timeline."""
    bounded_limit = min(max(limit, 1), 500)
    params: dict[str, Any] = {"limit": bounded_limit}
    if cursor:
        params["cursor"] = cursor
    return await commercial_api_request(
        ctx,
        billing_class="company.timeline",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments={"company_entity_id": company_entity_id, **params},
        method="GET",
        path=f"/internal/v1/domain/companies/{company_entity_id}/timeline",
        params=params,
    )


@mcp.tool()
async def get_regulatory_events(
    ctx: McpContext,
    idempotency_key: str,
    max_billable_units: str,
    entity_id: str = "",
    query: str = "",
    agency: str = "",
    limit: int = 100,
    cursor: str = "",
    jurisdiction: str = "",
    event_type: str = "",
    status: str = "",
    designation_type: str = "",
    label_change_type: str = "",
    has_boxed_warning: bool | None = None,
    safety_signal_type: str = "",
    safety_severity: str = "",
    safety_status: str = "",
    decision_from: str = "",
    decision_to: str = "",
    source_updated_from: str = "",
    source_updated_to: str = "",
    sort_by: Literal[
        "",
        "decision_date",
        "title",
        "agency",
        "jurisdiction",
        "event_type",
        "status",
        "subject",
        "source_updated_at",
    ] = "",
    sort_direction: Literal["", "asc", "desc"] = "",
    sort: list[str] | None = None,
) -> dict[str, Any]:
    """Read normalized regulatory timelines, labels, designations and safety signals with source identity."""
    bounded_limit = min(max(limit, 1), 500)
    params: dict[str, Any] = {
        "limit": bounded_limit,
        "sort": _canonical_sort(
            sort,
            REGULATORY_SORT_FIELDS,
            default_field="decision_date",
            default_direction="desc",
            legacy_field=sort_by,
            legacy_direction=sort_direction,
        ),
    }
    if entity_id:
        params["entity_id"] = entity_id
    if query:
        params["q"] = query
    if agency:
        params["agency"] = agency
    if jurisdiction:
        params["jurisdiction"] = jurisdiction
    if event_type:
        params["event_type"] = event_type
    if status:
        params["status"] = status
    for name, value in (
        ("designation_type", designation_type),
        ("label_change_type", label_change_type),
        ("safety_signal_type", safety_signal_type),
        ("safety_severity", safety_severity),
        ("safety_status", safety_status),
        ("decision_from", decision_from),
        ("decision_to", decision_to),
        ("source_updated_from", source_updated_from),
        ("source_updated_to", source_updated_to),
    ):
        if value:
            params[name] = value
    if has_boxed_warning is not None:
        params["has_boxed_warning"] = has_boxed_warning
    if cursor:
        params["cursor"] = cursor
    return await commercial_api_request(
        ctx,
        billing_class="regulatory.search",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments=params,
        method="GET",
        path="/internal/v1/domain/regulatory-events",
        params=params,
    )


@mcp.tool()
async def get_epidemiology_observations(
    ctx: McpContext,
    idempotency_key: str,
    max_billable_units: str,
    disease_entity_id: str = "",
    query: str = "",
    measure: str = "",
    geography: str = "",
    unit: str = "",
    population_scope: str = "",
    age_group: str = "",
    sex: str = "",
    period_start_from: str = "",
    period_end_to: str = "",
    limit: int = 100,
    cursor: str = "",
    patient_population_id: str = "",
    sort_by: Literal[
        "",
        "period_end",
        "period_start",
        "disease",
        "measure",
        "value",
        "geography",
        "unit",
        "publisher",
        "sample_size",
    ] = "",
    sort_direction: Literal["", "asc", "desc"] = "",
    sort: list[str] | None = None,
) -> dict[str, Any]:
    """Read source-bearing disease burden estimates with population, geography and time dimensions."""
    bounded_limit = min(max(limit, 1), 500)
    params: dict[str, Any] = {
        "limit": bounded_limit,
        "sort": _canonical_sort(
            sort,
            EPIDEMIOLOGY_SORT_FIELDS,
            default_field="period_end",
            default_direction="desc",
            legacy_field=sort_by,
            legacy_direction=sort_direction,
        ),
    }
    for name, value in (
        ("disease_entity_id", disease_entity_id),
        ("q", query),
        ("measure", measure),
        ("geography", geography),
        ("unit", unit),
        ("population_scope", population_scope),
        ("patient_population_id", patient_population_id),
        ("age_group", age_group),
        ("sex", sex),
        ("period_start_from", period_start_from),
        ("period_end_to", period_end_to),
        ("cursor", cursor),
    ):
        if value:
            params[name] = value
    return await commercial_api_request(
        ctx,
        billing_class="epidemiology.search",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments=params,
        method="GET",
        path="/internal/v1/domain/epidemiology-observations",
        params=params,
    )


@mcp.tool()
async def get_news_events(
    ctx: McpContext,
    idempotency_key: str,
    max_billable_units: str,
    entity_id: str = "",
    query: str = "",
    event_type: str = "",
    publisher: str = "",
    language: str = "",
    venue: str = "",
    published_from: str = "",
    published_to: str = "",
    limit: int = 100,
    cursor: str = "",
    sort_by: Literal["", "published_at", "title", "event_type", "publisher", "venue"] = "",
    sort_direction: Literal["", "asc", "desc"] = "",
    sort: list[str] | None = None,
) -> dict[str, Any]:
    """Read governed news, press releases and announcements with normalized entity links and source identity."""
    bounded_limit = min(max(limit, 1), 500)
    params: dict[str, Any] = {
        "limit": bounded_limit,
        "sort": _canonical_sort(
            sort,
            NEWS_SORT_FIELDS,
            default_field="published_at",
            default_direction="desc",
            legacy_field=sort_by,
            legacy_direction=sort_direction,
        ),
    }
    for name, value in (
        ("entity_id", entity_id),
        ("q", query),
        ("event_type", event_type),
        ("publisher", publisher),
        ("language", language),
        ("venue", venue),
        ("published_from", published_from),
        ("published_to", published_to),
        ("cursor", cursor),
    ):
        if value:
            params[name] = value
    return await commercial_api_request(
        ctx,
        billing_class="news.search",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments=params,
        method="GET",
        path="/internal/v1/domain/news-events",
        params=params,
    )


@mcp.tool()
async def search_knowledge_pages(
    ctx: McpContext,
    idempotency_key: str,
    max_billable_units: str,
    query: str = "",
    page_type: str = "",
    limit: int = 50,
    cursor: str = "",
) -> dict[str, Any]:
    """Search governed, versioned knowledge pages compiled from published evidence."""
    bounded_limit = min(max(limit, 1), 100)
    params: dict[str, Any] = {"limit": bounded_limit}
    if query:
        params["q"] = query
    if page_type:
        params["page_type"] = page_type
    if cursor:
        params["cursor"] = cursor
    return await commercial_api_request(
        ctx,
        billing_class="knowledge.search",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=bounded_limit,
        request_arguments=params,
        method="GET",
        path="/internal/v1/domain/knowledge/pages",
        params=params,
    )


@mcp.tool()
async def get_knowledge_page(
    ctx: McpContext,
    page_id: str,
    idempotency_key: str,
    max_billable_units: str,
) -> dict[str, Any]:
    """Read one governed page with structured facts, source citations, links and content hash."""
    return await commercial_api_request(
        ctx,
        billing_class="knowledge.read",
        idempotency_key=idempotency_key,
        max_billable_units=max_billable_units,
        requested_result_limit=1,
        request_arguments={"page_id": page_id},
        method="GET",
        path=f"/internal/v1/domain/knowledge/pages/{page_id}",
    )


@mcp.tool()
async def create_data_export(
    ctx: McpContext,
    dataset: str,
    idempotency_key: str,
    max_billable_units: str,
    export_format: str = "jsonl",
    filters: dict[str, Any] | None = None,
    fields: list[str] | None = None,
    max_records: int = 1000,
) -> dict[str, Any]:
    """Create a governed asynchronous structured-data export; large jobs may await human approval."""
    if not 1 <= max_records <= 5000:
        raise ValueError("max_records must be between 1 and 5000")
    return cast(
        dict[str, Any],
        await api_request(
            ctx,
            "POST",
            "/internal/v1/exports",
            json={
                "dataset": dataset,
                "export_format": export_format,
                "filters": filters or {},
                "fields": fields or [],
                "max_records": max_records,
                "max_billable_units": max_billable_units,
                "idempotency_key": idempotency_key,
            },
        ),
    )


@mcp.tool()
async def get_data_export(ctx: McpContext, job_id: str) -> dict[str, Any]:
    """Read the state, counts, checksums and expiry of an owned governed export job."""
    return cast(dict[str, Any], await api_request(ctx, "GET", f"/internal/v1/exports/{job_id}"))


@mcp.tool()
async def cancel_data_export(ctx: McpContext, job_id: str) -> dict[str, Any]:
    """Cancel an owned export that has not completed and release any reserved commercial units."""
    return cast(
        dict[str, Any],
        await api_request(ctx, "POST", f"/internal/v1/exports/{job_id}/cancel"),
    )


@mcp.tool()
async def read_data_export(
    ctx: McpContext,
    job_id: str,
    limit: int = 100,
    cursor: str = "",
) -> dict[str, Any]:
    """Read one signed, owner-bound page from a completed export with its signed manifest."""
    if not 1 <= limit <= settings.export_read_page_size_max:
        raise ValueError(f"limit must be between 1 and {settings.export_read_page_size_max}")
    params: dict[str, Any] = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    return cast(
        dict[str, Any],
        await api_request(
            ctx,
            "GET",
            f"/internal/v1/exports/{job_id}/chunks",
            params=params,
        ),
    )


def build_http_app_components() -> tuple[ASGIApp, Starlette]:
    lifespan_app = mcp.streamable_http_app()
    if not isinstance(lifespan_app, Starlette):
        raise RuntimeError("MCP SDK returned an unsupported HTTP application")
    app: ASGIApp = lifespan_app
    if not settings.mcp_dpop_required:
        return app, lifespan_app
    if token_verifier is None:
        raise RuntimeError("DPoP sender constraints require an MCP token verifier")
    replay_store = ValkeyDpopReplayStore(
        settings.redis_url,
        timeout_seconds=settings.mcp_dpop_replay_timeout_seconds,
    )
    proof_verifier = DpopProofVerifier(
        resource_url=settings.mcp_resource_server_url,
        replay_store=replay_store,
        max_proof_age_seconds=settings.mcp_dpop_max_proof_age_seconds,
        clock_skew_seconds=settings.mcp_dpop_clock_skew_seconds,
    )
    return (
        DpopSenderConstraintMiddleware(
            app,
            token_verifier=token_verifier,
            proof_verifier=proof_verifier,
        ),
        lifespan_app,
    )


def build_http_app() -> ASGIApp:
    app, _lifespan_app = build_http_app_components()
    return app


def run() -> None:
    import uvicorn

    initialize_telemetry("pharma-mcp")
    uvicorn.run(
        build_http_app(),
        host=settings.mcp_host,
        port=settings.mcp_port,
        log_level=settings.log_level.lower(),
    )
