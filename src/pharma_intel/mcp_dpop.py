from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import math
import re
import time
from collections.abc import Callable
from typing import Any, Protocol, cast
from urllib.parse import SplitResult, urlsplit, urlunsplit

import jwt
import structlog
from mcp.server.auth.provider import TokenVerifier
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

DPoP_JWT_TYPE = "dpop+jwt"
DPoP_HEADER = b"dpop"
AUTHORIZATION_HEADER = b"authorization"
ALLOWED_ALGORITHMS = frozenset({"ES256", "RS256"})
CONFIRMATION_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
JTI_PATTERN = re.compile(r"^[\x21-\x7e]{8,200}$")
JWT_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
MAX_ACCESS_TOKEN_BYTES = 32_768
MAX_PROOF_BYTES = 16_384
REPLAY_KEY_PREFIX = "pharma:mcp:dpop:v1:"

logger = structlog.get_logger("pharma_intel.mcp.dpop")


class DpopValidationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class DpopReplayStoreUnavailable(RuntimeError):
    pass


class DpopReplayStore(Protocol):
    async def reserve(self, *, key_thumbprint: str, jti: str, ttl_seconds: int) -> bool: ...

    async def aclose(self) -> None: ...


class ValkeyDpopReplayStore:
    """Shared, fail-closed DPoP replay window backed by Valkey/Redis SET NX."""

    def __init__(self, url: str, *, timeout_seconds: float = 1.0) -> None:
        self._client: Redis = Redis.from_url(
            url,
            decode_responses=True,
            protocol=3,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
            health_check_interval=30,
        )

    async def reserve(self, *, key_thumbprint: str, jti: str, ttl_seconds: int) -> bool:
        digest = hashlib.sha256(f"{key_thumbprint}\0{jti}".encode()).hexdigest()
        try:
            result = await self._client.set(
                f"{REPLAY_KEY_PREFIX}{digest}",
                "1",
                ex=ttl_seconds,
                nx=True,
            )
        except RedisError as exc:
            raise DpopReplayStoreUnavailable("DPoP replay store is unavailable") from exc
        return result is True

    async def aclose(self) -> None:
        await self._client.aclose()


class DpopProofVerifier:
    def __init__(
        self,
        *,
        resource_url: str,
        replay_store: DpopReplayStore,
        max_proof_age_seconds: int,
        clock_skew_seconds: int,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.resource_url = _canonical_uri(resource_url)
        self.resource_path = urlsplit(self.resource_url).path
        self.replay_store = replay_store
        self.max_proof_age_seconds = max_proof_age_seconds
        self.clock_skew_seconds = clock_skew_seconds
        self.now = now

    async def verify(
        self,
        *,
        method: str,
        authorization: str,
        proof: str,
        confirmation_thumbprint: str,
    ) -> str:
        token = _dpop_access_token(authorization)
        if len(token.encode("ascii", errors="ignore")) > MAX_ACCESS_TOKEN_BYTES:
            raise DpopValidationError("access_token_too_large")
        try:
            proof_bytes = proof.encode("ascii")
        except UnicodeEncodeError as exc:
            raise DpopValidationError("invalid_proof_encoding") from exc
        if len(proof_bytes) > MAX_PROOF_BYTES:
            raise DpopValidationError("proof_too_large")

        header = _proof_header(proof)
        algorithm = header.get("alg")
        jwk = header.get("jwk")
        if algorithm not in ALLOWED_ALGORITHMS or not isinstance(jwk, dict):
            raise DpopValidationError("unsupported_proof_key")
        _reject_private_jwk(jwk)
        _validate_jwk_algorithm(jwk, algorithm)
        actual_thumbprint = _jwk_thumbprint(jwk)
        if not hmac.compare_digest(actual_thumbprint, confirmation_thumbprint):
            raise DpopValidationError("proof_key_mismatch")

        try:
            signing_key = jwt.PyJWK.from_dict(jwk, algorithm=algorithm).key
            claims = jwt.decode(
                proof,
                signing_key,
                algorithms=[algorithm],
                options={
                    "require": ["jti", "htm", "htu", "iat", "ath"],
                    "verify_aud": False,
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                },
            )
        except (jwt.PyJWTError, ValueError, TypeError) as exc:
            raise DpopValidationError("invalid_proof_signature") from exc
        if not isinstance(claims, dict):
            raise DpopValidationError("invalid_proof_claims")

        jti = claims.get("jti")
        htm = claims.get("htm")
        htu = claims.get("htu")
        issued_at = claims.get("iat")
        access_token_hash = claims.get("ath")
        if not isinstance(jti, str) or JTI_PATTERN.fullmatch(jti) is None:
            raise DpopValidationError("invalid_proof_jti")
        if not isinstance(htm, str) or htm != method.upper():
            raise DpopValidationError("proof_method_mismatch")
        if not isinstance(htu, str) or _canonical_uri(htu) != self.resource_url:
            raise DpopValidationError("proof_uri_mismatch")
        if isinstance(issued_at, bool) or not isinstance(issued_at, int):
            raise DpopValidationError("invalid_proof_time")
        current_time = self.now()
        if issued_at > current_time + self.clock_skew_seconds:
            raise DpopValidationError("proof_from_future")
        if issued_at < current_time - self.max_proof_age_seconds - self.clock_skew_seconds:
            raise DpopValidationError("stale_proof")
        expected_access_token_hash = _base64url(hashlib.sha256(token.encode("ascii")).digest())
        if not isinstance(access_token_hash, str) or not hmac.compare_digest(
            access_token_hash,
            expected_access_token_hash,
        ):
            raise DpopValidationError("access_token_hash_mismatch")

        expires_at = issued_at + self.max_proof_age_seconds + self.clock_skew_seconds
        ttl_seconds = max(1, math.ceil(expires_at - current_time))
        if not await self.replay_store.reserve(
            key_thumbprint=actual_thumbprint,
            jti=jti,
            ttl_seconds=ttl_seconds,
        ):
            raise DpopValidationError("proof_replayed")
        return token


class DpopSenderConstraintMiddleware:
    """Validate a sender-constrained token before the MCP SDK authentication layer."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        token_verifier: TokenVerifier,
        proof_verifier: DpopProofVerifier,
    ) -> None:
        self.app = app
        self.token_verifier = token_verifier
        self.proof_verifier = proof_verifier

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._lifespan(scope, receive, send)
            return
        if scope["type"] != "http" or not _matches_resource_path(scope, self.proof_verifier.resource_path):
            await self.app(scope, receive, send)
            return
        try:
            authorization = _single_header(scope, AUTHORIZATION_HEADER)
            proof = _single_header(scope, DPoP_HEADER)
            if authorization is None or proof is None:
                raise DpopValidationError("proof_required")
            token = _dpop_access_token(authorization)
            if await self.token_verifier.verify_token(token) is None:
                raise DpopValidationError("invalid_access_token")
            confirmation_thumbprint = _verified_access_token_thumbprint(token)
            token = await self.proof_verifier.verify(
                method=str(scope.get("method", "")),
                authorization=authorization,
                proof=proof,
                confirmation_thumbprint=confirmation_thumbprint,
            )
        except DpopReplayStoreUnavailable:
            logger.error("mcp_dpop_replay_store_unavailable")
            await _error_response(send, status_code=503, code="sender_constraint_unavailable")
            return
        except (DpopValidationError, UnicodeError) as exc:
            code = exc.code if isinstance(exc, DpopValidationError) else "invalid_header_encoding"
            logger.info("mcp_dpop_rejected", reason=code)
            await _error_response(send, status_code=401, code="invalid_dpop_proof")
            return

        forwarded_scope = dict(scope)
        forwarded_scope["headers"] = _replace_authorization(scope, f"Bearer {token}".encode("ascii"))
        await self.app(forwarded_scope, receive, send)

    async def _lifespan(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def managed_send(message: Message) -> None:
            if message["type"] in {"lifespan.shutdown.complete", "lifespan.shutdown.failed"}:
                await self.proof_verifier.replay_store.aclose()
            await send(message)

        await self.app(scope, receive, managed_send)


async def _error_response(send: Send, *, status_code: int, code: str) -> None:
    headers = {"Cache-Control": "no-store"}
    if status_code == 401:
        headers["WWW-Authenticate"] = 'DPoP error="invalid_dpop_proof"'
    else:
        headers["Retry-After"] = "1"
    response = JSONResponse({"error": code}, status_code=status_code, headers=headers)
    await response({"type": "http", "method": "GET", "path": "/"}, _empty_receive, send)


async def _empty_receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


def _single_header(scope: Scope, name: bytes) -> str | None:
    headers = cast(list[tuple[bytes, bytes]], scope.get("headers", []))
    values = [value for key, value in headers if key.lower() == name]
    if len(values) > 1:
        raise DpopValidationError("duplicate_security_header")
    if not values:
        return None
    try:
        return values[0].decode("ascii")
    except UnicodeDecodeError as exc:
        raise DpopValidationError("invalid_header_encoding") from exc


def _replace_authorization(scope: Scope, value: bytes) -> list[tuple[bytes, bytes]]:
    return [(key, item) for key, item in scope.get("headers", []) if key.lower() != AUTHORIZATION_HEADER] + [
        (AUTHORIZATION_HEADER, value)
    ]


def _matches_resource_path(scope: Scope, expected_path: str) -> bool:
    path = str(scope.get("path", ""))
    return path.rstrip("/") == expected_path.rstrip("/")


def _dpop_access_token(authorization: str) -> str:
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].casefold() != "dpop" or not parts[1]:
        raise DpopValidationError("dpop_authorization_required")
    try:
        parts[1].encode("ascii")
    except UnicodeEncodeError as exc:
        raise DpopValidationError("invalid_access_token_encoding") from exc
    return parts[1]


def _verified_access_token_thumbprint(token: str) -> str:
    """Read cnf only after the configured TokenVerifier accepted this exact token."""

    segments = token.split(".")
    if len(segments) != 3 or JWT_SEGMENT_PATTERN.fullmatch(segments[1]) is None:
        raise DpopValidationError("invalid_access_token_shape")
    encoded_payload = segments[1]
    padded_payload = encoded_payload + ("=" * (-len(encoded_payload) % 4))
    try:
        payload = base64.b64decode(
            padded_payload,
            altchars=b"-_",
            validate=True,
        )
        claims = json.loads(payload)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DpopValidationError("invalid_access_token_shape") from exc
    confirmation = claims.get("cnf") if isinstance(claims, dict) else None
    if not isinstance(confirmation, dict) or set(confirmation).intersection({"jkt", "x5t#S256"}) != {"jkt"}:
        raise DpopValidationError("dpop_confirmation_required")
    thumbprint = confirmation.get("jkt")
    if not isinstance(thumbprint, str) or CONFIRMATION_PATTERN.fullmatch(thumbprint) is None:
        raise DpopValidationError("invalid_confirmation_thumbprint")
    return thumbprint


def _proof_header(proof: str) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(proof)
    except jwt.PyJWTError as exc:
        raise DpopValidationError("invalid_proof_header") from exc
    proof_type = header.get("typ") if isinstance(header, dict) else None
    if not isinstance(proof_type, str) or proof_type.casefold() != DPoP_JWT_TYPE:
        raise DpopValidationError("invalid_proof_type")
    return header


def _reject_private_jwk(jwk: dict[str, Any]) -> None:
    private_members = {"d", "k", "p", "q", "dp", "dq", "qi", "oth"}
    if private_members.intersection(jwk):
        raise DpopValidationError("private_proof_key_forbidden")


def _validate_jwk_algorithm(jwk: dict[str, Any], algorithm: object) -> None:
    key_type = jwk.get("kty")
    if algorithm == "ES256" and (key_type != "EC" or jwk.get("crv") != "P-256"):
        raise DpopValidationError("proof_key_algorithm_mismatch")
    if algorithm == "RS256" and key_type != "RSA":
        raise DpopValidationError("proof_key_algorithm_mismatch")


def _jwk_thumbprint(jwk: dict[str, Any]) -> str:
    key_type = jwk.get("kty")
    required: tuple[str, ...]
    if key_type == "EC":
        required = ("crv", "kty", "x", "y")
    elif key_type == "RSA":
        required = ("e", "kty", "n")
    else:
        raise DpopValidationError("unsupported_proof_key_type")
    if any(not isinstance(jwk.get(name), str) or not jwk[name] for name in required):
        raise DpopValidationError("incomplete_proof_key")
    canonical = json.dumps(
        {name: jwk[name] for name in required},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return _base64url(hashlib.sha256(canonical).digest())


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _canonical_uri(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise DpopValidationError("invalid_proof_uri") from exc
    scheme = parsed.scheme.casefold()
    if (
        scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise DpopValidationError("invalid_proof_uri")
    hostname = parsed.hostname.casefold()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    default_port = 443 if scheme == "https" else 80
    authority = hostname if port in {None, default_port} else f"{hostname}:{port}"
    path = parsed.path or "/"
    return urlunsplit(SplitResult(scheme, authority, path, "", ""))
