from __future__ import annotations

import ast
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from scripts.browser_cases import PROJECTS
from scripts.browser_snapshot_review import CAPTURE_FILES, CAPTURE_MARKERS, capture_scenarios

ROOT = Path(__file__).parents[1]
RUNNER = ROOT / "scripts/run-browser-acceptance.sh"


def test_review_keeps_the_full_readonly_pass_and_original_ci_budgets() -> None:
    workflow = cast(dict[str, Any], yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text()))
    jobs = workflow["jobs"]
    assert set(jobs) == {
        "backend",
        "frontend",
        "postgres-contract",
        "deployment-contract",
        "two-entry-smoke",
        "security-supply-chain",
        "company-controlled",
    }
    job = jobs["two-entry-smoke"]
    assert job["timeout-minutes"] == "${{ inputs.refresh_visual_baselines && 60 || 45 }}"
    steps = job["steps"]
    producer = next(step for step in steps if step.get("id") == "snapshot_generation")
    archive = next(step for step in steps if step.get("name") == "Archive visual baseline candidates for review")
    readonly = next(step for step in steps if step.get("id") == "workbench_smoke")
    assert producer["run"] == "./scripts/run-browser-acceptance.sh --update-snapshots"
    assert producer["if"] == "${{ github.event_name == 'workflow_dispatch' && inputs.refresh_visual_baselines }}"
    assert steps.index(producer) < steps.index(archive) < steps.index(readonly)
    assert "steps.snapshot_generation.outcome == 'success'" in archive["if"]
    assert archive["with"]["if-no-files-found"] == "error"
    assert "--update-snapshots" not in readonly["run"]
    assert "./scripts/run-browser-acceptance.sh --output /tmp/browser-acceptance-report.json" in readonly["run"]  # noqa: S108 - Existing CI report path, never opened here.
    assert (
        "./scripts/run-browser-acceptance.sh --phase full-stack --output /tmp/full-stack-browser-acceptance-report.json"
        in readonly["run"]
    )  # noqa: S108 - Existing CI report path, never opened here.
    assert not readonly.get("continue-on-error", False)
    assert "Require exact disjoint complete original browser coverage" in {step.get("name") for step in steps}


def test_capture_selection_is_reserved_for_explicit_updates_and_cannot_emit_release_evidence() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    preparation = source.split("fixture_ids_path=", maxsplit=1)[0]
    assert 'elif [[ "$update_snapshots" == true ]]; then' in preparation
    assert "python3 -m scripts.browser_snapshot_cli prepare" in preparation
    assert "snapshot_review_arguments=()" in preparation
    assert 'if [[ "$update_snapshots" == true && -n "$output_path" ]]' in source
    assert "--update-snapshots cannot be combined with --output" in source
    assert "python3 -m scripts.browser_snapshot_cli verify" in source
    assert source.index("python3 -m scripts.browser_snapshot_cli verify") < source.index("\nsync_updated_snapshots\n")
    assert "verify_fresh_captures(source_dir, expected" in source
    assert "verify_fresh_captures(baseline_dir, set(expected)" in source
    assert '"--workers=$browser_workers"' in source
    assert "browser_workers=${PHARMA_BROWSER_WORKERS:-4}" in source
    config = (ROOT / "apps/web/playwright.config.ts").read_text(encoding="utf-8")
    assert "retries: 0" in config
    assert ': "{testDir}/visual-baselines/{arg}-{projectName}{ext}"' in config
    assert "snapshotReviewMode" in config and "isAbsolute(snapshotReviewDirectory)" in config


def test_capture_policy_remains_in_the_original_format_lint_and_strict_type_gates() -> None:
    workflow = cast(dict[str, Any], yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text()))
    steps = workflow["jobs"]["backend"]["steps"]
    lint = next(step["run"] for step in steps if step.get("name") == "Lint and format gate")
    strict = next(step["run"] for step in steps if step.get("name") == "Strict typing gate")
    for filename in ("scripts/browser_snapshot_review.py", "scripts/browser_snapshot_cli.py"):
        assert all(filename in command for command in lint.splitlines())
        assert filename in strict


def test_capture_summary_accepts_the_actual_unchanged_runner_scenario_registry() -> None:
    match = re.search(r"^scenario_markers = (\{.*?^\})", RUNNER.read_text(), re.MULTILINE | re.DOTALL)
    assert match is not None
    scenarios = cast(dict[str, str], ast.literal_eval(match.group(1)))
    before = scenarios.copy()
    assert CAPTURE_MARKERS - set(scenarios.values()) == {"[global-search-landscape]"}
    expected = {name: marker for name, marker in scenarios.items() if marker in CAPTURE_MARKERS}
    assert len(expected) == 8
    assert capture_scenarios(scenarios) == expected
    assert scenarios == before


def test_every_original_screenshot_still_belongs_to_the_same_capture_inventory() -> None:
    directory = ROOT / "apps/web/e2e/workspace/navigation"
    names = set()
    for filename in (
        "login-and-appearance.ts",
        "dense-results-visual.ts",
        "clinical-query-and-results.ts",
        "news-deal-and-patent-details.ts",
    ):
        names.update(re.findall(r'toHaveScreenshot\(\s*"([a-z-]+)\.png"', (directory / filename).read_text()))
    assert len(names) == 5
    assert {f"{name}-{project}.png" for name in names for project in PROJECTS} == CAPTURE_FILES


@pytest.mark.parametrize("mode", ["false", "true"])
def test_capture_redirect_is_child_scoped_and_never_leaks_to_the_readonly_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    bash = shutil.which("bash")
    assert bash is not None
    match = re.search(r"run_playwright\(\) \(\n.*?\n\)\nsync_updated_snapshots", RUNNER.read_text(), re.DOTALL)
    assert match is not None
    function = match.group().removesuffix("\nsync_updated_snapshots")
    command = tmp_path / "browser-argv-probe"
    command.write_text(
        '#!/bin/sh\nprintf \'%s|%s\\n\' "${E2E_SNAPSHOT_REVIEW_MODE:-unset}" "${E2E_SNAPSHOT_REVIEW_DIR:-unset}"\n',
        encoding="utf-8",
    )
    command.chmod(0o755)
    for name in ("E2E_SNAPSHOT_REVIEW_MODE", "E2E_SNAPSHOT_REVIEW_DIR", "MSYSTEM"):
        monkeypatch.delenv(name, raising=False)
    program = (
        "set -euo pipefail; update_snapshots=$1; snapshot_review_state_dir=$2; "
        "E2E_PLAYWRIGHT_COMMAND=$3; E2E_PLAYWRIGHT_WORKDIR=$2; playwright_args=()\n"
        + function
        + "\nrun_playwright\n"
        + "printf 'parent=%s|%s\\n' "
        + '"${E2E_SNAPSHOT_REVIEW_MODE:-unset}" "${E2E_SNAPSHOT_REVIEW_DIR:-unset}"\n'
    )
    result = subprocess.run(  # noqa: S603 - The exact owned function is exercised with a local argv probe only.
        [bash, "-c", program, "snapshot-scope", mode, str(tmp_path), str(command)],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    expected = f"capture|{tmp_path}/snapshots" if mode == "true" else "unset|unset"
    assert result.stdout.splitlines() == [expected, "parent=unset|unset"]


@pytest.mark.parametrize("name", ["E2E_SNAPSHOT_REVIEW_DIR", "E2E_SNAPSHOT_REVIEW_MODE"])
def test_ordinary_runner_rejects_a_caller_supplied_snapshot_redirect_before_runtime_setup(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    bash = shutil.which("bash")
    assert bash is not None
    monkeypatch.setenv(name, "not-an-owned-review")
    result = subprocess.run(  # noqa: S603 - The actual CLI must fail before any runtime setup.
        [bash, str(RUNNER)],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert result.returncode == 2
    assert "reserved for the owned capture producer" in result.stderr


def test_readonly_pixel_and_behavior_assertions_are_not_relaxed() -> None:
    directory = ROOT / "apps/web/e2e/workspace/navigation"
    for filename in (
        "login-and-appearance.ts",
        "dense-results-visual.ts",
        "clinical-query-and-results.ts",
        "news-deal-and-patent-details.ts",
    ):
        source = (directory / filename).read_text()
        assert "maxDiffPixelRatio: 0.001" in source
