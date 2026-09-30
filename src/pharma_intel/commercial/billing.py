from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

PROVIDER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
PROVIDER_STATUS_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")
SENSITIVE_METADATA_KEYS = frozenset(
    {
        "card",
        "cardnumber",
        "pan",
        "cvv",
        "cvc",
        "track1",
        "track2",
        "magneticstripe",
        "expiry",
        "expiration",
        "securitycode",
    }
)
ALLOWED_PROVIDER_METADATA_KEYS = frozenset(
    {
        "accounting_reference",
        "credit_note_reference",
        "delivery_reference",
        "invoice_reference",
        "payment_status_reference",
        "provider_request_id",
        "tax_reference",
    }
)
RECEIPT_FIELDS = frozenset({"provider", "external_invoice_id", "status", "amount_due", "currency", "metadata"})


class BillingProviderError(RuntimeError):
    pass


class BillingProviderTransientError(BillingProviderError):
    pass


class BillingProviderPermanentError(BillingProviderError):
    pass


def canonical_manifest_bytes(payload: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
            default=_json_default,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Billing manifest is not valid canonical JSON") from exc


@dataclass(frozen=True)
class SignedBillingManifest:
    payload: dict[str, Any]
    sha256: str
    key_id: str
    signature: str

    def envelope(self) -> dict[str, Any]:
        return {
            "schema": "pharma.billing-statement-envelope.v1",
            "payload": self.payload,
            "sha256": self.sha256,
            "signature": {"algorithm": "HMAC-SHA256", "key_id": self.key_id, "value": self.signature},
        }


class BillingStatementSigner:
    def __init__(self, secret: str, *, key_id: str) -> None:
        secret_bytes = secret.encode("utf-8")
        if len(secret_bytes) < 32:
            raise ValueError("Billing statement signing secret must contain at least 32 bytes")
        if not key_id or len(key_id) > 120:
            raise ValueError("Billing statement signing key ID is invalid")
        self._secret = secret_bytes
        self.key_id = key_id

    def sign(self, payload: dict[str, Any]) -> SignedBillingManifest:
        body = canonical_manifest_bytes(payload)
        digest = hashlib.sha256(body).hexdigest()
        signature = hmac.new(self._secret, body, hashlib.sha256).hexdigest()
        return SignedBillingManifest(payload, digest, self.key_id, signature)

    def verify(self, manifest: SignedBillingManifest) -> bool:
        if manifest.key_id != self.key_id:
            return False
        expected = self.sign(manifest.payload)
        return hmac.compare_digest(expected.sha256, manifest.sha256) and hmac.compare_digest(
            expected.signature,
            manifest.signature,
        )


@dataclass(frozen=True)
class BillingProviderReceipt:
    provider: str
    external_invoice_id: str
    status: str
    amount_due: Decimal
    currency: str
    metadata: dict[str, Any]


class BillingProviderAdapter(Protocol):
    """External billing providers implement this boundary outside accounting storage."""

    def create_invoice(
        self,
        manifest: SignedBillingManifest,
        *,
        idempotency_key: str,
        customer_reference: str,
    ) -> BillingProviderReceipt: ...


class HttpBillingProviderAdapter:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_token: str,
        connect_timeout_seconds: float,
        request_timeout_seconds: float,
        verify: bool | str,
        max_response_bytes: int,
        max_metadata_bytes: int,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Billing provider base URL is invalid")
        if not PROVIDER_NAME_PATTERN.fullmatch(provider):
            raise ValueError("Billing provider name is invalid")
        if not api_token or len(api_token) > 16_384:
            raise ValueError("Billing provider API token is invalid")
        if max_response_bytes < 1024 or max_metadata_bytes < 256 or max_metadata_bytes > max_response_bytes:
            raise ValueError("Billing provider response limits are invalid")
        self.provider = provider
        self.endpoint = base_url.rstrip("/") + "/v1/invoices"
        self.api_token = api_token
        self.timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=request_timeout_seconds,
            write=request_timeout_seconds,
            pool=connect_timeout_seconds,
        )
        self.verify = verify
        self.max_response_bytes = max_response_bytes
        self.max_metadata_bytes = max_metadata_bytes

    def create_invoice(
        self,
        manifest: SignedBillingManifest,
        *,
        idempotency_key: str,
        customer_reference: str,
    ) -> BillingProviderReceipt:
        if not IDEMPOTENCY_KEY_PATTERN.fullmatch(idempotency_key):
            raise ValueError("Billing provider idempotency key is invalid")
        if not customer_reference or len(customer_reference) > 500:
            raise BillingProviderPermanentError("Billing customer mapping is unavailable")
        request_body = {
            "schema": "pharma.billing-provider-request.v1",
            "customer_reference": customer_reference,
            "statement": manifest.envelope(),
        }
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Idempotency-Key": idempotency_key,
            "X-Billing-Manifest-SHA256": manifest.sha256,
        }
        try:
            with httpx.Client(
                timeout=self.timeout,
                verify=self.verify,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                with client.stream("POST", self.endpoint, json=request_body, headers=headers) as response:
                    payload = _read_bounded_response(response, self.max_response_bytes)
                    status_code = response.status_code
                    content_type = response.headers.get("Content-Type", "").partition(";")[0].strip().casefold()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise BillingProviderTransientError("Billing provider request failed") from exc
        except httpx.HTTPError as exc:
            raise BillingProviderPermanentError("Billing provider protocol failed") from exc
        if status_code in {408, 425, 429} or status_code >= 500:
            raise BillingProviderTransientError(f"Billing provider returned retryable HTTP {status_code}")
        if 300 <= status_code < 400:
            raise BillingProviderPermanentError("Billing provider redirects are not allowed")
        if status_code not in {200, 201}:
            raise BillingProviderPermanentError(f"Billing provider returned HTTP {status_code}")
        if content_type != "application/json":
            raise BillingProviderPermanentError("Billing provider receipt must use application/json")
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BillingProviderPermanentError("Billing provider returned invalid JSON") from exc
        if not isinstance(document, dict) or set(document) != RECEIPT_FIELDS:
            raise BillingProviderPermanentError("Billing provider receipt schema is invalid")
        try:
            receipt = BillingProviderReceipt(
                provider=document["provider"],
                external_invoice_id=document["external_invoice_id"],
                status=document["status"],
                amount_due=Decimal(str(document["amount_due"])),
                currency=document["currency"],
                metadata=document["metadata"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BillingProviderPermanentError("Billing provider receipt values are invalid") from exc
        validated = validate_billing_provider_receipt(receipt, max_metadata_bytes=self.max_metadata_bytes)
        if validated.provider != self.provider:
            raise BillingProviderPermanentError("Billing provider receipt identity does not match configuration")
        return validated


def validate_billing_provider_receipt(
    receipt: BillingProviderReceipt,
    *,
    max_metadata_bytes: int = 16_384,
) -> BillingProviderReceipt:
    if not isinstance(receipt.provider, str) or not PROVIDER_NAME_PATTERN.fullmatch(receipt.provider):
        raise ValueError("Billing provider is invalid")
    if (
        not isinstance(receipt.external_invoice_id, str)
        or not receipt.external_invoice_id
        or len(receipt.external_invoice_id) > 500
    ):
        raise ValueError("External invoice ID is invalid")
    if not isinstance(receipt.status, str) or not PROVIDER_STATUS_PATTERN.fullmatch(receipt.status):
        raise ValueError("Billing provider status is invalid")
    amount_due = receipt.amount_due
    if not isinstance(amount_due, Decimal) or not amount_due.is_finite() or amount_due < 0:
        raise ValueError("Invoice amount must be finite and non-negative")
    currency = receipt.currency.upper() if isinstance(receipt.currency, str) else ""
    if re.fullmatch(r"[A-Z]{3}", currency) is None:
        raise ValueError("Invoice currency is invalid")
    if not isinstance(receipt.metadata, dict):
        raise ValueError("Billing provider metadata must be an object")
    _reject_sensitive_metadata(receipt.metadata)
    try:
        metadata_bytes = canonical_manifest_bytes(receipt.metadata)
    except ValueError as exc:
        raise ValueError("Billing provider metadata is invalid") from exc
    if len(metadata_bytes) > max_metadata_bytes:
        raise ValueError("Billing provider metadata exceeds the configured limit")
    return BillingProviderReceipt(
        receipt.provider,
        receipt.external_invoice_id,
        receipt.status,
        amount_due,
        currency,
        receipt.metadata,
    )


def _read_bounded_response(response: httpx.Response, maximum_bytes: int) -> bytes:
    content = bytearray()
    for chunk in response.iter_bytes():
        if len(content) + len(chunk) > maximum_bytes:
            raise BillingProviderPermanentError("Billing provider response exceeds the configured limit")
        content.extend(chunk)
    return bytes(content)


def _reject_sensitive_metadata(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("Billing provider metadata must be an object")
    if len(value) > len(ALLOWED_PROVIDER_METADATA_KEYS):
        raise ValueError("Billing provider metadata contains too many fields")
    for key, item in value.items():
        if not isinstance(key, str) or len(key) > 200:
            raise ValueError("Billing provider metadata key is invalid")
        normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
        if normalized in SENSITIVE_METADATA_KEYS:
            raise ValueError("Billing provider metadata contains prohibited payment-card fields")
        if key not in ALLOWED_PROVIDER_METADATA_KEYS:
            raise ValueError("Billing provider metadata key is not allowlisted")
        if item is not None and not isinstance(item, str | int | float | bool):
            raise ValueError("Billing provider metadata values must be scalar")
        if isinstance(item, str) and len(item) > 2000:
            raise ValueError("Billing provider metadata value is too long")


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    raise TypeError(f"Unsupported billing manifest value: {type(value).__name__}")
