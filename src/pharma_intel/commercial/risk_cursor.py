from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from datetime import UTC, datetime
from typing import Literal

RiskCaseFilter = Literal["all", "open", "acknowledged", "resolved", "dismissed"]

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
_VALID_FILTERS: frozenset[str] = frozenset({"all", "open", "acknowledged", "resolved", "dismissed"})


class RiskCursorError(ValueError):
    pass


class RiskCursorCodec:
    def __init__(self, secret: str, *, ttl_seconds: int = 900, max_token_chars: int = 4096) -> None:
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("Risk cursor signing secret must contain at least 32 bytes")
        if not 30 <= ttl_seconds <= 3600:
            raise ValueError("Risk cursor TTL must be between 30 and 3600 seconds")
        self._secret = secret.encode("utf-8")
        self._ttl_seconds = ttl_seconds
        self._max_token_chars = max_token_chars

    def issue(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        case_status: RiskCaseFilter,
        page_size: int,
        occurred_at: datetime,
        event_id: str,
        now_epoch: int | None = None,
    ) -> str:
        if (
            case_status not in _VALID_FILTERS
            or not tenant_id
            or not actor_id
            or not event_id
            or not 1 <= page_size <= 100
        ):
            raise RiskCursorError("Risk pagination values are invalid")
        normalized_occurred_at = (
            occurred_at.replace(tzinfo=UTC)
            if occurred_at.tzinfo is None or occurred_at.utcoffset() is None
            else occurred_at.astimezone(UTC)
        )
        issued_at = int(time.time()) if now_epoch is None else now_epoch
        payload = {
            "version": 1,
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "case_status": case_status,
            "page_size": page_size,
            "occurred_at": normalized_occurred_at.isoformat(),
            "event_id": event_id,
            "expires_at": issued_at + self._ttl_seconds,
        }
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self._secret, body, hashlib.sha256).digest()
        return f"{_encode(body)}.{_encode(signature)}"

    def verify(
        self,
        token: str,
        *,
        tenant_id: str,
        actor_id: str,
        case_status: RiskCaseFilter,
        page_size: int,
        now_epoch: int | None = None,
    ) -> tuple[datetime, str]:
        try:
            if len(token) > self._max_token_chars or not _TOKEN_PATTERN.fullmatch(token):
                raise ValueError
            encoded_body, encoded_signature = token.split(".", 1)
            body = _decode(encoded_body)
            signature = _decode(encoded_signature)
            expected_signature = hmac.new(self._secret, body, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected_signature):
                raise ValueError
            payload = json.loads(body)
            expected_keys = {
                "version",
                "tenant_id",
                "actor_id",
                "case_status",
                "page_size",
                "occurred_at",
                "event_id",
                "expires_at",
            }
            if not isinstance(payload, dict) or set(payload) != expected_keys:
                raise ValueError
            expires_at = payload["expires_at"]
            current_epoch = int(time.time()) if now_epoch is None else now_epoch
            if type(expires_at) is not int or expires_at <= current_epoch:
                raise ValueError
            if (
                payload["version"] != 1
                or type(payload["version"]) is not int
                or payload["tenant_id"] != tenant_id
                or payload["actor_id"] != actor_id
                or payload["case_status"] != case_status
                or payload["case_status"] not in _VALID_FILTERS
                or payload["page_size"] != page_size
                or type(payload["page_size"]) is not int
                or not 1 <= payload["page_size"] <= 100
                or not isinstance(payload["event_id"], str)
                or not payload["event_id"]
            ):
                raise ValueError
            occurred_at = datetime.fromisoformat(payload["occurred_at"])
            if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
                raise ValueError
            return occurred_at.astimezone(UTC), payload["event_id"]
        except (json.JSONDecodeError, TypeError, UnicodeError, ValueError) as exc:
            raise RiskCursorError("Risk pagination cursor is invalid or expired") from exc


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    if _encode(decoded) != value:
        raise ValueError("Base64URL value is not canonical")
    return decoded
