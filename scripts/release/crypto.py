from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from scripts.release.contracts.core import SHA256_PATTERN, SIGNATURE_SCHEMA
from scripts.release.contracts.production import PRODUCTION_HANDOFF_SIGNATURE_FIELDS
from scripts.release.io import _load_json_object, _sha256_bytes
from scripts.release.records import ReleaseEvidenceError


def _load_signing_key(path: Path) -> Ed25519PrivateKey:
    if path.is_symlink() or not path.is_file():
        raise ReleaseEvidenceError("release signing key must be a regular PEM file")
    if path.stat().st_mode & 0o077:
        raise ReleaseEvidenceError("release signing key permissions must not allow group or other access")
    password_text = os.environ.get("RELEASE_SIGNING_KEY_PASSWORD")
    password = password_text.encode() if password_text else None
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=password)
    except (OSError, ValueError, TypeError) as exc:
        raise ReleaseEvidenceError("cannot load release signing key") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ReleaseEvidenceError("release signing key must use Ed25519")
    return key


def _load_public_key(path: Path) -> Ed25519PublicKey:
    if path.is_symlink() or not path.is_file():
        raise ReleaseEvidenceError("trusted release public key must be a regular PEM file")
    try:
        key = serialization.load_pem_public_key(path.read_bytes())
    except (OSError, ValueError, TypeError) as exc:
        raise ReleaseEvidenceError("cannot load trusted release public key") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise ReleaseEvidenceError("trusted release public key must use Ed25519")
    return key


def _public_key_fingerprint(key: Ed25519PublicKey) -> str:
    encoded = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return _sha256_bytes(encoded)


def _verify_production_handoff_signature(
    *,
    root: Path,
    manifest: dict[str, Any],
    trusted_public_key: Path | None,
) -> bool:
    metadata = manifest.get("signature")
    if not isinstance(metadata, dict) or set(metadata) != PRODUCTION_HANDOFF_SIGNATURE_FIELDS:
        raise ReleaseEvidenceError("production handoff signature metadata is invalid")
    present = metadata.get("present")
    key_id = metadata.get("key_id")
    fingerprint = metadata.get("public_key_sha256")
    signature_path = root / "handoff-manifest.sig.json"
    if not isinstance(present, bool) or present != signature_path.is_file():
        raise ReleaseEvidenceError("production handoff signature presence differs from its manifest")
    if not present:
        if key_id is not None or fingerprint is not None:
            raise ReleaseEvidenceError("unsigned production handoff contains signing metadata")
        return False
    if (
        not isinstance(key_id, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{2,127}", key_id) is None
        or not isinstance(fingerprint, str)
        or SHA256_PATTERN.fullmatch(fingerprint) is None
    ):
        raise ReleaseEvidenceError("production handoff signature metadata is invalid")
    if trusted_public_key is None:
        raise ReleaseEvidenceError("a trusted Ed25519 public key is required to verify this handoff")
    trusted_key = _load_public_key(trusted_public_key)
    signature_document = _load_json_object(signature_path, "production handoff signature")
    manifest_payload = (root / "handoff-manifest.json").read_bytes()
    if (
        signature_document.get("schema") != SIGNATURE_SCHEMA
        or signature_document.get("schema_version") != 1
        or signature_document.get("algorithm") != "Ed25519"
        or signature_document.get("key_id") != key_id
        or signature_document.get("public_key_sha256") != fingerprint
        or fingerprint != _public_key_fingerprint(trusted_key)
        or signature_document.get("manifest_sha256") != _sha256_bytes(manifest_payload)
    ):
        raise ReleaseEvidenceError("production handoff signature metadata is invalid")
    encoded_signature = signature_document.get("signature")
    if not isinstance(encoded_signature, str):
        raise ReleaseEvidenceError("production handoff signature is invalid")
    try:
        trusted_key.verify(base64.b64decode(encoded_signature, validate=True), manifest_payload)
    except (ValueError, InvalidSignature) as exc:
        raise ReleaseEvidenceError("production handoff signature verification failed") from exc
    return True
