"""Keep independent account acceptance mandatory without occupying the stack job."""

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).parents[1]
NODE_SETUP = "actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1"
UV_SETUP = "astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884"


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
    """Retain both original owners and apply the same constraints to the extra isolated UI owner."""
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
    for name in ("frontend", "two-entry-smoke", "company-controlled"):
        steps = jobs[name]["steps"]
        preparations = [step for step in steps if "bash scripts/prepare-ci-browser.sh" in step.get("run", "")]
        assert len(preparations) == 1
        setup = preparations[0]
        assert setup.get("working-directory", ".") == "."
        assert setup["env"]["VISUAL_PROFILE_REVIEW"] == (
            "${{ github.event_name == 'workflow_dispatch' && inputs.refresh_visual_baselines }}"
        )
        assert "if" not in setup and not setup.get("continue-on-error", False)
        uv = next(step for step in steps if step.get("name") == "Install pinned uv and Python")
        assert uv["uses"] == UV_SETUP
        assert uv["with"]["version"] == "0.11.28"
        assert any("uv sync --locked --dev" in step.get("run", "") for step in steps)
        node = next(step for step in steps if step.get("uses", "").startswith("actions/setup-node@"))
        assert node["uses"] == NODE_SETUP
        assert node["with"]["node-version"] == "24.14.0"
        pnpm = next(step for step in steps if step.get("uses", "").startswith("pnpm/action-setup@"))
        assert pnpm["uses"] == "pnpm/action-setup@0ebf47130e4866e96fce0953f49152a61190b271"
        assert pnpm["with"]["version"] == "11.7.0"


def test_ci_and_version_reconciliation_keep_one_exact_node_action_and_runtime() -> None:
    for filename, expected_owners in (("ci.yml", 4), ("product-version.yml", 1)):
        workflow = cast(dict[str, Any], yaml.safe_load((ROOT / ".github/workflows" / filename).read_text()))
        setups = [
            step
            for job in workflow["jobs"].values()
            for step in job["steps"]
            if step.get("uses", "").startswith("actions/setup-node@")
        ]
        assert len(setups) == expected_owners
        for setup in setups:
            assert setup["uses"] == NODE_SETUP
            assert setup["with"]["node-version"] == "24.14.0"


def test_ci_and_version_reconciliation_keep_one_exact_uv_action_and_runtime() -> None:
    assert (ROOT / ".python-version").read_text().strip() == "3.13.16"
    for filename, expected_owners in (("ci.yml", 7), ("product-version.yml", 1)):
        workflow = cast(dict[str, Any], yaml.safe_load((ROOT / ".github/workflows" / filename).read_text()))
        setups = [
            step
            for job in workflow["jobs"].values()
            for step in job["steps"]
            if step.get("uses", "").startswith("astral-sh/setup-uv@")
        ]
        assert len(setups) == expected_owners
        for setup in setups:
            assert setup["uses"] == UV_SETUP
            assert setup["with"]["version"] == "0.11.28"
            assert "python-version" not in setup["with"]
