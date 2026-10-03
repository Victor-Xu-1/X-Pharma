from __future__ import annotations

import json
import secrets
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.accounts.contracts import InvitationCreate
from pharma_intel.accounts.identity import create_account
from pharma_intel.accounts.service import AccountRegistrationService
from pharma_intel.api import app
from pharma_intel.config import get_settings
from pharma_intel.db import get_session
from pharma_intel.human_oidc import OIDC_TRANSACTION_COOKIE, read_oidc_transaction
from pharma_intel.models import AccountInvitation, OrganizationMembership, Tenant, UserRole
from pharma_intel.security import Principal
from tests.test_human_oidc import _id_token, _signing_material


@pytest.mark.parametrize("identity", ["verified", "unverified", "different_email", "different_tenant_claim"])
def test_real_oidc_http_code_pkce_jwks_invitation_transaction_requires_verified_linked_identity(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
    identity: str,
) -> None:
    """A real loopback IdP protocol, RSA parser and database; no HTTP mock."""
    import jwt

    key, jwk = _signing_material()
    transaction: dict[str, str] = {}
    calls: list[str] = []
    settings = None

    class Authority(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *args: object) -> None:
            # The test authority never logs authorization codes or PKCE secrets.
            return

        def send_json(self, status: int, body: object) -> None:
            encoded = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            if self.path == "/jwks":
                calls.append("jwks")
                self.send_json(200, {"keys": [jwk]})
            else:
                self.send_json(404, {})

        def do_POST(self) -> None:
            declared = int(self.headers.get("Content-Length", "0"))
            if self.path != "/token" or not 0 < declared <= 8192:
                self.send_json(400, {})
                return
            form = parse_qs(self.rfile.read(declared).decode())
            if (
                settings is None
                or "token" in calls
                or form.get("code") != ["one-use-authority-code"]
                or form.get("code_verifier") != [transaction["code_verifier"]]
                or form.get("redirect_uri") != [settings.human_oidc_redirect_uri]
                or form.get("grant_type") != ["authorization_code"]
            ):
                self.send_json(400, {})
                return
            calls.append("token")
            token = _id_token(key, settings, tenant.id, transaction["nonce"])
            if identity != "verified":
                # Alter the authority-issued claims, then sign with the same real key.
                claims = jwt.decode(token, options={"verify_signature": False})
                claims["email_verified"] = identity != "unverified"
                if identity == "different_email":
                    claims["email"] = "someone-else@example.test"
                if identity == "different_tenant_claim":
                    claims["tenant_id"] = "not-an-authorized-organization"
                token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": jwk["kid"]})
            self.send_json(200, {"id_token": token, "token_type": "Bearer"})

    authority = ThreadingHTTPServer(("127.0.0.1", 0), Authority)
    thread = threading.Thread(target=authority.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{authority.server_port}"
    for name, value in {
        "HUMAN_AUTH_MODE": "oidc",
        "JWT_SECRET": secrets.token_urlsafe(32),
        "HUMAN_OIDC_ISSUER_URL": root,
        "HUMAN_OIDC_AUTHORIZATION_URL": root + "/authorize",
        "HUMAN_OIDC_TOKEN_URL": root + "/token",
        "HUMAN_OIDC_JWKS_URL": root + "/jwks",
        "HUMAN_OIDC_CLIENT_ID": "controlled-local-authority",
        "HUMAN_OIDC_CLIENT_SECRET": "",
        "HUMAN_OIDC_REDIRECT_URI": "http://testserver/api/v1/auth/oidc/callback",
        "PUBLIC_BASE_URL": "http://testserver",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    settings = get_settings()
    other = Tenant(slug=f"oidc-invitation-{identity}", name="OIDC invitation target")
    session.add(other)
    session.flush()
    account = create_account(
        tenant_id=tenant.id,
        email="oidc.user@example.test",
        normalized_email="oidc.user@example.test",
        display_name="Linked identity",
        password_hash=secrets.token_urlsafe(32),
        role=UserRole.VIEWER,
        oidc_issuer=root,
        oidc_subject="subject-123",
        active=False,
    )
    sponsor = create_account(
        tenant_id=other.id,
        email="sponsor@example.test",
        normalized_email="sponsor@example.test",
        display_name="Sponsor",
        password_hash=secrets.token_urlsafe(32),
        role=UserRole.ADMIN,
    )
    session.add_all([account, sponsor])
    session.commit()
    issued = AccountRegistrationService(session, "real-oidc-invitation").issue_invitation(
        Principal(other.id, sponsor.id, "user", frozenset()),
        InvitationCreate(email=account.email),
    )

    def override(request: Request) -> Generator[Session]:
        request.state.db_session = session
        yield session

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            rejected = client.post(
                "/api/v1/auth/oidc/invitation", json={"invitation_code": issued.code, "confirmed": False}
            )
            assert rejected.status_code == 422
            start = client.post(
                "/api/v1/auth/oidc/invitation", json={"invitation_code": issued.code, "confirmed": True}
            )
            assert start.status_code == 200, start.text
            assert issued.code not in start.text
            assert "HttpOnly" in start.headers["set-cookie"]
            state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]
            transaction.update(read_oidc_transaction(settings, client.cookies[OIDC_TRANSACTION_COOKIE], state))
            callback = client.get(
                "/api/v1/auth/oidc/callback",
                params={"code": "one-use-authority-code", "state": state},
                follow_redirects=False,
            )
            accepted = identity in {"verified", "different_tenant_claim"}
            assert callback.status_code == (302 if accepted else 401), callback.text
            assert calls == ["token", "jwks"]
            member = session.get(OrganizationMembership, (other.id, account.id))
            invitation = session.get(AccountInvitation, issued.invitation.id)
            assert invitation is not None
            if accepted:
                assert member is not None and member.role == UserRole.ANALYST
                me = client.get("/api/v1/auth/me")
                assert me.status_code == 200 and me.json()["tenant_id"] == other.id and me.json()["id"] == account.id
                assert invitation.claimed_user_id == account.id
            else:
                assert member is None and invitation.claimed_at is None
            assert account.home_tenant_id == tenant.id and not account.memberships[0].active
    finally:
        app.dependency_overrides.pop(get_session, None)
        authority.shutdown()
        authority.server_close()
        thread.join(timeout=5)
