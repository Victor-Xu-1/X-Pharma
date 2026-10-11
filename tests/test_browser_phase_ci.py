from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_browser_partition_preserves_original_jobs_workers_and_time_limits() -> None:
    jobs = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]
    assert set(jobs) == {
        "backend",
        "frontend",
        "postgres-contract",
        "deployment-contract",
        "two-entry-smoke",
        "security-supply-chain",
        "company-controlled",
    }
    assert jobs["frontend"]["timeout-minutes"] == 15
    assert jobs["two-entry-smoke"]["timeout-minutes"] == "${{ inputs.refresh_visual_baselines && 60 || 45 }}"
    assert jobs["two-entry-smoke"]["env"]["PHARMA_BROWSER_WORKERS"] == "1"


def test_controlled_browser_checks_are_required_in_the_existing_frontend_job() -> None:
    jobs = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]
    steps = jobs["frontend"]["steps"]
    runners = [step for step in steps if "scripts.run_controlled_browser_acceptance" in step.get("run", "")]
    assert len(runners) == 1
    archives = [step for step in steps if step.get("with", {}).get("name") == "controlled-browser-evidence"]
    assert len(archives) == 1
    assert archives[0]["with"]["if-no-files-found"] == "error"


def test_company_cases_have_a_separate_bounded_no_backend_job_and_mandatory_receipt() -> None:
    jobs = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]
    assert "company-controlled" in jobs
    job = jobs["company-controlled"]
    assert job["timeout-minutes"] == 15
    steps = job["steps"]
    runners = [step for step in steps if "scripts.run_controlled_browser_acceptance" in step.get("run", "")]
    assert len(runners) == 1 and "--phase company-controlled" in runners[0]["run"]
    assert all("docker" not in step.get("run", "") for step in steps)
    archives = [step for step in steps if step.get("with", {}).get("name") == "company-controlled-browser-evidence"]
    assert len(archives) == 1 and archives[0]["with"]["if-no-files-found"] == "error"
    closure = next(
        step["run"]
        for step in jobs["two-entry-smoke"]["steps"]
        if "scripts.browser_phase_cli close" in step.get("run", "")
    )
    assert "--company" in closure


def test_full_stack_requires_partition_closure_before_the_unchanged_mcp_checks() -> None:
    jobs = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]
    steps = jobs["two-entry-smoke"]["steps"]
    run = next(step for step in steps if step.get("id") == "workbench_smoke")["run"]
    assert "--phase full-stack" in run
    closures = [index for index, step in enumerate(steps) if "scripts.browser_phase_cli close" in step.get("run", "")]
    assert len(closures) == 1
    protocol = next(index for index, step in enumerate(steps) if "verify-entry-consistency.sh" in step.get("run", ""))
    assert closures[0] < protocol
    downloads = [step for step in steps if step.get("with", {}).get("name") == "controlled-browser-evidence"]
    assert len(downloads) == 1


def test_browser_phase_is_explicit_and_visual_review_remains_unpartitioned() -> None:
    script = (ROOT / "scripts/run-browser-acceptance.sh").read_text()
    assert "browser_phase=all" in script
    assert '"${assigned_browser_files[@]}"' in script
    assert (
        "Partitioned CI execution requires an output report and cannot update baselines or perform recovery" in script
    )
    assert script.index("scripts.browser_phase_cli prepare") < script.index('browser_user_id=""')
    jobs = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]
    step = next(step for step in jobs["two-entry-smoke"]["steps"] if step.get("id") == "workbench_smoke")
    review, normal = step["run"].split("else", 1)
    assert "--update-snapshots" in review and "--phase" not in review
    assert "--phase full-stack" in normal and "--update-snapshots" not in normal


def test_phase_identity_is_kept_outside_playwright_managed_output() -> None:
    script = (ROOT / "scripts/run-browser-acceptance.sh").read_text()
    assert 'browser_phase_state_dir=$(mktemp -d "$(dirname "$output_dir")/pharma-browser-phase.XXXXXXXX")' in script
    assert script.count('--manifest "$browser_phase_state_dir/phase-manifest.json"') == 2
    assert 'mapfile -t assigned_browser_files < "$browser_phase_state_dir/phase-arguments"' in script
    assert "$output_dir/phase-manifest.json" not in script
