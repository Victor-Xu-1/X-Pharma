from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from pharma_intel.commercial.billing import (
    BillingProviderPermanentError,
    BillingProviderReceipt,
    BillingProviderTransientError,
    BillingStatementSigner,
    HttpBillingProviderAdapter,
    validate_billing_provider_receipt,
)

SIGNING_SECRET = hashlib.sha256(b"billing-provider-test-signing-key").hexdigest()
API_TOKEN = hashlib.sha256(b"billing-provider-test-api-token").hexdigest()


class ProviderState:
    def __init__(self) -> None:
        self.status = 201
        self.response: bytes = json.dumps(
            {
                "provider": "approved-erp",
                "external_invoice_id": "INV-2026-0001",
                "status": "issued",
                "amount_due": "125.50",
                "currency": "CNY",
                "metadata": {"tax_reference": "TAX-001"},
            }
        ).encode()
        self.headers: dict[str, str] = {}
        self.request: dict[str, Any] = {}
        self.content_type = "application/json"


@contextmanager
def _provider_server() -> Any:
    state = ProviderState()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            state.headers = {key.casefold(): value for key, value in self.headers.items()}
            state.request = json.loads(self.rfile.read(length))
            self.send_response(state.status)
            if 300 <= state.status < 400:
                self.send_header("Location", "http://127.0.0.1:1/prohibited")
            self.send_header("Content-Type", state.content_type)
            self.send_header("Content-Length", str(len(state.response)))
            self.end_headers()
            self.wfile.write(state.response)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _adapter(base_url: str, *, max_response_bytes: int = 65_536) -> HttpBillingProviderAdapter:
    return HttpBillingProviderAdapter(
        provider="approved-erp",
        base_url=base_url,
        api_token=API_TOKEN,
        connect_timeout_seconds=2,
        request_timeout_seconds=2,
        verify=False,
        max_response_bytes=max_response_bytes,
        max_metadata_bytes=min(16_384, max_response_bytes),
    )


def _manifest() -> Any:
    return BillingStatementSigner(SIGNING_SECRET, key_id="billing-test-v1").sign(
        {"schema": "pharma.billing-statement.v1", "statement_key": "statement-2026-07"}
    )


def test_real_http_billing_adapter_sends_bound_idempotent_statement() -> None:
    with _provider_server() as (base_url, state):
        manifest = _manifest()
        receipt = _adapter(base_url).create_invoice(
            manifest,
            idempotency_key="statement:00000000-0000-0000-0000-000000000001:abcdef12",
            customer_reference="CUSTOMER-001",
        )

    assert receipt == BillingProviderReceipt(
        "approved-erp",
        "INV-2026-0001",
        "issued",
        Decimal("125.50"),
        "CNY",
        {"tax_reference": "TAX-001"},
    )
    assert state.headers["authorization"] == f"Bearer {API_TOKEN}"
    assert state.headers["idempotency-key"].startswith("statement:")
    assert state.headers["x-billing-manifest-sha256"] == manifest.sha256
    assert state.request["schema"] == "pharma.billing-provider-request.v1"
    assert state.request["customer_reference"] == "CUSTOMER-001"
    assert state.request["statement"] == manifest.envelope()


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (302, BillingProviderPermanentError),
        (400, BillingProviderPermanentError),
        (429, BillingProviderTransientError),
        (503, BillingProviderTransientError),
    ],
)
def test_billing_adapter_classifies_http_failures_without_following_redirects(
    status: int,
    error: type[Exception],
) -> None:
    with _provider_server() as (base_url, state):
        state.status = status
        with pytest.raises(error):
            _adapter(base_url).create_invoice(
                _manifest(),
                idempotency_key="statement:00000000-0000-0000-0000-000000000001:abcdef12",
                customer_reference="CUSTOMER-001",
            )


def test_billing_adapter_rejects_oversized_or_sensitive_receipts() -> None:
    with _provider_server() as (base_url, state):
        state.response = b"x" * 2048
        with pytest.raises(BillingProviderPermanentError, match="exceeds"):
            _adapter(base_url, max_response_bytes=1024).create_invoice(
                _manifest(),
                idempotency_key="statement:00000000-0000-0000-0000-000000000001:abcdef12",
                customer_reference="CUSTOMER-001",
            )

    with pytest.raises(ValueError, match="payment-card"):
        validate_billing_provider_receipt(
            BillingProviderReceipt(
                "approved-erp",
                "INV-1",
                "issued",
                Decimal("1"),
                "CNY",
                {"card_number": "4111111111111111"},
            )
        )
    with pytest.raises(ValueError, match="not allowlisted"):
        validate_billing_provider_receipt(
            BillingProviderReceipt(
                "approved-erp",
                "INV-1",
                "issued",
                Decimal("1"),
                "CNY",
                {"raw_provider_payload": "must not be persisted"},
            )
        )


def test_billing_adapter_rejects_provider_identity_or_schema_drift() -> None:
    with _provider_server() as (base_url, state):
        document = json.loads(state.response)
        document["provider"] = "unexpected-provider"
        state.response = json.dumps(document).encode()
        with pytest.raises(BillingProviderPermanentError, match="identity"):
            _adapter(base_url).create_invoice(
                _manifest(),
                idempotency_key="statement:00000000-0000-0000-0000-000000000001:abcdef12",
                customer_reference="CUSTOMER-001",
            )

        document["extra"] = True
        state.response = json.dumps(document).encode()
        with pytest.raises(BillingProviderPermanentError, match="schema"):
            _adapter(base_url).create_invoice(
                _manifest(),
                idempotency_key="statement:00000000-0000-0000-0000-000000000001:abcdef12",
                customer_reference="CUSTOMER-001",
            )


def test_billing_adapter_rejects_success_with_non_json_media_type() -> None:
    with _provider_server() as (base_url, state):
        state.content_type = "text/plain"

        with pytest.raises(BillingProviderPermanentError, match="application/json"):
            _adapter(base_url).create_invoice(
                _manifest(),
                idempotency_key="statement:00000000-0000-0000-0000-000000000001:abcdef12",
                customer_reference="CUSTOMER-001",
            )
