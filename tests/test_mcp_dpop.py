from __future__ import annotations

import base64
import hashlib
import json
import time
from collections.abc import Mapping
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from mcp.server.auth.provider import AccessToken, TokenVerifier
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from pharma_intel.config import Settings
from pharma_intel.mcp_auth import OidcJwksTokenVerifier
from pharma_intel.mcp_dpop import (
    DpopProofVerifier,
    DpopReplayStoreUnavailable,
    DpopSenderConstraintMiddleware,
    ValkeyDpopReplayStore,
)

RESOURCE_URL = "https://mcp.example.test/mcp"
NOW = 1_800_000_000


class MemoryReplayStore:
    def __init__(self, *, unavailable: bool = False) -> None:
        self.keys: set[tuple[str, str]] = set()
        self.ttls: list[int] = []
        self.unavailable = unavailable
        self.closed = False

    async def reserve(self, *, key_thumbprint: str, jti: str, ttl_seconds: int) -> bool:
        if self.unavailable:
            raise DpopReplayStoreUnavailable("unavailable")
        key = (key_thumbprint, jti)
        self.ttls.append(ttl_seconds)
        if key in self.keys:
            return False
        self.keys.add(key)
        return True

    async def aclose(self) -> None:
        self.closed = True


class StaticTokenVerifier(TokenVerifier):
    def __init__(self, accepted_token: str | None) -> None:
        self.accepted_token = accepted_token
        self.calls = 0

    async def verify_token(self, token: str) -> AccessToken | None:
        self.calls += 1
        if token != self.accepted_token:
            return None
        return AccessToken(
            token=token,
            client_id="client-1",
            scopes=["mcp:connect"],
            expires_at=NOW + 300,
            resource=RESOURCE_URL,
        )


class JwksHandler(BaseHTTPRequestHandler):
    payload = b"{}"
    requests = 0

    def do_GET(self) -> None:  # noqa: N802 - stdlib HTTP handler contract
        type(self).requests += 1
        if self.path != "/jwks":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(type(self).payload)))
        self.end_headers()
        self.wfile.write(type(self).payload)

    def log_message(self, _format: str, *_args: object) -> None:
        return


@contextmanager
def _jwks_server(payload: dict[str, Any]) -> Any:
    JwksHandler.payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    JwksHandler.requests = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), JwksHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


async def echo_authorization(request: Request) -> JSONResponse:
    return JSONResponse({"authorization": request.headers.get("authorization")})


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _public_jwk(private_key: ec.EllipticCurvePrivateKey) -> dict[str, str]:
    numbers = private_key.public_key().public_numbers()
    return {
        "crv": "P-256",
        "kty": "EC",
        "x": _base64url(numbers.x.to_bytes(32, "big")),
        "y": _base64url(numbers.y.to_bytes(32, "big")),
    }


def _thumbprint(jwk: Mapping[str, str]) -> str:
    canonical = json.dumps(
        {name: jwk[name] for name in ("crv", "kty", "x", "y")},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return _base64url(hashlib.sha256(canonical).digest())


def _credentials(
    *,
    claims_update: Mapping[str, Any] | None = None,
    header_update: Mapping[str, Any] | None = None,
    token_confirmation: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    jwk: dict[str, Any] = _public_jwk(private_key)
    token = jwt.encode(
        {"sub": "agent-1", "cnf": token_confirmation or {"jkt": _thumbprint(jwk)}},
        "test-access-token-secret-with-at-least-32-bytes",
        algorithm="HS256",
    )
    claims: dict[str, Any] = {
        "jti": "proof-jti-0001",
        "htm": "POST",
        "htu": RESOURCE_URL,
        "iat": NOW,
        "ath": _base64url(hashlib.sha256(token.encode("ascii")).digest()),
    }
    claims.update(claims_update or {})
    headers: dict[str, Any] = {"typ": "dpop+jwt", "jwk": jwk}
    headers.update(header_update or {})
    proof = jwt.encode(claims, private_key, algorithm="ES256", headers=headers)
    return token, proof


def _client(
    token: str | None,
    store: MemoryReplayStore,
) -> tuple[httpx.AsyncClient, StaticTokenVerifier]:
    verifier = StaticTokenVerifier(token)
    proof_verifier = DpopProofVerifier(
        resource_url=RESOURCE_URL,
        replay_store=store,
        max_proof_age_seconds=120,
        clock_skew_seconds=30,
        now=lambda: float(NOW),
    )
    downstream = Starlette(routes=[Route("/mcp", echo_authorization, methods=["POST"])])
    app = DpopSenderConstraintMiddleware(
        downstream,
        token_verifier=verifier,
        proof_verifier=proof_verifier,
    )
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="https://mcp.example.test"), verifier


@pytest.mark.anyio
async def test_valid_dpop_proof_is_verified_once_and_forwarded_as_bearer() -> None:
    token, proof = _credentials()
    store = MemoryReplayStore()
    client, verifier = _client(token, store)

    async with client:
        response = await client.post("/mcp", headers={"Authorization": f"DPoP {token}", "DPoP": proof})

    assert response.status_code == 200
    assert response.json() == {"authorization": f"Bearer {token}"}
    assert verifier.calls == 1
    assert len(store.keys) == 1
    assert store.ttls == [150]
    assert store.closed is False


@pytest.mark.anyio
async def test_dpop_proof_replay_is_rejected_without_reaching_the_application() -> None:
    token, proof = _credentials()
    store = MemoryReplayStore()
    client, _ = _client(token, store)

    async with client:
        first = await client.post("/mcp", headers={"Authorization": f"DPoP {token}", "DPoP": proof})
        replay = await client.post("/mcp", headers={"Authorization": f"DPoP {token}", "DPoP": proof})

    assert first.status_code == 200
    assert replay.status_code == 401
    assert replay.json() == {"error": "invalid_dpop_proof"}
    assert replay.headers["www-authenticate"] == 'DPoP error="invalid_dpop_proof"'
    assert replay.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "claims_update",
    [
        {"htm": "GET"},
        {"htu": "https://mcp.example.test/other"},
        {"htu": "https://mcp.example.test/mcp?query=forbidden"},
        {"iat": NOW - 151},
        {"iat": NOW + 31},
        {"iat": True},
        {"jti": "short"},
        {"ath": "wrong-token-hash"},
    ],
)
@pytest.mark.anyio
async def test_invalid_dpop_claims_are_rejected(claims_update: Mapping[str, Any]) -> None:
    token, proof = _credentials(claims_update=claims_update)
    client, _ = _client(token, MemoryReplayStore())

    async with client:
        response = await client.post("/mcp", headers={"Authorization": f"DPoP {token}", "DPoP": proof})

    assert response.status_code == 401
    assert response.json() == {"error": "invalid_dpop_proof"}


@pytest.mark.anyio
async def test_dpop_rejects_bearer_missing_duplicate_and_private_key_headers() -> None:
    token, proof = _credentials()
    client, _ = _client(token, MemoryReplayStore())
    async with client:
        bearer = await client.post("/mcp", headers={"Authorization": f"Bearer {token}", "DPoP": proof})
        missing = await client.post("/mcp", headers={"Authorization": f"DPoP {token}"})
        duplicate = await client.post(
            "/mcp",
            headers=[("Authorization", f"DPoP {token}"), ("DPoP", proof), ("DPoP", proof)],
        )
        _, private_proof = _credentials(header_update={"jwk": {"kty": "oct", "k": "private"}})
        private_key = await client.post(
            "/mcp",
            headers={"Authorization": f"DPoP {token}", "DPoP": private_proof},
        )

    assert {bearer.status_code, missing.status_code, duplicate.status_code, private_key.status_code} == {401}


@pytest.mark.anyio
async def test_dpop_rejects_unbound_or_cryptographically_invalid_access_tokens_before_reservation() -> None:
    token, proof = _credentials(token_confirmation={"x5t#S256": "a" * 43})
    store = MemoryReplayStore()
    client, _ = _client("a-different-token", store)

    async with client:
        response = await client.post("/mcp", headers={"Authorization": f"DPoP {token}", "DPoP": proof})

    assert response.status_code == 401
    assert store.keys == set()


@pytest.mark.anyio
async def test_dpop_replay_store_failure_is_fail_closed_and_retryable() -> None:
    token, proof = _credentials()
    client, _ = _client(token, MemoryReplayStore(unavailable=True))

    async with client:
        response = await client.post("/mcp", headers={"Authorization": f"DPoP {token}", "DPoP": proof})

    assert response.status_code == 503
    assert response.json() == {"error": "sender_constraint_unavailable"}
    assert response.headers["retry-after"] == "1"


@pytest.mark.integration
@pytest.mark.anyio
async def test_valkey_replay_store_uses_an_atomic_shared_reservation() -> None:
    store = ValkeyDpopReplayStore("redis://127.0.0.1:6380/15")
    jti = f"integration-{uuid4()}"
    try:
        first = await store.reserve(key_thumbprint="a" * 43, jti=jti, ttl_seconds=30)
        replay = await store.reserve(key_thumbprint="a" * 43, jti=jti, ttl_seconds=30)
    finally:
        await store.aclose()

    assert first is True
    assert replay is False


@pytest.mark.integration
@pytest.mark.anyio
async def test_real_oidc_jwks_dpop_and_valkey_sender_constraint_chain() -> None:
    now = int(time.time())
    dpop_private_key = ec.generate_private_key(ec.SECP256R1())
    dpop_jwk = _public_jwk(dpop_private_key)
    issuer_private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    issuer_numbers = issuer_private_key.public_key().public_numbers()
    issuer_jwk = {
        "alg": "RS256",
        "e": _base64url(issuer_numbers.e.to_bytes((issuer_numbers.e.bit_length() + 7) // 8, "big")),
        "kid": "integration-issuer-key",
        "kty": "RSA",
        "n": _base64url(issuer_numbers.n.to_bytes((issuer_numbers.n.bit_length() + 7) // 8, "big")),
        "use": "sig",
    }
    with _jwks_server({"keys": [issuer_jwk]}) as issuer_url:
        token = jwt.encode(
            {
                "aud": "pharma-intelligence-mcp",
                "azp": "integration-client",
                "cnf": {"jkt": _thumbprint(dpop_jwk)},
                "exp": now + 300,
                "iat": now,
                "iss": issuer_url,
                "scope": "mcp:connect entities:read",
                "sub": "integration-agent",
                "tenant_id": "00000000-0000-0000-0000-000000000001",
            },
            issuer_private_key,
            algorithm="RS256",
            headers={"kid": issuer_jwk["kid"]},
        )
        proof = jwt.encode(
            {
                "ath": _base64url(hashlib.sha256(token.encode("ascii")).digest()),
                "htm": "POST",
                "htu": RESOURCE_URL,
                "iat": now,
                "jti": f"oidc-valkey-{uuid4()}",
            },
            dpop_private_key,
            algorithm="ES256",
            headers={"jwk": dpop_jwk, "typ": "dpop+jwt"},
        )
        settings = Settings(
            _env_file=None,
            internal_service_jwt_secret="integration-" + ("internal-" * 4),  # noqa: S106
            mcp_auth_issuer_url=issuer_url,
            mcp_oidc_audience="pharma-intelligence-mcp",
            mcp_oidc_jwks_url=f"{issuer_url}/jwks",
            mcp_require_token_confirmation=True,
            mcp_resource_server_url=RESOURCE_URL,
            mcp_correlation_hmac_secret="integration-" + ("correlation-" * 3),  # noqa: S106
        )
        store = ValkeyDpopReplayStore("redis://127.0.0.1:6380/14")
        proof_verifier = DpopProofVerifier(
            resource_url=RESOURCE_URL,
            replay_store=store,
            max_proof_age_seconds=120,
            clock_skew_seconds=30,
            now=lambda: float(now),
        )
        downstream = Starlette(routes=[Route("/mcp", echo_authorization, methods=["POST"])])
        app = DpopSenderConstraintMiddleware(
            downstream,
            token_verifier=OidcJwksTokenVerifier(settings),
            proof_verifier=proof_verifier,
        )
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="https://mcp.example.test",
            ) as client:
                accepted = await client.post(
                    "/mcp",
                    headers={"Authorization": f"DPoP {token}", "DPoP": proof},
                )
                replayed = await client.post(
                    "/mcp",
                    headers={"Authorization": f"DPoP {token}", "DPoP": proof},
                )
        finally:
            await store.aclose()

    assert accepted.status_code == 200
    assert accepted.json() == {"authorization": f"Bearer {token}"}
    assert replayed.status_code == 401
    assert JwksHandler.requests == 1
