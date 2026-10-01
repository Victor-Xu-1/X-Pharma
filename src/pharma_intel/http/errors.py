from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from pharma_intel.chemistry import ChemistryBackendUnavailable, ChemistryValidationError
from pharma_intel.commercial.accounting import CommercialAccountingConflict, CommercialBalanceViolation
from pharma_intel.commercial.disputes import BillingDisputeConflict, BillingDisputeNotFound
from pharma_intel.commercial.exports import ExportStateConflict, ExportValidationError
from pharma_intel.commercial.operations import CommercialOperationsConflict, CommercialOperationsNotFound
from pharma_intel.commercial.service import (
    CommercialAccessDenied,
    CommercialError,
    CommercialInvariantViolation,
    CommercialNotConfigured,
    IdempotencyConflict,
    InsufficientCredits,
    ReservationConflict,
    ReservationExpired,
    SettlementLimitExceeded,
)
from pharma_intel.enterprise.admin import EnterpriseAdminAccessDenied, EnterpriseAdminConflict, EnterpriseAdminNotFound
from pharma_intel.governance.lifecycle import LifecycleConflict, LifecycleError
from pharma_intel.ingest.commands.errors import IngestionCommandError

request_logger = structlog.get_logger("pharma_intel.request")


async def request_validation_errors(request: Request, error: RequestValidationError) -> Response:
    if not request.url.path.startswith("/api/v1/auth/"):
        return await request_validation_exception_handler(request, error)
    # Framework errors otherwise echo the raw password or invitation input.
    detail = [{key: item[key] for key in ("type", "loc", "msg")} for item in error.errors()]
    return JSONResponse(status_code=422, content={"detail": detail})


async def commercial_error_handler(_: Request, exc: CommercialError) -> JSONResponse:
    if isinstance(exc, CommercialNotConfigured | InsufficientCredits):
        status_code = status.HTTP_402_PAYMENT_REQUIRED
        detail = str(exc)
    elif isinstance(exc, CommercialAccessDenied):
        status_code = status.HTTP_403_FORBIDDEN
        detail = str(exc)
    elif isinstance(
        exc,
        IdempotencyConflict
        | ReservationConflict
        | ReservationExpired
        | CommercialAccountingConflict
        | ExportStateConflict,
    ):
        status_code = status.HTTP_409_CONFLICT
        detail = str(exc)
    elif isinstance(exc, SettlementLimitExceeded | CommercialBalanceViolation | ExportValidationError):
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        detail = str(exc)
    elif isinstance(exc, CommercialInvariantViolation):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail = "Commercial accounting is temporarily unavailable"
        request_logger.error("commercial_invariant_violation", error_type=type(exc).__name__)
    else:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail = "Commercial accounting is temporarily unavailable"
    return JSONResponse(status_code=status_code, content={"detail": detail})


async def commercial_operations_not_found_handler(_: Request, exc: CommercialOperationsNotFound) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


async def commercial_operations_conflict_handler(_: Request, exc: CommercialOperationsConflict) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


async def billing_dispute_not_found_handler(_: Request, exc: BillingDisputeNotFound) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


async def billing_dispute_conflict_handler(_: Request, exc: BillingDisputeConflict) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


async def lifecycle_conflict_handler(_: Request, exc: LifecycleConflict) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


async def lifecycle_error_handler(_: Request, exc: LifecycleError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)})


async def enterprise_admin_not_found_handler(_: Request, exc: EnterpriseAdminNotFound) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


async def enterprise_admin_conflict_handler(_: Request, exc: EnterpriseAdminConflict) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


async def enterprise_admin_access_denied_handler(_: Request, exc: EnterpriseAdminAccessDenied) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})


async def chemistry_validation_error_handler(_: Request, exc: ChemistryValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": {"code": exc.code, "message": str(exc)}},
    )


async def chemistry_backend_error_handler(_: Request, exc: ChemistryBackendUnavailable) -> JSONResponse:
    request_logger.error("chemistry_backend_unavailable", error_type=type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": {"code": "chemistry_backend_unavailable", "message": "Chemical search is unavailable"}},
    )


async def ingestion_command_error_handler(_: Request, error: IngestionCommandError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"detail": error.detail})


def _register[ErrorType: Exception](
    app: FastAPI,
    error_type: type[ErrorType],
    handler: Callable[[Request, ErrorType], Awaitable[Response]],
) -> None:
    async def checked_handler(request: Request, error: Exception) -> Response:
        if not isinstance(error, error_type):
            raise TypeError("Exception dispatch does not match the registered error type")
        return await handler(request, error)

    app.add_exception_handler(error_type, checked_handler)


def install_error_handlers(app: FastAPI) -> None:
    _register(app, IngestionCommandError, ingestion_command_error_handler)
    _register(app, RequestValidationError, request_validation_errors)
    _register(app, CommercialError, commercial_error_handler)
    _register(app, CommercialOperationsNotFound, commercial_operations_not_found_handler)
    _register(app, CommercialOperationsConflict, commercial_operations_conflict_handler)
    _register(app, BillingDisputeNotFound, billing_dispute_not_found_handler)
    _register(app, BillingDisputeConflict, billing_dispute_conflict_handler)
    _register(app, LifecycleConflict, lifecycle_conflict_handler)
    _register(app, LifecycleError, lifecycle_error_handler)
    _register(app, EnterpriseAdminNotFound, enterprise_admin_not_found_handler)
    _register(app, EnterpriseAdminConflict, enterprise_admin_conflict_handler)
    _register(app, EnterpriseAdminAccessDenied, enterprise_admin_access_denied_handler)
    _register(app, ChemistryValidationError, chemistry_validation_error_handler)
    _register(app, ChemistryBackendUnavailable, chemistry_backend_error_handler)
