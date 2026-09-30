from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from uuid import UUID

from pharma_intel.config import get_settings

DOMAIN = b"X-Pharma/internal-account-invitation/v1\x00"


@dataclass(frozen=True)
class VerifiedInvitationCode:
    tenant_id: str
    invitation_id: str
    digest: str


def _signature(payload: str) -> str:
    secret = get_settings().effective_tenant_context_signing_secret.encode()
    signature = hmac.new(secret, DOMAIN + payload.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")


def issue_invitation_code(tenant_id: str, invitation_id: str) -> str:
    payload = f"xphi1.{UUID(tenant_id)}.{UUID(invitation_id)}.{secrets.token_urlsafe(32)}"
    return f"{payload}.{_signature(payload)}"


def verify_invitation_code(code: str) -> VerifiedInvitationCode:
    if not 100 <= len(code) <= 256 or not code.isascii():
        raise ValueError("邀请码无效或已失效")
    pieces = code.split(".")
    if len(pieces) != 5 or pieces[0] != "xphi1":
        raise ValueError("邀请码无效或已失效")
    payload, _, signature = code.rpartition(".")
    if not hmac.compare_digest(signature, _signature(payload)):
        raise ValueError("邀请码无效或已失效")
    try:
        tenant_id, invitation_id = str(UUID(pieces[1])), str(UUID(pieces[2]))
    except ValueError as exc:
        raise ValueError("邀请码无效或已失效") from exc
    return VerifiedInvitationCode(tenant_id, invitation_id, hashlib.sha256(code.encode("ascii")).hexdigest())
