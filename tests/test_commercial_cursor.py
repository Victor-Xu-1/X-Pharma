from __future__ import annotations

from dataclasses import replace

import pytest

from pharma_intel.commercial.cursor import CursorError, SignedCursorCodec, query_fingerprint
from pharma_intel.security import Principal

BASE64URL_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
SECRET = "cursor-test-secret-that-is-longer-than-thirty-two-bytes"  # noqa: S105


def _principal() -> Principal:
    return Principal(
        tenant_id="tenant-1",
        actor_id="subject-1",
        actor_type="agent",
        scopes=frozenset({"mcp:connect"}),
        client_id="client-1",
    )


def test_signed_cursor_round_trip_binds_every_commercial_dimension() -> None:
    codec = SignedCursorCodec(SECRET, ttl_seconds=300)
    principal = _principal()
    fingerprint = query_fingerprint("entity.search", {"q": "EGFR", "limit": 20}, 20)

    token = codec.issue(
        principal,
        tool="entity.search",
        query_sha256=fingerprint,
        page_size=20,
        offset=20,
        depth=2,
        now_epoch=100,
    )
    claims = codec.verify(
        token,
        principal,
        tool="entity.search",
        query_sha256=fingerprint,
        page_size=20,
        now_epoch=399,
    )

    assert claims.offset == 20
    assert claims.depth == 2
    assert claims.client_id == "client-1"
    assert claims.expires_at == 400

    mismatches = (
        (replace(principal, tenant_id="tenant-2"), "entity.search", fingerprint, 20),
        (replace(principal, actor_id="subject-2"), "entity.search", fingerprint, 20),
        (replace(principal, client_id="client-2"), "entity.search", fingerprint, 20),
        (principal, "entity.resolve", fingerprint, 20),
        (principal, "entity.search", "f" * 64, 20),
        (principal, "entity.search", fingerprint, 10),
    )
    for candidate, tool, query_sha256, page_size in mismatches:
        with pytest.raises(CursorError, match="invalid or expired"):
            codec.verify(
                token,
                candidate,
                tool=tool,
                query_sha256=query_sha256,
                page_size=page_size,
                now_epoch=200,
            )


def test_signed_cursor_rejects_tampering_expiry_and_invalid_inputs() -> None:
    codec = SignedCursorCodec(SECRET, ttl_seconds=30)
    principal = _principal()
    fingerprint = query_fingerprint("entity.search", {"q": "EGFR", "limit": 5}, 5)
    token = codec.issue(
        principal,
        tool="entity.search",
        query_sha256=fingerprint,
        page_size=5,
        offset=5,
        depth=2,
        now_epoch=100,
    )

    encoded_body, encoded_signature = token.split(".", 1)
    last_index = BASE64URL_ALPHABET.index(encoded_signature[-1])
    assert last_index % 4 == 0
    noncanonical_alias = BASE64URL_ALPHABET[last_index + 1]
    tampered_token = f"{encoded_body}.{encoded_signature[:-1]}{noncanonical_alias}"

    with pytest.raises(CursorError, match="invalid or expired"):
        codec.verify(
            tampered_token,
            principal,
            tool="entity.search",
            query_sha256=fingerprint,
            page_size=5,
            now_epoch=101,
        )
    with pytest.raises(CursorError, match="invalid or expired"):
        codec.verify(
            token,
            principal,
            tool="entity.search",
            query_sha256=fingerprint,
            page_size=5,
            now_epoch=130,
        )
    with pytest.raises(ValueError, match="at least 32 bytes"):
        SignedCursorCodec("too-short")
    with pytest.raises(CursorError, match="chain identity"):
        codec.issue(
            principal,
            tool="entity.search",
            query_sha256=fingerprint,
            page_size=5,
            offset=5,
            depth=2,
            chain_id="not-a-uuid",
        )


def test_query_fingerprint_excludes_only_cursor_and_is_canonical() -> None:
    first = query_fingerprint(
        "entity.search",
        {"q": "EGFR", "limit": 10, "cursor": "old-token", "entity_type": "target"},
        10,
    )
    second = query_fingerprint(
        "entity.search",
        {"entity_type": "target", "limit": 10, "cursor": "new-token", "q": "EGFR"},
        10,
    )

    assert first == second
    assert first != query_fingerprint("entity.search", {"q": "KRAS", "limit": 10}, 10)
