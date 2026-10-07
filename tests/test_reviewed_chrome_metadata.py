from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.reviewed_chrome_metadata import reviewed_metadata


def inputs() -> tuple[bytes, dict[str, object]]:
    root = Path(__file__).parents[1]
    return (root / "apps/web/e2e/visual-baselines/manifest.json").read_bytes(), json.loads(
        (root / "deploy/browser/reviewed-google-chrome.json").read_bytes()
    )


def test_reviewed_browser_artifact_has_one_version_authority_and_exact_integrity() -> None:
    reference, artifact = inputs()
    values = reviewed_metadata(reference, artifact)
    assert values[0].rsplit("-", 1)[0] == json.loads(reference)["browser"].removeprefix("Google Chrome ")
    assert values[3] == artifact["sha256"] and values[4] == artifact["executable_sha256"]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("filename", "../../outside.deb"),
        ("filename", "pool/main/g/google-chrome-stable/google-chrome-stable_0.0.0.0-1_amd64.deb"),
        ("size_bytes", True),
        ("size_bytes", 500_000_001),
        ("sha256", "not-a-digest"),
        ("executable_sha256", ""),
        ("visual_manifest_sha256", "0" * 64),
        ("license_url", "https://example.invalid/"),
    ],
)
def test_reviewed_artifact_rejects_drift_traversal_and_invalid_integrity(key: str, value: object) -> None:
    reference, artifact = inputs()
    artifact[key] = value
    with pytest.raises(ValueError):
        reviewed_metadata(reference, artifact)


def test_unreviewed_profile_and_unknown_artifact_fields_fail_closed() -> None:
    reference, artifact = inputs()
    with pytest.raises(ValueError, match="bound"):
        reviewed_metadata(reference + b"\n", artifact)
    artifact["automatic_latest_fallback"] = True
    with pytest.raises(ValueError, match="schema"):
        reviewed_metadata(reference, artifact)
