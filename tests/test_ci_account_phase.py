"""Keep independent account acceptance mandatory without occupying the stack job."""

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).parents[1]


def test_accounts_run_once_after_the_frontend_build_with_the_original_driver() -> None:
    workflow = cast(dict[str, Any], yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text()))
    jobs = workflow["jobs"]
    invocations = [
        (name, step)
        for name, job in jobs.items()
        for step in job["steps"]
        if "scripts/run_account_browser_acceptance.py" in step.get("run", "")
    ]
    assert len(invocations) == 1
    owner, account = invocations[0]
    assert owner == "frontend"
    assert account["working-directory"] == "."
    assert account["run"] == (
        "uv run python scripts/run_account_browser_acceptance.py --output /tmp/account-browser-acceptance-report.json"
    )
    assert "if" not in account and not account.get("continue-on-error", False)
    frontend = jobs[owner]
    steps = frontend["steps"]
    build = next(step for step in steps if step.get("run") == "pnpm build")
    assert steps.index(build) < steps.index(account)
    assert frontend["timeout-minutes"] == 15
    assert jobs["two-entry-smoke"]["timeout-minutes"] == "${{ inputs.refresh_visual_baselines && 60 || 45 }}"
    archive = next(step for step in steps if step.get("name") == "Archive account browser evidence")
    assert archive["if"] == "always()"
    assert archive["with"]["path"] == "/tmp/account-browser-acceptance-report.json"  # noqa: S108 - CI path assertion only.
    assert archive["with"]["if-no-files-found"] == "error"
    assert not archive.get("continue-on-error", False)


def test_both_browser_jobs_use_the_same_pinned_setup_without_adding_a_gate() -> None:
    workflow = cast(dict[str, Any], yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text()))
    jobs = workflow["jobs"]
    assert set(jobs) == {
        "backend",
        "frontend",
        "postgres-contract",
        "deployment-contract",
        "two-entry-smoke",
        "security-supply-chain",
    }
    for name in ("frontend", "two-entry-smoke"):
        steps = jobs[name]["steps"]
        setup = next(step for step in steps if "bash scripts/prepare-ci-browser.sh" in step.get("run", ""))
        assert setup.get("working-directory", ".") == "."
        assert setup["env"]["VISUAL_PROFILE_REVIEW"] == (
            "${{ github.event_name == 'workflow_dispatch' && inputs.refresh_visual_baselines }}"
        )
        assert "if" not in setup and not setup.get("continue-on-error", False)
        uv = next(step for step in steps if step.get("name") == "Install pinned uv and Python")
        assert uv["uses"] == "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b"
        assert uv["with"]["version"] == "0.11.28"
        assert any("uv sync --locked --dev" in step.get("run", "") for step in steps)
