from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).parents[1]


def test_full_stack_browser_ci_serializes_quality_measurements_but_keeps_mcp_concurrency() -> None:
    workflow = cast(dict[str, Any], yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")))
    job = workflow["jobs"]["two-entry-smoke"]
    assert job["env"]["PHARMA_BROWSER_WORKERS"] == "1"
    steps = {step.get("name"): step for step in job["steps"]}
    assert (
        "./scripts/run-browser-acceptance.sh --output /tmp/browser-acceptance-report.json"
        in steps["Browser workbench smoke"]["run"]
    )
    assert "--requests 20 --concurrency 4" in steps["Billed MCP concurrency baseline"]["run"]
    assert "--max-p95-ms 10000" in steps["Billed MCP concurrency baseline"]["run"]


def test_browser_runner_keeps_configurable_parallelism_viewports_and_complete_coverage_guard() -> None:
    runner = (ROOT / "scripts/run-browser-acceptance.sh").read_text(encoding="utf-8")
    assert "browser_workers=${PHARMA_BROWSER_WORKERS:-4}" in runner
    assert '"--workers=$browser_workers"' in runner
    assert "browser_projects=(desktop-1440 desktop-1920 tablet-1024 mobile-390)" in runner
    assert "browser acceptance scenarios are incomplete across projects" in runner
