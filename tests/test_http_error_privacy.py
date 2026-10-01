import asyncio
import secrets

import pytest
from fastapi import Request

from pharma_intel.chemistry import ChemistryBackendUnavailable
from pharma_intel.commercial.service import CommercialInvariantViolation
from pharma_intel.http import errors


def test_backend_failure_logs_do_not_copy_sensitive_exception_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[tuple[str, dict[str, object]]] = []

    class Logger:
        def error(self, event: str, **details: object) -> None:
            recorded.append((event, details))

    monkeypatch.setattr(errors, "request_logger", Logger())
    marker = secrets.token_urlsafe(24)
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    commercial = asyncio.run(errors.commercial_error_handler(request, CommercialInvariantViolation(marker)))
    chemical = asyncio.run(errors.chemistry_backend_error_handler(request, ChemistryBackendUnavailable(marker)))
    assert commercial.status_code == chemical.status_code == 503
    assert marker.encode() not in commercial.body and marker.encode() not in chemical.body
    assert all(marker not in str(details) and set(details) == {"error_type"} for _, details in recorded)
