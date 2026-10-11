from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts import browser_phase_cli
from scripts.browser_cases import mapping
from scripts.browser_phase_runtime import load, save
from scripts.browser_phases import CONTROLLED_FILES, create_manifest, verify_results
from tests.test_browser_phases import report


def evidence() -> tuple[dict[str, object], dict[str, object]]:
    manifest = create_manifest(report(set(CONTROLLED_FILES) | {"workspace.spec.ts"}), "a" * 40)
    stack: dict[str, object] = {
        "schema": "pharma.browser-acceptance.v9",
        "status": "passed",
        "browser": {"product": "Google Chrome", "version": "155.0.8059.39"},
        "tests": {"total": 4, "failed": 0},
        "performance": {"original": "unchanged real-stack budget evidence"},
        "visual_regression": {"max_diff_pixel_ratio": 0.001},
        "phase_manifest": manifest,
        "case_coverage": verify_results(manifest, report({"workspace.spec.ts"}, executed=True), "full-stack"),
    }
    controlled: dict[str, object] = {
        "schema": "x-pharma.controlled-browser-acceptance.v1",
        "status": "passed",
        "real_backend": False,
        "browser": "Google Chrome 155.0.8059.39",
        "phase_manifest": manifest,
        "case_coverage": verify_results(manifest, report(set(CONTROLLED_FILES), executed=True), "controlled"),
    }
    return stack, controlled


def test_closure_keeps_original_performance_and_visual_evidence_and_complete_case_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stack, controlled = evidence()
    save(tmp_path / "stack.json", stack)
    save(tmp_path / "controlled.json", controlled)
    monkeypatch.setattr(browser_phase_cli, "source_revision", lambda: "a" * 40)
    browser_phase_cli.close(tmp_path / "stack.json", tmp_path / "controlled.json", tmp_path / "complete.json")
    result = load(tmp_path / "complete.json")
    assert result["performance"] == stack["performance"]
    assert result["visual_regression"] == stack["visual_regression"]
    assert result["tests"] == {
        "total": 36,
        "failed": 0,
        "desktop_1440": 9,
        "desktop_1920": 9,
        "tablet_1024": 9,
        "mobile_390": 9,
    }


@pytest.mark.parametrize("change", ["browser", "source", "missing-case", "failed", "backend"])
def test_closure_fails_before_emitting_incomplete_or_mismatched_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    stack, controlled = evidence()
    invalid = deepcopy(controlled)
    if change == "browser":
        invalid["browser"] = "Google Chrome 154.0.8037.97"
    elif change == "source":
        invalid["phase_manifest"] = {}
    elif change == "missing-case":
        invalid["case_coverage"] = {}
    elif change == "failed":
        invalid["status"] = "failed"
    else:
        invalid["real_backend"] = True
    save(tmp_path / "stack.json", stack)
    save(tmp_path / "controlled.json", invalid)
    monkeypatch.setattr(browser_phase_cli, "source_revision", lambda: "a" * 40)
    with pytest.raises(ValueError):
        browser_phase_cli.close(tmp_path / "stack.json", tmp_path / "controlled.json", tmp_path / "complete.json")
    assert not (tmp_path / "complete.json").exists()


def test_browser_evidence_refuses_overwriting_or_following_existing_symlinks(tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    save(output, {"status": "original"})
    with pytest.raises(FileExistsError):
        save(output, {"status": "replacement"})
    assert load(output) == {"status": "original"}
    alias = tmp_path / "alias.json"
    alias.symlink_to(output)
    with pytest.raises(ValueError):
        load(alias)


@pytest.mark.parametrize("change", ["none", "source", "count", "result"])
def test_attachment_verifies_actual_execution_before_preserving_the_original_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    stack, _ = evidence()
    actual = report({"workspace.spec.ts"}, executed=True)
    if change == "count":
        stack["tests"] = {"total": 3}
    elif change == "result":
        actual = report({"unexecuted.spec.ts"}, executed=True)
    save(tmp_path / "manifest.json", mapping(stack["phase_manifest"]))
    save(tmp_path / "results.json", actual)
    save(tmp_path / "stack.json", stack)
    monkeypatch.setattr(browser_phase_cli, "source_revision", lambda: ("b" if change == "source" else "a") * 40)
    if change == "none":
        browser_phase_cli.attach(
            tmp_path / "manifest.json", tmp_path / "results.json", tmp_path / "stack.json", "full-stack"
        )
        assert load(tmp_path / "stack-verified.json")["case_coverage"] == stack["case_coverage"]
    else:
        with pytest.raises(ValueError):
            browser_phase_cli.attach(
                tmp_path / "manifest.json", tmp_path / "results.json", tmp_path / "stack.json", "full-stack"
            )
        assert not (tmp_path / "stack-verified.json").exists()
    assert load(tmp_path / "stack.json") == stack
