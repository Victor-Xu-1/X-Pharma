from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.release.version_manifest import advance_version, update_manifests


@pytest.mark.parametrize(
    ("before", "count", "after"),
    [
        ("0.1.0", 1, "0.1.1"),
        ("0.1.98", 1, "0.1.99"),
        ("0.1.99", 1, "0.2.0"),
        ("0.9.99", 1, "1.0.0"),
        ("1.9.99", 1, "2.0.0"),
        ("0.1.99", 101, "0.3.0"),
        ("0.9.98", 1002, "2.0.0"),
        ("0.1.0", 0, "0.1.0"),
    ],
)
def test_merged_pr_counter_carries_at_100_and_10(before: str, count: int, after: str) -> None:
    assert advance_version(before, count) == after


@pytest.mark.parametrize("version", ["v0.1.0", "0.10.0", "0.1.100", "00.1.0", "0.1.0-dev", "-1.1.0"])
def test_invalid_product_counter_versions_are_rejected(version: str) -> None:
    with pytest.raises(ValueError, match="version"):
        advance_version(version, 1)


@pytest.mark.parametrize("count", [-1, True, 1.5])
def test_invalid_merge_counts_are_rejected(count: int) -> None:
    with pytest.raises(ValueError, match="count"):
        advance_version("0.1.0", count)


def manifest_fixture(root: Path) -> None:
    (root / "apps/web").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "X-Pharma"\nversion = "0.1.99"\n'
        '[tool.x-pharma.versioning]\nprocessed-through = "' + "a" * 40 + '"\n',
    )
    (root / "apps/web/package.json").write_text(
        json.dumps({"name": "x-pharma-workspace", "version": "0.1.99", "dependencies": {"example": "9.8.7"}}),
    )


def test_increment_updates_only_product_manifests_and_the_processed_cursor(tmp_path: Path) -> None:
    manifest_fixture(tmp_path)
    assert update_manifests(tmp_path, "b" * 40, 1) == "0.2.0"
    assert 'version = "0.2.0"' in (tmp_path / "pyproject.toml").read_text()
    assert 'processed-through = "' + "b" * 40 + '"' in (tmp_path / "pyproject.toml").read_text()
    web = json.loads((tmp_path / "apps/web/package.json").read_text())
    assert web["version"] == "0.2.0"
    assert web["dependencies"] == {"example": "9.8.7"}


def test_no_pending_pr_does_not_change_the_version_or_cursor(tmp_path: Path) -> None:
    manifest_fixture(tmp_path)
    before = (tmp_path / "pyproject.toml").read_bytes()
    assert update_manifests(tmp_path, "b" * 40, 0) == "0.1.99"
    assert (tmp_path / "pyproject.toml").read_bytes() == before


def test_manifest_drift_fails_before_any_write(tmp_path: Path) -> None:
    manifest_fixture(tmp_path)
    web_path = tmp_path / "apps/web/package.json"
    web_path.write_text('{"version":"0.1.0"}')
    before = (tmp_path / "pyproject.toml").read_bytes()
    with pytest.raises(ValueError, match="mirror"):
        update_manifests(tmp_path, "b" * 40, 1)
    assert (tmp_path / "pyproject.toml").read_bytes() == before


def test_invalid_cursor_fails_before_any_write(tmp_path: Path) -> None:
    manifest_fixture(tmp_path)
    before = (tmp_path / "pyproject.toml").read_bytes()
    with pytest.raises(ValueError, match="revision"):
        update_manifests(tmp_path, "main; injected", 1)
    assert (tmp_path / "pyproject.toml").read_bytes() == before


@pytest.mark.parametrize(
    "document",
    [
        "GOAL.md",
        "docs/research-workflow-integrity.md",
        "docs/automatic-public-source-ingestion.md",
        "docs/completion-gap-checklist.md",
        "docs/formal-acceptance-inputs.md",
        "docs/researcher-experience-review.md",
        "docs/security-gates.md",
        "docs/public-research.md",
    ],
)
def test_evergreen_product_documents_defer_to_the_single_version_authority(document: str) -> None:
    text = (Path(__file__).resolve().parents[1] / document).read_text()
    relative_manifest = "pyproject.toml" if document == "GOAL.md" else "../pyproject.toml"
    assert re.search(r"\bX-Pharma(?:'s)?\s+v[0-9]+\.[0-9]+\.[0-9]+(?![0-9.])", text) is None
    assert "软件版本仍为v" not in text
    assert f"]({relative_manifest})" in text


@pytest.mark.parametrize(
    "document",
    ["docs/release-evidence.md", "docs/design-qa.md", "docs/visual-baseline-reviews.md"],
)
def test_dated_version_evidence_keeps_its_original_version_separate_from_current_authority(document: str) -> None:
    text = (Path(__file__).resolve().parents[1] / document).read_text()
    introduction = "\n".join(text.splitlines()[:10])
    assert "](../pyproject.toml)" in introduction
    assert "v0.1.0" in text
