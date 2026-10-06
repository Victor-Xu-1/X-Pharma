"""Bind an official frozen Chrome artifact to the sole reviewed visual manifest."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import cast


def reviewed_metadata(reference: bytes, artifact: dict[str, object]) -> list[str]:
    expected_fields = {
        "schema",
        "visual_manifest_sha256",
        "filename",
        "size_bytes",
        "sha256",
        "executable_sha256",
        "license_url",
        "provenance",
    }
    if set(artifact) != expected_fields or artifact["schema"] != "pharma.reviewed-chrome-artifact.v1":
        raise ValueError("Invalid reviewed Chrome artifact schema")
    if hashlib.sha256(reference).hexdigest() != artifact["visual_manifest_sha256"]:
        raise ValueError("Chrome artifact is not bound to the current reviewed visual manifest")
    reference_data = json.loads(reference)
    if not isinstance(reference_data, dict):
        raise ValueError("Invalid reviewed Chrome visual manifest")
    browser = reference_data.get("browser")
    if not isinstance(browser, str) or re.fullmatch(r"Google Chrome [0-9]+(?:\.[0-9]+){3}", browser) is None:
        raise ValueError("Invalid reviewed Chrome product/version")
    version = browser.removeprefix("Google Chrome ")
    filename = artifact["filename"]
    expected = rf"pool/main/g/google-chrome-stable/google-chrome-stable_{re.escape(version)}-([1-9][0-9]*)_amd64\.deb"
    if not isinstance(filename, str) or (match := re.fullmatch(expected, filename)) is None:
        raise ValueError("Reviewed Chrome path, architecture or version differs from the visual manifest")
    size = artifact["size_bytes"]
    if isinstance(size, bool) or not isinstance(size, int) or not 10_000_000 <= size <= 500_000_000:
        raise ValueError("Invalid reviewed Chrome artifact size")
    for key in ("sha256", "executable_sha256"):
        value = artifact[key]
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("Invalid reviewed Chrome digest")
    if artifact["license_url"] != "https://www.google.com/chrome/terms/":
        raise ValueError("Reviewed Chrome license reference differs from the declared vendor")
    provenance = artifact["provenance"]
    if not isinstance(provenance, str) or not 1 <= len(provenance) <= 500:
        raise ValueError("Invalid reviewed Chrome provenance")
    return [
        f"{version}-{match[1]}",
        filename,
        str(size),
        cast(str, artifact["sha256"]),
        cast(str, artifact["executable_sha256"]),
    ]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    reference_path = root / "apps/web/e2e/visual-baselines/manifest.json"
    artifact_path = root / "deploy/browser/reviewed-google-chrome.json"
    for path, limit in ((reference_path, 1024 * 1024), (artifact_path, 16 * 1024)):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise ValueError("Unsafe or oversized reviewed Chrome manifest")
    reference = reference_path.read_bytes()
    values = reviewed_metadata(reference, json.loads(artifact_path.read_bytes()))
    print("\n".join(values))


if __name__ == "__main__":
    main()
