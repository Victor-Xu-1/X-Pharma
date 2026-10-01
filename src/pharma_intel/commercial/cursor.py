from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from pharma_intel.security import Principal

CURSOR_VERSION = 1
INVALID_CURSOR_CODE = "INVALID_CURSOR"
CURSOR_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class CursorError(ValueError):
    pass


@dataclass(frozen=True)
class CursorClaims:
    version: int
    tenant_id: str
    subject_id: str
    actor_type: str
    client_id: str
    tool: str
    query_sha256: str
    page_size: int
    offset: int
    depth: int
    chain_id: str
    expires_at: int


class SignedCursorCodec:
    def __init__(self, secret: str, *, ttl_seconds: int = 300, max_token_chars: int = 4096) -> None:
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("Cursor signing secret must contain at least 32 bytes")
        if not 30 <= ttl_seconds <= 3600:
            raise ValueError("Cursor TTL must be between 30 and 3600 seconds")
        self._secret = secret.encode("utf-8")
        self._ttl_seconds = ttl_seconds
        self._max_token_chars = max_token_chars

    def issue(
        self,
        principal: Principal,
        *,
        tool: str,
        query_sha256: str,
        page_size: int,
        offset: int,
        depth: int,
        chain_id: str | None = None,
        now_epoch: int | None = None,
    ) -> str:
        client_id = principal.commercial_client_id
        if not client_id:
            raise CursorError("Cursor cannot be issued without an Agent client identity")
        if page_size <= 0 or offset < 0 or depth <= 0:
            raise CursorError("Cursor pagination values are invalid")
        if not SHA256_PATTERN.fullmatch(query_sha256):
            raise CursorError("Cursor query fingerprint is invalid")
        resolved_chain_id = chain_id or str(uuid.uuid4())
        try:
            uuid.UUID(resolved_chain_id)
        except ValueError as exc:
            raise CursorError("Cursor chain identity is invalid") from exc
        issued_at = int(time.time()) if now_epoch is None else now_epoch
        claims = CursorClaims(
            version=CURSOR_VERSION,
            tenant_id=principal.tenant_id,
            subject_id=principal.actor_id,
            actor_type=principal.actor_type,
            client_id=client_id,
            tool=tool,
            query_sha256=query_sha256,
            page_size=page_size,
            offset=offset,
            depth=depth,
            chain_id=resolved_chain_id,
            expires_at=issued_at + self._ttl_seconds,
        )
        body = json.dumps(asdict(claims), sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self._secret, body, hashlib.sha256).digest()
        return f"{_encode(body)}.{_encode(signature)}"

    def verify(
        self,
        token: str,
        principal: Principal,
        *,
        tool: str,
        query_sha256: str,
        page_size: int,
        now_epoch: int | None = None,
    ) -> CursorClaims:
        try:
            if len(token) > self._max_token_chars or not CURSOR_TOKEN_PATTERN.fullmatch(token):
                raise CursorError
            encoded_body, encoded_signature = token.split(".", 1)
            body = _decode(encoded_body)
            signature = _decode(encoded_signature)
            expected_signature = hmac.new(self._secret, body, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected_signature):
                raise CursorError
            payload = json.loads(body)
            if not isinstance(payload, dict) or set(payload) != {
                "version",
                "tenant_id",
                "subject_id",
                "actor_type",
                "client_id",
                "tool",
                "query_sha256",
                "page_size",
                "offset",
                "depth",
                "chain_id",
                "expires_at",
            }:
                raise CursorError
            claims = _claims_from_payload(payload)
        except (TypeError, ValueError, UnicodeError) as exc:
            raise CursorError("Pagination cursor is invalid or expired") from exc

        current_epoch = int(time.time()) if now_epoch is None else now_epoch
        client_id = principal.commercial_client_id
        values_match = (
            claims.version == CURSOR_VERSION
            and claims.tenant_id == principal.tenant_id
            and claims.subject_id == principal.actor_id
            and claims.actor_type == principal.actor_type
            and claims.client_id == client_id
            and claims.tool == tool
            and claims.query_sha256 == query_sha256
            and claims.page_size == page_size
            and type(claims.page_size) is int
            and type(claims.offset) is int
            and type(claims.depth) is int
            and type(claims.expires_at) is int
            and claims.offset >= 0
            and claims.depth > 0
            and claims.expires_at > current_epoch
        )
        if not values_match:
            raise CursorError("Pagination cursor is invalid or expired")
        return claims


def query_fingerprint(tool: str, arguments: dict[str, Any], page_size: int) -> str:
    normalized = {key: value for key, value in arguments.items() if key != "cursor"}
    body = json.dumps(
        {"tool": tool, "arguments": normalized, "page_size": page_size},
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _claims_from_payload(payload: dict[str, Any]) -> CursorClaims:
    string_fields = (
        "tenant_id",
        "subject_id",
        "actor_type",
        "client_id",
        "tool",
        "query_sha256",
        "chain_id",
    )
    if any(not isinstance(payload[field], str) or not payload[field] for field in string_fields):
        raise CursorError
    integer_fields = ("version", "page_size", "offset", "depth", "expires_at")
    if any(type(payload[field]) is not int for field in integer_fields):
        raise CursorError
    if not SHA256_PATTERN.fullmatch(payload["query_sha256"]):
        raise CursorError
    uuid.UUID(payload["chain_id"])
    return CursorClaims(**payload)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    if _encode(decoded) != value:
        raise ValueError("Base64URL value is not canonical")
    return decoded
